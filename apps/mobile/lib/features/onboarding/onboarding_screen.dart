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
            Align(alignment: Alignment.centerRight, child: TextButton(onPressed: () async { await markOnboardingComplete(); if (context.mounted) context.go('/home'); }, child: const Text('Lewati', style: TextStyle(color: Colors.white)))),
            Expanded(child: AnimatedSwitcher(duration: const Duration(milliseconds: 350), child: Center(key: ValueKey(step), child: Icon(icons[step], color: AppColors.mint300, size: 124)))),
            Container(width: double.infinity, padding: const EdgeInsets.fromLTRB(24, 30, 24, 24), decoration: const BoxDecoration(color: AppColors.paper, borderRadius: BorderRadius.vertical(top: Radius.circular(30))), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: List.generate(3, (i) => AnimatedContainer(duration: const Duration(milliseconds: 250), width: i == step ? 30 : 8, height: 8, margin: const EdgeInsets.only(right: 8), decoration: BoxDecoration(color: i == step ? AppColors.brand600 : AppColors.stroke, borderRadius: BorderRadius.circular(9))))),
              const SizedBox(height: 24), Text(titles[step], style: Theme.of(context).textTheme.headlineMedium), const SizedBox(height: 12), Text(descriptions[step], style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.ink600)), const SizedBox(height: 28),
              SizedBox(width: double.infinity, child: FilledButton(onPressed: next, child: Text(step == 2 ? 'Mulai jelajahi' : 'Lanjut'))),
            ])),
          ])),
        ),
      );
}
