import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/widgets.dart';
import '../domain/models.dart';
import 'providers.dart';

class ModeScreen extends ConsumerWidget {
  const ModeScreen({super.key});
  static const data = <PlanMode, (IconData, String, String)>{
    PlanMode.transit: (Icons.directions_transit, 'Transit', 'MRT, LRT, TransJakarta'),
    PlanMode.bike: (Icons.pedal_bike, 'Sepeda', 'Jalur aktif yang tersedia'),
    PlanMode.walk: (Icons.directions_walk, 'Jalan kaki', 'Untuk perjalanan dekat'),
    PlanMode.all: (Icons.compare_arrows, 'Semua', 'Bandingkan semua opsi'),
  };
  @override Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Pilih mode')),
      body: SafeArea(child: Column(children: [
        Expanded(child: ListView(padding: const EdgeInsets.fromLTRB(20, 12, 20, 24), children: [
          _JourneyCapsule(draft: draft), const SizedBox(height: 26),
          const PageHeader(eyebrow: 'Langkah 2 dari 2', title: 'Mau perjalanan seperti apa?', subtitle: 'Pilih moda utama. Kendaraan pribadi tetap ditampilkan sebagai pembanding.'), const SizedBox(height: 20),
          GridView.count(shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), crossAxisCount: 2, mainAxisSpacing: 12, crossAxisSpacing: 12, childAspectRatio: .92, children: data.entries.toList().asMap().entries.map((indexed) {
            final tileIndex = indexed.key;
            final entry = indexed.value;
            final selected = draft.mode == entry.key;
            final accent = [AppColors.mint300, AppColors.sky300, AppColors.sun300, AppColors.brand100][tileIndex];
            return InkWell(borderRadius: BorderRadius.circular(20), onTap: () => ref.read(journeyDraftProvider.notifier).setMode(entry.key), child: AnimatedContainer(duration: const Duration(milliseconds: 180), padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: selected ? accent : Colors.white, borderRadius: BorderRadius.only(topLeft: const Radius.circular(24), topRight: Radius.circular(tileIndex.isEven ? 8 : 24), bottomLeft: Radius.circular(tileIndex.isEven ? 8 : 24), bottomRight: const Radius.circular(24)), border: Border.all(color: selected ? AppColors.ink900 : AppColors.stroke, width: selected ? 1.5 : 1), boxShadow: selected ? const [BoxShadow(color: Color(0x22073C3B), offset: Offset(4, 5))] : null), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [Text('0${tileIndex + 1}', style: const TextStyle(fontSize: 11, letterSpacing: .8, fontWeight: FontWeight.w900, color: AppColors.ink600)), const Spacer(), if (selected) const Icon(Icons.check_circle, color: AppColors.ink900)]), const SizedBox(height: 10), Icon(entry.value.$1, color: AppColors.brand800, size: 31), const Spacer(), Text(entry.value.$2, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16, color: AppColors.ink900)), const SizedBox(height: 3), Text(entry.value.$3, style: const TextStyle(fontSize: 12, color: AppColors.ink600)),
            ])));
          }).toList()),
          const SizedBox(height: 18), Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: AppColors.surfaceSky, borderRadius: BorderRadius.circular(18)), child: Row(children: [const Icon(Icons.tune, color: AppColors.sky700), const SizedBox(width: 12), Expanded(child: Text('Profil: ${draft.sensitivity == Sensitivity.rentan ? 'lebih sensitif' : 'umum'} · Maks. jalan 1 km'))])),
        ])),
        Container(padding: const EdgeInsets.fromLTRB(20, 12, 20, 12), decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: AppColors.stroke))), child: SizedBox(width: double.infinity, child: FilledButton(onPressed: () { ref.read(planProvider.notifier).load(); context.push('/plan/results'); }, child: const Text('Lihat pilihan rute')))),
      ])),
    );
  }
}

class ResultsScreen extends ConsumerWidget {
  const ResultsScreen({super.key});
  @override Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final state = ref.watch(planProvider);
    return Scaffold(appBar: AppBar(title: const Text('Pilihan rute')), body: state.when(
      loading: () => const _PlanningLoader(),
      error: (error, _) => ListView(padding: const EdgeInsets.all(20), children: [const SizedBox(height: 100), ErrorPanel(message: error.toString(), onRetry: ref.read(planProvider.notifier).load)]),
      data: (result) {
        if (result == null) return Center(child: FilledButton(onPressed: ref.read(planProvider.notifier).load, child: const Text('Muat pilihan rute')));
        return Column(children: [
          if (result.isDemo) const DemoBanner(),
          Expanded(child: ListView(padding: const EdgeInsets.fromLTRB(20, 12, 20, 36), children: [
            _JourneyCapsule(draft: draft), const SizedBox(height: 14), const AirMapCard(compact: true), const SizedBox(height: 24),
            const PageHeader(eyebrow: 'Hasil perjalanan', title: 'Pilih perjalanan yang paling pas.', subtitle: 'Bandingkan udara yang dihirup dan menit yang dibutuhkan.'), const SizedBox(height: 18),
            Row(children: [QualityBadge(quality: result.dataQuality), const SizedBox(width: 8), Text('${formatTime(result.freshness.validHour)} · ${result.freshness.confidence}', style: const TextStyle(fontSize: 12, color: AppColors.ink600))]), const SizedBox(height: 16),
            ...result.options.asMap().entries.map((entry) => Padding(padding: const EdgeInsets.only(bottom: 16), child: _RouteCard(index: entry.key + 1, option: entry.value, onTap: () { ref.read(selectedRouteIdProvider.notifier).state = entry.value.id; context.push('/plan/detail/${entry.value.id}'); }))),
            _ComparisonSection(motorcycle: result.motorcycle, car: result.car), const SizedBox(height: 18),
            Text(result.disclaimer, style: const TextStyle(fontSize: 12, color: AppColors.ink600)),
          ])),
        ]);
      },
    ));
  }
}

class _PlanningLoader extends StatelessWidget {
  const _PlanningLoader();
  @override Widget build(BuildContext context) => Center(child: Padding(padding: const EdgeInsets.all(32), child: Column(mainAxisSize: MainAxisSize.min, children: [const CircularProgressIndicator(), const SizedBox(height: 20), Text('Menyusun pilihan perjalanan…', style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 6), const Text('Biasanya selesai dalam beberapa detik.', style: TextStyle(color: AppColors.ink600))])));
}

class _JourneyCapsule extends StatelessWidget {
  const _JourneyCapsule({required this.draft});
  final JourneyDraft draft;
  @override Widget build(BuildContext context) => Container(padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: AppColors.stroke)), child: Row(children: [
    const Icon(Icons.trip_origin, size: 18, color: AppColors.brand600), const SizedBox(width: 8), Expanded(child: Text(draft.origin.name, overflow: TextOverflow.ellipsis)), const Padding(padding: EdgeInsets.symmetric(horizontal: 8), child: Icon(Icons.arrow_forward, size: 18)), const Icon(Icons.location_on, size: 18, color: AppColors.brand600), const SizedBox(width: 6), Expanded(child: Text(draft.destination.name, overflow: TextOverflow.ellipsis)),
  ]));
}

class _RouteCard extends StatelessWidget {
  const _RouteCard({required this.index, required this.option, required this.onTap});
  final int index;
  final RouteOption option;
  final VoidCallback onTap;
  String label(String raw) => switch (raw) {'fastest' => 'Tercepat', 'cleanest' => 'Terbersih', 'balanced' => 'Seimbang', _ => raw};
  @override Widget build(BuildContext context) {
    final reduction = option.deltaDosePct < 0 ? '${option.deltaDosePct.abs().round()}% lebih rendah' : 'Acuan tercepat';
    final accent = index == 1 ? AppColors.sun300 : index == 2 ? AppColors.mint300 : AppColors.sky300;
    return Semantics(button: true, label: '${option.labels.map(label).join(', ')}, ${formatDuration(option.durationS)}, estimasi dosis ${formatDose(option.doseUg)}, $reduction', child: Container(
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(22), border: Border.all(color: AppColors.ink900, width: 1.2), boxShadow: const [BoxShadow(color: Color(0x16073C3B), offset: Offset(4, 5))]),
      child: InkWell(borderRadius: BorderRadius.circular(22), onTap: onTap, child: Column(children: [
        Container(padding: const EdgeInsets.fromLTRB(16, 12, 12, 12), decoration: BoxDecoration(color: accent, borderRadius: const BorderRadius.vertical(top: Radius.circular(21))), child: Row(children: [
          Text('0$index', style: const TextStyle(fontSize: 30, height: 1, fontWeight: FontWeight.w900, color: AppColors.ink900)),
          const SizedBox(width: 12),
          Expanded(child: Wrap(spacing: 6, runSpacing: 6, children: option.labels.map((e) => Text(label(e).toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: .7, fontWeight: FontWeight.w900, color: AppColors.ink900))).toList())),
          const Icon(Icons.arrow_outward, color: AppColors.ink900),
        ])),
        Padding(padding: const EdgeInsets.all(17), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('WAKTU', style: TextStyle(fontSize: 10, letterSpacing: .8, fontWeight: FontWeight.w800, color: AppColors.ink600)), Text(formatDuration(option.durationS), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900, color: AppColors.ink900))])), Container(width: 1, height: 44, color: AppColors.stroke), const SizedBox(width: 16), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('ESTIMASI DOSIS', style: TextStyle(fontSize: 10, letterSpacing: .8, fontWeight: FontWeight.w800, color: AppColors.ink600)), Text(formatDose(option.doseUg), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: AppColors.brand600))]))]),
          const SizedBox(height: 13),
          Text('$reduction · ${option.deltaDurationS > 0 ? '+${formatDuration(option.deltaDurationS)}' : 'tanpa tambahan waktu'}', style: const TextStyle(fontWeight: FontWeight.w800, color: AppColors.ink900)),
          const SizedBox(height: 12), ClipRRect(borderRadius: BorderRadius.circular(8), child: LinearProgressIndicator(minHeight: 7, value: (option.doseUg / 35).clamp(0, 1).toDouble(), backgroundColor: AppColors.stroke, color: AppColors.brand600)),
          const SizedBox(height: 9), Text('Rentang ${formatDose(option.doseP10)}–${formatDose(option.doseP90)} · ${option.transfers} transit', style: const TextStyle(fontSize: 12, color: AppColors.ink600)),
        ])),
      ])),
    ));
  }
}

class _ComparisonSection extends StatelessWidget {
  const _ComparisonSection({this.motorcycle, this.car});
  final VehicleComparison? motorcycle;
  final VehicleComparison? car;
  @override Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    const SizedBox(height: 10), Text('Pembanding kendaraan pribadi', style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 10),
    Card(child: Column(children: [_VehicleRow(icon: Icons.two_wheeler, name: 'Motor', value: motorcycle), const Divider(height: 1), _VehicleRow(icon: Icons.directions_car_outlined, name: 'Mobil', value: car)])),
  ]);
}

class _VehicleRow extends StatelessWidget {
  const _VehicleRow({required this.icon, required this.name, required this.value});
  final IconData icon;
  final String name;
  final VehicleComparison? value;
  @override Widget build(BuildContext context) => Padding(padding: const EdgeInsets.all(16), child: Row(children: [Icon(icon, color: AppColors.ink600), const SizedBox(width: 12), Expanded(child: Text(name, style: const TextStyle(fontWeight: FontWeight.w700))), if (value == null) const Text('Tidak tersedia') else Column(crossAxisAlignment: CrossAxisAlignment.end, children: [Text('${formatDuration(value!.durationS)} · ${formatDose(value!.doseUg)}', style: const TextStyle(fontWeight: FontWeight.w700)), Text('Rentang ${value!.doseP10.toStringAsFixed(1)}–${value!.doseP90.toStringAsFixed(1)} µg', style: const TextStyle(fontSize: 11, color: AppColors.ink600))]) ]));
}

class DetailScreen extends ConsumerWidget {
  const DetailScreen({super.key, required this.optionId});
  final String optionId;
  @override Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(planProvider).valueOrNull;
    if (result == null) return const Scaffold(body: Center(child: Text('Rute tidak tersedia.')));
    final option = result.options.firstWhere((item) => item.id == optionId, orElse: () => result.options.first);
    return Scaffold(
      appBar: AppBar(title: const Text('Detail rute')),
      bottomNavigationBar: SafeArea(child: Container(padding: const EdgeInsets.all(16), decoration: const BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: AppColors.stroke))), child: FilledButton.icon(onPressed: () { ref.read(selectedRouteIdProvider.notifier).state = option.id; context.push('/trip/active'); }, icon: const Icon(Icons.navigation_outlined), label: const Text('Mulai perjalanan')))),
      body: Column(children: [if (result.isDemo) const DemoBanner(), Expanded(child: ListView(padding: const EdgeInsets.fromLTRB(20, 12, 20, 30), children: [
        const AirMapCard(compact: true), const SizedBox(height: 20),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [Expanded(child: Text(formatDuration(option.durationS), style: Theme.of(context).textTheme.headlineMedium)), Text(formatDose(option.doseUg), style: const TextStyle(fontSize: 25, fontWeight: FontWeight.w800, color: AppColors.brand600))]),
        const SizedBox(height: 5), Text('${formatTime(option.departAt)}–${formatTime(option.arriveAt)} · ${(option.distanceM / 1000).toStringAsFixed(1)} km · ${option.transfers} transit', style: const TextStyle(color: AppColors.ink600)), const SizedBox(height: 16),
        Container(padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: AppColors.surfaceMint, borderRadius: BorderRadius.circular(18)), child: Text('Estimasi dosis ${formatDose(option.doseUg)} dengan rentang ${formatDose(option.doseP10)} sampai ${formatDose(option.doseP90)}.', style: const TextStyle(fontWeight: FontWeight.w700))),
        const SizedBox(height: 24), Row(children: [Expanded(child: Text('Cerita perjalanan', style: Theme.of(context).textTheme.titleLarge)), TextButton(onPressed: () => context.push('/plan/departure'), child: const Text('Cek jam lain'))]), const SizedBox(height: 10),
        ...option.legs.asMap().entries.map((entry) => _LegTile(leg: entry.value, last: entry.key == option.legs.length - 1)),
      ]))]),
    );
  }
}

class _LegTile extends StatelessWidget {
  const _LegTile({required this.leg, required this.last});
  final TripLeg leg;
  final bool last;
  IconData get icon => switch (leg.mode) {'WALK' => Icons.directions_walk, 'BICYCLE' => Icons.pedal_bike, 'BUS' => Icons.directions_bus, 'SUBWAY' || 'RAIL' => Icons.train, 'WAIT' => Icons.schedule, _ => Icons.route};
  @override Widget build(BuildContext context) => IntrinsicHeight(child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
    SizedBox(width: 44, child: Column(children: [Container(width: 38, height: 38, decoration: const BoxDecoration(color: AppColors.brand100, shape: BoxShape.circle), child: Icon(icon, size: 20, color: AppColors.brand600)), if (!last) Expanded(child: Container(width: 2, color: AppColors.stroke))])),
    const SizedBox(width: 10), Expanded(child: Padding(padding: const EdgeInsets.only(bottom: 22), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('${leg.routeName ?? _modeLabel(leg.mode)} · ${formatDuration(leg.durationS)}', style: const TextStyle(fontWeight: FontWeight.w800)), const SizedBox(height: 4), Text('${leg.from.name} → ${leg.to.name}', style: const TextStyle(color: AppColors.ink600)), const SizedBox(height: 6), Text('Estimasi ${formatDose(leg.doseUg)} · PM2.5 ${formatPm25(leg.meanPm25)}', style: const TextStyle(fontSize: 12, color: AppColors.brand800))]))),
  ]));
  String _modeLabel(String value) => switch (value) {'WALK' => 'Jalan kaki', 'WAIT' => 'Menunggu', 'BICYCLE' => 'Sepeda', 'BUS' => 'Bus', 'SUBWAY' => 'MRT', 'RAIL' => 'Kereta', _ => value};
}

class DepartureScreen extends ConsumerWidget {
  const DepartureScreen({super.key});
  @override Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final advice = ref.watch(departureAdviceProvider);
    return Scaffold(appBar: AppBar(title: const Text('Saran jam berangkat')), body: ListView(padding: const EdgeInsets.all(20), children: [
      const PageHeader(eyebrow: 'Fitur tahap berikutnya', title: 'Geser waktu, lihat bedanya.', subtitle: 'Saran akan memakai slot 15 menit dari endpoint departure-advice tanpa menebak dosis di perangkat.'), const SizedBox(height: 24),
      advice.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => ErrorPanel(message: error.toString(), onRetry: () => ref.invalidate(departureAdviceProvider)),
        data: (value) => value.slots.isEmpty
          ? Container(padding: const EdgeInsets.all(22), decoration: BoxDecoration(color: AppColors.surfaceSky, borderRadius: BorderRadius.circular(24)), child: Column(children: [const Icon(Icons.schedule_outlined, size: 48, color: AppColors.sky700), const SizedBox(height: 12), Text('Waktu saat ini ${formatTime(draft.departAt)}', style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 8), const Text('Belum ada slot valid untuk skenario ini.', textAlign: TextAlign.center)]))
          : Column(children: value.slots.map((slot) {
              final best = value.bestSlot != null && slot.departAt.isAtSameMomentAs(value.bestSlot!);
              return Padding(padding: const EdgeInsets.only(bottom: 10), child: Card(child: ListTile(
                leading: CircleAvatar(backgroundColor: best ? AppColors.mint300 : AppColors.surfaceSky, child: Icon(best ? Icons.star : Icons.schedule, color: AppColors.brand800)),
                title: Text(formatTime(slot.departAt), style: const TextStyle(fontWeight: FontWeight.w800)),
                subtitle: Text('${formatDuration(slot.durationS)} · rentang ${slot.doseP10.toStringAsFixed(1)}–${slot.doseP90.toStringAsFixed(1)} µg'),
                trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [Text(formatDose(slot.doseUg), style: const TextStyle(fontWeight: FontWeight.w800)), Text('${slot.deltaDosePct > 0 ? '+' : ''}${slot.deltaDosePct.toStringAsFixed(0)}%', style: TextStyle(fontSize: 12, color: slot.deltaDosePct <= 0 ? AppColors.brand600 : AppColors.ink600))]),
                onTap: () { ref.read(journeyDraftProvider.notifier).setTime(slot.departAt); ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Waktu ${formatTime(slot.departAt)} diterapkan.'))); },
              )));
            }).toList()),
      ),
    ]));
  }
}

class ActiveTripScreen extends ConsumerStatefulWidget {
  const ActiveTripScreen({super.key});
  @override ConsumerState<ActiveTripScreen> createState() => _ActiveTripScreenState();
}

class _ActiveTripScreenState extends ConsumerState<ActiveTripScreen> {
  int currentLeg = 0;
  @override Widget build(BuildContext context) {
    final option = ref.watch(selectedRouteProvider);
    final result = ref.watch(planProvider).valueOrNull;
    if (option == null || result == null) return const Scaffold(body: Center(child: Text('Pilih rute terlebih dahulu.')));
    final legIndex = currentLeg >= option.legs.length ? option.legs.length - 1 : currentLeg;
    final leg = option.legs[legIndex];
    return Scaffold(body: SafeArea(child: Column(children: [
      if (result.isDemo) const DemoBanner(),
      Padding(padding: const EdgeInsets.all(12), child: Row(children: [IconButton(onPressed: () => context.pop(), icon: const Icon(Icons.close)), const Expanded(child: Text('Perjalanan aktif', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.w800))), const SizedBox(width: 48)])),
      const Expanded(child: Padding(padding: EdgeInsets.symmetric(horizontal: 16), child: AirMapCard())),
      Container(width: double.infinity, padding: const EdgeInsets.fromLTRB(20, 22, 20, 16), decoration: const BoxDecoration(color: Colors.white, borderRadius: BorderRadius.vertical(top: Radius.circular(28))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Langkah ${currentLeg + 1} dari ${option.legs.length}', style: const TextStyle(fontSize: 11, color: AppColors.brand600, fontWeight: FontWeight.w800)), const SizedBox(height: 7), Text('${leg.from.name} → ${leg.to.name}', style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8), Text('${formatDuration(leg.durationS)} · estimasi ${formatDose(leg.doseUg)}', style: const TextStyle(color: AppColors.ink600)), const SizedBox(height: 18),
        SizedBox(width: double.infinity, child: FilledButton(onPressed: () {
          if (currentLeg < option.legs.length - 1) { setState(() => currentLeg++); return; }
          ref.read(historyProvider.notifier).save(option, ref.read(journeyDraftProvider), isDemo: result.isDemo);
          showDialog<void>(context: context, builder: (dialogContext) => AlertDialog(title: const Text('Perjalanan disimpan'), content: const Text('Ringkasan tersimpan lokal di perangkat.'), actions: [FilledButton(onPressed: () { Navigator.pop(dialogContext); context.go('/history'); }, child: const Text('Lihat riwayat'))]));
        }, child: Text(currentLeg < option.legs.length - 1 ? 'Langkah berikutnya' : 'Selesaikan & simpan'))),
      ])),
    ])));
  }
}
