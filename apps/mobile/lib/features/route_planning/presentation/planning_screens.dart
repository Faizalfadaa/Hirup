import 'package:flutter/material.dart';
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
      appBar: const HirupAppBar(section: 'ATUR PERJALANAN', code: '05'),
      bottomNavigationBar: SafeArea(
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 12),
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(top: BorderSide(color: AppColors.stroke)),
          ),
          child: FilledButton(
            onPressed: () {
              ref.read(planProvider.notifier).load();
              context.push('/plan/results');
            },
            child: const Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('LIHAT PILIHAN RUTE'),
                SizedBox(width: 9),
                Icon(Icons.arrow_forward_rounded, size: 19),
              ],
            ),
          ),
        ),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
        children: [
          _ExpandedJourneyCard(draft: draft),
          const SizedBox(height: 20),
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
                  Text('Pilih moda perjalanan',
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontSize: 19)),
                  const SizedBox(height: 4),
                  const Text(
                    'Estimasi mempertimbangkan udara, waktu, dan profilmu.',
                    style: TextStyle(fontSize: 11, color: AppColors.ink600),
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
                  const SizedBox(height: 18),
                  Row(children: [
                    Expanded(
                      child: Text('Preferensi rute',
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(fontSize: 16)),
                    ),
                    Text(
                        '${(draft.maxWalkM / 1000).toStringAsFixed(draft.maxWalkM % 1000 == 0 ? 0 : 1)} km jalan',
                        style: const TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            color: AppColors.brand600)),
                  ]),
                  const SizedBox(height: 10),
                  _PreferencePanel(draft: draft, ref: ref),
                  const SizedBox(height: 14),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppColors.surfaceSky,
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: AppColors.stroke),
                    ),
                    child: const Row(children: [
                      Icon(Icons.health_and_safety_outlined,
                          size: 20, color: AppColors.sky700),
                      SizedBox(width: 11),
                      Expanded(
                        child: Text(
                          'Rute Bersih Berbasis Sensor membandingkan estimasi paparan, bukan hanya jarak.',
                          style: TextStyle(
                              fontSize: 10.5, color: AppColors.ink700),
                        ),
                      ),
                    ]),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
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

class _PreferencePanel extends StatelessWidget {
  const _PreferencePanel({required this.draft, required this.ref});
  final JourneyDraft draft;
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(
          color: AppColors.surfaceMint,
          borderRadius: BorderRadius.circular(19),
          border: Border.all(color: AppColors.brand100),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('PROFIL PAPARAN',
              style: TextStyle(
                  fontSize: 8,
                  letterSpacing: .8,
                  color: AppColors.brand600,
                  fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          SegmentedButton<Sensitivity>(
            showSelectedIcon: false,
            segments: const [
              ButtonSegment(value: Sensitivity.umum, label: Text('Umum')),
              ButtonSegment(
                  value: Sensitivity.rentan, label: Text('Lebih sensitif')),
            ],
            selected: {draft.sensitivity},
            onSelectionChanged: (selection) => ref
                .read(journeyDraftProvider.notifier)
                .setSensitivity(selection.first),
          ),
          const SizedBox(height: 13),
          const Text('BATAS JALAN KAKI',
              style: TextStyle(
                  fontSize: 8,
                  letterSpacing: .8,
                  color: AppColors.brand600,
                  fontWeight: FontWeight.w900)),
          const SizedBox(height: 7),
          Wrap(
            spacing: 7,
            children: [500, 1000, 1500]
                .map((meters) => ChoiceChip(
                      label: Text(meters < 1000
                          ? '$meters m'
                          : '${meters ~/ 1000}${meters == 1500 ? ',5' : ''} km'),
                      selected: draft.maxWalkM == meters,
                      onSelected: (_) => ref
                          .read(journeyDraftProvider.notifier)
                          .setMaxWalk(meters),
                    ))
                .toList(),
          ),
        ]),
      );
}

class ResultsScreen extends ConsumerWidget {
  const ResultsScreen({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final state = ref.watch(planProvider);
    return Scaffold(
        appBar: const HirupAppBar(section: 'PILIHAN RUTE', code: '06'),
        body: state.when(
          loading: () => const _PlanningLoader(),
          error: (error, _) =>
              ListView(padding: const EdgeInsets.all(20), children: [
            const SizedBox(height: 100),
            ErrorPanel(
                message: error.toString(),
                onRetry: ref.read(planProvider.notifier).load)
          ]),
          data: (result) {
            if (result == null)
              return Center(
                  child: FilledButton(
                      onPressed: ref.read(planProvider.notifier).load,
                      child: const Text('Muat pilihan rute')));
            return Column(children: [
              if (result.isDemo) const DemoBanner(),
              Expanded(
                  child: ListView(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 36),
                      children: [
                    _JourneyCapsule(draft: draft),
                    const SizedBox(height: 14),
                    const AirMapCard(compact: true),
                    const SizedBox(height: 24),
                    const PageHeader(
                        eyebrow: 'Hasil perjalanan',
                        title: 'Pilih perjalanan yang paling pas.',
                        subtitle:
                            'Bandingkan udara yang dihirup dan menit yang dibutuhkan.'),
                    const SizedBox(height: 18),
                    Row(children: [
                      QualityBadge(quality: result.dataQuality),
                      const SizedBox(width: 8),
                      Text(
                          '${formatTime(result.freshness.validHour)} · ${result.freshness.confidence}',
                          style: const TextStyle(
                              fontSize: 12, color: AppColors.ink600))
                    ]),
                    const SizedBox(height: 16),
                    ...result.options.asMap().entries.map((entry) => Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: _RouteCard(
                            index: entry.key + 1,
                            option: entry.value,
                            onTap: () {
                              ref.read(selectedRouteIdProvider.notifier).state =
                                  entry.value.id;
                              context.push('/plan/detail/${entry.value.id}');
                            }))),
                    _ComparisonSection(
                        motorcycle: result.motorcycle, car: result.car),
                    const SizedBox(height: 18),
                    Text(result.disclaimer,
                        style: const TextStyle(
                            fontSize: 12, color: AppColors.ink600)),
                  ])),
            ]);
          },
        ));
  }
}

class _PlanningLoader extends StatelessWidget {
  const _PlanningLoader();
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

class _JourneyCapsule extends StatelessWidget {
  const _JourneyCapsule({required this.draft});
  final JourneyDraft draft;
  @override
  Widget build(BuildContext context) => Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.stroke)),
      child: Row(children: [
        const Icon(Icons.trip_origin, size: 18, color: AppColors.brand600),
        const SizedBox(width: 8),
        Expanded(
            child: Text(draft.origin.name, overflow: TextOverflow.ellipsis)),
        const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Icon(Icons.arrow_forward, size: 18)),
        const Icon(Icons.location_on, size: 18, color: AppColors.brand600),
        const SizedBox(width: 6),
        Expanded(
            child:
                Text(draft.destination.name, overflow: TextOverflow.ellipsis)),
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
              borderRadius: BorderRadius.circular(22),
              border: Border.all(color: AppColors.ink900, width: 1.2),
              boxShadow: const [
                BoxShadow(color: Color(0x16073C3B), offset: Offset(4, 5))
              ]),
          child: InkWell(
              borderRadius: BorderRadius.circular(22),
              onTap: onTap,
              child: Column(children: [
                Container(
                    padding: const EdgeInsets.fromLTRB(16, 12, 12, 12),
                    decoration: BoxDecoration(
                        color: accent,
                        borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(21))),
                    child: Row(children: [
                      Text('0$index',
                          style: const TextStyle(
                              fontSize: 30,
                              height: 1,
                              fontWeight: FontWeight.w900,
                              color: AppColors.ink900)),
                      const SizedBox(width: 12),
                      Expanded(
                          child: Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: option.labels
                                  .map((e) => Text(label(e).toUpperCase(),
                                      style: const TextStyle(
                                          fontSize: 11,
                                          letterSpacing: .7,
                                          fontWeight: FontWeight.w900,
                                          color: AppColors.ink900)))
                                  .toList())),
                      const Icon(Icons.arrow_outward, color: AppColors.ink900),
                    ])),
                Padding(
                    padding: const EdgeInsets.all(17),
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Expanded(
                                    child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                      const Text('WAKTU',
                                          style: TextStyle(
                                              fontSize: 10,
                                              letterSpacing: .8,
                                              fontWeight: FontWeight.w800,
                                              color: AppColors.ink600)),
                                      Text(formatDuration(option.durationS),
                                          style: const TextStyle(
                                              fontSize: 28,
                                              fontWeight: FontWeight.w900,
                                              color: AppColors.ink900))
                                    ])),
                                Container(
                                    width: 1,
                                    height: 44,
                                    color: AppColors.stroke),
                                const SizedBox(width: 16),
                                Expanded(
                                    child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                      const Text('ESTIMASI DOSIS',
                                          style: TextStyle(
                                              fontSize: 10,
                                              letterSpacing: .8,
                                              fontWeight: FontWeight.w800,
                                              color: AppColors.ink600)),
                                      Text(formatDose(option.doseUg),
                                          style: const TextStyle(
                                              fontSize: 22,
                                              fontWeight: FontWeight.w900,
                                              color: AppColors.brand600))
                                    ]))
                              ]),
                          const SizedBox(height: 13),
                          Text(
                              '$reduction · ${option.deltaDurationS > 0 ? '+${formatDuration(option.deltaDurationS)}' : 'tanpa tambahan waktu'}',
                              style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                  color: AppColors.ink900)),
                          const SizedBox(height: 12),
                          ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: LinearProgressIndicator(
                                  minHeight: 7,
                                  value: (option.doseUg / 35)
                                      .clamp(0, 1)
                                      .toDouble(),
                                  backgroundColor: AppColors.stroke,
                                  color: AppColors.brand600)),
                          const SizedBox(height: 9),
                          Text(
                              'Rentang ${formatDose(option.doseP10)}–${formatDose(option.doseP90)} · ${option.transfers} transit',
                              style: const TextStyle(
                                  fontSize: 12, color: AppColors.ink600)),
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
        Text('Pembanding kendaraan pribadi',
            style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 10),
        Card(
            child: Column(children: [
          _VehicleRow(
              icon: Icons.two_wheeler, name: 'Motor', value: motorcycle),
          const Divider(height: 1),
          _VehicleRow(
              icon: Icons.directions_car_outlined, name: 'Mobil', value: car)
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
      padding: const EdgeInsets.all(16),
      child: Row(children: [
        Icon(icon, color: AppColors.ink600),
        const SizedBox(width: 12),
        Expanded(
            child: Text(name,
                style: const TextStyle(fontWeight: FontWeight.w700))),
        if (value == null)
          const Text('Tidak tersedia')
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
    if (result == null)
      return const Scaffold(body: Center(child: Text('Rute tidak tersedia.')));
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
        if (result.isDemo) const DemoBanner(),
        Expanded(
            child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 12, 20, 30),
                children: [
              const AirMapCard(compact: true),
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
    if (option == null || result == null)
      return const Scaffold(
          body: Center(child: Text('Pilih rute terlebih dahulu.')));
    final legIndex =
        currentLeg >= option.legs.length ? option.legs.length - 1 : currentLeg;
    final leg = option.legs[legIndex];
    return Scaffold(
        body: SafeArea(
            child: Column(children: [
      if (result.isDemo) const DemoBanner(),
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
      const Expanded(
          child: Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: AirMapCard())),
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
