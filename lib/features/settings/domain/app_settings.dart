import '../../../core/series_catalog.dart';

enum AppLanguage { polish, english }

enum EventTimeMode { local, track }

/// Every championship is shown until the user turns it off in Settings.
final Set<String> defaultMotorsportCategories = {
  for (final series in allSeries) series.id,
};

class AppSettings {
  AppSettings({
    this.language = AppLanguage.english,
    this.timeMode = EventTimeMode.local,
    this.showPastEvents = true,
    Set<String>? motorsportCategories,
    this.esportCategories = const <String>{},
  }) : motorsportCategories =
           motorsportCategories ?? defaultMotorsportCategories;

  final AppLanguage language;
  final EventTimeMode timeMode;
  final bool showPastEvents;
  final Set<String> motorsportCategories;
  final Set<String> esportCategories;

  AppSettings copyWith({
    AppLanguage? language,
    EventTimeMode? timeMode,
    bool? showPastEvents,
    Set<String>? motorsportCategories,
    Set<String>? esportCategories,
  }) => AppSettings(
    language: language ?? this.language,
    timeMode: timeMode ?? this.timeMode,
    showPastEvents: showPastEvents ?? this.showPastEvents,
    motorsportCategories: motorsportCategories ?? this.motorsportCategories,
    esportCategories: esportCategories ?? this.esportCategories,
  );
}
