import 'package:flutter_test/flutter_test.dart';
import 'package:hirup/features/route_planning/data/geocoder.dart';
import 'package:hirup/features/route_planning/domain/models.dart';

void main() {
  test('Photon features become named places with lat/lon in the right order', () {
    final places = parsePhoton({
      'features': [
        {
          'geometry': {'coordinates': [106.849935, -6.2101704]},
          'properties': {'name': 'Manggarai', 'district': 'Tebet', 'city': 'DKI Jakarta'},
        },
        {
          // Same label again: dropped.
          'geometry': {'coordinates': [106.85, -6.21]},
          'properties': {'name': 'Manggarai', 'district': 'Tebet'},
        },
        {
          'geometry': {'coordinates': [106.8, -6.2]},
          'properties': {'street': 'Jalan Sudirman', 'city': 'Jakarta'},
        },
        {'geometry': {'coordinates': [106.8, -6.2]}, 'properties': <String, dynamic>{}},
      ],
    });
    expect(places.map((p) => p.name), ['Manggarai, Tebet', 'Jalan Sudirman, Jakarta']);
    expect(places.first.lat, -6.2101704);
    expect(places.first.lon, 106.849935);
  });

  test('routes are only offered inside the pilot corridor', () {
    expect(pilotPlaces.every((p) => p.insideRoutingPilot), isTrue);
    // Cempaka Putih: on the DKI map, east of the pilot corridor.
    expect(const PlacePoint(name: 'Cempaka Putih', lat: -6.18, lon: 106.87).insideRoutingPilot, isFalse);
    expect(pilotPlaces.first.samePlaceAs(PlacePoint(name: 'x', lat: pilotPlaces.first.lat, lon: pilotPlaces.first.lon)), isTrue);
  });
}
