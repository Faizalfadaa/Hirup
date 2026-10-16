import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';
import '../route_planning/domain/models.dart';
import '../route_planning/presentation/providers.dart';

class InsightsScreen extends ConsumerWidget {
  const InsightsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final insights = ref.watch(cityInsightsProvider);
    final origin = ref.watch(journeyDraftProvider).origin;
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () => ref.refresh(cityInsightsProvider.future),
        child: CustomScrollView(slivers: [
          SliverToBoxAdapter(
              child: _InsightsHero(count: insights.valueOrNull?.length)),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 30),
            sliver: SliverList.list(children: [
              const _InsightSectionLabel(
                  title: 'PETA UDARA', tag: 'JAKARTA  ·  LIVE'),
              const SizedBox(height: 10),
              _CityMapFrame(origin: origin),
              const SizedBox(height: 22),
              insights.when(
                loading: () => const _InsightsLoading(),
                error: (error, _) => ErrorPanel(
                    message: error.toString(),
                    onRetry: () => ref.invalidate(cityInsightsProvider)),
                data: (items) => items.isEmpty
                    ? const _EmptyInsights()
                    : _PriorityBoard(items: items),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

class _InsightsHero extends StatelessWidget {
  const _InsightsHero({required this.count});
  final int? count;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
        child: SizedBox(
          height: 232,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset('assets/images/air-unhealthy.png',
                fit: BoxFit.cover,
                alignment: const Alignment(.25, .1),
                cacheWidth: 900,
                filterQuality: FilterQuality.low),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xF2073C3B),
                    Color(0xA808665D),
                    Color(0xF007302F),
                  ],
                ),
              ),
            ),
            Positioned(
              right: -18,
              top: 82,
              child: CustomPaint(
                  size: const Size(150, 95), painter: _AirGridPainter()),
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
                      const Row(children: [
                        Icon(Icons.location_city_rounded,
                            size: 14, color: AppColors.sun300),
                        SizedBox(width: 6),
                        Text('LAPORAN KOTA  ·  7 HARI',
                            style: TextStyle(
                                color: AppColors.sun300,
                                fontSize: 8,
                                letterSpacing: 1,
                                fontWeight: FontWeight.w900)),
                      ]),
                      const SizedBox(height: 6),
                      const Text('Baca napas kota.',
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
                              'Lihat area prioritas dari ringkasan model kualitas udara Jakarta.',
                              style: TextStyle(
                                  color: Colors.white.withValues(alpha: .7),
                                  fontSize: 9.5,
                                  height: 1.35)),
                        ),
                        const SizedBox(width: 12),
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 9, vertical: 7),
                          decoration: BoxDecoration(
                              color: Colors.white.withValues(alpha: .12),
                              borderRadius: BorderRadius.circular(10),
                              border: Border.all(color: Colors.white30)),
                          child: Column(children: [
                            Text(
                                count == null
                                    ? '··'
                                    : count.toString().padLeft(2, '0'),
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 14,
                                    height: 1,
                                    fontWeight: FontWeight.w900)),
                            const SizedBox(height: 3),
                            const Text('AREA',
                                style: TextStyle(
                                    color: AppColors.mint300,
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

class _AirGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = Colors.white.withValues(alpha: .14)
      ..strokeWidth = 1;
    for (var x = 0.0; x <= size.width; x += 22) {
      canvas.drawLine(Offset(x, 0), Offset(x - 34, size.height), line);
    }
    for (var y = 4.0; y <= size.height; y += 22) {
      canvas.drawLine(Offset.zero.translate(0, y), Offset(size.width, y), line);
    }
    final dot = Paint()..color = AppColors.sun300.withValues(alpha: .7);
    canvas.drawCircle(Offset(size.width * .48, size.height * .44), 4, dot);
    canvas.drawCircle(Offset(size.width * .78, size.height * .7), 3, dot);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _InsightSectionLabel extends StatelessWidget {
  const _InsightSectionLabel({required this.title, required this.tag});
  final String title;
  final String tag;

  @override
  Widget build(BuildContext context) => Row(children: [
        Text(title,
            style: const TextStyle(
                fontSize: 9, letterSpacing: .8, fontWeight: FontWeight.w900)),
        const SizedBox(width: 9),
        const Expanded(child: Divider()),
        const SizedBox(width: 9),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
          decoration: BoxDecoration(
              color: AppColors.brand100,
              borderRadius: BorderRadius.circular(99)),
          child: Text(tag,
              style: const TextStyle(
                  fontSize: 6.5,
                  letterSpacing: .55,
                  fontWeight: FontWeight.w900,
                  color: AppColors.brand800)),
        ),
      ]);
}

class _CityMapFrame extends StatelessWidget {
  const _CityMapFrame({required this.origin});
  final PlacePoint origin;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(7),
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(26),
                topRight: Radius.circular(9),
                bottomLeft: Radius.circular(9),
                bottomRight: Radius.circular(26)),
            border: Border.all(color: AppColors.ink900, width: 1.2),
            boxShadow: const [
              BoxShadow(color: Color(0x1C073C3B), offset: Offset(5, 6))
            ]),
        child: ClipRRect(
          borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(20),
              topRight: Radius.circular(5),
              bottomLeft: Radius.circular(5),
              bottomRight: Radius.circular(20)),
          child: AirMapCard(origin: origin),
        ),
      );
}

class _PriorityBoard extends StatelessWidget {
  const _PriorityBoard({required this.items});
  final List<CityInsight> items;

  @override
  Widget build(BuildContext context) {
    final maxPm = items.fold<double>(1,
        (current, item) => item.meanPm25 > current ? item.meanPm25 : current);
    final average = items.fold<double>(0, (sum, item) => sum + item.meanPm25) /
        items.length;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(
            child: _CityMetric(
                label: 'RATA-RATA',
                value: average.toStringAsFixed(1),
                unit: 'µg/m³',
                color: AppColors.sky300)),
        const SizedBox(width: 9),
        Expanded(
            child: _CityMetric(
                label: 'TERTINGGI',
                value: maxPm.toStringAsFixed(1),
                unit: 'µg/m³',
                color: AppColors.sun300)),
      ]),
      const SizedBox(height: 22),
      Container(
        padding: const EdgeInsets.fromLTRB(14, 15, 14, 7),
        decoration: BoxDecoration(
            color: AppColors.brand900,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(28),
                topRight: Radius.circular(10),
                bottomLeft: Radius.circular(10),
                bottomRight: Radius.circular(28)),
            border: Border.all(color: AppColors.ink900),
            boxShadow: const [
              BoxShadow(color: Color(0x26073C3B), offset: Offset(5, 6))
            ]),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Row(children: [
            Icon(Icons.flag_outlined, size: 18, color: AppColors.mint300),
            SizedBox(width: 8),
            Expanded(
                child: Text('KELURAHAN PRIORITAS',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 9,
                        letterSpacing: .8,
                        fontWeight: FontWeight.w900))),
            Text('PM2.5',
                style: TextStyle(
                    color: Colors.white54,
                    fontSize: 7,
                    letterSpacing: .6,
                    fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 12),
          ...items.asMap().entries.map((entry) =>
              _PriorityCard(item: entry.value, index: entry.key, maxPm: maxPm)),
        ]),
      ),
    ]);
  }
}

class _CityMetric extends StatelessWidget {
  const _CityMetric(
      {required this.label,
      required this.value,
      required this.unit,
      required this.color});
  final String label;
  final String value;
  final String unit;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(12, 11, 11, 11),
        decoration: BoxDecoration(
            color: color,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(7),
                bottomLeft: Radius.circular(7),
                bottomRight: Radius.circular(18)),
            border: Border.all(color: AppColors.ink900)),
        child: Row(children: [
          Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                Text(label,
                    style: const TextStyle(
                        fontSize: 7,
                        letterSpacing: .6,
                        fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                Text(unit,
                    style:
                        const TextStyle(fontSize: 8, color: AppColors.ink600)),
              ])),
          Text(value,
              style: const TextStyle(
                  fontSize: 18,
                  height: 1,
                  fontWeight: FontWeight.w900,
                  color: AppColors.ink900)),
        ]),
      );
}

class _PriorityCard extends StatelessWidget {
  const _PriorityCard(
      {required this.item, required this.index, required this.maxPm});
  final CityInsight item;
  final int index;
  final double maxPm;

  @override
  Widget build(BuildContext context) {
    final ratio = (item.meanPm25 / maxPm).clamp(.08, 1.0);
    final accent = item.meanPm25 > 55
        ? const Color(0xFFFF9B83)
        : item.meanPm25 > 15.5
            ? AppColors.sun300
            : AppColors.mint300;
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.fromLTRB(10, 10, 10, 9),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.only(
              topLeft: Radius.circular(index.isEven ? 16 : 7),
              topRight: Radius.circular(index.isEven ? 7 : 16),
              bottomLeft: const Radius.circular(7),
              bottomRight: const Radius.circular(16))),
      child: Row(children: [
        Container(
          width: 31,
          height: 31,
          alignment: Alignment.center,
          decoration: BoxDecoration(
              color: accent,
              borderRadius: BorderRadius.circular(9),
              border: Border.all(color: AppColors.ink900)),
          child: Text('${item.priorityRank ?? index + 1}',
              style:
                  const TextStyle(fontSize: 10, fontWeight: FontWeight.w900)),
        ),
        const SizedBox(width: 10),
        Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(item.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style:
                    const TextStyle(fontSize: 11, fontWeight: FontWeight.w900)),
            const SizedBox(height: 2),
            Text(item.kecamatan,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontSize: 8.5, color: AppColors.ink600)),
            const SizedBox(height: 6),
            LayoutBuilder(
              builder: (_, constraints) => Stack(children: [
                Container(
                    height: 4,
                    decoration: BoxDecoration(
                        color: AppColors.stroke,
                        borderRadius: BorderRadius.circular(99))),
                Container(
                    width: constraints.maxWidth * ratio,
                    height: 4,
                    decoration: BoxDecoration(
                        color: accent,
                        borderRadius: BorderRadius.circular(99))),
              ]),
            ),
          ]),
        ),
        const SizedBox(width: 10),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text(item.meanPm25.toStringAsFixed(1),
              style:
                  const TextStyle(fontSize: 13, fontWeight: FontWeight.w900)),
          const Text('µg/m³',
              style: TextStyle(fontSize: 7.5, color: AppColors.ink600)),
        ]),
      ]),
    );
  }
}

class _InsightsLoading extends StatelessWidget {
  const _InsightsLoading();

  @override
  Widget build(BuildContext context) => const Padding(
        padding: EdgeInsets.symmetric(vertical: 34),
        child: Center(
            child: CircularProgressIndicator(
                color: AppColors.brand600, strokeWidth: 2.5)),
      );
}

class _EmptyInsights extends StatelessWidget {
  const _EmptyInsights();

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
            color: AppColors.surfaceSky,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(22),
                topRight: Radius.circular(8),
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(22)),
            border: Border.all(color: AppColors.stroke)),
        child:
            const Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(Icons.science_outlined, size: 21, color: AppColors.sky700),
          SizedBox(width: 11),
          Expanded(
              child: Text(
                  'Belum ada insight tervalidasi untuk periode ini. Tarik layar ke bawah untuk memuat ulang.',
                  style: TextStyle(
                      fontSize: 10, height: 1.45, color: AppColors.ink700))),
        ]),
      );
}
