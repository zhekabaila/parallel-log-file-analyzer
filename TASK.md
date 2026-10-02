# TASK.md — UTS Komputasi Paralel dan Terdistribusi
## Proyek: Parallel Log File Analyzer

> Dokumen ini adalah instruksi lengkap untuk AI agent. Kerjakan SEMUA bagian secara berurutan.
> Jangan melewatkan langkah, jangan memalsukan hasil benchmark, dan jangan menambah dependensi di luar yang disebut.

---

## 0. Konteks & Identitas

| Item | Nilai |
|---|---|
| Mata kuliah | Komputasi Paralel dan Terdistribusi (3 SKS) |
| Institusi | Informatika, Fakultas Teknik, Universitas Siliwangi |
| Dosen | Rohmat Gunawan, M.T. |
| Nama | **Zheka Baila Arkan** |
| NPM | **247006111152** |
| Tema | Parallel Computing in Our Lives — **Parallel Log File Analyzer** |
| Jenis tugas | Mini project individu, project-based |

**Setiap output program WAJIB menampilkan baris identitas:**

```
PARALLEL LOG FILE ANALYZER
By ZHEKA BAILA ARKAN (247006111152)
```

Simpan identitas sebagai konstanta tunggal di `config.py`, jangan di-hardcode berulang.

---

## 1. Tujuan

Membangun analyzer file log server berukuran besar (hingga jutaan baris) yang menghitung:

- jumlah error, warning, info, debug (per level)
- distribusi status code HTTP
- top-N IP address, top-N user, top-N path/endpoint
- distribusi HTTP method
- aktivitas pengguna per jam
- statistik response time (rata-rata, maksimum, p95) dan total bytes
- jumlah baris malformed (tidak sesuai format)

Solusi diimplementasikan dengan **3 pendekatan** dan dibandingkan:

1. **Sequential**
2. **Multithread** (`threading` / `ThreadPoolExecutor`)
3. **Multiprocessing** (`multiprocessing` / `ProcessPoolExecutor`)

Hasil ketiganya **harus identik** (divalidasi otomatis), hanya waktunya yang berbeda.

---

## 2. Keputusan Teknis (sudah ditetapkan, jangan diubah)

- **Bahasa:** Python 3.10+.
  Alasan: GIL membuat perbandingan thread vs process bermakna secara akademis (thread tidak mempercepat pekerjaan CPU-bound, process bisa).
- **Dependensi:** library standar Python saja untuk logika inti. Tambahan hanya `pytest` (testing), `matplotlib` (grafik), dan opsional `pytest-cov`. Tulis di `requirements.txt`.
- **Bahasa penulisan:** nama fungsi/variabel/class dalam bahasa Inggris. Docstring, komentar, output konsol, dan semua dokumen dalam **bahasa Indonesia**.
- **Cross-platform:** wajib jalan di Windows (spawn) dan Linux/macOS. Semua entry point multiprocessing dilindungi `if __name__ == "__main__":`. Gunakan `pathlib`.
- **Memory-friendly:** file log TIDAK boleh dibaca utuh ke memori. Baca streaming per baris atau per byte-range.
- **Reproducible:** semua keacakan memakai `random.Random(seed)`, default seed `42`.

---

## 3. Struktur Proyek

Buat struktur persis seperti ini:

```
uts-parallel-log-analyzer/
├── TASK.md
├── README.md                 # cara install, menjalankan, ringkas
├── DOKUMENTASI.md            # dokumentasi lengkap (lihat Bagian 9)
├── requirements.txt
├── pytest.ini
├── .gitignore                # abaikan data/*.log, results/*.png tidak perlu diabaikan
├── src/
│   └── log_analyzer/
│       ├── __init__.py
│       ├── config.py         # identitas, konstanta, format log
│       ├── generator.py      # generator log dummy
│       ├── parser.py         # parse satu baris log -> record
│       ├── stats.py          # class LogStats + merge()
│       ├── chunking.py       # pembagian file ke byte-range
│       ├── sequential.py     # pendekatan 1
│       ├── threaded.py       # pendekatan 2
│       ├── multiproc.py      # pendekatan 3
│       ├── reporter.py       # format output konsol (identitas, waktu, dll)
│       └── cli.py            # entry point argparse
├── bug_demo/                 # TAHAP "CODE WITH BUG"
│   ├── buggy_race_condition.py
│   ├── buggy_sync_overhead.py
│   └── buggy_comm_overhead.py
├── benchmarks/
│   ├── run_benchmark.py      # menjalankan semua konfigurasi
│   └── plot_results.py       # membuat grafik dari CSV
├── tests/
│   ├── conftest.py
│   ├── test_generator.py
│   ├── test_parser.py
│   ├── test_stats.py
│   ├── test_chunking.py
│   ├── test_equivalence.py
│   └── test_cli.py
├── data/                     # file log hasil generate (di-.gitignore)
├── results/                  # CSV, JSON, grafik PNG hasil benchmark
└── laporan/
    ├── LAPORAN.md            # isi laporan sesuai template UTS (Bagian 8)
    └── gambar/               # diagram arsitektur, dll
```

Jalankan kode dari root dengan `python -m log_analyzer.cli ...` (tambahkan `src` ke `PYTHONPATH` atau sediakan `pyproject.toml` minimal agar `pip install -e .` bisa dipakai).

---

## 4. Spesifikasi Format Log

Satu baris = satu event, contoh:

```
2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042 "GET /api/orders/123" 500 1234 87ms
```

Regex acuan (tulis sekali di `config.py`, compile sekali, jangan compile di dalam loop):

```
^(?P<ts>\S+) \[(?P<level>[A-Z]+)\] (?P<ip>\d{1,3}(?:\.\d{1,3}){3}) (?P<user>\S+) "(?P<method>[A-Z]+) (?P<path>\S+)" (?P<status>\d{3}) (?P<bytes>\d+) (?P<rt>\d+)ms$
```

Aturan nilai yang di-generate:

| Field | Aturan |
|---|---|
| timestamp | naik monotonik dari tanggal dasar, selisih acak kecil antar baris |
| level | bobot kira-kira: INFO 70%, DEBUG 10%, WARNING 12%, ERROR 8% |
| status | konsisten dengan level: ERROR → 5xx (dominan), WARNING → 4xx, INFO/DEBUG → 2xx/3xx |
| ip | dari pool 500 IP acak (agar top-N bermakna), distribusi miring (sebagian IP sangat aktif) |
| user | pool `user_000`–`user_199`, distribusi miring |
| method | GET 60%, POST 25%, PUT 8%, DELETE 5%, PATCH 2% |
| path | pool ~30 endpoint (`/api/orders/{id}`, `/login`, `/static/app.js`, dst.) |
| bytes | 100–50.000 |
| response time | 5–2000 ms, ekor panjang (mayoritas kecil) |
| malformed | **0,5%** baris sengaja rusak (kosong, field hilang, status huruf, dll) |

---

## 5. Spesifikasi Komponen

### 5.1 `generator.py`
- Fungsi utama: `generate_log_file(path, num_lines, seed=42, malformed_ratio=0.005) -> Path`.
- Menulis tepat `num_lines` baris (termasuk baris malformed) ke file baru, misal `1_000_000` baris.
- Tulis dalam batch (mis. 10.000 baris per `write`) agar cepat dan hemat memori.
- Pool IP/user/path dibuat sekali di awal.
- Buat folder induk otomatis. Tampilkan progres sederhana dan waktu generate.
- Seed sama + jumlah baris sama → isi file **byte-identical**.
- CLI: `python -m log_analyzer.cli generate --lines 1000000 --output data/server_1m.log --seed 42`.

### 5.2 `parser.py`
- `parse_line(line: str) -> dict | None` (atau dataclass/NamedTuple). Kembalikan `None` untuk baris malformed, **tidak boleh melempar exception**.
- Validasi dasar: level dikenal, status 100–599, angka tidak negatif.

### 5.3 `stats.py`
- Class `LogStats` berisi: `total_lines`, `malformed_lines`, `level_counts`, `status_counts`, `method_counts`, `ip_counts`, `user_counts`, `path_counts`, `hourly_counts`, `total_bytes`, `total_response_ms`, `max_response_ms`, serta cara menghitung p95 (mis. histogram bucket response time agar bisa di-merge secara tepat — **jangan** menyimpan list jutaan nilai).
- `add_record(record)` dan `add_malformed()`.
- `merge(other) -> LogStats` / `merge_all(list)`: harus **asosiatif dan komutatif**, dengan elemen identitas = `LogStats()` kosong.
- `top_n(counter, n)` dengan tie-break deterministik (urut hitungan menurun, lalu key menaik).
- `to_dict()` untuk perbandingan dan serialisasi, serta `__eq__` untuk validasi ekuivalensi.
- Objek harus **picklable** dan kecil (hanya agregat) karena dikirim antar process.

### 5.4 `chunking.py`
- `compute_chunks(file_size, num_chunks) -> list[tuple[int, int]]` membagi file menjadi byte-range `[start, end)`.
- `iter_lines_in_range(path, start, end)` membuka file **mode biner**, dengan aturan baku:
  - Sebuah baris dimiliki chunk tempat **byte pertama baris** berada di `[start, end)`.
  - Jika `start > 0`: `seek(start - 1)` lalu `readline()` dan buang hasilnya (menyelaraskan ke awal baris pertama milik chunk ini).
  - Loop: `pos = tell()`; jika `pos >= end` berhenti; `readline()`; jika kosong berhenti; decode `utf-8` dengan `errors="replace"`.
- Jaminan: gabungan semua chunk = seluruh baris file, **tanpa duplikat dan tanpa baris hilang**, untuk jumlah chunk berapa pun, file kosong, file satu baris, file tanpa newline di akhir, dan chunk lebih banyak dari baris.

### 5.5 `sequential.py`
- `analyze_sequential(path) -> LogStats` — satu loop, baseline pengukuran.

### 5.6 `threaded.py`
- `analyze_threaded(path, num_threads) -> LogStats`.
- Setiap thread memproses satu byte-range dan membangun `LogStats` **lokal** miliknya sendiri, lalu hasilnya di-merge di thread utama (pola map-reduce tanpa lock saat memproses).

### 5.7 `multiproc.py`
- `analyze_multiprocess(path, num_processes) -> LogStats`.
- Gunakan `ProcessPoolExecutor` (atau `multiprocessing.Pool`). Worker menerima `(path, start, end)` — **bukan** isi baris. Worker mengembalikan `LogStats` lokal. Merge di proses utama.
- Worker harus berupa fungsi top-level (agar bisa di-pickle di Windows).

### 5.8 `reporter.py` + `cli.py`
- Subcommand: `generate`, `analyze` (`--mode sequential|threads|processes`, `--workers N`, `--input PATH`), `compare` (jalankan ketiga mode lalu tampilkan speedup).
- Output konsol WAJIB berisi: banner + identitas (Bagian 0), mode, jumlah thread/process, jumlah baris, waktu total (detik, 2–3 desimal), throughput (baris/detik), speedup dan efisiensi (jika ada baseline), lalu ringkasan statistik (level, top-5 status, top-5 IP, top-5 user, top-5 path, response time).
- Contoh bentuk output:

```
======================================================
PARALLEL LOG FILE ANALYZER
By ZHEKA BAILA ARKAN (247006111152)
======================================================
Mode        : multiprocessing
Jumlah proses : 4
File        : data/server_1m.log (1.000.000 baris)
[MULAI] membagi file menjadi 4 chunk
[SELESAI] worker-1 ... worker-4
------------------------------------------------------
Waktu total : 2.481 detik
Throughput  : 403.063 baris/detik
Speedup     : 2.87x   Efisiensi: 71.8%
======================================================
```

Rumus: `speedup = T_sequential / T_parallel`, `efisiensi = speedup / jumlah_worker`.

---

## 6. Tahap "Code with Bug" (WAJIB, bernilai di UTS)

Soal mewajibkan **minimal satu bug komputasi paralel** pada kode tahap awal. Buat di `bug_demo/` dan **dokumentasikan bukti nyata**, bukan sekadar klaim.

### Bug 1 — Race Condition (`buggy_race_condition.py`)
- Beberapa thread memperbarui **satu objek statistik global bersama tanpa lock** (`total_lines += 1`, `counts[key] = counts.get(key, 0) + 1`).
- Agar race muncul andal: pecah operasi menjadi read → ubah → write dengan variabel sementara, dan panggil `sys.setswitchinterval(1e-6)` di awal skrip demo.
- Jalankan minimal 10 kali. Bandingkan dengan hasil sequential. Catat berapa kali hasil salah dan seberapa besar selisih jumlah baris/error yang hilang.
- Bukti ini masuk laporan.

### Bug 2 — Synchronization Overhead (`buggy_sync_overhead.py`)
- Perbaiki bug 1 dengan cara naif: satu `threading.Lock()` global yang dipegang **per baris**.
- Hasil benar, tetapi ukur: waktunya lebih lambat daripada sequential. Catat angkanya.

### Bug 3 — Communication Overhead (`buggy_comm_overhead.py`)
- Versi multiprocessing naif: proses utama membaca semua baris lalu mengirim baris ke worker lewat `Queue` atau memecah list berisi jutaan string (pickle besar).
- Ukur waktu dan bandingkan dengan versi final (worker membaca byte-range sendiri).

### Perbaikan (Final Code)
- Bug 1 & 2 → statistik **lokal per thread**, merge sekali di akhir (tanpa lock di hot path).
- Bug 3 → kirim hanya `(path, start, end)`, kembalikan hanya agregat kecil.
- Catatan jujur untuk analisis: karena GIL, **multithread diperkirakan tidak lebih cepat dari sequential** pada pekerjaan CPU-bound (regex parsing). Laporkan apa adanya apa pun hasil pengukuran; jelaskan penyebabnya.

---

## 7. Benchmark & Hasil Percobaan

### 7.1 `benchmarks/run_benchmark.py`
- Generate dataset sekali per ukuran, **di luar** pengukuran waktu.
- Variasi (minimal 3 konfigurasi untuk tiap variabel):
  - **Jumlah data:** 100.000 / 500.000 / 1.000.000 baris (tambahan 2.000.000 jika mesin kuat).
  - **Jumlah thread:** 1, 2, 4, 8.
  - **Jumlah process:** 1, 2, 4, 8 (sertakan nilai ≥ jumlah core fisik agar terlihat penurunan efisiensi).
- Setiap konfigurasi: 1× warm-up (dibuang) lalu **3 kali ulang**, ambil **median**.
- Gunakan `time.perf_counter()`.
- Setiap hasil paralel di-assert sama dengan hasil sequential; jika beda, benchmark berhenti dengan error jelas.
- Catat spesifikasi mesin (OS, CPU, jumlah core logis/fisik, versi Python, RAM jika tersedia) ke `results/machine_info.json`.
- Simpan semua hasil ke `results/benchmark_results.csv` (kolom: mode, workers, num_lines, run, seconds, median_seconds, speedup, efficiency, throughput) dan `results/benchmark_results.json`.
- Cetak tabel markdown siap tempel ke laporan.

### 7.2 `benchmarks/plot_results.py` (matplotlib, backend `Agg`)
Buat grafik PNG (judul, label sumbu, legenda, grid, resolusi ≥ 150 dpi) di `results/charts/`:

1. **Waktu vs Jumlah Thread** (satu garis per ukuran data, plus garis baseline sequential)
2. **Waktu vs Jumlah Process** (idem)
3. **Speedup vs Konfigurasi** (thread dan process dalam satu grafik, plus garis speedup ideal)
4. Tambahan opsional: bar chart perbandingan bug demo vs final.

---

## 8. Unit Testing (WAJIB)

Gunakan `pytest`. Semua test harus lulus dengan `pytest -q` dan berjalan **< 60 detik** (pakai file kecil via `tmp_path`, 1.000–20.000 baris). Target cakupan ≥ 85% pada `src/log_analyzer` (cek dengan `pytest --cov`).

| File test | Yang diuji |
|---|---|
| `test_generator.py` | jumlah baris persis sama dengan permintaan (0, 1, 1.000, 20.000); seed sama → file identik, seed beda → isi beda; rasio malformed mendekati target; baris valid lolos regex; folder output dibuat otomatis; argumen negatif ditolak |
| `test_parser.py` | baris valid terparse benar tiap field; baris kosong, field hilang, status huruf, level tidak dikenal, IP rusak → `None` tanpa exception; unicode aneh tidak membuat crash |
| `test_stats.py` | `merge` asosiatif, komutatif, dan identitas = stats kosong; `top_n` tie-break deterministik; p95 hasil merge sama dengan hitung langsung; objek bisa di-pickle; `__eq__` benar |
| `test_chunking.py` | gabungan semua chunk = semua baris tanpa duplikat/hilang, untuk 1..16 chunk; file kosong; satu baris; tanpa newline akhir; chunk > jumlah baris; baris panjang melintasi batas chunk |
| `test_equivalence.py` | `sequential == threads == processes` (parametrize workers 1, 2, 4) pada file hasil generate; hasil konsisten saat dijalankan berulang |
| `test_cli.py` | `generate` membuat file; `analyze` tiap mode menghasilkan output yang memuat **"ZHEKA BAILA ARKAN"** dan **"247006111152"**, jumlah worker, dan waktu total; argumen tidak valid memberi exit code non-zero |

Tambahan: tes untuk `bug_demo` bersifat **non-deterministik**, jadi jangan assert bahwa race condition pasti terjadi. Cukup uji bahwa skrip bisa dijalankan tanpa crash (smoke test) dengan data kecil.

---

## 9. Laporan (`laporan/LAPORAN.md`) → PDF

Susun mengikuti template UTS, isi memakai **hasil nyata dari benchmark**:

**A. Konsep dan Desain Solusi (20%)**
- Judul dan deskripsi singkat proyek.
- Deskripsi solusi untuk 3 pendekatan (Sequential, Multithread, Multiprocessing): cara membagi pekerjaan, byte-range chunking, map-reduce lokal lalu merge.
- Arsitektur sistem: buat diagram alur (generate PNG via matplotlib atau graphviz bila tersedia; sertakan juga sumber Mermaid) dengan tahap: Input File Log → Chunking (byte-range) → Worker 1..N (parse + hitung `LogStats` lokal) → Merge → Hasil & Metrik.

**B. Implementasi Kode (40%)**
- Kode versi bug (cuplikan relevan), penjelasan bug, dan **bukti** eksekusi (hasil salah, selisih, waktu).
- Kode final, penjelasan perbaikan, dan contoh output yang menampilkan NIM, nama, jumlah thread/process, waktu total, throughput/speedup/efisiensi.

**C. Hasil Percobaan (25%)**
- Spesifikasi mesin, tabel hasil untuk variasi jumlah data, thread, dan process, serta 3 grafik wajib dari Bagian 7.2.

**D. Analisis dan Kesimpulan (15%)**
- Perbedaan performa antar konfigurasi.
- Faktor paling berpengaruh (CPU-bound regex parsing vs I/O vs overhead komunikasi/merge), dikaitkan dengan GIL dan Hukum Amdahl.
- Mengapa efisiensi turun saat worker melebihi jumlah core.
- Kesimpulan umum.

**Output akhir laporan:** file `UTS_247006111152_ZhekaBailaArkan.pdf`. Jika tool konversi tersedia (pandoc / weasyprint / dll.), hasilkan PDF-nya. Jika tidak, siapkan `LAPORAN.md` yang rapi dan beri tahu pengguna cara konversinya.

---

## 10. Dokumentasi Akhir (WAJIB setelah semua selesai)

Setelah seluruh kode, test, benchmark, dan laporan beres, buat file baru **`DOKUMENTASI.md`** di root. Isinya harus lengkap:

1. **Ringkasan proyek** dan tujuan.
2. **Struktur direktori** lengkap berbentuk tree, dengan satu kalimat fungsi tiap file/folder.
3. **Alur data end-to-end** (dari generate → chunking → worker → merge → laporan) dengan diagram teks atau Mermaid.
4. **Penjelasan kode per file**, untuk SETIAP file sumber, test, dan skrip:
   - tujuan file,
   - setiap class dan fungsi: tanggung jawab, parameter, return value, kompleksitas bila relevan,
   - penjelasan baris/blok kode penting (regex, logika chunking, merge, pembagian worker),
   - alasan desain (mengapa byte-range, mengapa stats lokal, mengapa tanpa lock).
5. **Penjelasan setiap bug** di `bug_demo/`: mekanisme terjadinya, cara mereproduksi, bukti, dan perbaikannya.
6. **Penjelasan setiap file test**: apa yang diuji, mengapa itu penting, edge case yang ditangani.
7. **Panduan menjalankan**: instalasi, generate data, analyze, compare, benchmark, plot, test, dan coverage, lengkap dengan contoh perintah dan contoh output.
8. **Ringkasan hasil benchmark** (tabel final) dan keterbatasan (misalnya efek GIL, variasi hasil antar mesin).
9. **Catatan pengembangan lanjutan** (opsional).

Kode yang dijelaskan harus **sesuai dengan kode yang benar-benar ada**. Baca ulang file sumber sebelum menulis dokumentasi agar tidak ada yang mengarang.

---

## 11. Aturan Kerja untuk Agent

1. Kerjakan berurutan: struktur → config/parser/stats → generator → chunking → tiga pendekatan → CLI → unit test → bug demo → benchmark → grafik → laporan → dokumentasi.
2. Jalankan `pytest` setelah tiap komponen besar selesai; jangan lanjut jika masih ada test gagal.
3. **Dilarang** mengisi tabel atau grafik dengan angka karangan. Semua angka berasal dari eksekusi nyata di mesin ini.
4. Jangan menyalin kode dari proyek lain; ini tugas individu dan plagiarisme bernilai 0. Gaya penulisan kode harus konsisten dan bisa dijelaskan sendiri oleh pemilik tugas.
5. Beri type hints dan docstring pada semua fungsi publik.
6. Jika ada keputusan yang ambigu, pilih opsi paling sederhana yang sesuai dokumen ini dan catat di `DOKUMENTASI.md`.

---

## 12. Definition of Done (centang semua sebelum selesai)

- [ ] Output setiap mode menampilkan **Zheka Baila Arkan (247006111152)**, jumlah thread/process, waktu total, throughput
- [ ] Generator bisa membuat file dengan jumlah baris bebas (uji 1.000.000 baris)
- [ ] Sequential, multithread, dan multiprocessing menghasilkan statistik **identik**
- [ ] Minimal 1 bug paralel (target: 3) terdemonstrasi dengan bukti, dan versi final sudah memperbaikinya
- [ ] Benchmark ≥ 3 konfigurasi untuk data, thread, dan process; median dari 3 kali ulang
- [ ] 3 grafik wajib tersedia di `results/charts/`
- [ ] `pytest -q` lulus semua, cakupan ≥ 85%
- [ ] `laporan/LAPORAN.md` lengkap A–D dengan hasil nyata (dan PDF `UTS_247006111152_ZhekaBailaArkan.pdf` bila bisa dibuat)
- [ ] `README.md` berisi cara menjalankan singkat
- [ ] `DOKUMENTASI.md` lengkap sesuai Bagian 10
- [ ] Seluruh file kode siap dikumpulkan bersama PDF di LMS
