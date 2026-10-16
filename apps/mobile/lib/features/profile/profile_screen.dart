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

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final demo = ref.watch(demoModeProvider);
    return Scaffold(
      body: CustomScrollView(slivers: [
        SliverToBoxAdapter(child: _ProfileHero(sensitivity: draft.sensitivity)),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 30),
          sliver: SliverList.list(children: [
            const _ProfileSectionLabel(
                title: 'PROFIL REKOMENDASI', tag: 'DISIMPAN LOKAL'),
            const SizedBox(height: 10),
            _SensitivityPicker(
              selected: draft.sensitivity,
              onChanged: (value) =>
                  ref.read(journeyDraftProvider.notifier).setSensitivity(value),
            ),
            const SizedBox(height: 22),
            const _ProfileSectionLabel(
                title: 'PENGATURAN DATA', tag: 'PERANGKAT INI'),
            const SizedBox(height: 10),
            _DemoPanel(
              enabled: demo,
              scenario: ref.watch(demoScenarioProvider),
              onEnabled: (value) =>
                  ref.read(demoModeProvider.notifier).state = value,
              onScenario: (value) =>
                  ref.read(demoScenarioProvider.notifier).state = value,
            ),
            const SizedBox(height: 12),
            _ProfileActions(
              onOnboarding: () => context.push('/onboarding'),
              onClear: () async {
                await clearLocalData();
                ref.read(historyProvider.notifier).clear();
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                      content: Text(
                          'Riwayat, profil, dan preferensi lokal telah dihapus.')));
                }
              },
            ),
            const SizedBox(height: 16),
            const _PrivacyNote(),
          ]),
        ),
      ]),
    );
  }
}

class _ProfileHero extends StatelessWidget {
  const _ProfileHero({required this.sensitivity});
  final Sensitivity sensitivity;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
        child: SizedBox(
          height: 232,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset('assets/images/air-moderate.png',
                fit: BoxFit.cover,
                alignment: const Alignment(-.15, .15),
                cacheWidth: 900,
                filterQuality: FilterQuality.low),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xF2073C3B),
                    Color(0xA8076D61),
                    Color(0xF007302F),
                  ],
                ),
              ),
            ),
            Positioned(
              right: -30,
              bottom: -42,
              child: Container(
                width: 150,
                height: 150,
                decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white10, width: 22)),
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
                      Row(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            Container(
                              width: 52,
                              height: 52,
                              decoration: BoxDecoration(
                                  color: AppColors.mint300,
                                  borderRadius: const BorderRadius.only(
                                      topLeft: Radius.circular(18),
                                      topRight: Radius.circular(7),
                                      bottomLeft: Radius.circular(7),
                                      bottomRight: Radius.circular(18)),
                                  border: Border.all(color: AppColors.ink900)),
                              child: Icon(
                                  sensitivity == Sensitivity.rentan
                                      ? Icons.health_and_safety_rounded
                                      : Icons.person_rounded,
                                  size: 26,
                                  color: AppColors.brand900),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text('PASPOR UDARA  ·  TANPA AKUN',
                                        style: TextStyle(
                                            color: AppColors.sun300,
                                            fontSize: 8,
                                            letterSpacing: .9,
                                            fontWeight: FontWeight.w900)),
                                    const SizedBox(height: 6),
                                    const Text('Hirup, versimu.',
                                        style: TextStyle(
                                            color: Colors.white,
                                            fontSize: 20,
                                            height: 1,
                                            letterSpacing: -.3,
                                            fontWeight: FontWeight.w900)),
                                    const SizedBox(height: 7),
                                    Text(
                                        sensitivity == Sensitivity.rentan
                                            ? 'Rekomendasi lebih peka terhadap paparan.'
                                            : 'Rekomendasi seimbang untuk aktivitas harian.',
                                        style: TextStyle(
                                            color: Colors.white
                                                .withValues(alpha: .7),
                                            fontSize: 9.5)),
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

class _ProfileSectionLabel extends StatelessWidget {
  const _ProfileSectionLabel({required this.title, required this.tag});
  final String title;
  final String tag;

  @override
  Widget build(BuildContext context) => Row(children: [
        Text(title,
            style: const TextStyle(
                fontSize: 9, letterSpacing: .8, fontWeight: FontWeight.w900)),
        const SizedBox(width: 8),
        const Expanded(child: Divider()),
        const SizedBox(width: 8),
        Text(tag,
            style: const TextStyle(
                fontSize: 6.5,
                letterSpacing: .55,
                fontWeight: FontWeight.w800,
                color: AppColors.brand600)),
      ]);
}

class _SensitivityPicker extends StatelessWidget {
  const _SensitivityPicker({required this.selected, required this.onChanged});
  final Sensitivity selected;
  final ValueChanged<Sensitivity> onChanged;

  @override
  Widget build(BuildContext context) => Row(children: [
        Expanded(
            child: _SensitivityCard(
                selected: selected == Sensitivity.umum,
                icon: Icons.person_outline_rounded,
                title: 'Umum',
                subtitle: 'Seimbang untuk harian',
                accent: AppColors.sky300,
                onTap: () => onChanged(Sensitivity.umum))),
        const SizedBox(width: 9),
        Expanded(
            child: _SensitivityCard(
                selected: selected == Sensitivity.rentan,
                icon: Icons.health_and_safety_outlined,
                title: 'Lebih sensitif',
                subtitle: 'Kurangi paparan lebih jauh',
                accent: AppColors.mint300,
                onTap: () => onChanged(Sensitivity.rentan))),
      ]);
}

class _SensitivityCard extends StatelessWidget {
  const _SensitivityCard(
      {required this.selected,
      required this.icon,
      required this.title,
      required this.subtitle,
      required this.accent,
      required this.onTap});
  final bool selected;
  final IconData icon;
  final String title;
  final String subtitle;
  final Color accent;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
        color: selected ? accent : Colors.white,
        clipBehavior: Clip.antiAlias,
        borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(8),
            bottomLeft: Radius.circular(8),
            bottomRight: Radius.circular(20)),
        child: InkWell(
          onTap: onTap,
          child: Container(
            height: 116,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
                border: Border.all(
                    color: selected ? AppColors.ink900 : AppColors.stroke,
                    width: selected ? 1.3 : 1),
                borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(20),
                    topRight: Radius.circular(8),
                    bottomLeft: Radius.circular(8),
                    bottomRight: Radius.circular(20))),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(icon, size: 22, color: AppColors.brand800),
                const Spacer(),
                Icon(
                    selected
                        ? Icons.check_circle_rounded
                        : Icons.circle_outlined,
                    size: 18,
                    color: selected ? AppColors.brand900 : AppColors.stroke),
              ]),
              const Spacer(),
              Text(title,
                  style: const TextStyle(
                      fontSize: 11.5, fontWeight: FontWeight.w900)),
              const SizedBox(height: 3),
              Text(subtitle,
                  maxLines: 2,
                  style: const TextStyle(
                      fontSize: 8.5, height: 1.25, color: AppColors.ink600)),
            ]),
          ),
        ),
      );
}

class _DemoPanel extends StatelessWidget {
  const _DemoPanel(
      {required this.enabled,
      required this.scenario,
      required this.onEnabled,
      required this.onScenario});
  final bool enabled;
  final int scenario;
  final ValueChanged<bool> onEnabled;
  final ValueChanged<int> onScenario;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(12, 11, 10, 11),
        decoration: BoxDecoration(
            color: enabled ? AppColors.sun300 : Colors.white,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(22),
                topRight: Radius.circular(8),
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(22)),
            border: Border.all(color: AppColors.ink900, width: 1.1)),
        child: Column(children: [
          Row(children: [
            Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(
                    color: enabled ? Colors.white54 : AppColors.surfaceSky,
                    borderRadius: BorderRadius.circular(11)),
                child: const Icon(Icons.science_outlined,
                    size: 19, color: AppColors.brand800)),
            const SizedBox(width: 10),
            const Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text('Mode demo',
                      style: TextStyle(
                          fontSize: 11.5, fontWeight: FontWeight.w900)),
                  SizedBox(height: 3),
                  Text('Fixture offline berlabel simulasi.',
                      style: TextStyle(fontSize: 8.5, color: AppColors.ink600)),
                ])),
            Switch(value: enabled, onChanged: onEnabled),
          ]),
          if (enabled) ...[
            const SizedBox(height: 8),
            DropdownButtonFormField<int>(
              key: ValueKey(scenario),
              initialValue: scenario,
              isDense: true,
              style: const TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w700,
                  color: AppColors.ink900),
              decoration: const InputDecoration(
                  labelText: 'Skenario demo',
                  contentPadding:
                      EdgeInsets.symmetric(horizontal: 12, vertical: 10)),
              items: List.generate(
                  5,
                  (i) => DropdownMenuItem(
                      value: i, child: Text('Skenario ${i + 1}'))),
              onChanged: (value) {
                if (value != null) {
                  onScenario(value);
                }
              },
            ),
          ],
        ]),
      );
}

class _ProfileActions extends StatelessWidget {
  const _ProfileActions({required this.onOnboarding, required this.onClear});
  final VoidCallback onOnboarding;
  final VoidCallback onClear;

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(20),
                topRight: Radius.circular(8),
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(20)),
            border: Border.all(color: AppColors.stroke)),
        child: Column(children: [
          _ActionRow(
              icon: Icons.school_outlined,
              title: 'Kenali Hirup',
              subtitle: 'Buka kembali panduan awal',
              onTap: onOnboarding),
          const Divider(height: 1),
          const _ActionRow(
              icon: Icons.dns_outlined,
              title: 'Backend aktif',
              subtitle: AppConfig.apiBaseUrl),
          const Divider(height: 1),
          _ActionRow(
              icon: Icons.delete_outline_rounded,
              title: 'Hapus data lokal',
              subtitle: 'Riwayat dan preferensi perangkat',
              danger: true,
              onTap: onClear),
        ]),
      );
}

class _ActionRow extends StatelessWidget {
  const _ActionRow(
      {required this.icon,
      required this.title,
      required this.subtitle,
      this.onTap,
      this.danger = false});
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final bool danger;

  @override
  Widget build(BuildContext context) => InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 10, 10),
          child: Row(children: [
            Icon(icon,
                size: 18,
                color: danger ? AppColors.danger700 : AppColors.brand600),
            const SizedBox(width: 10),
            Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Text(title,
                      style: TextStyle(
                          fontSize: 10.5,
                          fontWeight: FontWeight.w800,
                          color:
                              danger ? AppColors.danger700 : AppColors.ink900)),
                  const SizedBox(height: 2),
                  Text(subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 8.5, color: AppColors.ink600)),
                ])),
            if (onTap != null)
              const Icon(Icons.chevron_right_rounded,
                  size: 18, color: AppColors.ink600),
          ]),
        ),
      );
}

class _PrivacyNote extends StatelessWidget {
  const _PrivacyNote();

  @override
  Widget build(BuildContext context) => const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.lock_outline_rounded, size: 14, color: AppColors.brand600),
          SizedBox(width: 7),
          Expanded(
            child: Text(
                'Hirup tidak memakai GPS latar belakang. Estimasi paparan bukan diagnosis atau nasihat medis.',
                style: TextStyle(
                    fontSize: 8.5, height: 1.4, color: AppColors.ink600)),
          ),
        ],
      );
}
