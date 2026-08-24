class RaceSession {
  const RaceSession({
    required this.type,
    required this.name,
    required this.startTimeUtc,
    required this.cancelled,
    this.startTimeTrack,
    this.trackTimeZone,
  });

  factory RaceSession.fromJson(Map<String, dynamic> json) => RaceSession(
    type: json['type'] as String,
    name: json['name'] as String,
    startTimeUtc: DateTime.parse(json['startTimeUtc'] as String).toUtc(),
    cancelled: json['cancelled'] as bool? ?? false,
    startTimeTrack: json['startTimeTrack'] as String?,
    trackTimeZone: json['trackTimeZone'] as String?,
  );

  final String type;
  final String name;
  final DateTime startTimeUtc;
  final bool cancelled;
  final String? startTimeTrack;
  final String? trackTimeZone;
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
    required this.resultsPath,
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
    resultsPath: json['resultsPath'] as String,
  );

  final String id;
  final String seriesId;
  final int season;
  final int? round;
  final String name;
  final bool cancelled;
  final Circuit circuit;
  final List<RaceSession> sessions;
  final String resultsPath;

  DateTime get startsAt => sessions
      .map((item) => item.startTimeUtc)
      .reduce((first, second) => first.isBefore(second) ? first : second);
  DateTime get endsAt => sessions
      .map((item) => item.startTimeUtc)
      .reduce((first, second) => first.isAfter(second) ? first : second);
}

class DriverIdentity {
  const DriverIdentity({
    required this.id,
    required this.code,
    required this.givenName,
    required this.familyName,
    this.nationality,
  });

  factory DriverIdentity.fromJson(Map<String, dynamic> json) => DriverIdentity(
    id: json['id'] as String,
    code: json['code'] as String? ?? '',
    givenName: json['givenName'] as String? ?? '',
    familyName: json['familyName'] as String? ?? '',
    nationality:
        json['nationality'] as String? ?? json['countryCode'] as String?,
  );

  final String id;
  final String code;
  final String givenName;
  final String familyName;
  final String? nationality;
}

class SessionResult {
  const SessionResult({
    required this.position,
    required this.positionText,
    required this.driver,
    required this.teamName,
    required this.teamColor,
    required this.time,
    required this.points,
    required this.status,
    required this.category,
  });

  factory SessionResult.fromJson(Map<String, dynamic> json) {
    final team = json['team'] as Map<String, dynamic>;
    return SessionResult(
      position: json['position'] as int?,
      positionText: json['positionText'] as String? ?? '–',
      driver: DriverIdentity.fromJson(json['driver'] as Map<String, dynamic>),
      teamName: team['name'] as String? ?? '',
      teamColor: team['color'] as String?,
      time: json['time'] as String?,
      points: (json['points'] as num?)?.toDouble(),
      status: json['status'] as String?,
      category:
          (json['components'] as Map<String, dynamic>?)?['category'] as String?,
    );
  }

  final int? position;
  final String positionText;
  final DriverIdentity driver;
  final String teamName;
  final String? teamColor;
  final String? time;
  final double? points;
  final String? status;
  final String? category;
}

class SessionResults {
  const SessionResults({
    required this.type,
    required this.name,
    required this.startTimeUtc,
    required this.results,
  });

  factory SessionResults.fromJson(Map<String, dynamic> json) => SessionResults(
    type: json['type'] as String,
    name: json['name'] as String,
    startTimeUtc: DateTime.parse(json['startTimeUtc'] as String).toUtc(),
    results: (json['results'] as List<dynamic>)
        .map((item) => SessionResult.fromJson(item as Map<String, dynamic>))
        .toList(growable: false),
  );

  final String type;
  final String name;
  final DateTime startTimeUtc;
  final List<SessionResult> results;
}

class EventResults {
  const EventResults({required this.eventId, required this.sessions});

  factory EventResults.fromJson(Map<String, dynamic> json) {
    final data = json['data'] as Map<String, dynamic>;
    return EventResults(
      eventId: data['eventId'] as String,
      sessions: (data['sessions'] as List<dynamic>)
          .map((item) => SessionResults.fromJson(item as Map<String, dynamic>))
          .toList(growable: false),
    );
  }

  final String eventId;
  final List<SessionResults> sessions;
}

class DriverStanding {
  const DriverStanding({
    required this.position,
    required this.points,
    required this.wins,
    required this.id,
    required this.code,
    required this.givenName,
    required this.familyName,
    required this.nationality,
    required this.teamIds,
    required this.teamNames,
    required this.category,
  });

  factory DriverStanding.fromJson(Map<String, dynamic> json) => DriverStanding(
    position: json['position'] as int,
    points: (json['points'] as num).toDouble(),
    wins: json['wins'] as int,
    id: json['id'] as String,
    code: json['code'] as String? ?? '',
    givenName: json['givenName'] as String,
    familyName: json['familyName'] as String,
    nationality: json['nationality'] as String? ?? '',
    teamIds: (json['teamIds'] as List<dynamic>).cast<String>(),
    teamNames: (json['teamNames'] as List<dynamic>? ?? const []).cast<String>(),
    category: json['category'] as String?,
  );

  final int position;
  final double points;
  final int wins;
  final String id;
  final String code;
  final String givenName;
  final String familyName;
  final String nationality;
  final List<String> teamIds;
  final List<String> teamNames;
  final String? category;
}

class TeamStanding {
  const TeamStanding({
    required this.position,
    required this.points,
    required this.wins,
    required this.id,
    required this.name,
    required this.category,
  });

  factory TeamStanding.fromJson(Map<String, dynamic> json) => TeamStanding(
    position: json['position'] as int,
    points: (json['points'] as num).toDouble(),
    wins: json['wins'] as int,
    id: json['id'] as String,
    name: json['name'] as String,
    category: json['category'] as String?,
  );

  final int position;
  final double points;
  final int wins;
  final String id;
  final String name;
  final String? category;
}

class StandingsData {
  const StandingsData({required this.drivers, required this.teams});
  final List<DriverStanding> drivers;
  final List<TeamStanding> teams;
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
