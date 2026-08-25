import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../domain/race_event.dart';

abstract interface class CalendarRepository {
  Future<CalendarData> load();
  Future<EventResults> loadResults(RaceEvent event);
  Future<StandingsData> loadStandings(String seriesId);
}

class AssetCalendarRepository implements CalendarRepository {
  AssetCalendarRepository({AssetBundle? bundle})
    : _bundle = bundle ?? rootBundle;

  final AssetBundle _bundle;

  Future<Map<String, dynamic>> _json(String path) async {
    final raw = await _bundle.loadString(path);
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  @override
  Future<CalendarData> load() async {
    final manifest = await _json('assets/data/manifest.json');
    final calendars = await Future.wait(
      (manifest['availableSeries'] as List<dynamic>).map((item) {
        final series = item as Map<String, dynamic>;
        final id = series['id'] as String;
        final seasons = (series['availableSeasons'] as List<dynamic>)
            .cast<int>();
        final season = seasons.reduce((a, b) => a > b ? a : b);
        return _json('assets/data/$id/$season/calendar.json');
      }),
    );
    return _mergeCalendars(calendars);
  }

  @override
  Future<EventResults> loadResults(RaceEvent event) async =>
      EventResults.fromJson(
        await _json(
          'assets/data/${event.seriesId}/${event.season}/${event.resultsPath}',
        ),
      );

  @override
  Future<StandingsData> loadStandings(String seriesId) async {
    final seasonRoot = 'assets/data/$seriesId/2026';
    final documents = await Future.wait([
      _json('$seasonRoot/standings_drivers.json'),
      _json('$seasonRoot/standings_teams.json'),
    ]);
    return StandingsData(
      drivers: (documents[0]['data'] as List<dynamic>)
          .map((item) => DriverStanding.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
      teams: (documents[1]['data'] as List<dynamic>)
          .map((item) => TeamStanding.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}

class NetworkFirstCalendarRepository implements CalendarRepository {
  NetworkFirstCalendarRepository({required this.fallback, http.Client? client})
    : _client = client ?? http.Client();

  static final _dataRoot = Uri.parse(
    'https://raw.githubusercontent.com/SoY256/MotorSport-Calendar/main/data/',
  );

  final CalendarRepository fallback;
  final http.Client _client;

  Future<Map<String, dynamic>?> _remote(String path) async {
    try {
      final uri = _dataRoot
          .resolve(path)
          .replace(
            queryParameters: {
              'refresh': DateTime.now().millisecondsSinceEpoch.toString(),
            },
          );
      final response = await _client
          .get(uri, headers: const {'Cache-Control': 'no-cache'})
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } on Object {
      // Every network read has an asset fallback.
    }
    return null;
  }

  @override
  Future<CalendarData> load() async {
    final local = await fallback.load();
    try {
      final manifest = await _remote('manifest.json');
      if (manifest == null) return local;
      final calendars = await Future.wait(
        (manifest['availableSeries'] as List<dynamic>).map((item) {
          final series = item as Map<String, dynamic>;
          final id = series['id'] as String;
          final seasons = (series['availableSeasons'] as List<dynamic>)
              .cast<int>();
          final season = seasons.reduce((a, b) => a > b ? a : b);
          return _remote('$id/$season/calendar.json');
        }),
      );
      if (calendars.any((calendar) => calendar == null)) return local;
      final remote = _mergeCalendars(calendars.cast<Map<String, dynamic>>());
      if (!remote.updatedAt.isAfter(local.updatedAt)) return local;
      final events = <String, RaceEvent>{
        for (final event in local.events) event.id: event,
        for (final event in remote.events) event.id: event,
      }.values.toList()..sort((a, b) => a.startsAt.compareTo(b.startsAt));
      return CalendarData(
        schemaVersion: local.schemaVersion,
        updatedAt: remote.updatedAt.isAfter(local.updatedAt)
            ? remote.updatedAt
            : local.updatedAt,
        events: events,
      );
    } on Object {
      return local;
    }
  }

  @override
  Future<EventResults> loadResults(RaceEvent event) async {
    try {
      final json = await _remote('${event.seriesId}/2026/${event.resultsPath}');
      if (json == null) return await fallback.loadResults(event);
      final remote = EventResults.fromJson(json);
      final hasIncompleteDrivers = remote.sessions
          .expand((session) => session.results)
          .any((result) => (result.driver.nationality ?? '').isEmpty);
      return hasIncompleteDrivers ? await fallback.loadResults(event) : remote;
    } on Object {
      return await fallback.loadResults(event);
    }
  }

  @override
  Future<StandingsData> loadStandings(String seriesId) async {
    final local = await fallback.loadStandings(seriesId);
    try {
      final documents = await Future.wait([
        _remote('$seriesId/2026/standings_drivers.json'),
        _remote('$seriesId/2026/standings_teams.json'),
      ]);
      if (documents.any((document) => document == null)) {
        return local;
      }
      final remote = StandingsData(
        drivers: (documents[0]!['data'] as List<dynamic>)
            .map(
              (item) => DriverStanding.fromJson(item as Map<String, dynamic>),
            )
            .toList(growable: false),
        teams: (documents[1]!['data'] as List<dynamic>)
            .map((item) => TeamStanding.fromJson(item as Map<String, dynamic>))
            .toList(growable: false),
      );
      final localMaxPoints = local.drivers.fold<double>(
        0,
        (value, item) => item.points > value ? item.points : value,
      );
      final remoteMaxPoints = remote.drivers.fold<double>(
        0,
        (value, item) => item.points > value ? item.points : value,
      );
      final localWins = local.drivers.fold<int>(
        0,
        (value, item) => value + item.wins,
      );
      final remoteWins = remote.drivers.fold<int>(
        0,
        (value, item) => value + item.wins,
      );
      final complete =
          remote.drivers.length >= local.drivers.length &&
          remote.teams.length >= local.teams.length &&
          remoteMaxPoints >= localMaxPoints &&
          remoteWins >= localWins;
      return complete ? remote : local;
    } on Object {
      return local;
    }
  }
}

CalendarData _mergeCalendars(List<Map<String, dynamic>> documents) {
  final calendars = documents.map(CalendarData.fromJson).toList();
  final events = calendars.expand((calendar) => calendar.events).toList()
    ..sort((a, b) => a.startsAt.compareTo(b.startsAt));
  final updatedAt = calendars
      .map((calendar) => calendar.updatedAt)
      .reduce((a, b) => a.isAfter(b) ? a : b);
  return CalendarData(
    schemaVersion: calendars.first.schemaVersion,
    updatedAt: updatedAt,
    events: events,
  );
}
