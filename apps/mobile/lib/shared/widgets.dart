import 'package:flutter/material.dart';

import '../core/theme/app_theme.dart';
import '../features/route_planning/domain/models.dart';
import 'air_map.dart';

class PageHeader extends StatelessWidget {
  const PageHeader({super.key, required this.eyebrow, required this.title, required this.subtitle});
  final String eyebrow;
  final String title;
  final String subtitle;
  @override Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(eyebrow.toUpperCase(), style: const TextStyle(fontSize: 11, letterSpacing: .8, fontWeight: FontWeight.w800, color: AppColors.brand600)),
        const SizedBox(height: 8), Text(title, style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: AppColors.ink900)),
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
  const AirMapCard({super.key, this.compact = false, this.origin, this.destination, this.route, this.highlightLeg, this.interactive = true});
  final bool compact;
  final PlacePoint? origin;
  final PlacePoint? destination;
  final RouteOption? route;
  final int? highlightLeg;
  final bool interactive;
  @override Widget build(BuildContext context) => Semantics(
        label: route != null ? 'Peta rute, warna garis menunjukkan estimasi PM2.5 per ruas.' : 'Peta area pilot Jakarta dengan estimasi PM2.5.',
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: Container(
              height: compact ? 190 : 310,
              width: double.infinity,
              decoration: BoxDecoration(border: Border.all(color: AppColors.stroke), borderRadius: BorderRadius.circular(24)),
              child: Stack(children: [
                Positioned.fill(child: AirMap(origin: origin, destination: destination, route: route, highlightLeg: highlightLeg, interactive: interactive)),
                Positioned(top: 13, left: 13, child: IgnorePointer(child: Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6), decoration: BoxDecoration(color: AppColors.ink900, borderRadius: BorderRadius.circular(8)), child: const Text('JKT / AIR GRID 01', style: TextStyle(fontSize: 9, letterSpacing: .8, fontWeight: FontWeight.w900, color: AppColors.mint300))))),
              ]),
            ),
          ),
          if (route != null) const Padding(padding: EdgeInsets.only(top: 8, left: 4), child: Pm25Legend()),
        ]),
      );
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
