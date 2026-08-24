class CircuitMetadata {
  const CircuitMetadata({required this.lengthKm, required this.lapRecord});

  final double? lengthKm;
  final String? lapRecord;
}

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
    _ => null,
  };
  return asset == null ? null : 'assets/circuits/$asset.svg';
}
