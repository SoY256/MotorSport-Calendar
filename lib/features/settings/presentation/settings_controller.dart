import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/series_catalog.dart';
import '../domain/app_settings.dart';

class SettingsController extends Notifier<AppSettings> {
  SharedPreferencesAsync? _preferences;

  @override
  AppSettings build() {
    unawaited(_restore());
    return AppSettings();
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
    final motorsport = await preferences.getStringList('motorsportCategories');
    final categorySchema = await preferences.getInt('categorySchema');
    final esport = await preferences.getStringList('esportCategories');
    // Schema 5 added the GT3 championships: switch them on once for
    // existing users, keeping every other choice they made.
    final motorsportCategories = switch (categorySchema) {
      5 => motorsport?.toSet() ?? defaultMotorsportCategories,
      4 => {...?motorsport, ...gt3SeriesIds},
      _ => defaultMotorsportCategories,
    };
    state = AppSettings(
      language: language == 'pl' ? AppLanguage.polish : AppLanguage.english,
      timeMode: timeMode == 'track' ? EventTimeMode.track : EventTimeMode.local,
      showPastEvents: showPast ?? true,
      motorsportCategories: motorsportCategories,
      esportCategories: esport?.toSet() ?? const <String>{},
    );
    if (categorySchema != 5) {
      unawaited(preferences.setInt('categorySchema', 5));
      unawaited(
        preferences.setStringList(
          'motorsportCategories',
          state.motorsportCategories.toList(),
        ),
      );
    }
  }

  void setMotorsportCategories(Set<String> value) {
    state = state.copyWith(motorsportCategories: {...value});
    final preferences = _getPreferences();
    if (preferences != null) {
      unawaited(
        preferences.setStringList('motorsportCategories', value.toList()),
      );
    }
  }

  void toggleEsportCategory(String id) {
    final next = {...state.esportCategories};
    next.contains(id) ? next.remove(id) : next.add(id);
    state = state.copyWith(esportCategories: next);
    final preferences = _getPreferences();
    if (preferences != null) {
      unawaited(preferences.setStringList('esportCategories', next.toList()));
    }
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
