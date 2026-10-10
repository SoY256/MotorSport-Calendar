import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../calendar/domain/race_event.dart';

class NotificationPreferences {
  static const channel = MethodChannel('secar/notifications');
  static List<RaceEvent> events = [];
  static DateTime reminderTime(DateTime start, int minutes) =>
      start.subtract(Duration(minutes: minutes));
  static Future<void> sync(List<RaceEvent> value) async {
    events = value;
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) return;
    final prefs = SharedPreferencesAsync();
    final enabled = await prefs.getBool('notificationsEnabled') ?? false;
    final series = await prefs.getStringList('notificationSeries') ?? ['f1'];
    final types = await prefs.getStringList('notificationTypes') ?? ['race'];
    final pl = await prefs.getString('language') == 'pl';
    final leadMinutes = await prefs.getInt('notificationLeadMinutes') ?? 0;
    final now = DateTime.now();
    final entries = <Map<String, Object>>[];
    if (enabled) {
      for (final event in value) {
        if (event.cancelled || !series.contains(event.seriesId)) continue;
        for (final session in event.sessions) {
          final type = kind(session.type);
          final scheduled = reminderTime(session.startTimeUtc, leadMinutes);
          if (session.cancelled ||
              !types.contains(type) ||
              !scheduled.isAfter(now)) {
            continue;
          }
          entries.add({
            'id':
                '${event.id}/${session.type}/${session.startTimeUtc.toIso8601String()}',
            'time': scheduled.millisecondsSinceEpoch,
            'title': '${event.seriesId.toUpperCase()} • ${event.name}',
            'body': leadMinutes == 0
                ? '${session.name} ${pl ? 'rozpoczyna się teraz' : 'starts now'}'
                : '${session.name} • ${pl ? 'Start za' : 'Starts in'} ${leadLabel(leadMinutes, pl)}',
          });
        }
      }
    }
    try {
      await channel.invokeMethod('schedule', jsonEncode(entries));
    } on MissingPluginException {
      /* Tests and unsupported hosts. */
    }
  }

  static String leadLabel(int minutes, bool polish) {
    if (minutes == 0) return polish ? 'W chwili startu' : 'At session start';
    if (minutes % 1440 == 0) {
      final days = minutes ~/ 1440;
      return polish ? '$days d' : '$days ${days == 1 ? 'day' : 'days'}';
    }
    if (minutes % 60 == 0) return '${minutes ~/ 60} ${polish ? 'godz.' : 'h'}';
    return '$minutes min';
  }

  static String kind(String type) => type.toUpperCase().contains('Q')
      ? 'qualifying'
      : (type == 'R' ||
            type.toUpperCase().contains('RACE') ||
            type.toUpperCase().contains('SPRINT'))
      ? 'race'
      : 'practice';
}

class NotificationSettings extends StatefulWidget {
  const NotificationSettings({super.key, required this.polish});
  final bool polish;
  @override
  State<NotificationSettings> createState() => _NotificationSettingsState();
}

class _NotificationSettingsState extends State<NotificationSettings> {
  SharedPreferencesAsync? _prefs;
  SharedPreferencesAsync get prefs => _prefs ??= SharedPreferencesAsync();
  bool enabled = false;
  int leadMinutes = 0;
  static const presets = [0, 5, 15, 30, 60, 120, 360, 720, 1440, 2880, 10080];
  Set<String> series = {'f1'}, types = {'race'};
  bool loaded = false;
  @override
  void initState() {
    super.initState();
    restore();
  }

  Future<void> restore() async {
    try {
      _prefs = SharedPreferencesAsync();
    } on StateError {
      return;
    }
    final e = await prefs.getBool('notificationsEnabled') ?? false;
    final s = await prefs.getStringList('notificationSeries') ?? ['f1'];
    final t = await prefs.getStringList('notificationTypes') ?? ['race'];
    final lead = await prefs.getInt('notificationLeadMinutes') ?? 0;
    if (mounted) {
      setState(() {
        enabled = e;
        series = s.toSet();
        types = t.toSet();
        leadMinutes = lead;
        loaded = true;
      });
    }
  }

  Future<void> save() async {
    await prefs.setBool('notificationsEnabled', enabled);
    await prefs.setStringList('notificationSeries', series.toList());
    await prefs.setStringList('notificationTypes', types.toList());
    await prefs.setInt('notificationLeadMinutes', leadMinutes);
    await NotificationPreferences.sync(NotificationPreferences.events);
  }

  Future<void> customLead() async {
    final pl = widget.polish;
    final input = TextEditingController();
    var multiplier = 1;
    String? error;
    final minutes = await showDialog<int>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, update) => AlertDialog(
          title: Text(pl ? 'Własne wyprzedzenie' : 'Custom reminder time'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: input,
                autofocus: true,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                decoration: InputDecoration(
                  labelText: pl ? 'Ile wcześniej?' : 'How far in advance?',
                  errorText: error,
                ),
              ),
              const SizedBox(height: 16),
              DropdownButtonFormField<int>(
                initialValue: multiplier,
                decoration: InputDecoration(
                  labelText: pl ? 'Jednostka' : 'Unit',
                ),
                items: [
                  DropdownMenuItem(
                    value: 1,
                    child: Text(pl ? 'Minuty' : 'Minutes'),
                  ),
                  DropdownMenuItem(
                    value: 60,
                    child: Text(pl ? 'Godziny' : 'Hours'),
                  ),
                  DropdownMenuItem(
                    value: 1440,
                    child: Text(pl ? 'Dni' : 'Days'),
                  ),
                ],
                onChanged: (value) => update(() => multiplier = value ?? 1),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: Text(pl ? 'Anuluj' : 'Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final value = int.tryParse(input.text);
                if (value == null || value < 1 || value * multiplier > 525600) {
                  update(
                    () => error = pl
                        ? 'Wpisz czas od 1 minuty do 365 dni.'
                        : 'Enter a time from 1 minute to 365 days.',
                  );
                  return;
                }
                Navigator.pop(dialogContext, value * multiplier);
              },
              child: Text(pl ? 'Zapisz' : 'Save'),
            ),
          ],
        ),
      ),
    );
    // The route animation can still reference its text controller.
    await Future<void>.delayed(const Duration(milliseconds: 300));
    input.dispose();
    if (!mounted || minutes == null) return;
    setState(() => leadMinutes = minutes);
    await save();
  }

  Future<void> toggle(bool value) async {
    if (value && !kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      final allowed =
          await NotificationPreferences.channel.invokeMethod<bool>(
            'permission',
          ) ??
          false;
      if (!mounted) return;
      if (!allowed) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              widget.polish
                  ? 'Zezwól na powiadomienia Secar w ustawieniach Androida.'
                  : 'Allow Secar notifications in Android settings.',
            ),
          ),
        );
        return;
      }
    }
    setState(() => enabled = value);
    await save();
  }

  @override
  Widget build(BuildContext context) {
    final pl = widget.polish;
    final supported =
        !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              secondary: const Icon(Icons.notifications_active_outlined),
              title: Text(
                pl ? 'Powiadomienia o sesjach' : 'Session notifications',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              subtitle: Text(
                supported
                    ? (pl
                          ? 'Przypomnienia o rozpoczęciu sesji, także gdy aplikacja jest zamknięta. Oszczędzanie baterii może opóźnić powiadomienia.'
                          : 'Session start reminders, even with the app closed. Battery saving may delay notifications.')
                    : (pl
                          ? 'Dostępne w aplikacji na Androida.'
                          : 'Available in the Android app.'),
              ),
              value: enabled,
              onChanged: loaded && supported ? toggle : null,
            ),
            if (enabled) ...[
              const SizedBox(height: 12),
              Text(
                pl ? 'Kiedy przypomnieć?' : 'When should we remind you?',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              DropdownButtonFormField<int>(
                key: ValueKey(leadMinutes),
                initialValue: leadMinutes,
                isExpanded: true,
                decoration: InputDecoration(
                  prefixIcon: const Icon(Icons.timer_outlined),
                  labelText: pl ? 'Wyprzedzenie' : 'Reminder time',
                ),
                items: [
                  for (final minutes in {
                    ...presets,
                    leadMinutes,
                  }.toList()..sort())
                    DropdownMenuItem(
                      value: minutes,
                      child: Text(
                        '${NotificationPreferences.leadLabel(minutes, pl)}${minutes == 0 ? '' : (pl ? ' przed sesją' : ' before the session')}',
                      ),
                    ),
                ],
                onChanged: (value) {
                  if (value == null) return;
                  setState(() => leadMinutes = value);
                  save();
                },
              ),
              TextButton.icon(
                onPressed: customLead,
                icon: const Icon(Icons.edit_outlined),
                label: Text(pl ? 'Ustaw własny czas' : 'Set a custom time'),
              ),
              Text(
                pl
                    ? 'Dotyczy wszystkich wybranych sesji. Jeśli wybrany termin przypomnienia już minął, nie wysyłamy zaległego powiadomienia.'
                    : 'Applies to all selected sessions. Reminders whose scheduled time has already passed are skipped.',
                style: Theme.of(context).textTheme.bodySmall,
              ),
              const SizedBox(height: 16),
              Text(pl ? 'Wybierz serie' : 'Choose series'),
              TextButton.icon(
                icon: const Icon(Icons.done_all),
                label: Text(pl ? 'Wszystkie serie' : 'All series'),
                onPressed: () {
                  setState(
                    () => series = {
                      'f1',
                      'f2',
                      'f3',
                      'imsa',
                      'indycar',
                      'indynxt',
                      'wec',
                    },
                  );
                  save();
                },
              ),
              Wrap(
                spacing: 8,
                children: [
                  for (final id in [
                    'f1',
                    'f2',
                    'f3',
                    'imsa',
                    'indycar',
                    'indynxt',
                    'wec',
                  ])
                    FilterChip(
                      label: Text(
                        id == 'indynxt' ? 'INDY NXT' : id.toUpperCase(),
                      ),
                      selected: series.contains(id),
                      onSelected: (selected) {
                        setState(() {
                          selected ? series.add(id) : series.remove(id);
                        });
                        save();
                      },
                    ),
                ],
              ),
              const SizedBox(height: 12),
              Text(pl ? 'Rodzaje sesji' : 'Session types'),
              Wrap(
                spacing: 8,
                children: [
                  for (final item in [
                    ('practice', pl ? 'Treningi' : 'Practice'),
                    ('qualifying', pl ? 'Kwalifikacje' : 'Qualifying'),
                    ('race', pl ? 'Wyścigi i sprinty' : 'Races and sprints'),
                  ])
                    FilterChip(
                      label: Text(item.$2),
                      selected: types.contains(item.$1),
                      onSelected: (selected) {
                        setState(() {
                          selected ? types.add(item.$1) : types.remove(item.$1);
                        });
                        save();
                      },
                    ),
                ],
              ),
              if (series.isEmpty || types.isEmpty)
                Text(
                  pl
                      ? 'Wybierz przynajmniej jedną serię i rodzaj sesji.'
                      : 'Choose at least one series and session type.',
                ),
            ],
          ],
        ),
      ),
    );
  }
}
