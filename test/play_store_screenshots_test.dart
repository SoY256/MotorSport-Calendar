import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secar/app/app.dart';
import 'package:secar/features/calendar/data/calendar_repository.dart';
import 'package:secar/features/calendar/presentation/calendar_providers.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('generate accurate Play Store phone screenshots', (tester) async {
    final roboto = FontLoader('Roboto')
      ..addFont(rootBundle.load('assets/fonts/Roboto-Regular.ttf'));
    await roboto.load();
    final materialIcons = FontLoader('MaterialIcons')
      ..addFont(rootBundle.load('assets/fonts/MaterialIcons-Regular.otf'));
    await materialIcons.load();
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(360, 640);
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
      matchesGoldenFile('play_store/list.png'),
    );

    await tester.tap(find.text('Calendar').last);
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('play_store/calendar.png'),
    );

    await tester.tap(find.text('Details').last);
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('play_store/details.png'),
    );

    await tester.tap(find.text('Standings').last);
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(Scaffold),
      matchesGoldenFile('play_store/standings.png'),
    );
  }, tags: ['golden']);
}
