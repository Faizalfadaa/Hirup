import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme/app_theme.dart';
import '../route_planning/presentation/providers.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});
  @override State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  int step = 0;
  final titles = const ['Lihat yang tak terlihat.', 'Temukan rute yang cocok buatmu.', 'Mulai dari mana?'];
  final descriptions = const [
    'Bandingkan estimasi dosis PM2.5 yang terhirup, bukan hanya angka kualitas udara di satu titik.',
    'Hirup menyeimbangkan waktu perjalanan dan estimasi paparan sesuai profil pilihanmu.',
    'Gunakan titik area pilot atau masukkan lokasi secara manual. Lokasimu tidak dipantau di latar belakang.',
  ];
  final icons = const [Icons.air_rounded, Icons.route_rounded, Icons.my_location_rounded];

  Future<void> next() async {
    if (step < 2) { setState(() => step++); return; }
    await markOnboardingComplete();
    if (mounted) context.go('/home');
  }

  @override Widget build(BuildContext context) => Scaffold(
        body: Container(
          decoration: const BoxDecoration(gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [AppColors.brand900, AppColors.brand600, Color(0xFF0B8073)])),
          child: SafeArea(child: Column(children: [
            Padding(padding: const EdgeInsets.fromLTRB(20, 10, 12, 0), child: Row(children: [
              const Text('HIRUP / JKT', style: TextStyle(fontSize: 12, letterSpacing: 1.4, fontWeight: FontWeight.w900, color: AppColors.mint300)),
              const Spacer(),
              TextButton(onPressed: () async { await markOnboardingComplete(); if (context.mounted) context.go('/home'); }, child: const Text('Lewati →', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700))),
            ])),
            Expanded(child: AnimatedSwitcher(duration: const Duration(milliseconds: 350), child: Stack(key: ValueKey(step), children: [
              Positioned(left: 16, top: 0, child: Text('0${step + 1}', style: TextStyle(fontSize: 126, height: 1, fontWeight: FontWeight.w900, color: Colors.white.withValues(alpha: .08)))),
              Positioned(left: 34, top: 86, child: Transform.rotate(angle: -.08, child: Container(width: 154, height: 154, decoration: BoxDecoration(color: step == 1 ? AppColors.sun300 : AppColors.mint300, borderRadius: const BorderRadius.only(topLeft: Radius.circular(46), topRight: Radius.circular(14), bottomLeft: Radius.circular(14), bottomRight: Radius.circular(46)), boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 0, offset: Offset(9, 9))]), child: Icon(icons[step], color: AppColors.ink900, size: 74)))),
              Positioned(right: 20, bottom: 28, child: Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8), decoration: BoxDecoration(border: Border.all(color: Colors.white54), borderRadius: BorderRadius.circular(99)), child: const Text('NAPAS · WAKTU · KOTA', style: TextStyle(fontSize: 9, letterSpacing: 1, color: Colors.white, fontWeight: FontWeight.w800)))),
            ]))),
            Container(width: double.infinity, padding: const EdgeInsets.fromLTRB(24, 26, 24, 24), decoration: const BoxDecoration(color: AppColors.paper, borderRadius: BorderRadius.only(topLeft: Radius.circular(42), topRight: Radius.circular(14))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: List.generate(3, (i) => AnimatedContainer(duration: const Duration(milliseconds: 250), width: i == step ? 38 : 12, height: 5, margin: const EdgeInsets.only(right: 7), decoration: BoxDecoration(color: i == step ? AppColors.brand600 : AppColors.stroke, borderRadius: BorderRadius.circular(9))))),
              const SizedBox(height: 20), Text(titles[step], style: Theme.of(context).textTheme.headlineMedium?.copyWith(color: AppColors.ink900)), const SizedBox(height: 10), Text(descriptions[step], style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.ink600)), const SizedBox(height: 24),
              SizedBox(width: double.infinity, child: FilledButton(onPressed: next, child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [Text(step == 2 ? 'MULAI JELAJAHI' : 'LANJUT'), const SizedBox(width: 10), const Icon(Icons.arrow_forward)]))),
            ])),
          ])),
        ),
      );
}
