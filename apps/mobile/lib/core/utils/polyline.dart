import 'package:latlong2/latlong.dart';

/// Decodes an encoded polyline. The API uses precision 6 (SPEC 13).
List<LatLng> decodePolyline(String encoded, {int precision = 6}) {
  final scale = _pow10(precision);
  final points = <LatLng>[];
  var index = 0, lat = 0, lon = 0;
  int next() {
    var result = 0, shift = 0, byte = 0;
    do {
      byte = encoded.codeUnitAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    return (result & 1) != 0 ? ~(result >> 1) : result >> 1;
  }

  while (index < encoded.length) {
    lat += next();
    lon += next();
    points.add(LatLng(lat / scale, lon / scale));
  }
  return points;
}

int _pow10(int exponent) => List.filled(exponent, 10).fold(1, (a, b) => a * b);
