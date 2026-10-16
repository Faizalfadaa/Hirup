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
    final totalDuration =
        trips.fold<int>(0, (sum, trip) => sum + trip.durationS);
    final averageDose = trips.isEmpty
        ? 0.0
        : trips.fold<double>(0, (sum, trip) => sum + trip.doseUg) /
            trips.length;
    return Scaffold(
      body: CustomScrollView(slivers: [
        SliverToBoxAdapter(child: _HistoryHero(count: trips.length)),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 30),
          sliver: SliverList.list(children: [
            if (trips.isNotEmpty) ...[
              _HistorySummary(
                  totalDuration: totalDuration, averageDose: averageDose),
              const SizedBox(height: 24),
              const _HistorySectionLabel(),
              const SizedBox(height: 10),
              ...trips.asMap().entries.map((entry) => _HistoryTripCard(
                    trip: entry.value,
                    index: entry.key,
                    isLast: entry.key == trips.length - 1,
                  )),
            ] else
              const _EmptyHistory(),
          ]),
        ),
      ]),
    );
  }
}

class _HistoryHero extends StatelessWidget {
  const _HistoryHero({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
        child: SizedBox(
          height: 226,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset('assets/images/air-good.png',
                fit: BoxFit.cover,
                alignment: const Alignment(-.45, .2),
                cacheWidth: 900,
                filterQuality: FilterQuality.low),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xF2073C3B),
                    Color(0xA807695E),
                    Color(0xEE07302F),
                  ],
                ),
              ),
            ),
            Positioned(
              right: 20,
              bottom: 22,
              child: Opacity(
                opacity: .16,
                child: Transform.rotate(
                  angle: -.13,
                  child: const Icon(Icons.route_rounded,
                      size: 118, color: Colors.white),
                ),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Center(
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          HirupLogoMark(size: 27, dark: false),
                          SizedBox(width: 7),
                          Text('hirup.',
                              style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 18,
                                  height: 1,
                                  letterSpacing: -.45,
                                  fontWeight: FontWeight.w900)),
                        ]),
                      ),
                      const Spacer(),
                      const Text('ARSIP NAPAS  ·  LOKAL',
                          style: TextStyle(
                              color: AppColors.mint300,
                              fontSize: 8,
                              letterSpacing: 1,
                              fontWeight: FontWeight.w900)),
                      const SizedBox(height: 6),
                      const Text('Jejak perjalananmu.',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              height: 1,
                              letterSpacing: -.3,
                              fontWeight: FontWeight.w900)),
                      const SizedBox(height: 8),
                      Row(children: [
                        Expanded(
                          child: Text(
                              'Lihat lagi waktu tempuh dan estimasi paparan yang pernah disimpan.',
                              style: TextStyle(
                                  color: Colors.white.withValues(alpha: .7),
                                  fontSize: 9.5,
                                  height: 1.35)),
                        ),
                        const SizedBox(width: 14),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 10, vertical: 7),
                          decoration: BoxDecoration(
                              color: AppColors.sun300,
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: AppColors.ink900)),
                          child: Column(children: [
                            Text(count.toString().padLeft(2, '0'),
                                style: const TextStyle(
                                    fontSize: 15,
                                    height: 1,
                                    fontWeight: FontWeight.w900,
                                    color: AppColors.ink900)),
                            const SizedBox(height: 3),
                            const Text('TRIP',
                                style: TextStyle(
                                    fontSize: 6.5,
                                    letterSpacing: .7,
                                    fontWeight: FontWeight.w900)),
                          ]),
                        ),
                      ]),
                    ]),
              ),
            ),
          ]),
        ),
      );
}

class _HistorySummary extends StatelessWidget {
  const _HistorySummary(
      {required this.totalDuration, required this.averageDose});
  final int totalDuration;
  final double averageDose;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(vertical: 13),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(22),
                topRight: Radius.circular(8),
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(22)),
            border: Border.all(color: AppColors.ink900, width: 1.1),
            boxShadow: const [
              BoxShadow(color: Color(0x18073C3B), offset: Offset(4, 5))
            ]),
        child: Row(children: [
          Expanded(
              child: _SummaryMetric(
                  icon: Icons.schedule_rounded,
                  label: 'TOTAL WAKTU',
                  value: formatDuration(totalDuration))),
          Container(width: 1, height: 34, color: AppColors.stroke),
          Expanded(
              child: _SummaryMetric(
                  icon: Icons.air_rounded,
                  label: 'RATA-RATA DOSIS',
                  value: formatDose(averageDose))),
        ]),
      );
}

class _SummaryMetric extends StatelessWidget {
  const _SummaryMetric(
      {required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(children: [
          Container(
              width: 31,
              height: 31,
              decoration: BoxDecoration(
                  color: AppColors.surfaceMint,
                  borderRadius: BorderRadius.circular(9)),
              child: Icon(icon, size: 16, color: AppColors.brand600)),
          const SizedBox(width: 8),
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(label,
                    style: const TextStyle(
                        fontSize: 6.5,
                        letterSpacing: .55,
                        fontWeight: FontWeight.w900,
                        color: AppColors.ink600)),
                const SizedBox(height: 3),
                Text(value,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w900,
                        color: AppColors.ink900)),
              ])),
        ]),
      );
}

class _HistorySectionLabel extends StatelessWidget {
  const _HistorySectionLabel();

  @override
  Widget build(BuildContext context) => const Row(children: [
        Text('PERJALANAN TERSIMPAN',
            style: TextStyle(
                fontSize: 9, letterSpacing: .8, fontWeight: FontWeight.w900)),
        SizedBox(width: 9),
        Expanded(child: Divider()),
        SizedBox(width: 9),
        Icon(Icons.lock_outline_rounded, size: 14, color: AppColors.ink600),
      ]);
}

class _HistoryTripCard extends StatelessWidget {
  const _HistoryTripCard(
      {required this.trip, required this.index, required this.isLast});
  final SavedTrip trip;
  final int index;
  final bool isLast;

  @override
  Widget build(BuildContext context) => IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            width: 30,
            child: Column(children: [
              Container(
                width: 22,
                height: 22,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                    color: index == 0 ? AppColors.sun300 : AppColors.brand100,
                    shape: BoxShape.circle,
                    border: Border.all(color: AppColors.ink900)),
                child: Text('${index + 1}',
                    style: const TextStyle(
                        fontSize: 8, fontWeight: FontWeight.w900)),
              ),
              if (!isLast)
                Expanded(
                    child: Container(width: 1.5, color: AppColors.brand100)),
            ]),
          ),
          const SizedBox(width: 7),
          Expanded(
            child: Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.fromLTRB(13, 12, 12, 12),
              decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(18),
                      topRight: Radius.circular(7),
                      bottomLeft: Radius.circular(7),
                      bottomRight: Radius.circular(18)),
                  border: Border.all(color: AppColors.stroke)),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Expanded(
                        child: Text('${trip.origin}  →  ${trip.destination}',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontSize: 11.5,
                                height: 1.25,
                                fontWeight: FontWeight.w900)),
                      ),
                    ]),
                    const SizedBox(height: 6),
                    Text(formatDateTime(trip.savedAt),
                        style: const TextStyle(
                            fontSize: 8.5, color: AppColors.ink600)),
                    const SizedBox(height: 11),
                    Row(children: [
                      _TripFact(
                          icon: Icons.schedule_rounded,
                          value: formatDuration(trip.durationS)),
                      const SizedBox(width: 8),
                      _TripFact(
                          icon: Icons.air_rounded,
                          value: formatDose(trip.doseUg)),
                      const Spacer(),
                      Container(
                        width: 28,
                        height: 28,
                        decoration: const BoxDecoration(
                            color: AppColors.brand900, shape: BoxShape.circle),
                        child: const Icon(Icons.arrow_outward_rounded,
                            size: 14, color: AppColors.mint300),
                      ),
                    ]),
                  ]),
            ),
          ),
        ]),
      );
}

class _TripFact extends StatelessWidget {
  const _TripFact({required this.icon, required this.value});
  final IconData icon;
  final String value;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
            color: AppColors.surfaceSky,
            borderRadius: BorderRadius.circular(8)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 13, color: AppColors.brand600),
          const SizedBox(width: 5),
          Text(value,
              style:
                  const TextStyle(fontSize: 8.5, fontWeight: FontWeight.w800)),
        ]),
      );
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(24, 28, 24, 26),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(28),
                topRight: Radius.circular(10),
                bottomLeft: Radius.circular(10),
                bottomRight: Radius.circular(28)),
            border: Border.all(color: AppColors.ink900),
            boxShadow: const [
              BoxShadow(color: Color(0x18073C3B), offset: Offset(5, 6))
            ]),
        child: Column(children: [
          Container(
              width: 54,
              height: 54,
              decoration: BoxDecoration(
                  color: AppColors.surfaceMint,
                  borderRadius: BorderRadius.circular(17)),
              child: const Icon(Icons.route_outlined,
                  size: 27, color: AppColors.brand600)),
          const SizedBox(height: 13),
          const Text('Belum ada jejak perjalanan',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900)),
          const SizedBox(height: 6),
          const Text(
              'Selesaikan dan simpan perjalanan pertamamu. Ringkasannya akan muncul di sini.',
              textAlign: TextAlign.center,
              style: TextStyle(
                  fontSize: 10, height: 1.45, color: AppColors.ink600)),
        ]),
      );
}
