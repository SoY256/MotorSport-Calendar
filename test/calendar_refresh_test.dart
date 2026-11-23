import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secar/features/calendar/data/calendar_repository.dart';

Map<String, dynamic> _manifest() => {
  'availableSeries': [
    for (final series in ['f1', 'wec'])
      {
        'id': series,
        'availableSeasons': [2026],
      },
  ],
};

Map<String, dynamic> _calendar(
  String series,
  int hour,
  List<String> ids, {
  int season = 2026,
}) => {
  'schemaVersion': 1,
  'lastSuccessfulUpdate': DateTime.utc(2026, 11, 23, hour).toIso8601String(),
  'data': [
    for (final id in ids)
      {
        'id': id,
        'seriesId': series,
        'season': season,
        'round': 1,
        'name': id,
        'circuit': {'name': 'Test Raceway'},
        'sessions': [
          {'type': 'R', 'name': 'Race', 'startTimeUtc': '2026-11-22T12:00:00Z'},
        ],
        'resultsPath': 'events/$id.json',
      },
  ],
};

class _CalendarBundle extends CachingAssetBundle {
  _CalendarBundle(this.documents);
  final Map<String, Map<String, dynamic>> documents;

  @override
  Future<ByteData> load(String key) async {
    final document = documents[key];
    if (document == null) throw FlutterError('Unable to load asset: "$key".');
    return ByteData.sublistView(
      Uint8List.fromList(utf8.encode(jsonEncode(document))),
    );
  }
}

NetworkFirstCalendarRepository _repository({
  required Map<String, Map<String, dynamic>> published,
  List<String> bundledF1 = const ['old-f1'],
  Map<String, dynamic>? publishedManifest,
  http.Client? client,
}) => NetworkFirstCalendarRepository(
  fallback: AssetCalendarRepository(
    bundle: _CalendarBundle({
      'assets/data/manifest.json': _manifest(),
      'assets/data/f1/2026/calendar.json': _calendar('f1', 10, bundledF1),
      'assets/data/wec/2026/calendar.json': _calendar('wec', 20, ['old-wec']),
    }),
  ),
  client:
      client ??
      MockClient((request) async {
        final path = request.url.path.split('/data/').last;
        final value = path == 'manifest.json'
            ? publishedManifest ?? _manifest()
            : published[path];
        return value == null
            ? http.Response('Temporarily unavailable', 503)
            : http.Response(jsonEncode(value), 200);
      }),
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('a later outage retains the last verified online calendar, not older bundled rounds', () async {
    final published = {
      'f1/2026/calendar.json': _calendar('f1', 21, ['new-f1']),
    };
    final repository = _repository(published: published);
    final first = await repository.load();
    published.clear();
    final offline = await repository.load();
    expect(
      first.events.map((event) => event.id),
      unorderedEquals(['new-f1', 'old-wec']),
    );
    expect(
      offline.events.map((event) => event.id),
      unorderedEquals(['new-f1', 'old-wec']),
    );
  });

  test(
    'an overlapping older response cannot replace a newer completed refresh',
    () async {
      final pending = Completer<http.Response>();
      final requested = Completer<void>();
      var reads = 0;
      final repository = _repository(
        published: {},
        client: MockClient((request) async {
          if (request.url.path.endsWith('manifest.json')) {
            return http.Response(jsonEncode(_manifest()), 200);
          }
          if (request.url.path.endsWith('f1/2026/calendar.json')) {
            if (reads++ == 0) {
              requested.complete();
              return pending.future;
            }
            return http.Response(
              jsonEncode(_calendar('f1', 22, ['latest-f1'])),
              200,
            );
          }
          return http.Response('', 503);
        }),
      );
      final olderRequest = repository.load();
      await requested.future;
      final latest = await repository.load();
      pending.complete(
        http.Response(jsonEncode(_calendar('f1', 21, ['older-f1'])), 200),
      );
      final delayed = await olderRequest;
      expect(
        latest.events.map((event) => event.id),
        unorderedEquals(['latest-f1', 'old-wec']),
      );
      expect(
        delayed.events.map((event) => event.id),
        unorderedEquals(['latest-f1', 'old-wec']),
      );
    },
  );

  test(
    'an outage in one series does not block another series update',
    () async {
      final data = await _repository(
        published: {
          'f1/2026/calendar.json': _calendar('f1', 21, ['new-f1']),
        },
      ).load();
      expect(
        data.events.map((event) => event.id),
        unorderedEquals(['new-f1', 'old-wec']),
      );
    },
  );

  test('freshness is compared per series, not against the newest unrelated calendar', () async {
    final data = await _repository(
      published: {
        'f1/2026/calendar.json': _calendar('f1', 15, ['new-f1']),
        'wec/2026/calendar.json': _calendar('wec', 20, ['old-wec']),
      },
    ).load();
    expect(
      data.events.map((event) => event.id),
      unorderedEquals(['new-f1', 'old-wec']),
    );
    expect(data.updatedAt, DateTime.utc(2026, 11, 23, 20));
  });

  test('a removed round does not reappear from bundled data', () async {
    final data = await _repository(
      bundledF1: ['kept-f1', 'removed-f1'],
      published: {
        'f1/2026/calendar.json': _calendar('f1', 21, ['kept-f1']),
        'wec/2026/calendar.json': _calendar('wec', 21, ['old-wec']),
      },
    ).load();
    expect(
      data.events.map((event) => event.id),
      unorderedEquals(['kept-f1', 'old-wec']),
    );
  });

  test('an older response cannot roll a single series back', () async {
    final data = await _repository(
      published: {
        'f1/2026/calendar.json': _calendar('f1', 9, ['stale-f1']),
        'wec/2026/calendar.json': _calendar('wec', 21, ['new-wec']),
      },
    ).load();
    expect(
      data.events.map((event) => event.id),
      unorderedEquals(['old-f1', 'new-wec']),
    );
  });

  test('a newly announced season is not compared against an unrelated bundled timestamp', () async {
    final data = await _repository(
      publishedManifest: {
        'availableSeries': [
          {
            'id': 'f1',
            'publishedSeasons': [2026, 2027],
          },
        ],
      },
      published: {
        'f1/2027/calendar.json': _calendar('f1', 9, [
          'next-year-f1',
        ], season: 2027),
      },
    ).load();
    expect(
      data.events.map((event) => event.id),
      unorderedEquals(['old-f1', 'old-wec', 'next-year-f1']),
    );
    expect(
      data.events.singleWhere((event) => event.id == 'next-year-f1').season,
      2027,
    );
  });

  for (final (label, invalid) in [
    ('empty feed', _calendar('wec', 21, [])),
    ('different series', _calendar('f1', 21, ['foreign-round'])),
    ('duplicate rounds', _calendar('wec', 21, ['duplicate', 'duplicate'])),
    (
      'malformed timestamp',
      {
        ..._calendar('wec', 21, ['new-wec']),
        'lastSuccessfulUpdate': 'invalid',
      },
    ),
    (
      'unsupported schema',
      {
        ..._calendar('wec', 21, ['new-wec']),
        'schemaVersion': 2,
      },
    ),
  ]) {
    test(
      '$label keeps its own fallback without blocking a healthy source',
      () async {
        final data = await _repository(
          published: {
            'f1/2026/calendar.json': _calendar('f1', 21, ['new-f1']),
            'wec/2026/calendar.json': invalid,
          },
        ).load();
        expect(
          data.events.map((event) => event.id),
          unorderedEquals(['new-f1', 'old-wec']),
        );
      },
    );
  }

  Map<String, dynamic> standings(
    int hour,
    double points, {
    bool teams = false,
  }) => {
    'lastSuccessfulUpdate': DateTime.utc(2026, 11, 23, hour).toIso8601String(),
    'data': [
      for (var index = 0; index < 2; index++)
        {
          'id': '${teams ? 'team' : 'driver'}-$index',
          'position': index + 1,
          'points': points - index,
          'wins': points > 100 ? 2 : 1,
          if (teams)
            'name': 'Team $index'
          else ...{
            'givenName': 'Driver',
            'familyName': '$index',
            'teamIds': ['team-$index'],
          },
        },
    ],
  };

  Future<double> leaderPoints({
    int driversHour = 21,
    int teamsHour = 21,
    double points = 90,
    bool truncated = false,
  }) async {
    final drivers = standings(driversHour, points);
    if (truncated) (drivers['data'] as List<dynamic>).removeLast();
    final repository = NetworkFirstCalendarRepository(
      fallback: AssetCalendarRepository(
        bundle: _CalendarBundle({
          'assets/data/f1/2026/standings_drivers.json': standings(20, 110),
          'assets/data/f1/2026/standings_teams.json': standings(
            20,
            110,
            teams: true,
          ),
        }),
      ),
      client: MockClient(
        (request) async => http.Response(
          jsonEncode(
            request.url.path.endsWith('standings_drivers.json')
                ? drivers
                : standings(teamsHour, points, teams: true),
          ),
          200,
        ),
      ),
    );
    return (await repository.loadStandings('f1', 2026)).drivers.first.points;
  }

  test('a full newer official correction may reduce points and wins', () async {
    expect(await leaderPoints(), 90);
  });

  test('an unchanged constructor timestamp does not block a newer driver correction', () async {
    expect(await leaderPoints(teamsHour: 20), 90);
  });

  test(
    'a newer timestamp cannot authorize a truncated standings table',
    () async {
      expect(await leaderPoints(truncated: true), 110);
    },
  );

  test(
    'older driver or constructor data cannot undo a bundled correction',
    () async {
      expect(await leaderPoints(driversHour: 19, points: 120), 110);
      expect(await leaderPoints(teamsHour: 19, points: 120), 110);
    },
  );
}
