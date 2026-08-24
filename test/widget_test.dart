import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:motor_sport_calendar/app/app.dart';
import 'package:motor_sport_calendar/features/calendar/data/calendar_repository.dart';
import 'package:motor_sport_calendar/features/calendar/presentation/calendar_providers.dart';

void main() {
  testWidgets('shows the real calendar and changes navigation page', (
    tester,
  ) async {
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

    expect(find.text('Sezon 2026'), findsOneWidget);
    expect(find.text('Italian Grand Prix'), findsWidgets);
    expect(find.text('Kalendarz'), findsOneWidget);

    await tester.tap(find.text('Weekend'));
    await tester.pumpAndSettle();
    expect(find.text('Practice 1'), findsOneWidget);
    expect(find.text('Qualifying'), findsOneWidget);
    expect(find.text('Race'), findsOneWidget);

    await tester.tap(find.text('Ustawienia'));
    await tester.pumpAndSettle();
    final switchTile = tester.widget<SwitchListTile>(
      find.byType(SwitchListTile),
    );
    switchTile.onChanged!(true);
    await tester.pumpAndSettle();
    expect(
      tester.widget<MaterialApp>(find.byType(MaterialApp)).themeMode,
      ThemeMode.dark,
    );
  });
}
