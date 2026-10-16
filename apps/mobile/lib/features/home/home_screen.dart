import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/formatters.dart';
import '../../shared/widgets.dart';
import '../route_planning/domain/models.dart';
import '../route_planning/presentation/providers.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final demo = ref.watch(demoModeProvider);
    final air = ref.watch(airPointProvider);
    return Scaffold(
      body: Column(children: [
        if (demo) const DemoBanner(),
        Expanded(child: CustomScrollView(slivers: [
          SliverAppBar(
            pinned: true,
            title: GestureDetector(
              onLongPress: () => ref.read(demoModeProvider.notifier).state = !demo,
              child: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('hirup.', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: AppColors.brand900)), Text('Jakarta · Area pilot', style: TextStyle(fontSize: 11, color: AppColors.ink600))]),
            ),
            actions: [IconButton(tooltip: 'Profil', onPressed: () => context.go('/profile'), icon: const Icon(Icons.person_outline))],
          ),
          SliverPadding(padding: const EdgeInsets.fromLTRB(20, 12, 20, 32), sliver: SliverList.list(children: [
            const PageHeader(eyebrow: 'Perjalanan baru', title: 'Ke mana hari ini?', subtitle: 'Cari jalan yang pas untuk waktu dan napasmu.'),
            const SizedBox(height: 22),
            _JourneyCard(draft: draft),
            const SizedBox(height: 18),
            Stack(clipBehavior: Clip.none, children: [
              const AirMapCard(),
              Positioned(left: 14, right: 14, bottom: -50, child: _AirSummary(air: air)),
            ]),
            const SizedBox(height: 70),
            Text('Akses cepat', style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 8, children: [
              ActionChip(avatar: const Icon(Icons.business_outlined, size: 18), label: const Text('Dukuh Atas'), onPressed: () => ref.read(journeyDraftProvider.notifier).setDestination(pilotPlaces[2])),
              ActionChip(avatar: const Icon(Icons.train_outlined, size: 18), label: const Text('Blok M'), onPressed: () => ref.read(journeyDraftProvider.notifier).setDestination(pilotPlaces[3])),
              ActionChip(avatar: const Icon(Icons.park_outlined, size: 18), label: const Text('Monas'), onPressed: () => ref.read(journeyDraftProvider.notifier).setDestination(pilotPlaces[4])),
            ]),
          ])),
        ])),
      ]),
    );
  }
}

class _JourneyCard extends ConsumerWidget {
  const _JourneyCard({required this.draft});
  final JourneyDraft draft;
  @override Widget build(BuildContext context, WidgetRef ref) => Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
        DropdownButtonFormField<PlacePoint>(
          value: draft.origin, decoration: const InputDecoration(labelText: 'Asal', prefixIcon: Icon(Icons.trip_origin)),
          items: pilotPlaces.map((p) => DropdownMenuItem(value: p, child: Text(p.name))).toList(), onChanged: (p) { if (p != null) ref.read(journeyDraftProvider.notifier).setOrigin(p); },
        ),
        Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Row(children: [const Expanded(child: Divider()), IconButton(tooltip: 'Tukar asal dan tujuan', onPressed: ref.read(journeyDraftProvider.notifier).swap, icon: const Icon(Icons.swap_vert)), const Expanded(child: Divider())])),
        DropdownButtonFormField<PlacePoint>(
          value: draft.destination, decoration: const InputDecoration(labelText: 'Tujuan', prefixIcon: Icon(Icons.location_on_outlined)),
          items: pilotPlaces.map((p) => DropdownMenuItem(value: p, child: Text(p.name))).toList(), onChanged: (p) { if (p != null) ref.read(journeyDraftProvider.notifier).setDestination(p); },
        ),
        const SizedBox(height: 12),
        Row(children: [const Icon(Icons.schedule, size: 20), const SizedBox(width: 8), Text('Berangkat ${formatTime(draft.departAt)}'), const Spacer(), TextButton(onPressed: () async {
          final picked = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(draft.departAt));
          if (picked != null) ref.read(journeyDraftProvider.notifier).setTime(DateTime(draft.departAt.year, draft.departAt.month, draft.departAt.day, picked.hour, picked.minute));
        }, child: const Text('Ubah'))]),
        const SizedBox(height: 8), SizedBox(width: double.infinity, child: FilledButton.icon(onPressed: draft.origin == draft.destination ? null : () => context.push('/plan/mode'), icon: const Icon(Icons.route), label: const Text('Cari rute'))),
      ])));
}

class _AirSummary extends StatelessWidget {
  const _AirSummary({required this.air});
  final AsyncValue<AirPoint> air;
  @override Widget build(BuildContext context) => Card(child: Padding(padding: const EdgeInsets.all(16), child: air.when(
        loading: () => const SizedBox(height: 56, child: Center(child: LinearProgressIndicator())),
        error: (_, __) => const Row(children: [Icon(Icons.info_outline), SizedBox(width: 10), Expanded(child: Text('Estimasi udara belum tersedia. Form rute tetap dapat digunakan.'))]),
        data: (value) => Row(children: [
          Container(width: 44, height: 44, decoration: const BoxDecoration(color: AppColors.brand100, shape: BoxShape.circle), child: const Icon(Icons.air, color: AppColors.brand600)), const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(value.category?.replaceAll('_', ' ') ?? 'Estimasi udara', style: const TextStyle(fontWeight: FontWeight.w800)), Text('${formatPm25(value.p50)} · rentang ${value.p10.toStringAsFixed(0)}–${value.p90.toStringAsFixed(0)}', style: const TextStyle(fontSize: 12, color: AppColors.ink600))])),
          QualityBadge(quality: value.quality),
        ]),
      )));
}
