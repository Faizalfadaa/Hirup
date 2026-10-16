import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';

class PageHeader extends StatelessWidget {
  const PageHeader({super.key, required this.eyebrow, required this.title, required this.subtitle});
  final String eyebrow;
  final String title;
  final String subtitle;
  @override Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(eyebrow.toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: .8, fontWeight: FontWeight.w800, color: AppColors.brand600)),
        const SizedBox(height: 8), Text(title, style: Theme.of(context).textTheme.headlineMedium),
        const SizedBox(height: 8), Text(subtitle, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.ink600)),
      ]);
}

class DemoBanner extends StatelessWidget {
  const DemoBanner({super.key});
  @override Widget build(BuildContext context) => Container(
        width: double.infinity, padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9), color: AppColors.sun300,
        child: const SafeArea(bottom: false, child: Text('MODE DEMO · DATA SIMULASI', textAlign: TextAlign.center, style: TextStyle(fontSize: 11, letterSpacing: .7, fontWeight: FontWeight.w900, color: AppColors.ink900))),
      );
}

class QualityBadge extends StatelessWidget {
  const QualityBadge({super.key, required this.quality});
  final String quality;
  @override Widget build(BuildContext context) {
    final label = switch (quality) {'real' => 'Data model', 'approximated' => 'Data perkiraan', _ => 'Data simulasi'};
    final color = quality == 'synthetic' ? AppColors.sun300 : AppColors.brand100;
    return Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6), decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(999)), child: Text(label, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800)));
  }
}

class AirMapCard extends StatelessWidget {
  const AirMapCard({super.key, this.compact = false});
  final bool compact;
  @override Widget build(BuildContext context) => Semantics(
        label: 'Peta interaktif belum tersedia. Ilustrasi ini tidak menunjukkan rute sebenarnya.',
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: SizedBox(
            height: compact ? 150 : 310,
            width: double.infinity,
            child: CustomPaint(
              painter: _MapPainter(),
              child: Stack(children: [
                Positioned(bottom: 14, left: 14, right: 14, child: Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white.withOpacity(.94), borderRadius: BorderRadius.circular(14)), child: const Row(children: [Icon(Icons.map_outlined, size: 20), SizedBox(width: 8), Expanded(child: Text('Peta interaktif belum tersedia · ilustrasi area', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 12)))]))),
              ]),
            ),
          ),
        ),
      );
}

class _MapPainter extends CustomPainter {
  @override void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = AppColors.surfaceSky);
    final road = Paint()..color = Colors.white..strokeWidth = 8..style = PaintingStyle.stroke..strokeCap = StrokeCap.round;
    for (var i = 0; i < 5; i++) {
      final path = Path()..moveTo(-20, size.height * (.18 + i * .17));
      for (double x = 0; x <= size.width + 40; x += 30) {
        path.lineTo(x, size.height * (.18 + i * .17) + math.sin(x / 55 + i) * 24);
      }
      canvas.drawPath(path, road);
    }
    final route = Paint()..color = AppColors.brand600..strokeWidth = 6..style = PaintingStyle.stroke..strokeCap = StrokeCap.round;
    canvas.drawPath(Path()..moveTo(size.width * .14, size.height * .83)..cubicTo(size.width * .38, size.height * .72, size.width * .52, size.height * .35, size.width * .86, size.height * .18), route);
    for (final point in [Offset(size.width * .14, size.height * .83), Offset(size.width * .86, size.height * .18)]) {
      canvas.drawCircle(point, 9, Paint()..color = Colors.white); canvas.drawCircle(point, 6, Paint()..color = AppColors.brand900);
    }
  }
  @override bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class ErrorPanel extends StatelessWidget {
  const ErrorPanel({super.key, required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(20), decoration: BoxDecoration(color: AppColors.danger100, borderRadius: BorderRadius.circular(20)),
        child: Column(children: [const Icon(Icons.cloud_off_outlined, color: AppColors.danger700, size: 32), const SizedBox(height: 10), Text(message, textAlign: TextAlign.center), const SizedBox(height: 12), OutlinedButton.icon(onPressed: onRetry, icon: const Icon(Icons.refresh), label: const Text('Coba lagi'))]),
      );
}
