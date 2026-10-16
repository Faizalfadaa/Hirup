import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/services.dart';

import '../../../core/config/app_config.dart';
import '../domain/models.dart';

abstract interface class HirupRepository {
  Future<PlanResult> plan(JourneyDraft draft);
  Future<AirPoint> airAt(PlacePoint point);
  Future<DepartureAdvice> departureAdvice(JourneyDraft draft);
  Future<List<CityInsight>> cityInsights(DateTime from, DateTime to);
}

class ApiHirupRepository implements HirupRepository {
  ApiHirupRepository() : _dio = Dio(BaseOptions(baseUrl: AppConfig.apiBaseUrl, connectTimeout: AppConfig.requestTimeout, receiveTimeout: AppConfig.requestTimeout, headers: {'Accept': 'application/json'}));
  final Dio _dio;

  @override
  Future<PlanResult> plan(JourneyDraft draft) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>('/v1/routes/plan', data: draft.toPlanJson());
      return PlanResult.fromJson(response.data!);
    } on DioException catch (error) {
      throw _problem(error, 'Rute belum berhasil dimuat. Periksa koneksi lalu coba lagi.');
    }
  }

  @override
  Future<AirPoint> airAt(PlacePoint point) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/aq/point', queryParameters: {'lat': point.lat, 'lon': point.lon});
      return AirPoint.fromJson(response.data!);
    } on DioException catch (error) {
      throw _problem(error, 'Data udara sedang tidak tersedia.');
    }
  }

  @override
  Future<DepartureAdvice> departureAdvice(JourneyDraft draft) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/routes/departure-advice', queryParameters: {
        'origin_lat': draft.origin.lat, 'origin_lon': draft.origin.lon, 'destination_lat': draft.destination.lat, 'destination_lon': draft.destination.lon,
        'around': apiTimestamp(draft.departAt), 'mode': draft.mode.name, 'sensitivity': draft.sensitivity.name,
      });
      return DepartureAdvice.fromJson(response.data!);
    } on DioException catch (error) { throw _problem(error, 'Saran waktu belum tersedia.'); }
  }

  @override
  Future<List<CityInsight>> cityInsights(DateTime from, DateTime to) async {
    String date(DateTime value) => '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}';
    try {
      final response = await _dio.get<Map<String, dynamic>>('/v1/insights/kelurahan', queryParameters: {'from': date(from), 'to': date(to)});
      return (response.data!['items'] as List).map((e) => CityInsight.fromJson(e as Map<String, dynamic>)).toList();
    } on DioException catch (error) { throw _problem(error, 'Insight kota belum tersedia.'); }
  }

  ApiProblem _problem(DioException error, String fallback) {
    final body = error.response?.data;
    if (body is Map<String, dynamic>) {
      return ApiProblem(body['detail'] as String? ?? body['title'] as String? ?? fallback, requestId: body['request_id'] as String?);
    }
    return ApiProblem(fallback);
  }
}

class DemoHirupRepository implements HirupRepository {
  DemoHirupRepository({this.scenario = 0});
  final int scenario;

  Future<Map<String, dynamic>> _scenario() async {
    final raw = await rootBundle.loadString('assets/demo/scenarios.json');
    final list = jsonDecode(raw) as List<dynamic>;
    return list[scenario.clamp(0, list.length - 1).toInt()] as Map<String, dynamic>;
  }

  @override
  Future<PlanResult> plan(JourneyDraft draft) async => PlanResult.fromJson((await _scenario())['plan'] as Map<String, dynamic>);

  @override
  Future<AirPoint> airAt(PlacePoint point) async => AirPoint.fromJson((await _scenario())['air'] as Map<String, dynamic>);

  @override
  Future<DepartureAdvice> departureAdvice(JourneyDraft draft) async => const DepartureAdvice(slots: [], dataQuality: 'synthetic');

  @override
  Future<List<CityInsight>> cityInsights(DateTime from, DateTime to) async => const [];
}
