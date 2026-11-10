import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:secar/app/app.dart';
import 'package:secar/features/calendar/data/calendar_repository.dart';
import 'package:secar/features/calendar/domain/race_event.dart';
import 'package:secar/features/calendar/presentation/calendar_providers.dart';
import 'package:secar/features/settings/domain/app_settings.dart';
import 'package:secar/features/settings/presentation/settings_controller.dart';
import 'package:secar/features/settings/presentation/theme_controller.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _video = bool.fromEnvironment('STORE_VIDEO');
const _fps = 24;
const _frameTime = Duration(microseconds: 41667);

void main() {
  testWidgets('capture real localized store screenshots and demo footage', (
    tester,
  ) async {
    final fatalHitTests = WidgetController.hitTestWarningShouldBeFatal;
    WidgetController.hitTestWarningShouldBeFatal = true;
    addTearDown(() {
      WidgetController.hitTestWarningShouldBeFatal = fatalHitTests;
    });
    await tester.runAsync(() async {
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
        'MaterialIcons': ['assets/fonts/MaterialIcons-Regular.otf'],
      }.entries) {
        final loader = FontLoader(family.key);
        for (final path in family.value) {
          loader.addFont(rootBundle.load(path));
        }
        await loader.load();
      }
    });

    final assets = AssetCalendarRepository();
    final data = (await tester.runAsync(assets.load))!;
    final monza = data.events.firstWhere(
      (event) =>
          event.seriesId == 'wec' && event.season == 2026 && event.round == 8,
    );
    final monzaResults = (await tester.runAsync(
      () => assets.loadResults(monza),
    ))!;
    final f1Standings = (await tester.runAsync(
      () => assets.loadStandings('f1', 2026),
    ))!;
    expect(monzaResults.sessions.any((session) => session.type == 'R'), isTrue);
    expect(f1Standings.drivers, isNotEmpty);
    final repository = _CaptureRepository(data, monzaResults, f1Standings);

    tester.view.physicalSize = const Size(432, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    for (final locale in ['en-US', 'pl-PL']) {
      SharedPreferences.setMockInitialValues({
        'language': locale == 'pl-PL' ? 'pl' : 'en',
        'showPastEvents': false,
      });
      final boundary = GlobalKey();
      await tester.pumpWidget(
        ProviderScope(
          overrides: [calendarRepositoryProvider.overrideWithValue(repository)],
          child: RepaintBoundary(
            key: boundary,
            child: const MotorsportCalendarApp(),
          ),
        ),
      );
      await _settle(tester);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(MotorsportCalendarApp)),
      );
      container.read(settingsProvider.notifier)
        ..setLanguage(
          locale == 'pl-PL' ? AppLanguage.polish : AppLanguage.english,
        )
        ..setShowPastEvents(false);
      container.read(themeModeProvider.notifier).toggle(Brightness.light);
      await _settle(tester);

      final capture = _StoreCapture(tester, boundary, locale);
      await _alignTop(tester, find.byKey(const ValueKey('next-round-hero')));
      await capture.scene('01-weekend', scroll: true);

      await _selectSeries(tester, 'WEC', 220);
      _scrollTop(tester);
      await _settle(tester);
      await tester.tap(find.text('2026'));
      await _navigate(tester, 2);
      final eventSelector = tester.widget<DropdownButtonFormField<String>>(
        find.byType(DropdownButtonFormField<String>),
      );
      expect(
        tester
            .widget<DropdownButton<String>>(find.byType(DropdownButton<String>))
            .items!
            .every((item) => item.value!.startsWith('wec-')),
        isTrue,
      );
      eventSelector.onChanged!(monza.id);
      await _settle(tester);
      final resultCard = find.byWidgetPredicate(
        (widget) => widget.runtimeType.toString() == '_SessionResultsCard',
      );
      expect(resultCard, findsWidgets);
      await _alignTop(tester, resultCard.first);
      await capture.scene('02-results', scroll: true);

      await _selectSeries(
        tester,
        locale == 'pl-PL' ? 'Wszystkie' : 'All',
        -220,
      );
      await _navigate(tester, 3);
      await _settle(tester);
      expect(find.text('Andrea Kimi Antonelli'), findsOneWidget);
      await capture.scene('03-standings', scroll: true);

      await _navigate(tester, 1);
      container.read(themeModeProvider.notifier).toggle(Brightness.dark);
      await _settle(tester);
      await _alignTop(
        tester,
        find
            .ancestor(of: find.byType(GridView), matching: find.byType(Card))
            .first,
      );
      await capture.scene('04-calendar');

      container.read(themeModeProvider.notifier).toggle(Brightness.light);
      await _navigate(tester, 0);
      _scrollTop(tester);
      await _settle(tester);
      await tester.tap(find.text('2027'));
      await _settle(tester);
      await capture.scene('05-seasons');

      await _navigate(tester, 4);
      final gt = find.byKey(const ValueKey('gt3-categories'));
      await tester.ensureVisible(gt);
      await _settle(tester);
      await capture.scene('06-series');

      await capture.finish();
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    }
  }, tags: ['golden']);
}

Future<void> _navigate(WidgetTester tester, int index) async {
  tester
      .widget<NavigationBar>(find.byType(NavigationBar))
      .onDestinationSelected!(index);
  await _settle(tester);
}

Future<void> _selectSeries(
  WidgetTester tester,
  String label,
  double delta,
) async {
  final horizontal = find
      .byWidgetPredicate(
        (widget) =>
            widget is Scrollable && widget.axisDirection == AxisDirection.right,
      )
      .first;
  await tester.scrollUntilVisible(
    find.text(label),
    delta,
    scrollable: horizontal,
    maxScrolls: 12,
  );
  await tester.pumpAndSettle();
  final position = tester.state<ScrollableState>(horizontal).position;
  final offset =
      position.pixels + tester.getCenter(find.text(label).first).dx - 216;
  position.jumpTo(offset.clamp(0, position.maxScrollExtent));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).first);
  await _settle(tester);
}

Future<void> _settle(WidgetTester tester) async {
  for (var pass = 0; pass < 3; pass++) {
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 100)),
    );
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pumpAndSettle();
}

Finder get _verticalScroll => find
    .byWidgetPredicate(
      (widget) =>
          widget is Scrollable && widget.axisDirection == AxisDirection.down,
    )
    .first;

void _scrollTop(WidgetTester tester) {
  tester.state<ScrollableState>(_verticalScroll).position.jumpTo(0);
}

Future<void> _alignTop(WidgetTester tester, Finder target) async {
  await tester.ensureVisible(target);
  await _settle(tester);
  final position = tester.state<ScrollableState>(_verticalScroll).position;
  final top = tester.getBottomRight(find.byType(AppBar)).dy + 8;
  final offset = position.pixels + tester.getTopLeft(target).dy - top;
  position.jumpTo(offset.clamp(0, position.maxScrollExtent));
  await _settle(tester);
}

class _CaptureRepository extends AssetCalendarRepository {
  _CaptureRepository(this.data, this.monza, this.f1);
  final CalendarData data;
  final EventResults monza;
  final StandingsData f1;

  @override
  Future<CalendarData> load() async => data;

  @override
  Future<EventResults> loadResults(RaceEvent event) => event.id == monza.eventId
      ? Future.value(monza)
      : super.loadResults(event);

  @override
  Future<StandingsData> loadStandings(String seriesId, int season) =>
      seriesId == 'f1' && season == 2026
      ? Future.value(f1)
      : super.loadStandings(seriesId, season);
}

class _StoreCapture {
  _StoreCapture(this.tester, this.boundary, this.locale);
  final WidgetTester tester;
  final GlobalKey boundary;
  final String locale;
  final List<Map<String, Object>> timeline = [];
  int _frame = 0;

  Directory get folder => Directory(
    ['.tmp', 'marketing-captures', locale].join(Platform.pathSeparator),
  );

  Future<void> _save(String name, String scene, int frames) async {
    final render =
        boundary.currentContext!.findRenderObject() as RenderRepaintBoundary;
    final file = File('${folder.path}${Platform.pathSeparator}$name.png');
    await tester.runAsync(() async {
      final image = await render.toImage(pixelRatio: 2.5);
      final png = (await image.toByteData(format: ui.ImageByteFormat.png))!;
      image.dispose();
      await folder.create(recursive: true);
      await file.writeAsBytes(png.buffer.asUint8List());
    });
    timeline.add({'file': '$name.png', 'scene': scene, 'frames': frames});
  }

  Future<void> scene(String name, {bool scroll = false}) async {
    await tester.pump();
    await _save(name, name, (scroll ? 2 : 3) * _fps);
    if (!_video || !scroll) return;
    final gesture = await tester.startGesture(const Offset(216, 480));
    for (var step = 0; step < 30; step++) {
      await gesture.moveBy(const Offset(0, -8));
      await tester.pump(_frameTime);
      await _save('frame-${(_frame++).toString().padLeft(4, '0')}', name, 1);
    }
    await gesture.up();
    await tester.pumpAndSettle();
    await _save('frame-${(_frame++).toString().padLeft(4, '0')}', name, _fps);
  }

  Future<void> finish() async {
    await tester.runAsync(
      () => File('${folder.path}${Platform.pathSeparator}timeline.json')
          .writeAsString(
            const JsonEncoder.withIndent('  ').convert({
              'locale': locale,
              'fps': _fps,
              'source': 'Actual Secar UI with bundled published race data',
              'timeline': timeline,
            }),
          ),
    );
  }
}
