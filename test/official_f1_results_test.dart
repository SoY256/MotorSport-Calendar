import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:secar/features/calendar/data/calendar_repository.dart';
import 'package:secar/features/calendar/domain/race_event.dart';

class EmptyResults extends AssetCalendarRepository {
  @override
  Future<EventResults> loadResults(RaceEvent event) async =>
      EventResults(eventId: event.id, sessions: []);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'official qualifying appears before estimated end without Jolpica',
    () async {
      final event = RaceEvent(
        id: 'live',
        seriesId: 'f1',
        season: 2026,
        round: 99,
        name: 'Singapore Grand Prix',
        cancelled: false,
        circuit: const Circuit(name: 'Singapore'),
        sessions: [
          RaceSession(
            type: 'Q',
            name: 'Qualifying',
            startTimeUtc: DateTime.now().toUtc().subtract(
              const Duration(minutes: 30),
            ),
            cancelled: false,
            durationMinutes: 60,
          ),
        ],
        resultsPath: 'events/live.json',
      );
      final requests = <String>[];
      final repository = NetworkFirstCalendarRepository(
        fallback: EmptyResults(),
        client: MockClient((request) async {
          requests.add(request.url.toString());
          if (request.url.host != 'www.formula1.com') {
            return http.Response('', 404);
          }
          if (request.url.path.endsWith('/races')) {
            return http.Response(
              '<a href="/en/results/2026/races/1296/singapore/race-result">Singapore</a>',
              200,
            );
          }
          return http.Response(
            '<table><tr><th>Pos</th></tr><tr><td>1</td><td>3</td><td>Max Verstappen VER</td><td>Red Bull Racing</td><td>1:33.241</td><td>1:31.639</td><td>1:31.373</td><td>15</td></tr></table>',
            200,
          );
        }),
      );
      final result = await repository.loadResults(event);
      expect(result.sessions.single.results.single.driver.code, 'VER');
      expect(result.sessions.single.results.single.time, '1:31.373');
      expect(requests.any((url) => url.contains('api.jolpi.ca')), isFalse);
    },
  );
}
