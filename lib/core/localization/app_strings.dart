import '../../features/settings/domain/app_settings.dart';

class AppStrings {
  const AppStrings(this.language);
  final AppLanguage language;
  bool get _en => language == AppLanguage.english;

  String get calendar => _en ? 'Calendar' : 'Kalendarz';
  String get list => _en ? 'List' : 'Lista';
  String get weekend => _en ? 'Weekend' : 'Weekend';
  String get standings => _en ? 'Standings' : 'Klasyfikacja';
  String get settings => _en ? 'Settings' : 'Ustawienia';
  String get season => _en ? 'Season' : 'Sezon';
  String rounds(int count) => _en ? '$count rounds' : '$count rund';
  String get timesInZone =>
      _en ? 'times in the selected time zone' : 'godziny w wybranej strefie';
  String get nextRound => _en ? 'NEXT ROUND' : 'NAJBLIŻSZA RUNDA';
  String sessions(int count) => _en ? '$count sessions' : '$count sesji';
  String get updated => _en ? 'Updated' : 'Dane zaktualizowano';
  String get refresh => _en ? 'Refresh data' : 'Odśwież dane';
  String get showPast =>
      _en ? 'Show completed events' : 'Pokaż poprzednie wydarzenia';
  String get hidePast =>
      _en ? 'Hide completed events' : 'Ukryj poprzednie wydarzenia';
  String get noUpcoming =>
      _en ? 'No upcoming events' : 'Brak nadchodzących wydarzeń';
  String get selectEvent => _en ? 'Select an event' : 'Wybierz wydarzenie';
  String get noResults =>
      _en ? 'Results are not available yet' : 'Wyniki nie są jeszcze dostępne';
  String get results => _en ? 'Details' : 'Szczegóły';
  String get month => _en ? 'Month' : 'Miesiąc';
  String get week => _en ? 'Week' : 'Tydzień';
  String get previous => _en ? 'Previous' : 'Poprzedni';
  String get next => _en ? 'Next' : 'Następny';
  String get plannedSessions =>
      _en ? 'Scheduled sessions' : 'Zaplanowane sesje';
  String get circuitLength => _en ? 'Circuit length' : 'Długość toru';
  String get lapRecord => _en ? 'Lap record' : 'Rekord toru';
  String get drivers => _en ? 'Drivers' : 'Kierowcy';
  String get constructors => _en ? 'Constructors' : 'Konstruktorzy';
  String get points => _en ? 'PTS' : 'PKT';
  String get wins => _en ? 'Wins' : 'Wygrane';
  String get customize =>
      _en ? 'Customize the application' : 'Dopasuj aplikację do siebie';
  String get darkMode => _en ? 'Dark mode' : 'Tryb ciemny';
  String get darkModeHint => _en
      ? 'One design system, different colors'
      : 'Ten sam design system, inne kolory';
  String get languageLabel => _en ? 'Language' : 'Język';
  String get polish => _en ? 'Polish' : 'Polski';
  String get english => _en ? 'English' : 'Angielski';
  String get eventTime => _en ? 'Event time' : 'Czas wydarzeń';
  String get localTime => _en ? 'My local time' : 'Mój czas lokalny';
  String get trackTime => _en ? 'Track local time' : 'Czas lokalny toru';
  String get loadingError =>
      _en ? 'Could not load data' : 'Nie udało się wczytać danych';
  String get retry => _en ? 'Try again' : 'Spróbuj ponownie';
  String get completed => _en ? 'Completed' : 'Zakończone';
}
