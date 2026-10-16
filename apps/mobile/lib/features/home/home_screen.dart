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
            toolbarHeight: 68,
            titleSpacing: 14,
            title: _BrandMasthead(onLongPress: () => ref.read(demoModeProvider.notifier).state = !demo),
          ),
          SliverPadding(padding: const EdgeInsets.fromLTRB(20, 8, 20, 32), sliver: SliverList.list(children: [
            _HomeHero(air: air),
            const SizedBox(height: 16),
            _JourneyCard(draft: draft),
            const SizedBox(height: 20),
            const SizedBox(height: 22),
            Text('Pilih cara bergerak', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 16)), const SizedBox(height: 12),
            _ModeShortcuts(ref: ref),
            const SizedBox(height: 22),
            Row(children: [Expanded(child: Text('Area perjalanan', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontSize: 16))), TextButton.icon(onPressed: () {}, icon: const Icon(Icons.layers_outlined, size: 16), label: const Text('Lapisan'))]),
            const SizedBox(height: 6),
            AirMapCard(compact: true, origin: draft.origin, destination: draft.destination),
          ])),
        ])),
      ]),
    );
  }
}

class _BrandMasthead extends StatelessWidget {
  const _BrandMasthead({required this.onLongPress});
  final VoidCallback onLongPress;

  @override Widget build(BuildContext context) => GestureDetector(
    onLongPress: onLongPress,
    child: Container(
      height: 49,
      padding: const EdgeInsets.fromLTRB(6, 5, 9, 5),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: AppColors.ink900, width: 1.4),
        borderRadius: BorderRadius.circular(14),
        boxShadow: const [BoxShadow(color: AppColors.ink900, offset: Offset(2, 2))],
      ),
      child: Row(children: [
        Container(
          width: 37,
          height: 37,
          decoration: BoxDecoration(color: AppColors.brand900, borderRadius: BorderRadius.circular(10)),
          child: const CustomPaint(painter: _HirupLogoPainter()),
        ),
        const SizedBox(width: 9),
        const Expanded(child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text('hirup', style: TextStyle(fontSize: 18, height: 1, letterSpacing: -.5, fontWeight: FontWeight.w900, color: AppColors.ink900)),
            Text('.', style: TextStyle(fontSize: 18, height: 1, fontWeight: FontWeight.w900, color: AppColors.brand600)),
          ]),
          SizedBox(height: 2),
          Text('NAPAS LEGA · JAKARTA', maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 7, letterSpacing: .55, fontWeight: FontWeight.w800, color: AppColors.ink600)),
        ])),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 5),
          decoration: BoxDecoration(color: AppColors.sun300, border: Border.all(color: AppColors.ink900), borderRadius: BorderRadius.circular(9)),
          child: const Column(mainAxisSize: MainAxisSize.min, children: [
            Text('JKT', style: TextStyle(fontSize: 8, height: 1, letterSpacing: .7, fontWeight: FontWeight.w900, color: AppColors.ink900)),
            SizedBox(height: 2),
            Text('01', style: TextStyle(fontSize: 7, height: 1, fontWeight: FontWeight.w800, color: AppColors.ink700)),
          ]),
        ),
      ]),
    ),
  );
}

class _HirupLogoPainter extends CustomPainter {
  const _HirupLogoPainter();
  @override void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = AppColors.mint300
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.2
      ..strokeCap = StrokeCap.round;
    final first = Path()
      ..moveTo(size.width * .18, size.height * .35)
      ..cubicTo(size.width * .38, size.height * .18, size.width * .55, size.height * .52, size.width * .82, size.height * .27);
    final second = Path()
      ..moveTo(size.width * .18, size.height * .55)
      ..cubicTo(size.width * .42, size.height * .36, size.width * .57, size.height * .72, size.width * .82, size.height * .46);
    final third = Path()
      ..moveTo(size.width * .18, size.height * .73)
      ..cubicTo(size.width * .39, size.height * .59, size.width * .58, size.height * .86, size.width * .76, size.height * .67);
    canvas.drawPath(first, line);
    canvas.drawPath(second, line);
    canvas.drawPath(third, line);
    canvas.drawCircle(Offset(size.width * .8, size.height * .27), 4.2, Paint()..color = AppColors.sun300);
  }
  @override bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _HomeHero extends StatelessWidget {
  const _HomeHero({required this.air});
  final AsyncValue<AirPoint> air;

  @override Widget build(BuildContext context) => Container(
    constraints: const BoxConstraints(minHeight: 126),
    padding: const EdgeInsets.all(16),
    decoration: BoxDecoration(
      gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [AppColors.brand900, AppColors.brand600, Color(0xFF0B8073)]),
      borderRadius: BorderRadius.circular(20),
      boxShadow: [BoxShadow(color: AppColors.brand900.withValues(alpha: .13), blurRadius: 18, offset: const Offset(0, 8))],
    ),
    child: Row(children: [
      Expanded(child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('RUTE + UDARA', style: TextStyle(fontSize: 9, letterSpacing: 1, fontWeight: FontWeight.w900, color: AppColors.mint300)),
        const SizedBox(height: 7),
        const Text('Ke mana\nhari ini?', style: TextStyle(fontSize: 22, height: 1.05, fontWeight: FontWeight.w900, color: Colors.white)),
        const SizedBox(height: 7),
        Text('Bandingkan napas dan waktu.', style: TextStyle(fontSize: 11, color: Colors.white.withValues(alpha: .78))),
      ])),
      const SizedBox(width: 12),
      air.when(
        loading: () => const SizedBox(width: 82, child: Center(child: CircularProgressIndicator(color: AppColors.mint300, strokeWidth: 3))),
        error: (_, __) => Container(width: 82, height: 82, decoration: BoxDecoration(color: Colors.white.withValues(alpha: .1), shape: BoxShape.circle), child: const Icon(Icons.cloud_off_outlined, color: Colors.white)),
        data: (value) => Container(width: 88, height: 88, decoration: BoxDecoration(color: AppColors.sun300, shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3)), child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [Text(value.p50.toStringAsFixed(0), style: const TextStyle(fontSize: 25, height: 1, fontWeight: FontWeight.w900, color: AppColors.ink900)), const SizedBox(height: 3), const Text('µg/m³', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: AppColors.ink700)), const Text('ESTIMASI', style: TextStyle(fontSize: 7, letterSpacing: .5, fontWeight: FontWeight.w900, color: AppColors.brand800))])),
      ),
    ]),
  );
}

class _JourneyCard extends ConsumerWidget {
  const _JourneyCard({required this.draft});
  final JourneyDraft draft;
  @override Widget build(BuildContext context, WidgetRef ref) => Container(
    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24), border: Border.all(color: AppColors.ink900, width: 1.4), boxShadow: const [BoxShadow(color: Color(0x14073C3B), blurRadius: 0, offset: Offset(5, 5))]),
    child: Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(14, 11, 14, 9), child: Row(children: [
        Container(width: 28, height: 28, alignment: Alignment.center, decoration: BoxDecoration(color: AppColors.sun300, borderRadius: BorderRadius.circular(8)), child: const Text('A→B', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w900, color: AppColors.ink900))),
        const SizedBox(width: 8),
        const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('TIKET PERJALANAN', style: TextStyle(fontSize: 9, letterSpacing: .8, fontWeight: FontWeight.w900, color: AppColors.ink900)), Text('Atur titik perjalanan', style: TextStyle(fontSize: 10, color: AppColors.ink600))])),
        const Text('JKT', style: TextStyle(fontSize: 10, letterSpacing: 1.2, fontWeight: FontWeight.w900, color: AppColors.brand600)),
      ])),
      const _Perforation(),
      Padding(padding: const EdgeInsets.fromLTRB(13, 10, 13, 13), child: Column(children: [
        DropdownButtonFormField<PlacePoint>(
          key: ValueKey('origin-${draft.origin.name}'), initialValue: draft.origin, isDense: true, iconSize: 18, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.ink900), decoration: const InputDecoration(labelText: 'Asal', prefixIcon: Icon(Icons.trip_origin, size: 18), contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10)),
          items: pilotPlaces.map((p) => DropdownMenuItem(value: p, child: Text(p.name))).toList(), onChanged: (p) { if (p != null) ref.read(journeyDraftProvider.notifier).setOrigin(p); },
        ),
        SizedBox(height: 32, child: Row(children: [const Expanded(child: Divider()), IconButton(tooltip: 'Tukar asal dan tujuan', padding: EdgeInsets.zero, constraints: const BoxConstraints.tightFor(width: 34, height: 30), onPressed: ref.read(journeyDraftProvider.notifier).swap, icon: const Icon(Icons.swap_vert, size: 18)), const Expanded(child: Divider())])),
        DropdownButtonFormField<PlacePoint>(
          key: ValueKey('destination-${draft.destination.name}'), initialValue: draft.destination, isDense: true, iconSize: 18, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: AppColors.ink900), decoration: const InputDecoration(labelText: 'Tujuan', prefixIcon: Icon(Icons.location_on_outlined, size: 18), contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10)),
          items: pilotPlaces.map((p) => DropdownMenuItem(value: p, child: Text(p.name))).toList(), onChanged: (p) { if (p != null) ref.read(journeyDraftProvider.notifier).setDestination(p); },
        ),
        const SizedBox(height: 7),
        Row(children: [const Icon(Icons.schedule, size: 17), const SizedBox(width: 7), Text('Berangkat ${formatTime(draft.departAt)}', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700)), const Spacer(), TextButton(style: TextButton.styleFrom(minimumSize: const Size(42, 32), padding: const EdgeInsets.symmetric(horizontal: 8)), onPressed: () async {
          final picked = await showTimePicker(context: context, initialTime: TimeOfDay.fromDateTime(draft.departAt));
          if (picked != null) ref.read(journeyDraftProvider.notifier).setTime(DateTime(draft.departAt.year, draft.departAt.month, draft.departAt.day, picked.hour, picked.minute));
        }, child: const Text('Ubah'))]),
        const SizedBox(height: 4), SizedBox(width: double.infinity, height: 44, child: FilledButton(onPressed: draft.origin == draft.destination ? null : () => context.push('/plan/mode'), child: const Row(mainAxisAlignment: MainAxisAlignment.center, children: [Text('CARI RUTE', style: TextStyle(fontSize: 12, letterSpacing: .7, color: Colors.white)), SizedBox(width: 8), Icon(Icons.arrow_outward, size: 18, color: Colors.white)]))),
      ])),
    ]),
  );
}

class _ModeShortcuts extends StatelessWidget {
  const _ModeShortcuts({required this.ref});
  final WidgetRef ref;

  @override Widget build(BuildContext context) {
    const items = <(PlanMode, IconData, String, Color)>[
      (PlanMode.transit, Icons.directions_transit, 'Transit', AppColors.mint300),
      (PlanMode.bike, Icons.pedal_bike, 'Sepeda', AppColors.sky300),
      (PlanMode.walk, Icons.directions_walk, 'Jalan', AppColors.sun300),
      (PlanMode.all, Icons.grid_view_rounded, 'Semua', AppColors.brand100),
    ];
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: items.map((item) => Expanded(child: InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () { ref.read(journeyDraftProvider.notifier).setMode(item.$1); context.push('/plan/mode'); },
      child: Padding(padding: const EdgeInsets.symmetric(vertical: 3), child: Column(children: [
        Container(width: 48, height: 48, decoration: BoxDecoration(color: item.$4, borderRadius: BorderRadius.circular(14), border: Border.all(color: AppColors.ink900, width: 1.1)), child: Icon(item.$2, size: 23, color: AppColors.ink900)),
        const SizedBox(height: 6),
        Text(item.$3, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: AppColors.ink900)),
      ])),
    ))).toList());
  }
}

class _Perforation extends StatelessWidget {
  const _Perforation();
  @override Widget build(BuildContext context) => Row(children: [
    Transform.translate(offset: const Offset(-7, 0), child: Container(width: 14, height: 14, decoration: const BoxDecoration(color: AppColors.paper, shape: BoxShape.circle, border: Border.fromBorderSide(BorderSide(color: AppColors.ink900))))),
    Expanded(child: CustomPaint(size: const Size(double.infinity, 1), painter: _DashPainter())),
    Transform.translate(offset: const Offset(7, 0), child: Container(width: 14, height: 14, decoration: const BoxDecoration(color: AppColors.paper, shape: BoxShape.circle, border: Border.fromBorderSide(BorderSide(color: AppColors.ink900))))),
  ]);
}

class _DashPainter extends CustomPainter {
  @override void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = AppColors.stroke..strokeWidth = 1.4;
    for (double x = 0; x < size.width; x += 8) { canvas.drawLine(Offset(x, 0), Offset((x + 4).clamp(0, size.width).toDouble(), 0), paint); }
  }
  @override bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

