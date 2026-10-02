"""Membuat grafik PNG hasil benchmark dari ``results/benchmark_results.csv``.

Empat grafik dihasilkan ke ``results/charts/`` dengan backend ``Agg`` (tanpa
display) dan resolusi 200 dpi: waktu vs thread, waktu vs process, speedup,
dan perbandingan bug demo vs kode final.

Cara menjalankan:
    python benchmarks/plot_results.py
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DPI = 200
COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


def load_rows(csv_path: Path) -> list[dict[str, float | int | str]]:
    """Baca CSV benchmark menjadi list dict dengan tipe angka yang benar."""
    rows: list[dict[str, float | int | str]] = []
    with open(csv_path, newline="", encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            rows.append(
                {
                    "mode": record["mode"],
                    "workers": int(record["workers"]),
                    "num_lines": int(record["num_lines"]),
                    "median_seconds": float(record["median_seconds"]),
                    "speedup": float(record["speedup"]),
                    "efficiency": float(record["efficiency"]),
                    "throughput": int(record["throughput"]),
                }
            )
    return rows


def _group_by_workers(
    rows: list[dict[str, float | int | str]], mode: str
) -> tuple[dict[int, dict[int, float]], list[int]]:
    """Kelompokkan median waktu menjadi ``{num_lines: {workers: seconds}}``."""
    grouped: dict[int, dict[int, float]] = defaultdict(dict)
    worker_values: set[int] = set()
    for row in rows:
        if row["mode"] != mode:
            continue
        num_lines = int(row["num_lines"])
        workers = int(row["workers"])
        grouped[num_lines][workers] = float(row["median_seconds"])
        worker_values.add(workers)
    return dict(grouped), sorted(worker_values)


def plot_time_vs_workers(
    rows: list[dict[str, float | int | str]], mode: str, title: str, out_path: Path
) -> None:
    """Grafik 1/2: waktu analisis vs jumlah worker, satu garis per ukuran data."""
    grouped, worker_values = _group_by_workers(rows, mode)
    baseline = {
        (int(row["num_lines"]), int(row["workers"])): float(row["median_seconds"])
        for row in rows
        if row["mode"] == "sequential"
    }

    figure, axis = plt.subplots(figsize=(8, 5))
    for index, (num_lines, points) in enumerate(sorted(grouped.items())):
        xs = sorted(points)
        ys = [points[x] for x in xs]
        axis.plot(xs, ys, marker="o", linewidth=2,
                  color=COLORS[index % len(COLORS)], label=f"{num_lines:,} baris")

    for index, (num_lines, _points) in enumerate(sorted(grouped.items())):
        base_seconds = baseline.get((num_lines, 1))
        if base_seconds is not None and worker_values:
            axis.axhline(
                base_seconds,
                linestyle="--",
                linewidth=1.0,
                color=COLORS[index % len(COLORS)],
                alpha=0.55,
            )
            if index == 0:
                axis.annotate(
                    "baseline sequential",
                    xy=(worker_values[0], base_seconds),
                    xytext=(4, 6),
                    textcoords="offset points",
                    fontsize=8,
                    color="#555555",
                )

    axis.set_title(title)
    axis.set_xlabel(f"Jumlah {'thread' if mode == 'threads' else 'proses'}")
    axis.set_ylabel("Waktu analisis (detik)")
    axis.set_xticks(worker_values)
    axis.grid(True, alpha=0.3)
    axis.legend(title="Ukuran data")
    figure.tight_layout()
    figure.savefig(out_path, dpi=DPI)
    plt.close(figure)


def plot_speedup(rows: list[dict[str, float | int | str]], out_path: Path) -> None:
    """Grafik 3: speedup thread & process untuk tiap ukuran data + garis ideal."""
    numbers: dict[tuple[str, int, int], float] = {}
    baseline: dict[int, float] = {}
    for row in rows:
        key = (str(row["mode"]), int(row["num_lines"]), int(row["workers"]))
        numbers[key] = float(row["speedup"])
        if row["mode"] == "sequential":
            baseline[int(row["num_lines"])] = float(row["median_seconds"])

    target_lines = sorted({int(row["num_lines"]) for row in rows if row["mode"] != "sequential"})
    worker_values = sorted({int(row["workers"]) for row in rows if row["mode"] != "sequential"})

    figure, axis = plt.subplots(figsize=(9, 5.5))
    for index, num_lines in enumerate(target_lines):
        thread_points = [numbers.get(("threads", num_lines, w)) for w in worker_values]
        process_points = [numbers.get(("processes", num_lines, w)) for w in worker_values]
        xs = [w for w, value in zip(worker_values, thread_points) if value is not None]
        axis.plot(xs, [v for v in thread_points if v is not None], marker="o",
                  linestyle="-", color=COLORS[index % len(COLORS)],
                  label=f"{num_lines:,} baris - thread")
        xs = [w for w, value in zip(worker_values, process_points) if value is not None]
        axis.plot(xs, [v for v in process_points if v is not None], marker="s",
                  linestyle="-.", color=COLORS[index % len(COLORS)], alpha=0.75,
                  label=f"{num_lines:,} baris - process")

    if worker_values:
        axis.plot(worker_values, worker_values, linestyle=":", color="#333333",
                  linewidth=1.5, label="speedup ideal (linear)")

    axis.set_title("Speedup terhadap baseline sequential")
    axis.set_xlabel("Jumlah worker (thread = lingkaran, process = kotak)")
    axis.set_ylabel("Speedup (x)")
    axis.set_xticks(worker_values)
    axis.grid(True, alpha=0.3)
    axis.legend(fontsize=8, ncol=2)
    figure.tight_layout()
    figure.savefig(out_path, dpi=DPI)
    plt.close(figure)


def plot_bug_comparison(results_dir: Path, out_path: Path) -> bool:
    """Grafik 4 (opsional): waktu bug demo vs kode final dari JSON bukti."""
    evidence_path = results_dir / "bug_evidence" / "bug_evidence.json"
    if not evidence_path.exists():
        return False
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    labels: list[str] = []
    values: list[float] = []
    for item in evidence.get("timings", []):
        labels.append(item["label"])
        values.append(item["seconds"])
    if not values:
        return False

    figure, axis = plt.subplots(figsize=(8, 4.6))
    bars = axis.bar(labels, values, color=["#d62728", "#ff7f0e", "#2ca02c"][: len(values)])
    for bar, value in zip(bars, values):
        axis.annotate(f"{value:.2f}s", xy=(bar.get_x() + bar.get_width() / 2, value),
                      xytext=(0, 3), textcoords="offset points", ha="center", fontsize=9)
    axis.set_title("Overhead bug paralel vs kode final")
    axis.set_ylabel("Waktu (detik)")
    axis.grid(True, axis="y", alpha=0.3)
    figure.tight_layout()
    figure.savefig(out_path, dpi=DPI)
    plt.close(figure)
    return True


def main(argv: list[str] | None = None) -> int:
    """Baca CSV benchmark lalu tulis seluruh grafik PNG."""
    parser = argparse.ArgumentParser(description="Plot hasil benchmark")
    parser.add_argument("--csv", type=Path, default=ROOT / "results" / "benchmark_results.csv")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results" / "charts")
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(f"ERROR: CSV tidak ditemukan: {args.csv}\n"
              f"Jalankan dulu: python benchmarks/run_benchmark.py", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.csv)

    outputs = {
        "waktu_vs_thread.png": ("threads", "Waktu Analisis vs Jumlah Thread"),
        "waktu_vs_process.png": ("processes", "Waktu Analisis vs Jumlah Proses"),
    }
    made: list[Path] = []
    for filename, (mode, title) in outputs.items():
        path = args.out_dir / filename
        plot_time_vs_workers(rows, mode, title, path)
        made.append(path)

    speedup_path = args.out_dir / "speedup_vs_konfigurasi.png"
    plot_speedup(rows, speedup_path)
    made.append(speedup_path)

    bug_path = args.out_dir / "bug_vs_final.png"
    if plot_bug_comparison(args.out_dir.parent, bug_path):
        made.append(bug_path)
    else:
        print("Catatan: bug_evidence.json belum ada, grafik 4 dilewati.")

    for path in made:
        print(f"grafik ditulis: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
