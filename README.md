# Parallel Log File Analyzer

**UTS Komputasi Paralel dan Terdistribusi (3 SKS)** — Informatika, Fakultas Teknik,
Universitas Siliwangi · Dosen: Rohmat Gunawan, M.T.
**Nama:** Zheka Baila Arkan · **NPM:** 247006111152
**Tema:** Parallel Computing in Our Lives

Analyzer file log server berukuran besar (diuji sampai 1.000.000 baris / 89,5 MB)
yang membandingkan tiga pendekatan: **Sequential**, **Multithread**, dan
**Multiprocessing**. Ketiganya menghasilkan statistik yang **identik** — hanya
waktunya yang berbeda, dan perbedaan itulah yang menjadi objek percobaan.

Statistik yang dihitung: jumlah baris per level (INFO/DEBUG/WARNING/ERROR),
distribusi status code & HTTP method, top-N IP address/user/path, aktivitas per jam,
response time (rata-rata, maksimum, p95), total bytes, dan jumlah baris malformed.

---

## Daftar Isi

1. [Prasyarat](#3-prasyarat)
2. [Instalasi](#4-instalasi)
3. [Mengaktifkan & keluar dari virtual environment](#5-mengaktifkan--keluar-dari-virtual-environment)
4. [Generate data log](#6-generate-data-log)
5. [Menjalankan analisis](#7-menjalankan-analisis)
6. [Membandingkan tiga pendekatan](#8-membandingkan-tiga-pendekatan)
7. [Bug demo paralel](#9-bug-demo-paralel)
8. [Benchmark & grafik](#10-benchmark--grafik)
9. [Unit test & coverage](#11-unit-test--coverage)
10. [Struktur folder & isi results/](#12-struktur-folder)
11. [Ringkasan hasil di mesin ini](#13-ringkasan-hasil-di-mesin-ini)
12. [Troubleshooting](#14-troubleshooting)

---

## 3. Prasyarat

| Kebutuhan | Versi | Catatan |
|---|---|---|
| Python | **3.10 atau lebih baru** | dikembangkan & diuji pada Python 3.14.4 (CPython) |
| OS | Windows / macOS / Linux | cross-platform; worker top-level + `if __name__ == "__main__":` agar aman pada start method `spawn` (default Windows & macOS) |
| RAM | ≥ 4 GB | file log **tidak pernah** dimuat utuh ke memori saat analisis |
| Disk | ±100 MB per 1 juta baris | dataset benchmark (100k + 500k + 1M) ≈ 134 MB di `data/` |
| Dependensi | hanya pustaka standar Python untuk logika inti | tambahan: `pytest`, `pytest-cov` (opsional), `matplotlib` |

Cek Python Anda:

```bash
python3 --version        # macOS / Linux
py -3 --version          # Windows
```

---

## 4. Instalasi

### 4.1 Clone / salin proyek, lalu buat virtual environment

```bash
cd parallel-log-file-analyzer

# macOS / Linux
python3 -m venv .venv

# Windows (PowerShell)
py -3 -m venv .venv
```

### 4.2 Aktifkan venv (langkah wajib sebelum perintah lain)

```bash
source .venv/bin/activate          # macOS / Linux (bash, zsh)
.venv\Scripts\Activate.ps1         # Windows (PowerShell)
.venv\Scripts\activate.bat         # Windows (cmd)
```

Setelah aktif, prompt shell berubah menjadi `(.venv) ...` dan `python` menunjuk ke
venv. Verifikasi:

```bash
python -c "import sys; print(sys.prefix)"
```

### 4.3 Install dependensi

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` berisi:

```
pytest>=8.0
pytest-cov>=5.0
matplotlib>=3.8
```

### 4.4 Install paket `log_analyzer` secara editable

```bash
pip install -e .
```

Perintah ini membaca `pyproject.toml` (layout `src/`) sehingga modul dapat diimpor
dari folder mana pun dengan nama `log_analyzer`. Setelah selesai, cek instalasi:

```bash
python -c "import log_analyzer; print(log_analyzer.__version__, log_analyzer.AUTHOR_NIM)"
# 1.0.0 247006111152

python -m log_analyzer.cli --help
```

> **Tanpa `pip install -e .`?** Semua perintah tetap bisa jalan dengan menambahkan
> folder `src` ke jalur impor:
> `PYTHONPATH=src python -m log_analyzer.cli ...` (Windows: `set PYTHONPATH=src`).

Keluar dari venv setelah selesai: `deactivate`.

---

## 6. Generate data log

```bash
python -m log_analyzer.cli generate --lines 1000000 --output data/server_1m.log --seed 42
```

Contoh output nyata:

```
======================================================
PARALLEL LOG FILE ANALYZER
By ZHEKA BAILA ARKAN (247006111152)
======================================================
[MULAI] membuat 1000000 baris log -> data/server_1m.log (seed=42)
  progress generate: 25% (250000/1000000 baris)
  progress generate: 50% (500000/1000000 baris)
  progress generate: 75% (750000/1000000 baris)
  progress generate: 100% (1000000/1000000 baris)
Selesai generate 1000000 baris -> data/server_1m.log dalam 6.52 detik
```

Format satu baris (regex acuan ada di `src/log_analyzer/config.py`):

```
2026-10-02T00:00:00.021 [INFO] 154.13.136.8 user_113 "GET /v2/items/7955" 204 37583 92ms
```

Opsi `generate`:

| Opsi | Default | Fungsi |
|---|---|---|
| `--lines` | 1000000 | jumlah baris total (termasuk yang malformed) |
| `--output` | wajib | lintasan file; folder induk dibuat otomatis |
| `--seed` | 42 | benih keacakan — **seed + jumlah baris sama ⇒ file byte-identical** |
| `--malformed-ratio` | 0.005 | proporsi baris rusak yang disengaja (0.0–1.0) |

---

## 7. Menjalankan analisis

```bash
python -m log_analyzer.cli analyze --input data/server_1m.log --mode sequential
python -m log_analyzer.cli analyze --input data/server_1m.log --mode threads   --workers 4
python -m log_analyzer.cli analyze --input data/server_1m.log --mode processes --workers 4
```

Opsi: `--mode sequential|threads|processes` (default sequential), `--workers N`
(jumlah thread/proses, default 4), `--top N` (banyaknya entri teratas, default 5).

Contoh output nyata (`--mode processes --workers 4`, file 1.000.000 baris):

```
======================================================
PARALLEL LOG FILE ANALYZER
By ZHEKA BAILA ARKAN (247006111152)
======================================================
[MULAI] membagi file menjadi 4 chunk
[SELESAI] worker-1 worker-2 worker-3 worker-4
======================================================
Mode             : multiprocessing
Jumlah proses  : 4
File             : data/server_1m.log (1.000.000 baris, 89.472.259 byte)
------------------------------------------------------
Waktu total      : 2.897 detik
Throughput       : 345.200 baris/detik
Speedup          : 1.62x   Efisiensi: 40.5%
======================================================
```

Cuplikan ringkasan statistik (mode yang sama):

```
Total baris      : 1.000.000
Baris malformed  : 5.037
Per level        : DEBUG 99.525 | ERROR 79.614 | INFO 696.396 | WARNING 119.428
Top-5 status     : 200 (521.536), 201 (83.261), 204 (75.926), 304 (58.983)
Response time    : rata-rata 248,17 ms | maksimum 2.000 ms | p95 1.252,54 ms
Total bytes      : 24.925.814.718
```

Catatan penting: pada mode `threads`/`processes`, program **juga** menjalankan
sequential satu kali sebagai baseline internal untuk menghitung speedup, sekaligus
**memvalidasi** bahwa hasil paralel identik dengan sequential. Bila berbeda, program
keluar dengan kode 2.

---

## 8. Membandingkan tiga pendekatan

```bash
python -m log_analyzer.cli compare --input data/server_1m.log --threads 4 --processes 4
```

Output nyata (transkrip: `results/cli_compare_1m.txt`):

```
Validasi ekuivalensi  : IDENTIK (lulus)
Base sequential (T0)  : 3.730 detik

| Mode          | Worker | Waktu (s) | Speedup | Efisiensi | Throughput (baris/s) |
|---------------|--------|-----------|---------|-----------|----------------------|
| sequential    |      1 |     3.730 |   1.00x |    100.0% |              268.101 |
```

Tabel ini siap disalin ke laporan. Kode exit 0 bila hasil identik, 2 bila berbeda.

---

## 9. Bug demo paralel

Tiga bug khas komputasi paralel, masing-masing berdiri sendiri dan mencetak bukti
pengukuran:

```bash
python bug_demo/buggy_race_condition.py --lines 50000  --threads 4 --runs 10
python bug_demo/buggy_sync_overhead.py  --lines 100000 --threads 4 --runs 3
python bug_demo/buggy_comm_overhead.py  --lines 100000 --processes 4 --runs 3
```

Hasil nyata di mesin ini (transkrip lengkap di `results/bug_evidence/`):

| Bug | Bukti |
|---|---|
| Race condition (statistik global tanpa lock) | **10/10 percobaan salah**, rata-rata 2.304 baris hilang (≈4,7%), jumlah ERROR hilang 175–216 baris |
| Sync overhead (1 lock per baris) | hasil benar, tetapi 0,399 s vs 0,259 s sequential = **1,54× lebih lambat** dengan 4 thread |
| Comm overhead (Queue per baris antar proses) | 1,301 s vs 0,197 s byte-range = **6,6× lebih lambat**; payload 10,3 MB vs 0,3 KB |

Skrip ini bersifat non-deterministik (race bisa tidak muncul pada sebagian mesin);
ulangi dengan `--runs` lebih besar atau `--lines` lebih banyak.

---

## 10. Benchmark & grafik

```bash
# Jalankan seluruh matriks (dataset dibuat otomatis di data/ sebelum pengukuran)
python benchmarks/run_benchmark.py

# Variasi pilihan
python benchmarks/run_benchmark.py --sizes 100000 500000 1000000 2000000 \
                                   --workers 1 2 4 8 --repeats 3
python benchmarks/run_benchmark.py --data-dir data --out-dir results --force-regenerate

# Buat grafik PNG dari CSV hasil benchmark
python benchmarks/plot_results.py
```

| Opsi `run_benchmark.py` | Default | Arti |
|---|---|---|
| `--sizes` | 100000 500000 1000000 | jumlah baris tiap dataset |
| `--workers` | 1 2 4 8 | jumlah thread **dan** proses yang dicoba |
| `--repeats` | 3 | kali ulang per konfigurasi (median diambil; 1× warm-up selalu dibuang) |
| `--seed` | 42 | benih generator |
| `--force-regenerate` | off | tulis ulang dataset meskipun sudah ada |

Keluaran benchmark:

- `results/benchmark_results.csv` — kolom: `mode, workers, num_lines, run, seconds,
  median_seconds, speedup, efficiency, throughput`
- `results/benchmark_results.json` — hasil + konfigurasi + info mesin
- `results/machine_info.json` — OS, CPU, core fisik/logis, RAM, versi Python
- tabel markdown di stdout (siap tempel ke `laporan/LAPORAN.md`)

Keluaran `plot_results.py` (backend `Agg`, 200 dpi, di `results/charts/`):

1. `waktu_vs_thread.png` — waktu vs jumlah thread + garis baseline sequential
2. `waktu_vs_process.png` — waktu vs jumlah proses + garis baseline sequential
3. `speedup_vs_konfigurasi.png` — speedup thread & proses + garis speedup ideal
4. `bug_vs_final.png` — perbandingan waktu bug demo vs kode final
   (muncul bila `results/bug_evidence/bug_evidence.json` tersedia)

Waktu tempuh benchmark penuh di mesin ini: ±4 menit.

---

## 11. Unit test & coverage

```bash
pytest -q                                     # semua test (95 test, ±2 detik)
pytest --cov=log_analyzer --cov-report=term   # cek cakupan
pytest --cov=log_analyzer --cov-report=html   # laporan HTML -> htmlcov/index.html
pytest tests/test_chunking.py -v              # satu berkas saja
```

Hasil di mesin ini: **95 passed**, cakupan **95%** (syarat tugas: lulus semua,
< 60 detik, cakupan ≥ 85%).

| Berkas test | Jumlah | Inti yang dibuktikan |
|---|---|---|
| `test_generator.py` | 12 | jumlah baris persis, seed ⇒ byte-identical, rasio malformed, validasi argumen |
| `test_parser.py` | 16 | field record benar; 10 bentuk baris rusak ⇒ `None` tanpa exception |
| `test_stats.py` | 13 | merge asosiatif/komutatif/identitas, `top_n` deterministik, p95 hasil merge, pickle |
| `test_chunking.py` | 31 | cakupan byte-range 1..16 chunk tanpa duplikat/hilang + edge case |
| `test_equivalence.py` | 12 | sequential == threads == processes (workers 1/2/4) |
| `test_cli.py` | 11 | output memuat nama & NIM, jumlah worker, waktu, throughput; exit code |

Konfigurasi pytest ada di `pytest.ini` (`testpaths = tests`, `pythonpath = src`), jadi
test tetap berjalan walau paket belum di-`pip install -e .`.

---

## 12. Struktur folder

```
.
├── TASK.md                Instruksi tugas
├── README.md              Dokumen ini
├── DOKUMENTASI.md         Penjelasan lengkap per file, fungsi, bug, test
├── requirements.txt       pytest, pytest-cov, matplotlib
├── pyproject.toml         pip install -e . (src layout)
├── pytest.ini             konfigurasi pytest
├── src/log_analyzer/      kode inti (config, generator, parser, stats,
│                          chunking, sequential, threaded, multiproc, reporter, cli)
├── bug_demo/              tiga bug paralel + bukti
├── benchmarks/            run_benchmark.py, plot_results.py
├── tests/                 95 unit test
├── data/                  file log hasil generate (di-.gitignore)
├── results/               CSV/JSON benchmark, machine info, bukti bug, charts/*.png
└── laporan/               LAPORAN.md, UTS_247006111152_ZhekaBailaArkan.pdf, gambar/
```

Laporan akhir ada di **`laporan/UTS_247006111152_ZhekaBailaArkan.pdf`** (14 halaman,
berisi bagian A Konsep & Desain, B Implementasi + bukti bug, C Hasil Percobaan +
grafik, D Analisis & Kesimpulan).

---

## 13. Ringkasan hasil di mesin ini

Mesin pengukuran: **Apple M1, 8 core fisik/logis, RAM 8 GB, macOS (arm64),
Python 3.14.4** — lihat `results/machine_info.json`. Median 3× ulang, 1× warm-up dibuang.

| Ukuran data | Sequential | Multithread terbaik | Multiprocessing terbaik |
|---|---|---|---|
| 100.000 | 0,316 s (1,00×) | 1 thread 0,363 s (0,87×) | 8 proses 0,289 s (1,09×) |
| 500.000 | 1,601 s (1,00×) | 1 thread 1,869 s (0,86×) | 8 proses 0,744 s (2,15×) |
| 1.000.000 | 3,183 s (1,00×) | 1 thread 3,725 s (0,85×) | 4 proses 1,498 s (**2,12×**, eff 53,1%) |

Interpretasi singkat: parsing regex adalah pekerjaan CPU-bound, sehingga **GIL membuat
multithread tidak lebih cepat dari sequential**, sedangkan **proses memberi percepatan
nyata namun sub-linear** (Amdahl + overhead startup pool ±0,6 s). Semua konfigurasi
paralel menghasilkan statistik identik dengan sequential.

---

## 14. Troubleshooting

| Gejala | Penyebab & solusi |
|---|---|
| `ModuleNotFoundError: No module named 'log_analyzer'` | Belum `pip install -e .` dari root proyek, atau venv belum aktif. Alternatif: `PYTHONPATH=src python -m log_analyzer.cli ...` |
| Perintah memakai Python sistem (bukan venv) | Aktifkan venv lebih dulu (`source .venv/bin/activate`); cek dengan `which python` / `where python` |
| `pip: command not found` setelah `python -m venv .venv` | Linux: pasang paket `python3-venv`; lalu ulangi `python -m pip install --upgrade pip` |
| PowerShell menolak `Activate.ps1` (execution policy) | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` lalu aktifkan lagi, atau pakai `.venv\Scripts\activate.bat` di cmd |
| `RuntimeError: ... start method ...` / error `pickle` pada mode processes | Pastikan menjalankan dari berkas (bukan `python - <<EOF`), dan worker tetap fungsi top-level. Semua entry point sudah dilindungi `if __name__ == "__main__":` |
| Mode processes tampak lebih lambat dari sequential pada file kecil | Wajar: overhead pembuatan pool ±0,6 s. Gunakan file ≥ 500.000 baris, atau bandingkan lewat `compare` |
| Angka benchmark berbeda dengan hasil Anda | Normal. Waktu bergantung mesin & beban latar; proyek ini melaporkan **median** — angka mentah tiap ulang ada di `results/benchmark_results.json` |
| `matplotlib` tidak bisa dipasang / grafik kosong | `pip install matplotlib`; plotting memakai backend `Agg` sehingga tidak butuh display. Jalankan `run_benchmark.py` lebih dulu agar CSV tersedia |
| `data/` kosong / file log hilang | Generate ulang (hasilnya reproducible): `python -m log_analyzer.cli generate --lines 1000000 --output data/server_1m.log --seed 42` |
| `pytest` bilang `log_analyzer` tidak ditemukan | `pytest.ini` sudah mengatur `pythonpath = src`; bila tetap bermasalah jalankan dari root proyek, atau `pip install -e .` |
| PDF laporan ingin dibuat ulang | `LAPORAN.md` → PDF bisa memakai pandoc (`pandoc laporan/LAPORAN.md -o laporan/UTS_247006111152_ZhekaBailaArkan.pdf`) atau Print-to-PDF dari aplikasi Markdown. PDF yang tersedia dibuat dengan Chrome headless + `markdown` sebagai build tool lokal (tidak ditambahkan ke `requirements.txt`) |

---

## Lisensi & Kontak

Proyek individu untuk keperluan UTS. Seluruh kode ditulis untuk tugas ini; angka
benchmark berasal dari eksekusi nyata, bukan estimasi.

**Zheka Baila Arkan — 247006111152 — Informatika, Universitas Siliwangi.**
