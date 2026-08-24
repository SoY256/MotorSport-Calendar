import 'package:flutter/material.dart';
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
    expect(find.text('Australian Grand Prix'), findsOneWidget);
    expect(find.text('🇦🇺'), findsOneWidget);
    expect(find.text('Kategorie • Wybrano: 3'), findsOneWidget);
    await tester.tap(find.text('Kategorie • Wybrano: 3'));
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(find.byType(Checkbox).first);
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Australian Grand Prix'), findsNothing);
    await tester.tap(find.byType(Checkbox).first);
    await tester.pump(const Duration(milliseconds: 200));
    await tester.tap(find.text('Kategorie • Wybrano: 3'));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Ukryj poprzednie wydarzenia'), findsOneWidget);

    await tester.tap(find.text('Ukryj poprzednie wydarzenia'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsNothing);
    await tester.tap(find.text('Pokaż poprzednie wydarzenia'));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Australian Grand Prix'), findsOneWidget);

    await tester.ensureVisible(find.text('Australian Grand Prix'));
    await tester.drag(find.byType(CustomScrollView), const Offset(0, 80));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Australian Grand Prix'));
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Szczegóły'), findsWidgets);
    expect(find.textContaining('Długość toru'), findsOneWidget);
    expect(
      tester.getTopLeft(find.text('Wyścig')).dy,
      lessThan(tester.getTopLeft(find.text('Kwalifikacje')).dy),
    );
    expect(find.text('Charles Leclerc'), findsWidgets);

    await tester.tap(find.text('Klasyfikacja'));
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Andrea Kimi Antonelli'), findsOneWidget);
    expect(find.text('Mistrzostwa'), findsOneWidget);
    expect(find.text('242 PKT'), findsOneWidget);

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
