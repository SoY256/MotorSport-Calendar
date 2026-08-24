import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../domain/app_settings.dart';

class SettingsController extends Notifier<AppSettings> {
  SharedPreferencesAsync? _preferences;

  @override
  AppSettings build() {
    unawaited(_restore());
    return const AppSettings();
  }

  SharedPreferencesAsync? _getPreferences() {
    try {
      return _preferences ??= SharedPreferencesAsync();
    } on StateError {
      // Widget tests do not install a platform preferences implementation.
      return null;
    }
  }

  Future<void> _restore() async {
    final preferences = _getPreferences();
    if (preferences == null) return;
    final language = await preferences.getString('language');
    final timeMode = await preferences.getString('timeMode');
    final showPast = await preferences.getBool('showPastEvents');
    state = AppSettings(
      language: language == 'en' ? AppLanguage.english : AppLanguage.polish,
      timeMode: timeMode == 'track' ? EventTimeMode.track : EventTimeMode.local,
      showPastEvents: showPast ?? true,
    );
  }

  void setLanguage(AppLanguage value) {
    state = state.copyWith(language: value);
    final preferences = _getPreferences();
    if (preferences != null) {
      unawaited(
        preferences.setString(
          'language',
          value == AppLanguage.english ? 'en' : 'pl',
        ),
      );
    }
  }

  void setTimeMode(EventTimeMode value) {
    state = state.copyWith(timeMode: value);
    final preferences = _getPreferences();
    if (preferences != null) {
      unawaited(preferences.setString('timeMode', value.name));
    }
  }

  void setShowPastEvents(bool value) {
    state = state.copyWith(showPastEvents: value);
    final preferences = _getPreferences();
    if (preferences != null) {
      unawaited(preferences.setBool('showPastEvents', value));
    }
  }
}

final settingsProvider = NotifierProvider<SettingsController, AppSettings>(
  SettingsController.new,
);
