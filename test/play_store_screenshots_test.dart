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
    for (final family in {
      'Roboto': [
        'assets/fonts/Roboto-Regular.ttf',
        'assets/fonts/Roboto-Medium.ttf',
        'assets/fonts/Roboto-Bold.ttf',
      ],
      'BarlowCondensed': [
        'assets/fonts/BarlowCondensed-SemiBold.ttf',
        'assets/fonts/BarlowCondensed-Bold.ttf',
        'assets/fonts/BarlowCondensed-BoldItalic.ttf',
        'assets/fonts/BarlowCondensed-ExtraBoldItalic.ttf',
      ],
    }.entries) {
      final loader = FontLoader(family.key);
      for (final path in family.value) {
        loader.addFont(rootBundle.load(path));
      }
      await loader.load();
    }
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
    // Result documents are loaded from the asset bundle with real I/O.
    for (var pass = 0; pass < 3; pass++) {
      await tester.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 200)),
      );
      await tester.pump(const Duration(milliseconds: 300));
    }
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
