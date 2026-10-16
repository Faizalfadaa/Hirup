import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../data/hirup_repository.dart';
import '../domain/models.dart';

final demoModeProvider = StateProvider<bool>((ref) => false);
final demoScenarioProvider = StateProvider<int>((ref) => 0);

final repositoryProvider = Provider<HirupRepository>((ref) {
  if (ref.watch(demoModeProvider))
    return DemoHirupRepository(scenario: ref.watch(demoScenarioProvider));
  return ApiHirupRepository();
});

class JourneyDraftNotifier extends Notifier<JourneyDraft> {
  @override
  JourneyDraft build() => JourneyDraft(
      origin: pilotPlaces.first,
      destination: pilotPlaces[2],
      departAt: DateTime.now());
  void setOrigin(PlacePoint point) => state = state.copyWith(origin: point);
  void setDestination(PlacePoint point) =>
      state = state.copyWith(destination: point);
  void swap() => state =
      state.copyWith(origin: state.destination, destination: state.origin);
  void setMode(PlanMode mode) => state = state.copyWith(mode: mode);
  void setSensitivity(Sensitivity value) =>
      state = state.copyWith(sensitivity: value);
  void setMaxWalk(int value) => state = state.copyWith(maxWalkM: value);
  void setIncludeComparison(bool value) =>
      state = state.copyWith(includeComparison: value);
  void setTime(DateTime value) => state = state.copyWith(departAt: value);
}

final journeyDraftProvider =
    NotifierProvider<JourneyDraftNotifier, JourneyDraft>(
        JourneyDraftNotifier.new);

class PlanNotifier extends AsyncNotifier<PlanResult?> {
  @override
  Future<PlanResult?> build() async => null;
  Future<void> load() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(() =>
        ref.read(repositoryProvider).plan(ref.read(journeyDraftProvider)));
  }
}

final planProvider =
    AsyncNotifierProvider<PlanNotifier, PlanResult?>(PlanNotifier.new);

final selectedRouteIdProvider = StateProvider<String?>((ref) => null);
final selectedRouteProvider = Provider<RouteOption?>((ref) {
  final result = ref.watch(planProvider).valueOrNull;
  final id = ref.watch(selectedRouteIdProvider);
  if (result == null || result.options.isEmpty) return null;
  return result.options.cast<RouteOption?>().firstWhere(
      (option) => option?.id == id,
      orElse: () => result.options.first);
});

final airPointProvider = FutureProvider<AirPoint>((ref) {
  final point = ref.watch(journeyDraftProvider.select((value) => value.origin));
  return ref.watch(repositoryProvider).airAt(point);
});

final departureAdviceProvider = FutureProvider<DepartureAdvice>((ref) => ref
    .watch(repositoryProvider)
    .departureAdvice(ref.watch(journeyDraftProvider)));

final cityInsightsProvider = FutureProvider<List<CityInsight>>((ref) {
  final now = DateTime.now();
  return ref
      .watch(repositoryProvider)
      .cityInsights(now.subtract(const Duration(days: 7)), now);
});

class SavedTrip {
  const SavedTrip(
      {required this.id,
      required this.routeLabel,
      required this.origin,
      required this.destination,
      required this.savedAt,
      required this.durationS,
      required this.doseUg,
      required this.isDemo});
  final String id;
  final String routeLabel;
  final String origin;
  final String destination;
  final DateTime savedAt;
  final int durationS;
  final double doseUg;
  final bool isDemo;
  Map<String, dynamic> toJson() => {
        'id': id,
        'routeLabel': routeLabel,
        'origin': origin,
        'destination': destination,
        'savedAt': savedAt.toIso8601String(),
        'durationS': durationS,
        'doseUg': doseUg,
        'isDemo': isDemo
      };
  factory SavedTrip.fromJson(Map<String, dynamic> json) => SavedTrip(
      id: json['id'] as String,
      routeLabel: json['routeLabel'] as String,
      origin: json['origin'] as String,
      destination: json['destination'] as String,
      savedAt: DateTime.parse(json['savedAt'] as String),
      durationS: json['durationS'] as int,
      doseUg: (json['doseUg'] as num).toDouble(),
      isDemo: json['isDemo'] as bool);
}

class HistoryNotifier extends Notifier<List<SavedTrip>> {
  @override
  List<SavedTrip> build() {
    Future<void>(() async {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList('saved_trips') ?? const [];
      state = raw
          .map((item) => SavedTrip.fromJson(
              Map<String, dynamic>.from(jsonDecode(item) as Map)))
          .toList();
    });
    return [];
  }

  void save(RouteOption option, JourneyDraft draft, {required bool isDemo}) {
    state = [
      SavedTrip(
          id: '${DateTime.now().microsecondsSinceEpoch}',
          routeLabel: option.labels.join(' · '),
          origin: draft.origin.name,
          destination: draft.destination.name,
          savedAt: DateTime.now(),
          durationS: option.durationS,
          doseUg: option.doseUg,
          isDemo: isDemo),
      ...state
    ];
    _persist();
  }

  void clear() {
    state = [];
    _persist();
  }

  Future<void> _persist() async =>
      (await SharedPreferences.getInstance()).setStringList('saved_trips',
          state.map((trip) => jsonEncode(trip.toJson())).toList());
}

final historyProvider =
    NotifierProvider<HistoryNotifier, List<SavedTrip>>(HistoryNotifier.new);

final onboardingCompleteProvider = FutureProvider<bool>((ref) async =>
    (await SharedPreferences.getInstance()).getBool('onboarding_complete') ??
    false);
Future<void> markOnboardingComplete() async =>
    (await SharedPreferences.getInstance())
        .setBool('onboarding_complete', true);
Future<void> clearLocalData() async =>
    (await SharedPreferences.getInstance()).clear();
