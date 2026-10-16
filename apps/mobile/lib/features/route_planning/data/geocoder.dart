import 'package:dio/dio.dart';

import '../../../core/config/app_config.dart';
import '../domain/models.dart';

/// Place search over OpenStreetMap through the public Photon geocoder (komoot): no key,
/// fair-use only, results limited to the DKI map extent. Only the typed text and the
/// map extent are sent; never the user's position.
class Geocoder {
  Geocoder([Dio? dio])
      : _dio = dio ??
            Dio(BaseOptions(
              baseUrl: 'https://photon.komoot.io',
              connectTimeout: AppConfig.requestTimeout,
              receiveTimeout: AppConfig.requestTimeout,
              headers: {'User-Agent': 'Hirup/1.0 (id.hirup.app)'},
            ));

  final Dio _dio;

  /// minLon,minLat,maxLon,maxLat of the DKI map extent (pipelines/configs/pipeline.yaml).
  static const bbox = '106.685,-6.375,106.975,-6.085';

  Future<List<PlacePoint>> search(String query) async {
    final text = query.trim();
    if (text.length < 3) return const [];
    final response = await _dio.get<Map<String, dynamic>>('/api/', queryParameters: {
      'q': text,
      'limit': 8,
      'bbox': bbox,
      'lat': -6.2,
      'lon': 106.83,
    });
    return parsePhoton(response.data ?? const {});
  }

  /// A readable name for a dropped pin, or null when nothing is near.
  Future<String?> reverse(double lat, double lon) async {
    final response = await _dio.get<Map<String, dynamic>>('/reverse', queryParameters: {'lat': lat, 'lon': lon, 'limit': 1});
    final places = parsePhoton(response.data ?? const {});
    return places.isEmpty ? null : places.first.name;
  }
}

/// Photon GeoJSON -> places named "name, district" (falling back to the street).
List<PlacePoint> parsePhoton(Map<String, dynamic> json) {
  final out = <PlacePoint>[];
  final seen = <String>{};
  for (final feature in (json['features'] as List<dynamic>? ?? const [])) {
    final props = (feature as Map<String, dynamic>)['properties'] as Map<String, dynamic>? ?? const {};
    final coords = (feature['geometry'] as Map<String, dynamic>?)?['coordinates'] as List<dynamic>?;
    if (coords == null || coords.length < 2) continue;
    final title = (props['name'] ?? props['street']) as String?;
    if (title == null || title.isEmpty) continue;
    final area = (props['district'] ?? props['locality'] ?? props['city']) as String?;
    final name = area == null || area == title ? title : '$title, $area';
    if (!seen.add(name)) continue;
    out.add(PlacePoint(name: name, lat: (coords[1] as num).toDouble(), lon: (coords[0] as num).toDouble()));
  }
  return out;
}
