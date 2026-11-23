import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secar/app/app.dart';
import 'package:secar/features/calendar/data/calendar_repository.dart';
import 'package:secar/features/calendar/domain/race_event.dart';
import 'package:secar/features/calendar/presentation/calendar_providers.dart';
import 'package:secar/features/settings/domain/app_settings.dart';
import 'package:secar/features/settings/presentation/settings_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _TrackCalendar extends AssetCalendarRepository {
  _TrackCalendar(this.event);
  final RaceEvent event;

  @override
  Future<CalendarData> load() async => CalendarData(
    schemaVersion: 1,
    updatedAt: DateTime.now().toUtc(),
    events: [event],
  );
}

void main() {
  testWidgets(
    'track date preserves its own year and does not repeat in another year',
    (tester) async {
      final year = DateTime.now().year + 1;
      final event = RaceEvent(
        id: 'year-boundary',
        seriesId: 'gtwc-asia',
        season: year,
        round: 1,
        name: 'New Year race',
        cancelled: false,
        circuit: const Circuit(name: 'Test Raceway'),
        sessions: [
          RaceSession(
            type: 'R',
            name: 'Race',
            startTimeUtc: DateTime.utc(year, 12, 31, 16, 30),
            startTimeTrack: '${year + 1}-01-01 01:30:00+09:00',
            cancelled: false,
            durationMinutes: 60,
          ),
        ],
        resultsPath: 'events/new-year.json',
      );
      SharedPreferences.setMockInitialValues({});
      tester.view.physicalSize = const Size(800, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            calendarRepositoryProvider.overrideWithValue(_TrackCalendar(event)),
          ],
          child: const MotorsportCalendarApp(),
        ),
      );
      addTearDown(() => tester.pumpWidget(const SizedBox.shrink()));
      await tester.pumpAndSettle();
      final container = ProviderScope.containerOf(
        tester.element(find.byType(MotorsportCalendarApp)),
      );
      container
          .read(settingsProvider.notifier)
          .setTimeMode(EventTimeMode.track);
      await tester.pumpAndSettle();

      const weekdays = [
        'Monday',
        'Tuesday',
        'Wednesday',
        'Thursday',
        'Friday',
        'Saturday',
        'Sunday',
      ];
      final day = weekdays[DateTime.utc(year + 1, 1, 1).weekday - 1];
      expect(find.text('$day, 01 JAN'), findsWidgets);

      await tester.tap(find.text('$year').first);
      await tester.pumpAndSettle();
      tester
          .widget<NavigationBar>(find.byType(NavigationBar))
          .onDestinationSelected!(1);
      await tester.pumpAndSettle();
      await tester.tap(find.byTooltip('Next'));
      await tester.pumpAndSettle();
      Finder cell(int y) => find.byKey(ValueKey('calendar-day-$y-01-01'));
      expect(
        find.descendant(
          of: cell(year + 1),
          matching: find.byTooltip(event.name),
        ),
        findsOneWidget,
      );

      for (var month = 0; month < 12; month++) {
        await tester.tap(find.byTooltip('Next'));
        await tester.pumpAndSettle();
      }
      expect(cell(year + 2), findsOneWidget);
      expect(
        find.descendant(
          of: cell(year + 2),
          matching: find.byTooltip(event.name),
        ),
        findsNothing,
      );
      expect(tester.takeException(), isNull);
    },
  );
}
