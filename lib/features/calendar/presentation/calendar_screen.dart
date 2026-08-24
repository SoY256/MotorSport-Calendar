import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_svg/flutter_svg.dart';

import '../../../core/localization/app_strings.dart';
import '../../../core/widgets/app_logo.dart';
import '../../settings/domain/app_settings.dart';
import '../../settings/presentation/settings_controller.dart';
import '../../settings/presentation/theme_controller.dart';
import '../domain/circuit_metadata.dart';
import '../domain/race_event.dart';
import 'calendar_providers.dart';

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  int _page = 0;
  String? _selectedEventId;
  String? _activeSeriesId;

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
            onEventTap: (event) => setState(() {
              _selectedEventId = event.id;
              _page = 2;
            }),
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
            onEventTap: (event) => setState(() {
              _selectedEventId = event.id;
              _page = 2;
            }),
          ),
          2 when selected != null => _ResultsPage(
            data: data,
            selected: selected,
            selectedSeries: selectedSeries,
            settings: settings,
            strings: strings,
            onSelected: (event) => setState(() => _selectedEventId = event.id),
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

    return Scaffold(
      body: SafeArea(
        child: Row(
          children: [
            if (wide)
              NavigationRail(
                selectedIndex: _page,
                onDestinationSelected: (value) => setState(() => _page = value),
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
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: _page,
              onDestinationSelected: (value) => setState(() => _page = value),
              destinations: destinations,
            ),
    );
  }
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
      color: Theme.of(context).colorScheme.surfaceContainerLow,
      child: SizedBox(
        height: 58,
        child: ListView(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
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
        : Colors.transparent,
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
    this.actions = const [],
  });
  final String title;
  final String subtitle;
  final Widget child;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => CustomScrollView(
    slivers: [
      SliverAppBar(
        pinned: true,
        toolbarHeight: 72,
        title: const AppLogo(),
        actions: actions,
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
                  Text(
                    title,
                    style: Theme.of(context).textTheme.headlineMedium
                        ?.copyWith(fontWeight: FontWeight.w900),
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
    final events = settings.showPastEvents
        ? matching
        : matching.where((event) => event.endsAt.isAfter(now)).toList();
    return _PageFrame(
      title: '${strings.season} ${data.events.first.season}',
      subtitle:
          '${strings.rounds(data.events.where((event) => !event.cancelled).length)} • ${strings.timesInZone}',
      actions: [
        IconButton(
          tooltip: strings.refresh,
          onPressed: () => ref.invalidate(calendarProvider),
          icon: const Icon(Icons.refresh_rounded),
        ),
        const SizedBox(width: 8),
      ],
      child: Column(
        children: [
          if (matching.isNotEmpty)
            _NextRaceHero(
              event: _nearestEvent(matching),
              settings: settings,
              strings: strings,
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
  });
  final RaceEvent event;
  final AppSettings settings;
  final AppStrings strings;

  @override
  Widget build(BuildContext context) {
    final first = event.sessions.first;
    final last = event.sessions.last;
    final seriesColor = _seriesColor(event.seriesId);
    final circuitAsset = circuitAssetFor(event.circuit.name);
    return Container(
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
                child: Padding(
                  padding: const EdgeInsets.only(right: 18),
                  child: Text(
                    _countryFlag(event.circuit.countryCode),
                    style: const TextStyle(fontSize: 132, height: 1),
                  ),
                ),
              ),
            ),
          ),
          if (circuitAsset != null)
            Positioned(
              right: 16,
              top: 18,
              bottom: 18,
              width: 235,
              child: Opacity(
                opacity: .42,
                child: _CircuitAsset(
                  path: circuitAsset,
                  fit: BoxFit.contain,
                  tint: Colors.white,
                  semanticsLabel: event.circuit.name,
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
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Row(
            children: [
              SizedBox(
                width: 52,
                child: Text(
                  _countryFlag(event.circuit.countryCode),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 34),
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
                        if (completed)
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
                    Text(
                      '${_seriesLabel(event.seriesId)} • R${event.round ?? '–'} • ${event.circuit.name}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                        fontSize: 13,
                      ),
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
  });
  final CalendarData data;
  final AppSettings settings;
  final AppStrings strings;
  final ValueChanged<RaceEvent> onEventTap;
  final Set<String> availableSeries;
  final Set<String> selectedSeries;
  final ValueChanged<Set<String>> onSeriesChanged;

  @override
  State<_CalendarGridPage> createState() => _CalendarGridPageState();
}

class _CalendarGridPageState extends State<_CalendarGridPage> {
  bool _month = true;
  late DateTime _anchor = DateTime.now();

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
                onSelectionChanged: (value) =>
                    setState(() => _month = value.first),
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
                      onPressed: () => setState(
                        () => _anchor = _month
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
                      onPressed: () => setState(
                        () => _anchor = _month
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
                      return DecoratedBox(
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
                                          onTap: () => widget.onEventTap(
                                            events[eventIndex],
                                          ),
                                        ),
                                  ),
                                ),
                            ],
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
}

class _SeriesBadge extends StatelessWidget {
  const _SeriesBadge({required this.seriesId, this.compact = false});
  final String seriesId;
  final bool compact;

  @override
  Widget build(BuildContext context) => Container(
    constraints: BoxConstraints(minWidth: compact ? 28 : 38),
    padding: EdgeInsets.symmetric(
      horizontal: compact ? 4 : 7,
      vertical: compact ? 2 : 4,
    ),
    decoration: BoxDecoration(
      color: _seriesColor(seriesId),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      _seriesLabel(seriesId),
      textAlign: TextAlign.center,
      style: TextStyle(
        color: Colors.white,
        fontSize: compact ? 8 : 11,
        fontWeight: FontWeight.w900,
      ),
    ),
  );
}

class _CalendarEventMarker extends StatelessWidget {
  const _CalendarEventMarker({
    required this.event,
    required this.showName,
    required this.onTap,
  });
  final RaceEvent event;
  final bool showName;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Tooltip(
    message: event.name,
    child: InkWell(
      borderRadius: BorderRadius.circular(6),
      onTap: onTap,
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
    ),
  );
}

class _ResultsPage extends ConsumerWidget {
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
  Widget build(BuildContext context, WidgetRef ref) {
    final results = ref.watch(eventResultsProvider(selected));
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
            items: data.events
                .where(
                  (event) =>
                      !event.cancelled &&
                      selectedSeries.contains(event.seriesId),
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
            onChanged: (id) =>
                onSelected(data.events.firstWhere((event) => event.id == id)),
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
              final completed = selected.endsAt.isBefore(
                DateTime.now().toUtc(),
              );
              if (!completed) {
                final sessions = [...selected.sessions]
                  ..sort((a, b) => a.startTimeUtc.compareTo(b.startTimeUtc));
                return Card(
                  child: Column(
                    children: [
                      ListTile(
                        leading: const Icon(Icons.schedule),
                        title: Text(
                          strings.plannedSessions,
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
                          subtitle: Text(_zoneName(session, settings, strings)),
                          trailing: Text(
                            '${_sessionDate(session, settings)}\n${_sessionTime(session, settings.timeMode)}',
                            textAlign: TextAlign.end,
                            style: const TextStyle(fontWeight: FontWeight.w800),
                          ),
                        ),
                    ],
                  ),
                );
              }
              final sessions = [...data.sessions]
                ..sort(
                  (a, b) =>
                      _resultOrder(a.type).compareTo(_resultOrder(b.type)),
                );
              return sessions.isEmpty
                  ? _EmptyCard(
                      icon: Icons.hourglass_empty,
                      message: strings.noResults,
                    )
                  : Column(
                      children: [
                        for (
                          var index = 0;
                          index < sessions.length;
                          index++
                        ) ...[
                          _SessionResultsCard(
                            session: sessions[index],
                            strings: strings,
                          ),
                          if (index < sessions.length - 1)
                            const SizedBox(height: 12),
                        ],
                      ],
                    );
            },
          ),
        ],
      ),
    );
  }
}

class _CircuitAsset extends StatelessWidget {
  const _CircuitAsset({
    required this.path,
    required this.fit,
    required this.semanticsLabel,
    this.tint,
  });

  final String path;
  final BoxFit fit;
  final String semanticsLabel;
  final Color? tint;

  @override
  Widget build(BuildContext context) => path.endsWith('.svg')
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
          semanticLabel: semanticsLabel,
          filterQuality: FilterQuality.high,
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
            final graphic = Container(
              width: 190,
              height: 110,
              padding: const EdgeInsets.all(14),
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
                    ),
            );
            if (constraints.maxWidth < 600) {
              return Column(
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Expanded(child: graphic),
                      const SizedBox(width: 16),
                      flag,
                    ],
                  ),
                  const SizedBox(height: 10),
                  Align(alignment: Alignment.centerLeft, child: info),
                ],
              );
            }
            return Row(
              children: [
                graphic,
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
  const _SessionResultsCard({required this.session, required this.strings});
  final SessionResults session;
  final AppStrings strings;

  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      initiallyExpanded: session.type == 'R' || session.type == 'SPRINT',
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
          Padding(
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
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${result.driver.givenName} ${result.driver.familyName}',
                        style: const TextStyle(fontWeight: FontWeight.w800),
                      ),
                      Text(
                        result.teamName,
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
                  label: Text(strings.constructors),
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
            data: (data) => Card(
              child: Column(
                children: showDrivers
                    ? data.drivers
                          .map(
                            (item) => _StandingRow(
                              position: item.position,
                              title: '${item.givenName} ${item.familyName}',
                              subtitle: item.teamIds.map(_teamName).join(' • '),
                              color: _teamColor(
                                item.teamIds.isEmpty
                                    ? null
                                    : item.teamIds.first,
                              ),
                              flag: _nationalityFlag(item.nationality),
                              points: item.points,
                              wins: item.wins,
                              strings: strings,
                            ),
                          )
                          .toList()
                    : data.teams
                          .map(
                            (item) => _StandingRow(
                              position: item.position,
                              title: item.name,
                              subtitle: '',
                              color: _teamColor(item.id),
                              flag: null,
                              points: item.points,
                              wins: item.wins,
                              strings: strings,
                            ),
                          )
                          .toList(),
              ),
            ),
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
    required this.wins,
    required this.strings,
    required this.color,
    required this.flag,
  });
  final int position;
  final String title;
  final String subtitle;
  final double points;
  final int wins;
  final AppStrings strings;
  final Color color;
  final String? flag;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        child: Row(
          children: [
            SizedBox(
              width: 38,
              child: Text(
                '$position',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ),
            Container(
              width: 5,
              height: 38,
              margin: const EdgeInsets.only(right: 12),
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
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
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  '${_number(points)} ${strings.points}',
                  style: const TextStyle(fontWeight: FontWeight.w900),
                ),
                Text(
                  '${strings.wins}: $wins',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ],
        ),
      ),
      const Divider(height: 1),
    ],
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
              ('f1', 'F1', 'assets/brands/f1.svg'),
              ('f2', 'F2', 'assets/brands/f2.svg'),
              ('f3', 'F3', 'assets/brands/f3.svg'),
              ('imsa', 'IMSA', 'assets/brands/imsa.svg'),
              ('indycar', 'INDYCAR', 'assets/brands/indycar.png'),
              ('indynxt', 'INDY NXT', 'assets/brands/indycar.png'),
              ('wec', 'WEC', 'assets/brands/wec.svg'),
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
            subtitle: strings.chooseAny,
            items: const [
              ('iracing', 'iRacing', 'assets/brands/iracing.png'),
              ('lmu', 'Le Mans Ultimate', 'assets/brands/lmu.jpg'),
            ],
            selected: settings.esportCategories,
            onToggle: controller.toggleEsportCategory,
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
        ],
      ),
    );
  }
}

class _CategorySelectionCard extends StatelessWidget {
  const _CategorySelectionCard({
    required this.title,
    required this.subtitle,
    required this.items,
    required this.selected,
    required this.onToggle,
  });
  final String title;
  final String subtitle;
  final List<(String, String, String)> items;
  final Set<String> selected;
  final ValueChanged<String> onToggle;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
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
                      onTap: () => onToggle(item.$1),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 180),
                        height: 116,
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: active
                              ? Theme.of(context).colorScheme.primaryContainer
                              : Theme.of(context).colorScheme.surfaceContainer,
                          border: Border.all(
                            color: active
                                ? Theme.of(context).colorScheme.primary
                                : Theme.of(context).dividerColor,
                            width: active ? 2 : 1,
                          ),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Stack(
                          children: [
                            Align(
                              alignment: Alignment.topRight,
                              child: Icon(
                                active
                                    ? Icons.check_circle
                                    : Icons.circle_outlined,
                                color: active
                                    ? Theme.of(context).colorScheme.primary
                                    : null,
                              ),
                            ),
                            Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Padding(
                                    padding: const EdgeInsets.only(right: 26),
                                    child: item.$3.endsWith('.svg')
                                        ? SvgPicture.asset(
                                            item.$3,
                                            fit: BoxFit.contain,
                                          )
                                        : Image.asset(
                                            item.$3,
                                            fit: BoxFit.contain,
                                          ),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  item.$2,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w900,
                                  ),
                                ),
                              ],
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
  return events.cast<RaceEvent?>().firstWhere(
    (event) => event!.endsAt.isAfter(now) && !event.cancelled,
    orElse: () => events.where((event) => !event.cancelled).last,
  )!;
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
    'R' => 'Wyścig',
    _ => original,
  };
}

int _resultOrder(String type) => switch (type) {
  'R' => 0,
  'SPRINT' => 1,
  'Q' => 2,
  'SQ' => 3,
  'FP3' => 4,
  'FP2' => 5,
  'FP1' => 6,
  _ => 7,
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

String _nationalityFlag(String nationality) => switch (nationality) {
  'Italian' => '🇮🇹',
  'British' => '🇬🇧',
  'Monegasque' => '🇲🇨',
  'Dutch' => '🇳🇱',
  'Australian' => '🇦🇺',
  'French' => '🇫🇷',
  'Spanish' => '🇪🇸',
  'German' => '🇩🇪',
  'Brazilian' => '🇧🇷',
  'Canadian' => '🇨🇦',
  'New Zealander' => '🇳🇿',
  'Mexican' => '🇲🇽',
  'American' => '🇺🇸',
  'Danish' => '🇩🇰',
  'Swedish' => '🇸🇪',
  'Polish' => '🇵🇱',
  'Japanese' => '🇯🇵',
  'Bulgarian' => '🇧🇬',
  'Irish' => '🇮🇪',
  'Indian' => '🇮🇳',
  'Norwegian' => '🇳🇴',
  'Thai' => '🇹🇭',
  'Paraguayan' => '🇵🇾',
  'Colombian' => '🇨🇴',
  'Finnish' => '🇫🇮',
  'Chinese' => '🇨🇳',
  'Sri Lankan' => '🇱🇰',
  'Singaporean' => '🇸🇬',
  'South African' => '🇿🇦',
  _ => '🏁',
};

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
