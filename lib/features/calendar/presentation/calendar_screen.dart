import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../core/localization/app_strings.dart';
import '../../../core/widgets/app_logo.dart';
import '../../settings/domain/app_settings.dart';
import '../../settings/presentation/settings_controller.dart';
import '../../settings/presentation/theme_controller.dart';
import '../domain/circuit_metadata.dart';
import '../domain/race_event.dart';
import 'calendar_providers.dart';

bool get _runningWidgetTest => WidgetsBinding.instance.runtimeType
    .toString()
    .contains('TestWidgetsFlutterBinding');

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen>
    with WidgetsBindingObserver {
  int _page = 0;
  String? _selectedEventId;
  String? _activeSeriesId;
  final List<_NavigationSnapshot> _navigationHistory = [];
  bool _handlingBack = false;
  Timer? _sixHourRefresh;
  DateTime _lastFullRefresh = DateTime.now();
  DateTime _calendarAnchor = DateTime.now();
  bool _calendarMonthView = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (!_runningWidgetTest) {
      _scheduleSixHourRefresh();
    }
  }

  void _scheduleSixHourRefresh() {
    _sixHourRefresh?.cancel();
    _sixHourRefresh = Timer(const Duration(hours: 6), () {
      final now = DateTime.now();
      if (now.difference(_lastFullRefresh) >= const Duration(hours: 6)) {
        _lastFullRefresh = now;
        _refreshAllProviders(ref);
        _scheduleSixHourRefresh();
      }
    });
  }

  _NavigationSnapshot get _navigationSnapshot => _NavigationSnapshot(
    page: _page,
    selectedEventId: _selectedEventId,
    activeSeriesId: _activeSeriesId,
  );

  void _navigate({
    required int page,
    String? selectedEventId,
    bool updateSelectedEvent = false,
  }) {
    final next = _NavigationSnapshot(
      page: page,
      selectedEventId: updateSelectedEvent ? selectedEventId : _selectedEventId,
      activeSeriesId: _activeSeriesId,
    );
    if (next == _navigationSnapshot) return;
    setState(() {
      _navigationHistory.add(_navigationSnapshot);
      _page = next.page;
      _selectedEventId = next.selectedEventId;
    });
  }

  void _navigateToEvent(RaceEvent event) =>
      _navigate(page: 2, selectedEventId: event.id, updateSelectedEvent: true);

  Future<void> _handleSystemBack() async {
    if (_handlingBack) return;
    if (_navigationHistory.isNotEmpty) {
      final previous = _navigationHistory.removeLast();
      setState(() {
        _page = previous.page;
        _selectedEventId = previous.selectedEventId;
        _activeSeriesId = previous.activeSeriesId;
      });
      return;
    }

    _handlingBack = true;
    final settings = ref.read(settingsProvider);
    final strings = AppStrings(settings.language);
    final shouldExit = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(strings.exitApp),
        content: Text(strings.exitAppMessage),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(strings.stayInApp),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(strings.exit),
          ),
        ],
      ),
    );
    _handlingBack = false;
    if (shouldExit == true) {
      await SystemNavigator.pop();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        DateTime.now().difference(_lastFullRefresh) >=
            const Duration(hours: 6)) {
      _lastFullRefresh = DateTime.now();
      _refreshAllProviders(ref);
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _sixHourRefresh?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final settings = ref.watch(settingsProvider);
    final strings = AppStrings(settings.language);
    final calendar = ref.watch(calendarProvider);
    final wide = MediaQuery.sizeOf(context).width >= 850;
    final destinations = [
      NavigationDestination(
        icon: const Icon(Icons.view_agenda_outlined),
        selectedIcon: const Icon(Icons.view_agenda),
        label: strings.list,
      ),
      NavigationDestination(
        icon: const Icon(Icons.calendar_month_outlined),
        selectedIcon: const Icon(Icons.calendar_month),
        label: strings.calendar,
      ),
      NavigationDestination(
        icon: const Icon(Icons.flag_outlined),
        selectedIcon: const Icon(Icons.flag),
        label: strings.results,
      ),
      NavigationDestination(
        icon: const Icon(Icons.emoji_events_outlined),
        selectedIcon: const Icon(Icons.emoji_events),
        label: strings.standings,
      ),
      NavigationDestination(
        icon: const Icon(Icons.tune_outlined),
        selectedIcon: const Icon(Icons.tune),
        label: strings.settings,
      ),
    ];
    final content = calendar.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => _ErrorState(
        message: error.toString(),
        strings: strings,
        onRetry: () => ref.invalidate(calendarProvider),
      ),
      data: (data) {
        final availableSeries = data.events
            .map((event) => event.seriesId)
            .toSet();
        final enabledSeries = settings.motorsportCategories.intersection(
          availableSeries,
        );
        if (_activeSeriesId != null &&
            !enabledSeries.contains(_activeSeriesId)) {
          _activeSeriesId = null;
        }
        final selectedSeries = _activeSeriesId == null
            ? enabledSeries
            : {_activeSeriesId!};
        final visibleEvents = data.events
            .where((event) => selectedSeries.contains(event.seriesId))
            .toList();
        final selected = visibleEvents.isEmpty
            ? null
            : visibleEvents.firstWhere(
                (event) => event.id == _selectedEventId,
                orElse: () => _nearestEvent(visibleEvents),
              );
        final page = switch (_page) {
          0 => _ListPage(
            data: data,
            availableSeries: availableSeries,
            selectedSeries: selectedSeries,
            onSeriesChanged: ref
                .read(settingsProvider.notifier)
                .setMotorsportCategories,
            settings: settings,
            strings: strings,
            onEventTap: _navigateToEvent,
          ),
          1 => _CalendarGridPage(
            data: data,
            availableSeries: availableSeries,
            selectedSeries: selectedSeries,
            onSeriesChanged: ref
                .read(settingsProvider.notifier)
                .setMotorsportCategories,
            settings: settings,
            strings: strings,
            onEventTap: _navigateToEvent,
            anchor: _calendarAnchor,
            monthView: _calendarMonthView,
            onViewChanged: (anchor, monthView) {
              _calendarAnchor = anchor;
              _calendarMonthView = monthView;
            },
          ),
          2 when selected != null => _ResultsPage(
            data: data,
            selected: selected,
            selectedSeries: selectedSeries,
            settings: settings,
            strings: strings,
            onSelected: _navigateToEvent,
          ),
          2 => _PageFrame(
            title: strings.results,
            subtitle: '',
            child: _EmptyCard(
              icon: Icons.category_outlined,
              message: strings.chooseAny,
            ),
          ),
          3 => _StandingsPage(
            strings: strings,
            availableSeries: selectedSeries,
          ),
          _ => _SettingsPage(settings: settings, strings: strings),
        };
        return Column(
          children: [
            _SeriesTabsBar(
              available: enabledSeries,
              active: _activeSeriesId,
              language: settings.language,
              onChanged: (value) => setState(() {
                _activeSeriesId = value;
                _selectedEventId = null;
              }),
            ),
            Expanded(child: page),
          ],
        );
      },
    );

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) unawaited(_handleSystemBack());
      },
      child: Scaffold(
        body: Stack(
          children: [
            const Positioned.fill(child: _RacingBackdrop()),
            SafeArea(
              child: Row(
                children: [
                  if (wide)
                    NavigationRail(
                      selectedIndex: _page,
                      onDestinationSelected: (value) => _navigate(page: value),
                      labelType: NavigationRailLabelType.all,
                      leading: const Padding(
                        padding: EdgeInsets.symmetric(vertical: 16),
                        child: AppLogo(compact: true),
                      ),
                      destinations: destinations
                          .map(
                            (item) => NavigationRailDestination(
                              icon: item.icon,
                              selectedIcon: item.selectedIcon,
                              label: Text(item.label),
                            ),
                          )
                          .toList(),
                    ),
                  Expanded(child: content),
                ],
              ),
            ),
          ],
        ),
        bottomNavigationBar: wide
            ? null
            : NavigationBar(
                selectedIndex: _page,
                onDestinationSelected: (value) => _navigate(page: value),
                destinations: destinations,
              ),
      ),
    );
  }
}

class _NavigationSnapshot {
  const _NavigationSnapshot({
    required this.page,
    required this.selectedEventId,
    required this.activeSeriesId,
  });

  final int page;
  final String? selectedEventId;
  final String? activeSeriesId;

  @override
  bool operator ==(Object other) =>
      other is _NavigationSnapshot &&
      page == other.page &&
      selectedEventId == other.selectedEventId &&
      activeSeriesId == other.activeSeriesId;

  @override
  int get hashCode => Object.hash(page, selectedEventId, activeSeriesId);
}

class _RacingBackdrop extends StatelessWidget {
  const _RacingBackdrop();

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    return IgnorePointer(
      child: Stack(
        fit: StackFit.expand,
        children: [
          ColorFiltered(
            colorFilter: dark
                ? const ColorFilter.matrix(<double>[
                    1.65,
                    0,
                    0,
                    0,
                    10,
                    0,
                    1.65,
                    0,
                    0,
                    10,
                    0,
                    0,
                    1.65,
                    0,
                    10,
                    0,
                    0,
                    0,
                    1,
                    0,
                  ])
                : const ColorFilter.mode(Colors.transparent, BlendMode.dst),
            child: Image.asset(
              dark
                  ? 'assets/branding/carbon-wallpaper-dark.png'
                  : 'assets/branding/carbon-wallpaper-light.png',
              fit: BoxFit.cover,
              alignment: Alignment.center,
              filterQuality: FilterQuality.high,
            ),
          ),
          ColoredBox(
            color: (dark ? const Color(0xFF05070A) : Colors.white).withValues(
              alpha: dark ? .04 : .18,
            ),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: dark
                    ? [
                        Colors.black.withValues(alpha: .01),
                        Colors.black.withValues(alpha: .08),
                      ]
                    : [
                        Colors.white.withValues(alpha: .08),
                        const Color(0xFFF4F6F9).withValues(alpha: .30),
                      ],
              ),
            ),
          ),
          CustomPaint(painter: _SpeedLinesPainter(dark: dark)),
        ],
      ),
    );
  }
}

class _SpeedLinesPainter extends CustomPainter {
  const _SpeedLinesPainter({required this.dark});
  final bool dark;

  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = (dark ? Colors.white : const Color(0xFF111827)).withValues(
        alpha: .025,
      )
      ..strokeWidth = 1;
    for (double x = -size.height; x < size.width; x += 34) {
      canvas.drawLine(Offset(x, 0), Offset(x + size.height, size.height), line);
    }
    final glow = Paint()
      ..shader = const LinearGradient(
        colors: [Colors.transparent, Color(0x55E10600), Colors.transparent],
      ).createShader(Rect.fromLTWH(0, 0, size.width, 3));
    canvas.drawRect(Rect.fromLTWH(0, 0, size.width, 3), glow);
  }

  @override
  bool shouldRepaint(covariant _SpeedLinesPainter oldDelegate) =>
      oldDelegate.dark != dark;
}

class _SeriesTabsBar extends StatelessWidget {
  const _SeriesTabsBar({
    required this.available,
    required this.active,
    required this.language,
    required this.onChanged,
  });
  final Set<String> available;
  final String? active;
  final AppLanguage language;
  final ValueChanged<String?> onChanged;

  @override
  Widget build(BuildContext context) {
    final ids = available.toList()..sort();
    return Material(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: .94),
      elevation: 3,
      shadowColor: Colors.black26,
      child: SizedBox(
        height: 62,
        child: ListView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          children: [
            _SeriesTab(
              label: language == AppLanguage.polish ? 'Wszystkie' : 'All',
              selected: active == null,
              onTap: () => onChanged(null),
            ),
            for (final id in ids) ...[
              const SizedBox(width: 8),
              _SeriesTab(
                label: _seriesLabel(id),
                color: _seriesColor(id),
                selected: active == id,
                onTap: () => onChanged(id),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SeriesTab extends StatelessWidget {
  const _SeriesTab({
    required this.label,
    required this.selected,
    required this.onTap,
    this.color,
  });
  final String label;
  final bool selected;
  final VoidCallback onTap;
  final Color? color;

  @override
  Widget build(BuildContext context) => Material(
    color: selected
        ? (color ?? Theme.of(context).colorScheme.primary)
        : Theme.of(context).colorScheme.surfaceContainer,
    shape: StadiumBorder(
      side: BorderSide(
        color: selected ? Colors.transparent : Theme.of(context).dividerColor,
      ),
    ),
    child: InkWell(
      customBorder: const StadiumBorder(),
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? Colors.white : null,
            fontWeight: FontWeight.w900,
          ),
        ),
      ),
    ),
  );
}

class _PageFrame extends StatelessWidget {
  const _PageFrame({
    required this.title,
    required this.subtitle,
    required this.child,
  });
  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) => CustomScrollView(
    slivers: [
      SliverAppBar(
        pinned: true,
        toolbarHeight: 72,
        title: const AppLogo(),
        actions: const [_GlobalRefreshButton(), SizedBox(width: 8)],
        backgroundColor: Theme.of(context).scaffoldBackgroundColor
            .withValues(alpha: .94),
      ),
      SliverToBoxAdapter(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1100),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        width: 34,
                        height: 4,
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primary,
                          borderRadius: BorderRadius.circular(4),
                          boxShadow: [
                            BoxShadow(
                              color: Theme.of(context).colorScheme.primary
                                  .withValues(alpha: .42),
                              blurRadius: 10,
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          'SECAR  /  LIVE MOTORSPORT',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.primary,
                            fontSize: 10,
                            fontWeight: FontWeight.w900,
                            letterSpacing: 1.35,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 9),
                  Text(
                    title.toUpperCase(),
                    style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w900,
                      fontStyle: FontStyle.italic,
                      letterSpacing: -1.1,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    subtitle,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
      SliverPadding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        sliver: SliverToBoxAdapter(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 1100),
              child: child,
            ),
          ),
        ),
      ),
    ],
  );
}

void _refreshAllProviders(WidgetRef ref) {
  ref.invalidate(calendarProvider);
  ref.invalidate(eventResultsProvider);
  ref.invalidate(standingsProvider);
}

class _GlobalRefreshButton extends ConsumerWidget {
  const _GlobalRefreshButton();

  @override
  Widget build(BuildContext context, WidgetRef ref) => IconButton(
    tooltip: AppStrings(ref.watch(settingsProvider).language).refresh,
    onPressed: () => _refreshAllProviders(ref),
    icon: const Icon(Icons.refresh_rounded),
  );
}

class _ListPage extends ConsumerWidget {
  const _ListPage({
    required this.data,
    required this.settings,
    required this.strings,
    required this.onEventTap,
    required this.availableSeries,
    required this.selectedSeries,
    required this.onSeriesChanged,
  });
  final CalendarData data;
  final AppSettings settings;
  final AppStrings strings;
  final ValueChanged<RaceEvent> onEventTap;
  final Set<String> availableSeries;
  final Set<String> selectedSeries;
  final ValueChanged<Set<String>> onSeriesChanged;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now().toUtc();
    final matching = data.events
        .where((event) => selectedSeries.contains(event.seriesId))
        .toList();
    final nextEvent = _nextEvent(matching, now);
    final events = settings.showPastEvents
        ? matching
        : matching.where((event) => event.endsAt.isAfter(now)).toList();
    return _PageFrame(
      title: '${strings.season} ${data.events.first.season}',
      subtitle:
          '${strings.events(events.length)} • ${settings.timeMode == EventTimeMode.local ? strings.localTime : strings.trackTime}',
      child: Column(
        children: [
          if (nextEvent != null)
            _NextRaceHero(
              event: nextEvent,
              settings: settings,
              strings: strings,
              onTap: () => onEventTap(nextEvent),
            ),
          const SizedBox(height: 14),
          Card(
            child: SwitchListTile(
              secondary: const Icon(Icons.history_rounded),
              title: Text(
                settings.showPastEvents ? strings.hidePast : strings.showPast,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              value: settings.showPastEvents,
              onChanged: ref.read(settingsProvider.notifier).setShowPastEvents,
            ),
          ),
          const SizedBox(height: 14),
          if (events.isEmpty)
            _EmptyCard(icon: Icons.event_busy, message: strings.noUpcoming)
          else
            for (final event in events) ...[
              _EventCard(
                event: event,
                settings: settings,
                strings: strings,
                completed: event.endsAt.isBefore(now),
                onTap: () => onEventTap(event),
              ),
              const SizedBox(height: 12),
            ],
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(
              '${strings.updated}: ${_dateTime(data.updatedAt.toLocal(), settings.language)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
        ],
      ),
    );
  }
}

class _NextRaceHero extends StatelessWidget {
  const _NextRaceHero({
    required this.event,
    required this.settings,
    required this.strings,
    required this.onTap,
  });
  final RaceEvent event;
  final AppSettings settings;
  final AppStrings strings;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final first = event.sessions.first;
    final last = event.sessions.last;
    final seriesColor = _seriesColor(event.seriesId);
    final circuitAsset = circuitAssetFor(event.circuit.name);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        key: const ValueKey('next-round-hero'),
        borderRadius: BorderRadius.circular(24),
        onTap: onTap,
        child: Container(
          width: double.infinity,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            gradient: LinearGradient(
              colors: const [Color(0xFF111722), Color(0xFF202B3A)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            boxShadow: [
              BoxShadow(
                color: seriesColor.withValues(alpha: .24),
                blurRadius: 28,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          clipBehavior: Clip.antiAlias,
          child: Stack(
            children: [
              Positioned.fill(
                child: IgnorePointer(
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: FractionallySizedBox(
                      widthFactor: .48,
                      child: Row(
                        textDirection: TextDirection.ltr,
                        children: [
                          SizedBox(
                            width: 94,
                            height: 82,
                            child: Opacity(
                              opacity: .86,
                              child: FittedBox(
                                fit: BoxFit.contain,
                                child: Text(
                                  _countryFlag(event.circuit.countryCode),
                                  style: const TextStyle(
                                    fontSize: 82,
                                    height: 1,
                                  ),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(width: 18),
                          if (circuitAsset != null)
                            Expanded(
                              child: ClipRect(
                                child: Opacity(
                                  opacity: .42,
                                  child: _CircuitAsset(
                                    path: circuitAsset,
                                    fit: BoxFit.contain,
                                    tint: Colors.white,
                                    semanticsLabel: event.circuit.name,
                                    quarterTurns: circuitQuarterTurns(
                                      event.circuit.name,
                                    ),
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
              Positioned.fill(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [
                        const Color(0xFF111722),
                        const Color(0xFF111722).withValues(alpha: .88),
                        seriesColor.withValues(alpha: .22),
                      ],
                      stops: const [0, .56, 1],
                    ),
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${strings.nextRound} • ${_seriesLabel(event.seriesId)}',
                      style: TextStyle(
                        color: Color.lerp(Colors.white, seriesColor, .28),
                        fontWeight: FontWeight.w800,
                        letterSpacing: 1.2,
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      event.name,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 26,
                        fontWeight: FontWeight.w900,
                        shadows: [Shadow(color: Colors.black, blurRadius: 10)],
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '${event.circuit.name} • ${event.circuit.country ?? ''}',
                      style: const TextStyle(color: Colors.white70),
                    ),
                    const SizedBox(height: 20),
                    Wrap(
                      spacing: 10,
                      runSpacing: 10,
                      children: [
                        _HeroPill(
                          icon: Icons.calendar_today,
                          label:
                              '${_sessionDate(first, settings)} – ${_sessionDate(last, settings)}',
                        ),
                        _HeroPill(
                          icon: Icons.schedule,
                          label: strings.sessions(event.sessions.length),
                        ),
                        _HeroPill(
                          icon: Icons.public,
                          label: _zoneName(first, settings, strings),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _HeroPill extends StatelessWidget {
  const _HeroPill({required this.icon, required this.label});
  final IconData icon;
  final String label;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    decoration: BoxDecoration(
      color: Colors.white.withValues(alpha: .14),
      borderRadius: BorderRadius.circular(30),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, color: Colors.white, size: 16),
        const SizedBox(width: 7),
        Text(
          label,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    ),
  );
}

class _EventCard extends StatelessWidget {
  const _EventCard({
    required this.event,
    required this.settings,
    required this.strings,
    required this.completed,
    required this.onTap,
  });
  final RaceEvent event;
  final AppSettings settings;
  final AppStrings strings;
  final bool completed;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final race = event.sessions.last;
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              Container(
                width: 4,
                height: 48,
                decoration: BoxDecoration(
                  color: _seriesColor(event.seriesId),
                  borderRadius: BorderRadius.circular(4),
                  boxShadow: [
                    BoxShadow(
                      color: _seriesColor(event.seriesId)
                          .withValues(alpha: .35),
                      blurRadius: 8,
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              SizedBox(
                width: 52,
                height: 46,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surfaceContainer,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Center(
                    child: Text(
                      _countryFlag(event.circuit.countryCode),
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 28),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 15),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            event.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                        if (completed &&
                            MediaQuery.sizeOf(context).width >= 520)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 7,
                              vertical: 3,
                            ),
                            decoration: BoxDecoration(
                              color: Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(10),
                            ),
                            child: Text(
                              strings.completed,
                              style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 5),
                    Row(
                      children: [
                        Flexible(
                          child: Text(
                            _seriesLabel(event.seriesId),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: _seriesColor(event.seriesId),
                              fontSize: 12,
                              fontWeight: FontWeight.w900,
                            ),
                          ),
                        ),
                        Expanded(
                          child: Text(
                            '  •  R${event.round ?? '–'}  •  ${event.circuit.name}',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _sessionDate(race, settings),
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _sessionTime(race, settings.timeMode),
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.primary,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 4),
              const Icon(Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}

class _CalendarGridPage extends StatefulWidget {
  const _CalendarGridPage({
    required this.data,
    required this.settings,
    required this.strings,
    required this.onEventTap,
    required this.availableSeries,
    required this.selectedSeries,
    required this.onSeriesChanged,
    required this.anchor,
    required this.monthView,
    required this.onViewChanged,
  });
  final CalendarData data;
  final AppSettings settings;
  final AppStrings strings;
  final ValueChanged<RaceEvent> onEventTap;
  final Set<String> availableSeries;
  final Set<String> selectedSeries;
  final ValueChanged<Set<String>> onSeriesChanged;
  final DateTime anchor;
  final bool monthView;
  final void Function(DateTime anchor, bool monthView) onViewChanged;

  @override
  State<_CalendarGridPage> createState() => _CalendarGridPageState();
}

class _CalendarGridPageState extends State<_CalendarGridPage> {
  late bool _month = widget.monthView;
  late DateTime _anchor = widget.anchor;

  void _setView({DateTime? anchor, bool? month}) {
    setState(() {
      _anchor = anchor ?? _anchor;
      _month = month ?? _month;
    });
    widget.onViewChanged(_anchor, _month);
  }

  @override
  void didUpdateWidget(covariant _CalendarGridPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.anchor != widget.anchor ||
        oldWidget.monthView != widget.monthView) {
      _anchor = widget.anchor;
      _month = widget.monthView;
    }
  }

  DateTime _dateFor(RaceSession session) {
    final parts = widget.settings.timeMode == EventTimeMode.track
        ? _trackParts(session)
        : null;
    return parts == null
        ? session.startTimeUtc.toLocal()
        : DateTime(_anchor.year, parts[0], parts[1]);
  }

  List<RaceEvent> _eventsOn(DateTime day) => widget.data.events
      .where(
        (event) =>
            widget.selectedSeries.contains(event.seriesId) &&
            !event.cancelled &&
            event.sessions.any((session) {
              final date = _dateFor(session);
              return date.year == day.year &&
                  date.month == day.month &&
                  date.day == day.day;
            }),
      )
      .toList();

  @override
  Widget build(BuildContext context) {
    final first = _month
        ? DateTime(_anchor.year, _anchor.month)
        : DateTime(
            _anchor.year,
            _anchor.month,
            _anchor.day,
          ).subtract(Duration(days: _anchor.weekday - 1));
    final leading = _month ? first.weekday - 1 : 0;
    final count = _month
        ? DateTime(_anchor.year, _anchor.month + 1, 0).day + leading
        : 7;
    final cells = _month ? ((count + 6) ~/ 7) * 7 : 7;
    final title = _month
        ? '${_monthName(_anchor.month, widget.strings.language)} ${_anchor.year}'
        : '${_date(first, widget.strings.language)} – ${_date(first.add(const Duration(days: 6)), widget.strings.language)}';
    return _PageFrame(
      title: widget.strings.calendar,
      subtitle: widget.strings.timesInZone,
      child: Column(
        children: [
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 12,
            runSpacing: 10,
            children: [
              SegmentedButton<bool>(
                segments: [
                  ButtonSegment(value: true, label: Text(widget.strings.month)),
                  ButtonSegment(value: false, label: Text(widget.strings.week)),
                ],
                selected: {_month},
                onSelectionChanged: (value) => _setView(month: value.first),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Card(
            clipBehavior: Clip.antiAlias,
            child: Column(
              children: [
                Row(
                  children: [
                    IconButton(
                      tooltip: widget.strings.previous,
                      onPressed: () => _setView(
                        anchor: _month
                            ? DateTime(_anchor.year, _anchor.month - 1)
                            : _anchor.subtract(const Duration(days: 7)),
                      ),
                      icon: const Icon(Icons.chevron_left),
                    ),
                    Expanded(
                      child: Text(
                        title,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                    ),
                    IconButton(
                      tooltip: widget.strings.next,
                      onPressed: () => _setView(
                        anchor: _month
                            ? DateTime(_anchor.year, _anchor.month + 1)
                            : _anchor.add(const Duration(days: 7)),
                      ),
                      icon: const Icon(Icons.chevron_right),
                    ),
                  ],
                ),
                const Divider(height: 1),
                Row(
                  children: _weekdayNames(widget.strings.language)
                      .map(
                        (day) => Expanded(
                          child: Padding(
                            padding: const EdgeInsets.symmetric(vertical: 8),
                            child: Text(
                              day,
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.labelMedium
                                  ?.copyWith(fontWeight: FontWeight.w900),
                            ),
                          ),
                        ),
                      )
                      .toList(),
                ),
                const Divider(height: 1),
                LayoutBuilder(
                  builder: (context, gridConstraints) => GridView.builder(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 7,
                      childAspectRatio: gridConstraints.maxWidth >= 700
                          ? (_month ? 1.55 : 1.35)
                          : (_month ? .72 : .55),
                    ),
                    itemCount: cells,
                    itemBuilder: (context, index) {
                      final offset = index - leading;
                      if (_month && (offset < 0 || offset >= count - leading)) {
                        return const SizedBox.shrink();
                      }
                      final day = first.add(
                        Duration(days: _month ? offset : index),
                      );
                      final events = _eventsOn(day);
                      final today = DateTime.now();
                      final isToday =
                          day.year == today.year &&
                          day.month == today.month &&
                          day.day == today.day;
                      return InkWell(
                        key: ValueKey(
                          'calendar-day-${day.year}-${_two(day.month)}-${_two(day.day)}',
                        ),
                        onTap: events.isEmpty
                            ? null
                            : () => _showDayEvents(context, day, events),
                        child: DecoratedBox(
                          decoration: BoxDecoration(
                            border: Border.all(
                              color: Theme.of(context).dividerColor
                                  .withValues(alpha: .35),
                            ),
                            color: isToday
                                ? Theme.of(context).colorScheme.primaryContainer
                                      .withValues(alpha: .5)
                                : null,
                          ),
                          child: Padding(
                            padding: const EdgeInsets.all(6),
                            child: Column(
                              children: [
                                Text(
                                  '${day.day}',
                                  style: TextStyle(
                                    fontWeight: isToday
                                        ? FontWeight.w900
                                        : FontWeight.w600,
                                  ),
                                ),
                                if (events.isNotEmpty)
                                  Expanded(
                                    child: ListView.separated(
                                      padding: const EdgeInsets.only(top: 3),
                                      itemCount: events.length,
                                      separatorBuilder: (_, _) =>
                                          const SizedBox(height: 3),
                                      itemBuilder: (context, eventIndex) =>
                                          _CalendarEventMarker(
                                            event: events[eventIndex],
                                            showName: !_month,
                                          ),
                                    ),
                                  ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _showDayEvents(
    BuildContext context,
    DateTime day,
    List<RaceEvent> events,
  ) async {
    final selected = await showModalBottomSheet<RaceEvent>(
      context: context,
      showDragHandle: true,
      builder: (sheetContext) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                _date(day, widget.strings.language),
                style: Theme.of(sheetContext).textTheme.titleLarge
                    ?.copyWith(fontWeight: FontWeight.w900),
              ),
              const SizedBox(height: 12),
              ConstrainedBox(
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.sizeOf(sheetContext).height * .62,
                ),
                child: ListView(
                  shrinkWrap: true,
                  children: [
                    for (final event in events)
                      Card(
                        child: ListTile(
                          leading: _SeriesBadge(seriesId: event.seriesId),
                          title: Text(
                            event.name,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                          subtitle: Text(event.circuit.name),
                          trailing: const Icon(Icons.chevron_right),
                          onTap: () => Navigator.of(sheetContext).pop(event),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
    if (selected != null) widget.onEventTap(selected);
  }
}

class _SeriesBadge extends StatelessWidget {
  const _SeriesBadge({required this.seriesId, this.compact = false});
  final String seriesId;
  final bool compact;

  @override
  Widget build(BuildContext context) => Container(
    width: compact ? 18 : null,
    height: compact ? 18 : null,
    constraints: BoxConstraints(minWidth: compact ? 18 : 38),
    padding: EdgeInsets.symmetric(
      horizontal: compact ? 2 : 7,
      vertical: compact ? 1 : 4,
    ),
    decoration: BoxDecoration(
      color: _seriesColor(seriesId),
      borderRadius: BorderRadius.circular(6),
    ),
    child: compact
        ? const Icon(Icons.sports_motorsports, color: Colors.white, size: 12)
        : Text(
            _seriesLabel(seriesId),
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 11,
              fontWeight: FontWeight.w900,
            ),
          ),
  );
}

class _CalendarEventMarker extends StatelessWidget {
  const _CalendarEventMarker({required this.event, required this.showName});
  final RaceEvent event;
  final bool showName;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: event.name,
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _SeriesBadge(seriesId: event.seriesId, compact: true),
        if (showName) ...[
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              event.name,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelSmall,
            ),
          ),
        ],
      ],
    ),
  );
}

class _ResultsPage extends ConsumerStatefulWidget {
  const _ResultsPage({
    required this.data,
    required this.selected,
    required this.selectedSeries,
    required this.settings,
    required this.strings,
    required this.onSelected,
  });
  final CalendarData data;
  final RaceEvent selected;
  final Set<String> selectedSeries;
  final AppSettings settings;
  final AppStrings strings;
  final ValueChanged<RaceEvent> onSelected;

  @override
  ConsumerState<_ResultsPage> createState() => _ResultsPageState();
}

class _ResultsPageState extends ConsumerState<_ResultsPage>
    with WidgetsBindingObserver {
  Timer? _resultTimer;
  DateTime? _lastResultPoll;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didUpdateWidget(covariant _ResultsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.selected.id != widget.selected.id) {
      _resultTimer?.cancel();
      _lastResultPoll = null;
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _lastResultPoll = DateTime.now().toUtc();
      ref.invalidate(eventResultsProvider(widget.selected));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _resultTimer?.cancel();
    super.dispose();
  }

  void _scheduleResultRefresh(EventResults results) {
    _resultTimer?.cancel();
    if (_runningWidgetTest) return;
    final now = DateTime.now().toUtc();
    final missing = widget.selected.sessions.where((session) {
      if (session.cancelled) return false;
      if (widget.selected.seriesId != 'f1' && session.type != 'R') {
        return false;
      }
      final received = _hasResultsForSession(session, results);
      return !received;
    }).toList();
    if (missing.isEmpty) return;
    missing.sort((a, b) => a.expectedEnd.compareTo(b.expectedEnd));
    final due = missing.first.expectedEnd.add(const Duration(minutes: 5));
    final sinceLastPoll = _lastResultPoll == null
        ? null
        : now.difference(_lastResultPoll!);
    final delay = due.isAfter(now)
        ? due.difference(now)
        : sinceLastPoll == null || sinceLastPoll >= const Duration(minutes: 5)
        ? Duration.zero
        : const Duration(minutes: 5) - sinceLastPoll;
    final intendedPollAt = now.add(delay);
    _resultTimer = Timer(delay, () {
      if (!mounted) return;
      // Fake clocks used by widget tests can fire timers without advancing
      // wall time. Production timers reach this instant normally.
      if (DateTime.now().toUtc().isBefore(intendedPollAt)) return;
      _lastResultPoll = DateTime.now().toUtc();
      ref.invalidate(eventResultsProvider(widget.selected));
      ref.invalidate(standingsProvider(widget.selected.seriesId));
    });
  }

  @override
  Widget build(BuildContext context) {
    final selected = widget.selected;
    final settings = widget.settings;
    final strings = widget.strings;
    final results = ref.watch(eventResultsProvider(selected));
    results.whenData(
      (data) => WidgetsBinding.instance.addPostFrameCallback(
        (_) => mounted ? _scheduleResultRefresh(data) : null,
      ),
    );
    return _PageFrame(
      title: strings.results,
      subtitle: '${selected.name} • ${selected.circuit.name}',
      child: Column(
        children: [
          DropdownButtonFormField<String>(
            initialValue: selected.id,
            decoration: InputDecoration(
              labelText: strings.selectEvent,
              border: const OutlineInputBorder(),
            ),
            isExpanded: true,
            items: widget.data.events
                .where(
                  (event) =>
                      !event.cancelled &&
                      widget.selectedSeries.contains(event.seriesId),
                )
                .map(
                  (event) => DropdownMenuItem(
                    value: event.id,
                    child: Text(
                      '${_seriesLabel(event.seriesId)} • R${event.round} • ${event.name}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                )
                .toList(),
            onChanged: (id) => widget.onSelected(
              widget.data.events.firstWhere((event) => event.id == id),
            ),
          ),
          const SizedBox(height: 16),
          _CircuitInfoCard(event: selected, strings: strings),
          const SizedBox(height: 16),
          results.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(),
            ),
            error: (error, _) => _ErrorState(
              message: error.toString(),
              strings: strings,
              onRetry: () => ref.invalidate(eventResultsProvider(selected)),
            ),
            data: (data) {
              final now = DateTime.now().toUtc();
              final sessions =
                  data.sessions
                      .where((session) => session.results.isNotEmpty)
                      .toList()
                    ..sort(
                      (a, b) =>
                          _resultOrder(a.type).compareTo(_resultOrder(b.type)),
                    );
              final withoutResults =
                  selected.sessions
                      .where(
                        (session) =>
                            !session.cancelled &&
                            !_hasResultsForSession(session, data),
                      )
                      .toList()
                    ..sort((a, b) => a.startTimeUtc.compareTo(b.startTimeUtc));
              final awaiting = withoutResults
                  .where((session) => !session.expectedEnd.isAfter(now))
                  .toList();
              final planned = withoutResults
                  .where((session) => session.expectedEnd.isAfter(now))
                  .toList();

              return Column(
                children: [
                  for (var index = 0; index < sessions.length; index++) ...[
                    _SessionResultsCard(
                      session: sessions[index],
                      strings: strings,
                      initiallyExpanded: index == 0,
                    ),
                    if (index < sessions.length - 1 ||
                        awaiting.isNotEmpty ||
                        planned.isNotEmpty)
                      const SizedBox(height: 12),
                  ],
                  if (awaiting.isNotEmpty) ...[
                    _SessionsScheduleCard(
                      title: strings.awaitingResults,
                      icon: Icons.hourglass_top_rounded,
                      sessions: awaiting,
                      settings: settings,
                      strings: strings,
                    ),
                    if (planned.isNotEmpty) const SizedBox(height: 12),
                  ],
                  if (planned.isNotEmpty)
                    _SessionsScheduleCard(
                      title: strings.plannedSessions,
                      icon: Icons.schedule,
                      sessions: planned,
                      settings: settings,
                      strings: strings,
                    ),
                  if (sessions.isEmpty && awaiting.isEmpty && planned.isEmpty)
                    _EmptyCard(
                      icon: Icons.hourglass_empty,
                      message: strings.noResults,
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

bool _hasResultsForSession(RaceSession session, EventResults results) => results
    .sessions
    .any((result) => result.type == session.type && result.results.isNotEmpty);

class _SessionsScheduleCard extends StatelessWidget {
  const _SessionsScheduleCard({
    required this.title,
    required this.icon,
    required this.sessions,
    required this.settings,
    required this.strings,
  });

  final String title;
  final IconData icon;
  final List<RaceSession> sessions;
  final AppSettings settings;
  final AppStrings strings;

  @override
  Widget build(BuildContext context) => Card(
    child: Column(
      children: [
        ListTile(
          leading: Icon(icon),
          title: Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w900),
          ),
        ),
        const Divider(height: 1),
        for (final session in sessions)
          ListTile(
            title: Text(
              _sessionLabel(session.type, session.name, strings),
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
            subtitle: Text(
              '${_zoneName(session, settings, strings)} • '
              '${strings.expectedDuration}: ${strings.duration(session.durationMinutes)}',
            ),
            trailing: Text(
              '${_sessionDate(session, settings)}\n'
              '${_sessionTime(session, settings.timeMode)}',
              textAlign: TextAlign.end,
              style: const TextStyle(fontWeight: FontWeight.w800),
            ),
          ),
      ],
    ),
  );
}

class _CircuitAsset extends StatelessWidget {
  const _CircuitAsset({
    required this.path,
    required this.fit,
    required this.semanticsLabel,
    this.tint,
    this.quarterTurns = 0,
  });

  final String path;
  final BoxFit fit;
  final String semanticsLabel;
  final Color? tint;
  final int quarterTurns;

  @override
  Widget build(BuildContext context) => RotatedBox(
    quarterTurns: quarterTurns,
    child: path.endsWith('.svg')
        ? SvgPicture.asset(
            path,
            fit: fit,
            colorFilter: tint == null
                ? null
                : ColorFilter.mode(tint!, BlendMode.srcIn),
            semanticsLabel: semanticsLabel,
          )
        : Image.asset(
            path,
            fit: fit,
            color: tint,
            colorBlendMode: tint == null ? null : BlendMode.srcIn,
            semanticLabel: semanticsLabel,
            filterQuality: FilterQuality.high,
          ),
  );
}

class _CircuitInfoCard extends StatelessWidget {
  const _CircuitInfoCard({required this.event, required this.strings});
  final RaceEvent event;
  final AppStrings strings;

  @override
  Widget build(BuildContext context) {
    final metadata = metadataForCircuit(event.circuit.name);
    final asset = circuitAssetFor(event.circuit.name);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: LayoutBuilder(
          builder: (context, constraints) {
            final info = Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  event.circuit.name,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  [
                    event.circuit.locality,
                    event.circuit.country,
                  ].whereType<String>().join(', '),
                ),
                const SizedBox(height: 14),
                Text(
                  '${strings.circuitLength}: ${metadata.lengthKm?.toStringAsFixed(3) ?? '–'} km',
                ),
                const SizedBox(height: 6),
                Text('${strings.lapRecord}: ${metadata.lapRecord ?? '–'}'),
              ],
            );
            final flag = Text(
              _countryFlag(event.circuit.countryCode),
              style: const TextStyle(fontSize: 48),
              semanticsLabel: event.circuit.country,
            );
            Widget circuitGraphic({double? width, double? height}) => Container(
              width: width ?? 220,
              height: height ?? 130,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Theme.of(context).colorScheme.primaryContainer,
                    Theme.of(context).colorScheme.surfaceContainerHighest,
                  ],
                ),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: Theme.of(context).colorScheme.primary
                      .withValues(alpha: .35),
                ),
              ),
              child: asset == null
                  ? Icon(
                      Icons.route,
                      size: 72,
                      color: Theme.of(context).colorScheme.primary,
                    )
                  : _CircuitAsset(
                      path: asset,
                      fit: BoxFit.contain,
                      tint: Theme.of(context).colorScheme.primary,
                      semanticsLabel: event.circuit.name,
                      quarterTurns: circuitQuarterTurns(event.circuit.name),
                    ),
            );
            if (constraints.maxWidth < 600) {
              return Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  circuitGraphic(width: 132, height: 118),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(right: 44),
                          child: info,
                        ),
                        Positioned(right: 0, top: 0, child: flag),
                      ],
                    ),
                  ),
                ],
              );
            }
            return Row(
              children: [
                circuitGraphic(),
                const SizedBox(width: 22),
                Expanded(child: info),
                const SizedBox(width: 18),
                flag,
              ],
            );
          },
        ),
      ),
    );
  }
}

class _SessionResultsCard extends StatelessWidget {
  const _SessionResultsCard({
    required this.session,
    required this.strings,
    this.initiallyExpanded = false,
  });
  final SessionResults session;
  final AppStrings strings;
  final bool initiallyExpanded;

  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      initiallyExpanded:
          initiallyExpanded || session.type == 'R' || session.type == 'SPRINT',
      title: Text(
        _sessionLabel(session.type, session.name, strings),
        style: const TextStyle(fontWeight: FontWeight.w900),
      ),
      subtitle: Text(
        '${_date(session.startTimeUtc.toLocal(), strings.language)} • ${session.results.length}',
      ),
      children: [
        const Divider(height: 1),
        for (final result in session.results)
          Container(
            color: _categoryColor(result.category).withValues(alpha: .11),
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            child: Row(
              children: [
                SizedBox(
                  width: 34,
                  child: Text(
                    result.positionText,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w900,
                    ),
                  ),
                ),
                Container(
                  width: 4,
                  height: 34,
                  decoration: BoxDecoration(
                    color: _hexColor(result.teamColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                const SizedBox(width: 10),
                Text(
                  _nationalityFlag(result.driver.nationality),
                  style: const TextStyle(fontSize: 20),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${result.driver.givenName} ${result.driver.familyName}',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      Text(
                        [
                          result.teamName,
                          if (result.category != null) result.category!,
                        ].join(' • '),
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      result.time ?? result.status ?? '–',
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    if (result.points != null)
                      Text(
                        '${_number(result.points!)} ${strings.points}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                  ],
                ),
              ],
            ),
          ),
      ],
    ),
  );
}

class _StandingsPage extends ConsumerStatefulWidget {
  const _StandingsPage({required this.strings, required this.availableSeries});
  final AppStrings strings;
  final Set<String> availableSeries;
  @override
  ConsumerState<_StandingsPage> createState() => _StandingsPageState();
}

class _StandingsPageState extends ConsumerState<_StandingsPage> {
  bool _drivers = true;
  String _standingsCategory = 'GTP';

  @override
  Widget build(BuildContext context) {
    if (widget.availableSeries.isEmpty) {
      return _PageFrame(
        title: widget.strings.standings,
        subtitle: '',
        child: _EmptyCard(
          icon: Icons.category_outlined,
          message: widget.strings.chooseAny,
        ),
      );
    }
    final series = widget.availableSeries.contains('f1')
        ? 'f1'
        : (widget.availableSeries.toList()..sort()).first;
    final standings = ref.watch(standingsProvider(series));
    final strings = widget.strings;
    final supportsTeams = {'f1', 'wec', 'imsa'}.contains(series);
    final showDrivers = !supportsTeams || _drivers;
    final hasClassStandings = {'wec', 'imsa'}.contains(series);
    final categories = series == 'wec'
        ? const ['HYPERCAR', 'LMGT3']
        : const ['GTP', 'LMP2', 'GTD PRO', 'GTD'];
    final selectedCategory = categories.contains(_standingsCategory)
        ? _standingsCategory
        : categories.first;
    final teamClassificationLabel = series == 'wec'
        ? (selectedCategory == 'HYPERCAR'
              ? strings.manufacturers
              : strings.teams)
        : (series == 'imsa' ? strings.teams : strings.constructors);
    return _PageFrame(
      title: strings.standings,
      subtitle: '${_seriesLabel(series)} • 2026',
      child: Column(
        children: [
          if (supportsTeams)
            SegmentedButton<bool>(
              segments: [
                ButtonSegment(
                  value: true,
                  icon: const Icon(Icons.person),
                  label: Text(strings.drivers),
                ),
                ButtonSegment(
                  value: false,
                  icon: const Icon(Icons.groups),
                  label: Text(teamClassificationLabel),
                ),
              ],
              selected: {_drivers},
              onSelectionChanged: (value) =>
                  setState(() => _drivers = value.first),
            ),
          if (supportsTeams) const SizedBox(height: 16),
          standings.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(),
            ),
            error: (error, _) => _ErrorState(
              message: error.toString(),
              strings: strings,
              onRetry: () => ref.invalidate(standingsProvider(series)),
            ),
            data: (data) {
              final drivers = hasClassStandings
                  ? data.drivers.where(
                      (item) => item.category == selectedCategory,
                    )
                  : data.drivers;
              final teams = hasClassStandings
                  ? data.teams.where(
                      (item) => item.category == selectedCategory,
                    )
                  : data.teams;
              return Column(
                children: [
                  if (hasClassStandings)
                    SingleChildScrollView(
                      scrollDirection: Axis.horizontal,
                      child: SegmentedButton<String>(
                        segments: categories
                            .map(
                              (category) => ButtonSegment(
                                value: category,
                                label: Text(category),
                              ),
                            )
                            .toList(growable: false),
                        selected: {selectedCategory},
                        onSelectionChanged: (value) =>
                            setState(() => _standingsCategory = value.first),
                      ),
                    ),
                  if (hasClassStandings) const SizedBox(height: 16),
                  Card(
                    child: Column(
                      children: showDrivers
                          ? drivers
                                .map(
                                  (item) => _StandingRow(
                                    position: item.position,
                                    title:
                                        '${item.givenName} ${item.familyName}',
                                    subtitle: item.teamNames.isNotEmpty
                                        ? item.teamNames.join(' • ')
                                        : item.teamIds
                                              .map(_teamName)
                                              .join(' • '),
                                    color: item.teamColors.isNotEmpty
                                        ? _hexColor(item.teamColors.first)
                                        : _teamColor(
                                            item.teamIds.isEmpty
                                                ? null
                                                : item.teamIds.first,
                                          ),
                                    flag: _nationalityFlag(item.nationality),
                                    imageUrl: item.imageUrl,
                                    teamLogoAsset: null,
                                    initials:
                                        '${item.givenName.isEmpty ? '' : item.givenName[0]}${item.familyName.isEmpty ? '' : item.familyName[0]}',
                                    points: item.points,
                                    strings: strings,
                                  ),
                                )
                                .toList()
                          : teams
                                .map(
                                  (item) => _StandingRow(
                                    position: item.position,
                                    title: item.name,
                                    subtitle: '',
                                    color: item.color == null
                                        ? _teamColor(item.id)
                                        : _hexColor(item.color),
                                    flag: null,
                                    imageUrl: null,
                                    teamLogoAsset: _teamLogoAsset(
                                      item.id,
                                      item.name,
                                    ),
                                    initials: '',
                                    points: item.points,
                                    strings: strings,
                                  ),
                                )
                                .toList(),
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

class _StandingRow extends StatelessWidget {
  const _StandingRow({
    required this.position,
    required this.title,
    required this.subtitle,
    required this.points,
    required this.strings,
    required this.color,
    required this.flag,
    required this.imageUrl,
    required this.teamLogoAsset,
    required this.initials,
  });
  final int position;
  final String title;
  final String subtitle;
  final double points;
  final AppStrings strings;
  final Color color;
  final String? flag;
  final String? imageUrl;
  final String? teamLogoAsset;
  final String initials;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
        child: Row(
          children: [
            SizedBox(
              width: 28,
              child: Text(
                '$position',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            Container(
              width: 4,
              height: 52,
              margin: const EdgeInsets.only(right: 8),
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            if (imageUrl != null) ...[
              _DriverPortrait(imageUrl: imageUrl!, initials: initials),
              const SizedBox(width: 9),
            ] else if (initials.isNotEmpty) ...[
              _DriverInitials(initials: initials),
              const SizedBox(width: 9),
            ] else if (teamLogoAsset != null) ...[
              _TeamLogo(asset: teamLogoAsset!),
              const SizedBox(width: 9),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      if (flag != null) ...[
                        Text(flag!, style: const TextStyle(fontSize: 20)),
                        const SizedBox(width: 8),
                      ],
                      Flexible(
                        child: Text(
                          title,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                    ],
                  ),
                  if (subtitle.isNotEmpty)
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            Text(
              '${_number(points)} ${strings.points}',
              style: const TextStyle(fontWeight: FontWeight.w900),
            ),
          ],
        ),
      ),
      const Divider(height: 1),
    ],
  );
}

class _TeamLogo extends StatelessWidget {
  const _TeamLogo({required this.asset});
  final String asset;

  @override
  Widget build(BuildContext context) => Container(
    width: 68,
    height: 52,
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 7),
    decoration: BoxDecoration(
      color: Colors.white,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: Colors.black.withValues(alpha: 0.10)),
      boxShadow: [
        BoxShadow(
          color: Colors.black.withValues(alpha: 0.07),
          blurRadius: 6,
          offset: const Offset(0, 2),
        ),
      ],
    ),
    child: asset.endsWith('.svg')
        ? SvgPicture.asset(asset, fit: BoxFit.contain)
        : Image.asset(
            asset,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
          ),
  );
}

String? _teamLogoAsset(String id, String name) {
  final value = '$id $name'.toLowerCase();
  const aliases = <String, String>{
    'tf sport': 'team-tf-sport',
    'tf-sport': 'team-tf-sport',
    'by tf': 'team-tf-sport',
    'the bend manthey': 'team-manthey',
    'manthey dk': 'team-manthey',
    'manthey 1st': 'team-manthey',
    'team wrt': 'team-team-wrt',
    'team-wrt': 'team-team-wrt',
    'akkodis': 'team-akkodis-asp',
    'vista af corse': 'team-af-corse',
    'vista-af-corse': 'team-af-corse',
    'af corse': 'team-af-corse',
    'af-corse': 'team-af-corse',
    'garage 59': 'team-garage-59',
    'garage-59': 'team-garage-59',
    'heart of racing': 'team-heart-of-racing',
    'heart-of-racing': 'team-heart-of-racing',
    'proton competition': 'team-proton-competition',
    'proton-competition': 'team-proton-competition',
    'iron lynx': 'team-iron-lynx',
    'iron-lynx': 'team-iron-lynx',
    'turner motorsport': 'team-turner-motorsport',
    'winward': 'team-winward-racing',
    'vasser sullivan': 'team-vasser-sullivan',
    'vasser-sullivan': 'team-vasser-sullivan',
    'conquest racing': 'team-conquest-racing',
    'conquest-racing': 'team-conquest-racing',
    'wright motorsport': 'team-wright-motorsports',
    'wright-motorsport': 'team-wright-motorsports',
    'dragonspeed': 'team-dragonspeed',
    'gradient racing': 'team-gradient-racing',
    'gradient-racing': 'team-gradient-racing',
    'dxdt': 'team-dxdt-racing',
    'triarsi': 'team-triarsi',
    'pfaff': 'team-pfaff-motorsports',
    'ao racing': 'team-ao-racing',
    'ao-racing': 'team-ao-racing',
    'paul miller': 'team-paul-miller-racing',
    'paul-miller': 'team-paul-miller-racing',
    'pratt miller': 'team-pratt-miller',
    'pratt-miller': 'team-pratt-miller',
    'risi': 'team-risi-competizione',
    'jdc-miller': 'team-jdc-miller',
    'inter europol': 'team-inter-europol',
    'inter-europol': 'team-inter-europol',
    'united autosports': 'team-united-autosports',
    'united-autosports': 'team-united-autosports',
    'era motorsport': 'team-era-motorsport',
    'era-motorsport': 'team-era-motorsport',
    'mercedes': 'mercedes',
    'williams': 'williams',
    'haas': 'haas',
    'alpine': 'alpine',
    'team-penske': 'penske',
    'team penske': 'penske',
    'aston martin': 'astonmartin',
    'aston-martin': 'astonmartin',
    'red bull': 'redbull',
    'red_bull': 'redbull',
    'mclaren': 'mclaren',
    'ferrari': 'ferrari',
    'audi': 'audi',
    'cadillac': 'cadillac',
    'bmw': 'team-bmw',
    'toyota': 'toyota',
    'peugeot': 'peugeot',
    'porsche': 'porsche',
    'manthey': 'team-manthey',
    'proton': 'team-proton-competition',
    'ford': 'ford',
    'acura': 'acura',
    'honda': 'honda',
    'chevrolet': 'chevrolet',
    'corvette': 'chevrolet',
    'mazda': 'mazda',
    'lamborghini': 'lamborghini',
  };
  for (final entry in aliases.entries) {
    if (value.contains(entry.key)) {
      final extension = entry.value.startsWith('team-') ? 'png' : 'svg';
      return 'assets/team_logos/${entry.value}.$extension';
    }
  }
  return null;
}

class _DriverPortrait extends StatelessWidget {
  const _DriverPortrait({required this.imageUrl, required this.initials});

  final String imageUrl;
  final String initials;

  String get _faceUrl {
    if (imageUrl.contains('res.cloudinary.com/') &&
        !imageUrl.contains('/image/upload/')) {
      final cloudNameEnd = imageUrl.indexOf(
        '/',
        'https://res.cloudinary.com/'.length,
      );
      final version = imageUrl.indexOf('/v', cloudNameEnd);
      if (cloudNameEnd > 0 && version > cloudNameEnd) {
        return '${imageUrl.substring(0, cloudNameEnd)}/image/upload/c_thumb,g_face,w_320,h_320,q_auto,f_auto${imageUrl.substring(version)}';
      }
    }
    if (!imageUrl.contains('/image/upload/')) return imageUrl;
    final upload = imageUrl.indexOf('/image/upload/') + '/image/upload/'.length;
    final version = imageUrl.indexOf('/v', upload);
    if (version < 0) return imageUrl;
    return '${imageUrl.substring(0, upload)}c_thumb,g_face,w_320,h_320,q_auto,f_auto${imageUrl.substring(version)}';
  }

  double get _scale {
    if (imageUrl.contains('assets/portraits/indycar/') ||
        imageUrl.contains('assets/portraits/indynxt/')) {
      return 3;
    }
    if (imageUrl.contains('imsa.com/')) return 1.28;
    if (imageUrl.contains('wikimedia.org/')) return 2.2;
    return 1;
  }

  Alignment get _alignment {
    if (imageUrl.contains('assets/portraits/indycar/') ||
        imageUrl.contains('assets/portraits/indynxt/')) {
      return const Alignment(0, -0.35);
    }
    return imageUrl.contains('imsa.com/') ||
            imageUrl.contains('indycar.com/') ||
            imageUrl.contains('indynxt.com/')
        ? Alignment.topCenter
        : Alignment.center;
  }

  Widget _image() {
    if (imageUrl.startsWith('assets/portraits/')) {
      return Image.asset(
        imageUrl,
        fit: BoxFit.cover,
        alignment: _alignment,
        errorBuilder: (_, _, _) => _DriverInitials(initials: initials),
      );
    }
    return Image.network(
      _faceUrl,
      fit: BoxFit.cover,
      alignment: _alignment,
      errorBuilder: (_, _, _) => _DriverInitials(initials: initials),
    );
  }

  @override
  Widget build(BuildContext context) => Container(
    width: 58,
    height: 58,
    clipBehavior: Clip.antiAlias,
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(14),
    ),
    child: Transform.scale(
      scale: _scale,
      alignment: _alignment,
      child: _image(),
    ),
  );
}

class _DriverInitials extends StatelessWidget {
  const _DriverInitials({required this.initials});
  final String initials;

  @override
  Widget build(BuildContext context) => Container(
    width: 46,
    height: 46,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      shape: BoxShape.circle,
    ),
    child: Text(initials, style: const TextStyle(fontWeight: FontWeight.w900)),
  );
}

class _SettingsPage extends ConsumerWidget {
  const _SettingsPage({required this.settings, required this.strings});
  final AppSettings settings;
  final AppStrings strings;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final controller = ref.read(settingsProvider.notifier);
    return _PageFrame(
      title: strings.settings,
      subtitle: strings.customize,
      child: Column(
        children: [
          _CategorySelectionCard(
            title: strings.motorsportCategories,
            subtitle: strings.chooseAny,
            items: const [
              ('f1', 'F1', 'assets/brands/f1-official.svg', null),
              ('f2', 'F2', 'assets/brands/f2-official.svg', null),
              ('f3', 'F3', 'assets/brands/f3-official.svg', null),
              ('imsa', 'IMSA', 'assets/brands/imsa.svg', null),
              (
                'indycar',
                'INDYCAR',
                'assets/brands/indycar-official.png',
                null,
              ),
              (
                'indynxt',
                'INDY NXT',
                'assets/brands/indynxt-official.png',
                null,
              ),
              ('wec', 'WEC', 'assets/brands/wec-official.png', null),
            ],
            selected: settings.motorsportCategories,
            onToggle: (id) {
              final next = {...settings.motorsportCategories};
              next.contains(id) ? next.remove(id) : next.add(id);
              controller.setMotorsportCategories(next);
            },
          ),
          const SizedBox(height: 12),
          _CategorySelectionCard(
            title: strings.esportCategories,
            subtitle: settings.language == AppLanguage.polish
                ? 'Wkrótce — przygotowujemy integracje wyścigów wirtualnych.'
                : 'Coming soon — virtual racing integrations are in development.',
            items: const [
              (
                'iracing',
                'iRacing',
                'assets/brands/iracing-official-light.png',
                'assets/brands/iracing-official-dark.png',
              ),
              (
                'lmu',
                'Le Mans Ultimate',
                'assets/brands/lmu-official.svg',
                null,
              ),
            ],
            selected: settings.esportCategories,
            onToggle: controller.toggleEsportCategory,
            comingSoon: true,
          ),
          const SizedBox(height: 12),
          Card(
            child: SwitchListTile(
              secondary: const Icon(Icons.dark_mode_outlined),
              title: Text(
                strings.darkMode,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(strings.darkModeHint),
              value: Theme.of(context).brightness == Brightness.dark,
              onChanged: (_) => ref
                  .read(themeModeProvider.notifier)
                  .toggle(Theme.of(context).brightness),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.language),
                      const SizedBox(width: 12),
                      Text(
                        strings.languageLabel,
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  SegmentedButton<AppLanguage>(
                    segments: [
                      ButtonSegment(
                        value: AppLanguage.polish,
                        label: Text(strings.polish),
                      ),
                      ButtonSegment(
                        value: AppLanguage.english,
                        label: Text(strings.english),
                      ),
                    ],
                    selected: {settings.language},
                    onSelectionChanged: (value) =>
                        controller.setLanguage(value.first),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.schedule),
                      const SizedBox(width: 12),
                      Text(
                        strings.eventTime,
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  SegmentedButton<EventTimeMode>(
                    segments: [
                      ButtonSegment(
                        value: EventTimeMode.local,
                        icon: const Icon(Icons.home),
                        label: Text(strings.localTime),
                      ),
                      ButtonSegment(
                        value: EventTimeMode.track,
                        icon: const Icon(Icons.sports_score),
                        label: Text(strings.trackTime),
                      ),
                    ],
                    selected: {settings.timeMode},
                    onSelectionChanged: (value) =>
                        controller.setTimeMode(value.first),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: const Icon(Icons.privacy_tip_outlined),
              title: Text(
                strings.privacyPolicy,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(strings.privacyPolicyHint),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => _showPrivacyPolicy(context, strings),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: const Icon(Icons.info_outline),
              title: Text(
                strings.aboutSecar,
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(strings.independentApp),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => showDialog<void>(
                context: context,
                builder: (context) => AlertDialog(
                  title: Text(strings.aboutSecar),
                  content: SelectableText(strings.legalNotice),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: Text(strings.close),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

Future<void> _showPrivacyPolicy(BuildContext context, AppStrings strings) =>
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(strings.privacyPolicy),
        content: SizedBox(
          width: 620,
          child: SingleChildScrollView(
            child: SelectableText(
              strings.language == AppLanguage.english
                  ? _privacyPolicyEnglish
                  : _privacyPolicyPolish,
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: Text(strings.close),
          ),
        ],
      ),
    );

const _privacyPolicyEnglish = '''Effective date: 27 August 2026

Developer: So_Y
Contact: marcin.soy@gmail.com
Public version: https://github.com/SoY256/MotorSport-Calendar/blob/main/PRIVACY.md

Secar is a motorsport calendar and results application. Secar does not require an account and the developer does not collect, sell or share personal data for advertising or profiling.

Data stored on your device
Secar stores your selected language, theme, time display, event visibility and selected motorsport categories locally on your device. This information is used only to remember your preferences. It remains on the device until you clear the application's data or uninstall it.

Network access and third-party content
Secar uses encrypted HTTPS connections to retrieve public motorsport schedules, results, standings and related images. Requests may be sent to GitHub-hosted Secar data and to the image hosts referenced by that content, including Cloudinary and Wikimedia. Like other internet services, those providers may receive technical information necessary to deliver a request, such as the IP address, date and time, requested resource and browser or application user agent. This processing is controlled by the respective provider under its own privacy terms; Secar's developer does not use it to identify users.

Secar contains no advertising SDK, analytics SDK, crash-reporting SDK or user-tracking system. It does not request access to location, contacts, photos, microphone, camera or advertising identifiers.

Data sharing, retention and deletion
The developer does not receive or retain personal data through Secar and therefore does not sell or share it. Locally saved preferences can be deleted at any time by clearing Secar's application data in Android settings or uninstalling the application. Technical server logs, if created by third-party hosting providers, are retained and deleted according to those providers' policies.

Security
Network data is transmitted using HTTPS. No method of electronic transmission is guaranteed to be completely secure, but Secar limits data access to what is necessary to provide its content.

Children
Secar is a general-audience motorsport information application and does not knowingly collect personal information from children.

Changes and contact
This policy may be updated when Secar's features or data practices change. The effective date will be updated on the public policy page. Questions and privacy requests may be sent to marcin.soy@gmail.com.''';

const _privacyPolicyPolish = '''Data wejścia w życie: 27 sierpnia 2026 r.

Deweloper: So_Y
Kontakt: marcin.soy@gmail.com
Wersja publiczna: https://github.com/SoY256/MotorSport-Calendar/blob/main/PRIVACY.md

Secar jest aplikacją prezentującą kalendarz, wyniki i klasyfikacje sportów motorowych. Nie wymaga konta, a deweloper nie zbiera, nie sprzedaje ani nie udostępnia danych osobowych na potrzeby reklam lub profilowania.

Dane zapisane na urządzeniu
Secar zapisuje lokalnie wybrany język, motyw, sposób wyświetlania czasu, widoczność wydarzeń i wybrane kategorie sportów motorowych. Dane te służą wyłącznie do zapamiętania preferencji. Pozostają na urządzeniu do czasu wyczyszczenia danych aplikacji lub jej odinstalowania.

Dostęp do sieci i treści podmiotów trzecich
Secar używa szyfrowanych połączeń HTTPS do pobierania publicznych terminarzy, wyników, klasyfikacji i powiązanych obrazów. Żądania mogą trafiać do danych Secar hostowanych przez GitHub oraz serwerów obrazów wskazanych w tych danych, w tym Cloudinary i Wikimedia. Podobnie jak inne usługi internetowe, dostawcy ci mogą otrzymywać informacje techniczne niezbędne do obsługi żądania, takie jak adres IP, data i godzina, żądany zasób oraz identyfikator przeglądarki lub aplikacji. Przetwarzanie to odbywa się na zasadach danego dostawcy; deweloper Secar nie wykorzystuje go do identyfikacji użytkowników.

Secar nie zawiera reklam, narzędzi analitycznych, narzędzi raportowania awarii ani systemu śledzenia użytkowników. Nie prosi o dostęp do lokalizacji, kontaktów, zdjęć, mikrofonu, aparatu ani identyfikatorów reklamowych.

Udostępnianie, przechowywanie i usuwanie danych
Deweloper nie otrzymuje ani nie przechowuje danych osobowych za pośrednictwem Secar, dlatego ich nie sprzedaje ani nie udostępnia. Lokalne preferencje można usunąć w dowolnym momencie przez wyczyszczenie danych Secar w ustawieniach Androida lub odinstalowanie aplikacji. Ewentualne techniczne logi serwerów zewnętrznych dostawców są przechowywane i usuwane zgodnie z ich zasadami.

Bezpieczeństwo
Dane sieciowe są przesyłane przez HTTPS. Żadna metoda transmisji elektronicznej nie gwarantuje pełnego bezpieczeństwa, jednak Secar ogranicza dostęp do danych do zakresu niezbędnego do dostarczenia treści.

Dzieci
Secar jest ogólnodostępną aplikacją informacyjną o sportach motorowych i świadomie nie zbiera danych osobowych dzieci.

Zmiany i kontakt
Polityka może być aktualizowana, gdy zmienią się funkcje Secar lub sposób przetwarzania danych. Data wejścia w życie zostanie zaktualizowana na publicznej stronie. Pytania i żądania dotyczące prywatności można kierować na marcin.soy@gmail.com.''';

class _CategorySelectionCard extends StatelessWidget {
  const _CategorySelectionCard({
    required this.title,
    required this.subtitle,
    required this.items,
    required this.selected,
    required this.onToggle,
    this.comingSoon = false,
  });
  final String title;
  final String subtitle;
  final List<(String, String, String, String?)> items;
  final Set<String> selected;
  final ValueChanged<String> onToggle;
  final bool comingSoon;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title.toUpperCase(),
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w900,
                    letterSpacing: .8,
                  ),
                ),
              ),
              if (comingSoon)
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 5,
                  ),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      colors: [Color(0xFFE10600), Color(0xFFFF3D3D)],
                    ),
                    borderRadius: BorderRadius.circular(30),
                  ),
                  child: const Text(
                    'COMING SOON',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.w900,
                      letterSpacing: .8,
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 4),
          Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 14),
          LayoutBuilder(
            builder: (context, constraints) {
              final width = constraints.maxWidth >= 700
                  ? (constraints.maxWidth - 24) / 3
                  : (constraints.maxWidth - 12) / 2;
              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: items.map((item) {
                  final active = selected.contains(item.$1);
                  return SizedBox(
                    width: width,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(16),
                      onTap: comingSoon ? null : () => onToggle(item.$1),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        height: 116,
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: active && !comingSoon
                              ? Theme.of(context).colorScheme.primaryContainer
                              : Theme.of(context).colorScheme.surfaceContainer,
                          border: Border.all(
                            color: active && !comingSoon
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).dividerColor,
                            width: active && !comingSoon ? 2 : 1,
                          ),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Stack(
                          children: [
                            Positioned.fill(
                              child: Opacity(
                                opacity: comingSoon ? .55 : 1,
                                child: _BrandLogo(
                                  path: item.$3,
                                  darkPath: item.$4,
                                  fallbackLabel: item.$2,
                                ),
                              ),
                            ),
                            if (!comingSoon)
                              Align(
                                alignment: Alignment.topRight,
                                child: DecoratedBox(
                                  decoration: const BoxDecoration(
                                    color: Colors.white,
                                    shape: BoxShape.circle,
                                  ),
                                  child: Icon(
                                    active
                                        ? Icons.check_circle
                                        : Icons.circle_outlined,
                                    color: active
                                        ? Theme.of(context).colorScheme.primary
                                        : const Color(0xFF455A64),
                                  ),
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  );
                }).toList(),
              );
            },
          ),
        ],
      ),
    ),
  );
}

class _BrandLogo extends StatelessWidget {
  const _BrandLogo({
    required this.path,
    required this.fallbackLabel,
    this.darkPath,
  });
  final String path;
  final String? darkPath;
  final String fallbackLabel;

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final resolvedPath = isDark && darkPath != null ? darkPath! : path;
    final isWec = path.endsWith('wec-official.png');
    final isLmu = path.endsWith('lmu-official.svg');
    final isIracing = path.contains('iracing-official');
    final isF1 = path.endsWith('f1-official.svg');
    final fallback = Center(
      child: Text(
        fallbackLabel,
        textAlign: TextAlign.center,
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
      ),
    );
    Widget image = resolvedPath.endsWith('.svg')
        ? SvgPicture.asset(
            resolvedPath,
            fit: isF1 ? BoxFit.fitWidth : BoxFit.contain,
            placeholderBuilder: (_) => fallback,
            errorBuilder: (_, _, _) => fallback,
          )
        : Image.asset(
            resolvedPath,
            fit: BoxFit.contain,
            filterQuality: FilterQuality.high,
            errorBuilder: (_, _, _) => fallback,
          );
    return Container(
      width: double.infinity,
      height: double.infinity,
      padding: EdgeInsets.all(isF1 ? 2 : 10),
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(
        color: isWec
            ? const Color(0xFF203B78)
            : (isLmu || (isIracing && isDark)
                  ? const Color(0xFF171A21)
                  : Colors.white),
        borderRadius: BorderRadius.circular(11),
      ),
      child: image,
    );
  }
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard({required this.icon, required this.message});
  final IconData icon;
  final String message;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        children: [
          Icon(icon, size: 44),
          const SizedBox(height: 12),
          Text(message, textAlign: TextAlign.center),
        ],
      ),
    ),
  );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({
    required this.message,
    required this.strings,
    required this.onRetry,
  });
  final String message;
  final AppStrings strings;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Center(
    child: Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.cloud_off_rounded, size: 52),
          const SizedBox(height: 12),
          Text(
            strings.loadingError,
            style: const TextStyle(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: Text(strings.retry),
          ),
        ],
      ),
    ),
  );
}

RaceEvent _nearestEvent(List<RaceEvent> events) {
  final now = DateTime.now().toUtc();
  return _nextEvent(events, now) ??
      events.lastWhere((event) => !event.cancelled);
}

RaceEvent? _nextEvent(List<RaceEvent> events, DateTime now) {
  for (final event in events) {
    if (!event.cancelled && event.endsAt.isAfter(now)) return event;
  }
  return null;
}

String _sessionLabel(String type, String original, AppStrings strings) {
  if (strings.language == AppLanguage.english) return original;
  return switch (type) {
    'FP1' => 'Trening 1',
    'FP2' => 'Trening 2',
    'FP3' => 'Trening 3',
    'SQ' => 'Kwalifikacje sprintu',
    'SPRINT' => 'Sprint',
    'Q' => 'Kwalifikacje',
    'Q1' => 'Kwalifikacje 1',
    'Q2' => 'Kwalifikacje 2',
    'QA' => 'Kwalifikacje – grupa A',
    'QB' => 'Kwalifikacje – grupa B',
    'R' => 'Wyścig',
    'R1' => 'Wyścig 1',
    'R2' => 'Wyścig 2',
    _ => original,
  };
}

int _resultOrder(String type) => switch (type) {
  'R' => 0,
  'R2' => 0,
  'R1' => 1,
  'SPRINT' => 2,
  'Q2' => 3,
  'Q1' => 4,
  'QB' => 5,
  'QA' => 6,
  'Q' => 7,
  'SQ' => 8,
  'FP3' => 9,
  'FP2' => 10,
  'FP1' => 11,
  _ => 12,
};

String _teamName(String id) => switch (id) {
  'red_bull' => 'Oracle Red Bull Racing',
  'rb' => 'Visa Cash App Racing Bulls',
  'alpine' => 'BWT Alpine F1 Team',
  'haas' => 'MoneyGram Haas F1 Team',
  'aston_martin' => 'Aston Martin Aramco',
  'cadillac' => 'Cadillac Formula 1 Team',
  'campos' => 'Campos Racing',
  'prema' => 'PREMA Racing',
  'invicta' => 'Invicta Racing',
  'rodin' => 'Rodin Motorsport',
  'aix' => 'AIX Racing',
  'dams' => 'DAMS Lucas Oil',
  'hitech' => 'Hitech TGR',
  'trident' => 'Trident',
  'art' => 'ART Grand Prix',
  'van-amersfoort' => 'Van Amersfoort Racing',
  'mp' => 'MP Motorsport',
  'chip_ganassi' => 'Chip Ganassi Racing',
  'andretti' => 'Andretti Global',
  'arrow_mclaren' => 'Arrow McLaren',
  'penske' => 'Team Penske',
  'meyer_shank' => 'Meyer Shank Racing',
  'juncos' => 'Juncos Hollinger Racing',
  'hmd' => 'HMD Motorsports',
  'cape' => 'Cape Motorsports',
  'foyt' => 'A.J. Foyt Enterprises',
  'abel' => 'Abel Motorsports',
  'cusick' => 'Cusick Morgan Motorsports',
  'toyota' => 'Toyota Gazoo Racing',
  'bmw' => 'BMW M Team WRT',
  'corvette' => 'Corvette Racing',
  'porsche' => 'Porsche',
  'mercedes' => 'Mercedes-AMG Petronas',
  'ferrari' => 'Scuderia Ferrari HP',
  'mclaren' => 'McLaren Formula 1 Team',
  'williams' => 'Atlassian Williams F1 Team',
  'audi' => 'Audi Revolut F1 Team',
  _ => id.replaceAll('_', ' ').replaceAll('-', ' '),
};

Color _teamColor(String? id) => switch (id) {
  'mercedes' => const Color(0xFF00D7B6),
  'ferrari' => const Color(0xFFED1131),
  'mclaren' => const Color(0xFFF47600),
  'red_bull' => const Color(0xFF4781D7),
  'rb' => const Color(0xFF6C98FF),
  'alpine' => const Color(0xFF00A1E8),
  'haas' => const Color(0xFF9C9FA2),
  'audi' => const Color(0xFFF50537),
  'williams' => const Color(0xFF1868DB),
  'aston_martin' => const Color(0xFF229971),
  'cadillac' => const Color(0xFFB8B8B8),
  'campos' => const Color(0xFFE5D100),
  'prema' => const Color(0xFFE10600),
  'invicta' => const Color(0xFF26A9E0),
  'rodin' => const Color(0xFFF36F21),
  'aix' => const Color(0xFF00A651),
  'dams' => const Color(0xFF0067B1),
  'hitech' => const Color(0xFFED1C24),
  'trident' => const Color(0xFF183883),
  'art' => const Color(0xFFEE3124),
  'van-amersfoort' => const Color(0xFFF58220),
  'mp' => const Color(0xFFF15A29),
  'chip_ganassi' => const Color(0xFF0B5BA7),
  'andretti' => const Color(0xFFE31B23),
  'arrow_mclaren' => const Color(0xFFFF6C0C),
  'penske' => const Color(0xFF143B78),
  'meyer_shank' => const Color(0xFFE91E63),
  'juncos' => const Color(0xFF4A148C),
  'hmd' => const Color(0xFF202A44),
  'cape' => const Color(0xFF00A3E0),
  'foyt' => const Color(0xFFD71920),
  'abel' => const Color(0xFF111111),
  'cusick' => const Color(0xFF8BC34A),
  'toyota' => const Color(0xFFE50000),
  'bmw' => const Color(0xFF0066B1),
  'corvette' => const Color(0xFFFFD600),
  'porsche' => const Color(0xFFD50000),
  _ => Colors.grey,
};

String _nationalityFlag(String? nationality) {
  if (nationality?.contains(',') ?? false) {
    return nationality!
        .split(',')
        .map((country) => _nationalityFlag(country.trim()))
        .join();
  }
  return switch (nationality?.toUpperCase()) {
    'USA' || 'US' => '🇺🇸',
    'GBR' || 'GB' => '🇬🇧',
    'ESP' || 'ES' => '🇪🇸',
    'DNK' || 'DEN' || 'DK' => '🇩🇰',
    'SWE' || 'SE' => '🇸🇪',
    'NZL' || 'NZ' => '🇳🇿',
    'NLD' || 'NED' || 'NL' => '🇳🇱',
    'BRA' || 'BR' => '🇧🇷',
    'MEX' || 'MX' => '🇲🇽',
    'FRA' || 'FR' => '🇫🇷',
    'DEU' || 'GER' || 'DE' => '🇩🇪',
    'JPN' || 'JP' => '🇯🇵',
    'POL' || 'PL' => '🇵🇱',
    'CAN' || 'CA' => '🇨🇦',
    'ITA' || 'IT' => '🇮🇹',
    'AUS' || 'AU' => '🇦🇺',
    'COL' || 'CO' => '🇨🇴',
    'NOR' || 'NO' => '🇳🇴',
    'CHE' || 'SUI' || 'CH' => '🇨🇭',
    'BEL' || 'BE' => '🇧🇪',
    'PRT' || 'POR' || 'PT' => '🇵🇹',
    'ARG' || 'AR' => '🇦🇷',
    'AUT' || 'AT' => '🇦🇹',
    'ZAF' || 'RSA' || 'ZA' => '🇿🇦',
    'IRL' || 'IE' => '🇮🇪',
    'VEN' || 'VE' => '🇻🇪',
    'CHL' || 'CL' => '🇨🇱',
    'URY' || 'UY' => '🇺🇾',
    'TUR' || 'TR' => '🇹🇷',
    'ROU' || 'RO' => '🇷🇴',
    'KOR' || 'KR' => '🇰🇷',
    'CHN' || 'CN' => '🇨🇳',
    'EST' || 'EE' => '🇪🇪',
    'IDN' || 'INA' || 'ID' => '🇮🇩',
    'RUS' || 'RU' => '🇷🇺',
    'QAT' || 'QA' => '🇶🇦',
    'LUX' || 'LU' => '🇱🇺',
    'CYM' || 'KY' => '🇰🇾',
    'ITALIAN' => '🇮🇹',
    'BRITISH' => '🇬🇧',
    'MONEGASQUE' => '🇲🇨',
    'DUTCH' => '🇳🇱',
    'AUSTRALIAN' => '🇦🇺',
    'FRENCH' => '🇫🇷',
    'SPANISH' => '🇪🇸',
    'GERMAN' => '🇩🇪',
    'BRAZILIAN' => '🇧🇷',
    'CANADIAN' => '🇨🇦',
    'NEW ZEALANDER' => '🇳🇿',
    'MEXICAN' => '🇲🇽',
    'AMERICAN' => '🇺🇸',
    'DANISH' => '🇩🇰',
    'SWEDISH' => '🇸🇪',
    'POLISH' => '🇵🇱',
    'JAPANESE' => '🇯🇵',
    'BULGARIAN' => '🇧🇬',
    'IRISH' => '🇮🇪',
    'INDIAN' => '🇮🇳',
    'NORWEGIAN' => '🇳🇴',
    'THAI' => '🇹🇭',
    'PARAGUAYAN' => '🇵🇾',
    'COLOMBIAN' => '🇨🇴',
    'FINNISH' => '🇫🇮',
    'CHINESE' => '🇨🇳',
    'SRI LANKAN' => '🇱🇰',
    'SINGAPOREAN' => '🇸🇬',
    'SOUTH AFRICAN' => '🇿🇦',
    _ => '🏁',
  };
}

String _seriesLabel(String id) => switch (id.toLowerCase()) {
  'f1' => 'F1',
  'f2' => 'F2',
  'f3' => 'F3',
  'wec' => 'WEC',
  'imsa' => 'IMSA',
  'indycar' => 'INDYCAR',
  'indynxt' => 'INDY NXT',
  _ => id.toUpperCase(),
};

Color _seriesColor(String id) => switch (id.toLowerCase()) {
  'f1' => const Color(0xFFE10600),
  'f2' => const Color(0xFF1565C0),
  'f3' => const Color(0xFF7B1FA2),
  'wec' => const Color(0xFF00695C),
  'imsa' => const Color(0xFFEF6C00),
  'indycar' => const Color(0xFFD71920),
  'indynxt' => const Color(0xFFE31837),
  _ => const Color(0xFF455A64),
};

String _countryFlag(String? code) => switch (code) {
  'AUS' => '🇦🇺',
  'CHN' => '🇨🇳',
  'JPN' => '🇯🇵',
  'USA' => '🇺🇸',
  'CAN' => '🇨🇦',
  'MCO' => '🇲🇨',
  'ESP' => '🇪🇸',
  'AUT' => '🇦🇹',
  'GBR' => '🇬🇧',
  'BEL' => '🇧🇪',
  'HUN' => '🇭🇺',
  'NLD' => '🇳🇱',
  'ITA' => '🇮🇹',
  'AZE' => '🇦🇿',
  'MYS' => '🇲🇾',
  'SGP' => '🇸🇬',
  'MEX' => '🇲🇽',
  'BRA' => '🇧🇷',
  'QAT' => '🇶🇦',
  'ARE' => '🇦🇪',
  'SAU' => '🇸🇦',
  _ => '🏁',
};

String _zoneName(
  RaceSession session,
  AppSettings settings,
  AppStrings strings,
) {
  if (settings.timeMode == EventTimeMode.local) return strings.localTime;
  return session.trackTimeZone?.split('/').last.replaceAll('_', ' ') ??
      strings.trackTime;
}

List<int>? _trackParts(RaceSession session) {
  final value = session.startTimeTrack;
  if (value == null || value.length < 16) return null;
  return [
    int.parse(value.substring(5, 7)),
    int.parse(value.substring(8, 10)),
    int.parse(value.substring(11, 13)),
    int.parse(value.substring(14, 16)),
  ];
}

String _sessionDate(RaceSession session, AppSettings settings) {
  final track = settings.timeMode == EventTimeMode.track
      ? _trackParts(session)
      : null;
  if (track != null) {
    return '${_two(track[1])} ${_monthName(track[0], settings.language)}';
  }
  return _date(session.startTimeUtc.toLocal(), settings.language);
}

String _sessionTime(RaceSession session, EventTimeMode mode) {
  final track = mode == EventTimeMode.track ? _trackParts(session) : null;
  if (track != null) return '${_two(track[2])}:${_two(track[3])}';
  return _time(session.startTimeUtc.toLocal());
}

Color _hexColor(String? value) {
  if (value == null) return Colors.grey;
  return Color(int.parse(value.replaceFirst('#', '0xFF')));
}

Color _categoryColor(String? category) => switch (category) {
  'GTP' => const Color(0xFFE10600),
  'LMP2' => const Color(0xFF1976D2),
  'GTD PRO' => const Color(0xFFFFC107),
  'GTD' => const Color(0xFF43A047),
  _ => Colors.transparent,
};

String _number(double value) => value == value.roundToDouble()
    ? value.toInt().toString()
    : value.toStringAsFixed(1);
const _monthsPl = [
  'STY',
  'LUT',
  'MAR',
  'KWI',
  'MAJ',
  'CZE',
  'LIP',
  'SIE',
  'WRZ',
  'PAŹ',
  'LIS',
  'GRU',
];
const _monthsEn = [
  'JAN',
  'FEB',
  'MAR',
  'APR',
  'MAY',
  'JUN',
  'JUL',
  'AUG',
  'SEP',
  'OCT',
  'NOV',
  'DEC',
];
String _two(int value) => value.toString().padLeft(2, '0');
String _monthName(int month, AppLanguage language) =>
    (language == AppLanguage.english ? _monthsEn : _monthsPl)[month - 1];
String _date(DateTime value, AppLanguage language) =>
    '${_two(value.day)} ${_monthName(value.month, language)}';
String _time(DateTime value) => '${_two(value.hour)}:${_two(value.minute)}';
String _dateTime(DateTime value, AppLanguage language) =>
    '${_date(value, language)} ${value.year}, ${_time(value)}';

List<String> _weekdayNames(AppLanguage language) =>
    language == AppLanguage.english
    ? const ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
    : const ['PON', 'WT', 'ŚR', 'CZW', 'PT', 'SOB', 'NIE'];
