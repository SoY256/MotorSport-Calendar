import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:motor_sport_calendar/app/app.dart';
import 'package:motor_sport_calendar/features/calendar/data/calendar_repository.dart';
import 'package:motor_sport_calendar/features/calendar/presentation/calendar_providers.dart';
import 'package:motor_sport_calendar/features/settings/domain/app_settings.dart';
import 'package:motor_sport_calendar/features/settings/presentation/settings_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('fresh installations default to English', () {
    expect(const AppSettings().language, AppLanguage.english);
  });

  test(
    'WEC standings include complete Hypercar and LMGT3 classifications',
    () async {
      final standings = await AssetCalendarRepository().loadStandings('wec');
      final hypercarDrivers = standings.drivers.where(
        (item) => item.category == 'HYPERCAR',
      );
      final lmgt3Drivers = standings.drivers.where(
        (item) => item.category == 'LMGT3',
      );
      final hypercarTeams = standings.teams.where(
        (item) => item.category == 'HYPERCAR',
      );
      final lmgt3Teams = standings.teams.where(
        (item) => item.category == 'LMGT3',
      );

      expect(hypercarDrivers, hasLength(51));
      expect(lmgt3Drivers, hasLength(58));
      expect(hypercarTeams, hasLength(8));
      expect(lmgt3Teams, hasLength(18));
      expect(
        standings.drivers.every((item) => item.nationality.isNotEmpty),
        isTrue,
      );
      expect(standings.drivers.any((item) => item.wins > 0), isTrue);
      expect(standings.teams.any((item) => item.wins > 0), isTrue);

      final hypercarById = {for (final item in hypercarDrivers) item.id: item};
      expect(hypercarById['rene-rast']!.points, 75);
      expect(hypercarById['robin-frijns']!.points, 75);
      expect(hypercarById['kamui-kobayashi']!.points, 75);
      expect(hypercarById['mike-conway']!.points, 75);
      expect(hypercarById['nyck-de-vries']!.points, 75);

      final manufacturers = {for (final item in hypercarTeams) item.name: item};
      expect(manufacturers['Toyota']!.position, 1);
      expect(manufacturers['Toyota']!.points, 132);
      expect(manufacturers['BMW']!.position, 2);
      expect(manufacturers['BMW']!.points, 127);
    },
  );

  test(
    'truncated remote standings cannot replace complete bundled data',
    () async {
      final repository = NetworkFirstCalendarRepository(
        fallback: AssetCalendarRepository(),
        client: MockClient(
          (_) async => http.Response(
            '{"data":[]}',
            200,
            headers: {'content-type': 'application/json'},
          ),
        ),
      );

      final standings = await repository.loadStandings('wec');

      expect(standings.drivers, hasLength(109));
      expect(standings.teams, hasLength(26));
      expect(standings.drivers.any((item) => item.wins > 0), isTrue);
    },
  );

  test(
    'remote F1 results without flags fall back to bundled results',
    () async {
      final fallback = AssetCalendarRepository();
      final calendar = await fallback.load();
      final event = calendar.events.firstWhere(
        (item) => item.seriesId == 'f1' && item.round == 1,
      );
      final repository = NetworkFirstCalendarRepository(
        fallback: fallback,
        client: MockClient(
          (_) async => http.Response(
            '''{"data":{"eventId":"incomplete","sessions":[{"type":"R","name":"Race","startTimeUtc":"2026-01-01T00:00:00Z","results":[{"position":1,"positionText":"1","driver":{"id":"x","givenName":"Test","familyName":"Driver"},"team":{"name":"Test Team","color":"#000000"},"components":{}}]}]}}''',
            200,
            headers: {'content-type': 'application/json'},
          ),
        ),
      );

      final results = await repository.loadResults(event);

      expect(results.sessions, isNotEmpty);
      expect(
        results.sessions
            .expand((session) => session.results)
            .every((result) => (result.driver.nationality ?? '').isNotEmpty),
        isTrue,
      );
    },
  );

  testWidgets('calendar fits a narrow phone without overflow', (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          calendarRepositoryProvider.overrideWithValue(
            AssetCalendarRepository(),
          ),
        ],
        child: const MotorsportCalendarApp(),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Calendar'));
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
  });

  testWidgets('settings tiles use logos without visible name captions', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          calendarRepositoryProvider.overrideWithValue(
            AssetCalendarRepository(),
          ),
        ],
        child: const MotorsportCalendarApp(),
      ),
    );
    await tester.pump(const Duration(seconds: 1));
    await tester.tap(find.text('Settings'));
    await tester.pump(const Duration(seconds: 1));

    expect(find.text('iRacing'), findsNothing);
    expect(find.text('Le Mans Ultimate'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('list subtitle reflects visible events and selected time mode', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    final repository = AssetCalendarRepository();
    final calendar = await repository.load();
    final visibleCount = calendar.events
        .where((event) => event.seriesId == 'f1')
        .length;
    await tester.pumpWidget(
      ProviderScope(
        overrides: [calendarRepositoryProvider.overrideWithValue(repository)],
        child: const MotorsportCalendarApp(),
      ),
    );
    await tester.pump(const Duration(seconds: 1));

    expect(
      find.text('${calendar.events.length} events • My local time'),
      findsOneWidget,
    );
    await tester.tap(find.text('F1'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('$visibleCount events • My local time'), findsOneWidget);

    final container = ProviderScope.containerOf(
      tester.element(find.byType(MotorsportCalendarApp)),
    );
    container.read(settingsProvider.notifier).setTimeMode(EventTimeMode.track);
    await tester.pump(const Duration(milliseconds: 300));
    expect(
      find.text('$visibleCount events • Track local time'),
      findsOneWidget,
    );
    expect(
      find.textContaining('times in the selected time zone'),
      findsNothing,
    );
  });

  testWidgets('calendar, results, standings and settings work end to end', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({'language': 'pl'});
    final repository = AssetCalendarRepository();
    final calendar = await repository.load();
    final australian = calendar.events.firstWhere(
      (event) => event.seriesId == 'f1' && event.round == 1,
    );
    final australianResults = await repository.loadResults(australian);
    expect(australianResults.sessions, isNotEmpty);
    expect(
      australianResults.sessions.any(
        (session) => session.type == 'R' && session.results.isNotEmpty,
      ),
      isTrue,
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [calendarRepositoryProvider.overrideWithValue(repository)],
        child: const MotorsportCalendarApp(),
      ),
    );
    await tester.pump(const Duration(milliseconds: 500));

    await tester.tap(find.text('Kalendarz'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Miesiąc'), findsOneWidget);
    expect(find.text('Tydzień'), findsOneWidget);
    await tester.tap(find.text('Tydzień'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Lista'));
    await tester.pump(const Duration(milliseconds: 300));

    await tester.tap(find.text('Szczegóły'));
    await tester.pumpAndSettle();
    expect(find.text('Zaplanowane sesje'), findsOneWidget);
    await tester.tap(find.text('Lista'));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Sezon 2026'), findsOneWidget);
    expect(find.text('Australian Grand Prix'), findsNWidgets(3));
    expect(find.text('🇦🇺'), findsNWidgets(3));
    expect(find.text('Wszystkie'), findsOneWidget);
    expect(find.text('INDYCAR'), findsOneWidget);
    expect(find.text('INDY NXT'), findsOneWidget);
    await tester.tap(find.text('IMSA').first);
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsNothing);
    await tester.tap(find.text('Wszystkie'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Ukryj poprzednie wydarzenia'), findsOneWidget);

    await tester.tap(find.text('Ukryj poprzednie wydarzenia'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsNothing);
    await tester.tap(find.text('Pokaż poprzednie wydarzenia'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsNWidgets(3));

    await tester.ensureVisible(find.text('Australian Grand Prix').first);
    await tester.drag(find.byType(CustomScrollView), const Offset(0, 80));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Australian Grand Prix').first);
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Szczegóły'), findsWidgets);
    await tester.tap(find.byType(DropdownButtonFormField<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('F1 • R1 • Australian Grand Prix').last);
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.textContaining('Długość toru'), findsOneWidget);

    await tester.tap(find.text('Klasyfikacja'));
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Andrea Kimi Antonelli'), findsOneWidget);
    expect(find.text('242 PKT'), findsOneWidget);
    expect(find.textContaining('Wygrane:'), findsNothing);

    await tester.tap(find.text('Ustawienia'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Kategorie Motorsport'), findsOneWidget);
    expect(find.text('E-Sport'), findsOneWidget);
    expect(find.text('IMSA'), findsWidgets);
    expect(find.text('WEC'), findsWidgets);
    expect(find.text('iRacing'), findsOneWidget);
    expect(find.text('Le Mans Ultimate'), findsOneWidget);
    await tester.ensureVisible(find.text('Angielski'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Angielski'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Calendar'), findsOneWidget);
    expect(find.text('List'), findsOneWidget);
    expect(find.text('Track local time'), findsOneWidget);

    await tester.ensureVisible(find.text('Track local time'));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Track local time'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Event time'), findsOneWidget);
  });
}
