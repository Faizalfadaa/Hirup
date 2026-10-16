# Hirup Mobile

Aplikasi Android Flutter berdasarkan `frontend/design.md`. UI berbahasa Indonesia dan memakai kontrak `contracts/openapi.yaml` tanpa menghitung dosis atau kategori ISPU di perangkat.

## Menjalankan

Butuh Flutter stable dan Android SDK. Dari folder ini:

```bash
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

`10.0.2.2` adalah alamat host dari Android Emulator. Untuk perangkat fisik, pakai URL HTTPS backend yang dapat dijangkau perangkat. Cleartext HTTP hanya diizinkan pada debug build.

Backend lokal dijalankan dari root repository dengan `make api`. Mock OpenAPI dapat dijalankan dengan `make mock`, lalu ganti port base URL ke `4010`.

## Mode demo

Long-press logo `hirup.` di Beranda atau aktifkan lewat Profil. Lima skenario offline berada di `assets/demo/scenarios.json`; semua tampilan terkait diberi label `MODE DEMO · DATA SIMULASI`.

## Verifikasi

```bash
flutter analyze
flutter test
flutter build apk --debug --dart-define=API_BASE_URL=http://10.0.2.2:8000
```

Saat ini peta menggunakan state placeholder yang eksplisit. AQ point dan route planning sudah terhubung ke backend; basemap/raster interaktif membutuhkan style/tiles berlisensi sebelum `maplibre_gl` dipasang.
