"""Entry point command line: subcommand ``generate``, ``analyze``, ``compare``.

Contoh:
    python -m log_analyzer.cli generate --lines 1000000 --output data/server_1m.log
    python -m log_analyzer.cli analyze --mode processes --workers 4 --input data/server_1m.log
    python -m log_analyzer.cli compare --input data/server_1m.log --threads 4 --processes 4
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from log_analyzer.config import (
    DEFAULT_MALFORMED_RATIO,
    DEFAULT_NUM_WORKERS,
    DEFAULT_SEED,
    DEFAULT_TOP_N,
    MAX_ALLOWED_WORKERS,
    MODES,
)
from log_analyzer.generator import generate_log_file
from log_analyzer.multiproc import analyze_multiprocess
from log_analyzer.reporter import (
    count_file_lines,
    print_banner,
    print_chunk_plan,
    print_result,
    print_worker_done,
)
from log_analyzer.sequential import analyze_sequential
from log_analyzer.stats import LogStats
from log_analyzer.threaded import analyze_threaded

ANALYZERS = {
    "sequential": lambda path, workers: analyze_sequential(path),
    "threads": analyze_threaded,
    "processes": analyze_multiprocess,
}


class InputError(ValueError):
    """Galat validasi input (file tidak ada / bukan file) -> kode exit 1."""


def positive_int(value: str) -> int:
    """Type argparse: bilangan bulat positif dalam batas worker."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"nilai harus bilangan bulat: {value!r}") from exc
    if number < 1 or number > MAX_ALLOWED_WORKERS:
        raise argparse.ArgumentTypeError(
            f"nilai harus berada di rentang 1-{MAX_ALLOWED_WORKERS}, bukan {number}"
        )
    return number


def non_negative_int(value: str) -> int:
    """Type argparse: bilangan bulat >= 0."""
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"nilai harus bilangan bulat: {value!r}") from exc
    if number < 0:
        raise argparse.ArgumentTypeError(f"nilai tidak boleh negatif: {number}")
    return number


def ratio(value: str) -> float:
    """Type argparse: rasio di rentang 0.0 - 1.0."""
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"nilai harus pecahan: {value!r}") from exc
    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError(f"rasio harus di rentang 0.0-1.0, bukan {number}")
    return number


def build_parser() -> argparse.ArgumentParser:
    """Susun parser argparse beserta seluruh subcommand."""
    parser = argparse.ArgumentParser(
        prog="log_analyzer.cli",
        description=(
            "Parallel Log File Analyzer - Komputasi Paralel dan Terdistribusi "
            "UTS (Zheka Baila Arkan, 247006111152)"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="buat file log dummy")
    generate.add_argument("--lines", type=non_negative_int, default=1_000_000, help="jumlah baris")
    generate.add_argument("--output", type=Path, required=True, help="lintasan file hasil")
    generate.add_argument("--seed", type=int, default=DEFAULT_SEED, help="benih keacakan")
    generate.add_argument(
        "--malformed-ratio",
        type=ratio,
        default=DEFAULT_MALFORMED_RATIO,
        help="proporsi baris rusak yang disengaja",
    )

    analyze = subparsers.add_parser("analyze", help="analisis satu file log")
    analyze.add_argument("--input", type=Path, required=True, help="file log yang dianalisis")
    analyze.add_argument("--mode", choices=MODES, default="sequential", help="pendekatan analisis")
    analyze.add_argument(
        "--workers", type=positive_int, default=DEFAULT_NUM_WORKERS, help="jumlah thread/proses"
    )
    analyze.add_argument("--top", type=positive_int, default=DEFAULT_TOP_N, help="banyaknya entri teratas")

    compare = subparsers.add_parser("compare", help="bandingkan ketiga pendekatan")
    compare.add_argument("--input", type=Path, required=True, help="file log yang dianalisis")
    compare.add_argument("--threads", type=positive_int, default=DEFAULT_NUM_WORKERS, help="jumlah thread")
    compare.add_argument("--processes", type=positive_int, default=DEFAULT_NUM_WORKERS, help="jumlah proses")
    compare.add_argument("--top", type=positive_int, default=DEFAULT_TOP_N, help="banyaknya entri teratas")

    return parser


def _require_file(path: Path) -> None:
    """Validasi bahwa input berupa file biasa yang tersedia.

    Raise:
        InputError: bila path tidak ada atau bukan file biasa. Kode exit 1
        dihasilkan oleh ``main`` yang menangkap ValueError ini.
    """
    if not path.exists():
        print(f"ERROR: file tidak ditemukan: {path}", file=sys.stderr)
        raise InputError(f"file tidak ditemukan: {path}")
    if not path.is_file():
        print(f"ERROR: bukan file biasa: {path}", file=sys.stderr)
        raise InputError(f"bukan file biasa: {path}")


def _run(mode: str, path: Path, workers: int) -> tuple[LogStats, float]:
    """Jalankan satu mode analisis dan ukur waktunya dengan perf_counter."""
    analyzer = ANALYZERS[mode]
    started = time.perf_counter()
    stats = analyzer(path, workers)
    elapsed = time.perf_counter() - started
    return stats, elapsed


def cmd_generate(args: argparse.Namespace) -> int:
    """Implementasi subcommand ``generate``."""
    print_banner()
    print(f"[MULAI] membuat {args.lines} baris log -> {args.output} (seed={args.seed})")
    generate_log_file(
        path=args.output,
        num_lines=args.lines,
        seed=args.seed,
        malformed_ratio=args.malformed_ratio,
    )
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Implementasi subcommand ``analyze``."""
    _require_file(args.input)
    print_banner()

    if args.mode == "sequential":
        stats, elapsed = _run("sequential", args.input, 1)
        print_result(stats, "sequential", elapsed, args.input, num_workers=1, top_n_value=args.top)
        return 0

    file_size = args.input.stat().st_size
    num_chunks = min(args.workers, max(1, file_size))
    print_chunk_plan(num_chunks)
    stats, elapsed = _run(args.mode, args.input, args.workers)
    print_worker_done(num_chunks)
    baseline_stats, baseline_seconds = _run("sequential", args.input, 1)
    if baseline_stats != stats:
        print(
            "ERROR: hasil paralel berbeda dari sequential, periksa chunking/merge.",
            file=sys.stderr,
        )
        return 2
    print_result(
        stats,
        args.mode,
        elapsed,
        args.input,
        num_workers=args.workers,
        baseline_seconds=baseline_seconds,
        top_n_value=args.top,
        show_banner=False,
    )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    """Implementasi subcommand ``compare``: jalankan tiga mode lalu bandingkan."""
    _require_file(args.input)
    print_banner()

    results: list[tuple[str, int, LogStats, float]] = []

    print_chunk_plan(1)
    seq_stats, seq_seconds = _run("sequential", args.input, 1)
    results.append(("sequential", 1, seq_stats, seq_seconds))

    print_chunk_plan(args.threads)
    thread_stats, thread_seconds = _run("threads", args.input, args.threads)
    print_worker_done(args.threads)
    results.append(("threads", args.threads, thread_stats, thread_seconds))

    print_chunk_plan(args.processes)
    process_stats, process_seconds = _run("processes", args.input, args.processes)
    print_worker_done(args.processes)
    results.append(("processes", args.processes, process_stats, process_seconds))

    identical = seq_stats == thread_stats == process_stats
    print("-" * 54)
    print(f"Validasi ekuivalensi  : {'IDENTIK (lulus)' if identical else 'BEDA (gagal)'}")
    print(f"Base sequential (T0)  : {seq_seconds:.3f} detik")
    print()
    print("| Mode          | Worker | Waktu (s) | Speedup | Efisiensi | Throughput (baris/s) |")
    print("|---------------|--------|-----------|---------|-----------|----------------------|")
    for mode, workers, _stats, seconds in results:
        speedup = seq_seconds / seconds if seconds > 0 else 0.0
        efficiency = speedup / workers * 100.0
        throughput = seq_stats.total_lines / seconds if seconds > 0 else 0.0
        label = {"sequential": "sequential", "threads": "multithread", "processes": "multiproc"}[mode]
        print(
            f"| {label:<13} | {workers:>6} | {seconds:>9.3f} | {speedup:>6.2f}x "
            f"| {efficiency:>9.1f}% | {throughput:>20,.0f} |".replace(",", ".")
        )
    print()

    for mode, workers, stats, seconds in results:
        baseline = seq_seconds if mode != "sequential" else None
        print_result(
            stats,
            mode,
            seconds,
            args.input,
            num_workers=workers,
            baseline_seconds=baseline,
            top_n_value=args.top,
            show_banner=False,
        )
        print()

    return 0 if identical else 2


def main(argv: list[str] | None = None) -> int:
    """Dispatcher utama CLI; mengembalikan exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {"generate": cmd_generate, "analyze": cmd_analyze, "compare": cmd_compare}
    try:
        return handlers[args.command](args)
    except KeyboardInterrupt:
        print("\nDibatalkan pengguna.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
