import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:html/parser.dart' as html;

import '../domain/race_event.dart';

abstract interface class CalendarRepository {
  Future<CalendarData> load();
  Future<EventResults> loadResults(RaceEvent event);
  Future<StandingsData> loadStandings(String seriesId, int season);
}

class ResultsUnavailableException implements Exception {
  const ResultsUnavailableException(this.eventId);
  final String eventId;

  @override
  String toString() => 'Results could not be downloaded for $eventId';
}

/// Every season of a manifest entry. `publishedSeasons` lists all seasons
/// with data (e.g. the next season's calendar); `availableSeasons` holds
/// only the current one so older app versions keep working.
List<int> manifestSeasons(Map<String, dynamic> series) =>
    ((series['publishedSeasons'] ?? series['availableSeasons'])
            as List<dynamic>)
        .cast<int>()
        .toSet()
        .toList()
      ..sort();

StandingsData _standingsFrom(
  Map<String, dynamic> drivers,
  Map<String, dynamic> teams,
) {
  final driverUpdate = DateTime.tryParse(
    drivers['lastSuccessfulUpdate'] as String? ?? '',
  );
  final teamUpdate = DateTime.tryParse(
    teams['lastSuccessfulUpdate'] as String? ?? '',
  );
  return StandingsData(
    sourceUpdatedAt: driverUpdate == null || teamUpdate == null
        ? null
        : (drivers: driverUpdate.toUtc(), teams: teamUpdate.toUtc()),
    drivers: (drivers['data'] as List<dynamic>)
        .map((item) => DriverStanding.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
    teams: (teams['data'] as List<dynamic>)
        .map((item) => TeamStanding.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
  );
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
    final calendars = await Future.wait([
      for (final item in manifest['availableSeries'] as List<dynamic>)
        for (final season in manifestSeasons(item as Map<String, dynamic>))
          _json('assets/data/${item['id']}/$season/calendar.json'),
    ]);
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
  Future<StandingsData> loadStandings(String seriesId, int season) async {
    final seasonRoot = 'assets/data/$seriesId/$season';
    try {
      final documents = await Future.wait([
        _json('$seasonRoot/standings_drivers.json'),
        _json('$seasonRoot/standings_teams.json'),
      ]);
      return _standingsFrom(documents[0], documents[1]);
    } on Object {
      // A season that has not started yet ships no standings.
      return const StandingsData(drivers: [], teams: []);
    }
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
  CalendarData? _lastCalendar;

  Future<Map<String, dynamic>?> _absoluteJson(Uri uri) async {
    try {
      final response = await _client
          .get(uri)
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } on Object {
      // Live reads are best-effort and always retain the verified fallback.
    }
    return null;
  }

  Future<Map<String, dynamic>?> _remote(String path) async {
    try {
      // The query parameter bypasses caches. Custom request headers are
      // avoided: on the web they trigger a CORS preflight that GitHub's raw
      // file host rejects, which silently disabled live data there.
      final uri = _dataRoot
          .resolve(path)
          .replace(
            queryParameters: {
              'refresh': DateTime.now().millisecondsSinceEpoch.toString(),
            },
          );
      final response = await _client
          .get(uri)
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
    var local = _lastCalendar ?? await fallback.load();
    try {
      final manifest = await _remote('manifest.json');
      if (manifest == null) return _lastCalendar ?? local;
      final sources = {
        for (final item in manifest['availableSeries'] as List<dynamic>)
          for (final season in manifestSeasons(item as Map<String, dynamic>))
            (seriesId: item['id'] as String, season: season),
      }.toList();
      final calendars = await Future.wait([
        for (final source in sources)
          _loadCalendarSource(source, local.schemaVersion),
      ]);
      local = _lastCalendar ?? local;
      final events = [...local.events];
      final updates = {
        for (final event in local.events)
          (seriesId: event.seriesId, season: event.season):
              local.sourceUpdatedAt[(
                seriesId: event.seriesId,
                season: event.season,
              )] ??
              local.updatedAt,
      };
      var updatedAt = local.updatedAt;
      for (var index = 0; index < sources.length; index++) {
        final source = sources[index];
        final calendar = calendars[index];
        final bundledUpdate = updates[source];
        if (calendar == null ||
            (bundledUpdate != null &&
                !calendar.updatedAt.isAfter(bundledUpdate))) {
          continue;
        }
        events.removeWhere(
          (event) =>
              event.seriesId == source.seriesId &&
              event.season == source.season,
        );
        events.addAll(calendar.events);
        updates[source] = calendar.updatedAt;
        if (calendar.updatedAt.isAfter(updatedAt)) {
          updatedAt = calendar.updatedAt;
        }
      }
      events.sort((a, b) => a.startsAt.compareTo(b.startsAt));
      final updated = CalendarData(
        schemaVersion: local.schemaVersion,
        updatedAt: updatedAt,
        events: events,
        sourceUpdatedAt: updates,
      );
      _lastCalendar = updated;
      return updated;
    } on FormatException catch (error) {
      debugPrint('Invalid published calendar manifest: $error');
      return _lastCalendar ?? local;
    } on TypeError catch (error) {
      debugPrint('Invalid published calendar manifest: $error');
      return _lastCalendar ?? local;
    }
  }

  Future<CalendarData?> _loadCalendarSource(
    CalendarSource source,
    int schemaVersion,
  ) async {
    final path = '${source.seriesId}/${source.season}/calendar.json';
    final document = await _remote(path);
    if (document == null) {
      debugPrint('Calendar $path unavailable; keeping its bundled data');
      return null;
    }
    try {
      final calendar = CalendarData.fromJson(document);
      if (calendar.schemaVersion != schemaVersion ||
          calendar.events.isEmpty ||
          calendar.events.any(
            (event) =>
                event.seriesId != source.seriesId ||
                event.season != source.season ||
                event.sessions.isEmpty,
          ) ||
          calendar.events.map((event) => event.id).toSet().length !=
              calendar.events.length) {
        throw const FormatException(
          'Incomplete, mismatched or duplicate calendar events',
        );
      }
      return calendar;
    } on FormatException catch (error) {
      debugPrint('Rejected calendar $path: $error');
    } on TypeError catch (error) {
      debugPrint('Rejected calendar $path: $error');
    }
    return null;
  }

  @override
  Future<EventResults> loadResults(RaceEvent event) async {
    EventResults? remote;
    try {
      final json = await _remote(
        '${event.seriesId}/${event.season}/${event.resultsPath}',
      );
      if (json != null) {
        final result = EventResults.fromJson(json);
        // A missing optional flag must never hide an otherwise valid official
        // classification. Metadata is enriched separately. An event mismatch,
        // however, means the classification belongs to a different round.
        if (result.eventId == event.id) {
          remote = result;
        } else {
          debugPrint(
            'Rejected results for ${result.eventId}; expected ${event.id}',
          );
        }
      }
    } on FormatException catch (error) {
      debugPrint('Invalid published results for ${event.id}: $error');
    } on TypeError catch (error) {
      debugPrint('Invalid published results for ${event.id}: $error');
    }

    EventResults? local;
    try {
      local = await fallback.loadResults(event);
    } on FlutterError catch (error) {
      // A newly announced event is not in an already-installed app bundle.
      // Its valid online document must not depend on that file existing.
      if (!error.message.contains('Unable to load asset:') ||
          !error.message.contains(event.resultsPath)) {
        rethrow;
      }
      debugPrint('No bundled results for ${event.id}; online data is required');
    } on FormatException catch (error) {
      debugPrint('Invalid bundled results for ${event.id}: $error');
    } on TypeError catch (error) {
      debugPrint('Invalid bundled results for ${event.id}: $error');
    }
    final base = local ?? EventResults(eventId: event.id, sessions: const []);
    final selected = remote == null
        ? base
        : _mergeVerifiedResults(event, base, remote);
    final loaded = event.seriesId == 'f1'
        ? await _withLiveF1Results(event, selected)
        : selected;
    if (local == null && remote == null && loaded.sessions.isEmpty) {
      throw ResultsUnavailableException(event.id);
    }
    return _onlyCompletedScheduledSessions(event, loaded);
  }

  EventResults _mergeVerifiedResults(
    RaceEvent event,
    EventResults bundled,
    EventResults remote,
  ) {
    // A CDN/cache can temporarily return an older event document. Never let
    // an empty or partial response erase a classification already shipped in
    // the app. A verified non-classification notice resolves an otherwise
    // empty session, but cannot erase actual classification rows.
    final merged = <String, SessionResults>{
      for (final session in bundled.sessions)
        if (session.hasPublishedOutcome) session.type: session,
    };
    for (final session in remote.sessions) {
      final previous = merged[session.type];
      if (session.hasPublishedOutcome &&
          !(previous != null &&
              previous.results.isNotEmpty &&
              session.results.isEmpty)) {
        merged[session.type] = session;
      }
    }
    final order = {
      for (var index = 0; index < event.sessions.length; index++)
        event.sessions[index].type: index,
    };
    final sessions = merged.values.toList()
      ..sort((a, b) => (order[a.type] ?? 999).compareTo(order[b.type] ?? 999));
    return EventResults(eventId: event.id, sessions: sessions);
  }

  EventResults _onlyCompletedScheduledSessions(
    RaceEvent event,
    EventResults results,
  ) {
    final now = DateTime.now().toUtc();
    final scheduled = {
      for (final session in event.sessions) session.type: session,
    };
    final verified = results.sessions
        .where((result) {
          final session = scheduled[result.type];
          return session != null &&
              !session.cancelled &&
              !(event.seriesId == 'f1' && result.noClassificationReason == null
                      ? session.startTimeUtc
                      : session.expectedEnd)
                  .isAfter(now) &&
              result.hasPublishedOutcome;
        })
        .toList(growable: false);
    return EventResults(eventId: event.id, sessions: verified);
  }

  Future<EventResults> _withLiveF1Results(
    RaceEvent event,
    EventResults base,
  ) async {
    base = await _withOfficialF1Results(event, base);
    final now = DateTime.now().toUtc();
    final available = {
      for (final session in base.sessions)
        if (session.hasPublishedOutcome) session.type,
    };
    final missing = event.sessions.where(
      (session) =>
          !session.cancelled &&
          !available.contains(session.type) &&
          !session.expectedEnd.isAfter(now),
    );
    if (missing.isEmpty) return base;

    final fresh = <SessionResults>[];
    for (final session in missing) {
      final code = session.type == 'SPRINT' ? 'SR' : session.type;
      final payload = await _absoluteJson(
        Uri.parse('https://api.jolpi.ca/f1/alpha/results/${event.id}/$code/'),
      );
      final data = payload?['data'];
      if (data is! Map<String, dynamic> || data['results'] is! List) continue;
      try {
        final rows = (data['results'] as List<dynamic>)
            .map((item) {
              final raw = item as Map<String, dynamic>;
              final driver = raw['driver'] as Map<String, dynamic>;
              final team = raw['team'] as Map<String, dynamic>;
              final color = team['primary_color'] as String?;
              return {
                'position': (raw['position'] as num?)?.toInt(),
                'positionText': raw['position_text']?.toString(),
                'driver': {
                  'id': driver['id'],
                  'code': driver['abbreviation'],
                  'givenName': driver['given_name'],
                  'familyName': driver['family_name'],
                  'nationality':
                      driver['country_code'] ?? driver['nationality'],
                },
                'team': {
                  'id': team['id'],
                  'name': team['name'],
                  'color': color == null || color.startsWith('#')
                      ? color
                      : '#$color',
                },
                'time': raw['time']?.toString(),
                'points': raw['points'],
                'status': raw['status']?.toString(),
                'components': raw['components'] ?? <String, dynamic>{},
              };
            })
            .toList(growable: false);
        if (rows.isEmpty) continue;
        fresh.add(
          SessionResults.fromJson({
            'type': session.type,
            'name': data['title']?.toString() ?? session.name,
            'startTimeUtc':
                data['timestamp']?.toString() ??
                session.startTimeUtc.toIso8601String(),
            'results': rows,
          }),
        );
      } on Object {
        // Reject malformed live data instead of replacing verified data.
      }
    }
    if (fresh.isEmpty) return base;
    final merged = <String, SessionResults>{
      for (final session in base.sessions) session.type: session,
      for (final session in fresh) session.type: session,
    };
    final order = {
      for (var index = 0; index < event.sessions.length; index++)
        event.sessions[index].type: index,
    };
    final sessions = merged.values.toList()
      ..sort((a, b) => (order[a.type] ?? 999).compareTo(order[b.type] ?? 999));
    return EventResults(eventId: event.id, sessions: sessions);
  }

  Future<EventResults> _withOfficialF1Results(
    RaceEvent event,
    EventResults base,
  ) async {
    final now = DateTime.now().toUtc();
    final received = {
      for (final session in base.sessions)
        if (session.hasPublishedOutcome) session.type,
    };
    final missing = event.sessions
        .where(
          (s) =>
              !s.cancelled &&
              !s.startTimeUtc.isAfter(now) &&
              !received.contains(s.type),
        )
        .toList();
    if (missing.isEmpty) return base;
    Future<String?> page(String path) async {
      try {
        final uri =
            Uri.parse(
              'https://www.formula1.com/en/results/${event.season}/$path',
            ).replace(
              queryParameters: {
                'refresh': now.millisecondsSinceEpoch.toString(),
              },
            );
        final response = await _client
            .get(uri)
            .timeout(const Duration(seconds: 8));
        return response.statusCode == 200 ? response.body : null;
      } on Object {
        return null;
      }
    }

    final index = await page('races');
    if (index == null) return base;
    final paths = RegExp(
      '/en/results/${event.season}/races/(\\d+)/([^/"?]+)/race-result',
    ).allMatches(index).map((m) => '${m[1]}/${m[2]}').toSet().toList();
    const slugs = {
      'Australian': 'australia',
      'Chinese': 'china',
      'Japanese': 'japan',
      'Canadian': 'canada',
      'Barcelona': 'barcelona-catalunya',
      'Austrian': 'austria',
      'British': 'great-britain',
      'Belgian': 'belgium',
      'Hungarian': 'hungary',
      'Dutch': 'netherlands',
      'Italian': 'italy',
      'Spanish': 'spain',
      'Mexico City': 'mexico',
      'Brazilian': 'brazil',
    };
    final name = event.name.split(' Grand Prix').first;
    final slug = slugs[name] ?? name.toLowerCase().replaceAll(' ', '-');
    final matching = paths.where((p) => p.split('/').last == slug);
    if (matching.length != 1) return base;
    final path = matching.single;
    final standings = await loadStandings('f1', event.season);
    final drivers = {for (final d in standings.drivers) d.code: d};
    const routes = {
      'FP1': 'practice/1',
      'FP2': 'practice/2',
      'FP3': 'practice/3',
      'Q': 'qualifying',
      'SQ': 'sprint-qualifying',
      'SPRINT': 'sprint-results',
      'R': 'race-result',
    };
    final fresh = <SessionResults>[];
    for (final session in missing) {
      final route = routes[session.type];
      if (route == null) continue;
      final body = await page('races/$path/$route');
      if (body == null) continue;
      final rows = <Map<String, dynamic>>[];
      for (final tr in html.parse(body).querySelectorAll('table tr')) {
        final cells = tr
            .querySelectorAll('td')
            .map((td) => td.text.replaceAll(RegExp(r'\s+'), ' ').trim())
            .toList();
        if (cells.length < 5 || int.tryParse(cells[1]) == null) continue;
        final match = RegExp(r'([A-Z]{3})$').firstMatch(cells[2]);
        final driver = drivers[match?[1]];
        if (driver == null) {
          continue; // Never guess an unknown driver's identity.
        }
        final timed = cells
            .skip(4)
            .where((v) => RegExp(r'^(?:\d+:)?\d+\.\d+$').hasMatch(v))
            .toList();
        rows.add({
          'position': int.tryParse(cells[0]),
          'positionText': cells[0],
          'driver': {
            'id': driver.id,
            'code': driver.code,
            'givenName': driver.givenName,
            'familyName': driver.familyName,
            'nationality': driver.nationality,
          },
          'team': {
            'name': cells[3],
            'id': driver.teamIds.firstOrNull,
            'color': driver.teamColors.firstOrNull,
          },
          'time': {'Q', 'SQ'}.contains(session.type)
              ? (timed.isEmpty ? null : timed.last)
              : cells.length > 5 && {'R', 'SPRINT'}.contains(session.type)
              ? cells[5]
              : cells[4],
          'points': {'R', 'SPRINT'}.contains(session.type)
              ? double.tryParse(cells.last)
              : null,
          'components': <String, dynamic>{},
        });
      }
      if (rows.isNotEmpty) {
        fresh.add(
          SessionResults.fromJson({
            'type': session.type,
            'name': session.name,
            'startTimeUtc': session.startTimeUtc.toIso8601String(),
            'results': rows,
          }),
        );
      }
    }
    return EventResults(
      eventId: event.id,
      sessions: [...base.sessions, ...fresh],
    );
  }

  @override
  Future<StandingsData> loadStandings(String seriesId, int season) async {
    final local = await fallback.loadStandings(seriesId, season);
    try {
      final documents = await Future.wait([
        _remote('$seriesId/$season/standings_drivers.json'),
        _remote('$seriesId/$season/standings_teams.json'),
      ]);
      if (documents.any((document) => document == null)) {
        return local;
      }
      final remote = _standingsFrom(documents[0]!, documents[1]!);
      final localDrivers = {
        for (final driver in local.drivers) driver.id: driver,
      };
      final enrichedRemote = StandingsData(
        sourceUpdatedAt: remote.sourceUpdatedAt,
        drivers: remote.drivers
            .map((driver) {
              final bundled = localDrivers[driver.id];
              return DriverStanding(
                position: driver.position,
                points: driver.points,
                wins: driver.wins,
                id: driver.id,
                code: driver.code,
                givenName: driver.givenName,
                familyName: driver.familyName,
                nationality: driver.nationality,
                teamIds: driver.teamIds,
                teamNames: driver.teamNames,
                teamColors: driver.teamColors,
                category: driver.category,
                // Bundled portraits are verified face crops. Remote feeds may
                // contain full-body promotional images, so never let them replace
                // the curated headshot shipped with the app.
                imageUrl: bundled?.imageUrl ?? driver.imageUrl,
              );
            })
            .toList(growable: false),
        teams: remote.teams,
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
      final localUpdate = local.sourceUpdatedAt;
      final remoteUpdate = remote.sourceUpdatedAt;
      if (localUpdate != null &&
          remoteUpdate != null &&
          (remoteUpdate.drivers.isBefore(localUpdate.drivers) ||
              remoteUpdate.teams.isBefore(localUpdate.teams))) {
        return local;
      }
      final newer =
          localUpdate != null &&
          remoteUpdate != null &&
          (remoteUpdate.drivers.isAfter(localUpdate.drivers) ||
              remoteUpdate.teams.isAfter(localUpdate.teams));
      final complete =
          remote.drivers.length >= local.drivers.length &&
          remote.teams.length >= local.teams.length &&
          ((remoteMaxPoints >= localMaxPoints && remoteWins >= localWins) ||
              newer);
      return complete ? enrichedRemote : local;
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
    sourceUpdatedAt: {
      for (final calendar in calendars) ...calendar.sourceUpdatedAt,
    },
  );
}
