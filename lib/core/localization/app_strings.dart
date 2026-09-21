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
  String events(int count) => _en ? '$count events' : '$count wydarzeń';
  String get timesInZone =>
      _en ? 'times in the selected time zone' : 'godziny w wybranej strefie';
  String get nextRound => _en ? 'NEXT ROUND' : 'NAJBLIŻSZA RUNDA';
  String sessions(int count) => _en ? '$count sessions' : '$count sesji';
  String duration(int minutes) {
    if (minutes >= 60 && minutes % 60 == 0) {
      final hours = minutes ~/ 60;
      return _en ? '$hours h' : '$hours godz.';
    }
    return _en ? '$minutes min' : '$minutes min';
  }

  String get expectedDuration =>
      _en ? 'Expected duration' : 'Przewidywany czas';
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
  String get awaitingResults =>
      _en ? 'Waiting for results' : 'Oczekiwanie na wyniki';
  String get results => _en ? 'Details' : 'Szczegóły';
  String get month => _en ? 'Month' : 'Miesiąc';
  String get week => _en ? 'Week' : 'Tydzień';
  String get previous => _en ? 'Previous' : 'Poprzedni';
  String get next => _en ? 'Next' : 'Następny';
  String get plannedSessions =>
      _en ? 'Scheduled sessions' : 'Zaplanowane sesje';
  String get circuitLength => _en ? 'Circuit length' : 'Długość toru';
  String get lapRecord => _en ? 'Lap record' : 'Rekord toru';
  String get categories => _en ? 'Categories' : 'Kategorie';
  String selectedCategories(int count) =>
      _en ? '$count selected' : 'Wybrano: $count';
  String get championship => _en ? 'Championship' : 'Mistrzostwa';
  String get motorsportCategories =>
      _en ? 'Motorsport categories' : 'Kategorie Motorsport';
  String get esportCategories => _en ? 'E-Sport' : 'E-Sport';
  String get chooseAny => _en
      ? 'Choose any number of categories'
      : 'Wybierz dowolną liczbę kategorii';
  String get drivers => _en ? 'Drivers' : 'Kierowcy';
  String get constructors => _en ? 'Constructors' : 'Konstruktorzy';
  String get manufacturers => _en ? 'Manufacturers' : 'Producenci';
  String get teams => _en ? 'Teams' : 'Zespoły';
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
  String get privacyPolicy => _en ? 'Privacy Policy' : 'Polityka prywatności';
  String get privacyPolicyHint =>
      _en ? 'How Secar handles data' : 'Jak Secar przetwarza dane';
  String get aboutSecar => _en ? 'About Secar' : 'O Secar';
  String get independentApp => _en
      ? 'Independent, unofficial motorsport application'
      : 'Niezależna, nieoficjalna aplikacja motorsportowa';
  String get legalNotice => _en
      ? 'Secar is an independent, unofficial motorsport reference application. It is not affiliated with, endorsed by or sponsored by Formula 1, FIA Formula 2, FIA Formula 3, FIA WEC, IMSA, INDYCAR, INDY NXT, their organizers, teams or manufacturers. All series names, team names, logos, driver images and other trademarks belong to their respective owners. Results and schedules can change; for official decisions, consult the relevant championship organizer.'
      : 'Secar jest niezależną, nieoficjalną aplikacją informacyjną o sportach motorowych. Nie jest powiązana, zatwierdzona ani sponsorowana przez Formula 1, FIA Formula 2, FIA Formula 3, FIA WEC, IMSA, INDYCAR, INDY NXT, ich organizatorów, zespoły ani producentów. Nazwy serii i zespołów, logotypy, zdjęcia kierowców oraz inne znaki towarowe należą do ich właścicieli. Wyniki i terminarze mogą ulec zmianie; oficjalne decyzje należy sprawdzać u organizatora danych mistrzostw.';
  String get close => _en ? 'Close' : 'Zamknij';
  String get exitApp => _en ? 'Exit Secar?' : 'Wyjść z Secar?';
  String get exitAppMessage => _en
      ? 'Are you sure you want to close the application?'
      : 'Czy na pewno chcesz zamknąć aplikację?';
  String get stayInApp => _en ? 'Stay' : 'Zostań';
  String get exit => _en ? 'Exit' : 'Wyjdź';
  String get loadingError =>
      _en ? 'Could not load data' : 'Nie udało się wczytać danych';
  String get retry => _en ? 'Try again' : 'Spróbuj ponownie';
  String get completed => _en ? 'Completed' : 'Zakończone';
}
