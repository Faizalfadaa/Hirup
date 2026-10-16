import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../core/config/app_config.dart';
import '../core/theme/app_theme.dart';
import '../core/utils/polyline.dart';
import '../features/route_planning/domain/models.dart';

/// Pilot corridor (SPEC 6.1): lat -6.30..-6.13, lon 106.76..106.85.
final pilotBounds = LatLngBounds(const LatLng(-6.30, 106.76), const LatLng(-6.13, 106.85));

/// Colour anchors at the PM2.5 category bounds used by the P2 tile renderer
/// (ml/configs/model.yaml `tiles.ispu`). Still `verified_by: null` there, so the
/// colours are labelled as an estimate in the legend.
const _anchors = <(double, Color)>[
  (0, Color(0xFF00B050)),
  (15.5, Color(0xFF00B050)),
  (55.4, Color(0xFF0070C0)),
  (150.4, Color(0xFFFFC000)),
  (250.4, Color(0xFFFF0000)),
  (500, Color(0xFF000000)),
];

Color pm25Color(double value) {
  if (value <= _anchors.first.$1) return _anchors.first.$2;
  for (var i = 1; i < _anchors.length; i++) {
    final (upper, colour) = _anchors[i];
    if (value <= upper) {
      final (lower, from) = _anchors[i - 1];
      return Color.lerp(from, colour, (value - lower) / (upper - lower))!;
    }
  }
  return _anchors.last.$2;
}

/// A run of consecutive polyline segments that share one colour.
class RouteSegment {
  const RouteSegment(this.points, this.color, {this.dashed = false});
  final List<LatLng> points;
  final Color color;
  final bool dashed;
}

/// What the map draws for a route: one white casing per leg and coloured runs on top.
class RouteDrawing {
  const RouteDrawing(this.casings, this.runs);
  final List<List<LatLng>> casings;
  final List<RouteSegment> runs;
  bool get isEmpty => casings.isEmpty;
  Iterable<LatLng> get points => casings.expand((path) => path);
}

/// Colours each leg by `segments_pm25` (FR-04), one value per polyline segment.
/// Values are binned to 5 ug/m3 so neighbouring segments merge into longer runs;
/// legs without concentrations use their mean. Walking and cycling legs are dashed.
RouteDrawing routeDrawing(RouteOption option, {int? highlightLeg}) {
  final casings = <List<LatLng>>[];
  final runs = <RouteSegment>[];
  for (final (index, leg) in option.legs.indexed) {
    final encoded = leg.polyline;
    if (encoded == null || encoded.isEmpty) continue;
    final points = decodePolyline(encoded);
    if (points.length < 2) continue;
    casings.add(points);
    final dimmed = highlightLeg != null && highlightLeg != index;
    final dashed = leg.mode == 'WALK' || leg.mode == 'BICYCLE';
    final values = leg.segmentsPm25;
    final perSegment = values != null && values.length == points.length - 1;
    Color colourAt(int i) {
      final value = perSegment ? values[i] : leg.meanPm25;
      final colour = pm25Color((value / 5).round() * 5.0);
      return dimmed ? colour.withValues(alpha: .35) : colour;
    }

    var start = 0;
    for (var i = 1; i < points.length; i++) {
      // Close the run at the last point or where the next segment changes colour.
      if (i == points.length - 1 || colourAt(i) != colourAt(start)) {
        runs.add(RouteSegment(points.sublist(start, i + 1), colourAt(start), dashed: dashed));
        start = i;
      }
    }
  }
  return RouteDrawing(casings, runs);
}

/// About 40% saturation, slightly lifted, so the basemap stays calm under the route.
const _muted = <double>[
  0.5, 0.45, 0.05, 0, 20, //
  0.15, 0.8, 0.05, 0, 20, //
  0.15, 0.45, 0.4, 0, 20, //
  0, 0, 0, 1, 0,
];

/// Interactive basemap with the PM2.5 tile overlay, the journey end points and,
/// when given, the selected route coloured by concentration.
class AirMap extends StatelessWidget {
  const AirMap({
    super.key,
    this.origin,
    this.destination,
    this.route,
    this.highlightLeg,
    this.interactive = true,
    this.showAirLayer = true,
  });

  final PlacePoint? origin;
  final PlacePoint? destination;
  final RouteOption? route;
  final int? highlightLeg;
  final bool interactive;
  final bool showAirLayer;

  @override
  Widget build(BuildContext context) {
    final drawing = route == null ? const RouteDrawing([], []) : routeDrawing(route!, highlightLeg: highlightLeg);
    final ends = [
      if (origin != null) LatLng(origin!.lat, origin!.lon),
      if (destination != null) LatLng(destination!.lat, destination!.lon),
    ];
    final focus = [...ends, ...drawing.points];
    final fit = focus.length >= 2
        ? CameraFit.coordinates(coordinates: focus, padding: const EdgeInsets.all(36), maxZoom: 16)
        : CameraFit.bounds(bounds: pilotBounds, padding: const EdgeInsets.all(8));
    return FlutterMap(
      // A new key refits the camera when the route or the end points change.
      key: ValueKey(Object.hashAll([...focus, highlightLeg])),
      options: MapOptions(
        initialCameraFit: fit,
        minZoom: 10,
        maxZoom: 18,
        backgroundColor: AppColors.surfaceSky,
        interactionOptions: InteractionOptions(
          flags: interactive ? InteractiveFlag.all & ~InteractiveFlag.rotate : InteractiveFlag.none,
        ),
      ),
      children: [
        ColorFiltered(
          // Muted basemap so the PM2.5 colours carry the meaning (SPEC 14.4).
          colorFilter: const ColorFilter.matrix(_muted),
          child: TileLayer(
            // OpenStreetMap standard tiles: no key; the tile usage policy asks for
            // attribution and an identifying user agent, both set here.
            urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
            userAgentPackageName: 'id.hirup.app',
            maxNativeZoom: 19,
          ),
        ),
        if (showAirLayer)
          Opacity(
            opacity: .65,
            child: TileLayer(
              // Rendered by the P2 hourly job; absent (HTTP 503) until the ISPU
              // colour table is verified, in which case only the basemap shows.
              urlTemplate: '${AppConfig.apiBaseUrl}/v1/aq/tiles/{z}/{x}/{y}.png',
              minNativeZoom: 10,
              maxNativeZoom: 15,
              tileBounds: pilotBounds,
              userAgentPackageName: 'id.hirup.app',
              errorTileCallback: (tile, error, stackTrace) {},
            ),
          ),
        if (!drawing.isEmpty)
          PolylineLayer(polylines: [
            for (final casing in drawing.casings) Polyline(points: casing, color: Colors.white, strokeWidth: 10),
            for (final run in drawing.runs)
              Polyline(
                points: run.points,
                color: run.color,
                strokeWidth: 6,
                pattern: run.dashed ? StrokePattern.dashed(segments: const [12, 8]) : const StrokePattern.solid(),
              ),
          ]),
        if (ends.isNotEmpty)
          MarkerLayer(markers: [
            if (origin != null) _endMarker(LatLng(origin!.lat, origin!.lon), Icons.trip_origin, AppColors.brand600),
            if (destination != null) _endMarker(LatLng(destination!.lat, destination!.lon), Icons.place, AppColors.danger700),
          ]),
        // Required by the OSM tile usage policy; kept small so it does not cover the route.
        Align(
          alignment: Alignment.bottomRight,
          child: Container(
            margin: const EdgeInsets.all(6),
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(color: Colors.white.withValues(alpha: .85), borderRadius: BorderRadius.circular(6)),
            child: const Text('© OpenStreetMap contributors', style: TextStyle(fontSize: 9, color: AppColors.ink700)),
          ),
        ),
      ],
    );
  }

  Marker _endMarker(LatLng point, IconData icon, Color colour) => Marker(
        point: point,
        width: 34,
        height: 34,
        child: DecoratedBox(
          decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: colour, width: 2.5)),
          child: Icon(icon, size: 18, color: colour),
        ),
      );
}

/// Legend for the route and overlay colours; text accompanies the colours (SPEC 14.2).
class Pm25Legend extends StatelessWidget {
  const Pm25Legend({super.key});
  @override
  Widget build(BuildContext context) => Wrap(spacing: 10, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
        // Each swatch is the anchor colour at the category's upper bound.
        for (final (label, value) in const [('Baik', 15.5), ('Sedang', 55.4), ('Tidak sehat', 150.4), ('Sangat tidak sehat', 250.4)])
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 12, height: 12, decoration: BoxDecoration(color: pm25Color(value), borderRadius: BorderRadius.circular(3))),
            const SizedBox(width: 4),
            Text(label, style: const TextStyle(fontSize: 11, color: AppColors.ink700)),
          ]),
        const Text('· warna estimasi PM2.5', style: TextStyle(fontSize: 11, color: AppColors.ink600)),
      ]);
}
