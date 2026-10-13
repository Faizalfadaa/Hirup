> Spesifikasi teknis Hirup (bab 1–16 dan lampiran). Diagram tidak disertakan dalam versi Markdown ini.

**SPESIFIKASI PROYEK**

**Hirup**

Perencana Rute Multimoda Rendah Paparan Polusi Udara untuk Jakarta

Aplikasi Android · Transportasi umum, jalan kaki, sepeda, dengan pembanding motor dan mobil

| **Atribut**   | **Keterangan**                                                                                                                                                                |
|---------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Lomba         | Hackathon JOINTS x INSPIRE 2026 (UGM) · Tema Healthcare                                                                                                                       |
| Subtema       | Warga kota di Asia setiap hari terpapar polusi udara dan kemacetan serta minim ruang hijau, sehingga kesulitan mengetahui tingkat paparan dan dampaknya bagi kesehatan mereka |
| Versi dokumen | 2.0 (revisi dari v1.0)                                                                                                                                                        |
| Tanggal       | 13 Oktober 2026                                                                                                                                                               |
| Disusun oleh  | v1.0: Tengku Naufal Saqib · v2.0: revisi tim                                                                                                                                  |
| Tim           | 4 mahasiswa                                |
| Platform      | Aplikasi Android (Flutter). Backend Python di 1 VM                                                                                                                            |
| Status        | Acuan kerja sprint 4 hari (13–16 Oktober). Tidak ada pengembangan setelah pengumpulan. Bagian bertanda "verifikasi" wajib dikonfirmasi di H0                                  |


Daftar Isi

1\. Ringkasan Eksekutif

2\. Latar Belakang dan Pernyataan Masalah

3\. Analisis Solusi yang Sudah Ada

4\. Visi, Proposisi Nilai, dan Metrik

5\. Persona dan Perjalanan Pengguna

6\. Ruang Lingkup

7\. Kebutuhan Fungsional

8\. Kebutuhan Non-Fungsional

9\. Arsitektur Sistem

10\. Spesifikasi Data

11\. Spesifikasi Machine Learning

12\. Algoritma Routing dan Model Paparan

13\. Spesifikasi API

14\. Spesifikasi UI/UX Mobile

15\. Keamanan dan Privasi

16\. Strategi Pengujian

Lampiran A. Struktur Repositori

Lampiran B. Definition of Done

Lampiran C. Glosarium

Lampiran D. Referensi

# 1. Ringkasan Eksekutif

**Hirup** adalah aplikasi Android perencana perjalanan di Jakarta yang memilih rute bukan hanya berdasarkan waktu tempuh, tetapi juga berdasarkan **dosis polusi PM2.5 yang dihirup** pengguna sepanjang perjalanan. Hirup menggabungkan TransJakarta, MRT, LRT, jalan kaki, dan sepeda, lalu membandingkannya secara adil dengan motor dan mobil pribadi. Dasarnya adalah peta kualitas udara beresolusi 100 m per jam yang dihasilkan model machine learning.

Setiap pencarian menghasilkan tiga opsi, **Tercepat**, **Terbersih**, dan **Seimbang**, dengan rincian dosis per leg (jalan kaki, menunggu, di dalam kendaraan) serta perbandingan dengan motor dan mobil.

Tiga masalah dalam subtema dijawab sekaligus:

- **Paparan tidak terlihat** → dosis per perjalanan dan per hari ditampilkan konkret, termasuk porsinya terhadap dosis harian dan padanan rokok per hari.

- **Kemacetan** → perbandingan langsung transit vs motor/mobil dari sisi waktu, dosis, dan CO₂, mendorong perpindahan ke transportasi umum.

- **Minim ruang hijau** → leg jalan kaki dan sepeda diarahkan lewat koridor yang lebih hijau dan jauh dari arteri; tab Insight Kota memetakan kelurahan dengan paparan tinggi dan ruang hijau rendah.

**Pembeda utama.** Aplikasi kualitas udara di Indonesia (Nafas, JAKI, udara.jakarta.go.id) hanya menampilkan AQI per lokasi. Semua aplikasi rute rendah polusi yang kami temukan (Green Paths Helsinki, Purify London, Healthy Route Planner Valencia, Fresh Route, Insight Dublin) **hanya untuk jalan kaki dan sepeda**. Riset multimoda yang ada masih berupa simulasi. Belum ditemukan produk yang memadukan **transit multimoda + motor + paparan per leg + konteks kota Asia**.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Target sprint 4 hari (Must + Should)</strong></p>
<p>• Area pilot: koridor MRT Lebak Bulus–Bundaran HI + TransJakarta Koridor 1 (±136 km², ±13.600 sel grid 100 m).</p>
<p>• APK Android: cari rute 3 opsi (transit, sepeda, jalan kaki), kartu paparan per leg, pembanding motor/mobil, saran jam berangkat, prakiraan 24 jam, riwayat dan ringkasan mingguan di perangkat, tab Insight Kota.</p>
<p>• Model PM2.5 per jam pada grid 100 m dengan interval P10–P90, dibandingkan terbuka dengan baseline IDW pada validasi leave-one-station-out.</p>
<p>• Bukti dampak: median penurunan dosis Terbersih vs Tercepat pada 50 pasangan asal–tujuan, uji sensitivitas, dan validasi eksternal (hold-out waktu &amp; sumber), dilaporkan apa adanya.</p>
<p>• <strong>UI/UX kelas produk</strong>: design system sendiri, 10 layar hi-fi dengan state lengkap, animasi khas, dan uji usability 5 responden. Targetnya terasa seperti aplikasi yang siap dipakai, bukan prototipe.</p></td>
</tr>
</tbody>
</table>

# 2. Latar Belakang dan Pernyataan Masalah

## 2.1 Konteks

Jakarta memiliki sistem pemantauan kualitas udara paling lengkap di Indonesia: per Oktober 2025 terdapat **111 Stasiun Pemantau Kualitas Udara (SPKU)**, gabungan stasiun referensi dan sensor berbiaya rendah, yang datanya ditampilkan di udara.jakarta.go.id dan JAKI. Di sisi mobilitas, TransJakarta mengangkut sekitar 1 juta penumpang per hari, ditambah Mikrotrans dan MRT (verifikasi angka terbaru sebelum masuk deck).

Studi paparan personal terbaru memperkuat masalahnya. Vital Strategies (2026) memasang sensor pribadi 24 jam pada 51 siswa SD di Jakarta dan menemukan sekitar 4 dari 5 anak terpapar PM2.5 di atas baku mutu harian 55 µg/m³, dengan **perjalanan pagi ke sekolah sebagai periode paling berisiko** di luar rumah akibat kemacetan.

Meski data tersedia, warga tetap tidak tahu berapa polusi yang mereka hirup. ISPU/AQI menggambarkan udara di titik stasiun, bukan paparan orang yang bergerak: berjalan di trotoar arteri, menunggu di halte median jalan, lalu duduk di bus ber-AC. Akibatnya informasi kualitas udara jarang berubah menjadi keputusan perjalanan.

## 2.2 Pernyataan masalah

**Komuter di Jakarta tidak punya cara untuk mengetahui dan mengurangi dosis polusi udara yang mereka hirup selama perjalanan harian, dan pilihan transportasi yang tersedia tidak mempertimbangkan faktor kesehatan ini.**

## 2.3 Akar masalah

| **Akar masalah**                                          | **Dampak**                                             | **Jawaban Hirup**                                                                |
|-----------------------------------------------------------|--------------------------------------------------------|----------------------------------------------------------------------------------|
| Informasi kualitas udara berbasis stasiun, bukan individu | Warga tidak bisa mengaitkan AQI dengan aktivitasnya    | Dosis dihitung per leg perjalanan dan per hari                                   |
| Resolusi data kasar (stasiun jarang)                      | Perbedaan jalan arteri vs jalan paralel tidak terlihat | Downscaling ML ke grid 100 m dengan fitur jalan, bangunan, vegetasi              |
| Navigasi hanya mengoptimalkan waktu                       | Rute tercepat sering lewat koridor paling tercemar     | Optimasi dua tujuan (waktu, dosis) dengan himpunan Pareto                        |
| Pilihan moda tidak dibandingkan dari sisi kesehatan       | Ketergantungan pada motor di jalan terbuka             | Perbandingan transit vs motor vs mobil dengan model mikro-lingkungan yang sama   |
| Satuan µg/m³ dan ISPU abstrak                             | Tidak memicu perubahan perilaku                        | Perbandingan antar-opsi dalam persen, porsi dosis harian, padanan rokok per hari |

*Tabel 2.1 Akar masalah dan respons solusi*

# 3. Analisis Solusi yang Sudah Ada

Komponen solusi ini sudah ada secara terpisah. Kebaruan Hirup terletak pada **integrasinya untuk perjalanan multimoda di kota Asia**. Tabel ini disertakan terbuka di proposal dan pitch deck sebagai *related work*; menyebut pesaing terdekat justru memperkuat kredibilitas.

| **Solusi**                             | **Apa yang dilakukan**                                                              | **Keterbatasan relevan**                                          |
|----------------------------------------|-------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| Nafas (Indonesia)                      | Jaringan sensor, peta AQI real-time, notifikasi lokasi                              | AQI per lokasi; tidak menghitung dosis perjalanan; tidak ada rute |
| JAKI / udara.jakarta.go.id             | ISPU 111 SPKU, peringkat lokasi, panduan aktivitas                                  | Informasi per stasiun; tidak ada API publik                       |
| Sh\*\*t! I Smoke                       | Konversi PM2.5 stasiun ke batang rokok (aturan Berkeley Earth)                      | Hanya lokasi saat ini; tidak memperhitungkan pergerakan           |
| Google Maps, Moovit, JakLingko         | Rute transit multimoda                                                              | Tidak memakai kualitas udara dalam pemilihan rute                 |
| Green Paths (Univ. Helsinki)           | Rute jalan kaki & sepeda dengan polusi, kebisingan, area hijau                      | Hanya jalan kaki/sepeda; Helsinki                                 |
| Purify (Imperial College, 2025)        | Green routing London, sensor Breathe London + TomTom                                | Hanya jalan kaki/sepeda                                           |
| Healthy Route Planner (Valencia, 2026) | Rute jalan kaki/sepeda dipersonalisasi untuk kelompok rentan                        | Hanya jalan kaki/sepeda; paparan turun hingga 11,6%               |
| Insight DCU (Dublin)                   | Rute bersih berbasis data Google AQ                                                 | Prototipe; jalan kaki/sepeda                                      |
| Fresh Route (pemenang hackathon Utah)  | Rute jalan kaki dengan udara lebih bersih                                           | Prototipe hackathon; jalan kaki                                   |
| AQI Path, Citamoove                    | Rute rendah AQI untuk jalan kaki, lari, sepeda (AQI Path juga mobil)                | Tidak memodelkan transportasi umum                                |
| Riset multimoda (Chengdu, 2025)        | Model penugasan lalu lintas dengan biaya paparan, termasuk bus, metro, waktu tunggu | Simulasi di jaringan benchmark, bukan aplikasi                    |
| OpenTripPlanner Data Overlay           | Fitur eksperimental penalti kualitas udara di OTP                                   | Infrastruktur, bukan produk; dipakai sebagai inspirasi            |
| Plume Labs Flow                        | Sensor wearable paparan personal                                                    | Penjualan konsumen dihentikan; butuh hardware                     |

*Tabel 3.1 Lanskap solusi (sumber di Lampiran D)*

## 3.1 Celah yang diisi Hirup

1.  **Transit-aware clean routing**: rute bersih yang mencakup BRT, MRT, LRT, termasuk paparan saat menunggu di halte dan stasiun.

2.  **Perbandingan moda yang adil**: transit, jalan kaki, sepeda, motor, dan mobil diberi skor dengan model mikro-lingkungan yang sama.

3.  **Paparan personal tanpa hardware**: dihitung dari lintasan rute dan model kualitas udara.

4.  **Data untuk kebijakan**: peta paparan dan ketimpangan ruang hijau per kelurahan.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Argumen inti: kenapa multimoda lebih penting</strong></p>
<p>Riset rute jalan kaki/sepeda hanya menurunkan paparan sekitar 8–18% dengan cara memutar jalan (Barcelona 7,8%, Valencia 11,6%, Dublin 17,9%). Perbedaan antar-moda jauh lebih besar: studi Delhi menemukan bus ber-AC punya paparan dalam kendaraan terendah dan moda terbuka tertinggi. Keputusan terbesar bagi kesehatan bukan "lewat jalan mana", tetapi <strong>"naik apa dan berangkat jam berapa"</strong>. Perbedaan ini juga tetap terlihat meski data kualitas udara tidak sempurna, sehingga model lebih tahan terhadap ketidakpastian.</p></td>
</tr>
</tbody>
</table>

# 4. Visi, Proposisi Nilai, dan Metrik

## 4.1 Visi

*Setiap warga kota bisa melihat polusi yang ia hirup dan memilih perjalanan yang lebih sehat, dan pilihan sehat itu sering kali adalah transportasi umum.*

## 4.2 Proposisi nilai

| **Pengguna**                                                     | **Pekerjaan yang ingin diselesaikan**                   | **Nilai yang diberikan**                                     |
|------------------------------------------------------------------|---------------------------------------------------------|--------------------------------------------------------------|
| Komuter harian                                                   | Sampai tujuan tepat waktu tanpa merusak kesehatan       | Rute dengan dosis lebih rendah dan tambahan waktu yang jelas |
| Kelompok rentan (asma, lansia, ibu hamil, orang tua dengan anak) | Menghindari paparan tinggi pada jam dan lokasi tertentu | Profil rentan, saran jam berangkat, peringatan               |
| Pengendara motor                                                 | Memutuskan apakah layak pindah ke transportasi umum     | Perbandingan waktu, dosis, biaya, dan CO₂ motor vs transit   |
| Pesepeda dan pejalan kaki                                        | Rute aktif yang lebih bersih dan teduh                  | Rute sepeda/jalan kaki berbobot paparan dan area hijau       |
| Pemerintah daerah (DLH, Dishub, Dinkes)                          | Prioritas intervensi udara dan ruang hijau              | Tab Insight Kota: paparan dan ketimpangan per kelurahan      |

## 4.3 Metrik keberhasilan

**North Star Metric:** total dosis PM2.5 yang dihindari pengguna per minggu (µg), yaitu selisih dosis opsi yang dipilih terhadap opsi Tercepat.

| **Dimensi**               | **Metrik**                                                                                                                        | **Batas lulus (Must)**                    | **Target ambisius (Should)**                          |
|---------------------------|-----------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------|-------------------------------------------------------|
| Dampak rute               | Median penurunan dosis Terbersih vs Tercepat pada 50 pasangan OD × 3 slot jam                                                     | ≥ 15% dengan tambahan ≤ 10 menit          | ≥ 20%; dilaporkan apa adanya                          |
| Dampak moda               | Selisih dosis motor vs opsi transit terbaik pada OD yang sama                                                                     | Dilaporkan sebagai distribusi             | \+ dibandingkan dengan rasio moda dari studi terbitan |
| Akurasi model             | RMSE PM2.5 per jam, leave-one-station-out                                                                                         | Lebih rendah dari IDW                     | ≥ 15% lebih rendah dari IDW                           |
| Kalibrasi ketidakpastian  | Cakupan interval P10–P90                                                                                                          | Dilaporkan                                | 70–90%                                                |
| Performa                  | Latensi p95 POST /v1/routes/plan                                                                                                  | ≤ 5 detik                                 | ≤ 3 detik                                             |
| Kualitas aplikasi         | APK berjalan tanpa crash di perangkat uji                                                                                         | 2 perangkat Android (low-end & mid-range) | \+ uji beban 20 pengguna serentak (Could)             |
| Kualitas UI               | Layar Must yang lulus checklist UI (Bab 14.7)                                                                                     | 100% layar Must                           | 100% layar Must + Should                              |
| Usability                 | Uji tugas inti + System Usability Scale                                                                                           | Uji 5 responden dilakukan                 | SUS ≥ 75; keberhasilan tugas ≥ 90%                    |
| Validasi eksternal (data) | RMSE pada data yang tidak dipakai melatih: hold-out waktu (20% periode terakhir) dan hold-out sumber (stasiun di luar data latih) | Hold-out waktu dilaporkan                 | RMSE hold-out ≤ 1,2× RMSE LOSO; + hold-out sumber     |

*Tabel 4.1 Metrik keberhasilan. Batas lulus wajib tercapai; target ambisius dikejar dan hasilnya dilaporkan apa adanya.*

# 5. Persona dan Perjalanan Pengguna

## 5.1 Persona

| **Persona**               | **Profil**                                                                 | **Kebutuhan dan frustrasi**                                                     |
|---------------------------|----------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| Raka, 26, karyawan swasta | Tinggal di Lebak Bulus, kerja di Sudirman. Naik motor ±50 menit tiap hari. | Capek macet, sering batuk, tidak yakin transit lebih cepat. Ingin data konkret. |
| Dinda, 20, mahasiswi      | Naik MRT + jalan kaki/sepeda ke kampus.                                    | Ingin rute jalan kaki/sepeda yang lebih teduh. Suka konten yang bisa dibagikan. |
| Bu Sari, 41, ibu dua anak | Anak bungsu asma. Mengantar anak naik TransJakarta.                        | Butuh tahu jam berangkat yang lebih aman. Tidak paham angka ISPU.               |
| Pak Hendra, analis DLH    | Menyusun rekomendasi kebijakan udara dan ruang hijau.                      | Data stasiun tidak menunjukkan di mana warga terpapar saat bergerak.            |

## 5.2 Perjalanan pengguna utama (Raka)

1.  Malam sebelumnya Raka membuka tab "Besok": prakiraan menunjukkan PM2.5 di koridor Fatmawati tinggi pukul 07.00. Berangkat 06.30 menurunkan dosis perjalanan sekitar 15–20% (angka dari model, ditampilkan beserta rentangnya).

2.  Pagi hari ia memasukkan tujuan kantor. Aplikasi menampilkan tiga kartu: **Tercepat** (MRT, 38 menit), **Terbersih** (rute jalan kaki lebih hijau ke stasiun + MRT, 44 menit, dosis −25% vs Tercepat), dan **Seimbang**.

3.  Kartu pembanding menunjukkan motor: 50 menit, **dosis sekitar 1,8× opsi Tercepat**, ditambah estimasi CO₂ dan biaya.

4.  Raka memilih Seimbang. Detail rute menyorot segmen merah dan menyarankan menunggu di dalam stasiun, bukan di trotoar.

5.  Akhir minggu, ringkasan menunjukkan: "Perjalananmu hanya 7% dari harimu, tapi menyumbang ±11% dosis harianmu saat naik motor. Minggu ini kamu menghindari X µg dibanding rute biasamu." Kartu ini bisa dibagikan.

*Semua angka di atas adalah ilustrasi format. Angka final berasal dari model dan dilaporkan apa adanya.*

# 6. Ruang Lingkup

## 6.1 Area pilot

**Koridor Selatan–Pusat Jakarta**: buffer ±3 km kiri-kanan jalur MRT Lebak Bulus–Bundaran HI, diperpanjang ke Kota mengikuti TransJakarta Koridor 1. Area ini memuat simpul integrasi multimoda (Dukuh Atas, Blok M, Lebak Bulus), kontras lingkungan yang besar (arteri Sudirman–Thamrin vs perumahan Kebayoran), dan kepadatan stasiun yang relatif tinggi.

| **Parameter**          | **Nilai**                                                                                             |
|------------------------|-------------------------------------------------------------------------------------------------------|
| Batas kasar (lat, lon) | −6,30 s.d. −6,13; 106,76 s.d. 106,85 (difinalkan di H0)                                               |
| Luas dan grid          | ±136 km² · grid 100 m × 100 m pada EPSG:32748 (UTM 48S) → ±13.600 sel                                 |
| Moda dirutekan penuh   | TransJakarta BRT & non-BRT, MRT, LRT Jakarta, jalan kaki, sepeda                                      |
| Moda pembanding        | Motor dan mobil, dirutekan lewat OSRM (2–3 alternatif) dan diberi skor paparan dengan mesin yang sama |
| Polutan                | PM2.5 (satu-satunya polutan yang dimodelkan)                                                          |

## 6.2 Lingkup dengan MoSCoW

Semua pekerjaan terjadi dalam satu sprint 4 hari; setelah 16 Oktober tidak ada pengembangan lagi. Karena itu lingkup ditata dengan **MoSCoW** dan sengaja dibuat ambisius: Must adalah produk minimum yang wajib jadi, Should adalah target sebenarnya tim, dan Could diambil begitu lajur seseorang selesai lebih cepat.

<table>
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 24%" />
<col style="width: 23%" />
</colgroup>
<thead>
<tr class="header">
<th><strong>Must (wajib, H0–H2)</strong></th>
<th><strong>Should (target tim, H2–H3)</strong></th>
<th><strong>Could (stretch, bila sempat)</strong></th>
<th><strong>Won't (tidak di lomba ini)</strong></th>
</tr>
</thead>
<tbody>
<tr class="odd">
<td><p>Rute 3 opsi: TransJakarta, MRT, LRT, jalan kaki</p>
<p>Rute sepeda berbobot paparan</p>
<p>Rincian dosis per leg + polyline berwarna</p>
<p>Pembanding motor &amp; mobil (OSRM)</p>
<p>Peta PM2.5 100 m per jam + tap titik (P10–P90)</p>
<p>LightGBM + quantile, LOSO vs IDW</p>
<p>Profil umum / rentan</p>
<p>Riwayat di perangkat</p>
<p>API live + APK rilis + video 2 menit</p>
<p>Design system + 10 layar hi-fi (design freeze H1)</p>
<p>State loading, kosong, error, di luar area</p>
<p>Onboarding 3 langkah</p>
<p>Mode demo dengan data fixture berlabel</p></td>
<td><p>Uji usability 5 responden + perbaikan</p>
<p>Animasi khas (Bab 14.6)</p>
<p>Saran jam berangkat + prakiraan 24 jam terkoreksi</p>
<p>Ringkasan mingguan + kartu berbagi</p>
<p>Insight Kota: koroplet + indeks ketimpangan ruang hijau</p>
<p>Preferensi + lokasi favorit</p>
<p>Slider bobot waktu ↔︎ udara (re-rank di klien)</p>
<p>Laporan 50 OD + uji sensitivitas</p>
<p>Validasi eksternal (hold-out waktu &amp; sumber) + SHAP</p>
<p>Latensi p95 ≤ 3 dtk</p></td>
<td><p>Notifikasi lokal prakiraan buruk (tanpa server push)</p>
<p>Ruang hijau terdekat + jam terbaik</p>
<p>Mikrotrans (jika ada di feed GTFS)</p>
<p>Regression kriging residual</p>
<p>Uji beban Locust</p>
<p>Mode gelap</p>
<p>Haptic + suara halus pada aksi utama</p></td>
<td><p>Akun + sinkronisasi, iOS</p>
<p>KRL, LRT Jabodebek, seluruh DKI</p>
<p>Agregat data pengguna (butuh pengguna nyata)</p>
<p>GTFS-Realtime, pembayaran JakLingko</p>
<p>Data SPKU via PPID (tidak tiba sebelum tenggat)</p>
<p>Perangkat keras / sensor</p>
<p>NO₂, O₃</p>
<p>Diagnosis atau saran medis</p></td>
</tr>
</tbody>
</table>

*Tabel 6.1 Aturan main: Should mulai dikerjakan setelah gerbang G1 lulus; Could hanya diambil anggota yang lajur Must + Should-nya sudah selesai, dan berhenti total pada freeze H3 12.00.*

## 6.3 Asumsi dan batasan

- **Tenggat pengumpulan belum pasti**: guidebook menulis 15–16 Oktober 23.50 WIB, website menulis 23 Oktober. Rencana mengacu ke **16 Oktober**. Jika 23 Oktober dikonfirmasi panitia, item Could dikerjakan dengan waktu tambahan itu; jadwal tetap satu sprint.

- Data SPKU tidak punya API publik; data historisnya hanya lewat permintaan PPID. Karena tidak akan tiba sebelum tenggat, Hirup memakai OpenAQ + WAQI + ISPU historis (Bab 10).

- Feed GTFS TransJakarta resmi tersedia di Mobility Database (240 rute). Status lisensi dicantumkan sebagai atribusi + penggunaan non-komersial lomba.

- Faktor mikro-lingkungan per moda diambil dari literatur, disimpan sebagai parameter yang bisa dikonfigurasi, lalu diuji lewat analisis sensitivitas dan pembandingan dengan studi paparan terbitan.

- Tim 4 mahasiswa dibantu asisten AI. Manusia memegang keputusan arsitektur, verifikasi sumber ilmiah, dan review sebelum merge.

# 7. Kebutuhan Fungsional

Prioritas MoSCoW (**M** Must, **S** Should, **C** Could, **W** Won't) mengikuti Tabel 6.1. Kriteria penerimaan ditulis agar bisa langsung menjadi test case.

## 7.1 Perencanaan rute

| **ID** | **Kebutuhan**                                                                | **Prio** | **Kriteria penerimaan**                                                                  |
|--------|------------------------------------------------------------------------------|----------|------------------------------------------------------------------------------------------|
| FR-01  | Input asal (GPS/pencarian/pin), tujuan, waktu berangkat atau tiba            | M        | Pin dapat digeser; default waktu = sekarang; di luar area pilot → pesan jelas            |
| FR-02  | Hingga 3 opsi berlabel Tercepat, Terbersih, Seimbang                         | M        | Opsi identik → label digabung; tiap opsi: durasi, transfer, dosis, selisih % vs Tercepat |
| FR-03  | Rincian per leg (jalan kaki, sepeda, tunggu, naik moda) dengan dosis per leg | M        | Σ dosis leg = total dosis (toleransi pembulatan 1%)                                      |
| FR-04  | Polyline rute diwarnai konsentrasi per segmen                                | M        | Skala warna konsisten dengan legenda ISPU + label teks                                   |
| FR-05  | Kartu pembanding motor dan mobil (waktu, dosis, CO₂, biaya)                  | M        | Selalu tampil; asumsi faktor emisi & kemacetan dapat dibuka                              |
| FR-06  | Mode moda: Transit / Sepeda / Jalan kaki / Semua                             | M        | Kandidat rute mengikuti mode yang dipilih                                                |
| FR-07  | Preferensi: maks. jalan kaki, hindari transfer, moda dikecualikan            | S        | Tersimpan di perangkat dan memengaruhi kandidat                                          |
| FR-08  | Slider bobot waktu ↔ udara bersih                                            | S        | Urutan berubah tanpa memanggil ulang OTP (re-rank di klien)                              |

## 7.2 Kualitas udara dan paparan

| **ID** | **Kebutuhan**                                                  | **Prio** | **Kriteria penerimaan**                                               |
|--------|----------------------------------------------------------------|----------|-----------------------------------------------------------------------|
| FR-10  | Lapisan peta PM2.5 grid 100 m untuk jam berjalan               | M        | Tersedia ≤ 20 menit setelah pergantian jam; transparansi dapat diatur |
| FR-11  | Tap peta → PM2.5 P50 dan rentang P10–P90                       | M        | Respons ≤ 500 ms                                                      |
| FR-12  | Prakiraan per jam ≤ 24 jam untuk titik dan rute                | S        | Dari CAMS yang dikoreksi bias model                                   |
| FR-13  | Saran jam berangkat: jendela ±90 menit, slot 15 menit          | S        | Menampilkan selisih dosis (%) dan waktu tempuh per slot               |
| FR-14  | Catat perjalanan yang dikonfirmasi pengguna                    | M        | Disimpan di perangkat; dapat dihapus                                  |
| FR-15  | Ringkasan mingguan: dosis, dosis dihindari, porsi dosis harian | S        | Dapat diekspor sebagai gambar kartu berbagi                           |
| FR-16  | Ruang hijau terdekat dengan udara terbaik                      | C        | 5 taman terdekat + PM2.5 + jam terbaik hari ini                       |

## 7.3 Profil dan notifikasi

| **ID** | **Kebutuhan**                                               | **Prio** | **Kriteria penerimaan**                                                 |
|--------|-------------------------------------------------------------|----------|-------------------------------------------------------------------------|
| FR-20  | Mode tamu tanpa akun (akun: Won't)                          | M        | Semua fitur inti berjalan tanpa login                                   |
| FR-21  | Profil sensitivitas: umum / rentan                          | M        | Mengubah α, toleransi waktu Terbersih, dan ambang peringatan (Bab 12.4) |
| FR-22  | Lokasi favorit (rumah, kantor, sekolah)                     | S        | Maks. 10, disimpan di perangkat                                         |
| FR-23  | Notifikasi lokal prakiraan buruk untuk perjalanan rutin     | C        | Dijadwalkan di perangkat; maks. 1×/hari; dapat dimatikan                |
| FR-24  | Mode demo offline berisi 5 skenario fixture, berlabel jelas | M        | Semua layar inti bisa didemokan tanpa internet                          |

## 7.4 Tab Insight Kota (pengganti dashboard web)

| **ID** | **Kebutuhan**                                                                   | **Prio** | **Kriteria penerimaan**                                          |
|--------|---------------------------------------------------------------------------------|----------|------------------------------------------------------------------|
| FR-30  | Koroplet rata-rata PM2.5 per kelurahan (hasil model)                            | S        | Filter jam dan hari; data dari raster model, bukan data pengguna |
| FR-31  | Indeks ketimpangan: paparan tinggi × ruang hijau rendah × kepadatan penduduk    | S        | Peringkat kelurahan prioritas; metodologi dapat dibuka           |
| FR-32  | Titik paparan komuter (halte, segmen jalan kaki tercemar) dari agregat pengguna | W        | Butuh pengguna nyata; tidak dikerjakan di lomba ini              |

# 8. Kebutuhan Non-Fungsional

| **Kategori**     | **Kebutuhan**                      | **Target**                                                                                              |
|------------------|------------------------------------|---------------------------------------------------------------------------------------------------------|
| Performa         | Latensi perencanaan rute           | p95 ≤ 5 dtk (Must), ≤ 3 dtk (Should); hasil di-cache 10 menit per (sel asal, sel tujuan, slot 15 menit) |
| Performa         | Latensi query titik kualitas udara | p95 ≤ 500 ms (raster dibaca per jendela kecil)                                                          |
| Kesegaran data   | Raster prediksi                    | Diperbarui tiap jam, ≤ 20 menit setelah data sumber masuk                                               |
| Degradasi anggun | Jika model gagal                   | Fallback ke IDW + CAMS; UI menandai "akurasi rendah"                                                    |
| Ketersediaan     | Selama masa penilaian lomba                   | Restart otomatis kontainer + monitor uptime sederhana                                                   |
| Mobile           | Perangkat target                   | Android 8+; jalan lancar di perangkat RAM 3 GB; ukuran APK ≤ 60 MB                                      |
| Privasi          | UU No. 27/2022 PDP                 | Tanpa pelacakan GPS latar belakang; riwayat di perangkat (Bab 15)                                       |
| Keamanan         | API                                | HTTPS; rate limit per IP; API key pihak ketiga hanya di server                                          |
| Aksesibilitas    | UI                                 | Kontras WCAG AA; warna tidak jadi satu-satunya penanda; ikuti ukuran huruf sistem                       |
| Reprodusibilitas | ML dan konstanta ilmiah            | Seed tetap; versi data & model tercatat; semua konstanta di file konfigurasi dengan kolom sumber        |

# 9. Arsitektur Sistem

## 9.1 Gambaran umum

Backend memakai pola **modular monolith**: satu codebase FastAPI yang dipisah per domain (route, aq, exposure), dengan komponen berat (OpenTripPlanner, OSRM, pipeline data, inferensi ML) sebagai proses terpisah. Semua berjalan dengan Docker Compose di 1 VM. Untuk sprint 4 hari, data disimpan sebagai **Parquet + DuckDB** dan raster **Cloud-Optimized GeoTIFF** di disk, tanpa database server; PostGIS baru dipakai di Fase B saat ada data agregat pengguna.

*Gambar 9.1 Arsitektur komponen Hirup*

## 9.2 Komponen

| **Komponen**               | **Tanggung jawab**                                      | **Catatan desain**                                                                 |
|----------------------------|---------------------------------------------------------|------------------------------------------------------------------------------------|
| Aplikasi Android           | Cari rute, peta, kartu paparan, riwayat, Insight Kota   | Flutter 3 + maplibre_gl + Riverpod; riwayat di Isar/Hive; cache rute terakhir      |
| FastAPI /v1                | Validasi, rate limit, routing ke modul                  | Pydantic v2; OpenAPI = kontrak tunggal untuk aplikasi                              |
| Route Service              | Orkestrasi generate-and-rerank (Bab 12)                 | Memanggil OTP GraphQL, OSRM, dan router jalan kaki/sepeda secara paralel           |
| Router jalan kaki & sepeda | Rute optimal-paparan antara dua titik                   | Graf OSM di memori (OSMnx + rustworkx); bobot edge diperbarui tiap jam dari raster |
| OpenTripPlanner 2          | Routing transit multimoda                               | Kontainer Java; graf dibangun dari GTFS + OSM area pilot                           |
| OSRM                       | Rute motor dan mobil                                    | Kontainer; ekstrak OSM Jawa (Geofabrik); 2–3 alternatif; faktor kemacetan per jam  |
| Exposure Engine            | Dosis per leg, porsi harian, padanan rokok              | Fungsi murni + exposure_params.yaml dengan kolom sumber                            |
| Air Quality Service        | Nilai titik/garis/bbox, tile, prakiraan                 | Membaca COG terbaru; sampling polyline tiap 25 m                                   |
| Pipeline data              | Ingest, QC, kalibrasi, fitur                            | Skrip Python + cron; log ke ingest_runs.parquet                                    |
| ML Inference               | Raster PM2.5 P10/P50/P90 per jam + prakiraan terkoreksi | Job terjadwal; model dimuat dari disk; target \< 30 dtk                            |

## 9.3 Tech stack

| **Lapisan**         | **Pilihan**                                             | **Alasan**                                                             |
|---------------------|---------------------------------------------------------|------------------------------------------------------------------------|
| Mobile              | Flutter 3 + maplibre_gl + Riverpod + go_router + dio    | Satu codebase, build APK lokal tanpa layanan cloud, peta vektor gratis |
| Backend             | Python 3.12, FastAPI, Pydantic v2                       | Satu bahasa dengan stack ML; OpenAPI otomatis                          |
| Routing transit     | OpenTripPlanner 2.x                                     | Membaca GTFS + OSM langsung; multi-itinerary; GraphQL                  |
| Routing jalan       | OSRM                                                    | Cepat, alternatif rute, mudah di-Docker                                |
| Jalan kaki & sepeda | OSMnx + rustworkx                                       | Bobot kustom per jam; cepat untuk ±100 ribu edge                       |
| Data                | Parquet + DuckDB; GeoPandas, rasterio, xarray           | Tanpa server DB; query spasial-tabular cepat                           |
| ML                  | LightGBM, scikit-learn, Optuna, SHAP                    | Akurat untuk tabular; quantile regression bawaan                       |
| Tile peta           | Tile PNG pra-render per jam dari COG (rio-tiler)        | Lebih sederhana dari TiTiler untuk sprint 4 hari                       |
| Infra & CI          | Docker Compose di 1 VM (4 vCPU, 16 GB) · GitHub Actions | Cukup untuk area pilot; lint + test + build APK                        |

## 9.4 Alur data saat runtime

1.  Tiap 10 menit scraper WAQI berjalan; tiap jam pipeline menarik OpenAQ, cuaca, dan prakiraan CAMS, lalu menjalankan QC dan kalibrasi.

2.  Job inferensi membangun fitur dinamis untuk seluruh sel, menjalankan model, menulis pm25\_{yyyymmddhh}\_{p10\|p50\|p90}.tif, lalu memperbarui pointer "latest".

3.  Router jalan kaki/sepeda memuat raster terbaru dan memperbarui bobot edge (pemetaan edge → sel dihitung sekali saat build graf).

4.  Saat pengguna mencari rute, Route Service meminta kandidat ke OTP, OSRM, dan router sepeda, mengoptimalkan leg aktif, menghitung dosis, memilih set Pareto, lalu mengembalikan respons.

# 10. Spesifikasi Data

## 10.1 Sumber data

| **Sumber**                     | **Isi**                                                                  | **Resolusi / frekuensi**        | **Akses & lisensi**                                                            | **Peran**                                        |
|--------------------------------|--------------------------------------------------------------------------|---------------------------------|--------------------------------------------------------------------------------|--------------------------------------------------|
| OpenAQ API v3                  | Pengukuran stasiun termasuk Jakarta                                      | Titik, per jam, historis        | Gratis, API key, 60 req/menit & 2.000 req/jam                                  | Label utama (historis)                           |
| WAQI / aqicn API               | PM2.5 real-time stasiun Jakarta                                          | Titik, real-time                | Gratis, token. Data tidak boleh diredistribusi; dipakai internal sebagai label | Label live (scrape tiap 10 menit sejak H0)       |
| ISPU KLHK / Satu Data          | ISPU historis stasiun DKI                                                | Harian, 2010 dst.               | Unduh CSV                                                                      | Analisis pola & sanity check                     |
| Open-Meteo (cuaca)             | Angin, suhu, RH, hujan, tinggi lapisan batas (verifikasi nama parameter) | ±9–25 km, per jam + prakiraan   | Gratis non-komersial, tanpa key                                                | Fitur dinamis                                    |
| Open-Meteo Air Quality (CAMS)  | PM2.5, NO₂, dll. global + prakiraan 5 hari                               | ±45 km, per jam, sejak Agt 2022 | Gratis non-komersial, tanpa key                                                | Latar regional + dasar prakiraan                 |
| OpenStreetMap                  | Jalan (kelas), bangunan, taman, halte                                    | Vektor                          | ODbL (atribusi)                                                                | Fitur + graf jalan kaki/sepeda + OSRM            |
| ESA WorldCover / Sentinel-2    | Tutupan lahan, NDVI                                                      | 10 m                            | Gratis (CC-BY / GEE)                                                           | Fitur statis + skor keteduhan                    |
| WorldPop                       | Kepadatan penduduk                                                       | 100 m                           | Terbuka                                                                        | Fitur + indeks ketimpangan                       |
| GTFS TransJakarta (mdb-1909)   | 240 rute bus, halte, shapes                                              | Jadwal statis                   | Feed resmi; atribusi + non-komersial                                           | Graf transit OTP                                 |
| GTFS MRT & LRT Jakarta         | Stasiun, rute, headway                                                   | Jadwal statis                   | Dibuat manual dari jadwal resmi                                                | Graf transit OTP                                 |
| TomTom Traffic Flow (opsional) | Kecepatan vs free-flow per ruas                                          | Real-time                       | Gratis 20.000 req/bulan                                                        | Fitur lalu lintas + faktor kemacetan motor/mobil |
| Batas administrasi             | Poligon kelurahan DKI                                                    | Vektor                          | Data terbuka pemda/BIG                                                         | Agregasi Insight Kota                            |

*Tabel 10.1 Sumber data. Google Air Quality API dikeluarkan karena berbayar dan ketentuan penyimpanannya tidak cocok untuk data latih; dapat dipertimbangkan pasca-lomba.*

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Validasi H0 (wajib sebelum model dibangun)</strong></p>
<p>1) Hitung stasiun Jakarta di area pilot ± 10 km yang tersedia di OpenAQ dan WAQI, beserta panjang riwayat per jam.</p>
<p>2) Pastikan feed GTFS TransJakarta bisa diunduh dan shapes valid di area pilot.</p>
<p>3) Pastikan Open-Meteo menyediakan tinggi lapisan batas untuk Jakarta (nama parameter).</p>
<p><strong>Gerbang G0:</strong> jika &lt; 10 stasiun dengan ≥ 7 hari data per jam, model utama memakai IDW + CAMS + fitur statis (LUR sederhana), dan inovasi difokuskan pada routing multimoda.</p></td>
</tr>
</tbody>
</table>

## 10.2 Kontrol kualitas dan kalibrasi

- **Rentang fisik**: PM2.5 \< 0 atau \> 1.000 µg/m³ dibuang.

- **Flatline**: nilai identik ≥ 6 jam berturut-turut ditandai rusak.

- **Lonjakan**: perubahan \> 5σ terhadap median bergerak 24 jam yang tidak dikonfirmasi stasiun tetangga (≤ 3 km) ditandai.

- **Gap**: celah ≤ 2 jam boleh diinterpolasi untuk fitur, **tidak pernah** dipakai sebagai label.

- **Kalibrasi data sensor murah pihak ketiga** (data yang sudah terpublikasi di OpenAQ/WAQI, bukan perangkat milik tim): untuk pasangan sensor murah–stasiun referensi ≤ 1 km, latih PM_ref = a·PM_lcs + b·RH + c·PM_lcs·RH + d lalu terapkan per merek. Simpan versi koefisien.

- **Deduplikasi lintas sumber**: stasiun yang sama di OpenAQ dan WAQI digabung berdasarkan jarak ≤ 50 m dan korelasi tinggi.

- **Bobot sampel**: stasiun referensi diberi bobot lebih tinggi dari sensor murah terkalibrasi.

## 10.3 Model data

| **Artefak**                                            | **Isi utama**                                                             | **Format**                                   |
|--------------------------------------------------------|---------------------------------------------------------------------------|----------------------------------------------|
| stations                                               | station_id, name, type {reference, lcs}, source, lat, lon, active         | Parquet                                      |
| aq_observations                                        | station_id, ts, value_raw, value_cal, qc_flag, source                     | Parquet (partisi harian), di-query DuckDB    |
| grid_cells                                             | cell_id, geom, kelurahan_id, fitur statis                                 | GeoParquet (±13.600 baris)                   |
| weather_hourly                                         | cell_group_id, ts, wind_u, wind_v, temp, rh, precip, blh                  | Parquet                                      |
| pm25 rasters                                           | P10/P50/P90 per jam + prakiraan                                           | COG, 7 hari terakhir; arsip rata-rata harian |
| ped_bike_graph                                         | edge_id, u, v, length_m, highway, cell_ids\[\], shade_score, bike_allowed | Pickle/Parquet                               |
| model_registry                                         | model_version, trained_at, data_window, metrics, path, is_active          | JSON                                         |
| ingest_runs                                            | run_id, source, start, end, status, rows, error                           | Parquet                                      |
| (di perangkat) trips, trip_legs, saved_places, profile | Riwayat dan preferensi pengguna                                           | Isar/Hive lokal                              |

## 10.4 Strategi data dummy (fallback)

Tidak semua data dijamin bisa diambil dalam 4 hari (kuota API, stasiun sedikit, jadwal MRT/LRT manual, belum ada pengguna nyata). Agar UI dan demo tidak pernah terhambat, setiap komponen punya **jalur cadangan bertingkat**: data nyata → perkiraan dari data nyata → data dummy berlabel. Data dummy juga dipakai sejak H0 supaya lajur mobile bisa membangun UI final tanpa menunggu backend.

| **Komponen**                 | **Target (nyata)**                 | **Cadangan 1 (perkiraan)**                                       | **Cadangan 2 (dummy)**                                                                       | **Pemicu**                                        |
|------------------------------|------------------------------------|------------------------------------------------------------------|----------------------------------------------------------------------------------------------|---------------------------------------------------|
| Label PM2.5 stasiun          | OpenAQ + WAQI + ISPU               | CAMS + IDW + fitur statis (tetap data nyata)                     | Tidak ada. Model dan metriknya tidak boleh memakai data dummy                                | Gerbang G0                                        |
| Jadwal MRT/LRT               | GTFS manual dari jadwal resmi      | Trip sintetis dari headway resmi per jam                         | \-                                                                                           | GTFS manual belum lolos validasi H1               |
| Kemacetan motor/mobil        | TomTom free tier                   | Faktor kemacetan per jam dari profil tipikal yang dipublikasikan | \-                                                                                           | Kuota habis / API gagal                           |
| Prakiraan 24 jam             | CAMS terkoreksi model              | Rata-rata historis per jam-dalam-minggu                          | \-                                                                                           | Koreksi prakiraan belum siap                      |
| Insight Kota                 | Agregat raster model per kelurahan | Agregat CAMS + fitur statis                                      | Koroplet ilustrasi dengan pola dari ISPU historis                                            | Raster model belum stabil H2                      |
| Riwayat & ringkasan mingguan | \-                                 | \-                                                               | Selalu dummy di demo: 14 hari riwayat persona Raka & Bu Sari, dibuat skrip dengan seed tetap | Belum ada pengguna nyata                          |
| Respons rute end-to-end      | API live                           | Respons ter-cache dari API live                                  | Fixture JSON 5 skenario demo (Bab 14.8)                                                      | Server/OTP bermasalah saat rekaman atau penjurian |

*Tabel 10.4 Jalur cadangan per komponen. Tanda "-" berarti cadangan itu tidak diperlukan.*

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Aturan kejujuran data dummy (wajib)</strong></p>
<p>1. Setiap respons API membawa field data_quality: real, approximated, atau synthetic. Aplikasi menampilkan lencana "Perkiraan" atau "Data simulasi" pada kartu yang terdampak.</p>
<p>2. Data dummy <strong>tidak pernah</strong> dipakai untuk metrik model, laporan dampak 50 OD, atau angka di deck. Angka bukti hanya dari data nyata.</p>
<p>3. Dummy dibuat oleh skrip (fixtures/generate.py, seed tetap) dari distribusi yang realistis, misalnya pola jam dari ISPU historis, bukan angka karangan tangan.</p>
<p>4. README menyebutkan bagian mana yang memakai data simulasi.</p></td>
</tr>
</tbody>
</table>

# 11. Spesifikasi Machine Learning

## 11.1 Formulasi masalah

**Nowcast spasial (utama):** prediksi PM2.5 per jam y(s, t) di setiap sel 100 m s pada jam t, dengan label hanya di lokasi stasiun. Ini regresi spasio-temporal dengan pendekatan *Land Use Regression* (LUR) yang diperkaya fitur dinamis.

**Prakiraan 1–24 jam (sekunder):** untuk saran jam berangkat. Hirup memakai prakiraan CAMS (Open-Meteo) sebagai fitur latar + cuaca prakiraan, lalu dikoreksi model yang sama. Model prakiraan khusus tidak dibuat; koreksi bias sudah cukup untuk saran jam.

## 11.2 Fitur

| **Kelompok**           | **Fitur**                                                                                        | **Sumber**                                       |
|------------------------|--------------------------------------------------------------------------------------------------|--------------------------------------------------|
| Jalan                  | Panjang jalan per kelas dalam buffer 50/100/300/500 m; jarak ke trunk/primary; kepadatan simpang | OSM                                              |
| Transit                | Jarak ke koridor BRT; jumlah trip bus per jam yang melintas sel                                  | GTFS                                             |
| Bangunan               | Fraksi tapak bangunan, jumlah bangunan dalam buffer                                              | OSM / Google Open Buildings                      |
| Vegetasi & lahan       | NDVI rata-rata/maks buffer 100/300 m; fraksi pohon, built-up, air                                | Sentinel-2, WorldCover                           |
| Penduduk               | Kepadatan penduduk                                                                               | WorldPop                                         |
| Waktu                  | Jam (sin/cos), hari, libur nasional, Ramadan                                                     | Kalender                                         |
| Cuaca                  | u, v, suhu, RH, hujan 1 & 6 jam, tinggi lapisan batas                                            | Open-Meteo                                       |
| Latar regional         | PM2.5 CAMS di sel (interpolasi)                                                                  | Open-Meteo Air Quality                           |
| Lalu lintas (opsional) | Rasio kecepatan/free-flow ruas terdekat                                                          | TomTom                                           |
| Spasial-temporal       | IDW PM2.5 dari stasiun lain (tanpa stasiun target) dan lag 1–3 jam                               | Stasiun; dihitung leave-one-out agar tidak bocor |

## 11.3 Model

| **Model**             | **Deskripsi**                                        | **Peran**                                |
|-----------------------|------------------------------------------------------|------------------------------------------|
| B0 CAMS               | Nilai CAMS di lokasi stasiun                         | Baseline eksternal                       |
| B1 IDW                | Inverse distance weighting dari stasiun lain (p = 2) | Baseline utama yang harus dikalahkan     |
| B2 Kriging            | Ordinary kriging per jam, variogram eksponensial     | Baseline geostatistik (jika waktu cukup) |
| M1 LightGBM           | Gradient boosting seluruh fitur, objective L2        | Model utama P50                          |
| M1-Q                  | LightGBM quantile α = 0,1 / 0,5 / 0,9                | Interval ketidakpastian untuk UI         |
| M2 Regression kriging | Kriging pada residual M1                             | Could                                    |

## 11.4 Skema validasi

- **Leave-One-Station-Out (LOSO)**: tiap fold menahan satu stasiun beserta semua jamnya; fitur IDW dihitung ulang tanpa stasiun itu.

- **Spatial block CV** (blok 2 km) sebagai pemeriksaan tambahan autokorelasi spasial.

- **Temporal hold-out**: 20% periode terakhir dipisahkan.

- **Hold-out sumber** (validasi eksternal): stasiun yang hanya muncul di satu sumber (mis. WAQI saja), tidak dipakai melatih sama sekali. Tidak ada pengukuran mandiri dengan sensor.

- Metrik: RMSE, MAE, R², bias; untuk quantile: cakupan P10–P90 dan pinball loss.

- Analisis kesalahan per kelas jalan, per jam, dan per kategori ISPU, dengan fokus jam sibuk 06.00–09.00.

## 11.5 Training

- Jendela data: semua riwayat per jam yang tersedia di OpenAQ dan ISPU untuk stasiun area pilot, ditambah data live WAQI sejak H0, dengan fitur latar CAMS sejak Agustus 2022.

- Tuning Optuna 30–50 trial dengan skor LOSO (num_leaves, min_data_in_leaf, feature_fraction, lambda_l2).

- Monotonic constraint: PM2.5 tidak turun saat panjang jalan trunk naik, tidak naik saat NDVI naik, agar peta masuk akal di sel tanpa data.

- SHAP summary dan peta kontribusi fitur untuk slide presentasi.

- Model baru hanya dipromosikan jika RMSE LOSO tidak lebih buruk \> 5% dari model aktif.

## 11.6 Inferensi dan pemantauan

- Inferensi per jam: matriks ±13.600 × ±60 fitur, target \< 30 dtk di CPU.

- Post-processing: clip \[0, 500\], smoothing Gaussian ringan (σ = 1 sel), simpan COG.

- Drift: rolling RMSE 24 jam terhadap observasi baru; alarm jika \> 1,5× RMSE validasi → fallback IDW + CAMS dan tandai UI.

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Batasan yang dinyatakan jujur di proposal</strong></p>
<p>Model hanya seakurat jaringan stasiunnya. Area dengan sedikit stasiun punya ketidakpastian lebih tinggi, dan itu ditampilkan lewat interval P10–P90.</p>
<p>Grid 100 m belum menangkap variasi skala trotoar (beberapa meter dari knalpot). Faktor mikro-lingkungan per moda (Bab 12) menutup sebagian celah ini; nilainya diambil dari studi terbitan dan diuji sensitivitasnya.</p></td>
</tr>
</tbody>
</table>

# 12. Algoritma Routing dan Model Paparan

## 12.1 Strategi: generate-and-rerank

OpenTripPlanner tidak dirancang menerima bobot polusi kustom per edge secara stabil. Daripada memodifikasi mesinnya, Hirup memakai pendekatan dua tingkat: mesin routing menghasilkan kandidat yang beragam, lalu Hirup mengoptimalkan ulang leg aktif (jalan kaki, sepeda) dan memberi skor paparan pada setiap kandidat.

*Gambar 12.1 Alur algoritma perencanaan rute*

### Tahap 1: Generate

- **Transit**: panggil OTP GraphQL secara paralel dengan variasi walkReluctance ∈ {1,5; 3; 6} dan set moda {semua; rail-first; bus-only}, numItineraries = 5. Tambah kandidat dari halte/stasiun akses alternatif dalam radius 800 m (atau max_walk_m). Deduplikasi berdasarkan urutan (route_id, boarding, alighting); target 8–12 kandidat unik.

- **Sepeda**: router sepeda dengan λ ∈ {0; 1,5; 3}; edge motorway dilarang, trunk diberi penalti.

- **Motor & mobil**: OSRM dengan 2–3 alternatif rute; waktu tempuh dikalikan faktor kemacetan per jam (dari TomTom jika tersedia, atau tabel per jam yang dicantumkan sumbernya).

### Tahap 2: Optimasi leg jalan kaki dan sepeda

> w(e) = t(e) × (1 + λ × C_norm(e, jam))
>
> t(e) = panjang(e) / kecepatan (jalan kaki 1,2 m/s; sepeda 4,2 m/s)
>
> C_norm(e) = C(e) / C_ref ; C(e) = rata-rata P50 sel yang dilintasi edge
>
> C_ref = median kota pada jam tersebut ; λ ∈ {0; 0,5; 1,5; 3}

Varian dengan tambahan waktu \> 50% atau \> 8 menit dibanding leg asli dibuang. Opsional: bonus skor keteduhan (NDVI) untuk leg jalan kaki agar rute lewat koridor hijau.

### Tahap 3: Skor paparan

> Dosis_leg (µg) = C̄\_leg (µg/m³) × F_moda × VR_aktivitas (m³/jam) × durasi (jam)
>
> C̄\_leg = rata-rata P50 sepanjang polyline (sampel tiap 25 m, jam sesuai waktu leg;
>
> memakai prakiraan jika leg di masa depan)
>
> Leg TUNGGU: durasi = headway/2 (dari GTFS), F = F_halte atau F_stasiun
>
> Total dosis = Σ dosis semua leg ; rentang P10–P90 dihitung dengan cara yang sama

| **Mikro-lingkungan**                   | **F_moda (awal)**                       | **Aktivitas**    | **VR (m³/jam, awal)** |
|----------------------------------------|-----------------------------------------|------------------|-----------------------|
| Jalan kaki di trotoar                  | 1,0–1,3 (lebih tinggi di trunk/primary) | Jalan santai     | ±1,2                  |
| Bersepeda                              | 1,0–1,3 (lebih tinggi di trunk/primary) | Aktivitas sedang | ±2,0                  |
| Menunggu di halte pinggir/median jalan | 1,1–1,3                                 | Berdiri          | ±0,6                  |
| Menunggu di dalam stasiun MRT/LRT      | 0,5–0,8                                 | Berdiri          | ±0,6                  |
| Bus TransJakarta ber-AC                | 0,5–0,8                                 | Duduk/berdiri    | ±0,5                  |
| Kereta MRT/LRT                         | 0,4–0,7                                 | Duduk/berdiri    | ±0,5                  |
| Motor                                  | 1,1–1,5                                 | Mengendarai      | ±0,6                  |
| Mobil AC resirkulasi                   | 0,3–0,6                                 | Duduk            | ±0,5                  |

*Tabel 12.1 Parameter paparan awal. Semua nilai adalah placeholder yang **wajib diverifikasi manusia** terhadap literatur: US EPA Exposure Factors Handbook Bab 6 (laju ventilasi), review sistematis paparan per moda (2017), studi in-vehicle Delhi, dan studi komuter Asia lain. Asisten AI tidak boleh menjadi sumber angka atau sitasi tanpa verifikasi.*

## 12.4 Tahap 4: Seleksi Pareto dan pelabelan (dikoreksi)

- Hitung himpunan Pareto pada (durasi total, dosis total) dengan penalti transfer 5 menit-setara per transfer.

- **Tercepat** = durasi minimum.

- **Terbersih** = dosis minimum dengan durasi ≤ Tercepat + toleransi_profil.

- **Seimbang** = minimum J = α·T/T_min + (1−α)·D/D_min.

| **Parameter**                                | **Profil umum**             | **Profil rentan**      |
|----------------------------------------------|-----------------------------|------------------------|
| α (bobot waktu pada skor Seimbang)           | 0,5                         | 0,3                    |
| Toleransi waktu opsi Terbersih               | max(10 menit, 30%)          | max(15 menit, 40%)     |
| Ambang peringatan PM2.5 (P50 rata-rata rute) | Kategori ISPU "Tidak Sehat" | Kategori ISPU "Sedang" |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Koreksi dari v1.0</strong></p>
<p>v1.0 mengalikan dosis profil rentan dengan 1,5. Karena skor Seimbang memakai rasio D/D_min, pengali itu ikut membagi dirinya sendiri dan tidak mengubah urutan apa pun; ambang Terbersih juga tidak berubah. Profil rentan kini dibedakan lewat α, toleransi waktu, dan ambang peringatan, sehingga benar-benar menghasilkan rekomendasi yang berbeda.</p></td>
</tr>
</tbody>
</table>

## 12.5 Padanan rokok dan porsi dosis harian (dikoreksi)

Aturan praktis Berkeley Earth: paparan PM2.5 rata-rata 22 µg/m³ selama 24 jam ≈ 1 batang rokok per hari. Artinya **1 batang ≈ 528 µg·jam/m³** (integral konsentrasi-waktu).

> cig_eq = Σ_leg (C̄\_leg × F_moda × durasi_jam) / 528

**Konsekuensinya**, satu perjalanan menghasilkan angka kecil. Contoh: motor 50 menit, PM2.5 60 µg/m³, F = 1,3 → 60 × 1,3 × 0,83 / 528 ≈ **0,12 batang**. Contoh "2,3 batang untuk sekali naik motor" di v1.0 tidak konsisten dengan rumus ini dan **dihapus** dari demo, persona, dan contoh API.

Agar tetap konkret dan jujur, UI memakai tiga pembingkaian:

1.  **Selisih antar-opsi dalam persen** sebagai angka utama kartu rute: "Terbersih −25% dosis, +6 menit".

2.  **Porsi dosis harian**: porsi = dosis_perjalanan / dosis_harian_estimasi, dengan dosis harian = rata-rata PM2.5 hari itu × F_dalam_ruangan × VR harian (±16 m³/hari, verifikasi EPA). Contoh: "Perjalanan PP-mu 7% dari harimu, tapi ±11% dari dosis harianmu."

3.  **Padanan rokok per hari** di layar beranda dan ringkasan: "Udara hari ini setara ±2,3 batang" saat rata-rata PM2.5 harian 50 µg/m³. Ini angka yang benar menurut aturan Berkeley Earth dan tetap kuat sebagai hook.

UI wajib menyertakan catatan bahwa padanan rokok adalah alat komunikasi risiko, bukan ukuran medis.

## 12.6 Emisi dan kemacetan

- CO₂ dihindari = jarak × (faktor emisi kendaraan pribadi − faktor emisi per penumpang moda transit). Faktor emisi dari sumber resmi (pedoman inventarisasi KLHK atau DEFRA), ditampilkan sumbernya.

- Biaya: tarif transit resmi; motor/mobil dari konsumsi BBM per km × harga BBM (dicantumkan asumsinya).

## 12.7 Validasi dampak rute

1.  Tetapkan 50 pasangan OD yang mewakili pola komuter area pilot pada 3 slot jam (06.30, 07.30, 17.30).

2.  Laporkan median dan distribusi selisih dosis dan waktu: Terbersih vs Tercepat, dan motor vs opsi transit terbaik.

3.  Uji sensitivitas: hasil tetap dilaporkan saat F_moda diambil di batas bawah dan atas rentangnya. Ini menunjukkan kesimpulan tidak bergantung pada satu angka.

4.  **Validasi eksternal tanpa perangkat keras** (semua dari data terbuka): (a) **hold-out waktu**: 20% periode terakhir dipisahkan dan hanya dipakai menguji (Bab 11.4); (b) **hold-out sumber**: stasiun yang hanya ada di satu sumber (mis. WAQI saja) sama sekali tidak dipakai saat melatih; (c) **pembandingan dengan studi terbitan**: rasio dalam-kendaraan/ambien yang dipakai harus berada dalam rentang review sistematis 2017 dan studi in-vehicle Delhi, dan pola jam paparan dicek terhadap temuan Vital Strategies 2026 (perjalanan pagi paling berisiko).

# 13. Spesifikasi API

REST JSON dengan versi di path (/v1). Kontrak dihasilkan dari skema Pydantic (OpenAPI 3.1) dan menjadi **sumber kebenaran tunggal** untuk aplikasi mobile; mock server dari kontrak yang sama dipakai agar pengembangan aplikasi tidak menunggu backend. Waktu ISO 8601 zona Asia/Jakarta; koordinat WGS84; polyline memakai encoded polyline presisi 6.

| **Metode** | **Endpoint**                         | **Fungsi**                                      | **Prio** |
|------------|--------------------------------------|-------------------------------------------------|----------|
| POST       | /v1/routes/plan                      | Rencanakan rute 3 opsi + pembanding motor/mobil | M        |
| GET        | /v1/routes/departure-advice          | Dosis per slot 15 menit dalam jendela ±90 menit | S        |
| GET        | /v1/aq/point?lat&lon&ts              | PM2.5 P10/P50/P90 di titik                      | M        |
| GET        | /v1/aq/tiles/{z}/{x}/{y}.png?ts      | Tile lapisan peta                               | M        |
| GET        | /v1/aq/forecast?lat&lon&hours=24     | Prakiraan per jam                               | S        |
| GET        | /v1/aq/daily-summary?lat&lon&date    | Rata-rata harian + padanan rokok per hari       | S        |
| GET        | /v1/greenspaces/nearby?lat&lon&limit | Ruang hijau terdekat + PM2.5 + jam terbaik      | C        |
| GET        | /v1/insights/kelurahan?from&to       | Data tab Insight Kota                           | S        |
| GET        | /v1/health                           | Status layanan, versi model, umur data          | M        |

## 13.2 Contoh: POST /v1/routes/plan

> // Request
>
> { "origin": {"lat": -6.2891, "lon": 106.7745},
>
> "destination": {"lat": -6.2088, "lon": 106.8227},
>
> "depart_at": "2026-10-16T07:00:00+07:00",
>
> "mode": "transit", // transit \| bike \| walk \| all
>
> "profile": {"sensitivity": "vulnerable", "max_walk_m": 1000},
>
> "include_comparison": true }
>
> // Response (dipersingkat)
>
> { "request_id": "rq_9f2c...",
>
> "data_freshness": {"aq_valid_hour": "2026-10-16T07:00+07:00",
>
> "model_version": "lgbm-2026w42", "confidence": "medium"},
>
> "options": \[
>
> { "option_id": "op_1", "labels": \["fastest"\], "duration_s": 2280, "transfers": 1,
>
> "dose_ug": 21.8, "dose_ug_p10": 16.0, "dose_ug_p90": 29.5,
>
> "ct_ugh_m3": 25.6, "cig_eq": 0.05, "delta_vs_fastest_pct": 0,
>
> "legs": \[
>
> {"mode": "WALK", "duration_s": 420, "mean_pm25": 61, "dose_ug": 9.8,
>
> "polyline": "...", "segments_pm25": \[58, 63, 61\]},
>
> {"mode": "WAIT", "place": "MRT Lebak Bulus", "duration_s": 150, "dose_ug": 0.9},
>
> {"mode": "SUBWAY", "route": "MRT Utara-Selatan", "from": "Lebak Bulus",
>
> "to": "Dukuh Atas", "duration_s": 1500, "dose_ug": 5.7},
>
> {"mode": "WALK", "duration_s": 240, "mean_pm25": 58, "dose_ug": 5.3} \] },
>
> { "option_id": "op_2", "labels": \["cleanest"\], "...": "..." },
>
> { "option_id": "op_3", "labels": \["balanced"\], "...": "..." } \],
>
> "comparison": {
>
> "motorcycle": {"duration_s": 3000, "dose_ug": 39.0, "cig_eq": 0.12, "co2_kg": 1.2},
>
> "car": {"duration_s": 3300, "dose_ug": 12.4, "cig_eq": 0.05, "co2_kg": 3.1} },
>
> "disclaimer": "Estimasi model, bukan pengukuran medis." }

*Angka contoh dihitung dengan parameter awal Tabel 12.1 dan konsisten dengan rumus Bab 12 (misalnya total CT 25,6 µg·jam/m³ ÷ 528 = 0,05 batang). Bukan hasil model.*

## 13.3 Konvensi

- Error mengikuti RFC 9457 (Problem Details): type, title, status, detail, request_id.

- Kode umum: 400 validasi, 404 di luar area layanan (type: out_of_service_area), 429 rate limit, 503 data/model tidak tersedia (respons tetap berisi fallback bila mungkin).

- Header X-Data-Age-Seconds pada endpoint AQ agar aplikasi bisa menampilkan peringatan data basi.

- Field data_quality (real \| approximated \| synthetic) pada setiap respons; lihat Bab 10.4.

# 14. Spesifikasi UI/UX Mobile

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>UI/UX adalah prioritas utama</strong></p>
<p>Kesan pertama pengguna datang dari tampilan dan alur, jadi kualitas UI diperlakukan setara dengan kebenaran teknis.</p>
<p><strong>Aturan:</strong> fitur Should hanya masuk APK jika lulus checklist UI (Bab 14.7). Fitur yang berfungsi tapi terlihat setengah jadi lebih merugikan daripada tidak ada.</p></td>
</tr>
</tbody>
</table>

## 14.1 Kenapa aplikasi mobile

Perencanaan perjalanan adalah kegiatan "di jalan": pengguna butuh GPS, peta di genggaman, dan kartu yang bisa dilihat sambil berangkat. Mobile juga memungkinkan aplikasi dicoba langsung sebagai APK, bukan sekadar tautan web. Dashboard pemda v1.0 dilebur menjadi tab **Insight Kota** agar seluruh produk tetap satu aplikasi.

## 14.2 Prinsip desain

- **Perbandingan, bukan angka mentah**: dosis selalu dibandingkan (dengan opsi lain, dengan motor, dengan kemarin).

- **Satu angka utama per kartu**: selisih % dosis sebagai headline; µg, CT, dan padanan rokok sebagai detail.

- **Jujur soal ketidakpastian**: tingkat keyakinan (tinggi/sedang/rendah) dan rentang P10–P90 selalu tersedia.

- **Memberdayakan, bukan menakut-nakuti**: "kamu menghindari 25%", bukan alarmis. Profil rentan memakai nada lebih protektif.

- **Warna + bentuk + teks**: kategori ISPU juga dibedakan dengan ikon dan label (ramah buta warna).

- **Ramah satu tangan**: tombol utama di sepertiga bawah layar; peta bisa disembunyikan saat bergerak.

## 14.3 Daftar layar

| **Layar**              | **Isi utama**                                                                                               | **FR**              |
|------------------------|-------------------------------------------------------------------------------------------------------------|---------------------|
| Onboarding (3 langkah) | Konsep dosis, pilih profil umum/rentan, izin lokasi                                                         | FR-20, FR-21        |
| Beranda / Peta         | Lapisan PM2.5, kartu "udara hari ini setara ±X batang", kolom "Mau ke mana?", favorit, ruang hijau terdekat | FR-10, FR-11, FR-16 |
| Pilih mode             | Segmented control: Transit · Sepeda · Jalan kaki · Semua                                                    | FR-06               |
| Hasil rute             | 3 kartu opsi (durasi, transfer, selisih % dosis) + kartu pembanding motor/mobil                             | FR-02, FR-05        |
| Detail rute            | Polyline berwarna, timeline leg, dosis per leg, tips ("tunggu di dalam stasiun")                            | FR-03, FR-04        |
| Saran jam berangkat    | Grafik batang dosis per slot 15 menit                                                                       | FR-13               |
| Perjalanan aktif       | Langkah demi langkah ringkas, sorot segmen merah, tombol "Selesai" untuk menyimpan                          | FR-14               |
| Riwayat & ringkasan    | Dosis harian/mingguan, porsi dosis harian, dosis dihindari, kartu berbagi                                   | FR-15               |
| Insight Kota           | Koroplet kelurahan, peringkat ketimpangan ruang hijau, metodologi                                           | FR-30, FR-31        |
| Profil & privasi       | Sensitivitas, preferensi, hapus semua data lokal                                                            | FR-07, FR-21        |

## 14.4 Arah visual dan design system

| **Elemen**       | **Keputusan**                                                                                                                                                   |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Karakter         | "Napas lega": tenang, bersih, optimis. Bukan aplikasi bencana; merah hanya untuk segmen yang benar-benar buruk.                                                 |
| Warna            | Primer hijau-teal (udara bersih), netral hangat untuk latar; skala ISPU resmi khusus untuk data polusi agar tidak bentrok dengan warna merek.                   |
| Tipografi        | Plus Jakarta Sans (gratis, Google Fonts, sekaligus sentuhan lokal). Angka dosis memakai tabular figures agar tidak "goyang" saat beranimasi.                    |
| Grid & spasi     | Grid 8 pt, radius 16 untuk kartu, 24 untuk bottom sheet. Target sentuh ≥ 48 dp.                                                                                 |
| Komponen inti    | Kartu opsi rute, chip moda, timeline leg, batang dosis, legenda ISPU, lencana data_quality, bottom sheet peta, kartu berbagi.                                   |
| Ikon & ilustrasi | Satu set ikon (Phosphor/Lucide) + 3–4 ilustrasi sederhana untuk onboarding dan state kosong.                                                                    |
| Token ke kode    | Warna, tipografi, spasi, dan radius diekspor dari Figma menjadi ThemeData + ThemeExtension Flutter di H0–H1, sehingga desain dan kode memakai sumber yang sama. |

## 14.5 State dan mikro-interaksi

- **Loading bercerita**: skeleton kartu + teks bergantian ("Membaca udara di 1.240 segmen jalan…", "Membandingkan 9 kandidat rute…"), bukan spinner kosong.

- **State lengkap di setiap layar**: kosong (ilustrasi + aksi), error (penjelasan + coba lagi), offline (data terakhir + umur data), di luar area pilot (peta area + ajakan).

- **Transisi**: kartu hasil masuk bertahap (stagger 60 ms); peta ke detail rute memakai shared-element transition; bottom sheet bisa ditarik.

- **Umpan balik**: haptic ringan saat memilih opsi; snackbar konfirmasi saat perjalanan disimpan.

## 14.6 Momen khas

1.  **Balapan dosis**: di layar Hasil, batang dosis tiap opsi + motor tumbuh bersamaan dari nol; motor jelas tertinggal paling panjang. Satu animasi ini menjelaskan seluruh nilai produk dalam 2 detik.

2.  **Polyline bernapas**: warna segmen rute beranimasi mengikuti konsentrasi; segmen merah berdenyut halus.

3.  **Kartu "udara hari ini"** di Beranda dengan padanan rokok per hari dan grafik 24 jam mini.

4.  **Kartu berbagi** mingguan yang rapi untuk Instagram Story ("Minggu ini aku menghindari 31% polusi di perjalanan").

## 14.7 Checklist UI (Definition of Done tiap layar)

| **Aspek**         | **Kriteria lulus**                                                                            |
|-------------------|-----------------------------------------------------------------------------------------------|
| Kesesuaian desain | Sesuai Figma: spasi, warna, tipografi memakai token; tidak ada nilai hard-coded               |
| State             | Loading, kosong, error, offline sudah ada dan dicek                                           |
| Perangkat         | Rapi di layar 5,5" dan 6,7"; lancar (± 60 fps) di HP RAM 3 GB                                 |
| Aksesibilitas     | Kontras WCAG AA; ukuran huruf sistem 130% tidak merusak tata letak; label untuk pembaca layar |
| Bahasa            | Bahasa Indonesia sehari-hari, tanpa jargon; angka memakai format Indonesia (koma desimal)     |
| Kejujuran         | Label estimasi dan lencana data_quality tampil bila relevan                                   |

## 14.8 Proses desain dan mode demo

- **H0**: moodboard, design system, wireframe 10 layar. **H1 18.00: design freeze** hi-fi + prototipe Figma. Setelah freeze, perubahan hanya dari temuan uji usability.

- **Design QA harian** pada sesi integrasi 21.00: tim desain membandingkan APK dengan Figma dan mencatat selisih sebagai issue berlabel ui.

- **Uji usability (Should)**: 5 responden di luar tim, H2 malam; 5 tugas inti (cari rute, bandingkan dengan motor, pilih jam berangkat, simpan, buka Insight Kota) lalu SUS. Temuan kritis diperbaiki H3 pagi sebelum freeze.

- **Mode demo**: menu tersembunyi (tekan lama logo) memuat 5 skenario fixture (mis. Lebak Bulus → Sudirman jam 07.00) yang berjalan offline, selalu berlabel "Mode demo". Dipakai bila koneksi atau server bermasalah saat demo.

# 15. Keamanan dan Privasi

Data lokasi termasuk data pribadi menurut UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi; profil rentan diperlakukan sebagai data sensitif.

| **Prinsip**                      | **Implementasi**                                                                                                                                                                                                         |
|----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Minimisasi data                  | Tanpa akun. Tanpa pelacakan GPS latar belakang. Riwayat perjalanan dan profil hanya di perangkat. Server tidak menyimpan asal–tujuan setelah respons dikirim (log hanya sel grid kasar untuk debugging, retensi 7 hari). |
| Persetujuan eksplisit            | Izin lokasi diminta saat dibutuhkan, dengan penjelasan singkat kegunaannya.                                                                                                                                              |
| Agregasi aman                    | Insight Kota hanya dari raster model, bukan data pengguna. Jika kelak memakai agregat pengguna, wajib k-anonimitas ≥ 10.                                                                                                 |
| Profil kesehatan                 | Disimpan sebagai kategori (umum/rentan), bukan diagnosis; tidak dikirim ke server kecuali sebagai parameter permintaan.                                                                                                  |
| Hak pengguna                     | Tombol "hapus semua data" di aplikasi.                                                                                                                                                                                   |
| Keamanan teknis                  | HTTPS (TLS 1.2+); rate limit per IP; secret di environment; API key pihak ketiga tidak pernah dikirim ke aplikasi; dependensi dipindai di CI.                                                                            |
| Keamanan kerja dengan asisten AI | Secret produksi tidak pernah ditempel ke prompt asisten AI; file .env diabaikan git; review anggota lain wajib sebelum merge ke main.                                                                                    |

<table>
<colgroup>
<col style="width: 100%" />
</colgroup>
<tbody>
<tr class="odd">
<td><p><strong>Batas klaim kesehatan</strong></p>
<p>Hirup tidak memberi diagnosis atau saran pengobatan. Semua dosis dan padanan rokok diberi label estimasi. Profil rentan hanya mengubah pemeringkatan rute dan ambang peringatan.</p></td>
</tr>
</tbody>
</table>

# 16. Strategi Pengujian

| **Level**  | **Cakupan**                                                                                         | **Alat**                  | **Kriteria lulus**                                                               | **Prio** |
|------------|-----------------------------------------------------------------------------------------------------|---------------------------|----------------------------------------------------------------------------------|----------|
| Unit       | Exposure Engine, cig_eq, porsi harian, Pareto, label per profil, QC data                            | pytest, flutter_test      | Kasus batas lulus (dosis 0, rute tanpa jalan kaki, profil rentan mengubah hasil) | M        |
| Data       | Skema, rentang nilai, kelengkapan per jam                                                           | pandera                   | Pipeline berhenti + log jika gagal                                               | M        |
| Model      | LOSO, cakupan kuantil, sanity check peta                                                            | Notebook evaluasi standar | Target Tabel 4.1; tidak ada artefak grid                                         | M        |
| Integrasi  | API ↔ OTP ↔ OSRM ↔ router sepeda                                                                    | pytest + docker compose   | golden_od.json (10 OD) selalu ≥ 1 opsi; 50 OD untuk laporan dampak               | M        |
| Kontrak    | Respons API sesuai OpenAPI                                                                          | schemathesis              | Tanpa pelanggaran skema                                                          | S        |
| E2E mobile | Cari → pilih → simpan → ringkasan                                                                   | Flutter integration_test  | Lulus di 2 perangkat Android                                                     | M        |
| Beban      | plan & aq/point                                                                                     | Locust                    | Target NFR performa                                                              | C        |
| Design QA  | Setiap layar vs Figma + checklist UI                                                                | Figma + 2 HP Android      | 100% layar Must lulus Bab 14.7                                                   | M        |
| Usability  | Tugas inti oleh pengguna                                                                            | Uji moderasi + SUS        | 5 responden; SUS ≥ 75; keberhasilan tugas ≥ 90%                                  | S        |
| Eksternal  | Prediksi vs data yang tidak dipakai melatih (hold-out waktu & sumber); rasio moda vs studi terbitan | Notebook evaluasi         | RMSE hold-out ≤ 1,2× LOSO; rasio dalam rentang literatur                         | S        |

# Lampiran A. Struktur Repositori

```
hirup/
├── apps/mobile/       # Flutter
├── contracts/         # kontrak beku H0 (openapi, schemas, params, golden_od)
├── services/
│ ├── api/             # FastAPI
│ ├── routing/         # OTP, OSRM, router kaki/sepeda
│ └── exposure/        # Exposure Engine
├── ml/                # notebooks, src/, configs/
├── pipelines/         # ingest, QC, kalibrasi, fitur
├── data_prep/         # gtfs_manual/ MRT & LRT
├── fixtures/          # data dummy + skenario demo
├── infra/             # docker-compose, otp/, osrm/
├── docs/, design/     # ADR, ekspor Figma
└── data/              # gitignored
```

- Python: ruff + mypy; Dart: flutter_lints. Commit mengikuti Conventional Commits (feat:, fix:, data:, ml:).

- Semua konstanta ilmiah (F, VR, 528 µg·jam/m³, faktor emisi) di file konfigurasi dengan kolom source dan verified_by.

- Dataset turunan diberi versi tanggal (mis. features_static_v2026-10-14.parquet).

# Lampiran B. Definition of Done

- Merge ke main lewat PR dengan CI hijau dan 1 review manusia.

- Uji unit untuk logika baru; golden_od.json tetap lulus.

- Endpoint baru tercermin di openapi.yaml dan dicoba dari aplikasi.

- Pekerjaan ML: notebook evaluasi diperbarui, metrik tercatat di model_registry.json.

- Pekerjaan data: validasi skema lulus; sumber & lisensi tercatat di docs/data_sources.md.

- Konstanta ilmiah baru punya sumber yang sudah diverifikasi manusia.

- Layar UI lulus checklist Bab 14.7 dan design QA. Tidak ada secret di repo.

- Data dummy selalu berlabel data_quality: synthetic dan tidak masuk metrik atau deck.

# Lampiran C. Glosarium

| **Istilah**      | **Arti**                                                                                           |
|------------------|----------------------------------------------------------------------------------------------------|
| PM2.5            | Partikel udara berdiameter ≤ 2,5 µm; polutan utama perkotaan yang dapat masuk ke paru-paru dalam   |
| ISPU             | Indeks Standar Pencemar Udara (Permen LHK 14/2020)                                                 |
| SPKU             | Stasiun Pemantau Kualitas Udara                                                                    |
| Dosis inhalasi   | Massa polutan yang dihirup = konsentrasi × laju ventilasi × durasi (µg)                            |
| CT               | Integral konsentrasi-waktu (µg·jam/m³); dasar padanan rokok                                        |
| Mikro-lingkungan | Lingkungan spesifik (trotoar, dalam bus, dalam stasiun) dengan konsentrasi berbeda dari udara luar |
| GTFS             | General Transit Feed Specification; format standar data jadwal transportasi umum                   |
| OTP / OSRM       | OpenTripPlanner (routing transit) / Open Source Routing Machine (routing jalan)                    |
| LUR              | Land Use Regression; model polusi dari karakteristik lingkungan sekitar                            |
| LOSO             | Leave-One-Station-Out; validasi silang dengan menahan satu stasiun per fold                        |
| Pareto           | Himpunan solusi yang tidak bisa diperbaiki di satu tujuan tanpa memburuk di tujuan lain            |
| COG              | Cloud-Optimized GeoTIFF; raster yang bisa dibaca sebagian                                          |
| Headway          | Selang waktu antar-kedatangan kendaraan pada satu rute                                             |

# Lampiran D. Referensi

- Berita Jakarta (17 Okt 2025). Jakarta Owns the Most Extensive Integrated Air Quality Monitoring System in Indonesia (111 SPKU). beritajakarta.id/en/read/60571

- Vital Strategies (2026). Risalah Kebijakan: Mengungkap Risiko Tersembunyi Paparan PM2.5 pada Anak Usia Sekolah di Jakarta. vitalstrategies.org

- Mobility Database. Transjakarta GTFS Schedule feed mdb-1909. mobilitydatabase.org/feeds/gtfs/mdb-1909

- OpenAQ. API rate limits (General use: gratis, 60 req/menit, 2.000 req/jam). docs.openaq.org

- WAQI / aqicn. Air Quality Open Data Platform API (gratis, token; data tidak boleh diredistribusi). aqicn.org/api

- Open-Meteo. Historical Weather API dan Air Quality API (CAMS). open-meteo.com

- TomTom. Pricing (Traffic Flow segment data: 20.000 request/bulan gratis). docs.tomtom.com/pricing

- OpenAQ use case: Sh\*\*t! I Smoke (aturan Berkeley Earth 22 µg/m³ ≈ 1 batang/hari). openaq.org/use-cases/shootismoke

- University of Helsinki, Digital Geography Lab. Green Paths route planner. helsinki.fi/en/researchgroups/digital-geography-lab/green-paths

- Imperial College London (2025). Purify: new route planning app to avoid air pollution. imperial.ac.uk/news/262673

- Healthy Route Planner for sensitive groups (2026). Journal of Transport & Health. trid.trb.org/View/2752446

- Insight SFI / DCU (2023). Clean air travel app, Dublin. techcentral.ie

- Bistaffa & Calo Oliveira (2025). Recommending Green Routes for Pedestrians in Barcelona. AAMAS 2025 Demo Track.

- University of Utah RAI (2025). Students use AI to solve air quality challenges (Fresh Route). rai.utah.edu

- Liu et al. Navigating pollution: A multimodal approach to traffic and exposure management. arXiv:2502.01324

- OpenTripPlanner 2 documentation, Data Overlay sandbox. opentripplanner.readthedocs.io

- Pant et al. In-vehicle PM2.5 and black carbon exposure by mode in Delhi (dirangkum TheCityFix). thecityfix.com

- Levels of ambient air pollution according to mode of transport: a systematic review (2017). PLoS ONE.

- Personal exposure to fine particulate air pollution while commuting: six transport modes. PMC5679559

- US EPA. Exposure Factors Handbook, Chapter 6: Inhalation Rates.

- Elmbridge Borough Council (2026). Clean Air Routes now available in Surrey. elmbridge.gov.uk

- UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi.
