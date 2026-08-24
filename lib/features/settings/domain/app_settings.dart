enum AppLanguage { polish, english }

enum EventTimeMode { local, track }

class AppSettings {
  const AppSettings({
    this.language = AppLanguage.polish,
    this.timeMode = EventTimeMode.local,
    this.showPastEvents = true,
    this.motorsportCategories = const {'f1', 'wec', 'imsa'},
    this.esportCategories = const <String>{},
  });

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
