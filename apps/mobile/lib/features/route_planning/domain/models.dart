enum PlanMode { transit, bike, walk, all }

enum Sensitivity { umum, rentan }

/// The API rejects timestamps without an offset; UTC (`...Z`) is always explicit.
String apiTimestamp(DateTime value) => value.toUtc().toIso8601String();

class PlacePoint {
  const PlacePoint({required this.name, required this.lat, required this.lon});
  final String name;
  final double lat;
  final double lon;
  Map<String, dynamic> toCoordinatesJson() => {'lat': lat, 'lon': lon};
  factory PlacePoint.fromJson(Map<String, dynamic> json) => PlacePoint(
        name: json['name'] as String? ?? 'Titik',
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
      );
}

const pilotPlaces = <PlacePoint>[
  PlacePoint(name: 'MRT Lebak Bulus', lat: -6.2891, lon: 106.7745),
  PlacePoint(name: 'Bundaran HI', lat: -6.1938, lon: 106.8230),
  PlacePoint(name: 'Dukuh Atas', lat: -6.2008, lon: 106.8227),
  PlacePoint(name: 'Blok M', lat: -6.2444, lon: 106.7984),
  PlacePoint(name: 'Monas', lat: -6.1754, lon: 106.8272),
];

class JourneyDraft {
  const JourneyDraft({
    required this.origin,
    required this.destination,
    required this.departAt,
    this.mode = PlanMode.transit,
    this.sensitivity = Sensitivity.umum,
    this.maxWalkM = 1000,
    this.includeComparison = true,
  });
  final PlacePoint origin;
  final PlacePoint destination;
  final DateTime departAt;
  final PlanMode mode;
  final Sensitivity sensitivity;
  final int maxWalkM;
  final bool includeComparison;

  JourneyDraft copyWith(
          {PlacePoint? origin,
          PlacePoint? destination,
          DateTime? departAt,
          PlanMode? mode,
          Sensitivity? sensitivity,
          int? maxWalkM,
          bool? includeComparison}) =>
      JourneyDraft(
        origin: origin ?? this.origin,
        destination: destination ?? this.destination,
        departAt: departAt ?? this.departAt,
        mode: mode ?? this.mode,
        sensitivity: sensitivity ?? this.sensitivity,
        maxWalkM: maxWalkM ?? this.maxWalkM,
        includeComparison: includeComparison ?? this.includeComparison,
      );

  Map<String, dynamic> toPlanJson() => {
        'origin': origin.toCoordinatesJson(),
        'destination': destination.toCoordinatesJson(),
        'depart_at': apiTimestamp(departAt),
        'mode': mode.name,
        'profile': {'sensitivity': sensitivity.name, 'max_walk_m': maxWalkM},
        'include_comparison': includeComparison,
      };
}

class DataFreshness {
  const DataFreshness(
      {required this.validHour, this.modelVersion, required this.confidence});
  final DateTime validHour;
  final String? modelVersion;
  final String confidence;
  factory DataFreshness.fromJson(Map<String, dynamic> json) => DataFreshness(
        validHour: DateTime.parse(json['aq_valid_hour'] as String),
        modelVersion: json['model_version'] as String?,
        confidence: json['confidence'] as String,
      );
}

class TripLeg {
  const TripLeg(
      {required this.mode,
      required this.startTime,
      required this.endTime,
      required this.durationS,
      required this.from,
      required this.to,
      required this.meanPm25,
      required this.doseUg,
      this.routeName});
  final String mode;
  final DateTime startTime;
  final DateTime endTime;
  final int durationS;
  final PlacePoint from;
  final PlacePoint to;
  final double meanPm25;
  final double doseUg;
  final String? routeName;
  factory TripLeg.fromJson(Map<String, dynamic> json) {
    final route = json['route'] as Map<String, dynamic>?;
    return TripLeg(
      mode: json['mode'] as String,
      startTime: DateTime.parse(json['start_time'] as String),
      endTime: DateTime.parse(json['end_time'] as String),
      durationS: json['duration_s'] as int,
      from: PlacePoint.fromJson(json['from'] as Map<String, dynamic>),
      to: PlacePoint.fromJson(json['to'] as Map<String, dynamic>),
      meanPm25: (json['mean_pm25'] as num).toDouble(),
      doseUg: (json['dose_ug'] as num).toDouble(),
      routeName:
          route?['short_name'] as String? ?? route?['long_name'] as String?,
    );
  }
}

class RouteOption {
  const RouteOption(
      {required this.id,
      required this.labels,
      required this.departAt,
      required this.arriveAt,
      required this.durationS,
      required this.transfers,
      required this.distanceM,
      required this.doseUg,
      required this.doseP10,
      required this.doseP90,
      required this.deltaDosePct,
      required this.deltaDurationS,
      required this.dataQuality,
      required this.legs});
  final String id;
  final List<String> labels;
  final DateTime departAt;
  final DateTime arriveAt;
  final int durationS;
  final int transfers;
  final double distanceM;
  final double doseUg;
  final double doseP10;
  final double doseP90;
  final double deltaDosePct;
  final int deltaDurationS;
  final String dataQuality;
  final List<TripLeg> legs;
  factory RouteOption.fromJson(Map<String, dynamic> json) => RouteOption(
        id: json['option_id'] as String,
        labels: (json['labels'] as List).cast<String>(),
        departAt: DateTime.parse(json['depart_at'] as String),
        arriveAt: DateTime.parse(json['arrive_at'] as String),
        durationS: json['duration_s'] as int,
        transfers: json['transfers'] as int,
        distanceM: (json['distance_m'] as num).toDouble(),
        doseUg: (json['dose_ug'] as num).toDouble(),
        doseP10: (json['dose_ug_p10'] as num).toDouble(),
        doseP90: (json['dose_ug_p90'] as num).toDouble(),
        deltaDosePct: (json['delta_vs_fastest_pct'] as num).toDouble(),
        deltaDurationS: json['delta_duration_vs_fastest_s'] as int,
        dataQuality: json['data_quality'] as String,
        legs: (json['legs'] as List)
            .map((e) => TripLeg.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class VehicleComparison {
  const VehicleComparison(
      {required this.durationS,
      required this.doseUg,
      required this.doseP10,
      required this.doseP90,
      this.costIdr,
      this.co2Kg});
  final int durationS;
  final double doseUg;
  final double doseP10;
  final double doseP90;
  final int? costIdr;
  final double? co2Kg;
  factory VehicleComparison.fromJson(Map<String, dynamic> json) =>
      VehicleComparison(
        durationS: json['duration_s'] as int,
        doseUg: (json['dose_ug'] as num).toDouble(),
        doseP10: (json['dose_ug_p10'] as num).toDouble(),
        doseP90: (json['dose_ug_p90'] as num).toDouble(),
        costIdr: json['cost_idr'] as int?,
        co2Kg: (json['co2_kg'] as num?)?.toDouble(),
      );
}

class PlanResult {
  const PlanResult(
      {required this.requestId,
      required this.dataQuality,
      required this.freshness,
      required this.options,
      this.motorcycle,
      this.car,
      required this.disclaimer});
  final String requestId;
  final String dataQuality;
  final DataFreshness freshness;
  final List<RouteOption> options;
  final VehicleComparison? motorcycle;
  final VehicleComparison? car;
  final String disclaimer;
  bool get isDemo => dataQuality == 'synthetic';
  factory PlanResult.fromJson(Map<String, dynamic> json) {
    final comparison = json['comparison'] as Map<String, dynamic>?;
    return PlanResult(
      requestId: json['request_id'] as String,
      dataQuality: json['data_quality'] as String,
      freshness: DataFreshness.fromJson(
          json['data_freshness'] as Map<String, dynamic>),
      options: (json['options'] as List)
          .map((e) => RouteOption.fromJson(e as Map<String, dynamic>))
          .toList(),
      motorcycle: comparison?['motorcycle'] == null
          ? null
          : VehicleComparison.fromJson(
              comparison!['motorcycle'] as Map<String, dynamic>),
      car: comparison?['car'] == null
          ? null
          : VehicleComparison.fromJson(
              comparison!['car'] as Map<String, dynamic>),
      disclaimer: json['disclaimer'] as String,
    );
  }
}

class AirPoint {
  const AirPoint(
      {required this.validHour,
      required this.p10,
      required this.p50,
      required this.p90,
      required this.quality,
      this.category});
  final DateTime validHour;
  final double p10;
  final double p50;
  final double p90;
  final String quality;
  final String? category;
  factory AirPoint.fromJson(Map<String, dynamic> json) {
    final pm = json['pm25'] as Map<String, dynamic>;
    return AirPoint(
      validHour: DateTime.parse(json['valid_hour'] as String),
      p10: (pm['p10'] as num).toDouble(),
      p50: (pm['p50'] as num).toDouble(),
      p90: (pm['p90'] as num).toDouble(),
      quality: json['data_quality'] as String,
      category: json['ispu_category'] as String?,
    );
  }
}

class ApiProblem implements Exception {
  const ApiProblem(this.message, {this.requestId});
  final String message;
  final String? requestId;
  @override
  String toString() => message;
}

class DepartureSlot {
  const DepartureSlot(
      {required this.departAt,
      required this.durationS,
      required this.doseUg,
      required this.doseP10,
      required this.doseP90,
      required this.deltaDosePct,
      required this.deltaDurationS});
  final DateTime departAt;
  final int durationS;
  final double doseUg;
  final double doseP10;
  final double doseP90;
  final double deltaDosePct;
  final int deltaDurationS;
  factory DepartureSlot.fromJson(Map<String, dynamic> json) => DepartureSlot(
        departAt: DateTime.parse(json['depart_at'] as String),
        durationS: json['duration_s'] as int,
        doseUg: (json['dose_ug'] as num).toDouble(),
        doseP10: (json['dose_ug_p10'] as num).toDouble(),
        doseP90: (json['dose_ug_p90'] as num).toDouble(),
        deltaDosePct: (json['delta_dose_pct'] as num).toDouble(),
        deltaDurationS: json['delta_duration_s'] as int,
      );
}

class DepartureAdvice {
  const DepartureAdvice(
      {required this.slots, this.bestSlot, required this.dataQuality});
  final List<DepartureSlot> slots;
  final DateTime? bestSlot;
  final String dataQuality;
  factory DepartureAdvice.fromJson(Map<String, dynamic> json) =>
      DepartureAdvice(
        slots: (json['slots'] as List)
            .map((e) => DepartureSlot.fromJson(e as Map<String, dynamic>))
            .toList(),
        bestSlot: json['best_slot'] == null
            ? null
            : DateTime.parse(json['best_slot'] as String),
        dataQuality: json['data_quality'] as String,
      );
}

class CityInsight {
  const CityInsight(
      {required this.name,
      required this.kecamatan,
      required this.meanPm25,
      this.inequalityIndex,
      this.priorityRank});
  final String name;
  final String kecamatan;
  final double meanPm25;
  final double? inequalityIndex;
  final int? priorityRank;
  factory CityInsight.fromJson(Map<String, dynamic> json) => CityInsight(
      name: json['name'] as String,
      kecamatan: json['kecamatan'] as String,
      meanPm25: (json['mean_pm25'] as num).toDouble(),
      inequalityIndex: (json['inequality_index'] as num?)?.toDouble(),
      priorityRank: json['priority_rank'] as int?);
}
