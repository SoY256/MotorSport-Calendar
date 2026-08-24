import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/calendar_repository.dart';
import '../domain/race_event.dart';

final calendarRepositoryProvider = Provider<CalendarRepository>((ref) {
  return NetworkFirstCalendarRepository(fallback: AssetCalendarRepository());
});

final calendarProvider = FutureProvider<CalendarData>((ref) {
  return ref.watch(calendarRepositoryProvider).load();
});

final eventResultsProvider = FutureProvider.family<EventResults, RaceEvent>((
  ref,
  event,
) {
  return ref.watch(calendarRepositoryProvider).loadResults(event);
});

final standingsProvider = FutureProvider<StandingsData>((ref) {
  return ref.watch(calendarRepositoryProvider).loadStandings();
});
