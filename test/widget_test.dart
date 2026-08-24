import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:motor_sport_calendar/app/app.dart';
import 'package:motor_sport_calendar/features/calendar/data/calendar_repository.dart';
import 'package:motor_sport_calendar/features/calendar/presentation/calendar_providers.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('calendar, results, standings and settings work end to end', (
    tester,
  ) async {
    SharedPreferences.setMockInitialValues({});
    final repository = AssetCalendarRepository();
    await tester.pumpWidget(
      ProviderScope(
        overrides: [calendarRepositoryProvider.overrideWithValue(repository)],
        child: const MotorsportCalendarApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sezon 2026'), findsOneWidget);
    expect(find.text('Australian Grand Prix'), findsOneWidget);
    expect(find.text('Ukryj poprzednie wydarzenia'), findsOneWidget);

    await tester.tap(find.text('Ukryj poprzednie wydarzenia'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsNothing);
    await tester.tap(find.text('Pokaż poprzednie wydarzenia'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsOneWidget);

    await tester.ensureVisible(find.text('Australian Grand Prix'));
    await tester.tap(find.text('Australian Grand Prix'));
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Wyniki'), findsWidgets);
    await tester.tap(find.text('Trening 1'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Charles Leclerc'), findsWidgets);

    await tester.tap(find.text('Klasyfikacja'));
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Andrea Kimi Antonelli'), findsOneWidget);
    expect(find.text('242 PKT'), findsOneWidget);

    await tester.tap(find.text('Ustawienia'));
    await tester.pump(const Duration(milliseconds: 500));
    await tester.tap(find.text('Angielski'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Calendar'), findsOneWidget);
    expect(find.text('Track local time'), findsOneWidget);

    await tester.tap(find.text('Track local time'));
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Event time'), findsOneWidget);
  });
}
