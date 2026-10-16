import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';

class PageHeader extends StatelessWidget {
  const PageHeader(
      {super.key,
      required this.eyebrow,
      required this.title,
      required this.subtitle});
  final String eyebrow;
  final String title;
  final String subtitle;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(eyebrow.toUpperCase(),
            style: const TextStyle(
                fontSize: 11,
                letterSpacing: .8,
                fontWeight: FontWeight.w800,
                color: AppColors.brand600)),
        const SizedBox(height: 8),
        Text(title,
            style: Theme.of(context)
                .textTheme
                .headlineMedium
                ?.copyWith(color: AppColors.ink900)),
        const SizedBox(height: 8),
        Text(subtitle,
            style: Theme.of(context)
                .textTheme
                .bodyMedium
                ?.copyWith(color: AppColors.ink600)),
      ]);
}

class DemoBanner extends StatelessWidget {
  const DemoBanner({super.key});
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
        color: AppColors.sun300,
        child: const SafeArea(
            bottom: false,
            child: Text('MODE DEMO · DATA SIMULASI',
                textAlign: TextAlign.center,
                style: TextStyle(
                    fontSize: 11,
                    letterSpacing: .7,
                    fontWeight: FontWeight.w900,
                    color: AppColors.ink900))),
      );
}

class QualityBadge extends StatelessWidget {
  const QualityBadge({super.key, required this.quality});
  final String quality;
  @override
  Widget build(BuildContext context) {
    final label = switch (quality) {
      'real' => 'Data model',
      'approximated' => 'Data perkiraan',
      _ => 'Data simulasi'
    };
    final color =
        quality == 'synthetic' ? AppColors.sun300 : AppColors.brand100;
    return Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
            color: color, borderRadius: BorderRadius.circular(999)),
        child: Text(label,
            style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800)));
  }
}

class HirupAppBar extends StatelessWidget implements PreferredSizeWidget {
  const HirupAppBar(
      {super.key,
      required this.section,
      required this.code,
      this.automaticallyImplyLeading = true});
  final String section;
  final String code;
  final bool automaticallyImplyLeading;

  @override
  Size get preferredSize => const Size.fromHeight(76);

  @override
  Widget build(BuildContext context) => AppBar(
        toolbarHeight: 76,
        titleSpacing: automaticallyImplyLeading ? 2 : 14,
        centerTitle: true,
        automaticallyImplyLeading: automaticallyImplyLeading,
        title: HirupBrandHeader(section: section, code: code),
      );
}

class HirupBrandHeader extends StatelessWidget {
  const HirupBrandHeader(
      {super.key, required this.section, required this.code, this.onLongPress});
  final String section;
  final String code;
  final VoidCallback? onLongPress;

  @override
  Widget build(BuildContext context) => GestureDetector(
        onLongPress: onLongPress,
        child: Container(
          height: 60,
          width: double.infinity,
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppColors.brand900, width: 1.2),
            boxShadow: const [
              BoxShadow(
                  color: Color(0x24073C3B),
                  blurRadius: 10,
                  offset: Offset(0, 4))
            ],
          ),
          child: Stack(fit: StackFit.expand, children: [
            Image.asset('assets/images/air-moderate.png',
                fit: BoxFit.cover,
                alignment: const Alignment(0, .28),
                cacheWidth: 720,
                filterQuality: FilterQuality.low),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.centerLeft,
                  end: Alignment.centerRight,
                  colors: [
                    Color(0xF2073C3B),
                    Color(0xD9076259),
                    Color(0xE8073C3B),
                  ],
                ),
              ),
            ),
            Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Row(mainAxisSize: MainAxisSize.min, children: [
                  HirupLogoMark(size: 26, dark: false),
                  SizedBox(width: 7),
                  Text('hirup.',
                      style: TextStyle(
                          fontSize: 18,
                          height: 1,
                          letterSpacing: -.45,
                          fontWeight: FontWeight.w900,
                          color: Colors.white)),
                ]),
                const SizedBox(height: 5),
                Text('$section  ·  JAKARTA  ·  $code',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                        fontSize: 7.5,
                        letterSpacing: .75,
                        fontWeight: FontWeight.w800,
                        color: Colors.white.withValues(alpha: .76))),
              ]),
            ),
          ]),
        ),
      );
}

// ignore: unused_element
class _LegacyHirupBrandHeader extends StatelessWidget {
  const _LegacyHirupBrandHeader({required this.section, required this.code});
  final String section;
  final String code;

  @override
  Widget build(BuildContext context) => GestureDetector(
        onLongPress: null,
        child: Container(
          height: 49,
          padding: const EdgeInsets.fromLTRB(6, 5, 9, 5),
          decoration: BoxDecoration(
            color: Colors.white,
            border: Border.all(color: AppColors.ink900, width: 1.4),
            borderRadius: BorderRadius.circular(14),
            boxShadow: const [
              BoxShadow(color: AppColors.ink900, offset: Offset(2, 2))
            ],
          ),
          child: Row(children: [
            Container(
              width: 37,
              height: 37,
              decoration: BoxDecoration(
                  color: AppColors.brand900,
                  borderRadius: BorderRadius.circular(10)),
              child: const CustomPaint(painter: _HirupLogoPainter()),
            ),
            const SizedBox(width: 9),
            Expanded(
                child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  const Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('hirup',
                            style: TextStyle(
                                fontSize: 18,
                                height: 1,
                                letterSpacing: -.5,
                                fontWeight: FontWeight.w900,
                                color: AppColors.ink900)),
                        Text('.',
                            style: TextStyle(
                                fontSize: 18,
                                height: 1,
                                fontWeight: FontWeight.w900,
                                color: AppColors.brand600)),
                      ]),
                  const SizedBox(height: 2),
                  Text('$section · JAKARTA',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 7,
                          letterSpacing: .55,
                          fontWeight: FontWeight.w800,
                          color: AppColors.ink600)),
                ])),
            const SizedBox(width: 8),
            Container(
              constraints: const BoxConstraints(minWidth: 35),
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 5),
              decoration: BoxDecoration(
                  color: AppColors.sun300,
                  border: Border.all(color: AppColors.ink900),
                  borderRadius: BorderRadius.circular(9)),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Text('JKT',
                    style: TextStyle(
                        fontSize: 8,
                        height: 1,
                        letterSpacing: .7,
                        fontWeight: FontWeight.w900,
                        color: AppColors.ink900)),
                const SizedBox(height: 2),
                Text(code,
                    style: const TextStyle(
                        fontSize: 7,
                        height: 1,
                        fontWeight: FontWeight.w800,
                        color: AppColors.ink700)),
              ]),
            ),
          ]),
        ),
      );
}

class HirupLogoMark extends StatelessWidget {
  const HirupLogoMark({super.key, this.size = 32, this.dark = true});
  final double size;
  final bool dark;

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color:
              dark ? AppColors.brand900 : Colors.white.withValues(alpha: .16),
          borderRadius: BorderRadius.circular(size * .28),
          border: dark
              ? null
              : Border.all(color: Colors.white.withValues(alpha: .38)),
        ),
        child: const CustomPaint(painter: _HirupLogoPainter()),
      );
}

class _HirupLogoPainter extends CustomPainter {
  const _HirupLogoPainter();
  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = AppColors.mint300
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.2
      ..strokeCap = StrokeCap.round;
    final first = Path()
      ..moveTo(size.width * .18, size.height * .35)
      ..cubicTo(size.width * .38, size.height * .18, size.width * .55,
          size.height * .52, size.width * .82, size.height * .27);
    final second = Path()
      ..moveTo(size.width * .18, size.height * .55)
      ..cubicTo(size.width * .42, size.height * .36, size.width * .57,
          size.height * .72, size.width * .82, size.height * .46);
    final third = Path()
      ..moveTo(size.width * .18, size.height * .73)
      ..cubicTo(size.width * .39, size.height * .59, size.width * .58,
          size.height * .86, size.width * .76, size.height * .67);
    canvas.drawPath(first, line);
    canvas.drawPath(second, line);
    canvas.drawPath(third, line);
    canvas.drawCircle(Offset(size.width * .8, size.height * .27), 4.2,
        Paint()..color = AppColors.sun300);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class AirMapCard extends StatelessWidget {
  const AirMapCard({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => Semantics(
        label:
            'Peta interaktif belum tersedia. Ilustrasi ini tidak menunjukkan rute sebenarnya.',
        child: ClipRRect(
          borderRadius: BorderRadius.circular(24),
          child: SizedBox(
            height: compact ? 150 : 310,
            width: double.infinity,
            child: CustomPaint(
              painter: _MapPainter(),
              child: Stack(children: [
                Positioned(
                    top: 13,
                    left: 13,
                    child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                            color: AppColors.ink900,
                            borderRadius: BorderRadius.circular(8)),
                        child: const Text('JKT / AIR GRID 01',
                            style: TextStyle(
                                fontSize: 9,
                                letterSpacing: .8,
                                fontWeight: FontWeight.w900,
                                color: AppColors.mint300)))),
                Positioned(
                    top: 14,
                    right: 14,
                    child: Container(
                        width: 36,
                        height: 36,
                        decoration: BoxDecoration(
                            color: AppColors.sun300,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: AppColors.ink900)),
                        child: const Icon(Icons.my_location,
                            size: 18, color: AppColors.ink900))),
                Positioned(
                    bottom: 14,
                    left: 14,
                    right: 14,
                    child: Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: .94),
                            borderRadius: BorderRadius.circular(14)),
                        child: const Row(children: [
                          Icon(Icons.map_outlined, size: 20),
                          SizedBox(width: 8),
                          Expanded(
                              child: Text(
                                  'Peta interaktif belum tersedia · ilustrasi area',
                                  style: TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 12,
                                      color: AppColors.ink900)))
                        ]))),
              ]),
            ),
          ),
        ),
      );
}

class _MapPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = AppColors.surfaceSky);
    final block = Paint()..color = const Color(0xFFDDEAE5);
    final blocks = <RRect>[
      RRect.fromRectAndRadius(
          Rect.fromLTWH(size.width * .05, size.height * .16, size.width * .22,
              size.height * .2),
          const Radius.circular(12)),
      RRect.fromRectAndRadius(
          Rect.fromLTWH(size.width * .64, size.height * .1, size.width * .29,
              size.height * .22),
          const Radius.circular(14)),
      RRect.fromRectAndRadius(
          Rect.fromLTWH(size.width * .1, size.height * .55, size.width * .26,
              size.height * .27),
          const Radius.circular(15)),
      RRect.fromRectAndRadius(
          Rect.fromLTWH(size.width * .69, size.height * .56, size.width * .25,
              size.height * .25),
          const Radius.circular(12)),
    ];
    for (final shape in blocks) {
      canvas.drawRRect(shape, block);
    }
    final airflow = Paint()
      ..color = Colors.white
      ..strokeWidth = 7
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < 4; i++) {
      final path = Path()..moveTo(-18, size.height * (.28 + i * .15));
      for (double x = 0; x <= size.width + 40; x += 24) {
        path.lineTo(
            x, size.height * (.28 + i * .15) + math.sin(x / 48 + i * .7) * 19);
      }
      canvas.drawPath(path, airflow);
    }
    final marker = Offset(size.width * .57, size.height * .44);
    canvas.drawCircle(
        marker, 34, Paint()..color = AppColors.mint300.withValues(alpha: .36));
    canvas.drawCircle(marker, 17, Paint()..color = AppColors.sun300);
    canvas.drawCircle(marker, 7, Paint()..color = AppColors.ink900);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class ErrorPanel extends StatelessWidget {
  const ErrorPanel({super.key, required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
            color: AppColors.danger100,
            borderRadius: BorderRadius.circular(20)),
        child: Column(children: [
          const Icon(Icons.cloud_off_outlined,
              color: AppColors.danger700, size: 32),
          const SizedBox(height: 10),
          Text(message, textAlign: TextAlign.center),
          const SizedBox(height: 12),
          OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Coba lagi'))
        ]),
      );
}
