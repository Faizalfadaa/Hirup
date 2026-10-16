import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/formatters.dart';
import '../../shared/widgets.dart';
import '../route_planning/presentation/providers.dart';

class HistoryScreen extends ConsumerWidget {
  const HistoryScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final trips = ref.watch(historyProvider);
    return Scaffold(
        appBar: const HirupAppBar(
            section: 'RIWAYAT', code: '02', automaticallyImplyLeading: false),
        body: ListView(
            padding: const EdgeInsets.fromLTRB(20, 10, 20, 32),
            children: [
              const PageHeader(
                  eyebrow: 'Tersimpan di perangkat',
                  title: 'Perjalananmu',
                  subtitle:
                      'Lihat kembali pilihan perjalanan dan estimasi dosisnya.'),
              const SizedBox(height: 24),
              if (trips.isEmpty)
                Card(
                    child: Padding(
                        padding: const EdgeInsets.all(28),
                        child: Column(children: [
                          const Icon(Icons.route_outlined,
                              size: 44, color: AppColors.brand600),
                          const SizedBox(height: 14),
                          Text('Belum ada perjalanan',
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 6),
                          const Text(
                              'Simpan perjalanan setelah rute selesai untuk melihatnya di sini.',
                              textAlign: TextAlign.center)
                        ])))
              else
                ...trips.map((trip) => Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Card(
                        child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(children: [
                                    Expanded(
                                        child: Text(
                                            '${trip.origin} → ${trip.destination}',
                                            style: const TextStyle(
                                                fontWeight: FontWeight.w800))),
                                    if (trip.isDemo)
                                      const QualityBadge(quality: 'synthetic')
                                  ]),
                                  const SizedBox(height: 8),
                                  Text(
                                      '${formatDateTime(trip.savedAt)} · ${formatDuration(trip.durationS)}'),
                                  const SizedBox(height: 4),
                                  Text(
                                      'Estimasi dosis ${formatDose(trip.doseUg)}',
                                      style: const TextStyle(
                                          color: AppColors.ink600)),
                                ]))))),
            ]));
  }
}
