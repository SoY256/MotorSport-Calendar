import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secar/app/app.dart';
import 'package:secar/core/localization/app_strings.dart';
import 'package:secar/core/series_catalog.dart';
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
        expect(find.text(strings.noTimedLaps), findsOneWidget);
        expect(find.text(strings.awaitingResults), findsNothing);
        expect(find.text(strings.noResults), findsNothing);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
      },
    );
  }

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
