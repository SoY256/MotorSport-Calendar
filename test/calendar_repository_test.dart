import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secar/app/app.dart';
import 'package:secar/core/localization/app_strings.dart';
import 'package:secar/core/series_catalog.dart';
import 'package:secar/core/widgets/racing_ui.dart';
import 'package:secar/features/calendar/data/calendar_repository.dart';
import 'package:secar/features/calendar/domain/race_event.dart';
import 'package:secar/features/calendar/presentation/calendar_providers.dart';
import 'package:secar/features/settings/domain/app_settings.dart';
import 'package:secar/features/settings/presentation/settings_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

RaceEvent newEvent(String series, {String type = 'R'}) => RaceEvent(
  id: '$series-new-event',
  seriesId: series,
  season: 2026,
  round: 99,
  name: 'New racing weekend',
  cancelled: false,
  circuit: const Circuit(name: 'Test Raceway'),
  sessions: [
    RaceSession(
      type: type,
      name: type == 'FP1' ? 'Practice 1' : 'Race',
      startTimeUtc: DateTime.now().toUtc().subtract(const Duration(days: 1)),
      cancelled: false,
      durationMinutes: 60,
    ),
  ],
  resultsPath: 'events/brand-new-event.json',
);

Map<String, dynamic> document(
  RaceEvent event, {
  bool noClassification = false,
}) => {
  'data': {
    'eventId': event.id,
    'sessions': [
      {
        'type': event.sessions.single.type,
        'name': event.sessions.single.name,
        'startTimeUtc': event.sessions.single.startTimeUtc.toIso8601String(),
        'results': noClassification
            ? <Map<String, dynamic>>[]
            : [
                {
                  'position': 1,
                  'positionText': '1',
                  'driver': {
                    'id': 'driver',
                    'code': 'DRV',
                    'givenName': 'Test',
                    'familyName': 'Driver',
                  },
                  'team': {'name': 'Team'},
                  'time': '1:20.123',
                  'points': 25,
                },
              ],
        if (noClassification) ...{
          'classificationStatus': 'not-issued',
          'classificationReason': 'no-timed-laps',
          'source': {
            'name': 'fia-official-timing',
            'url': 'https://www.fia.com/sites/default/files/laps.pdf',
          },
        },
      },
    ],
  },
};

class SingleEventRepository extends AssetCalendarRepository {
  SingleEventRepository(
    this.event, {
    this.results,
    this.downloadError = false,
    this.bundledError,
  });
  final RaceEvent event;
  final EventResults? results;
  final bool downloadError;
  final Object? bundledError;

  @override
  Future<CalendarData> load() async => CalendarData(
    schemaVersion: 1,
    updatedAt: DateTime.now().toUtc(),
    events: [event],
  );

  @override
  Future<EventResults> loadResults(RaceEvent event) {
    if (downloadError) throw ResultsUnavailableException(event.id);
    final error = bundledError;
    if (error != null) throw error;
    return results == null ? super.loadResults(event) : Future.value(results);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  for (final series in allSeries) {
    test(
      'new ${series.id} event loads online without a bundled file',
      () async {
        final event = newEvent(series.id);
        final requests = <Uri>[];
        final repository = NetworkFirstCalendarRepository(
          fallback: AssetCalendarRepository(),
          client: MockClient((request) async {
            requests.add(request.url);
            return http.Response(jsonEncode(document(event)), 200);
          }),
        );

        final result = await repository.loadResults(event);

        expect(result.eventId, event.id);
        expect(result.sessions.single.results.single.driver.id, 'driver');
        expect(requests, hasLength(1));
        expect(
          requests.single.path,
          endsWith('/${series.id}/2026/${event.resultsPath}'),
        );
      },
    );
  }

  test(
    'missing online and bundled results report a recoverable download error',
    () async {
      final event = newEvent('gtwc-asia');
      final repository = NetworkFirstCalendarRepository(
        fallback: AssetCalendarRepository(),
        client: MockClient((_) async => http.Response('', 404)),
      );
      await expectLater(
        repository.loadResults(event),
        throwsA(isA<ResultsUnavailableException>()),
      );
    },
  );

  test('a different event cannot fill a missing bundled document', () async {
    final event = newEvent('gtwc-asia');
    final remote = document(event);
    (remote['data'] as Map<String, dynamic>)['eventId'] = 'another-event';
    final repository = NetworkFirstCalendarRepository(
      fallback: AssetCalendarRepository(),
      client: MockClient((_) async => http.Response(jsonEncode(remote), 200)),
    );
    await expectLater(
      repository.loadResults(event),
      throwsA(isA<ResultsUnavailableException>()),
    );
  });

  test(
    'a damaged bundled document does not block valid online results',
    () async {
      final event = newEvent('gtwc-asia');
      final repository = NetworkFirstCalendarRepository(
        fallback: SingleEventRepository(
          event,
          bundledError: const FormatException('Damaged bundled JSON'),
        ),
        client: MockClient(
          (_) async => http.Response(jsonEncode(document(event)), 200),
        ),
      );
      final result = await repository.loadResults(event);
      expect(result.sessions.single.results.single.driver.id, 'driver');
    },
  );

  test(
    'unexpected local errors are not disguised as a missing asset',
    () async {
      final event = newEvent('gtwc-asia');
      final failure = StateError('Unexpected repository bug');
      final repository = NetworkFirstCalendarRepository(
        fallback: SingleEventRepository(event, bundledError: failure),
        client: MockClient(
          (_) async => http.Response(jsonEncode(document(event)), 200),
        ),
      );
      await expectLater(repository.loadResults(event), throwsA(same(failure)));
    },
  );

  test(
    'an empty new event document is valid and does not require a bundled asset',
    () async {
      final event = newEvent('wec');
      final repository = NetworkFirstCalendarRepository(
        fallback: AssetCalendarRepository(),
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'data': {'eventId': event.id, 'sessions': []},
            }),
            200,
          ),
        ),
      );
      expect((await repository.loadResults(event)).sessions, isEmpty);
    },
  );

  test('verified non-classification stops F1 fallback requests and survives empty remote data', () async {
    final event = newEvent('f1', type: 'FP1');
    final notice = EventResults.fromJson(
      document(event, noClassification: true),
    );
    final requests = <Uri>[];
    final repository = NetworkFirstCalendarRepository(
      fallback: SingleEventRepository(event, results: notice),
      client: MockClient((request) async {
        requests.add(request.url);
        return http.Response(
          jsonEncode({
            'data': {'eventId': event.id, 'sessions': []},
          }),
          200,
        );
      }),
    );
    final result = await repository.loadResults(event);
    expect(
      result.sessions.single.noClassificationReason,
      NoClassificationReason.noTimedLaps,
    );
    expect(requests, hasLength(1));
    expect(requests.single.host, 'raw.githubusercontent.com');
  });

  test(
    'actual classification cannot be erased by a non-classification notice',
    () async {
      final event = newEvent('f1', type: 'FP1');
      final repository = NetworkFirstCalendarRepository(
        fallback: SingleEventRepository(
          event,
          results: EventResults.fromJson(document(event)),
        ),
        client: MockClient(
          (_) async => http.Response(
            jsonEncode(document(event, noClassification: true)),
            200,
          ),
        ),
      );
      final result = await repository.loadResults(event);
      expect(result.sessions.single.results, hasLength(1));
      expect(result.sessions.single.noClassificationReason, isNull);
    },
  );

  test(
    'unverified non-classification is not accepted as a terminal outcome',
    () {
      final data = document(
        newEvent('f1', type: 'FP1'),
        noClassification: true,
      );
      final sessions =
          (data['data'] as Map<String, dynamic>)['sessions'] as List;
      (sessions.single as Map<String, dynamic>)['source'] = {
        'name': 'unknown',
        'url': 'https://example.com/laps.pdf',
      };
      expect(() => EventResults.fromJson(data), throwsFormatException);
    },
  );

  for (final language in AppLanguage.values) {
    testWidgets(
      'non-classification explains the missing practice in $language',
      (tester) async {
        final event = newEvent('f1', type: 'FP1');
        SharedPreferences.setMockInitialValues({});
        await tester.pumpWidget(
          ProviderScope(
            overrides: [
              calendarRepositoryProvider.overrideWithValue(
                SingleEventRepository(
                  event,
                  results: EventResults.fromJson(
                    document(event, noClassification: true),
                  ),
                ),
              ),
            ],
            child: const MotorsportCalendarApp(),
          ),
        );
        await tester.pumpAndSettle();
        final container = ProviderScope.containerOf(
          tester.element(find.byType(MotorsportCalendarApp)),
        );
        container.read(settingsProvider.notifier).setLanguage(language);
        tester
            .widget<NavigationBar>(find.byType(NavigationBar))
            .onDestinationSelected!(2);
        await tester.pumpAndSettle();
        final strings = AppStrings(language);
        expect(find.text(strings.noTimedLaps), findsNothing);
        final tile = find.byType(ExpansionTile).first;
        await Scrollable.ensureVisible(tester.element(tile), alignment: .5);
        await tester.pumpAndSettle();
        await tester.tap(tile);
        await tester.pumpAndSettle();
        expect(find.text(strings.noTimedLaps), findsOneWidget);
        expect(find.text(strings.awaitingResults), findsNothing);
        expect(find.text(strings.noResults), findsNothing);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
      },
    );
  }

  testWidgets('Vegas sessions are newest first with only the race expanded', (
    tester,
  ) async {
    final assets = AssetCalendarRepository();
    final calendar = (await tester.runAsync(assets.load))!;
    final vegas = calendar.events.firstWhere(
      (event) =>
          event.seriesId == 'f1' &&
          event.season == 2026 &&
          event.name == 'Las Vegas Grand Prix',
    );
    final results = (await tester.runAsync(() => assets.loadResults(vegas)))!;
    await _showTimeline(tester, SingleEventRepository(vegas, results: results));

    expect(_timelineKinds(vegas), ['R', 'Q', 'FP3', 'FP2', 'FP1']);
    _expectExpandedResults(vegas, results, 'R');
    expect(
      find.text(AppStrings(AppLanguage.english).noTimedLaps),
      findsNothing,
    );
    final firstHeader = _sessionTile(vegas, 'R');
    final noticeHeader = _sessionTile(vegas, 'FP1');
    expect(
      tester.getTopLeft(firstHeader).dy,
      lessThan(tester.getTopLeft(noticeHeader).dy),
    );
    await _tapSession(tester, vegas, 'FP1');
    expect(
      find.text(AppStrings(AppLanguage.english).noTimedLaps),
      findsOneWidget,
    );
  });

  for (final (series, kinds, race) in [
    ('f1', ['FP1', 'SPRINT', 'Q', 'R'], 'R'),
    ('gtwc-asia', ['FP1', 'R1', 'Q2', 'R2'], 'R2'),
  ]) {
    testWidgets(
      '$series opens only its newest race and resets when changing events',
      (tester) async {
        final first = _timelineEvent(series, kinds, 'first');
        final second = _timelineEvent(series, kinds, 'second');
        final firstResults = _timelineResults(first);
        final secondResults = _timelineResults(second);
        await _showTimeline(
          tester,
          _TimelineRepository(
            [first, second],
            {first.id: firstResults, second.id: secondResults},
          ),
        );
        tester
            .widget<DropdownButtonFormField<String>>(
              find.byType(DropdownButtonFormField<String>),
            )
            .onChanged!(first.id);
        await tester.pumpAndSettle();

        expect(_timelineKinds(first), kinds.reversed.toList());
        _expectExpandedResults(first, firstResults, race);

        final qualifying = kinds[kinds.length - 2];
        await _tapSession(tester, first, qualifying);
        final opened = firstResults.sessions
            .firstWhere((session) => session.type == qualifying)
            .results
            .single
            .driver;
        expect(
          find.text('${opened.givenName} ${opened.familyName}'),
          findsOneWidget,
        );
        await _tapSession(tester, first, race);
        tester
            .widget<DropdownButtonFormField<String>>(
              find.byType(DropdownButtonFormField<String>),
            )
            .onChanged!(second.id);
        await tester.pumpAndSettle();

        _expectExpandedResults(second, secondResults, race);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets('a newly received race opens while the older race collapses', (
    tester,
  ) async {
    final event = _timelineEvent('gtwc-europe', [
      'FP1',
      'R1',
      'Q2',
      'R2',
    ], 'live');
    final all = _timelineResults(event);
    final repository = _TimelineRepository(
      [event],
      {
        event.id: EventResults(
          eventId: event.id,
          sessions: all.sessions
              .where((session) => session.type != 'R2')
              .toList(),
        ),
      },
    );
    await _showTimeline(tester, repository);
    _expectExpandedResults(event, repository.results[event.id]!, 'R1');
    expect(_timelineKinds(event), ['R2', 'Q2', 'R1', 'FP1']);

    repository.results[event.id] = all;
    final container = ProviderScope.containerOf(
      tester.element(find.byType(MotorsportCalendarApp)),
    );
    container.invalidate(eventResultsProvider(event));
    await tester.pumpAndSettle();

    _expectExpandedResults(event, all, 'R2');
    expect(
      find.text(AppStrings(AppLanguage.english).awaitingResults),
      findsNothing,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'download errors show retry instructions instead of an asset path',
    (tester) async {
      final event = newEvent('gtwc-asia');
      SharedPreferences.setMockInitialValues({});
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            calendarRepositoryProvider.overrideWithValue(
              SingleEventRepository(event, downloadError: true),
            ),
          ],
          child: const MotorsportCalendarApp(),
        ),
      );
      await tester.pumpAndSettle();
      tester
          .widget<NavigationBar>(find.byType(NavigationBar))
          .onDestinationSelected!(2);
      await tester.pumpAndSettle();
      expect(
        find.text(AppStrings(AppLanguage.english).resultsDownloadFailed),
        findsOneWidget,
      );
      expect(find.textContaining('Unable to load asset'), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}

Finder _sessionCard(RaceEvent event, String kind) =>
    find.byKey(ValueKey('event-session-${event.id}-$kind'));

Finder _sessionTile(RaceEvent event, String kind) => find.descendant(
  of: _sessionCard(event, kind),
  matching: find.byType(ExpansionTile),
);

List<String> _timelineKinds(RaceEvent event) {
  final prefix = 'event-session-${event.id}-';
  return find
      .byWidgetPredicate(
        (widget) =>
            widget.key is ValueKey<String> &&
            (widget.key! as ValueKey<String>).value.startsWith(prefix),
      )
      .evaluate()
      .map(
        (element) => (element.widget.key! as ValueKey<String>).value.substring(
          prefix.length,
        ),
      )
      .toList();
}

void _expectExpandedResults(
  RaceEvent event,
  EventResults data,
  String expanded,
) {
  for (final session in data.sessions) {
    final tile = _sessionTile(event, session.type);
    final hasResults = session.results.isNotEmpty;
    expect(
      find.descendant(of: tile, matching: find.byType(PositionBadge)),
      hasResults && session.type == expanded ? findsWidgets : findsNothing,
      reason: '${session.type}: only $expanded should be expanded',
    );
  }
}

Future<void> _tapSession(
  WidgetTester tester,
  RaceEvent event,
  String kind,
) async {
  final header = find
      .descendant(of: _sessionTile(event, kind), matching: find.byType(Text))
      .first;
  await Scrollable.ensureVisible(tester.element(header), alignment: .5);
  await tester.pumpAndSettle();
  await tester.tap(header);
  await tester.pumpAndSettle();
}

Future<void> _showTimeline(
  WidgetTester tester,
  CalendarRepository repository,
) async {
  SharedPreferences.setMockInitialValues({});
  await tester.pumpWidget(
    ProviderScope(
      overrides: [calendarRepositoryProvider.overrideWithValue(repository)],
      child: const MotorsportCalendarApp(),
    ),
  );
  addTearDown(() => tester.pumpWidget(const SizedBox.shrink()));
  await tester.pumpAndSettle();
  tester
      .widget<NavigationBar>(find.byType(NavigationBar))
      .onDestinationSelected!(2);
  await tester.pumpAndSettle();
}

RaceEvent _timelineEvent(String series, List<String> kinds, String id) {
  final start = DateTime.now().toUtc().subtract(const Duration(days: 3));
  return RaceEvent(
    id: id,
    seriesId: series,
    season: start.year,
    round: 1,
    name: 'Race weekend $id',
    cancelled: false,
    circuit: const Circuit(name: 'Test Raceway'),
    sessions: [
      for (var index = kinds.length - 1; index >= 0; index--)
        RaceSession(
          type: kinds[index],
          name: kinds[index],
          startTimeUtc: start.add(Duration(hours: index)),
          cancelled: false,
          durationMinutes: 30,
        ),
    ],
    resultsPath: 'events/$id.json',
  );
}

EventResults _timelineResults(RaceEvent event) => EventResults.fromJson({
  'data': {
    'eventId': event.id,
    'sessions': [
      for (final scheduled in event.sessions)
        {
          'type': scheduled.type,
          'name': scheduled.name,
          'startTimeUtc': scheduled.startTimeUtc.toIso8601String(),
          'results': [
            {
              'position': 1,
              'positionText': '1',
              'driver': {
                'id': '${event.id}-${scheduled.type}',
                'givenName': scheduled.type,
                'familyName': event.id,
              },
              'team': {'name': 'Team'},
              'time': '1:20.123',
            },
          ],
        },
    ],
  },
});

class _TimelineRepository implements CalendarRepository {
  _TimelineRepository(this.events, this.results);
  final List<RaceEvent> events;
  final Map<String, EventResults> results;

  @override
  Future<CalendarData> load() async => CalendarData(
    schemaVersion: 1,
    updatedAt: DateTime.now().toUtc(),
    events: events,
  );

  @override
  Future<EventResults> loadResults(RaceEvent event) async => results[event.id]!;

  @override
  Future<StandingsData> loadStandings(String seriesId, int season) async =>
      const StandingsData(drivers: [], teams: []);
}
