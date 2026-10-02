"""BUG DEMO 2 - Synchronization overhead: satu lock global dipegang per baris.

Perbaikan naif dari bug 1 adalah menambahkan ``threading.Lock()`` dan
mengakuisisinya untuk SETIAP baris. Hasilnya benar, tetapi seluruh thread
menumpu pada satu mutex sehingga pekerjaan justru lebih lambat daripada
sequential.

Cara menjalankan:
    python bug_demo/buggy_sync_overhead.py --lines 100000 --threads 4 --runs 3
"""

from __future__ import annotations

import argparse
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from log_analyzer.chunking import compute_chunks, get_file_size, iter_lines_in_range  # noqa: E402
from log_analyzer.config import DEFAULT_SEED  # noqa: E402
from log_analyzer.generator import generate_log_file  # noqa: E402
from log_analyzer.parser import parse_line  # noqa: E402
from log_analyzer.reporter import print_banner  # noqa: E402
from log_analyzer.sequential import analyze_sequential  # noqa: E402


class LockedCounters:
    """Statistik bersama yang dilindungi satu lock global (perbaikan naif)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.total_lines = 0
        self.error_count = 0

    def record(self, is_error: bool) -> None:
        """Akuisisi lock untuk SATU baris - inilah sumber overhead."""
        with self.lock:
            self.total_lines += 1
            if is_error:
                self.error_count += 1


def worker(path: Path, start: int, end: int, counters: LockedCounters) -> None:
    """Thread pemroses satu byte-range dengan update berkunci."""
    for line in iter_lines_in_range(path, start, end):
        record = parse_line(line)
        counters.record(bool(record and record["level"] == "ERROR"))


def run_locked(path: Path, num_threads: int) -> tuple[float, int, int]:
    """Jalankan versi lock per baris; kembalikan (waktu, total, error)."""
    counters = LockedCounters()
    chunks = [c for c in compute_chunks(get_file_size(path), num_threads) if c[1] > c[0]]
    started = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(path, s, e, counters)) for s, e in chunks]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return time.perf_counter() - started, counters.total_lines, counters.error_count


def run_unthreaded(path: Path) -> tuple[float, int, int]:
    """Loop tunggal tanpa lock sebagai pembanding (bentuk kode sama)."""
    total = 0
    errors = 0
    started = time.perf_counter()
    for line in iter_lines_in_range(path, 0, get_file_size(path)):
        record = parse_line(line)
        total += 1
        if record and record["level"] == "ERROR":
            errors += 1
    return time.perf_counter() - started, total, errors


def main(argv: list[str] | None = None) -> int:
    """Ukur waktu lock-per-baris dibandingkan sequential dan paralel tanpa lock."""
    parser = argparse.ArgumentParser(description="Demo synchronization overhead")
    parser.add_argument("--lines", type=int, default=100_000)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "bug_sync.log")
    args = parser.parse_args(argv)

    print_banner()
    print("BUG DEMO 2 : Synchronization overhead, satu lock global per baris")
    print("-" * 54)

    if not args.output.exists() or get_file_size(args.output) == 0:
        print(f"  prepare data uji: {args.lines} baris -> {args.output}")
        generate_log_file(args.output, args.lines, seed=DEFAULT_SEED)

    baseline = analyze_sequential(args.output)
    sequential_times: list[float] = []
    for _ in range(args.runs):
        elapsed, total, errors = run_unthreaded(args.output)
        sequential_times.append(elapsed)
        assert total == baseline.total_lines

    locked_times: list[float] = []
    locked_correct = True
    for _ in range(args.runs):
        elapsed, total, errors = run_locked(args.output, args.threads)
        locked_times.append(elapsed)
        locked_correct = locked_correct and (total == baseline.total_lines) and (
            errors == baseline.level_counts.get("ERROR", 0)
        )

    sequential_median = statistics.median(sequential_times)
    locked_median = statistics.median(locked_times)

    print("\nTiga kali ulang (detik):")
    print(f"  sequential tanpa lock : {['%.3f' % value for value in sequential_times]}")
    print(f"  threads + lock/baris  : {['%.3f' % value for value in locked_times]}")
    print("\nRingkasan:")
    print(f"  jumlah thread                 : {args.threads}")
    print(f"  median sequential             : {sequential_median:.3f} s")
    print(f"  median lock per baris         : {locked_median:.3f} s")
    print(f"  rasio waktu                   : {locked_median / sequential_median:.2f}x sequential")
    print(f"  hasil benar?                  : {'YA' if locked_correct else 'TIDAK'}")
    print("  Kesimpulan: benar, tetapi biaya akuisisi lock per baris membuat")
    print("  paralelisasi tidak memberi kecepatan apa pun (semua thread antre).")
    print("=" * 54)
    return 0


if __name__ == "__main__":
    sys.exit(main())
