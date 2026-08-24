import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/widgets/app_logo.dart';
import '../../settings/presentation/theme_controller.dart';
import '../domain/race_event.dart';
import 'calendar_providers.dart';

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});
  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  int _page = 0;

  @override
  Widget build(BuildContext context) {
    final calendar = ref.watch(calendarProvider);
    final wide = MediaQuery.sizeOf(context).width >= 850;
    final content = calendar.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (error, _) => _ErrorState(
        message: error.toString(),
        onRetry: () => ref.invalidate(calendarProvider),
      ),
      data: (data) => switch (_page) {
        0 => _CalendarPage(data: data),
        1 => _WeekendPage(data: data),
        2 => _StandingsPage(data: data),
        _ => const _SettingsPage(),
      },
    );
    final destinations = const [
      NavigationDestination(
        icon: Icon(Icons.calendar_month_outlined),
        selectedIcon: Icon(Icons.calendar_month),
        label: 'Kalendarz',
      ),
      NavigationDestination(
        icon: Icon(Icons.flag_outlined),
        selectedIcon: Icon(Icons.flag),
        label: 'Weekend',
      ),
      NavigationDestination(
        icon: Icon(Icons.emoji_events_outlined),
        selectedIcon: Icon(Icons.emoji_events),
        label: 'Klasyfikacja',
      ),
      NavigationDestination(
        icon: Icon(Icons.tune_outlined),
        selectedIcon: Icon(Icons.tune),
        label: 'Ustawienia',
      ),
    ];
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
            .withValues(alpha: .92),
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

class _CalendarPage extends ConsumerWidget {
  const _CalendarPage({required this.data});
  final CalendarData data;

  @override
  Widget build(BuildContext context, WidgetRef ref) => _PageFrame(
    title: 'Sezon ${data.events.first.season}',
    subtitle: '${data.events.length} rund • godziny w Twojej strefie czasowej',
    actions: [
      IconButton(
        tooltip: 'Odśwież dane',
        onPressed: () => ref.invalidate(calendarProvider),
        icon: const Icon(Icons.refresh_rounded),
      ),
      const SizedBox(width: 8),
    ],
    child: Column(
      children: [
        _NextRaceHero(event: _nearestEvent(data.events)),
        const SizedBox(height: 18),
        for (final event in data.events) ...[
          _EventCard(event: event),
          const SizedBox(height: 12),
        ],
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text(
            'Dane zaktualizowano ${_dateTime(data.updatedAt.toLocal())}',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      ],
    ),
  );
}

class _NextRaceHero extends StatelessWidget {
  const _NextRaceHero({required this.event});
  final RaceEvent event;

  @override
  Widget build(BuildContext context) => Container(
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
        const Text(
          'NAJBLIŻSZA RUNDA',
          style: TextStyle(
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
                  '${_date(event.startsAt.toLocal())} – ${_date(event.endsAt.toLocal())}',
            ),
            _HeroPill(
              icon: Icons.schedule,
              label: '${event.sessions.length} sesji',
            ),
          ],
        ),
      ],
    ),
  );
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
  const _EventCard({required this.event});
  final RaceEvent event;

  @override
  Widget build(BuildContext context) {
    final race = event.sessions.last;
    return Card(
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
                    _month(race.startTimeUtc.toLocal()),
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
                  Text(
                    event.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                    ),
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
                  _date(race.startTimeUtc.toLocal()),
                  style: const TextStyle(fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 4),
                Text(
                  _time(race.startTimeUtc.toLocal()),
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.primary,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _WeekendPage extends StatelessWidget {
  const _WeekendPage({required this.data});
  final CalendarData data;

  @override
  Widget build(BuildContext context) {
    final event = _nearestEvent(data.events);
    return _PageFrame(
      title: event.name,
      subtitle:
          '${event.circuit.name}, ${event.circuit.locality ?? event.circuit.country ?? ''}',
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            children: [
              for (var index = 0; index < event.sessions.length; index++)
                _SessionRow(
                  session: event.sessions[index],
                  last: index == event.sessions.length - 1,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _SessionRow extends StatelessWidget {
  const _SessionRow({required this.session, required this.last});
  final RaceSession session;
  final bool last;

  @override
  Widget build(BuildContext context) => IntrinsicHeight(
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Column(
          children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                shape: BoxShape.circle,
              ),
            ),
            if (!last)
              Expanded(
                child: Container(
                  width: 2,
                  color: Theme.of(context).colorScheme.outlineVariant,
                ),
              ),
          ],
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Padding(
            padding: EdgeInsets.only(bottom: last ? 0 : 24),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    session.name,
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                ),
                Text(
                  '${_date(session.startTimeUtc.toLocal())}  ${_time(session.startTimeUtc.toLocal())}',
                ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

class _StandingsPage extends StatelessWidget {
  const _StandingsPage({required this.data});
  final CalendarData data;
  @override
  Widget build(BuildContext context) => _PageFrame(
    title: 'Klasyfikacja',
    subtitle: 'Kierowcy i konstruktorzy • sezon ${data.events.first.season}',
    child: const _InformationCard(
      icon: Icons.emoji_events_rounded,
      title: 'Klasyfikacja jest gotowa po stronie danych',
      message: 'Widok tabel zostanie zasilony plikami standings po pierwszym udanym przebiegu GitHub Actions.',
    ),
  );
}

class _SettingsPage extends ConsumerWidget {
  const _SettingsPage();
  @override
  Widget build(BuildContext context, WidgetRef ref) => _PageFrame(
    title: 'Ustawienia',
    subtitle: 'Dopasuj aplikację do siebie',
    child: Card(
      child: SwitchListTile(
        secondary: const Icon(Icons.dark_mode_outlined),
        title: const Text(
          'Tryb ciemny',
          style: TextStyle(fontWeight: FontWeight.w800),
        ),
        subtitle: const Text('Ten sam design system, inne kolory'),
        value: Theme.of(context).brightness == Brightness.dark,
        onChanged: (_) => ref
            .read(themeModeProvider.notifier)
            .toggle(Theme.of(context).brightness),
      ),
    ),
  );
}

class _InformationCard extends StatelessWidget {
  const _InformationCard({
    required this.icon,
    required this.title,
    required this.message,
  });
  final IconData icon;
  final String title;
  final String message;
  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(28),
      child: Column(
        children: [
          Icon(icon, size: 48, color: Theme.of(context).colorScheme.primary),
          const SizedBox(height: 16),
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleLarge
                ?.copyWith(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    ),
  );
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});
  final String message;
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
          const Text(
            'Nie udało się wczytać kalendarza',
            style: TextStyle(fontWeight: FontWeight.w900),
          ),
          const SizedBox(height: 6),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 18),
          FilledButton.icon(
            onPressed: onRetry,
            icon: const Icon(Icons.refresh),
            label: const Text('Spróbuj ponownie'),
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
    orElse: () => events.last,
  )!;
}

const _months = [
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
String _two(int value) => value.toString().padLeft(2, '0');
String _month(DateTime value) => _months[value.month - 1];
String _date(DateTime value) => '${_two(value.day)} ${_month(value)}';
String _time(DateTime value) => '${_two(value.hour)}:${_two(value.minute)}';
String _dateTime(DateTime value) =>
    '${_date(value)} ${value.year}, ${_time(value)}';
