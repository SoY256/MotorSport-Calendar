import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:motor_sport_calendar/app/app.dart';
import 'package:motor_sport_calendar/features/calendar/data/calendar_repository.dart';
import 'package:motor_sport_calendar/features/calendar/presentation/calendar_providers.dart';

void main() {
  testWidgets('phone calendar visual regression', (tester) async {
    tester.view.physicalSize = const Size(390, 844);
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

    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('goldens/calendar_phone.png'),
    );
  }, tags: ['golden']);
}
