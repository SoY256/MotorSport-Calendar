import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/calendar/presentation/calendar_screen.dart';
import '../features/settings/domain/app_settings.dart';
import '../features/settings/presentation/theme_controller.dart';
import '../features/settings/presentation/settings_controller.dart';
import 'theme.dart';

class MotorsportCalendarApp extends ConsumerWidget {
  const MotorsportCalendarApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeModeProvider);
    final settings = ref.watch(settingsProvider);
    return MaterialApp(
      title: 'MotorSport Calendar',
      debugShowCheckedModeBanner: false,
      theme: MotorsportTheme.light,
      darkTheme: MotorsportTheme.dark,
      themeMode: themeMode,
      locale: Locale(settings.language == AppLanguage.english ? 'en' : 'pl'),
      home: const CalendarScreen(),
    );
  }
}
