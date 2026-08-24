import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
        final selected = data.events.firstWhere(
          (event) => event.id == _selectedEventId,
          orElse: () => _nearestEvent(data.events),
        );
        return switch (_page) {
          0 => _ListPage(
            data: data,
            settings: settings,
            strings: strings,
            onEventTap: (event) => setState(() {
              _selectedEventId = event.id;
              _page = 2;
            }),
          ),
          1 => _CalendarGridPage(
            data: data,
            settings: settings,
            strings: strings,
            onEventTap: (event) => setState(() {
              _selectedEventId = event.id;
              _page = 2;
            }),
          ),
          2 => _ResultsPage(
            data: data,
            selected: selected,
            settings: settings,
            strings: strings,
            onSelected: (event) => setState(() => _selectedEventId = event.id),
          ),
          3 => _StandingsPage(strings: strings),
          _ => _SettingsPage(settings: settings, strings: strings),
        };
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
  });
  final CalendarData data;
  final AppSettings settings;
  final AppStrings strings;
  final ValueChanged<RaceEvent> onEventTap;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final now = DateTime.now().toUtc();
    final events = settings.showPastEvents
        ? data.events
        : data.events.where((event) => event.endsAt.isAfter(now)).toList();
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
          _NextRaceHero(
            event: _nearestEvent(data.events),
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
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        gradient: const LinearGradient(
          colors: [Color(0xFFE10600), Color(0xFF8A0501)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFFE10600).withValues(alpha: .24),
            blurRadius: 28,
            offset: const Offset(0, 12),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            strings.nextRound,
            style: const TextStyle(
              color: Colors.white70,
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
              Container(
                width: 52,
                height: 58,
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      'R${event.round ?? '–'}',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.primary,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    Text(
                      _sessionMonth(race, settings),
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
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
                      '${event.circuit.countryCode ?? ''}  ${event.circuit.name}',
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
  });
  final CalendarData data;
  final AppSettings settings;
  final AppStrings strings;
  final ValueChanged<RaceEvent> onEventTap;

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
            !event.cancelled &&
            event.sessions.any((session) {
              final date = _dateFor(session);
              return date.year == day.year &&
                  date.month == day.month &&
                  date.day == day.day;
            }),
      )
      .toList();

  void _openDay(DateTime day) {
    final events = _eventsOn(day);
    if (events.isEmpty) return;
    if (events.length == 1) {
      widget.onEventTap(events.first);
      return;
    }
    showModalBottomSheet<void>(
      context: context,
      builder: (context) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: events
              .map(
                (event) => ListTile(
                  leading: const Icon(Icons.sports_score),
                  title: Text(event.name),
                  subtitle: Text(event.circuit.name),
                  onTap: () {
                    Navigator.pop(context);
                    widget.onEventTap(event);
                  },
                ),
              )
              .toList(),
        ),
      ),
    );
  }

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
          SegmentedButton<bool>(
            segments: [
              ButtonSegment(value: true, label: Text(widget.strings.month)),
              ButtonSegment(value: false, label: Text(widget.strings.week)),
            ],
            selected: {_month},
            onSelectionChanged: (value) => setState(() => _month = value.first),
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
                        onTap: events.isEmpty ? null : () => _openDay(day),
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
                                if (events.isNotEmpty) ...[
                                  const Spacer(),
                                  Icon(
                                    Icons.sports_score,
                                    size: 18,
                                    color: Theme.of(context)
                                        .colorScheme
                                        .primary,
                                  ),
                                  if (!_month)
                                    Text(
                                      events.first.name,
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      textAlign: TextAlign.center,
                                      style: Theme.of(context)
                                          .textTheme
                                          .labelSmall,
                                    ),
                                  const Spacer(),
                                ],
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
}

class _ResultsPage extends ConsumerWidget {
  const _ResultsPage({
    required this.data,
    required this.selected,
    required this.settings,
    required this.strings,
    required this.onSelected,
  });
  final CalendarData data;
  final RaceEvent selected;
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
                .where((event) => !event.cancelled)
                .map(
                  (event) => DropdownMenuItem(
                    value: event.id,
                    child: Text(
                      'R${event.round} • ${event.name}',
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

class _CircuitInfoCard extends StatelessWidget {
  const _CircuitInfoCard({required this.event, required this.strings});
  final RaceEvent event;
  final AppStrings strings;

  @override
  Widget build(BuildContext context) {
    final metadata = metadataForCircuit(event.circuit.name);
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
            final graphic = SizedBox(
              width: 190,
              height: 110,
              child: CustomPaint(
                painter: _CircuitPainter(
                  event.circuit.name,
                  Theme.of(context).colorScheme.primary,
                ),
              ),
            );
            if (constraints.maxWidth < 600) {
              return Column(
                children: [
                  graphic,
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
              ],
            );
          },
        ),
      ),
    );
  }
}

class _CircuitPainter extends CustomPainter {
  _CircuitPainter(this.seed, this.color);
  final String seed;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final hash = seed.codeUnits.fold<int>(0, (value, item) => value + item);
    final points = <Offset>[];
    for (var i = 0; i < 12; i++) {
      final angle = i * 3.14159 * 2 / 12;
      final wobble = .62 + ((hash >> (i % 8)) & 3) * .09;
      points.add(
        Offset(
          size.width / 2 + size.width * .42 * wobble * math.cos(angle),
          size.height / 2 + size.height * .42 * wobble * math.sin(angle),
        ),
      );
    }
    final path = Path()..moveTo(points.first.dx, points.first.dy);
    for (final point in points.skip(1)) {
      path.lineTo(point.dx, point.dy);
    }
    path.close();
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 8
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = Colors.white.withValues(alpha: .8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2,
    );
  }

  @override
  bool shouldRepaint(covariant _CircuitPainter oldDelegate) =>
      oldDelegate.seed != seed || oldDelegate.color != color;
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
  const _StandingsPage({required this.strings});
  final AppStrings strings;
  @override
  ConsumerState<_StandingsPage> createState() => _StandingsPageState();
}

class _StandingsPageState extends ConsumerState<_StandingsPage> {
  bool _drivers = true;

  @override
  Widget build(BuildContext context) {
    final standings = ref.watch(standingsProvider);
    final strings = widget.strings;
    return _PageFrame(
      title: strings.standings,
      subtitle: 'F1 • 2026',
      child: Column(
        children: [
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
          const SizedBox(height: 16),
          standings.when(
            loading: () => const Padding(
              padding: EdgeInsets.all(32),
              child: CircularProgressIndicator(),
            ),
            error: (error, _) => _ErrorState(
              message: error.toString(),
              strings: strings,
              onRetry: () => ref.invalidate(standingsProvider),
            ),
            data: (data) => Card(
              child: Column(
                children: _drivers
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
  'mercedes' => 'Mercedes-AMG Petronas',
  'ferrari' => 'Scuderia Ferrari HP',
  'mclaren' => 'McLaren Formula 1 Team',
  'williams' => 'Atlassian Williams F1 Team',
  'audi' => 'Audi Revolut F1 Team',
  _ => id.replaceAll('_', ' '),
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

String _sessionMonth(RaceSession session, AppSettings settings) {
  final track = settings.timeMode == EventTimeMode.track
      ? _trackParts(session)
      : null;
  return _monthName(
    track?[0] ?? session.startTimeUtc.toLocal().month,
    settings.language,
  );
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
