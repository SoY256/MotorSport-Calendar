enum AppLanguage { polish, english }

enum EventTimeMode { local, track }

class AppSettings {
  const AppSettings({
    this.language = AppLanguage.polish,
    this.timeMode = EventTimeMode.local,
    this.showPastEvents = true,
  });

  final AppLanguage language;
  final EventTimeMode timeMode;
  final bool showPastEvents;

  AppSettings copyWith({
    AppLanguage? language,
    EventTimeMode? timeMode,
    bool? showPastEvents,
  }) => AppSettings(
    language: language ?? this.language,
    timeMode: timeMode ?? this.timeMode,
    showPastEvents: showPastEvents ?? this.showPastEvents,
  );
}
