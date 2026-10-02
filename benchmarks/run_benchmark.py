"""Benchmark tiga pendekatan analisis log pada beberapa ukuran data.

Dataset dibuat SEKALI di luar pengukuran waktu. Setiap konfigurasi dijalankan
1x warm-up (dibuang) lalu 3x ulang, dan nilai yang dipakai adalah median dari
``time.perf_counter()``. Hasil paralel selalu di-assert identik dengan sequential.

Cara menjalankan:
    python benchmarks/run_benchmark.py
    python benchmarks/run_benchmark.py --sizes 100000 500000 --repeats 3
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from log_analyzer.config import DEFAULT_SEED  # noqa: E402
from log_analyzer.generator import generate_log_file  # noqa: E402
from log_analyzer.multiproc import analyze_multiprocess  # noqa: E402
from log_analyzer.reporter import print_banner  # noqa: E402
from log_analyzer.sequential import analyze_sequential  # noqa: E402
from log_analyzer.stats import LogStats  # noqa: E402
from log_analyzer.threaded import analyze_threaded  # noqa: E402

DEFAULT_SIZES = (100_000, 500_000, 1_000_000)
DEFAULT_WORKERS = (1, 2, 4, 8)
MODE_LABEL = {"sequential": "sequential", "threads": "multithread", "processes": "multiprocess"}

RUNNER = {
    "sequential": lambda path, workers: analyze_sequential(path),
    "threads": analyze_threaded,
    "processes": analyze_multiprocess,
}


def _sysctl(key: str) -> str | None:
    """Ambil nilai sysctl bila tersedia (dipakai untuk info mesin macOS)."""
    try:
        result = subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def collect_machine_info() -> dict[str, Any]:
    """Kumpulkan spesifikasi mesin: OS, CPU, core, RAM, versi Python.

    Return:
        Dict siap serialisasi JSON untuk ``results/machine_info.json``.
    """
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "logical_cores": os.cpu_count(),
        "gil_enabled": sys._getframe is not None and platform.python_implementation() == "CPython",
    }
    if platform.system() == "Darwin":
        info["cpu_brand"] = _sysctl("machdep.cpu.brand_string")
        info["physical_cores"] = _sysctl("hw.physicalcpu")
        info["logical_cores_sysctl"] = _sysctl("hw.logicalcpu")
        memory_bytes = _sysctl("hw.memsize")
        if memory_bytes:
            info["ram_gb"] = round(int(memory_bytes) / 1024**3, 1)
    else:
        info["cpu_brand"] = _sysctl("kernel.hostname")
        info["physical_cores"] = None
        try:
            meminfo = Path("/proc/meminfo").read_text(encoding="utf-8")
            first_line = meminfo.splitlines()[0]
            kb = int(first_line.split()[1])
            info["ram_gb"] = round(kb / 1024**2, 1)
        except (OSError, IndexError, ValueError):
            info["ram_gb"] = None
    return info


def measure(
    path: Path, mode: str, workers: int, repeats: int
) -> tuple[LogStats, float, list[float]]:
    """Jalankan warm-up lalu ``repeats`` pengukuran; kembalikan (stats, median, times).

    Raise:
        RuntimeError: bila hasil mode yang diukur berbeda dari hasil sebelumnya.
    """
    runner = RUNNER[mode]
    warmup = runner(path, workers)
    timings: list[float] = []
    last_stats = warmup
    for _ in range(repeats):
        started = time.perf_counter()
        stats = runner(path, workers)
        timings.append(time.perf_counter() - started)
        if stats != last_stats:
            raise RuntimeError(f"hasil {mode} workers={workers} tidak konsisten antar ulang")
    return warmup, statistics.median(timings), timings


def ensure_dataset(data_dir: Path, num_lines: int, seed: int, force: bool) -> Path:
    """Siapkan file log uji; generate hanya bila belum ada."""
    path = data_dir / f"server_{num_lines // 1000}k.log" if num_lines < 1_000_000 else data_dir / f"server_{num_lines // 1_000_000}m.log"
    if force or not path.exists() or path.stat().st_size == 0:
        print(f"\n[DATA] membuat dataset {num_lines} baris -> {path}")
        generate_log_file(path, num_lines, seed=seed)
    else:
        print(f"\n[DATA] memakai dataset yang sudah ada: {path} ({path.stat().st_size} byte)")
    return path


def build_parser() -> argparse.ArgumentParser:
    """Susun CLI benchmark."""
    parser = argparse.ArgumentParser(description="Benchmark sequential/thread/process")
    parser.add_argument("--sizes", type=int, nargs="+", default=list(DEFAULT_SIZES))
    parser.add_argument("--workers", type=int, nargs="+", default=list(DEFAULT_WORKERS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--force-regenerate", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Jalankan seluruh matriks benchmark dan tulis CSV/JSON/JSON mesin."""
    args = build_parser().parse_args(argv)
    print_banner()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.data_dir.mkdir(parents=True, exist_ok=True)

    machine_info = collect_machine_info()
    machine_info["measured_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (args.out_dir / "machine_info.json").write_text(
        json.dumps(machine_info, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n[MESIN] {machine_info.get('cpu_brand') or machine_info.get('processor')} | "
          f"fisik={machine_info.get('physical_cores')} logis={machine_info.get('logical_cores')} | "
          f"RAM={machine_info.get('ram_gb')} GB | Python {machine_info['python_version']}")

    rows: list[dict[str, Any]] = []
    summary: list[dict[str, Any]] = []
    failures: list[str] = []

    for num_lines in args.sizes:
        path = ensure_dataset(args.data_dir, num_lines, args.seed, args.force_regenerate)
        line_count = sum(1 for _ in open(path, "rb"))
        print(f"[VALIDASI] {path.name} berisi {line_count} baris")

        baseline_stats, baseline_median, baseline_times = measure(path, "sequential", 1, args.repeats)
        print(f"  sequential median = {baseline_median:.3f}s {['%.3f' % t for t in baseline_times]}")
        rows.append(
            {
                "mode": "sequential",
                "workers": 1,
                "num_lines": num_lines,
                "run": "median",
                "seconds": round(baseline_median, 6),
                "median_seconds": round(baseline_median, 6),
                "speedup": 1.0,
                "efficiency": 100.0,
                "throughput": round(num_lines / baseline_median),
            }
        )
        summary.append(
            {
                "num_lines": num_lines,
                "mode": "sequential",
                "workers": 1,
                "median_seconds": round(baseline_median, 6),
                "speedup": 1.0,
                "efficiency": 100.0,
                "throughput_rows_per_s": round(num_lines / baseline_median),
                "runs_seconds": [round(value, 6) for value in baseline_times],
                "equivalent_to_sequential": True,
            }
        )

        for mode in ("threads", "processes"):
            for workers in args.workers:
                try:
                    stats, median, times = measure(path, mode, workers, args.repeats)
                except RuntimeError as exc:
                    failures.append(str(exc))
                    print(f"  [GAGAL] {MODE_LABEL[mode]} workers={workers}: {exc}")
                    continue
                if stats != baseline_stats:
                    failures.append(
                        f"{MODE_LABEL[mode]} workers={workers} != sequential pada {num_lines} baris"
                    )
                    print(f"  [GAGAL] hasil {mode} workers={workers} berbeda dari sequential")
                    continue
                speedup = baseline_median / median
                efficiency = speedup / workers * 100.0
                print(f"  {MODE_LABEL[mode]:<13} w={workers}: {median:.3f}s "
                      f"speedup={speedup:.2f}x eff={efficiency:.1f}% "
                      f"{['%.3f' % t for t in times]}")
                rows.append(
                    {
                        "mode": mode,
                        "workers": workers,
                        "num_lines": num_lines,
                        "run": "median",
                        "seconds": round(median, 6),
                        "median_seconds": round(median, 6),
                        "speedup": round(speedup, 4),
                        "efficiency": round(efficiency, 2),
                        "throughput": round(num_lines / median),
                    }
                )
                summary.append(
                    {
                        "num_lines": num_lines,
                        "mode": mode,
                        "workers": workers,
                        "median_seconds": round(median, 6),
                        "speedup": round(speedup, 4),
                        "efficiency": round(efficiency, 2),
                        "throughput_rows_per_s": round(num_lines / median),
                        "runs_seconds": [round(value, 6) for value in times],
                        "equivalent_to_sequential": True,
                    }
                )

    csv_path = args.out_dir / "benchmark_results.csv"
    fieldnames = ["mode", "workers", "num_lines", "run", "seconds", "median_seconds",
                  "speedup", "efficiency", "throughput"]
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    json_payload = {
        "machine": machine_info,
        "config": {
            "sizes": list(args.sizes),
            "workers": list(args.workers),
            "repeats": args.repeats,
            "warmup_runs": 1,
            "seed": args.seed,
            "timer": "time.perf_counter",
            "aggregation": "median",
        },
        "results": summary,
    }
    json_path = args.out_dir / "benchmark_results.json"
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n## Tabel hasil benchmark (median dari "
          f"{args.repeats}x ulang, 1x warm-up dibuang)")
    print()
    print("| Jumlah data | Mode | Worker | Waktu (s) | Speedup | Efisiensi | Throughput (baris/s) |")
    print("|---|---|---|---|---|---|---|")
    for item in summary:
        print(
            f"| {item['num_lines']:,} | {MODE_LABEL[item['mode']]} | {item['workers']} | "
            f"{item['median_seconds']:.3f} | {item['speedup']:.2f}x | "
            f"{item['efficiency']:.1f}% | {item['throughput_rows_per_s']:,} |"
        )

    print(f"\nCSV   : {csv_path}")
    print(f"JSON  : {json_path}")
    if failures:
        print(f"\nADA {len(failures)} KEGAGALAN VALIDASI:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("Validasi ekuivalensi: seluruh konfigurasi IDENTIK dengan sequential.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
