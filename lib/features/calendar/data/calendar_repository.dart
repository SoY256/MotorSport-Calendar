import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../domain/race_event.dart';

abstract interface class CalendarRepository {
  Future<CalendarData> load();
}

class AssetCalendarRepository implements CalendarRepository {
  AssetCalendarRepository({AssetBundle? bundle})
    : _bundle = bundle ?? rootBundle;

  final AssetBundle _bundle;

  @override
  Future<CalendarData> load() async {
    final raw = await _bundle.loadString('assets/data/calendar.json');
    return CalendarData.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }
}

class NetworkFirstCalendarRepository implements CalendarRepository {
  NetworkFirstCalendarRepository({required this.fallback, http.Client? client})
    : _client = client ?? http.Client();

  static final endpoint = Uri.parse(
    'https://raw.githubusercontent.com/SoY256/MotorSport-Calendar/main/data/f1/2026/calendar.json',
  );

  final CalendarRepository fallback;
  final http.Client _client;

  @override
  Future<CalendarData> load() async {
    try {
      final response = await _client
          .get(endpoint)
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        return CalendarData.fromJson(
          jsonDecode(response.body) as Map<String, dynamic>,
        );
      }
    } on Object {
      // The bundled snapshot keeps the app useful offline and during API outages.
    }
    return fallback.load();
  }
}
