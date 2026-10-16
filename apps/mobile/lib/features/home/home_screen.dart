import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/theme/app_theme.dart';
import '../../core/utils/formatters.dart';
import '../../shared/widgets.dart';
import '../route_planning/domain/models.dart';
import '../route_planning/presentation/providers.dart';

const _greenPlaces = <_GreenPlace>[
  _GreenPlace(
    name: 'Taman Suropati',
    area: 'Menteng, Jakarta Pusat',
    asset: 'assets/images/park-suropati.png',
    point: PlacePoint(name: 'Taman Suropati', lat: -6.1994, lon: 106.8326),
  ),
  _GreenPlace(
    name: 'Taman Menteng',
    area: 'Menteng, Jakarta Pusat',
    asset: 'assets/images/park-menteng.png',
    point: PlacePoint(name: 'Taman Menteng', lat: -6.1964, lon: 106.8294),
  ),
  _GreenPlace(
    name: 'Taman Situ Lembang',
    area: 'Menteng, Jakarta Pusat',
    asset: 'assets/images/park-situ-lembang.png',
    point: PlacePoint(name: 'Taman Situ Lembang', lat: -6.1979, lon: 106.8351),
  ),
];

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final draft = ref.watch(journeyDraftProvider);
    final demo = ref.watch(demoModeProvider);
    final air = ref.watch(airPointProvider);
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        body: Column(children: [
          Expanded(
              child: CustomScrollView(slivers: [
            SliverToBoxAdapter(
                child: _DashboardHero(
                    air: air,
                    location: draft.origin.name,
                    onLongPress: () =>
                        ref.read(demoModeProvider.notifier).state = !demo)),
            SliverPadding(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
                sliver: SliverList.list(children: [
                  Row(children: [
                    Expanded(
                        child: Text('Area perjalanan',
                            style: Theme.of(context)
                                .textTheme
                                .titleMedium
                                ?.copyWith(fontSize: 16))),
                    TextButton.icon(
                        onPressed: () {},
                        icon: const Icon(Icons.layers_outlined, size: 16),
                        label: const Text('Lapisan'))
                  ]),
                  const SizedBox(height: 6),
                  AirMapCard(
                      compact: true,
                      origin: draft.origin,
                      destination: draft.destination),
                  const SizedBox(height: 20),
                  Text('Mau ke mana?',
                      style: Theme.of(context)
                          .textTheme
                          .titleMedium
                          ?.copyWith(fontSize: 16)),
                  const SizedBox(height: 10),
                  _JourneyCard(draft: draft),
                  const SizedBox(height: 28),
                  _GreenPlacesSection(ref: ref),
                ])),
          ])),
        ]),
      ),
    );
  }
}

class _GreenPlace {
  const _GreenPlace(
      {required this.name,
      required this.area,
      required this.asset,
      required this.point});
  final String name;
  final String area;
  final String asset;
  final PlacePoint point;
}

class _GreenPlacesSection extends StatelessWidget {
  const _GreenPlacesSection({required this.ref});
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.fromLTRB(16, 16, 0, 15),
        decoration: BoxDecoration(
          color: AppColors.brand900,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(30),
            topRight: Radius.circular(10),
            bottomLeft: Radius.circular(10),
            bottomRight: Radius.circular(30),
          ),
          border: Border.all(color: AppColors.ink900, width: 1.2),
          boxShadow: const [
            BoxShadow(color: Color(0x26073C3B), offset: Offset(5, 6))
          ],
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                width: 38,
                height: 38,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                    color: AppColors.mint300,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.ink900)),
                child: const Icon(Icons.park_rounded,
                    size: 21, color: AppColors.brand900),
              ),
              const SizedBox(width: 11),
              const Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('KABUR SEBENTAR',
                          style: TextStyle(
                              color: AppColors.mint300,
                              fontSize: 8,
                              letterSpacing: 1.2,
                              fontWeight: FontWeight.w900)),
                      SizedBox(height: 4),
                      Text('Hijau di tengah kota.',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              height: 1.1,
                              fontWeight: FontWeight.w900)),
                    ]),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: .1),
                    borderRadius: BorderRadius.circular(99),
                    border: Border.all(color: Colors.white24)),
                child: const Text('03 TEMPAT',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 7,
                        letterSpacing: .6,
                        fontWeight: FontWeight.w900)),
              ),
            ]),
          ),
          const SizedBox(height: 9),
          Padding(
            padding: const EdgeInsets.only(right: 20),
            child: Text(
              'Geser, pilih taman, lalu kami carikan jalan dengan paparan lebih rendah.',
              style: TextStyle(
                  color: Colors.white.withValues(alpha: .66),
                  fontSize: 10,
                  height: 1.4),
            ),
          ),
          const SizedBox(height: 15),
          SizedBox(
            height: 178,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.only(right: 16),
              itemCount: _greenPlaces.length,
              separatorBuilder: (_, __) => const SizedBox(width: 11),
              itemBuilder: (context, index) => SizedBox(
                width: 232,
                child: _GreenPlaceCard(
                  place: _greenPlaces[index],
                  variant: index,
                  onTap: () {
                    ref
                        .read(journeyDraftProvider.notifier)
                        .setDestination(_greenPlaces[index].point);
                    context.push('/plan/mode');
                  },
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Row(children: [
              ...List.generate(
                  3,
                  (index) => Container(
                        width: index == 0 ? 22 : 6,
                        height: 5,
                        margin: const EdgeInsets.only(right: 5),
                        decoration: BoxDecoration(
                            color:
                                index == 0 ? AppColors.mint300 : Colors.white24,
                            borderRadius: BorderRadius.circular(99)),
                      )),
              const Spacer(),
              Text('GESER UNTUK LIHAT',
                  style: TextStyle(
                      color: Colors.white.withValues(alpha: .5),
                      fontSize: 7,
                      letterSpacing: .8,
                      fontWeight: FontWeight.w800)),
              const SizedBox(width: 5),
              const Icon(Icons.arrow_forward_rounded,
                  size: 13, color: AppColors.mint300),
            ]),
          ),
        ]),
      );
}

class _GreenPlaceCard extends StatelessWidget {
  const _GreenPlaceCard(
      {required this.place, required this.variant, required this.onTap});
  final _GreenPlace place;
  final int variant;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Material(
        color: AppColors.paper,
        clipBehavior: Clip.antiAlias,
        borderRadius: const BorderRadius.only(
          topLeft: Radius.circular(22),
          topRight: Radius.circular(8),
          bottomLeft: Radius.circular(8),
          bottomRight: Radius.circular(22),
        ),
        child: InkWell(
          onTap: onTap,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(22),
            topRight: Radius.circular(8),
            bottomLeft: Radius.circular(8),
            bottomRight: Radius.circular(22),
          ),
          child: Container(
            decoration: BoxDecoration(
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(22),
                topRight: Radius.circular(8),
                bottomLeft: Radius.circular(8),
                bottomRight: Radius.circular(22),
              ),
              border: Border.all(color: AppColors.ink900, width: 1.1),
            ),
            child: Column(children: [
              Expanded(
                child: Stack(fit: StackFit.expand, children: [
                  Image.asset(
                    place.asset,
                    fit: BoxFit.cover,
                    cacheWidth: 640,
                    filterQuality: FilterQuality.medium,
                  ),
                  const DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topCenter,
                        end: Alignment.bottomCenter,
                        colors: [Colors.transparent, Color(0x26073C3B)],
                      ),
                    ),
                  ),
                  Positioned(
                    left: 10,
                    top: 9,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 7, vertical: 4),
                      decoration: BoxDecoration(
                          color: AppColors.sun300,
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppColors.ink900)),
                      child: Text('0${variant + 1}',
                          style: const TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w900,
                              color: AppColors.ink900)),
                    ),
                  ),
                ]),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 9, 10),
                child: Row(children: [
                  Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(place.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.w900,
                                  color: AppColors.ink900)),
                          const SizedBox(height: 4),
                          Text(place.area,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                  fontSize: 9, color: AppColors.ink600)),
                        ]),
                  ),
                  Container(
                    width: 31,
                    height: 31,
                    decoration: const BoxDecoration(
                        color: AppColors.brand900, shape: BoxShape.circle),
                    child: const Icon(Icons.arrow_outward_rounded,
                        size: 16, color: AppColors.mint300),
                  ),
                ]),
              ),
            ]),
          ),
        ),
      );
}

class _DashboardHero extends StatelessWidget {
  const _DashboardHero(
      {required this.air, required this.location, required this.onLongPress});

  final AsyncValue<AirPoint> air;
  final String location;
  final VoidCallback onLongPress;

  _AirMood _mood(double pm25) {
    if (pm25 <= 15.5) {
      return const _AirMood(
          asset: 'assets/images/air-good.png',
          label: 'UDARA BAIK',
          message: 'Waktu yang nyaman untuk bergerak.',
          accent: AppColors.mint300);
    }
    if (pm25 <= 55.4) {
      return const _AirMood(
          asset: 'assets/images/air-moderate.png',
          label: 'UDARA SEDANG',
          message: 'Pilih rute yang lebih hijau hari ini.',
          accent: AppColors.sun300);
    }
    return const _AirMood(
        asset: 'assets/images/air-unhealthy.png',
        label: 'UDARA BURUK',
        message: 'Kurangi paparan dan perjalanan panjang.',
        accent: Color(0xFFFF9B83));
  }

  @override
  Widget build(BuildContext context) {
    final value = air.valueOrNull;
    final mood = _mood(value?.p50 ?? 30);
    return GestureDetector(
      onLongPress: onLongPress,
      child: ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(30)),
        child: SizedBox(
          height: 286,
          child: Stack(fit: StackFit.expand, children: [
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 500),
              child: Image.asset(mood.asset,
                  key: ValueKey(mood.asset),
                  fit: BoxFit.cover,
                  cacheWidth: 900,
                  filterQuality: FilterQuality.low,
                  gaplessPlayback: true),
            ),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  stops: [0, .45, 1],
                  colors: [
                    Color(0xD9073C3B),
                    Color(0x7507564F),
                    Color(0xEB07302F),
                  ],
                ),
              ),
            ),
            SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
                child: Column(children: [
                  Stack(alignment: Alignment.center, children: [
                    const Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          HirupLogoMark(size: 30, dark: false),
                          SizedBox(width: 8),
                          Text('hirup.',
                              style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 19,
                                  height: 1,
                                  letterSpacing: -.5,
                                  fontWeight: FontWeight.w900)),
                        ]),
                    Align(
                      alignment: Alignment.centerRight,
                      child: Container(
                        width: 8,
                        height: 8,
                        decoration: BoxDecoration(
                            color: mood.accent,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(color: mood.accent, blurRadius: 8)
                            ]),
                      ),
                    ),
                  ]),
                  const SizedBox(height: 7),
                  Text(location.toUpperCase(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                          color: Colors.white.withValues(alpha: .72),
                          fontSize: 8,
                          letterSpacing: 1.15,
                          fontWeight: FontWeight.w800)),
                  const Spacer(),
                  Container(
                    padding: const EdgeInsets.fromLTRB(15, 13, 14, 13),
                    decoration: BoxDecoration(
                      color: const Color(0xE6103F3C),
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(
                          color: Colors.white.withValues(alpha: .28)),
                      boxShadow: const [
                        BoxShadow(
                            color: Color(0x3D001F1D),
                            blurRadius: 16,
                            offset: Offset(0, 7))
                      ],
                    ),
                    child: air.when(
                      loading: () => const SizedBox(
                          height: 62,
                          child: Center(
                              child: CircularProgressIndicator(
                                  color: AppColors.mint300, strokeWidth: 2.5))),
                      error: (_, __) => const SizedBox(
                          height: 62,
                          child: Row(children: [
                            Icon(Icons.cloud_off_outlined, color: Colors.white),
                            SizedBox(width: 10),
                            Text('Data udara belum tersedia',
                                style: TextStyle(color: Colors.white))
                          ])),
                      data: (airValue) => Row(children: [
                        Expanded(
                          child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(children: [
                                  Container(
                                      width: 7,
                                      height: 7,
                                      decoration: BoxDecoration(
                                          color: mood.accent,
                                          shape: BoxShape.circle)),
                                  const SizedBox(width: 7),
                                  Text(mood.label,
                                      style: TextStyle(
                                          color: mood.accent,
                                          fontSize: 9,
                                          letterSpacing: .9,
                                          fontWeight: FontWeight.w900)),
                                ]),
                                const SizedBox(height: 7),
                                Text(mood.message,
                                    style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 12,
                                        fontWeight: FontWeight.w700)),
                                const SizedBox(height: 4),
                                Text(
                                    'Diperbarui ${DateFormat('HH:mm').format(airValue.validHour.toLocal())} · ${airValue.quality == 'real' ? 'Model langsung' : 'Perkiraan data nyata'}',
                                    style: TextStyle(
                                        color:
                                            Colors.white.withValues(alpha: .62),
                                        fontSize: 8.5)),
                              ]),
                        ),
                        const SizedBox(width: 12),
                        Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(airValue.p50.toStringAsFixed(0),
                                  style: const TextStyle(
                                      color: Colors.white,
                                      fontSize: 34,
                                      height: .9,
                                      fontWeight: FontWeight.w900)),
                              const SizedBox(height: 5),
                              Text('PM2.5  µg/m³',
                                  style: TextStyle(
                                      color:
                                          Colors.white.withValues(alpha: .72),
                                      fontSize: 9,
                                      fontWeight: FontWeight.w700)),
                            ]),
                      ]),
                    ),
                  ),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

class _AirMood {
  const _AirMood(
      {required this.asset,
      required this.label,
      required this.message,
      required this.accent});
  final String asset;
  final String label;
  final String message;
  final Color accent;
}

// Kept temporarily to avoid a noisy migration diff while the new dashboard
// header is evaluated on physical devices.
// ignore: unused_element
class _HomeHero extends StatelessWidget {
  const _HomeHero({required this.air});
  final AsyncValue<AirPoint> air;

  @override
  Widget build(BuildContext context) => Container(
        constraints: const BoxConstraints(minHeight: 126),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                AppColors.brand900,
                AppColors.brand600,
                Color(0xFF0B8073)
              ]),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
                color: AppColors.brand900.withValues(alpha: .13),
                blurRadius: 18,
                offset: const Offset(0, 8))
          ],
        ),
        child: Row(children: [
          Expanded(
              child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                const Text('RUTE + UDARA',
                    style: TextStyle(
                        fontSize: 9,
                        letterSpacing: 1,
                        fontWeight: FontWeight.w900,
                        color: AppColors.mint300)),
                const SizedBox(height: 7),
                const Text('Ke mana\nhari ini?',
                    style: TextStyle(
                        fontSize: 22,
                        height: 1.05,
                        fontWeight: FontWeight.w900,
                        color: Colors.white)),
                const SizedBox(height: 7),
                Text('Bandingkan napas dan waktu.',
                    style: TextStyle(
                        fontSize: 11,
                        color: Colors.white.withValues(alpha: .78))),
              ])),
          const SizedBox(width: 12),
          air.when(
            loading: () => const SizedBox(
                width: 82,
                child: Center(
                    child: CircularProgressIndicator(
                        color: AppColors.mint300, strokeWidth: 3))),
            error: (_, __) => Container(
                width: 82,
                height: 82,
                decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: .1),
                    shape: BoxShape.circle),
                child:
                    const Icon(Icons.cloud_off_outlined, color: Colors.white)),
            data: (value) => Container(
                width: 88,
                height: 88,
                decoration: BoxDecoration(
                    color: AppColors.sun300,
                    shape: BoxShape.circle,
                    border: Border.all(color: Colors.white, width: 3)),
                child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(value.p50.toStringAsFixed(0),
                          style: const TextStyle(
                              fontSize: 25,
                              height: 1,
                              fontWeight: FontWeight.w900,
                              color: AppColors.ink900)),
                      const SizedBox(height: 3),
                      const Text('µg/m³',
                          style: TextStyle(
                              fontSize: 9,
                              fontWeight: FontWeight.w800,
                              color: AppColors.ink700)),
                      const Text('ESTIMASI',
                          style: TextStyle(
                              fontSize: 7,
                              letterSpacing: .5,
                              fontWeight: FontWeight.w900,
                              color: AppColors.brand800))
                    ])),
          ),
        ]),
      );
}

class _JourneyCard extends ConsumerWidget {
  const _JourneyCard({required this.draft});
  final JourneyDraft draft;
  @override
  Widget build(BuildContext context, WidgetRef ref) => Container(
        decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppColors.ink900, width: 1.4),
            boxShadow: const [
              BoxShadow(
                  color: Color(0x14073C3B), blurRadius: 0, offset: Offset(5, 5))
            ]),
        child: Column(children: [
          Padding(
              padding: const EdgeInsets.fromLTRB(14, 11, 14, 9),
              child: Row(children: [
                Container(
                    width: 28,
                    height: 28,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                        color: AppColors.sun300,
                        borderRadius: BorderRadius.circular(8)),
                    child: const Text('A→B',
                        style: TextStyle(
                            fontSize: 9,
                            fontWeight: FontWeight.w900,
                            color: AppColors.ink900))),
                const SizedBox(width: 8),
                const Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      Text('TIKET PERJALANAN',
                          style: TextStyle(
                              fontSize: 9,
                              letterSpacing: .8,
                              fontWeight: FontWeight.w900,
                              color: AppColors.ink900)),
                      Text('Atur titik perjalanan',
                          style:
                              TextStyle(fontSize: 10, color: AppColors.ink600))
                    ])),
                const Text('JKT',
                    style: TextStyle(
                        fontSize: 10,
                        letterSpacing: 1.2,
                        fontWeight: FontWeight.w900,
                        color: AppColors.brand600)),
              ])),
          const _Perforation(),
          Padding(
              padding: const EdgeInsets.fromLTRB(13, 10, 13, 13),
              child: Column(children: [
                _PlaceField(
                    label: 'Asal',
                    place: draft.origin,
                    icon: Icons.trip_origin,
                    onTap: () => context.push('/place/origin')),
                SizedBox(
                    height: 32,
                    child: Row(children: [
                      const Expanded(child: Divider()),
                      IconButton(
                          tooltip: 'Tukar asal dan tujuan',
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints.tightFor(
                              width: 34, height: 30),
                          onPressed:
                              ref.read(journeyDraftProvider.notifier).swap,
                          icon: const Icon(Icons.swap_vert, size: 18)),
                      const Expanded(child: Divider())
                    ])),
                _PlaceField(
                    label: 'Tujuan',
                    place: draft.destination,
                    icon: Icons.location_on_outlined,
                    onTap: () => context.push('/place/destination')),
                if (!draft.origin.insideRoutingPilot ||
                    !draft.destination.insideRoutingPilot)
                  const Padding(
                    padding: EdgeInsets.only(top: 8),
                    child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(Icons.info_outline,
                              size: 16, color: AppColors.danger700),
                          SizedBox(width: 6),
                          Expanded(
                              child: Text(
                                  'Rute tersedia di koridor pilot Lebak Bulus–Kota. Kualitas udara di titik lain tetap bisa dilihat di peta.',
                                  style: TextStyle(
                                      fontSize: 11,
                                      color: AppColors.danger700))),
                        ]),
                  ),
                const SizedBox(height: 7),
                Row(children: [
                  const Icon(Icons.schedule, size: 17),
                  const SizedBox(width: 7),
                  Text('Berangkat ${formatTime(draft.departAt)}',
                      style: const TextStyle(
                          fontSize: 11, fontWeight: FontWeight.w700)),
                  const Spacer(),
                  TextButton(
                      style: TextButton.styleFrom(
                          minimumSize: const Size(42, 32),
                          padding: const EdgeInsets.symmetric(horizontal: 8)),
                      onPressed: () async {
                        final picked = await showTimePicker(
                            context: context,
                            initialTime:
                                TimeOfDay.fromDateTime(draft.departAt));
                        if (picked != null) {
                          ref.read(journeyDraftProvider.notifier).setTime(
                              DateTime(
                                  draft.departAt.year,
                                  draft.departAt.month,
                                  draft.departAt.day,
                                  picked.hour,
                                  picked.minute));
                        }
                      },
                      child: const Text('Ubah'))
                ]),
                const SizedBox(height: 4),
                SizedBox(
                    width: double.infinity,
                    height: 44,
                    child: FilledButton(
                        onPressed:
                            draft.origin.samePlaceAs(draft.destination) ||
                                    !draft.origin.insideRoutingPilot ||
                                    !draft.destination.insideRoutingPilot
                                ? null
                                : () => context.push('/plan/mode'),
                        child: const Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text('CARI RUTE',
                                  style: TextStyle(
                                      fontSize: 12,
                                      letterSpacing: .7,
                                      color: Colors.white)),
                              SizedBox(width: 8),
                              Icon(Icons.arrow_outward,
                                  size: 18, color: Colors.white)
                            ]))),
              ])),
        ]),
      );
}

class _PlaceField extends StatelessWidget {
  const _PlaceField(
      {required this.label,
      required this.place,
      required this.icon,
      required this.onTap});

  final String label;
  final PlacePoint place;
  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Semantics(
        button: true,
        label: '$label: ${place.name}. Ketuk untuk mengganti.',
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(14),
          child: InputDecorator(
            decoration: InputDecoration(
                labelText: label,
                prefixIcon: Icon(icon, size: 18),
                suffixIcon: const Icon(Icons.search, size: 18),
                contentPadding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                isDense: true),
            child: Text(place.name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: AppColors.ink900)),
          ),
        ),
      );
}

// ignore: unused_element
class _ModeShortcuts extends StatelessWidget {
  const _ModeShortcuts({required this.ref});
  final WidgetRef ref;

  @override
  Widget build(BuildContext context) {
    const items = <(PlanMode, IconData, String, Color)>[
      (
        PlanMode.transit,
        Icons.directions_transit,
        'Transit',
        AppColors.mint300
      ),
      (PlanMode.bike, Icons.pedal_bike, 'Sepeda', AppColors.sky300),
      (PlanMode.walk, Icons.directions_walk, 'Jalan', AppColors.sun300),
      (PlanMode.all, Icons.grid_view_rounded, 'Semua', AppColors.brand100),
    ];
    return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: items
            .map((item) => Expanded(
                    child: InkWell(
                  borderRadius: BorderRadius.circular(14),
                  onTap: () {
                    ref.read(journeyDraftProvider.notifier).setMode(item.$1);
                    context.push('/plan/mode');
                  },
                  child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Column(children: [
                        Container(
                            width: 48,
                            height: 48,
                            decoration: BoxDecoration(
                                color: item.$4,
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(
                                    color: AppColors.ink900, width: 1.1)),
                            child: Icon(item.$2,
                                size: 23, color: AppColors.ink900)),
                        const SizedBox(height: 6),
                        Text(item.$3,
                            style: const TextStyle(
                                fontSize: 10,
                                fontWeight: FontWeight.w700,
                                color: AppColors.ink900)),
                      ])),
                )))
            .toList());
  }
}

class _Perforation extends StatelessWidget {
  const _Perforation();
  @override
  Widget build(BuildContext context) => Row(children: [
        Transform.translate(
            offset: const Offset(-7, 0),
            child: Container(
                width: 14,
                height: 14,
                decoration: const BoxDecoration(
                    color: AppColors.paper,
                    shape: BoxShape.circle,
                    border: Border.fromBorderSide(
                        BorderSide(color: AppColors.ink900))))),
        Expanded(
            child: CustomPaint(
                size: const Size(double.infinity, 1), painter: _DashPainter())),
        Transform.translate(
            offset: const Offset(7, 0),
            child: Container(
                width: 14,
                height: 14,
                decoration: const BoxDecoration(
                    color: AppColors.paper,
                    shape: BoxShape.circle,
                    border: Border.fromBorderSide(
                        BorderSide(color: AppColors.ink900))))),
      ]);
}

class _DashPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppColors.stroke
      ..strokeWidth = 1.4;
    for (double x = 0; x < size.width; x += 8) {
      canvas.drawLine(Offset(x, 0),
          Offset((x + 4).clamp(0, size.width).toDouble(), 0), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
