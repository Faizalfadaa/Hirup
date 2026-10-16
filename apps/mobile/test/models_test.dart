import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:hirup/features/route_planning/domain/models.dart';

void main() {
  test('JourneyDraft serializes exactly to the plan contract', () {
    final draft = JourneyDraft(origin: pilotPlaces.first, destination: pilotPlaces[1], departAt: DateTime.parse('2026-10-16T07:00:00+07:00'), mode: PlanMode.transit, sensitivity: Sensitivity.rentan);
    final json = draft.toPlanJson();
    expect(json['mode'], 'transit');
    expect((json['profile'] as Map)['sensitivity'], 'rentan');
    expect(json.containsKey('include_comparison'), isTrue);
    expect(json.containsKey('arrive_at'), isFalse);
    expect(json['depart_at'], '2026-10-16T00:00:00.000Z');
  });

  test('Local departure times are sent with an explicit offset', () {
    final local = DateTime(2026, 10, 16, 7);
    expect(apiTimestamp(local), endsWith('Z'));
    expect(DateTime.parse(apiTimestamp(local)), local.toUtc());
  });

  test('PlanResult keeps multi-label routes as one option', () {
    final result = PlanResult.fromJson(jsonDecode(_planJson) as Map<String, dynamic>);
    expect(result.options, hasLength(1));
    expect(result.options.single.labels, ['fastest', 'cleanest', 'balanced']);
    expect(result.isDemo, isTrue);
  });
}

const _planJson = '''
{"request_id":"test","data_quality":"synthetic","data_freshness":{"aq_valid_hour":"2026-10-16T07:00:00+07:00","model_version":"test","confidence":"high"},"options":[{"option_id":"one","labels":["fastest","cleanest","balanced"],"depart_at":"2026-10-16T07:00:00+07:00","arrive_at":"2026-10-16T07:10:00+07:00","duration_s":600,"transfers":0,"distance_m":1000,"dose_ug":4.0,"dose_ug_p10":3.0,"dose_ug_p90":5.0,"delta_vs_fastest_pct":0.0,"delta_duration_vs_fastest_s":0,"data_quality":"synthetic","legs":[{"mode":"WALK","start_time":"2026-10-16T07:00:00+07:00","end_time":"2026-10-16T07:10:00+07:00","duration_s":600,"from":{"name":"A","lat":-6.2,"lon":106.8},"to":{"name":"B","lat":-6.21,"lon":106.81},"mean_pm25":30.0,"dose_ug":4.0}]}],"comparison":null,"disclaimer":"test"}
''';
