import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../domain/race_event.dart';

abstract interface class CalendarRepository {
  Future<CalendarData> load();
  Future<EventResults> loadResults(RaceEvent event);
  Future<StandingsData> loadStandings();
}

class AssetCalendarRepository implements CalendarRepository {
  AssetCalendarRepository({AssetBundle? bundle})
    : _bundle = bundle ?? rootBundle;

  static const _seasonRoot = 'assets/data/f1/2026';
  final AssetBundle _bundle;

  Future<Map<String, dynamic>> _json(String path) async {
    final raw = await _bundle.loadString(path);
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  @override
  Future<CalendarData> load() async =>
      CalendarData.fromJson(await _json('$_seasonRoot/calendar.json'));

  @override
  Future<EventResults> loadResults(RaceEvent event) async =>
      EventResults.fromJson(await _json('$_seasonRoot/${event.resultsPath}'));

  @override
  Future<StandingsData> loadStandings() async {
    final documents = await Future.wait([
      _json('$_seasonRoot/standings_drivers.json'),
      _json('$_seasonRoot/standings_teams.json'),
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

  static final _root = Uri.parse(
    'https://raw.githubusercontent.com/SoY256/MotorSport-Calendar/main/data/f1/2026/',
  );

  final CalendarRepository fallback;
  final http.Client _client;

  Future<Map<String, dynamic>?> _remote(String path) async {
    try {
      final response = await _client
          .get(_root.resolve(path))
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
    final json = await _remote('calendar.json');
    return json == null ? fallback.load() : CalendarData.fromJson(json);
  }

  @override
  Future<EventResults> loadResults(RaceEvent event) async {
    final json = await _remote(event.resultsPath);
    return json == null
        ? fallback.loadResults(event)
        : EventResults.fromJson(json);
  }

  @override
  Future<StandingsData> loadStandings() async {
    final documents = await Future.wait([
      _remote('standings_drivers.json'),
      _remote('standings_teams.json'),
    ]);
    if (documents.any((document) => document == null)) {
      return fallback.loadStandings();
    }
    return StandingsData(
      drivers: (documents[0]!['data'] as List<dynamic>)
          .map((item) => DriverStanding.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
      teams: (documents[1]!['data'] as List<dynamic>)
          .map((item) => TeamStanding.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
    );
  }
}
