import 'package:flutter/material.dart';

enum SeriesGroup { main, gt3 }

/// A championship the app can show. Everything series-specific (labels,
/// colours, logos, settings grouping) is defined here once.
class SeriesInfo {
  const SeriesInfo({
    required this.id,
    required this.label,
    required this.name,
    required this.color,
    this.group = SeriesGroup.main,
    this.logo,
    this.darkLogo,
    this.region,
  });

  final String id;

  /// Short upper-case label used in tabs, tags and notifications.
  final String label;
  final String name;
  final Color color;
  final SeriesGroup group;
  final String? logo;
  final String? darkLogo;

  /// Where a GT3 championship races, e.g. "Europe".
  final String? region;
}

const mainSeries = <SeriesInfo>[
  SeriesInfo(
    id: 'f1',
    label: 'F1',
    name: 'Formula 1',
    color: Color(0xFFE10600),
    logo: 'assets/brands/f1-official.svg',
  ),
  SeriesInfo(
    id: 'f2',
    label: 'F2',
    name: 'FIA Formula 2',
    color: Color(0xFF1565C0),
    logo: 'assets/brands/f2-official.svg',
  ),
  SeriesInfo(
    id: 'f3',
    label: 'F3',
    name: 'FIA Formula 3',
    color: Color(0xFF7B1FA2),
    logo: 'assets/brands/f3-official.svg',
  ),
  SeriesInfo(
    id: 'imsa',
    label: 'IMSA',
    name: 'IMSA WeatherTech',
    color: Color(0xFFEF6C00),
    logo: 'assets/brands/imsa.svg',
  ),
  SeriesInfo(
    id: 'indycar',
    label: 'INDYCAR',
    name: 'NTT INDYCAR SERIES',
    color: Color(0xFFD71920),
    logo: 'assets/brands/indycar-official.png',
  ),
  SeriesInfo(
    id: 'indynxt',
    label: 'INDY NXT',
    name: 'INDY NXT by Firestone',
    color: Color(0xFFE31837),
    logo: 'assets/brands/indynxt-official.png',
  ),
  SeriesInfo(
    id: 'wec',
    label: 'WEC',
    name: 'FIA World Endurance Championship',
    color: Color(0xFF00695C),
    logo: 'assets/brands/wec-official.png',
  ),
];

/// SRO GT3 championships, imported by scripts/fetch_gt3_results.py.
const gt3Series = <SeriesInfo>[
  SeriesInfo(
    id: 'gtwc-endurance',
    label: 'GTWC ENDURANCE',
    name: 'GT World Challenge Europe Endurance Cup',
    color: Color(0xFF0057B8),
    group: SeriesGroup.gt3,
    region: 'Europe',
  ),
  SeriesInfo(
    id: 'gtwc-sprint',
    label: 'GTWC SPRINT',
    name: 'GT World Challenge Europe Sprint Cup',
    color: Color(0xFF00A3E0),
    group: SeriesGroup.gt3,
    region: 'Europe',
  ),
  SeriesInfo(
    id: 'igtc',
    label: 'IGTC',
    name: 'Intercontinental GT Challenge',
    color: Color(0xFFB8860B),
    group: SeriesGroup.gt3,
    region: 'World',
  ),
  SeriesInfo(
    id: 'gtwc-america',
    label: 'GTWC AMERICA',
    name: 'GT World Challenge America',
    color: Color(0xFF3949AB),
    group: SeriesGroup.gt3,
    region: 'North America',
  ),
  SeriesInfo(
    id: 'gtwc-asia',
    label: 'GTWC ASIA',
    name: 'GT World Challenge Asia',
    color: Color(0xFFC2185B),
    group: SeriesGroup.gt3,
    region: 'Asia',
  ),
  SeriesInfo(
    id: 'gtwc-australia',
    label: 'GTWC AUSTRALIA',
    name: 'GT World Challenge Australia',
    color: Color(0xFFF9A825),
    group: SeriesGroup.gt3,
    region: 'Australia',
  ),
  SeriesInfo(
    id: 'british-gt',
    label: 'BRITISH GT',
    name: 'British GT Championship',
    color: Color(0xFF2E7D32),
    group: SeriesGroup.gt3,
    region: 'United Kingdom',
  ),
];

const allSeries = <SeriesInfo>[...mainSeries, ...gt3Series];

final Set<String> gt3SeriesIds = {for (final item in gt3Series) item.id};

final Map<String, SeriesInfo> _byId = {
  for (final item in allSeries) item.id: item,
};

SeriesInfo? seriesInfo(String id) => _byId[id.toLowerCase()];

String seriesLabel(String id) => seriesInfo(id)?.label ?? id.toUpperCase();

Color seriesColor(String id) =>
    seriesInfo(id)?.color ?? const Color(0xFF455A64);

/// Catalog order (main series first, then GT3), unknown ids last.
int seriesOrder(String id) {
  final index = allSeries.indexWhere((item) => item.id == id);
  return index < 0 ? allSeries.length : index;
}
