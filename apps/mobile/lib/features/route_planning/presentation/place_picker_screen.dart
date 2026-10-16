import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/air_map.dart';
import '../../../shared/widgets.dart';
import '../data/geocoder.dart';
import '../domain/models.dart';
import 'providers.dart';

final geocoderProvider = Provider<Geocoder>((ref) => Geocoder());

/// FR-01: choose an origin or destination by search, GPS or a pin on the map.
class PlacePickerScreen extends ConsumerStatefulWidget {
  const PlacePickerScreen({super.key, required this.isOrigin});
  final bool isOrigin;
  @override
  ConsumerState<PlacePickerScreen> createState() => _PlacePickerScreenState();
}

class _PlacePickerScreenState extends ConsumerState<PlacePickerScreen> {
  final _query = TextEditingController();
  Timer? _debounce;
  List<PlacePoint> _results = const [];
  bool _searching = false;
  bool _locating = false;
  String? _error;

  @override
  void dispose() {
    _debounce?.cancel();
    _query.dispose();
    super.dispose();
  }

  void _onChanged(String text) {
    _debounce?.cancel();
    // Photon is fair-use: wait for a pause in typing instead of querying every key.
    _debounce = Timer(const Duration(milliseconds: 450), () => _search(text));
  }

  Future<void> _search(String text) async {
    if (text.trim().length < 3) {
      setState(() {
        _results = const [];
        _error = null;
        _searching = false;
      });
      return;
    }
    setState(() => _searching = true);
    try {
      final results = await ref.read(geocoderProvider).search(text);
      if (mounted && _query.text == text) {
        setState(() {
          _results = results;
          _error = null;
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error =
            'Pencarian belum berhasil. Periksa koneksi lalu coba lagi.');
      }
    } finally {
      if (mounted) setState(() => _searching = false);
    }
  }

  void _choose(PlacePoint place) {
    final draft = ref.read(journeyDraftProvider.notifier);
    widget.isOrigin ? draft.setOrigin(place) : draft.setDestination(place);
    context.pop();
  }

  Future<void> _useMyLocation() async {
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _locating = true);
    try {
      if (!await Geolocator.isLocationServiceEnabled()) {
        messenger.showSnackBar(const SnackBar(
            content: Text(
                'Aktifkan layanan lokasi di pengaturan HP terlebih dahulu.')));
        return;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        messenger.showSnackBar(const SnackBar(
            content: Text(
                'Izin lokasi ditolak. Kamu tetap bisa mencari alamat atau memilih di peta.')));
        return;
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
            accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 15)),
      );
      if (mounted) {
        _choose(PlacePoint(
            name: 'Lokasi saya',
            lat: position.latitude,
            lon: position.longitude));
      }
    } catch (_) {
      messenger.showSnackBar(const SnackBar(
          content: Text('Lokasi belum didapat. Coba lagi di tempat terbuka.')));
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _pickOnMap() async {
    final draft = ref.read(journeyDraftProvider);
    final start = widget.isOrigin ? draft.origin : draft.destination;
    final picked = await Navigator.of(context).push<PlacePoint>(
        MaterialPageRoute(
            builder: (_) =>
                _MapPickScreen(start: start, isOrigin: widget.isOrigin)));
    if (picked != null && mounted) _choose(picked);
  }

  @override
  Widget build(BuildContext context) {
    final typing = _query.text.trim().length >= 3;
    return Scaffold(
      body: CustomScrollView(
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        slivers: [
          SliverToBoxAdapter(
              child: _LocationHero(
                  isOrigin: widget.isOrigin, onBack: context.pop)),
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(18, 18, 18, 30),
            sliver: SliverList.list(children: [
              Container(
                padding: const EdgeInsets.fromLTRB(12, 12, 12, 11),
                decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: const BorderRadius.only(
                        topLeft: Radius.circular(22),
                        topRight: Radius.circular(8),
                        bottomLeft: Radius.circular(8),
                        bottomRight: Radius.circular(22)),
                    border: Border.all(color: AppColors.ink900, width: 1.2),
                    boxShadow: const [
                      BoxShadow(color: Color(0x19073C3B), offset: Offset(4, 5))
                    ]),
                child: Column(children: [
                  TextField(
                    controller: _query,
                    autofocus: true,
                    textInputAction: TextInputAction.search,
                    style: const TextStyle(
                        fontSize: 12.5, fontWeight: FontWeight.w700),
                    onChanged: (text) {
                      setState(() {});
                      _onChanged(text);
                    },
                    onSubmitted: _search,
                    decoration: InputDecoration(
                      hintText: 'Cari alamat, halte, atau tempat',
                      hintStyle: const TextStyle(fontSize: 11.5),
                      prefixIcon: const Icon(Icons.search_rounded, size: 19),
                      suffixIcon: _searching
                          ? const Padding(
                              padding: EdgeInsets.all(14),
                              child: SizedBox(
                                  width: 17,
                                  height: 17,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2)))
                          : _query.text.isEmpty
                              ? null
                              : IconButton(
                                  tooltip: 'Hapus',
                                  icon: const Icon(Icons.close, size: 18),
                                  onPressed: () => setState(() {
                                        _query.clear();
                                        _results = const [];
                                      })),
                    ),
                  ),
                  const SizedBox(height: 10),
                  Row(children: [
                    Expanded(
                        child: _QuickAction(
                            icon: Icons.my_location_rounded,
                            label: 'Lokasi saya',
                            loading: _locating,
                            onTap: _locating ? null : _useMyLocation)),
                    const SizedBox(width: 8),
                    Expanded(
                        child: _QuickAction(
                            icon: Icons.map_outlined,
                            label: 'Pilih di peta',
                            onTap: _pickOnMap)),
                  ]),
                  const SizedBox(height: 8),
                  const Row(children: [
                    Icon(Icons.lock_outline_rounded,
                        size: 13, color: AppColors.ink600),
                    SizedBox(width: 5),
                    Expanded(
                        child: Text(
                            'Dipakai sekali untuk perjalanan ini, tidak dilacak.',
                            style: TextStyle(
                                fontSize: 8.5, color: AppColors.ink600))),
                  ]),
                ]),
              ),
              const SizedBox(height: 22),
              _SectionLabel(
                  label: typing ? 'HASIL PENCARIAN' : 'TEMPAT CEPAT',
                  count: typing ? _results.length : pilotPlaces.length),
              const SizedBox(height: 9),
              if (_error != null)
                _PickerMessage(icon: Icons.cloud_off_outlined, message: _error!)
              else if (typing && _results.isEmpty && !_searching)
                const _PickerMessage(
                    icon: Icons.search_off_rounded,
                    message: 'Tidak ada tempat yang cocok di Jakarta.')
              else
                for (final place in typing ? _results : pilotPlaces)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _PlaceTile(
                        place: place,
                        icon: typing
                            ? Icons.place_outlined
                            : Icons.star_outline_rounded,
                        onTap: () => _choose(place)),
                  ),
              const SizedBox(height: 10),
              const Text(
                  'Pencarian menggunakan Photon dan OpenStreetMap. Hanya teks pencarian yang dikirim.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      fontSize: 8.5, height: 1.4, color: AppColors.ink600)),
            ]),
          ),
        ],
      ),
    );
  }
}

class _LocationHero extends StatelessWidget {
  const _LocationHero({required this.isOrigin, required this.onBack});

  final bool isOrigin;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) => ClipRRect(
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(28)),
        child: SizedBox(
          height: 196,
          child: Stack(fit: StackFit.expand, children: [
            Image.asset(
              isOrigin
                  ? 'assets/images/air-good.png'
                  : 'assets/images/air-moderate.png',
              fit: BoxFit.cover,
              alignment: const Alignment(0, .25),
              cacheWidth: 850,
              filterQuality: FilterQuality.low,
            ),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [
                    Color(0xD9073C3B),
                    Color(0x9E075B54),
                    Color(0xF207302F),
                  ],
                ),
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
                        Center(
                          child: Row(mainAxisSize: MainAxisSize.min, children: [
                            const HirupLogoMark(size: 26, dark: false),
                            const SizedBox(width: 7),
                            const Text('hirup.',
                                style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 17,
                                    height: 1,
                                    letterSpacing: -.4,
                                    fontWeight: FontWeight.w900)),
                            const SizedBox(width: 7),
                            Container(
                                width: 5,
                                height: 5,
                                decoration: const BoxDecoration(
                                    color: AppColors.mint300,
                                    shape: BoxShape.circle)),
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
                      Text(
                          isOrigin
                              ? 'LANGKAH 01  ·  TITIK ASAL'
                              : 'LANGKAH 02  ·  TUJUAN',
                          style: const TextStyle(
                              color: AppColors.mint300,
                              fontSize: 8,
                              letterSpacing: 1,
                              fontWeight: FontWeight.w900)),
                      const SizedBox(height: 6),
                      Text(isOrigin ? 'Mulai dari mana?' : 'Mau ke mana?',
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 20,
                              height: 1,
                              letterSpacing: -.25,
                              fontWeight: FontWeight.w900)),
                      const SizedBox(height: 7),
                      Text(
                          isOrigin
                              ? 'Cari titik keberangkatan yang paling pas.'
                              : 'Temukan tujuan, lalu lihat kondisi udara di jalurnya.',
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

class _QuickAction extends StatelessWidget {
  const _QuickAction(
      {required this.icon,
      required this.label,
      required this.onTap,
      this.loading = false});

  final IconData icon;
  final String label;
  final VoidCallback? onTap;
  final bool loading;

  @override
  Widget build(BuildContext context) => SizedBox(
        height: 39,
        child: OutlinedButton.icon(
          onPressed: onTap,
          icon: loading
              ? const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 1.8))
              : Icon(icon, size: 16),
          label: Text(label,
              style:
                  const TextStyle(fontSize: 10, fontWeight: FontWeight.w800)),
          style: OutlinedButton.styleFrom(
              padding: const EdgeInsets.symmetric(horizontal: 9),
              side: const BorderSide(color: AppColors.ink900),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(11))),
        ),
      );
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.label, required this.count});

  final String label;
  final int count;

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
          child: Text(count.toString().padLeft(2, '0'),
              style: const TextStyle(
                  fontSize: 7.5,
                  fontWeight: FontWeight.w900,
                  color: AppColors.ink900)),
        ),
        const SizedBox(width: 8),
        const Expanded(child: Divider()),
      ]);
}

class _PickerMessage extends StatelessWidget {
  const _PickerMessage({required this.icon, required this.message});

  final IconData icon;
  final String message;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
            color: AppColors.surfaceMint,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: AppColors.stroke)),
        child: Row(children: [
          Icon(icon, size: 19, color: AppColors.brand600),
          const SizedBox(width: 9),
          Expanded(
              child: Text(message,
                  style: const TextStyle(
                      fontSize: 10.5, height: 1.35, color: AppColors.ink600))),
        ]),
      );
}

class _PlaceTile extends StatelessWidget {
  const _PlaceTile(
      {required this.place,
      required this.onTap,
      this.icon = Icons.place_outlined});
  final PlacePoint place;
  final VoidCallback onTap;
  final IconData icon;
  @override
  Widget build(BuildContext context) => Material(
        color: Colors.white,
        clipBehavior: Clip.antiAlias,
        borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(15),
            topRight: Radius.circular(7),
            bottomLeft: Radius.circular(7),
            bottomRight: Radius.circular(15)),
        child: InkWell(
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.fromLTRB(11, 10, 9, 10),
            decoration: BoxDecoration(
                border: Border.all(color: AppColors.stroke),
                borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(15),
                    topRight: Radius.circular(7),
                    bottomLeft: Radius.circular(7),
                    bottomRight: Radius.circular(15))),
            child: Row(children: [
              Container(
                  width: 34,
                  height: 34,
                  decoration: BoxDecoration(
                      color: place.insideRoutingPilot
                          ? AppColors.surfaceMint
                          : AppColors.danger100,
                      borderRadius: BorderRadius.circular(10)),
                  child: Icon(icon,
                      size: 17,
                      color: place.insideRoutingPilot
                          ? AppColors.brand600
                          : AppColors.danger700)),
              const SizedBox(width: 10),
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text(place.name,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                            fontSize: 11.5,
                            fontWeight: FontWeight.w800,
                            color: AppColors.ink900)),
                    if (!place.insideRoutingPilot) ...[
                      const SizedBox(height: 3),
                      const Text('Di luar koridor rute',
                          style: TextStyle(
                              fontSize: 8.5, color: AppColors.danger700)),
                    ],
                  ])),
              const Icon(Icons.arrow_outward_rounded,
                  size: 16, color: AppColors.brand600),
            ]),
          ),
        ),
      );
}

/// Pan the map under a fixed centre pin, then confirm.
class _MapPickScreen extends ConsumerStatefulWidget {
  const _MapPickScreen({required this.start, required this.isOrigin});
  final PlacePoint start;
  final bool isOrigin;
  @override
  ConsumerState<_MapPickScreen> createState() => _MapPickScreenState();
}

class _MapPickScreenState extends ConsumerState<_MapPickScreen> {
  final _map = MapController();
  bool _naming = false;

  Future<void> _confirm() async {
    final centre = _map.camera.center;
    setState(() => _naming = true);
    String? name;
    try {
      name = await ref
          .read(geocoderProvider)
          .reverse(centre.latitude, centre.longitude);
    } catch (_) {
      name = null; // the coordinates still work without a street name
    }
    if (!mounted) return;
    Navigator.of(context).pop(PlacePoint(
        name: name ?? 'Titik di peta',
        lat: centre.latitude,
        lon: centre.longitude));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: HirupAppBar(
            section: widget.isOrigin ? 'PILIH TITIK ASAL' : 'PILIH TUJUAN',
            code: widget.isOrigin ? '01' : '02'),
        body: Stack(children: [
          FlutterMap(
            mapController: _map,
            options: MapOptions(
              initialCenter: LatLng(widget.start.lat, widget.start.lon),
              initialZoom: 15,
              minZoom: 10,
              maxZoom: 18,
              cameraConstraint:
                  CameraConstraint.containCenter(bounds: mapBounds),
              interactionOptions: const InteractionOptions(
                  flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
            ),
            children: [basemapLayer(), osmAttribution()],
          ),
          // The pin's tip marks the map centre.
          IgnorePointer(
              child: Center(
                  child: Padding(
                      padding: const EdgeInsets.only(bottom: 40),
                      child: Icon(Icons.location_on,
                          size: 44,
                          color: widget.isOrigin
                              ? AppColors.brand600
                              : AppColors.danger700)))),
          Positioned(
            top: 12,
            left: 16,
            right: 16,
            child: IgnorePointer(
              child: Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
                decoration: BoxDecoration(
                    color: const Color(0xEB073C3B),
                    borderRadius: BorderRadius.circular(13),
                    border: Border.all(color: Colors.white30)),
                child: const Row(children: [
                  Icon(Icons.open_with_rounded,
                      size: 16, color: AppColors.mint300),
                  SizedBox(width: 8),
                  Expanded(
                      child: Text(
                          'Geser peta sampai pin berada di titik pilihanmu.',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 9.5,
                              fontWeight: FontWeight.w700))),
                ]),
              ),
            ),
          ),
        ]),
        bottomNavigationBar: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(18, 10, 18, 14),
            child: SizedBox(
              height: 44,
              child: FilledButton.icon(
                onPressed: _naming ? null : _confirm,
                icon: _naming
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.check_rounded, size: 18),
                label: const Text('GUNAKAN TITIK INI',
                    style: TextStyle(fontSize: 10.5, letterSpacing: .5)),
              ),
            ),
          ),
        ),
      );
}
