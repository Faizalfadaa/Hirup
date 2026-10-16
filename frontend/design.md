# HIRUP — Frontend Design Specification

> **Napas lega, kota terasa dekat.**  
> Product UI/UX & Flutter Implementation Blueprint · Versi 1.0 · 16 Oktober 2026  
> Status: **Design proposal / implementation-ready**, bukan pernyataan bahwa semua fitur sudah tersedia.  
> Platform target: **Android (Flutter)**, Bahasa Indonesia, orientasi portrait utama.

---

## 0. Cara menggunakan dokumen ini

Dokumen ini adalah **single design brief untuk pengembangan frontend Hirup**. Gunakan bersama:

1. **`Hirup_Spesifikasi_Proyek_v2.pdf`** — sumber kebenaran produk, ruang lingkup, kebutuhan fungsional, API, dan batasan ilmiah; terutama Bab 6–8, 12–15, dan 17–18.
2. **`Hirup Trip Planning App.zip`** — referensi visual/interaksi yang sudah ada. Berisi **prototipe React + CSS**, `src/App.tsx`, `src/index.css`, dan `docs/FLUTTER_HANDOFF.md`. Ini **bukan** aplikasi Flutter, bukan kontrak API, dan **semua** nilai kualitas udara/route pada prototipe bersifat simulasi.
3. **`contracts/openapi.yaml` dari tim backend**, bila sudah tersedia — sumber kebenaran **field wire/API**. Contoh request/response di PDF bersifat ringkas, bukan pengganti OpenAPI.

Jika ada konflik: **kontrak API final** berlaku untuk nama/tipe field; **spesifikasi PDF v2** berlaku untuk fitur, prioritas, batas ilmiah, dan aturan demo; dokumen ini berlaku untuk **arah visual dan perilaku UI**. Hindari menyalin angka, posisi peta, atau geometry SVG prototipe sebagai data produksi.

### Status keputusan

- **[SPEC]** = wajib atau ditetapkan di PDF.
- **[PROPOSAL]** = improvement UI yang diusulkan di dokumen ini.
- **[VERIFY]** = perlu konfirmasi bersama P1/P2/P4 atau implementasi yang tersedia.
- **[MUST / SHOULD / COULD]** = prioritas sprint dari PDF, **bukan** kepastian fitur sudah jadi.

**Penting:** tujuan dokumen ini bukan menambah scope backend yang baru. Tampilan boleh lebih kaya, tetapi tetap dibangun dari komponen reusable dan data yang memang tersedia. Jangan menunda fitur Must untuk sekadar mengerjakan animasi kosmetik.

---

## 1. Product vision & pengalaman yang ingin dibangun

### 1.1 Ringkasan produk [SPEC]

Hirup adalah perencana rute multimoda di Jakarta yang membantu orang membandingkan **waktu perjalanan** dengan **estimasi dosis PM2.5 yang terhirup**. Untuk satu asal–tujuan, pengguna melihat hingga tiga rekomendasi berlabel **Tercepat**, **Terbersih**, dan **Seimbang**. Setiap rekomendasi menampilkan langkah perjalanan (leg), paparan per leg, dan pembanding **motor serta mobil**.

Area awal: koridor MRT Lebak Bulus–Bundaran HI dan TransJakarta Koridor 1, dengan buffer area pilot yang dijelaskan di PDF. Rute transit, jalan kaki, dan sepeda dapat dipilih; motor/mobil **adalah pembanding**, bukan primary navigation mode.

### 1.2 Nilai utama produk

1. **See the invisible** — membuat paparan polusi yang tidak terlihat menjadi visual dan mudah dibandingkan.
2. **Choose, don't fear** — membantu pengguna mengambil keputusan, bukan membuat mereka takut bepergian.
3. **Healthy by design** — pilihan lebih sehat dijelaskan bersama konsekuensi waktunya, tanpa janji medis.
4. **Trust the data** — transparan soal estimasi, rentang ketidakpastian, sumber, umur data, dan simulasi.
5. **Urban, human, optimistic** — berasa aplikasi mobilitas Jakarta, bukan dashboard laboratorium atau aplikasi bencana.

### 1.3 Brand personality [PROPOSAL]

**Urban Air Lab × Friendly Mobility**: segar, bergerak, percaya diri, ramah, dan informatif. Karakter desain: *fresh, fluid, layered, expressive but controlled*. Bukan minimalis putih-hijau polos, bukan juga neon yang membuat data sulit dibaca.

**Arah kreatif:** menggunakan ruang putih hangat dan tinta teal gelap sebagai fondasi; *mint, sky blue, dan warm amber* untuk aksen. Tiga elemen khas visualnya ialah **Air Flow Ribbon** (garis angin abstrak), **Exposure Comparison Bar** (balapan batang dosis), dan **Route Story Timeline** (perjalanan diceritakan per langkah).

### 1.4 Nada bahasa (microcopy)

- Pendek, humanis, actionable: **“Jalan yang lebih bersih, tanpa kehilangan banyak waktu.”**
- Bandingkan dua pilihan, jangan menghakimi: **“Dosis diperkirakan 25% lebih rendah, dengan tambahan 6 menit.”**
- Gunakan **“estimasi”**, **“diperkirakan”**, dan **“rentang”** pada data model.
- Jangan menulis “aman”, “bebas polusi”, “mencegah asma”, atau pernyataan diagnosis.
- Hindari penggunaan angka contoh sebagai data nyata. Semua copy dengan angka pada wireframe atau fixture harus diberi label **“Contoh visual / Data simulasi”**.

---

## 2. Visual direction — **HIRUP / Air in Motion**

### 2.1 Apa yang di-improve dari prototipe ZIP

Prototipe React sudah punya fondasi bagus: empat tab bawah, layout mobile satu kolom, Plus Jakarta Sans, warna hijau, komponen kartu, dan sepuluh kategori layar. Improvement yang diinginkan:

| Aspek | Referensi prototipe | Arah desain baru [PROPOSAL] |
|---|---|---|
| Branding | Hijau netral, terasa cukup seragam | Teal yang lebih kaya + mint, biru langit, amber, dan aksen grafis angin |
| Hierarki | Banyak panel putih yang setara | Satu **hero panel**, satu area aksi jelas, cards bertingkat, whitespace terarah |
| Beranda | Map, kartu, form tersebar | **Map-first experience** dengan search overlay dan floating air-quality summary |
| Hasil rute | Tiga kartu teks/metrik | **Editorial result cards** dengan hero persentase, perbedaan durasi, dan bar komparasi |
| Detail | Timeline fungsional | **Route Story Timeline** dengan identitas moda, titik transfer, dan paparan tiap leg |
| Data | Badge dan angka kecil | **Data transparency drawer** yang mudah dibuka: kualitas, sumber, jam data, P10–P90 |
| Insight | Peta + teks | Heatmap/koroplet sebagai hero, filter waktu, dan ranking kelurahan **hanya bila tervalidasi** |
| Motion | Transisi standar | Dua signature moments yang bermakna: *dose race* dan transisi peta–rute |

**Jangan** copy prototipe 1:1 ke Flutter: upgrade visualnya, tetapi pertahankan intent interaksi yang sudah masuk akal.

### 2.2 Color system

**Aturan utama:** warna brand untuk UI **berbeda secara semantik** dari warna **ISPU resmi**. Warna artistik biru/amber **tidak boleh** dipakai sebagai kode kategori kualitas udara pada peta atau legenda. Kategori polusi hanya memakai skala yang diverifikasi dengan tim data.

#### Brand, neutral & accents [PROPOSAL]

| Token | Hex | Penggunaan |
|---|---|---|
| `brand.900` | `#073C3B` | Hero gelap, headline inverse, brand anchor |
| `brand.800` | `#07564F` | Pressed button, dark CTA |
| `brand.600` | `#086A60` | **Primary CTA**, selected navigation, links |
| `brand.100` | `#DFF5E8` | Selected pill, tinted card |
| `mint.300` | `#B9F4D0` | Hero flourish, badge dekoratif, tab highlight |
| `sky.300` | `#A9DEFA` | Accent grafik dekoratif/forecast, informasi netral |
| `sky.700` | `#355B69` | Teks pada tinted sky surface |
| `sun.300` | `#FFD27A` | Highlight waktu & spotlight ilustrasi (bukan data polusi) |
| `sun.800` | `#8D5E15` | Teks di permukaan amber |
| `paper` | `#F7F9F6` | Background app |
| `surface` | `#FFFFFF` | Card standar |
| `surface.mint` | `#E9F6EF` | Panel catatan sehat/positive |
| `surface.sky` | `#EDF5F8` | Panel forecast/info |
| `ink.900` | `#102F30` | Headline/teks utama |
| `ink.700` | `#405B59` | Teks pendukung |
| `ink.600` | `#526661` | Secondary text yang cukup kontras |
| `stroke` | `#DCE8E1` | Border non-interaktif |
| `disabled` | `#E8EFEB` | Disabled background |
| `danger.700` | `#A14336` | Hapus, error kritis — **bukan** peta udara |
| `danger.100` | `#FAEDE9` | Error surface |

**Kontras terverifikasi untuk pasangan utama:** `brand.600` + teks putih ≈ **6.48:1**; `ink.900` pada putih ≈ **14.27:1**; `ink.600` pada putih ≈ **6.12:1**. Tetap audit kombinasi lain, opacity, dan font kecil dengan WCAG AA sebelum release.

**Gradients [PROPOSAL]** — boleh digunakan untuk **hero dan ilustrasi**:

```text
Airflow Hero       linear-gradient(135deg, #073C3B 0%, #086A60 65%, #0B8073 100%)
Mint Horizon       linear-gradient(135deg, #DFF5E8 0%, #EDF5F8 100%)
Sunrise Accent     linear-gradient(120deg, #FFD27A 0%, #FFE6AF 100%)
```

**Larangan:** jangan membuat gradient merah–hijau untuk menggambarkan dosis atau menyamakan gradient dekoratif dengan kategori ISPU. Dosis antar-rute gunakan **satu warna batang netral/teal + label nilai**, bukan palet AQI. Untuk Peta PM2.5 gunakan **skala diskrit ISPU resmi**, beserta kategori/ikon/teks yang diotorisasi.

#### Warna kualitas udara [SPEC, wajib verifikasi mapping]

Palet lima kategori pada handoff: **Baik `#00A000`**, **Sedang `#FFFF00`**, **Tidak sehat `#FF0000`**, **Sangat tidak sehat `#7030A0`**, **Berbahaya `#000000`**. Ambang PM2.5 ↔ kategori ISPU, versi regulasi, dan transformasi dari konsentrasi ke kategori harus dikelola **oleh data/backend**, bukan dihitung di widget. Kategori selalu diberi label teks dan simbol; jangan memakai warna saja. Jika warna resmi gagal kontras sebagai teks, gunakan label di chip kontras terpisah.

### 2.3 Typography

**Primary:** Plus Jakarta Sans (asset lokal dalam APK agar tetap bekerja offline). Angka memakai `FontFeature.tabularFigures()`; terutama dosis, waktu, dan persentase.

| Style | Font size / line height | Weight | Penggunaan |
|---|---:|---:|---|
| `display` | 34 / 42 sp | 700 | Hero headlines, screen emphasis |
| `headline` | 28 / 36 sp | 700 | Headline halaman |
| `metric.hero` | 36 / 42 sp | 750 | **Angka utama** dosis/perbandingan |
| `metric.card` | 26 / 32 sp | 700 | Durasi dan metrik opsi |
| `title.lg` | 21 / 29 sp | 700 | Card penting, judul seksi |
| `title.md` | 18 / 26 sp | 650 | Modal dan header card |
| `body` | 14 / 22 sp | 400 | Isi utama |
| `body.medium` | 14 / 22 sp | 600 | Row, label angka |
| `support` | 12 / 18 sp | 500 | Metadata dan disclaimer pendukung |
| `eyebrow` | 11 / 16 sp | 700 | Label kecil, tracking 0.8 |
| `button` | 14 / 20 sp | 700 | CTA, tombol sekunder |

Skala font system **130–200%**: izinkan wrapping, perluas card secara vertikal, jangan menghilangkan angka atau disclaimer. Ukuran kurang dari 12 sp tidak dipakai untuk informasi esensial. Hindari menerjemahkan ukuran CSS desktop prototipe secara literal.

### 2.4 Spacing, shape & elevation

- Basis **8 dp**; skala: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.
- Screen horizontal inset: **20 dp** (16 dp pada width ≤ 340 dp); jarak antar-section **24–32 dp**.
- Radius: `button 14`, `input 16`, `card 20`, `feature.card 24`, `bottomSheet 28 top`, `pill 999`, `mapControl 16` dp.
- Interaksi minimum **48×48 dp** dan visible focus ring; jarak antar action sejajar ≥ 8 dp.
- Shadow 1: `0 4 18` pada opacity 5% (`#102F30`); Shadow 2: `0 12 32` pada opacity 10%; gunakan **maksimal satu shadow kuat** per viewport.
- Border: 1 dp biasa; selected state = 2 dp + icon/checkmark + perubahan background, **bukan** hanya outline berwarna.
- Gunakan **layering**: peta di dasar, floating capsule controls, surface kartu 1 tingkat, sheet di foreground. Hindari 4–5 kartu nested yang menambah noise.

### 2.5 Graphic language & ikon

- Motif **Air Flow Ribbon**: 2–3 garis lengkung tipis/putus yang melintas perlahan di area dekoratif hero. Tidak menyerupai rute navigasi aktual. Di map asli, semua garis dengan arti navigasi harus berasal dari data geometri rute.
- Ilustrasi onboarding: **kota Jakarta geometris**, daun/angin, transportasi multimoda, figur manusia sederhana; gaya rounded 2.5D/vector, bukan stock photo realistis.
- Ikon: satu keluarga **Lucide atau Phosphor**, stroke konsisten. 20–24 dp standar, 16 dp untuk supporting icon, 28–32 dp untuk hero. Jika pakai Flutter, sediakan asset SVG terkurasi untuk ikon non-standar.
- Do **not** merender puluhan ilustrasi besar: 3 onboarding + 3 shared empty states cukup.

---

## 3. Layout & navigasi aplikasi

### 3.1 Target perangkat [SPEC]

- Android 8+, performa wajar pada RAM 3 GB; ukuran APK target ≤ 60 MB.
- Base design frame **390×844 logical dp**; audit 320, 360, 390, 412 dp serta layar tinggi/rendah dan tablet.
- SafeArea system status/navigation/gesture dan keyboard insets wajib dihitung.
- Default portrait. Landscape/tablet memakai centered content max ~560 dp untuk halaman teks; peta boleh memakai lebar lebih besar. Hindari tablet cuma stretched card raksasa.

### 3.2 Bottom navigation (4 destination)

1. **Beranda** — map, cari rute, udara dan titik lokasi.
2. **Riwayat** — perjalanan tersimpan, tren/ringkasan.
3. **Insight Kota** — kondisi per kelurahan & ruang hijau (**Should**).
4. **Profil** — sensitivitas, preferensi, privasi, mode demo.

Style [PROPOSAL]: bottom bar putih translusen, top hairline, tinggi **72–80 dp + SafeArea**, ikon 23 dp, label 12 sp; tab aktif berupa **soft mint lozenge** di belakang ikon + label teal tebal. Pada hasil/detail/rute aktif, tab Beranda tetap menjadi konteks. Hindari overlay dengan button sticky.

### 3.3 Navigation tree

```text
Splash/First Run
└── Onboarding [3 steps, only first launch; always re-openable]
    └── AppShell
        ├── Beranda (tab)
        │   ├── Cari asal & tujuan / pilih pin
        │   ├── Pilih Mode
        │   ├── Hasil Rute
        │   │   ├── Detail Rute
        │   │   │   └── Perjalanan Aktif → Konfirmasi Simpan
        │   │   └── Saran Jam Berangkat [Should] → Terapkan Waktu
        │   └── Info Titik Udara (sheet)
        ├── Riwayat (tab) → Detail perjalanan lokal → Share Card [Should]
        ├── Insight Kota (tab, Should) → Detail kelurahan/methodology
        └── Profil (tab) → Preferensi / Privasi / Mode Demo
```

**Deep link teknis (route suggestions):** `/onboarding`, `/home`, `/plan/mode`, `/plan/results`, `/plan/detail/:id`, `/plan/departure`, `/trip/active`, `/history`, `/insights`, `/profile`. Gunakan `go_router` nested shell atau setara. Kembalinya detail rute mempertahankan scroll dan selected option.

### 3.4 Behavior global

- **Persistent app shell** untuk empat tab. Konten seperti hasil rute punya app bar `Back`, judul ringkas, share jika tersedia.
- `PrimaryCTA` di bawah viewport via sticky action bar; selalu berada **di atas bottom navigation** bila keduanya tampil. Dalam perjalanan aktif, bottom tab boleh disembunyikan untuk fokus navigasi ringkas.
- Map layer membutuhkan **“Lihat peta / Sembunyikan peta”** eksplisit sehingga UX tetap bisa dipakai saat bergerak/untuk aksesibilitas.
- Peta tidak boleh menutupi attribution sumber. Tap marker/rute memilih objek, lalu membuka sheet.
- Loading/error/empty tidak mereset asal, tujuan, mode, atau profil.

---

## 4. Screen-by-screen specification — **10 layar utama**

> Layout di bawah adalah hierarki, bukan gambar final. **[M] Must**, **[S] Should**, **[C] Could** sesuai spesifikasi.

### 01 — Onboarding [M] · 3 langkah

**Tujuan:** pengguna mengerti konsep, mengatur profil, dan siap mencari rute tanpa harus login.

**Visual:** full-bleed gradient teal → hijau, ilustrasi vektor mengambang pada 40% atas, konten dalam rounded light panel bagian bawah. Progress berupa tiga *flow dots* yang berubah menjadi garis pendek. Headline 28–32 sp.

- **Step A — “Lihat yang tak terlihat.”** Ilustrasi kota dengan dua rute; jelaskan **dosis paparan** berbeda dari angka AQI suatu lokasi. CTA **Lanjut**.
- **Step B — “Temukan rute yang cocok buatmu.”** Pilih **Umum** atau **Lebih sensitif terhadap polusi**; ringkasan singkat pengaruh profil terhadap rekomendasi. Hindari meminta diagnosis/riwayat kesehatan. CTA **Pilih & lanjut**.
- **Step C — “Mulai dari mana?”** Dua pilihan jelas: **Gunakan lokasi saya** (penjelasan sebelum permission) atau **Masukkan lokasi manual**. CTA **Mulai jelajahi**. Sediakan **Lewati untuk sekarang** bila izin lokasi belum diberikan.

**State:** izin granted/denied/permanently denied/location unavailable; tetap bisa input manual. Simpan completion onboarding lokal. Ada entry **Kenali Hirup** di Profil untuk melihat ulang.

**Micro-interaction:** ribbon udara bergerak 6–8 px dalam 600 ms saat mengganti step; `reduceMotion` → tanpa transisi.

### 02 — Beranda / Peta [M]

**Goal:** dalam 5 detik pengguna tahu keadaan udara secara *estimasi* dan menemukan aksi cari rute.

**Komposisi top-to-bottom:**

1. AppBar: `hirup.` + kecil **“Jakarta · Area pilot”** + aksi profil dan indikator kualitas data.
2. Greeting pendek: **“Ke mana hari ini?”** diikuti label **“Cari jalan yang pas untuk waktu dan napasmu.”**
3. **Floating Search Journey** di atas peta: `Asal`, `Tujuan`, tombol tukar lokasi, pilih waktu **Berangkat / Tiba**, CTA **Cari rute**.
4. **Hero MapLibre** tinggi kira-kira 300–380 dp pada first view, rounded 24; layer PM2.5 semi-transparan, controls zoom/lokasi/opacity dan legenda.
5. **Air Now compact card** overlapping bagian bawah peta: kategori udara + nilai P50 + P10–P90 + cap **estimasi** dan jam model. Bisa ditap menuju detail titik. Jika daily equivalent tersedia, **kartu terpisah** dengan penjelasan risiko dan rentang waktu *per hari*, bukan per trip.
6. Horizontal **quick action chips**: `Kantor`, `Rumah`, `Dekat saya` (hanya bila tersedia; favorit Should).
7. **24-hour preview** mini sparkline (Should; hanya jika data forecast valid). Ruang hijau terdekat [Could] tidak boleh memakan ruang penting jika endpoint belum tersedia.

**UI signature:** map memiliki corner aurora dekoratif *di luar area polusi*; white floating search card punya shadow tipis, aksen kecil amber pada pilihan waktu (bukan kategori AQI).

**State:** `loading map`, `AQ unavailable`, `AQ stale`, `GPS denied`, `forecast unavailable`, `offline last known`, `out of service area`. Jika geometri/tiles tidak ada, tampilkan surface berlabel **“Peta belum tersedia”** dan form cari tetap bekerja; **jangan** substitusi SVG prototipe menjadi peta nyata.

### 03 — Pilih Mode [M]

**Goal:** memilih kandidat rute untuk perencanaan.

**Visual:** mini origin→destination journey capsule di atas; title **“Mau perjalanan seperti apa?”**; empat **Mode Choice Tiles** berbentuk segmented grid 2×2 dengan ikon + label + keterangan satu baris:

- `Transit` — MRT / LRT / TransJakarta + jalan kaki penghubung.
- `Sepeda` — utamakan jalur lebih rendah paparan.
- `Jalan kaki` — jalur aktif yang memungkinkan.
- `Semua` — bandingkan opsi yang tersedia.

Selected tile: border 2 dp teal, soft mint surface, icon check, label semantik; bukan hanya highlight warna. Row **Waktu keberangkatan** dapat diedit. Preview profil sensitivitas dan **preferensi** hanya bila sudah didukung ([S]). Sticky CTA **“Lihat pilihan rute”**.

**State:** mode unavailable karena di luar cakupan → disabled dengan alasan, tanpa asumsi tarif atau durasi fiktif.

### 04 — Hasil Rute [M] · **Primary showcase**

**Goal:** keputusan paling penting terjadi di sini: memilih rute berdasarkan **% dosis vs Tercepat** dan waktu.

**Top section:** mini map strip/toggle peta (bila geometri tersedia), lokasi A→B, label waktu, `DataQualityBadge` dan timestamp model.

**Hero:** **“Pilih perjalanan yang paling pas.”** + subcopy **“Bandingkan udara yang dihirup dan menit yang dibutuhkan.”**

**Tiga kartu** dengan hierarchy konsisten (jika opsi duplikat, gabungkan label sesuai FR-02):

- **Terbersih** — visual featured, border teal, corner mint leaf/ribbon, headline **“−X% dosis”**, detail **“+Y menit dari Tercepat”**. **Jangan** paksa menjadi featured jika hasil model/data tidak tersedia.
- **Tercepat** — headline durasi terbesar, subcopy pembanding dosis vs baseline (biasanya 0%).
- **Seimbang** — tampilkan trade-off yang jelas, tanpa menjanjikan paling baik untuk semua orang.

Setiap `RouteOptionCard`: label opsi; durasi; transfer; badge moda/leg; dosis µg; rentang P10–P90 **jika disediakan**; `DataQualityBadge`; bar dosis **dengan skala konsisten**; CTA **“Lihat detail”**; radio/button **“Pilih rute”**. Nilai persen menggunakan **baseline Tercepat** yang eksplisit. `DoseComparison` harus menangani `naik`, `turun`, `sama`, dan `tidak tersedia`.

**Signature #1: Dose Race** — bar opsi dan motor/mobil dianimasikan dari nol ke nilai **sebenarnya** dalam 450–650 ms; grafik menggunakan panjang linear/terlabel, bukan animasi manipulatif. **Jangan** membuat motor selalu terpanjang: dari contoh spesifikasi, **mobil bisa memiliki dosis lebih kecil daripada transit**. Seluruh moda diperlakukan adil.

**Mandatory separate comparison card:** **“Bagaimana jika naik kendaraan pribadi?”** dengan dua baris **Motor** dan **Mobil** (waktu, dosis, CO₂, biaya **bila tersedia**, keterangan asumsi). Harus tetap hadir walaupun sebagian nilai unavailable, tidak mengganti dengan nol. CTA **“Lihat asumsi perhitungan”** [VERIFY data backend].

**Sticky action:** **“Lanjut dengan [label rute]”** bila sudah memilih; selection tidak otomatis memulai perjalanan.

**State:** `3 results`, `1–2 unique results`, `no possible route`, `timeout`, `stale`, `out of area`, `partial comparison`, `demo`. Jangan menampilkan tiga placeholder palsu jika hasil sebenarnya kurang dari tiga.

### 05 — Detail Rute [M]

**Goal:** menjelaskan *di bagian mana* paparan terjadi dan bagaimana rute dijalani.

**Layout:** map besar di atas 240–310 dp + polyline berwarna per konsentrasi (menggunakan data), selected segment diangkat (white casing). Floating label **“Langkah 2 dari 5”**, toggle peta. Bagian bawah berbentuk sheet rounded 28.

- Header: `Terbersih` / `Tercepat` / `Seimbang`; total waktu; total dosis; % vs Tercepat; tingkat keyakinan bila tersedia.
- **Route Story Timeline**: ikon moda, titik berangkat / halte, durasi, dosis tiap leg µg, label kategori jika tervalidasi; garis connector jelas untuk `WALK`, `WAIT`, `SUBWAY`, `BUS`, `BIKE`, dan moda valid lain dari backend.
- Tap leg → map zoom/highlight pada geometri yang benar-benar tersedia. `WAIT` leg menampilkan lokasi menunggu dan durasi; bukan garis map yang dipaksakan.
- **Helpful tip** panel mint: mis. **“Bila memungkinkan, tunggu di dalam stasiun.”** Hanya jika relevan, dukungan data/rute mencukupi dan tidak memberi perintah berbahaya.
- **Model notes** expandable: estimasi, rentang P10–P90, cara hitung paparan secara ringkas, sumber, asumsi.
- CTA **“Mulai perjalanan”**; action kedua **“Cari waktu berangkat yang lebih baik”** [S].

**Checks:** total dosis harus konsisten dengan total seluruh leg (toleransi pembulatan 1% sesuai FR-03). Kalau backend kehilangan dosis suatu leg, tampilkan keterbatasan; jangan hitung total keliru di UI.

### 06 — Saran Jam Berangkat [S]

**Goal:** membandingkan waktu keberangkatan dalam rentang ±90 menit, resolusi 15 menit.

**Visual:** hero **“Sedikit menggeser waktu, mungkin bikin beda.”**, small live range badge; grafik **Departure Dose Bars** dengan garis referensi waktu awal. Slot terbaik hanya di-highlight **berdasarkan respons**; jangan diasumsikan lebih pagi selalu lebih bersih.

- Sumbu X waktu `HH.mm` zona Jakarta, sumbu Y nilai dosis µg; *axis labels* tetap terbaca di width kecil (horizontal scrolling).
- Tiap slot aksesibel, tap → bawah grafik tampil detail **“Pukul X:XX · estimasi dosis ... µg · durasi ... menit”**, selisih terhadap slot awal jika tersedia.
- Tampilkan interval P10–P90 sebagai range/whisker **hanya bila API mengirimkannya**.
- Jika backend hanya punya forecast per jam tetapi bukan saran 15-menit, **jangan interpolasi secara diam-diam dan berpura-pura akurat**.
- CTA **“Pakai waktu ini”** lalu ulangi route planning dengan `depart_at` terpilih atau gunakan mekanisme kontrak yang disetujui P1; *tidak* mengubah nilai route lama secara sembunyi.

**State:** gap forecast, unavailable, slot tidak feasible, offline, demo; missing → **gap**, bukan batang nol.

### 07 — Perjalanan Aktif [M]

**Goal:** pendamping langkah ringan, **bukan** klaim turn-by-turn navigation setara Google Maps.

**Visual:** map upper half dan anchored large **Next Step Card**. Status timeline/progress, mode/halte, instruksi leg selanjutnya **bila diberikan**, estimasi dosis leg/rute. Saat tidak ada instruksi detail, gunakan ringkasan moda & destinasi (tidak buat instruksi belok fiktif).

- CTA tetap **“Selesai”** → confirm sheet **“Simpan perjalanan ini ke riwayat?”**.
- Simpan hanya setelah konfirmasi eksplisit; trip disimpan lokal dengan timestamp benar, mode, asal/tujuan, estimasi dosis, kualitas data, dan pilihan rute.
- Tidak memantau GPS di latar belakang (SPEC); jangan menampilkan breadcrumb live kecuali lokasinya memang didapat dengan izin saat foreground.
- Peringatan saat leg berpaparan lebih tinggi harus ringkas dan tidak alarmis; tidak menjamin kondisi aman.

### 08 — Riwayat & Ringkasan [M history, S weekly/share]

**Goal:** menunjukkan kebiasaan dan dampak pilihan berdasarkan **perjalanan yang benar-benar disimpan**.

- Header **“Setiap perjalanan berarti.”**
- **Weekly Insight Hero** (Should): total dosis perjalanan periode tertentu, dosis dihindari **jika baseline valid**, kartu breakdown harian; jelas bahwa ini bukan total paparan tubuh 24 jam kecuali estimasinya tersedia.
- Kalender strip 7 hari / weekly switch hanya jika memberi insight nyata; jangan render bar fiktif untuk tanggal yang kosong.
- **Trip History List** dengan tanggal Asia/Jakarta, A→B, moda, durasi, dosis, data-quality dan status simulasi.
- Detail lokal: tindakan **Hapus perjalanan** via dialog konfirmasi.
- **Shareable Card** (Should): story frame 9:16 atau 1080×1920 export, deep teal gradient, angka headline, minggu/date-range, disclaimer kecil yang tetap terbaca, watermark **“Data simulasi”** jika fixture. Tidak membagikan lokasi presisi secara default.

**State:** pengguna baru → illustration **“Belum ada perjalanan, mulai satu dulu yuk.”** + **Cari rute**; weekly data tidak cukup → **“Ringkasan belum tersedia”**, bukan `0% terhindar`.

### 09 — Insight Kota [S]

**Goal:** insight spasial kelurahan dari **hasil model**, bukan tracking pengguna.

**Visual:** editorial city header **“Kenali kualitas udara di sekitar kota.”** dengan segmented filter periode (sesuai API), **choropleth MapLibre** sebagai fokus, legend lima kategori atau legenda metrik tervalidasi (jangan campur keduanya), selected kelurahan bottom sheet.

- Panel statistik kota hanya memakai agregat yang dikirim backend. Jangan klaim angka total kota Jakarta dari area pilot kecil.
- List **“Wilayah yang perlu perhatian”** hanya jika indeks ketimpangan terverifikasi: paparan tinggi × rendah ruang hijau × kepadatan.
- **Metodologi & sumber** expandable (model raster, periode, keterbatasan). Tampilkan `data_quality`.
- Empty state yang jujur jika data kelurahan belum tersedia, sambil tetap menjelaskan konsep dan cakupan wilayah pilot.
- Jangan membuat titik paparan komuter agregat pengguna (FR-32 Won't).

### 10 — Profil & Privasi [M profile, S preferences]

**Goal:** mudah mengendalikan sensitivitas dan data yang disimpan.

**Komposisi:** userless avatar monogram bertema daun, badge **“Tanpa akun”**, header **“Perjalananmu, kendalimu.”**

1. **Profil sensitivitas**: `Umum` / `Lebih sensitif` (Must) dan konsekuensinya. Jangan meminta informasi penyakit.
2. **Preferensi perjalanan** (Should): max berjalan kaki, hindari transfer, pengecualian moda jika benar-benar dipakai oleh routing.
3. **Lokasi & izin**: status izin jelas, tautan ke pengaturan OS jika ditolak permanen.
4. **Data & privasi**: riwayat hanya di perangkat; `Hapus semua data lokal` = destructive confirmation, tidak auto clear sebelum konfirmasi.
5. **Tentang estimasi**: penjelasan dosis, padanan rokok, model, sumber, versi.
6. **Mode demo** (Must): dipicu **long-press logo** sesuai PDF, dapat pula ditampilkan sebagai entry khusus lingkungan penjurian sesuai keputusan tim; selalu banner persistently visible bila aktif.

**State:** profil tidak disimpan? gunakan default jelas `Umum`; saat preferensi berubah, tandai rute terdahulu berasal dari profil lama dan tawarkan **Hitung ulang** bila relevan.

---

## 5. Komponen reusable & kontrak visual

Semua widget **presentation-only**; request/API dan perhitungan ilmiah bukan tanggung jawab widget. Skema bawah adalah **view-model** internal, bukan nama wire API.

| Widget / komponen | Isi & variants | Perilaku penting |
|---|---|---|
| `HirupScaffold` | Topbar, body, bottom nav, optional bottom CTA | SafeArea, keyboard inset, tab preservation |
| `HirupAppBar` | Title, back, timestamp/status | Hit target 48dp; no overflowing title |
| `PrimaryButton` | default, loading, disabled, destructive | Height 52–56dp, radius14, progress inline |
| `FloatingJourneySearch` | Origin, destination, swap, depart/arrive, search | Validasi asal≠tujuan; supported GPS/pin/manual |
| `LocationField` | idle, focusing, suggestion, manual, error | Tidak menyimpan lokasi sebelum pilihan pengguna |
| `ModeChoiceTile` | transit, bike, walk, all | Selected ring+check+label; accessible radio semantics |
| `RouteOptionCard` | one/multiple labels, selected, partial, no-range | Delta vs Tercepat; separate onSelect/onDetails |
| `ExposureComparisonBar` | options + motor + mobil | Sumbu sama, unit µg, tidak memanipulasi urutan/data |
| `DoseMetric` | value, unit, range, unavailable | Tabular numbers, formatting ID, `—` saat null |
| `DataQualityBadge` | real / approximated / synthetic | `real` bukan berarti dosis diukur langsung |
| `ConfidenceBadge` | high/medium/low/unknown | Hanya dari API; explanation accessible |
| `AirQualityLegend` | 5 kategori ISPU terverifikasi | Ikon+teks+warna; method/metric jelas |
| `AirQualityPointSheet` | P50, P10/P90, timestamp, category | AQ point response, attribution, freshness |
| `MapLayerControl` | opacity slider, show/hide, location | Attribution tetap terlihat; no overlapping CTA |
| `MapRoutePolyline` | by actual leg geometry, selected, unavailable | No invented routes; line casing untuk readability |
| `MapBottomSheet` | peek / half / full | Snap assist, handle, focus semantics |
| `RouteStoryTimeline` | legs, active/highlighted | Duration, mode, dose; sum check at data layer |
| `DepartureDoseChart` | discrete slots, missing, selected | Scrollable, touch 48dp, semantics per slot |
| `ExposureSummaryCard` | weekly, insufficient, synthetic | Explicit period and baseline |
| `ShareableSummaryCard` | story export, preview | Watermark if synthetic + privacy-safe |
| `SourceMethodologySheet` | source, version, limitations, data age | Consistent bottom sheet used across screens |
| `InlineNotice` | estimated, stale, offline, demo | No disappearing disclosures |
| `EmptyState` | no result/no trip/no AQ/no insight | Illustration + one next action |
| `ErrorState` | network, server, rate limit, invalid data | Retry, offline fallback, no raw error dump |
| `SkeletonLoader` | cards / chart / map | Stable layout, no fake real progress |
| `ConfirmationSheet` | trip completion, delete | Explicit confirm/cancel; system back safe |

### 5.1 Card anatomy [PROPOSAL]

```text
┌──────────────────────────────────────┐
│ [🍃 TERBERSIH]           [Perkiraan] │
│                                      │
│ −25% dosis               44 menit   │
│ dibanding Tercepat        +6 menit  │
│ ━━━━━━━━━━━━━━················       │
│ 16–30 µg (contoh simulasi)          │
│                                      │
│ 🚶 Jalan · 🚇 MRT · 1 transfer      │
│ [Pilih rute]        [Lihat detail →] │
└──────────────────────────────────────┘
```

Angka dan nama moda di atas **hanya ilustrasi format (data simulasi)**. Gunakan API untuk nilai sebenarnya. Bar dosis hanya bermakna jika baseline dan nilai pembanding ada. Jika `delta_vs_fastest_pct` tidak ada, tampilkan **“Perbandingan belum tersedia”**.

### 5.2 Motion design

| Motion | Waktu | Easing / rule |
|---|---:|---|
| Press button | 100–140 ms | subtle 0.98 scale, `easeOut` |
| Card selection | 180–240 ms | background/border and small icon fade |
| Page push | 240–320 ms | fade + slide 12dp; respect platform back |
| Route cards enter | stagger 60 ms | `easeOutCubic`; only when result first appears |
| Dose race [S] | 450–650 ms | `easeOutCubic`, proportional bar lengths |
| Map→Detail [S] | 250–400 ms | Hero transition or camera interpolation |
| Sheet snap [S] | 260–340 ms | spring gentle; dismiss affordance always present |
| Error/loading | no dramatic animations | use stable skeletons, reduce motion option |

**Animation budget:** represent actual data, never change values for visual drama; offscreen animated segments disabled for RAM/CPU. Reduce Motion/Text scaling respected. Polyline breathing effect [S] **decorative only**, should be toned down and never suggest a safety status that data doesn't support.

---

## 6. Screen states, error handling, & trust

### 6.1 Standard state machine

Setiap screen dengan data network wajib mendukung:

```text
initial → loading → content
                  ↘ partial/stale
                  ↘ empty
                  ↘ error → retry → loading
      demo (explicitly enabled) → synthetic content + permanent demo badge
```

| State | UI copy contoh | Recovery |
|---|---|---|
| Loading route | “Sedang membandingkan pilihan rute…” | Skeleton layout dengan CTA disabled; jangan klaim jumlah ruas jika backend tidak memberi progress |
| Empty routes | “Belum ada rute untuk pilihan ini.” | Ubah mode, waktu, asal/tujuan |
| Offline with cache | “Kamu sedang offline. Menampilkan data terakhir dari 07.00.” | Tampilkan umur data aktual, `Coba lagi` |
| No cache/offline | “Butuh koneksi untuk mencari rute baru.” | Pertahankan input, retry, atau demo manual |
| API 404 area | “Lokasi ini berada di luar area layanan Hirup saat ini.” | Buka area pilot/map dan edit lokasi |
| API 429 | “Permintaan terlalu banyak. Coba lagi sebentar.” | Retry dengan backoff, no storm |
| API 503 | “Data udara belum siap.” | Fallback hanya jika backend secara eksplisit mengirim/mendukungnya |
| AQ stale | “Perkiraan udara belum diperbarui.” | Badge stale + timestamp dan sumber |
| Missing interval | “Rentang perkiraan belum tersedia.” | Hide error bars; **jangan** buat rentang palsu |
| Synthetic/demo | “Mode demo · Data simulasi” | Persistent top banner/badge, label di kartu dan ekspor |
| Insufficient weekly | “Belum cukup perjalanan untuk ringkasan minggu ini.” | Tampilkan riwayat yang memang tersimpan |

**Data quality rules [SPEC]:** respons mengandung `data_quality: real | approximated | synthetic`; `approximated` → **Perkiraan**, `synthetic` → **Data simulasi**. Istilah `real` berarti sumber input/perhitungan berbasis data nyata; **dosis perjalanan tetap estimasi model**, bukan pembacaan personal sensor. Bila badge data quality per-item tidak tersedia, beri disclosure setingkat respons dengan cakupan yang benar. Jangan menghapus badge saat mengambil screenshot demo.

### 6.2 Kebutuhan kejujuran ilmiah

- PM2.5 konsentrasi (µg/m³), dosis terhirup (µg), dan CT (µg·jam/m³) **berbeda**; label dan unit jangan tertukar.
- Waktu keberangkatan memakai **Asia/Jakarta**, input/output ISO 8601 dari backend.
- Confidence dan P10–P90 berasal dari backend; jangan hitung confidence di UI.
- Perbandingan persen dan dosis dihindari hanya jika baseline Tercepat valid dan denominator non-zero. Nilai yang lebih tinggi ditulis **“+X% dosis”**, bukan selalu “hemat”.
- **Padanan rokok** hanya alat komunikasi risiko dari pendekatan di Bab 12.5 dan harus menyebut **jangka waktu** serta disclaimer **bukan ukuran medis**. Jangan menampilkan “X batang” sekali trip seolah sama dengan merokok langsung; jangan copy angka keliru v1.0.
- Porsi dosis harian hanya jika backend mengirim estimasi dosis 24 jam beserta asumsi dan periode; **jangan** membagi jumlah perjalanan dengan total dosis *perjalanan* lalu menyebutnya dosis harian.
- Nilai `0` berbeda dengan `null` atau **“belum tersedia”**; spinner dan chart missing tidak boleh berubah menjadi zero.
- Pembanding motor/mobil tetap menggunakan mesin model yang sama dengan transit. Jangan paksa motor/mobil lebih buruk untuk mempercantik visual.
- `data_quality=synthetic` **tidak boleh** muncul sebagai bukti dampak ilmiah atau peringkat kota nyata.

---

## 7. Design tokens → Flutter

> Gunakan satu source-of-truth token (`assets/tokens/hirup_tokens.json` atau Dart constants), jangan hard-code warna/radius tersebar. Figma styles dan Flutter `ThemeData` harus mengikuti token yang sama.

Contoh potongan awal (bukan implementasi ThemeData lengkap):

```dart
import 'package:flutter/material.dart';

abstract final class HirupColors {
  static const primary = Color(0xFF086A60);
  static const primaryDark = Color(0xFF07564F);
  static const deepTeal = Color(0xFF073C3B);
  static const mint = Color(0xFFB9F4D0);
  static const mintSurface = Color(0xFFE9F6EF);
  static const sky = Color(0xFFA9DEFA);
  static const skySurface = Color(0xFFEDF5F8);
  static const amber = Color(0xFFFFD27A);
  static const paper = Color(0xFFF7F9F6);
  static const surface = Color(0xFFFFFFFF);
  static const ink = Color(0xFF102F30);
  static const secondaryText = Color(0xFF526661);
  static const stroke = Color(0xFFDCE8E1);
  static const danger = Color(0xFFA14336);
}

abstract final class HirupRadius {
  static const button = 14.0;
  static const input = 16.0;
  static const card = 20.0;
  static const featuredCard = 24.0;
  static const sheet = 28.0;
}

abstract final class HirupSpace {
  static const xs = 4.0;
  static const sm = 8.0;
  static const md = 16.0;
  static const lg = 24.0;
  static const xl = 32.0;
}
```

Implementasi disarankan: `ColorScheme.fromSeed` boleh sebagai starting scaffold, **tetapi override explicit** brand/surface/onSurface/outline/semantic tokens agar cocok dengan desain; gunakan `ThemeExtension` untuk `mint`, `sky`, `sun`, map shadow/route styles, dan gradient. **Palet ISPU** dipisah pada `AirQualityPalette`, bukan `ThemeData.primary`.

---

## 8. Flutter code structure & boundaries

### 8.1 Stack [SPEC + usulan implementasi]

- **Flutter 3 / Dart** untuk Android.
- **`flutter_riverpod`** untuk state; **`go_router`** untuk navigation shell.
- **`dio`** dengan timeout, error normalization, `request_id`, headers data age.
- **`maplibre_gl`** untuk map + tile layer PM2.5 + route geometries + GeoJSON city.
- **Isar atau Hive** untuk history, favorites, preferences, onboarding & demo settings (pilih satu dan konsisten).
- `intl` untuk `id_ID` dan formatting angka/tanggal; timestamps tetap timezone-aware.
- Package graph: prefer Flutter built-in/custom painter dahulu; tambah chart dependency bila memang mempercepat deliverable.

### 8.2 Rekomendasi folder frontend

```text
lib/
  app/
    app.dart
    router.dart
  core/
    theme/                 # colors, typography, gradients, radii, theme extensions
    config/                # environment endpoints, pilot-area metadata
    network/               # dio, error/problem details, data freshness
    utils/                 # format values, timezone, units, accessibility
  shared/
    widgets/               # buttons, badges, sheets, states, loading
    models/                # view models & data quality, not raw DTO guesses
  features/
    onboarding/
    home/
    route_planning/
      data/                 # DTO/Repository/Adapter
      domain/               # route display models, formatting
      presentation/         # mode, results, detail, departure
    active_trip/
    history/
    city_insights/
    profile/
  data/
    demo/                   # five labelled JSON fixture scenarios
assets/
  fonts/
  illustrations/
  icons/
  tokens/
```

Pisahkan tiga lapisan:

```text
Backend DTO (from OpenAPI) → Repository/Adapter → immutable Presentation Model
                                               ↓
                                       Riverpod AsyncState
                                               ↓
                                         Flutter Widgets
```

**Tidak boleh:** widget membuat geometri rute fiktif, menghitung dosis model kesehatan, menentukan threshold ISPU, mengganti `data_quality`, atau menetapkan nilai confidence. UI boleh memformat *nilai yang sudah dihitung* dan mengatur urutan presentasi berdasarkan kebijakan yang jelas.

### 8.3 Controller & state [PROPOSAL]

- `JourneyDraftController`: origin, destination, mode, depart/arrive toggle, profile, preferensi.
- `RoutePlanningController`: async plan, request ID, selected `option_id`, comparison, overlay segments.
- `AirQualityController`: point/raster freshness + map overlay visibility/opacity.
- `DepartureAdviceController` [S]: selected time slot, source data, apply behavior.
- `ActiveTripController`: selected itinerary, foreground progress, confirm/save (tanpa background GPS).
- `HistoryController`: local CRUD, week aggregation on compatible/validated data.
- `CityInsightsController` [S]: kelurahan geometries, stats, time filters.
- `ProfileController`: sensitivity, privacy, favorites [S], demo mode.

**Rules:** perubahan mode/asal/tujuan membatalkan atau mendepresiasi respons route sebelumnya; response older request tidak boleh meng-overwrite hasil terbaru. Gunakan cancellation token/debouncing untuk pencarian dan guard asynchronous race.

---

## 9. Data/API integration contract

### 9.1 Endpoint map [SPEC]

| Kebutuhan UI | Endpoint | Prioritas |
|---|---|---|
| Rute + 3 opsi + motor/mobil | `POST /v1/routes/plan` | M |
| Poin PM2.5 | `GET /v1/aq/point?lat&lon&ts` | M |
| Raster tiles PM2.5 | `GET /v1/aq/tiles/{z}/{x}/{y}.png?ts` | M |
| Health/data freshness | `GET /v1/health` | M |
| 15-min departure suggestion | `GET /v1/routes/departure-advice` | S |
| Forecast 24 jam | `GET /v1/aq/forecast?lat&lon&hours=24` | S |
| Daily AQ & cigarette per day | `GET /v1/aq/daily-summary?lat&lon&date` | S |
| City Insights | `GET /v1/insights/kelurahan?from&to` | S |
| Nearby green spaces | `GET /v1/greenspaces/nearby?lat&lon&limit` | C |

[VERIFY] Tidak ada endpoint geocoding/search lokasi yang didefinisikan di tabel PDF. Tentukan dengan P1 apakah menggunakan POI dataset lokal, provider berlisensi, atau pilihan pin manual. **Jangan** mendesain search suggestion seolah API-nya sudah tersedia.

### 9.2 Plan request fields yang dicontohkan PDF

`origin {lat, lon}`, `destination {lat, lon}`, `depart_at`, `mode ('transit' | 'bike' | 'walk' | 'all')`, `profile {sensitivity, max_walk_m}`, `include_comparison`.

**Catatan [VERIFY]:** `arrive_at` merupakan kebutuhan UX FR-01 tetapi contoh request di PDF hanya menunjukkan `depart_at`. Jangan mengirim `arrive_at`, field pengecualian moda, atau bobot slider sebelum benar-benar masuk kontrak OpenAPI.

### 9.3 Plan response (contoh field yang didokumentasikan PDF)

- Root: `request_id`, `data_freshness {aq_valid_hour, model_version, confidence}`, `options[]`, `comparison`, `disclaimer`, `data_quality` (diperlukan konvensi API walau contoh payload dipersingkat).
- Route option: `option_id`, `labels[] ('fastest'|'cleanest'|'balanced')`, `duration_s`, `transfers`, `dose_ug`, `dose_ug_p10`, `dose_ug_p90`, `ct_ugh_m3`, `cig_eq`, `delta_vs_fastest_pct`, `legs[]`.
- Leg: `mode`, `duration_s`, `mean_pm25`, `dose_ug`, `polyline`, `segments_pm25`; `route`, `place`, `from`, `to` sesuai jenis leg dan field yang diberikan.
- Comparison: `motorcycle`, `car`; contoh menyediakan `duration_s`, `dose_ug`, `cig_eq`, `co2_kg`. `cost` **belum muncul dalam contoh** meskipun diwajibkan pada FR-05: tandai kebutuhan integrasi bersama P1.
- Format: WGS84 lat/lon; `polyline` encoded precision **6**; timezone **Asia/Jakarta**; Problem Details **RFC 9457** (`type/title/status/detail/request_id`).

### 9.4 Rules rendering data

- Percent reduction = dari `delta_vs_fastest_pct` backend (format Indonesia). Hindari menghitung ulang kecuali definisi disepakati dan unit/baseline divalidasi.
- Sorting options: `fastest / cleanest / balanced` dapat datang sebagai beberapa label pada satu opsi. Jika satu itinerary menang beberapa kategori, tampilkan **satu kartu** dengan multi-badge, bukan duplicating fake results.
- Semua value numeric null-handling menggunakan `—` + hint; `0` hanya jika backend benar-benar `0`.
- Store timestamp (timezone-aware) ketika user mengonfirmasi trip; hindari bug prototipe React yang menyimpan trip tanpa timestamp.
- `X-Data-Age-Seconds` dipakai untuk warning stale; bandingkan dengan kebijakan freshness dari backend, bukan mengarang expiry.
- `FR-08` slider waktu ↔ udara [S] mere-ranking kandidat yang **sudah** tersedia, tidak menebak kandidat baru, tidak mengubah dosis aslinya.
- `POST /routes/plan` target p95 ≤ 5 detik [M] / ≤ 3 detik [S]; UI tetap punya timeout/retry dan copy masuk akal, tanpa progressive fake status.
- Data demo: fixture yang sama melewati `Repository` interface; bukan hard-coded di screen.

---

## 10. Mode demo untuk hackathon [M]

**Tujuan:** flow dapat didemokan offline ketika server/raster/OTP tidak tersedia.

- Akses **long press logo Hirup** (sesuai Bab 14.8).
- **Lima skenario fixture JSON** (bukan angka dipilih manual secara acak di widget). Pilihan skenario menampilkan asal, tujuan, jam, moda, profil, dan hasilnya jika fixture lengkap.
- Saat aktif: banner **“MODE DEMO · DATA SIMULASI”** selalu terlihat di layar yang memakai fixture; setiap kartu/ekspor mendapat label `Data simulasi`.
- Semua trip demo lokal diberi `is_demo=true` dan tidak masuk statistik perjalanan nyata tanpa disclosure terpisah.
- Jangan pernah menggunakan fixture untuk metrik ML, laporan 50 OD, atau klaim “pengurangan dosis rata-rata”.
- Simulasikan interaksi hasil rute → detail → jam berangkat → perjalanan aktif → simpan → riwayat → Insight hanya sejauh fixture tersedia. Jika tidak ada data untuk suatu fitur, tampilkan state unavailable yang jujur.
- Label peta fixture: **“Ilustrasi / data simulasi”**; jangan memperlakukan SVG demo dari ZIP sebagai route geometry navigasi sebenarnya.

---

## 11. Accessibility, performance & privacy

### Aksesibilitas

- Kontras teks utama minimal **4.5:1**, large text **3:1**, dan indikator nonteks **3:1** pada konteksnya; audit kombinasi aktual.
- Touch target **≥48×48dp** untuk CTA, tabs, chart slots, legend controls, zoom controls, dan icon-only actions.
- Semantik TalkBack: label harus menyebut **opsi, durasi, dosis + unit, dibanding apa, status terpilih**. Contoh: “Terbersih, empat puluh empat menit, estimasi dosis dua puluh satu koma delapan mikrogram, lebih rendah dua puluh lima persen dibanding tercepat, belum dipilih.” Nilai dinamis harus berasal dari data.
- Warna tidak menjadi satu-satunya cara membaca paparan: **warna + simbol + teks kategori**.
- 130% system text scale wajib lulus; 200% sebisa mungkin dengan scroll vertikal/line wrap, tidak memotong CTA kritis.
- Chart bisa dibaca lewat daftar data alternatif; sheet dapat di-close dengan Back dan mengembalikan fokus yang masuk akal.
- Reduce motion menonaktifkan animasi dosis/progress yang tidak esensial.

### Performance

- Lazy load map & overlay hanya ketika relevan; tampilkan skeleton map tanpa memblokir form.
- Raster tiles dimuat untuk viewport/zoom yang perlu; hindari puluhan raster full resolution sebagai image besar pada klien.
- Hindari rebuild seluruh halaman pada pergeseran chart slider / render tiap map frame; gunakan `Consumer` scoped, selector dan isolate bila parsing polyline besar.
- Gunakan `const`, image asset vector kecil, batch polyline/layer update, minim blur mahal. Sasaran UX ~60 fps pada device RAM 3GB (harus diuji, bukan klaim otomatis).
- Persistent cache terbatas untuk last route, tipe data & timestamp; cache label stale jelas. APK ≤60 MB (SPEC).

### Privacy & security [SPEC]

- Guest-first: **tanpa login/akun**, history/preferensi di perangkat; clear-all benar-benar menghapus cache/history/profile/consent sesuai implementasi.
- **Tidak menggunakan background GPS**; minta izin dengan alasan yang masuk akal dan pertahankan input manual.
- Tidak menyimpan token API pihak ketiga atau privileged key di aplikasi; gunakan backend HTTPS.
- Jangan mengirim asal/tujuan/sensitivitas dalam analytics eksternal tanpa dasar yang diizinkan.
- Screenshot/share default menyembunyikan koordinat/alamat rumah presisi; profil “lebih sensitif” bukan diagnosis medis.

---

## 12. Priority & implementation order

### Phase A — Foundation + Must [SPEC]

- [ ] Theme tokens, bundled typography, icons, four-tab Shell, 48dp tap targets.
- [ ] Onboarding 3 langkah dan profil umum/rentan dengan persistence lokal.
- [ ] Location manual/GPS + area pilot validation (pin drag bila disediakan map).
- [ ] Beranda map PM2.5 + legend + AQ point sheet (P50 + P10/P90); freshness.
- [ ] Cari route dan pilih mode transit/sepeda/jalan kaki/semua.
- [ ] Tiga kategori route (deduplicate labels), dosis/perbandingan %/durasi/transfer.
- [ ] Pembanding motor **dan** mobil, partial-data presentation.
- [ ] Detail rute per leg, colored map polyline & tips sesuai data.
- [ ] Active trip confirm/save; riwayat lokal dengan timestamp nyata.
- [ ] Loading, empty, error, offline, out-of-area, stale, demo states.
- [ ] API integration lewat OpenAPI/mock → backend; permission/error handling.
- [ ] Mode demo offline **5 fixture berlabel**.

### Phase B — Should [SPEC]

- [ ] Departure advice ±90m / 15-min slots, range jika didukung.
- [ ] 24-hour forecast dan daily-summary disclosure yang benar.
- [ ] Weekly summary + export kartu berbagi.
- [ ] Insight Kota choropleth, index ketimpangan setelah validasi.
- [ ] Favorit dan preferensi yang benar-benar memengaruhi routing.
- [ ] Slider preference waktu↔udara re-rank dari candidates (bukan model ulang di UI).
- [ ] Dose race + transisi peta–detail yang halus; QA usability 5 responden.

### Phase C — Could [SPEC]

- [ ] Green spaces nearby endpoint, local warning (maks. 1×/hari), haptics, dark mode bila ada waktu.

### Won't (jangan masuk roadmap pengumpulan)

Akun/sinkronisasi, iOS, pembayaran, GTFS-Realtime, semua DKI, data agregat pergerakan pengguna, diagnosis medis, sensor fisik. Jangan membuat UI palsu untuk fitur-fitur tersebut.

**Design freeze:** menurut dokumen lomba, design freeze H1 18.00 dan app freeze H3 siang. Jika mengerjakan setelah waktu tersebut untuk tujuan baru/non-lomba, prioritaskan persetujuan tim dan backward compatibility, jangan diam-diam menganggap jadwal historis ini masih berlaku.

---

## 13. QA checklist / definition of done

### Per screen

- [ ] Hierarki jelas: satu headline, satu aksi utama, satu prioritas visual per viewport.
- [ ] Token dipakai konsisten: tidak ada warna heks/radius tak terdokumentasi yang tersebar.
- [ ] UI nyaman pada 320/360/390/412 dp, tinggi layar pendek, keyboard open, Android gesture nav.
- [ ] State `loading / content / empty / error / offline / out-of-area / demo` dites jika relevan.
- [ ] Semua angka punya unit, rentang bila ada, baseline, timestamp, dan `data_quality` yang benar.
- [ ] Tidak ada nilai simulasi yang menyamar sebagai data nyata, termasuk gambar share.
- [ ] Selected state terlihat tanpa mengandalkan warna; touch ≥48dp; TalkBack dan text scaling diuji.
- [ ] Navigasi kembali tidak kehilangan input dan tidak membuat request route ganda.
- [ ] Peta tidak menutupi bottom controls, attribution, legend, dan selected leg.
- [ ] Tidak ada overflow, clipping, skeleton layout jump, atau animasi mengganggu.

### Test flow untuk usability (dari Bab 14.8)

1. Dari Beranda pilih asal dan tujuan di area pilot, lalu cari rute.
2. Bandingkan opsi Terbersih/Seimbang/Tercepat dengan motor dan mobil.
3. Pilih waktu keberangkatan yang lebih baik bila fiturnya tersedia.
4. Simpan satu perjalanan ke Riwayat, lalu cek ringkasan.
5. Buka Insight Kota dan pahami perbedaan hasil model vs paparan pengguna.

Uji dengan **5 responden di luar tim** bila mengejar Should. Rekam task success, completion time, kesalahan, dan SUS; perbaiki bottleneck nyata, bukan hanya kosmetik.

### Release gate

- [ ] Build APK Android, smoke test 2 perangkat (low-end + mid-range), Android 8+.
- [ ] Tidak ada secret/client key yang tidak boleh berada di APK.
- [ ] Backend/API failure memberi recovery; offline fixture dapat menjalankan core demo.
- [ ] Copy dan metadata data-quality diperiksa P2/P4; threshold ISPU dari sumber yang diverifikasi.
- [ ] P4 meninjau visual APK vs Figma/token; P3 meninjau implementasi interaksi.
- [ ] Video demo maksimal **2 menit** jika dipakai untuk pengumpulan hackathon sesuai PDF.

---

## 14. Figma / handoff output [PROPOSAL]

Gunakan satu Figma file/struktur logis:

```text
00_Cover_&_Brand             # moodboard, logo, air-flow motifs
01_Foundations               # colors, text, 8pt grid, radii, elevation, icon set
02_Components                # badges, buttons, route cards, maps, sheets, chart
03_Onboarding                # 3 steps + permission states
04_Travel_Flow               # home, mode, results, detail, departure, active
05_Insights_&_Profile        # history, city insights, profile
06_States                    # loading, error, offline, empty, out-of-area, demo
07_Prototype                 # clickable happy path + safe back behavior
08_Dev_Handoff               # widget mapping, token export, accessibility notes
```

Design frames: **390×844** (utama), **320×700** (stress test), **412×915** (tall), **tablet** if time. Komponen Figma harus memakai Auto Layout, variants `default/selected/pressed/disabled/loading/error`, color/text variables, dan nama sesuai widget Flutter. Tulis **data fixture disclosure** pada preview yang memuat angka demo. Design final harus dapat diimplementasi tanpa pixel-perfect hacks.

---

## 15. Open questions yang harus diselesaikan sebelum wiring API

| Pertanyaan | Dampak frontend | Owner disarankan |
|---|---|---|
| Contract `openapi.yaml` sudah final? | DTO, nullability, `data_quality`, endpoint path | P1 |
| Cara user mencari lokasi & geocoding? | Autocomplete, pin drag, fallback manual | P1 / P3 |
| `arrive_at` didukung? | Waktu tiba pada form dan route planner | P1 |
| Skema kategori ISPU dari P50? | Legend map/warna segmen akurat | P2 / P4 |
| Confidence berada di tingkat mana? | Badge route, AQ point, tile/timestamps | P1 / P2 |
| `dose_ug_p10/p90` per leg selalu ada? | Range chart/timeline, null states | P1 / P2 |
| Cost motor/mobil ada pada response? | FR-05 UI comparison card | P1 |
| Geometri leg yang tidak memiliki polyline? | Focus map & timeline handling | P1 |
| Data 15 menit benar dikembalikan? | Departure chart / should-scope | P1 / P2 |
| Daily estimated dose tersedia & valid? | Daily share/cigarette-equivalent display | P2 / P4 |
| GeoJSON kelurahan/join key & methodology? | Choropleth, city ranking | P2 |
| Lisensi map tiles/font/icon source? | Attribution & distribusi APK | P3 / P4 |

---

## 16. Definition of the intended final impression

Ketika aplikasi dibuka, pengguna melihat **map berlapis informasi yang tetap ringan**, search card yang mengundang aksi, dan sebuah ringkasan udara yang transparan. Ketika hasil muncul, pengguna langsung memahami **trade-off dosis vs menit** dari tiga pilihan dan perbandingan kendaraan pribadi melalui kartu ekspresif serta bar komparasi. Di detail, perjalanan dijelaskan secara bertahap. Di seluruh pengalaman, UI terasa optimis, kaya tetapi tertata, dan jujur tentang keterbatasan model.

**Tagline visual:** **“Bukan sekadar sampai. Tapi memilih cara yang lebih baik untuk bernapas.”**

**North star UI:** dalam ≤10 detik setelah hasil tersedia, pengguna bisa menjawab: **“Rute mana yang saya pilih, berapa tambahan waktunya, dan seberapa besar estimasi perubahan dosisnya?”**

---

### Lampiran — sumber dan ruang lingkup

- `Hirup_Spesifikasi_Proyek_v2.pdf` v2.0 (13 Oktober 2026), terutama Bab 1, 4, 6–8, 9.3, 10.4, 12.4–12.5, 13, 14, 15, 17–18.
- ZIP `Hirup Trip Planning App.zip` (prototipe web responsif), terutama `docs/FLUTTER_HANDOFF.md`, `src/App.tsx`, `src/index.css`.
- Warna, gradient, card styling, komposisi map-first, animation timings, dan folder Flutter di dokumen ini adalah **usulan perancangan**, bukan klaim sudah tercantum dalam spesifikasi PDF atau diimplementasikan di ZIP.

*End of design specification.*
