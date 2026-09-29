class CircuitMetadata {
  const CircuitMetadata({required this.lengthKm, required this.lapRecord});

  final double? lengthKm;
  final String? lapRecord;

  /// The built-in catalogue contains Formula 1 records only. Records for
  /// other championships come from their official, series-specific feeds.
  String? lapRecordFor(String seriesId, String circuitName) =>
      _seriesLapRecords['$seriesId|$circuitName'] ??
      (seriesId == 'f1' ? lapRecord : null);
}

// Fastest officially published lap for the named series in the 2026 event.
// Future rounds intentionally have no entry until their official timing exists.
const _seriesLapRecords = <String, String>{
  'f2|Albert Park Grand Prix Circuit': '1:28.695 • Dino Beganovic (2026)',
  'f2|Miami International Autodrome': '1:39.888 • Kush Maini (2026)',
  'f2|Circuit Gilles Villeneuve': '1:21.422 • Laurens van Hoepen (2026)',
  'f2|Circuit de Monaco': '1:20.923 • Rafael Câmara (2026)',
  'f2|Circuit de Barcelona-Catalunya': '1:24.810 • Rafael Câmara (2026)',
  'f2|Red Bull Ring': '1:15.544 • Noel Leon (2026)',
  'f2|Silverstone Circuit': '1:39.690 • Rafael Câmara (2026)',
  'f2|Circuit de Spa-Francorchamps': '1:56.306 • Rafael Câmara (2026)',
  'f2|Hungaroring': '1:28.896 • Kush Maini (2026)',
  'f2|Autodromo Nazionale di Monza': '1:31.326 • Rafael Câmara (2026)',
  'f2|Madring': '1:44.331 • Dino Beganovic (2026)',
  'f2|Baku City Circuit': '1:53.728 • Martinius Stenshorne (2026)',
  'f3|Albert Park Grand Prix Circuit': '1:34.187 • Théophile Naël (2026)',
  'f3|Circuit de Monaco': '1:24.471 • Théophile Naël (2026)',
  'f3|Circuit de Barcelona-Catalunya': '1:28.263 • Théophile Naël (2026)',
  'f3|Red Bull Ring': '1:21.730 • Hiyu Yamakoshi (2026)',
  'f3|Silverstone Circuit': '1:45.620 • Freddie Slater (2026)',
  'f3|Circuit de Spa-Francorchamps': '2:05.150 • Freddie Slater (2026)',
  'f3|Hungaroring': '1:33.411 • Tuukka Taponen (2026)',
  'f3|Autodromo Nazionale di Monza': '1:37.445 • Alessandro Giusti (2026)',
  'f3|Madring': '1:49.750 • Tuukka Taponen (2026)',
  'wec|Imola Circuit': '1:32.066 • Nicklas Nielsen (2026)',
  'wec|Circuit de Spa-Francorchamps': '2:04.177 • Stoffel Vandoorne (2026)',
  'wec|Circuit de la Sarthe': '3:25.041 • Ryo Hirakawa (2026)',
  'wec|Autódromo José Carlos Pace': '1:25.508 • Will Stevens (2026)',
  'wec|Circuit of the Americas': '1:53.674 • Nyck de Vries (2026)',
  'wec|Fuji Speedway': '1:30.486 • Victor Martins (2026)',
  'imsa|Daytona International Speedway': '1:35.826 • Matt Campbell (2026)',
  'imsa|Sebring International Raceway': '1:49.020 • Felipe Nasr (2026)',
  'imsa|Long Beach Street Circuit': '1:12.918 • Laurin Heinrich (2026)',
  'imsa|WeatherTech Raceway Laguna Seca': '1:15.315 • Jack Aitken (2026)',
  'imsa|Detroit Street Circuit': '1:06.234 • Earl Bamber (2026)',
  'imsa|Watkins Glen International': '1:34.967 • Jack Aitken (2026)',
  'imsa|Canadian Tire Motorsport Park': '1:08.481 • Sebastian Alvarez (2026)',
  'imsa|Road America': '1:52.124 • Sheldon van der Linde (2026)',
  'imsa|Virginia International Raceway': '1:46.686 • Andrea Caldarelli (2026)',
  'imsa|Indianapolis Motor Speedway': '1:16.610 • Renger van der Zande (2026)',
  'indycar|Streets of St. Petersburg': '1:02.2131 • Kyle Kirkwood (2026)',
  'indycar|Phoenix Raceway': '0:21.8686 • Will Power (2026)',
  'indycar|Streets of Arlington': '1:33.9902 • Scott Dixon (2026)',
  'indycar|Barber Motorsports Park': '1:08.6127 • Christian Lundgaard (2026)',
  'indycar|Long Beach Street Circuit': '1:08.8328 • Josef Newgarden (2026)',
  'indycar|Indianapolis Motor Speedway Road Course':
      '1:12.1221 • Alex Palou (2026)',
  'indycar|Indianapolis Motor Speedway': '0:39.9777 • Conor Daly (2026)',
  'indycar|Detroit Street Circuit': '1:03.0794 • Alex Palou (2026)',
  'indycar|World Wide Technology Raceway': '0:26.5257 • Josef Newgarden (2026)',
  'indycar|Road America': '1:45.5659 • Christian Lundgaard (2026)',
  'indycar|Mid-Ohio Sports Car Course': '1:06.5323 • Josef Newgarden (2026)',
  'indycar|Nashville Superspeedway': '0:24.1178 • Scott McLaughlin (2026)',
  'indycar|Portland International Raceway':
      '1:00.3070 • Marcus Ericsson (2026)',
  'indycar|Streets of Markham': '1:14.2690 • Marcus Ericsson (2026)',
  'indycar|Streets of Washington, D.C.': '0:57.9495 • Will Power (2026)',
  'indycar|Milwaukee Mile': '0:22.9156 • Pato O\'Ward (2026)',
  'indycar|WeatherTech Raceway Laguna Seca': '1:11.6544 • Rinus VeeKay (2026)',
  'indynxt|Streets of St. Petersburg': '1:05.0881 • Max Taylor (2026)',
  'indynxt|Streets of Arlington': '1:38.5998 • Max Taylor (2026)',
  'indynxt|Barber Motorsports Park': '1:12.0646 • Alessandro de Tullio (2026)',
  'indynxt|Indianapolis Motor Speedway Road Course':
      '1:16.4803 • Alessandro de Tullio (2026)',
  'indynxt|Detroit Street Circuit': '1:06.2411 • Enzo Fittipaldi (2026)',
  'indynxt|World Wide Technology Raceway': '0:28.3282 • Myles Rowe (2026)',
  'indynxt|Road America': '1:52.6679 • Bryce Aron (2026)',
  'indynxt|Mid-Ohio Sports Car Course': '1:09.9312 • Enzo Fittipaldi (2026)',
  'indynxt|Nashville Superspeedway': '0:26.1858 • Lochie Hughes (2026)',
  'indynxt|Portland International Raceway': '1:03.0202 • Jacob Abel (2026)',
  'indynxt|Milwaukee Mile': '0:24.6137 • Jack Beeton (2026)',
  'indynxt|WeatherTech Raceway Laguna Seca': '1:15.1093 • Josh Pierson (2026)',
};

const _circuitMetadata = <String, CircuitMetadata>{
  'Albert Park Grand Prix Circuit': CircuitMetadata(
    lengthKm: 5.278,
    lapRecord: '1:19.813 • Charles Leclerc (2024)',
  ),
  'Shanghai International Circuit': CircuitMetadata(
    lengthKm: 5.451,
    lapRecord: '1:32.238 • Michael Schumacher (2004)',
  ),
  'Suzuka International Racing Course': CircuitMetadata(
    lengthKm: 5.807,
    lapRecord: '1:30.983 • Lewis Hamilton (2019)',
  ),
  'Suzuka Circuit': CircuitMetadata(
    lengthKm: 5.807,
    lapRecord: '1:30.983 • Lewis Hamilton (2019)',
  ),
  'Miami International Autodrome': CircuitMetadata(
    lengthKm: 5.412,
    lapRecord: '1:29.708 • Max Verstappen (2023)',
  ),
  'Circuit Gilles Villeneuve': CircuitMetadata(
    lengthKm: 4.361,
    lapRecord: '1:13.078 • Valtteri Bottas (2019)',
  ),
  'Circuit de Monaco': CircuitMetadata(
    lengthKm: 3.337,
    lapRecord: '1:12.909 • Lewis Hamilton (2021)',
  ),
  'Circuit de Barcelona-Catalunya': CircuitMetadata(
    lengthKm: 4.657,
    lapRecord: '1:16.330 • Max Verstappen (2023)',
  ),
  'Red Bull Ring': CircuitMetadata(
    lengthKm: 4.318,
    lapRecord: '1:05.619 • Carlos Sainz (2020)',
  ),
  'Silverstone Circuit': CircuitMetadata(
    lengthKm: 5.891,
    lapRecord: '1:27.097 • Max Verstappen (2020)',
  ),
  'Circuit de Spa-Francorchamps': CircuitMetadata(
    lengthKm: 7.004,
    lapRecord: '1:44.701 • Sergio Pérez (2024)',
  ),
  'Hungaroring': CircuitMetadata(
    lengthKm: 4.381,
    lapRecord: '1:16.627 • Lewis Hamilton (2020)',
  ),
  'Circuit Zandvoort': CircuitMetadata(
    lengthKm: 4.259,
    lapRecord: '1:11.097 • Lewis Hamilton (2021)',
  ),
  'Circuit Park Zandvoort': CircuitMetadata(
    lengthKm: 4.259,
    lapRecord: '1:11.097 • Lewis Hamilton (2021)',
  ),
  'Autodromo Nazionale di Monza': CircuitMetadata(
    lengthKm: 5.793,
    lapRecord: '1:21.046 • Rubens Barrichello (2004)',
  ),
  'Baku City Circuit': CircuitMetadata(
    lengthKm: 6.003,
    lapRecord: '1:43.009 • Charles Leclerc (2019)',
  ),
  'Madring': CircuitMetadata(lengthKm: 5.474, lapRecord: null),
  'Marina Bay Street Circuit': CircuitMetadata(
    lengthKm: 4.940,
    lapRecord: '1:35.867 • Lewis Hamilton (2023)',
  ),
  'Circuit of the Americas': CircuitMetadata(
    lengthKm: 5.513,
    lapRecord: '1:36.169 • Charles Leclerc (2019)',
  ),
  'Autódromo Hermanos Rodríguez': CircuitMetadata(
    lengthKm: 4.304,
    lapRecord: '1:17.774 • Valtteri Bottas (2021)',
  ),
  'Autódromo José Carlos Pace': CircuitMetadata(
    lengthKm: 4.309,
    lapRecord: '1:10.540 • Valtteri Bottas (2018)',
  ),
  'Las Vegas Strip Street Circuit': CircuitMetadata(
    lengthKm: 6.201,
    lapRecord: '1:34.876 • Lando Norris (2024)',
  ),
  'Lusail International Circuit': CircuitMetadata(
    lengthKm: 5.419,
    lapRecord: '1:22.384 • Lando Norris (2024)',
  ),
  'Losail International Circuit': CircuitMetadata(
    lengthKm: 5.419,
    lapRecord: '1:22.384 • Lando Norris (2024)',
  ),
  'Yas Marina Circuit': CircuitMetadata(
    lengthKm: 5.281,
    lapRecord: '1:26.103 • Max Verstappen (2021)',
  ),
  'Sepang International Circuit': CircuitMetadata(
    lengthKm: 5.543,
    lapRecord: '1:34.080 • Sebastian Vettel (2017)',
  ),
  'Imola Circuit': CircuitMetadata(lengthKm: 4.909, lapRecord: null),
  'Circuit de la Sarthe': CircuitMetadata(lengthKm: 13.626, lapRecord: null),
  'Fuji Speedway': CircuitMetadata(lengthKm: 4.563, lapRecord: null),
  'Bahrain International Circuit': CircuitMetadata(
    lengthKm: 5.412,
    lapRecord: null,
  ),
  'Daytona International Speedway': CircuitMetadata(
    lengthKm: 5.729,
    lapRecord: null,
  ),
  'Sebring International Raceway': CircuitMetadata(
    lengthKm: 6.019,
    lapRecord: null,
  ),
  'Long Beach Street Circuit': CircuitMetadata(
    lengthKm: 3.167,
    lapRecord: null,
  ),
  'WeatherTech Raceway Laguna Seca': CircuitMetadata(
    lengthKm: 3.602,
    lapRecord: null,
  ),
  'Detroit Street Circuit': CircuitMetadata(lengthKm: 2.736, lapRecord: null),
  'Watkins Glen International': CircuitMetadata(
    lengthKm: 5.472,
    lapRecord: null,
  ),
  'Canadian Tire Motorsport Park': CircuitMetadata(
    lengthKm: 3.957,
    lapRecord: null,
  ),
  'Road America': CircuitMetadata(lengthKm: 6.437, lapRecord: null),
  'Virginia International Raceway': CircuitMetadata(
    lengthKm: 5.263,
    lapRecord: null,
  ),
  'Indianapolis Motor Speedway': CircuitMetadata(
    lengthKm: 3.925,
    lapRecord: null,
  ),
  'Michelin Raceway Road Atlanta': CircuitMetadata(
    lengthKm: 4.088,
    lapRecord: null,
  ),
  'Streets of St. Petersburg': CircuitMetadata(
    lengthKm: 2.897,
    lapRecord: null,
  ),
  'Phoenix Raceway': CircuitMetadata(lengthKm: 1.645, lapRecord: null),
  'Streets of Arlington': CircuitMetadata(lengthKm: 4.394, lapRecord: null),
  'Barber Motorsports Park': CircuitMetadata(lengthKm: 3.830, lapRecord: null),
  'Indianapolis Motor Speedway Road Course': CircuitMetadata(
    lengthKm: 3.925,
    lapRecord: null,
  ),
  'World Wide Technology Raceway': CircuitMetadata(
    lengthKm: 2.012,
    lapRecord: null,
  ),
  'Mid-Ohio Sports Car Course': CircuitMetadata(
    lengthKm: 3.634,
    lapRecord: null,
  ),
  'Nashville Superspeedway': CircuitMetadata(lengthKm: 2.145, lapRecord: null),
  'Portland International Raceway': CircuitMetadata(
    lengthKm: 3.166,
    lapRecord: null,
  ),
  'Streets of Markham': CircuitMetadata(lengthKm: 3.520, lapRecord: null),
  'Streets of Washington, D.C.': CircuitMetadata(
    lengthKm: 2.736,
    lapRecord: null,
  ),
  'Milwaukee Mile': CircuitMetadata(lengthKm: 1.609, lapRecord: null),
};

CircuitMetadata metadataForCircuit(String name) =>
    _circuitMetadata[name] ??
    const CircuitMetadata(lengthKm: null, lapRecord: null);

String? circuitAssetFor(String name) {
  final asset = switch (name) {
    'Albert Park Grand Prix Circuit' => 'albert-park',
    'Shanghai International Circuit' => 'shanghai',
    'Suzuka Circuit' || 'Suzuka International Racing Course' => 'suzuka',
    'Miami International Autodrome' => 'miami',
    'Circuit Gilles Villeneuve' => 'montreal',
    'Circuit de Monaco' => 'monaco',
    'Circuit de Barcelona-Catalunya' => 'catalunya',
    'Red Bull Ring' => 'red-bull-ring',
    'Silverstone Circuit' => 'silverstone',
    'Circuit de Spa-Francorchamps' => 'spa',
    'Hungaroring' => 'hungaroring',
    'Circuit Park Zandvoort' || 'Circuit Zandvoort' => 'zandvoort',
    'Autodromo Nazionale di Monza' => 'monza',
    'Madring' => 'madring',
    'Baku City Circuit' => 'baku',
    'Sepang International Circuit' => 'sepang',
    'Marina Bay Street Circuit' => 'marina-bay',
    'Circuit of the Americas' => 'austin',
    'Autódromo Hermanos Rodríguez' => 'mexico-city',
    'Autódromo José Carlos Pace' => 'interlagos',
    'Las Vegas Strip Street Circuit' => 'las-vegas',
    'Losail International Circuit' ||
    'Lusail International Circuit' => 'lusail',
    'Yas Marina Circuit' => 'yas-marina',
    'Jeddah Corniche Circuit' => 'jeddah',
    'Imola Circuit' => 'imola',
    'Fuji Speedway' => 'fuji',
    'Bahrain International Circuit' => 'bahrain',
    'Sebring International Raceway' => 'sebring',
    'Long Beach Street Circuit' => 'long-beach',
    'Detroit Street Circuit' => 'detroit',
    'Watkins Glen International' => 'watkins-glen',
    'Canadian Tire Motorsport Park' => 'mosport',
    'Indianapolis Motor Speedway' => 'indianapolis',
    'Indianapolis Motor Speedway Road Course' => 'indianapolis',
    'Circuit de la Sarthe' => 'le-mans',
    'Daytona International Speedway' => 'daytona',
    'WeatherTech Raceway Laguna Seca' => 'laguna-seca',
    'Road America' => 'road-america',
    'Virginia International Raceway' => 'vir',
    'Michelin Raceway Road Atlanta' => 'road-atlanta',
    'Portland International Raceway' => 'portland',
    'Barber Motorsports Park' => 'barber',
    'Mid-Ohio Sports Car Course' => 'mid-ohio',
    'Nashville Superspeedway' => 'nashville',
    'Phoenix Raceway' => 'phoenix',
    'Milwaukee Mile' => 'milwaukee',
    'World Wide Technology Raceway' => 'gateway',
    'Streets of St. Petersburg' => 'st-petersburg.png',
    'Streets of Arlington' => 'arlington.png',
    'Streets of Markham' => 'markham.jpg',
    'Streets of Washington, D.C.' => 'washington-dc.jpg',
    _ => null,
  };
  return asset == null
      ? null
      : 'assets/circuits/$asset${asset.contains('.') ? '' : '.svg'}';
}

int circuitQuarterTurns(String name) => switch (name) {
  'Streets of St. Petersburg' => 1,
  _ => 0,
};
