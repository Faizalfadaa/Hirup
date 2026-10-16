import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/config/app_config.dart';
import '../../core/theme/app_theme.dart';
import '../../shared/widgets.dart';
import '../route_planning/domain/models.dart';
import '../route_planning/presentation/providers.dart';

class ProfileScreen extends ConsumerWidget {
  const ProfileScreen({super.key});
  @override Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final demo = ref.watch(demoModeProvider);
    return Scaffold(appBar: AppBar(title: const Text('Profil')), body: ListView(padding: const EdgeInsets.fromLTRB(20, 10, 20, 32), children: [
      const PageHeader(eyebrow: 'Tanpa akun', title: 'Sesuaikan Hirup', subtitle: 'Preferensi disimpan di perangkat. Profil sensitivitas bukan diagnosis medis.'), const SizedBox(height: 24),
      Text('Profil rekomendasi', style: Theme.of(context).textTheme.titleMedium), const SizedBox(height: 10),
      SegmentedButton<Sensitivity>(segments: const [ButtonSegment(value: Sensitivity.umum, icon: Icon(Icons.person_outline), label: Text('Umum')), ButtonSegment(value: Sensitivity.rentan, icon: Icon(Icons.health_and_safety_outlined), label: Text('Lebih sensitif'))], selected: {draft.sensitivity}, onSelectionChanged: (set) => ref.read(journeyDraftProvider.notifier).setSensitivity(set.first)),
      const SizedBox(height: 24),
      Card(child: Column(children: [
        SwitchListTile(value: demo, onChanged: (value) => ref.read(demoModeProvider.notifier).state = value, title: const Text('Mode demo', style: TextStyle(fontWeight: FontWeight.w700)), subtitle: const Text('Memakai fixture offline yang selalu diberi label data simulasi.')),
        if (demo) Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 16), child: DropdownButtonFormField<int>(key: ValueKey(ref.watch(demoScenarioProvider)), initialValue: ref.watch(demoScenarioProvider), decoration: const InputDecoration(labelText: 'Skenario demo'), items: List.generate(5, (i) => DropdownMenuItem(value: i, child: Text('Skenario ${i + 1}'))), onChanged: (value) { if (value != null) ref.read(demoScenarioProvider.notifier).state = value; })),
      ])),
      const SizedBox(height: 16),
      Card(child: Column(children: [
        ListTile(leading: const Icon(Icons.school_outlined), title: const Text('Kenali Hirup'), trailing: const Icon(Icons.chevron_right), onTap: () => context.push('/onboarding')),
        const Divider(height: 1),
        ListTile(leading: const Icon(Icons.dns_outlined), title: const Text('Alamat API'), subtitle: const Text(AppConfig.apiBaseUrl)),
        const Divider(height: 1),
        ListTile(leading: const Icon(Icons.delete_outline, color: AppColors.danger700), title: const Text('Hapus data lokal'), onTap: () async { await clearLocalData(); ref.read(historyProvider.notifier).clear(); if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Riwayat, profil, dan preferensi lokal telah dihapus.'))); }),
      ])),
      const SizedBox(height: 16), const Text('Hirup tidak memakai GPS latar belakang. Estimasi paparan bukan nasihat medis.', style: TextStyle(fontSize: 12, color: AppColors.ink600)),
    ]));
  }
}
