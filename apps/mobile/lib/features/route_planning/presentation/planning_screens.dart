import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_theme.dart';
import '../../../core/utils/formatters.dart';
import '../../../shared/widgets.dart';
import '../domain/models.dart';
import 'providers.dart';

class ModeScreen extends ConsumerWidget {
  const ModeScreen({super.key});
  static const data = <PlanMode, (IconData, String, String)>{
    PlanMode.transit: (
      Icons.directions_transit,
      'Transit',
      'MRT, LRT, TransJakarta'
    ),
    PlanMode.bike: (Icons.pedal_bike, 'Sepeda', 'Jalur aktif yang tersedia'),
    PlanMode.walk: (
      Icons.directions_walk,
      'Jalan kaki',
      'Untuk perjalanan dekat'
    ),
    PlanMode.all: (Icons.compare_arrows, 'Semua', 'Bandingkan semua opsi'),
  };
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    return Scaffold(
      appBar: const HirupAppBar(section: 'PILIH MODE', code: '05'),
      body: SafeArea(
          child: Column(children: [
        Expanded(
            child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
                children: [
              _JourneyCapsule(draft: draft),
              const SizedBox(height: 26),
              const PageHeader(
                  eyebrow: 'Langkah 2 dari 2',
                  title: 'Mau perjalanan seperti apa?',
                  subtitle:
                      'Pilih moda utama. Kendaraan pribadi tetap ditampilkan sebagai pembanding.'),
              const SizedBox(height: 20),
              GridView.count(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  crossAxisCount: 2,
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: .92,
                  children:
                      data.entries.toList().asMap().entries.map((indexed) {
                    final tileIndex = indexed.key;
                    final entry = indexed.value;
                    final selected = draft.mode == entry.key;
                    final accent = [
                      AppColors.mint300,
                      AppColors.sky300,
                      AppColors.sun300,
                      AppColors.brand100
                    ][tileIndex];
                    return InkWell(
                        borderRadius: BorderRadius.circular(20),
                        onTap: () => ref
                            .read(journeyDraftProvider.notifier)
                            .setMode(entry.key),
                        child: AnimatedContainer(
                            duration: const Duration(milliseconds: 180),
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                                color: selected ? accent : Colors.white,
                                borderRadius: BorderRadius.only(
                                    topLeft: const Radius.circular(24),
                                    topRight: Radius.circular(
                                        tileIndex.isEven ? 8 : 24),
                                    bottomLeft: Radius.circular(
                                        tileIndex.isEven ? 8 : 24),
                                    bottomRight: const Radius.circular(24)),
                                border: Border.all(
                                    color: selected
                                        ? AppColors.ink900
                                        : AppColors.stroke,
                                    width: selected ? 1.5 : 1),
                                boxShadow: selected
                                    ? const [
                                        BoxShadow(
                                            color: Color(0x22073C3B),
                                            offset: Offset(4, 5))
                                      ]
                                    : null),
                            child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Row(children: [
                                    Text('0${tileIndex + 1}',
                                        style: const TextStyle(
                                            fontSize: 11,
                                            letterSpacing: .8,
                                            fontWeight: FontWeight.w900,
                                            color: AppColors.ink600)),
                                    const Spacer(),
                                    if (selected)
                                      const Icon(Icons.check_circle,
                                          color: AppColors.ink900)
                                  ]),
                                  const SizedBox(height: 10),
                                  Icon(entry.value.$1,
                                      color: AppColors.brand800, size: 31),
                                  const Spacer(),
                                  Text(entry.value.$2,
                                      style: const TextStyle(
                                          fontWeight: FontWeight.w900,
                                          fontSize: 16,
                                          color: AppColors.ink900)),
                                  const SizedBox(height: 3),
                                  Text(entry.value.$3,
                                      style: const TextStyle(
                                          fontSize: 12,
                                          color: AppColors.ink600)),
                                ])));
                  }).toList()),
              const SizedBox(height: 18),
              Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                      color: AppColors.surfaceSky,
                      borderRadius: BorderRadius.circular(18)),
                  child: Row(children: [
                    const Icon(Icons.tune, color: AppColors.sky700),
                    const SizedBox(width: 12),
                    Expanded(
                        child: Text(
                            'Profil: ${draft.sensitivity == Sensitivity.rentan ? 'lebih sensitif' : 'umum'} · Maks. jalan 1 km'))
                  ])),
            ])),
        Container(
            padding: const EdgeInsets.fromLTRB(20, 12, 20, 12),
            decoration: const BoxDecoration(
                color: Colors.white,
                border: Border(top: BorderSide(color: AppColors.stroke))),
            child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                    onPressed: () {
                      ref.read(planProvider.notifier).load();
                      context.push('/plan/results');
                    },
                    child: const Text('Lihat pilihan rute')))),
      ])),
    );
  }
}

class JourneyPreferencesScreen extends ConsumerStatefulWidget {
  const JourneyPreferencesScreen({super.key});

  @override
  ConsumerState<JourneyPreferencesScreen> createState() =>
      _JourneyPreferencesScreenState();
}

class _JourneyPreferencesScreenState
    extends ConsumerState<JourneyPreferencesScreen> {
  bool _revealed = false;

  @override
  void initState() {
    super.initState();
    Future<void>.delayed(const Duration(milliseconds: 240), () {
      if (mounted) setState(() => _revealed = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    final draft = ref.watch(journeyDraftProvider);
    return Scaffold(
      bottomNavigationBar: SafeArea(
        child: Container(
          padding: const EdgeInsets.fromLTRB(18, 10, 18, 12),
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(top: BorderSide(color: AppColors.stroke)),
          ),
          child: SizedBox(
            height: 44,
            child: FilledButton(
              onPressed: () {
                ref.read(planProvider.notifier).load();
                context.push('/plan/results');
              },
              child: const Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text('LIHAT PILIHAN RUTE',
                      style: TextStyle(fontSize: 10.5, letterSpacing: .55)),
                  SizedBox(width: 9),
                  Icon(Icons.arrow_forward_rounded, size: 18),
                ],
              ),
            ),
          ),
        ),
      ),
      body: CustomScrollView(
        slivers: [
          SliverToBoxAdapter(child: _RouteSetupHero(onBack: context.pop)),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 26),
            sliver: SliverList.list(children: [
              _ExpandedJourneyCard(draft: draft),
              const SizedBox(height: 22),
              AnimatedSlide(
                duration: const Duration(milliseconds: 360),
                curve: Curves.easeOutCubic,
                offset: _revealed ? Offset.zero : const Offset(0, .07),
                child: AnimatedOpacity(
                  duration: const Duration(milliseconds: 300),
                  opacity: _revealed ? 1 : 0,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _PlanningSectionLabel(
                          label: 'PILIH MODA', code: '04 OPSI'),
                      const SizedBox(height: 8),
                      const Text(
                        'Kami membandingkan kualitas udara dan waktu perjalanan.',
                        style: TextStyle(fontSize: 10, color: AppColors.ink600),
                      ),
                      const SizedBox(height: 13),
                      _ModeChoice(
                        mode: PlanMode.all,
                        selected: draft.mode == PlanMode.all,
                        icon: Icons.auto_awesome_rounded,
                        title: 'Semua opsi',
                        subtitle: 'Bandingkan semua moda untuk rute terbaik.',
                        badge: 'Direkomendasikan',
                        onTap: () => ref
                            .read(journeyDraftProvider.notifier)
                            .setMode(PlanMode.all),
                      ),
                      _ModeChoice(
                        mode: PlanMode.transit,
                        selected: draft.mode == PlanMode.transit,
                        icon: Icons.directions_transit_rounded,
                        title: 'Transit publik',
                        subtitle: 'MRT, LRT, dan TransJakarta.',
                        badge: 'Lebih rendah emisi',
                        onTap: () => ref
                            .read(journeyDraftProvider.notifier)
                            .setMode(PlanMode.transit),
                      ),
                      _ModeChoice(
                        mode: PlanMode.bike,
                        selected: draft.mode == PlanMode.bike,
                        icon: Icons.pedal_bike_rounded,
                        title: 'Sepeda',
                        subtitle: 'Aktif untuk perjalanan yang lebih dekat.',
                        onTap: () => ref
                            .read(journeyDraftProvider.notifier)
                            .setMode(PlanMode.bike),
                      ),
                      _ModeChoice(
                        mode: PlanMode.walk,
                        selected: draft.mode == PlanMode.walk,
                        icon: Icons.directions_walk_rounded,
                        title: 'Jalan kaki',
                        subtitle: 'Pilihan sehat untuk jarak pendek.',
                        onTap: () => ref
                            .read(journeyDraftProvider.notifier)
                            .setMode(PlanMode.walk),
                      ),
                      const SizedBox(height: 3),
                      _ComparisonToggle(
                        value: draft.includeComparison,
                        onChanged: (value) => ref
                            .read(journeyDraftProvider.notifier)
                            .setIncludeComparison(value),
                      ),
                      const SizedBox(height: 14),
                      Container(
                        padding: const EdgeInsets.all(13),
                        decoration: BoxDecoration(
                          color: AppColors.surfaceSky,
                          borderRadius: BorderRadius.circular(15),
                          border: Border.all(color: AppColors.stroke),
                        ),
                        child: const Row(children: [
                          Icon(Icons.health_and_safety_outlined,
                              size: 18, color: AppColors.sky700),
                          SizedBox(width: 9),
                          Expanded(
                            child: Text(
                              'Rute diperingkat berdasarkan estimasi paparan, bukan hanya jarak.',
                              style: TextStyle(
                                  fontSize: 9.5, color: AppColors.ink700),
                            ),
                          ),
                        ]),
                      ),
                    ],
                  ),
                ),
              ),
            ]),
          ),
        ],
      ),
    );
  }
}

class _RouteSetupHero extends StatelessWidget {
  const _RouteSetupHero({required this.onBack});

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(28)),
        child: SizedBox(
          height: 196,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset('assets/images/air-moderate.png',
                fit: BoxFit.cover,
                alignment: const Alignment(.45, .1),
                cacheWidth: 850,
                filterQuality: FilterQuality.low),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xF2073C3B),
                    Color(0xB307665B),
                    Color(0xE807302F),
                  ],
                ),
              ),
            ),
            Positioned(
              right: -20,
              bottom: -35,
              child: Container(
                width: 135,
                height: 135,
                decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white12, width: 18)),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 18, 18),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Stack(alignment: Alignment.center, children: [
                        const Center(
                          child: Row(mainAxisSize: MainAxisSize.min, children: [
                            HirupLogoMark(size: 26, dark: false),
                            SizedBox(width: 7),
                            Text('hirup.',
                                style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 17,
                                    height: 1,
                                    letterSpacing: -.4,
                                    fontWeight: FontWeight.w900)),
                          ]),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Material(
                            color: Colors.white.withValues(alpha: .13),
                            shape: const CircleBorder(
                                side: BorderSide(color: Colors.white30)),
                            child: InkWell(
                              customBorder: const CircleBorder(),
                              onTap: onBack,
                              child: const SizedBox(
                                  width: 36,
                                  height: 36,
                                  child: Icon(Icons.arrow_back_rounded,
                                      size: 19, color: Colors.white)),
                            ),
                          ),
                        ),
                      ]),
                      const Spacer(),
                      const Row(children: [
                        Icon(Icons.route_rounded,
                            size: 14, color: AppColors.mint300),
                        SizedBox(width: 6),
                        Text('LANGKAH 03  ·  RUTE + UDARA',
                            style: TextStyle(
                                color: AppColors.mint300,
                                fontSize: 8,
                                letterSpacing: 1,
                                fontWeight: FontWeight.w900)),
                      ]),
                      const SizedBox(height: 6),
                      const Text('Pilih cara bergerak.',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              height: 1,
                              letterSpacing: -.25,
                              fontWeight: FontWeight.w900)),
                      const SizedBox(height: 7),
                      Text(
                          'Satu tujuan, beberapa cara dengan paparan yang berbeda.',
                          style: TextStyle(
                              color: Colors.white.withValues(alpha: .72),
                              fontSize: 10,
                              height: 1.3)),
                    ]),
              ),
            ),
          ]),
        ),
      );
}

class _PlanningSectionLabel extends StatelessWidget {
  const _PlanningSectionLabel({required this.label, required this.code});

  final String label;
  final String code;

  @override
  Widget build(BuildContext context) => Row(children: [
        Text(label,
            style: const TextStyle(
                fontSize: 9,
                letterSpacing: .85,
                fontWeight: FontWeight.w900,
                color: AppColors.ink900)),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
              color: AppColors.mint300,
              borderRadius: BorderRadius.circular(99),
              border: Border.all(color: AppColors.ink900)),
          child: Text(code,
              style: const TextStyle(
                  fontSize: 7.5,
                  fontWeight: FontWeight.w900,
                  color: AppColors.ink900)),
        ),
        const SizedBox(width: 8),
        const Expanded(child: Divider()),
      ]);
}

class _ExpandedJourneyCard extends StatelessWidget {
  const _ExpandedJourneyCard({required this.draft});
  final JourneyDraft draft;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(15, 14, 15, 13),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(22),
          border: Border.all(color: AppColors.brand900, width: 1.2),
          boxShadow: const [
            BoxShadow(color: Color(0x16073C3B), offset: Offset(4, 5))
          ],
        ),
        child: Column(children: [
          Row(children: [
            Container(
              width: 29,
              height: 29,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                color: AppColors.brand100,
                borderRadius: BorderRadius.circular(9),
              ),
              child: const Icon(Icons.route_rounded,
                  size: 17, color: AppColors.brand800),
            ),
            const SizedBox(width: 9),
            const Expanded(
              child: Text('TITIK PERJALANAN',
                  style: TextStyle(
                      fontSize: 9,
                      letterSpacing: .8,
                      fontWeight: FontWeight.w900)),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              decoration: BoxDecoration(
                  color: AppColors.mint300,
                  borderRadius: BorderRadius.circular(99)),
              child: Text(formatTime(draft.departAt),
                  style: const TextStyle(
                      fontSize: 9, fontWeight: FontWeight.w900)),
            ),
          ]),
          const SizedBox(height: 13),
          _LocationLine(label: 'DARI', name: draft.origin.name, first: true),
          _LocationLine(
              label: 'TUJUAN', name: draft.destination.name, first: false),
          const SizedBox(height: 9),
          Row(children: [
            const Icon(Icons.schedule_rounded,
                size: 15, color: AppColors.brand600),
            const SizedBox(width: 7),
            Text('Berangkat ${formatTime(draft.departAt)}',
                style: const TextStyle(
                    fontSize: 10.5, fontWeight: FontWeight.w700)),
            const Spacer(),
            const Text('UBAH DI BERANDA',
                style: TextStyle(
                    fontSize: 8,
                    letterSpacing: .6,
                    color: AppColors.ink600,
                    fontWeight: FontWeight.w800)),
          ]),
        ]),
      );
}

class _LocationLine extends StatelessWidget {
  const _LocationLine(
      {required this.label, required this.name, required this.first});
  final String label;
  final String name;
  final bool first;

  @override
  Widget build(BuildContext context) => IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            width: 22,
            child: Column(children: [
              Container(
                  width: 9,
                  height: 9,
                  decoration: BoxDecoration(
                      color: first ? AppColors.brand600 : AppColors.sun300,
                      shape: BoxShape.circle,
                      border: Border.all(color: AppColors.brand900))),
              if (first)
                Expanded(
                    child: Container(width: 1.5, color: AppColors.brand100)),
            ]),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(label,
                        style: const TextStyle(
                            fontSize: 7.5,
                            letterSpacing: .7,
                            color: AppColors.ink600,
                            fontWeight: FontWeight.w800)),
                    const SizedBox(height: 2),
                    Text(name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 12, fontWeight: FontWeight.w800)),
                  ]),
            ),
          ),
          const Icon(Icons.edit_rounded, size: 16, color: AppColors.brand600),
        ]),
      );
}

class _ModeChoice extends StatelessWidget {
  const _ModeChoice({
    required this.mode,
    required this.selected,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.badge,
  });
  final PlanMode mode;
  final bool selected;
  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final String? badge;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 9),
        child: Material(
          color: selected ? AppColors.brand800 : Colors.white,
          borderRadius: BorderRadius.circular(17),
          child: InkWell(
            onTap: onTap,
            borderRadius: BorderRadius.circular(17),
            child: Container(
              constraints: const BoxConstraints(minHeight: 66),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(17),
                border: Border.all(
                    color: selected ? AppColors.brand900 : AppColors.stroke),
                boxShadow: selected
                    ? const [
                        BoxShadow(
                            color: Color(0x22073C3B), offset: Offset(3, 4))
                      ]
                    : null,
              ),
              child: Row(children: [
                Container(
                  width: 37,
                  height: 37,
                  decoration: BoxDecoration(
                    color: selected
                        ? Colors.white.withValues(alpha: .14)
                        : AppColors.surfaceSky,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Icon(icon,
                      size: 20,
                      color: selected ? Colors.white : AppColors.brand800),
                ),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          Flexible(
                            child: Text(title,
                                style: TextStyle(
                                    color: selected
                                        ? Colors.white
                                        : AppColors.ink900,
                                    fontSize: 12,
                                    fontWeight: FontWeight.w900)),
                          ),
                          if (badge != null) ...[
                            const SizedBox(width: 6),
                            Flexible(
                              child: Container(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 6, vertical: 3),
                                decoration: BoxDecoration(
                                  color: selected
                                      ? AppColors.mint300
                                      : AppColors.brand100,
                                  borderRadius: BorderRadius.circular(99),
                                ),
                                child: Text(badge!,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                        color: AppColors.brand900,
                                        fontSize: 7,
                                        fontWeight: FontWeight.w900)),
                              ),
                            ),
                          ],
                        ]),
                        const SizedBox(height: 3),
                        Text(subtitle,
                            style: TextStyle(
                                color: selected
                                    ? Colors.white.withValues(alpha: .72)
                                    : AppColors.ink600,
                                fontSize: 9.5)),
                      ]),
                ),
                const SizedBox(width: 8),
                Icon(
                  selected ? Icons.check_circle_rounded : Icons.circle_outlined,
                  color: selected ? AppColors.mint300 : AppColors.stroke,
                  size: 20,
                ),
              ]),
            ),
          ),
        ),
      );
}

class _ComparisonToggle extends StatelessWidget {
  const _ComparisonToggle({required this.value, required this.onChanged});
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(12, 9, 8, 9),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(17),
          border: Border.all(color: AppColors.stroke),
        ),
        child: Row(children: [
          Container(
            width: 37,
            height: 37,
            decoration: BoxDecoration(
                color: AppColors.surfaceSky,
                borderRadius: BorderRadius.circular(12)),
            child: const Icon(Icons.commute_rounded,
                size: 20, color: AppColors.brand800),
          ),
          const SizedBox(width: 11),
          const Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Bandingkan motor & mobil',
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900)),
              SizedBox(height: 3),
              Text('Lihat selisih waktu dan paparan.',
                  style: TextStyle(fontSize: 9.5, color: AppColors.ink600)),
            ]),
          ),
          Switch(value: value, onChanged: onChanged),
        ]),
      );
}

class ResultsScreen extends ConsumerWidget {
  const ResultsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final state = ref.watch(planProvider);
    final air = ref.watch(airPointProvider);
    return AnnotatedRegion<SystemUiOverlayStyle>(
        value: SystemUiOverlayStyle.light,
        child: Scaffold(
            body: Column(children: [
          _ResultsHero(draft: draft, air: air, onBack: context.pop),
          Expanded(
              child: state.when(
                  loading: () => const _RoutePlanningLoader(),
                  error: (error, _) =>
                      ListView(padding: const EdgeInsets.all(20), children: [
                        const SizedBox(height: 100),
                        ErrorPanel(
                            message: error.toString(),
                            onRetry: ref.read(planProvider.notifier).load)
                      ]),
                  data: (result) {
                    if (result == null) {
                      return Center(
                          child: FilledButton(
                              onPressed: ref.read(planProvider.notifier).load,
                              child: const Text('Muat pilihan rute')));
                    }
                    return Column(children: [
                      Expanded(
                          child: ListView(
                              padding:
                                  const EdgeInsets.fromLTRB(20, 18, 20, 36),
                              children: [
                            _JourneyCapsule(draft: draft),
                            const SizedBox(height: 16),
                            AirMapCard(
                                compact: true,
                                interactive: false,
                                origin: draft.origin,
                                destination: draft.destination,
                                route: result.options.isEmpty
                                    ? null
                                    : result.options.first),
                            const SizedBox(height: 24),
                            _ResultsSectionLabel(count: result.options.length),
                            const SizedBox(height: 7),
                            Row(children: [
                              if (!result.isDemo) ...[
                                QualityBadge(quality: result.dataQuality),
                                const SizedBox(width: 8),
                              ],
                              Text(
                                  '${formatTime(result.freshness.validHour)} · ${result.freshness.confidence}',
                                  style: const TextStyle(
                                      fontSize: 10, color: AppColors.ink600))
                            ]),
                            const SizedBox(height: 13),
                            ...result.options
                                .asMap()
                                .entries
                                .map((entry) => Padding(
                                    padding: const EdgeInsets.only(bottom: 12),
                                    child: _RouteCard(
                                        index: entry.key + 1,
                                        option: entry.value,
                                        onTap: () {
                                          ref
                                              .read(selectedRouteIdProvider
                                                  .notifier)
                                              .state = entry.value.id;
                                          context.push(
                                              '/plan/detail/${entry.value.id}');
                                        }))),
                            _ComparisonSection(
                                motorcycle: result.motorcycle, car: result.car),
                            const SizedBox(height: 18),
                            Text(result.disclaimer,
                                style: const TextStyle(
                                    fontSize: 12, color: AppColors.ink600)),
                          ])),
                    ]);
                  })),
        ])));
  }
}

class _ResultsHero extends StatelessWidget {
  const _ResultsHero(
      {required this.draft, required this.air, required this.onBack});
  final JourneyDraft draft;
  final AsyncValue<AirPoint> air;
  final VoidCallback onBack;

  String _asset(double pm25) {
    if (pm25 <= 15.5) return 'assets/images/air-good.png';
    if (pm25 <= 55.4) return 'assets/images/air-moderate.png';
    return 'assets/images/air-unhealthy.png';
  }

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(28)),
        child: SizedBox(
          height: 238,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset(_asset(air.valueOrNull?.p50 ?? 30),
                fit: BoxFit.cover,
                alignment: const Alignment(.35, .15),
                cacheWidth: 850,
                filterQuality: FilterQuality.low),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xF2073C3B),
                    Color(0xA8076B60),
                    Color(0xF007302F),
                  ],
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
                      Stack(alignment: Alignment.center, children: [
                        const Center(
                          child: Row(mainAxisSize: MainAxisSize.min, children: [
                            HirupLogoMark(size: 26, dark: false),
                            SizedBox(width: 7),
                            Text('hirup.',
                                style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 17,
                                    height: 1,
                                    letterSpacing: -.4,
                                    fontWeight: FontWeight.w900)),
                          ]),
                        ),
                        Align(
                          alignment: Alignment.centerLeft,
                          child: Material(
                            color: Colors.white.withValues(alpha: .13),
                            shape: const CircleBorder(
                                side: BorderSide(color: Colors.white30)),
                            child: InkWell(
                              customBorder: const CircleBorder(),
                              onTap: onBack,
                              child: const SizedBox(
                                  width: 36,
                                  height: 36,
                                  child: Icon(Icons.arrow_back_rounded,
                                      size: 19, color: Colors.white)),
                            ),
                          ),
                        ),
                      ]),
                      const Spacer(),
                      Container(
                        padding: const EdgeInsets.fromLTRB(15, 13, 14, 13),
                        decoration: BoxDecoration(
                          color: const Color(0xE6103F3C),
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: Colors.white24),
                          boxShadow: const [
                            BoxShadow(
                                color: Color(0x3D001F1D),
                                blurRadius: 16,
                                offset: Offset(0, 7))
                          ],
                        ),
                        child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Row(children: [
                                Icon(Icons.route_rounded,
                                    size: 14, color: AppColors.mint300),
                                SizedBox(width: 7),
                                Text('HASIL PERJALANAN',
                                    style: TextStyle(
                                        color: AppColors.mint300,
                                        fontSize: 9,
                                        letterSpacing: .9,
                                        fontWeight: FontWeight.w900)),
                              ]),
                              const SizedBox(height: 7),
                              const Text('Pilih napas terbaik.',
                                  style: TextStyle(
                                      color: Colors.white,
                                      fontSize: 19,
                                      height: 1,
                                      letterSpacing: -.2,
                                      fontWeight: FontWeight.w900)),
                              const SizedBox(height: 10),
                              Row(children: [
                                const Icon(Icons.trip_origin_rounded,
                                    size: 12, color: AppColors.sun300),
                                const SizedBox(width: 5),
                                Expanded(
                                    child: Text(draft.origin.name,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: const TextStyle(
                                            color: Colors.white70,
                                            fontSize: 10))),
                                const Padding(
                                  padding: EdgeInsets.symmetric(horizontal: 7),
                                  child: Icon(Icons.arrow_forward_rounded,
                                      size: 13, color: AppColors.mint300),
                                ),
                                Expanded(
                                    child: Text(draft.destination.name,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        textAlign: TextAlign.right,
                                        style: const TextStyle(
                                            color: Colors.white70,
                                            fontSize: 10))),
                              ]),
                            ]),
                      ),
                    ]),
              ),
            ),
          ]),
        ),
      );
}

class _ResultsSectionLabel extends StatelessWidget {
  const _ResultsSectionLabel({required this.count});
  final int count;

  @override
  Widget build(BuildContext context) => Row(children: [
        const Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Pilihan rute',
                style: TextStyle(
                    fontSize: 16,
                    height: 1.15,
                    fontWeight: FontWeight.w900,
                    color: AppColors.ink900)),
            SizedBox(height: 3),
            Text('Urutkan waktu dan paparan sesuai kebutuhanmu.',
                style: TextStyle(fontSize: 10, color: AppColors.ink600)),
          ]),
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
          decoration: BoxDecoration(
              color: AppColors.mint300,
              borderRadius: BorderRadius.circular(99),
              border: Border.all(color: AppColors.ink900)),
          child: Text(count.toString().padLeft(2, '0'),
              style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w900)),
        ),
      ]);
}

// ignore: unused_element
class _LegacyPlanningLoader extends StatelessWidget {
  const _LegacyPlanningLoader();
  @override
  Widget build(BuildContext context) => Center(
      child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 20),
            Text('Menyusun pilihan perjalanan…',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            const Text('Biasanya selesai dalam beberapa detik.',
                style: TextStyle(color: AppColors.ink600))
          ])));
}

class _RoutePlanningLoader extends StatefulWidget {
  const _RoutePlanningLoader();

  @override
  State<_RoutePlanningLoader> createState() => _RoutePlanningLoaderState();
}

class _RoutePlanningLoaderState extends State<_RoutePlanningLoader>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Center(
        child: AnimatedBuilder(
          animation: _controller,
          builder: (_, __) => CustomPaint(
            size: const Size(190, 120),
            painter: _RouteLoaderPainter(_controller.value),
          ),
        ),
      );
}

class _RouteLoaderPainter extends CustomPainter {
  const _RouteLoaderPainter(this.progress);
  final double progress;

  @override
  void paint(Canvas canvas, Size size) {
    final frame =
        RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(24));
    canvas.drawRRect(frame, Paint()..color = Colors.white);
    canvas.drawRRect(
        frame,
        Paint()
          ..color = AppColors.ink900
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2);
    final paths = <(Path, Color)>[
      (
        Path()
          ..moveTo(18, 88)
          ..cubicTo(58, 89, 62, 25, 112, 37)
          ..cubicTo(142, 44, 150, 83, 174, 69),
        AppColors.mint300
      ),
      (
        Path()
          ..moveTo(18, 73)
          ..cubicTo(55, 54, 72, 78, 102, 68)
          ..cubicTo(135, 57, 146, 31, 174, 42),
        AppColors.sun300
      ),
      (
        Path()
          ..moveTo(18, 48)
          ..cubicTo(49, 25, 76, 43, 94, 54)
          ..cubicTo(125, 76, 147, 94, 174, 90),
        AppColors.sky300
      ),
    ];
    for (var i = 0; i < paths.length; i++) {
      final path = paths[i].$1;
      final color = paths[i].$2;
      canvas.drawPath(
          path,
          Paint()
            ..color = color.withValues(alpha: .35)
            ..style = PaintingStyle.stroke
            ..strokeWidth = 5
            ..strokeCap = StrokeCap.round);
      final metric = path.computeMetrics().first;
      final shifted = (progress + i * .24) % 1;
      final point = metric.getTangentForOffset(metric.length * shifted);
      if (point != null) {
        canvas.drawCircle(point.position, 5, Paint()..color = color);
        canvas.drawCircle(
            point.position,
            5,
            Paint()
              ..color = AppColors.ink900
              ..style = PaintingStyle.stroke
              ..strokeWidth = 1.2);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _RouteLoaderPainter oldDelegate) =>
      oldDelegate.progress != progress;
}

class _JourneyCapsule extends StatelessWidget {
  const _JourneyCapsule({required this.draft});
  final JourneyDraft draft;
  @override
  Widget build(BuildContext context) => Container(
      padding: const EdgeInsets.fromLTRB(13, 11, 13, 11),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(20),
              topRight: Radius.circular(8),
              bottomLeft: Radius.circular(8),
              bottomRight: Radius.circular(20)),
          border: Border.all(color: AppColors.ink900, width: 1.1)),
      child: Row(children: [
        Container(
            width: 30,
            height: 30,
            alignment: Alignment.center,
            decoration: BoxDecoration(
                color: AppColors.sun300,
                borderRadius: BorderRadius.circular(9),
                border: Border.all(color: AppColors.ink900)),
            child: const Icon(Icons.route_rounded,
                size: 16, color: AppColors.ink900)),
        const SizedBox(width: 10),
        Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(draft.origin.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                  fontSize: 10.5,
                  fontWeight: FontWeight.w800,
                  color: AppColors.ink900)),
          const SizedBox(height: 2),
          Text(draft.destination.name,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, color: AppColors.ink600)),
        ])),
        const SizedBox(width: 8),
        const Icon(Icons.arrow_forward_rounded,
            size: 17, color: AppColors.brand600),
      ]));
}

class _RouteCard extends StatelessWidget {
  const _RouteCard(
      {required this.index, required this.option, required this.onTap});
  final int index;
  final RouteOption option;
  final VoidCallback onTap;
  String label(String raw) => switch (raw) {
        'fastest' => 'Tercepat',
        'cleanest' => 'Terbersih',
        'balanced' => 'Seimbang',
        _ => raw
      };
  @override
  Widget build(BuildContext context) {
    final reduction = option.deltaDosePct < 0
        ? '${option.deltaDosePct.abs().round()}% lebih rendah'
        : 'Acuan tercepat';
    final accent = index == 1
        ? AppColors.sun300
        : index == 2
            ? AppColors.mint300
            : AppColors.sky300;
    return Semantics(
        button: true,
        label:
            '${option.labels.map(label).join(', ')}, ${formatDuration(option.durationS)}, estimasi dosis ${formatDose(option.doseUg)}, $reduction',
        child: Container(
          decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(22),
                  topRight: Radius.circular(8),
                  bottomLeft: Radius.circular(8),
                  bottomRight: Radius.circular(22)),
              border: Border.all(color: AppColors.ink900, width: 1.2),
              boxShadow: const [
                BoxShadow(color: Color(0x16073C3B), offset: Offset(4, 4))
              ]),
          child: InkWell(
              borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(22),
                  topRight: Radius.circular(8),
                  bottomLeft: Radius.circular(8),
                  bottomRight: Radius.circular(22)),
              onTap: onTap,
              child: Column(children: [
                Container(
                    height: 5,
                    decoration: BoxDecoration(
                        color: accent,
                        borderRadius: const BorderRadius.only(
                            topLeft: Radius.circular(20),
                            topRight: Radius.circular(7)))),
                Padding(
                    padding: const EdgeInsets.fromLTRB(13, 12, 13, 13),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(children: [
                            Container(
                              width: 32,
                              height: 32,
                              alignment: Alignment.center,
                              decoration: BoxDecoration(
                                  color: accent,
                                  borderRadius: BorderRadius.circular(10),
                                  border: Border.all(color: AppColors.ink900)),
                              child: Text('0$index',
                                  style: const TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.w900,
                                      color: AppColors.ink900)),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                                child: Wrap(
                                    spacing: 6,
                                    runSpacing: 4,
                                    children: option.labels
                                        .map((e) => Text(label(e),
                                            style: const TextStyle(
                                                fontSize: 12,
                                                fontWeight: FontWeight.w900,
                                                color: AppColors.ink900)))
                                        .toList())),
                            Container(
                              width: 30,
                              height: 30,
                              decoration: const BoxDecoration(
                                  color: AppColors.brand900,
                                  shape: BoxShape.circle),
                              child: const Icon(Icons.arrow_outward_rounded,
                                  size: 15, color: AppColors.mint300),
                            ),
                          ]),
                          const SizedBox(height: 12),
                          Container(
                            padding: const EdgeInsets.all(11),
                            decoration: BoxDecoration(
                                color: AppColors.surfaceMint,
                                borderRadius: BorderRadius.circular(14)),
                            child: Row(
                                crossAxisAlignment: CrossAxisAlignment.end,
                                children: [
                                  Expanded(
                                      child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                        const Text('WAKTU',
                                            style: TextStyle(
                                                fontSize: 8,
                                                letterSpacing: .8,
                                                fontWeight: FontWeight.w800,
                                                color: AppColors.ink600)),
                                        const SizedBox(height: 2),
                                        Text(formatDuration(option.durationS),
                                            style: const TextStyle(
                                                fontSize: 18,
                                                fontWeight: FontWeight.w900,
                                                color: AppColors.ink900))
                                      ])),
                                  Container(
                                      width: 1,
                                      height: 34,
                                      color: AppColors.stroke),
                                  const SizedBox(width: 12),
                                  Expanded(
                                      child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          children: [
                                        const Text('ESTIMASI DOSIS',
                                            style: TextStyle(
                                                fontSize: 8,
                                                letterSpacing: .8,
                                                fontWeight: FontWeight.w800,
                                                color: AppColors.ink600)),
                                        const SizedBox(height: 2),
                                        Text(formatDose(option.doseUg),
                                            style: const TextStyle(
                                                fontSize: 15,
                                                fontWeight: FontWeight.w900,
                                                color: AppColors.brand600))
                                      ]))
                                ]),
                          ),
                          const SizedBox(height: 11),
                          Text(
                              '$reduction · ${option.deltaDurationS > 0 ? '+${formatDuration(option.deltaDurationS)}' : 'tanpa tambahan waktu'}',
                              style: const TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w800,
                                  color: AppColors.ink900)),
                          const SizedBox(height: 9),
                          ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: LinearProgressIndicator(
                                  minHeight: 5,
                                  value: (option.doseUg / 35)
                                      .clamp(0, 1)
                                      .toDouble(),
                                  backgroundColor: AppColors.stroke,
                                  color: AppColors.brand600)),
                          const SizedBox(height: 7),
                          Text(
                              'Rentang ${formatDose(option.doseP10)}–${formatDose(option.doseP90)} · ${option.transfers} transit',
                              style: const TextStyle(
                                  fontSize: 9.5, color: AppColors.ink600)),
                        ])),
              ])),
        ));
  }
}

class _ComparisonSection extends StatelessWidget {
  const _ComparisonSection({this.motorcycle, this.car});
  final VehicleComparison? motorcycle;
  final VehicleComparison? car;
  @override
  Widget build(BuildContext context) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SizedBox(height: 10),
        const Row(children: [
          Text('PEMBANDING PRIBADI',
              style: TextStyle(
                  fontSize: 9, letterSpacing: .8, fontWeight: FontWeight.w900)),
          SizedBox(width: 8),
          Expanded(child: Divider()),
        ]),
        const SizedBox(height: 10),
        Container(
            decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(20),
                    topRight: Radius.circular(8),
                    bottomLeft: Radius.circular(8),
                    bottomRight: Radius.circular(20)),
                border: Border.all(color: AppColors.stroke)),
            child: Column(children: [
              _VehicleRow(
                  icon: Icons.two_wheeler, name: 'Motor', value: motorcycle),
              const Divider(height: 1),
              _VehicleRow(
                  icon: Icons.directions_car_outlined,
                  name: 'Mobil',
                  value: car)
            ])),
      ]);
}

class _VehicleRow extends StatelessWidget {
  const _VehicleRow(
      {required this.icon, required this.name, required this.value});
  final IconData icon;
  final String name;
  final VehicleComparison? value;
  @override
  Widget build(BuildContext context) => Padding(
      padding: const EdgeInsets.all(12),
      child: Row(children: [
        Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
                color: AppColors.surfaceSky,
                borderRadius: BorderRadius.circular(9)),
            child: Icon(icon, size: 17, color: AppColors.brand600)),
        const SizedBox(width: 9),
        Expanded(
            child: Text(name,
                style: const TextStyle(
                    fontSize: 10.5, fontWeight: FontWeight.w800))),
        if (value == null)
          const Text('Tidak tersedia', style: TextStyle(fontSize: 9))
        else
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(
                '${formatDuration(value!.durationS)} · ${formatDose(value!.doseUg)}',
                style: const TextStyle(fontWeight: FontWeight.w700)),
            Text(
                'Rentang ${value!.doseP10.toStringAsFixed(1)}–${value!.doseP90.toStringAsFixed(1)} µg',
                style: const TextStyle(fontSize: 11, color: AppColors.ink600))
          ])
      ]));
}

class DetailScreen extends ConsumerWidget {
  const DetailScreen({super.key, required this.optionId});
  final String optionId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final result = ref.watch(planProvider).valueOrNull;
    if (result == null) {
      return const Scaffold(body: Center(child: Text('Rute tidak tersedia.')));
    }
    final option = result.options.firstWhere((item) => item.id == optionId,
        orElse: () => result.options.first);
    return Scaffold(
      appBar: const HirupAppBar(section: 'DETAIL RUTE', code: '07'),
      bottomNavigationBar: SafeArea(
          child: Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                  color: Colors.white,
                  border: Border(top: BorderSide(color: AppColors.stroke))),
              child: FilledButton.icon(
                  onPressed: () {
                    ref.read(selectedRouteIdProvider.notifier).state =
                        option.id;
                    context.push('/trip/active');
                  },
                  icon: const Icon(Icons.navigation_outlined),
                  label: const Text('Mulai perjalanan')))),
      body: Column(children: [
        Expanded(
            child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 30),
                children: [
              AirMapCard(
                  origin: option.legs.isEmpty ? null : option.legs.first.from,
                  destination: option.legs.isEmpty ? null : option.legs.last.to,
                  route: option),
              const SizedBox(height: 20),
              Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                Expanded(
                    child: Text(formatDuration(option.durationS),
                        style: Theme.of(context).textTheme.headlineMedium)),
                Text(formatDose(option.doseUg),
                    style: const TextStyle(
                        fontSize: 25,
                        fontWeight: FontWeight.w800,
                        color: AppColors.brand600))
              ]),
              const SizedBox(height: 5),
              Text(
                  '${formatTime(option.departAt)}–${formatTime(option.arriveAt)} · ${(option.distanceM / 1000).toStringAsFixed(1)} km · ${option.transfers} transit',
                  style: const TextStyle(color: AppColors.ink600)),
              const SizedBox(height: 16),
              Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                      color: AppColors.surfaceMint,
                      borderRadius: BorderRadius.circular(18)),
                  child: Text(
                      'Estimasi dosis ${formatDose(option.doseUg)} dengan rentang ${formatDose(option.doseP10)} sampai ${formatDose(option.doseP90)}.',
                      style: const TextStyle(fontWeight: FontWeight.w700))),
              const SizedBox(height: 24),
              Row(children: [
                Expanded(
                    child: Text('Cerita perjalanan',
                        style: Theme.of(context).textTheme.titleLarge)),
                TextButton(
                    onPressed: () => context.push('/plan/departure'),
                    child: const Text('Cek jam lain'))
              ]),
              const SizedBox(height: 10),
              ...option.legs.asMap().entries.map((entry) => _LegTile(
                  leg: entry.value, last: entry.key == option.legs.length - 1)),
            ]))
      ]),
    );
  }
}

class _LegTile extends StatelessWidget {
  const _LegTile({required this.leg, required this.last});
  final TripLeg leg;
  final bool last;
  IconData get icon => switch (leg.mode) {
        'WALK' => Icons.directions_walk,
        'BICYCLE' => Icons.pedal_bike,
        'BUS' => Icons.directions_bus,
        'SUBWAY' || 'RAIL' => Icons.train,
        'WAIT' => Icons.schedule,
        _ => Icons.route
      };
  @override
  Widget build(BuildContext context) => IntrinsicHeight(
          child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        SizedBox(
            width: 44,
            child: Column(children: [
              Container(
                  width: 38,
                  height: 38,
                  decoration: const BoxDecoration(
                      color: AppColors.brand100, shape: BoxShape.circle),
                  child: Icon(icon, size: 20, color: AppColors.brand600)),
              if (!last)
                Expanded(child: Container(width: 2, color: AppColors.stroke))
            ])),
        const SizedBox(width: 10),
        Expanded(
            child: Padding(
                padding: const EdgeInsets.only(bottom: 22),
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                          '${leg.routeName ?? _modeLabel(leg.mode)} · ${formatDuration(leg.durationS)}',
                          style: const TextStyle(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 4),
                      Text('${leg.from.name} → ${leg.to.name}',
                          style: const TextStyle(color: AppColors.ink600)),
                      const SizedBox(height: 6),
                      Text(
                          'Estimasi ${formatDose(leg.doseUg)} · PM2.5 ${formatPm25(leg.meanPm25)}',
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.brand800))
                    ]))),
      ]));
  String _modeLabel(String value) => switch (value) {
        'WALK' => 'Jalan kaki',
        'WAIT' => 'Menunggu',
        'BICYCLE' => 'Sepeda',
        'BUS' => 'Bus',
        'SUBWAY' => 'MRT',
        'RAIL' => 'Kereta',
        _ => value
      };
}

class DepartureScreen extends ConsumerWidget {
  const DepartureScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final advice = ref.watch(departureAdviceProvider);
    return Scaffold(
        appBar: const HirupAppBar(section: 'SARAN WAKTU', code: '08'),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          const PageHeader(
              eyebrow: 'Fitur tahap berikutnya',
              title: 'Geser waktu, lihat bedanya.',
              subtitle:
                  'Saran akan memakai slot 15 menit dari endpoint departure-advice tanpa menebak dosis di perangkat.'),
          const SizedBox(height: 24),
          advice.when(
            loading: () => const Center(child: CircularProgressIndicator()),
            error: (error, _) => ErrorPanel(
                message: error.toString(),
                onRetry: () => ref.invalidate(departureAdviceProvider)),
            data: (value) => value.slots.isEmpty
                ? Container(
                    padding: const EdgeInsets.all(22),
                    decoration: BoxDecoration(
                        color: AppColors.surfaceSky,
                        borderRadius: BorderRadius.circular(24)),
                    child: Column(children: [
                      const Icon(Icons.schedule_outlined,
                          size: 48, color: AppColors.sky700),
                      const SizedBox(height: 12),
                      Text('Waktu saat ini ${formatTime(draft.departAt)}',
                          style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 8),
                      const Text('Belum ada slot valid untuk skenario ini.',
                          textAlign: TextAlign.center)
                    ]))
                : Column(
                    children: value.slots.map((slot) {
                    final best = value.bestSlot != null &&
                        slot.departAt.isAtSameMomentAs(value.bestSlot!);
                    return Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: Card(
                            child: ListTile(
                          leading: CircleAvatar(
                              backgroundColor: best
                                  ? AppColors.mint300
                                  : AppColors.surfaceSky,
                              child: Icon(best ? Icons.star : Icons.schedule,
                                  color: AppColors.brand800)),
                          title: Text(formatTime(slot.departAt),
                              style:
                                  const TextStyle(fontWeight: FontWeight.w800)),
                          subtitle: Text(
                              '${formatDuration(slot.durationS)} · rentang ${slot.doseP10.toStringAsFixed(1)}–${slot.doseP90.toStringAsFixed(1)} µg'),
                          trailing: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(formatDose(slot.doseUg),
                                    style: const TextStyle(
                                        fontWeight: FontWeight.w800)),
                                Text(
                                    '${slot.deltaDosePct > 0 ? '+' : ''}${slot.deltaDosePct.toStringAsFixed(0)}%',
                                    style: TextStyle(
                                        fontSize: 12,
                                        color: slot.deltaDosePct <= 0
                                            ? AppColors.brand600
                                            : AppColors.ink600))
                              ]),
                          onTap: () {
                            ref
                                .read(journeyDraftProvider.notifier)
                                .setTime(slot.departAt);
                            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                                content: Text(
                                    'Waktu ${formatTime(slot.departAt)} diterapkan.')));
                          },
                        )));
                  }).toList()),
          ),
        ]));
  }
}

class ActiveTripScreen extends ConsumerStatefulWidget {
  const ActiveTripScreen({super.key});
  @override
  ConsumerState<ActiveTripScreen> createState() => _ActiveTripScreenState();
}

class _ActiveTripScreenState extends ConsumerState<ActiveTripScreen> {
  int currentLeg = 0;
  @override
  Widget build(BuildContext context) {
    final option = ref.watch(selectedRouteProvider);
    final result = ref.watch(planProvider).valueOrNull;
    if (option == null || result == null) {
      return const Scaffold(
          body: Center(child: Text('Pilih rute terlebih dahulu.')));
    }
    final legIndex =
        currentLeg >= option.legs.length ? option.legs.length - 1 : currentLeg;
    final leg = option.legs[legIndex];
    return Scaffold(
        body: SafeArea(
            child: Column(children: [
      Padding(
          padding: const EdgeInsets.fromLTRB(8, 10, 14, 10),
          child: Row(children: [
            IconButton(
                onPressed: () => context.pop(), icon: const Icon(Icons.close)),
            const SizedBox(width: 2),
            const Expanded(
                child:
                    HirupBrandHeader(section: 'PERJALANAN AKTIF', code: '09'))
          ])),
      Expanded(
          child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: SingleChildScrollView(
                  child: AirMapCard(
                      origin: option.legs.first.from,
                      destination: option.legs.last.to,
                      route: option,
                      highlightLeg: legIndex)))),
      Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(20, 22, 20, 16),
          decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(28))),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Langkah ${currentLeg + 1} dari ${option.legs.length}',
                style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.brand600,
                    fontWeight: FontWeight.w800)),
            const SizedBox(height: 7),
            Text('${leg.from.name} → ${leg.to.name}',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
                '${formatDuration(leg.durationS)} · estimasi ${formatDose(leg.doseUg)}',
                style: const TextStyle(color: AppColors.ink600)),
            const SizedBox(height: 18),
            SizedBox(
                width: double.infinity,
                child: FilledButton(
                    onPressed: () {
                      if (currentLeg < option.legs.length - 1) {
                        setState(() => currentLeg++);
                        return;
                      }
                      ref.read(historyProvider.notifier).save(
                          option, ref.read(journeyDraftProvider),
                          isDemo: result.isDemo);
                      showDialog<void>(
                          context: context,
                          builder: (dialogContext) => AlertDialog(
                                  title: const Text('Perjalanan disimpan'),
                                  content: const Text(
                                      'Ringkasan tersimpan lokal di perangkat.'),
                                  actions: [
                                    FilledButton(
                                        onPressed: () {
                                          Navigator.pop(dialogContext);
                                          context.go('/history');
                                        },
                                        child: const Text('Lihat riwayat'))
                                  ]));
                    },
                    child: Text(currentLeg < option.legs.length - 1
                        ? 'Langkah berikutnya'
                        : 'Selesaikan & simpan'))),
          ])),
    ])));
  }
}
