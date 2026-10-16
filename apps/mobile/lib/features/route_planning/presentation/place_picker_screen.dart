import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';

import '../../../core/theme/app_theme.dart';
import '../../../shared/air_map.dart';
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
      if (mounted) setState(() => _error = 'Pencarian belum berhasil. Periksa koneksi lalu coba lagi.');
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
        messenger.showSnackBar(const SnackBar(content: Text('Aktifkan layanan lokasi di pengaturan HP terlebih dahulu.')));
        return;
      }
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) permission = await Geolocator.requestPermission();
      if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
        messenger.showSnackBar(const SnackBar(content: Text('Izin lokasi ditolak. Kamu tetap bisa mencari alamat atau memilih di peta.')));
        return;
      }
      final position = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 15)),
      );
      if (mounted) _choose(PlacePoint(name: 'Lokasi saya', lat: position.latitude, lon: position.longitude));
    } catch (_) {
      messenger.showSnackBar(const SnackBar(content: Text('Lokasi belum didapat. Coba lagi di tempat terbuka.')));
    } finally {
      if (mounted) setState(() => _locating = false);
    }
  }

  Future<void> _pickOnMap() async {
    final draft = ref.read(journeyDraftProvider);
    final start = widget.isOrigin ? draft.origin : draft.destination;
    final picked = await Navigator.of(context).push<PlacePoint>(MaterialPageRoute(builder: (_) => _MapPickScreen(start: start, isOrigin: widget.isOrigin)));
    if (picked != null && mounted) _choose(picked);
  }

  @override
  Widget build(BuildContext context) {
    final typing = _query.text.trim().length >= 3;
    return Scaffold(
      appBar: AppBar(title: Text(widget.isOrigin ? 'Pilih asal' : 'Pilih tujuan')),
      body: ListView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 32), children: [
        TextField(
          controller: _query,
          autofocus: true,
          textInputAction: TextInputAction.search,
          onChanged: (text) {
            setState(() {});
            _onChanged(text);
          },
          onSubmitted: _search,
          decoration: InputDecoration(
            hintText: 'Cari alamat, halte, atau tempat',
            prefixIcon: const Icon(Icons.search),
            suffixIcon: _searching
                ? const Padding(padding: EdgeInsets.all(14), child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)))
                : _query.text.isEmpty
                    ? null
                    : IconButton(tooltip: 'Hapus', icon: const Icon(Icons.close), onPressed: () => setState(() {
                          _query.clear();
                          _results = const [];
                        })),
          ),
        ),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: OutlinedButton.icon(onPressed: _locating ? null : _useMyLocation, icon: _locating ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.my_location), label: const Text('Lokasi saya'))),
          const SizedBox(width: 10),
          Expanded(child: OutlinedButton.icon(onPressed: _pickOnMap, icon: const Icon(Icons.map_outlined), label: const Text('Pilih di peta'))),
        ]),
        const Padding(
          padding: EdgeInsets.only(top: 6, left: 4),
          child: Text('Lokasi hanya dipakai sekali untuk titik ini, tidak dilacak di latar belakang.', style: TextStyle(fontSize: 11, color: AppColors.ink600)),
        ),
        const SizedBox(height: 18),
        if (_error != null)
          Text(_error!, style: const TextStyle(color: AppColors.danger700))
        else if (typing) ...[
          Text('Hasil pencarian', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          if (_results.isEmpty && !_searching) const Text('Tidak ada tempat yang cocok di Jakarta.', style: TextStyle(color: AppColors.ink600)),
          for (final place in _results) _PlaceTile(place: place, onTap: () => _choose(place)),
        ] else ...[
          Text('Tempat cepat', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 6),
          for (final place in pilotPlaces) _PlaceTile(place: place, icon: Icons.star_outline, onTap: () => _choose(place)),
        ],
        const SizedBox(height: 18),
        const Text('Pencarian memakai Photon dengan data OpenStreetMap; hanya teks yang kamu ketik yang dikirim.', style: TextStyle(fontSize: 11, color: AppColors.ink600)),
      ]),
    );
  }
}

class _PlaceTile extends StatelessWidget {
  const _PlaceTile({required this.place, required this.onTap, this.icon = Icons.place_outlined});
  final PlacePoint place;
  final VoidCallback onTap;
  final IconData icon;
  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: Icon(icon, color: AppColors.brand600),
        title: Text(place.name, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: place.insideRoutingPilot ? null : const Text('Di luar koridor rute; kualitas udara tetap bisa dilihat', style: TextStyle(fontSize: 12, color: AppColors.danger700)),
        onTap: onTap,
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
      name = await ref.read(geocoderProvider).reverse(centre.latitude, centre.longitude);
    } catch (_) {
      name = null; // the coordinates still work without a street name
    }
    if (!mounted) return;
    Navigator.of(context).pop(PlacePoint(name: name ?? 'Titik di peta', lat: centre.latitude, lon: centre.longitude));
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text(widget.isOrigin ? 'Geser peta ke titik asal' : 'Geser peta ke titik tujuan')),
        body: Stack(children: [
          FlutterMap(
            mapController: _map,
            options: MapOptions(
              initialCenter: LatLng(widget.start.lat, widget.start.lon),
              initialZoom: 15,
              minZoom: 10,
              maxZoom: 18,
              cameraConstraint: CameraConstraint.containCenter(bounds: mapBounds),
              interactionOptions: const InteractionOptions(flags: InteractiveFlag.all & ~InteractiveFlag.rotate),
            ),
            children: [basemapLayer(), osmAttribution()],
          ),
          // The pin's tip marks the map centre.
          IgnorePointer(child: Center(child: Padding(padding: const EdgeInsets.only(bottom: 40), child: Icon(Icons.location_on, size: 44, color: widget.isOrigin ? AppColors.brand600 : AppColors.danger700)))),
        ]),
        bottomNavigationBar: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton.icon(
              onPressed: _naming ? null : _confirm,
              icon: _naming ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.check),
              label: const Text('Gunakan titik ini'),
            ),
          ),
        ),
      );
}
