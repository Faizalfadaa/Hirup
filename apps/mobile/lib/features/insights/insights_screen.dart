import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';
import '../route_planning/presentation/providers.dart';

class InsightsScreen extends ConsumerWidget {
  const InsightsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
      appBar: const HirupAppBar(
          section: 'INSIGHT KOTA',
          code: '03',
          automaticallyImplyLeading: false),
      body: ListView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 32),
          children: [
            const PageHeader(
                eyebrow: 'Gambaran kota',
                title: 'Udara di sekitar kita',
                subtitle:
                    'Ringkasan model per kelurahan, terpisah dari paparan pribadi saat perjalanan.'),
            const SizedBox(height: 22),
            const AirMapCard(),
            const SizedBox(height: 18),
            ref.watch(cityInsightsProvider).when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (error, _) => ErrorPanel(
                      message: error.toString(),
                      onRetry: () => ref.invalidate(cityInsightsProvider)),
                  data: (items) => items.isEmpty
                      ? Container(
                          padding: const EdgeInsets.all(18),
                          decoration: BoxDecoration(
                              color: AppColors.surfaceSky,
                              borderRadius: BorderRadius.circular(20)),
                          child: const Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(Icons.science_outlined,
                                    color: AppColors.sky700),
                                SizedBox(width: 12),
                                Expanded(
                                    child: Text(
                                        'Belum ada insight tervalidasi untuk periode ini. Peta ranking baru akan tampil setelah boundary GeoJSON tersedia.'))
                              ]))
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                              Text('Kelurahan prioritas',
                                  style:
                                      Theme.of(context).textTheme.titleMedium),
                              const SizedBox(height: 10),
                              ...items.map((item) => Card(
                                      child: ListTile(
                                    leading: CircleAvatar(
                                        backgroundColor: AppColors.brand100,
                                        child: Text(
                                            '${item.priorityRank ?? '—'}')),
                                    title: Text(item.name,
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w800)),
                                    subtitle: Text(item.kecamatan),
                                    trailing: Text(
                                        '${item.meanPm25.toStringAsFixed(1)}\nµg/m³',
                                        textAlign: TextAlign.right,
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w700)),
                                  ))),
                            ]),
                ),
          ]));
}
