import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hirup/core/utils/polyline.dart';
import 'package:hirup/features/route_planning/domain/models.dart';
import 'package:hirup/shared/air_map.dart';

const _walkLeg = <String, dynamic>{
  'mode': 'WALK',
  'start_time': '2026-10-16T07:00:00+07:00',
  'end_time': '2026-10-16T07:10:00+07:00',
  'duration_s': 600,
  'from': {'name': 'A', 'lat': 38.5, 'lon': -120.2},
  'to': {'name': 'B', 'lat': 43.252, 'lon': -126.453},
  'mean_pm25': 30,
  'dose_ug': 1.0,
  'polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
  'segments_pm25': [10, 200],
};

void main() {
  test('decodes the reference polyline at precision 5 and 6', () {
    final five = decodePolyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@', precision: 5);
    expect(five.map((p) => [p.latitude, p.longitude]), [
      [38.5, -120.2],
      [40.7, -120.95],
      [43.252, -126.453],
    ]);
    // The same coordinates divided by 10 when read at precision 6.
    expect(decodePolyline('_p~iF~ps|U', precision: 6).single.latitude, closeTo(3.85, 1e-9));
  });

  test('routes are coloured per polyline segment over one casing per leg', () {
    final leg = TripLeg.fromJson(_walkLeg);
    final option = RouteOption(id: 'r', labels: const ['fastest'], departAt: leg.startTime, arriveAt: leg.endTime, durationS: 600, transfers: 0, distanceM: 1000, doseUg: 1, doseP10: 0.5, doseP90: 2, deltaDosePct: 0, deltaDurationS: 0, dataQuality: 'real', legs: [leg]);
    final drawing = routeDrawing(option);
    expect(drawing.casings.single, hasLength(3));
    expect(drawing.runs, hasLength(2));
    expect(drawing.runs.first.color, pm25Color(10));
    expect(drawing.runs.last.color, pm25Color(200));
    expect(drawing.runs.every((s) => s.dashed), isTrue);
    // Consecutive runs share their joining point, so the line has no gaps.
    expect(drawing.runs.first.points.last, drawing.runs.last.points.first);
  });

  test('neighbouring segments with similar values merge into one run', () {
    final leg = TripLeg.fromJson({..._walkLeg, 'mode': 'BUS', 'segments_pm25': [40, 41]});
    final option = RouteOption(id: 'r', labels: const ['fastest'], departAt: leg.startTime, arriveAt: leg.endTime, durationS: 600, transfers: 0, distanceM: 1000, doseUg: 1, doseP10: 0.5, doseP90: 2, deltaDosePct: 0, deltaDurationS: 0, dataQuality: 'real', legs: [leg]);
    final run = routeDrawing(option).runs.single;
    expect(run.points, hasLength(3));
    expect(run.dashed, isFalse);
  });

  test('PM2.5 colours get darker as concentration rises past the bounds', () {
    expect(pm25Color(5), const Color(0xFF00B050));
    expect(pm25Color(55.4), const Color(0xFF0070C0));
    expect(pm25Color(1000), const Color(0xFF000000));
  });
}
