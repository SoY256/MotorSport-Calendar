class RaceSession {
  const RaceSession({
    required this.type,
    required this.name,
    required this.startTimeUtc,
    required this.cancelled,
  });

  factory RaceSession.fromJson(Map<String, dynamic> json) => RaceSession(
    type: json['type'] as String,
    name: json['name'] as String,
    startTimeUtc: DateTime.parse(json['startTimeUtc'] as String).toUtc(),
    cancelled: json['cancelled'] as bool? ?? false,
  );

  final String type;
  final String name;
  final DateTime startTimeUtc;
  final bool cancelled;
}

class Circuit {
  const Circuit({
    required this.name,
    this.locality,
    this.country,
    this.countryCode,
  });

  factory Circuit.fromJson(Map<String, dynamic> json) => Circuit(
    name: json['name'] as String,
    locality: json['locality'] as String?,
    country: json['country'] as String?,
    countryCode: json['countryCode'] as String?,
  );

  final String name;
  final String? locality;
  final String? country;
  final String? countryCode;
}

class RaceEvent {
  const RaceEvent({
    required this.id,
    required this.seriesId,
    required this.season,
    required this.round,
    required this.name,
    required this.cancelled,
    required this.circuit,
    required this.sessions,
  });

  factory RaceEvent.fromJson(Map<String, dynamic> json) => RaceEvent(
    id: json['id'] as String,
    seriesId: json['seriesId'] as String,
    season: json['season'] as int,
    round: json['round'] as int?,
    name: json['name'] as String,
    cancelled: json['cancelled'] as bool? ?? false,
    circuit: Circuit.fromJson(json['circuit'] as Map<String, dynamic>),
    sessions: (json['sessions'] as List<dynamic>)
        .map((item) => RaceSession.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
  );

  final String id;
  final String seriesId;
  final int season;
  final int? round;
  final String name;
  final bool cancelled;
  final Circuit circuit;
  final List<RaceSession> sessions;

  DateTime get startsAt => sessions
      .map((item) => item.startTimeUtc)
      .reduce((first, second) => first.isBefore(second) ? first : second);
  DateTime get endsAt => sessions
      .map((item) => item.startTimeUtc)
      .reduce((first, second) => first.isAfter(second) ? first : second);
}

class CalendarData {
  const CalendarData({
    required this.schemaVersion,
    required this.updatedAt,
    required this.events,
  });

  factory CalendarData.fromJson(Map<String, dynamic> json) => CalendarData(
    schemaVersion: json['schemaVersion'] as int,
    updatedAt: DateTime.parse(json['lastSuccessfulUpdate'] as String).toUtc(),
    events: (json['data'] as List<dynamic>)
        .map((item) => RaceEvent.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
  );

  final int schemaVersion;
  final DateTime updatedAt;
  final List<RaceEvent> events;
}
