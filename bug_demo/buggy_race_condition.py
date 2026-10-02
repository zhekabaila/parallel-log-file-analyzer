"""BUG DEMO 1 - Race condition pada statistik global tanpa lock.

Beberapa thread memperbarui satu objek statistik bersama secara langsung.
Operasi ``total += 1`` dipecah menjadi read -> ubah -> write memakai variabel
sementara, dan ``sys.setswitchinterval`` diperkecil agar window preemption
thread jatuh tepat di antara read dan write.

Cara menjalankan:
    python bug_demo/buggy_race_condition.py --lines 50000 --threads 4 --runs 10
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from log_analyzer.chunking import compute_chunks, get_file_size  # noqa: E402
from log_analyzer.config import DEFAULT_SEED  # noqa: E402
from log_analyzer.generator import generate_log_file  # noqa: E402
from log_analyzer.parser import parse_line  # noqa: E402
from log_analyzer.reporter import print_banner  # noqa: E402
from log_analyzer.sequential import analyze_sequential  # noqa: E402


class SharedCounters:
    """Statistik bersama yang sengaja TIDAK dilindungi lock (sumber bug)."""

    def __init__(self) -> None:
        self.total_lines = 0
        self.error_count = 0
        self.ip_counts: dict[str, int] = {}

    def record(self, ip: str, is_error: bool) -> None:
        """read -> ubah -> write pada ketiga field bersama.

        Jendela antara membaca nilai lama dan menulis nilai baru membuat thread
        lain dapat membaca nilai yang sama, sehingga update hilang.
        """
        current_total = self.total_lines
        current_errors = self.error_count
        current_ip = self.ip_counts.get(ip, 0)

        # Variabel sementara memperlebar jendela race tanpa menambah I/O.
        new_total = current_total + 1
        new_errors = current_errors + (1 if is_error else 0)
        new_ip = current_ip + 1

        self.total_lines = new_total
        self.ip_counts[ip] = new_ip
        self.error_count = new_errors


def worker(path: Path, start: int, end: int, counters: SharedCounters) -> None:
    """Satu thread: parse byte-range miliknya lalu tulis ke statistik bersama."""
    from log_analyzer.chunking import iter_lines_in_range

    for line in iter_lines_in_range(path, start, end):
        record = parse_line(line)
        counters.record(
            record["ip"] if record else "__malformed__",
            bool(record and record["level"] == "ERROR"),
        )


def run_once(path: Path, num_threads: int) -> tuple[int, int]:
    """Jalankan satu percobaan paralel; kembalikan (total_lines, error_count)."""
    counters = SharedCounters()
    chunks = [chunk for chunk in compute_chunks(get_file_size(path), num_threads) if chunk[1] > chunk[0]]
    threads = [
        threading.Thread(target=worker, args=(path, start, end, counters))
        for start, end in chunks
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return counters.total_lines, counters.error_count


def main(argv: list[str] | None = None) -> int:
    """Bangun data, ulangi percobaan, lalu bandingkan dengan hasil sequential."""
    parser = argparse.ArgumentParser(description="Demo race condition tanpa lock")
    parser.add_argument("--lines", type=int, default=50_000, help="jumlah baris data uji")
    parser.add_argument("--threads", type=int, default=4, help="jumlah thread")
    parser.add_argument("--runs", type=int, default=10, help="banyaknya pengulangan")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "bug_race.log")
    args = parser.parse_args(argv)

    print_banner()
    print("BUG DEMO 1 : Race condition, statistik global tanpa lock")
    print("-" * 54)

    if not args.output.exists() or get_file_size(args.output) == 0:
        print(f"prepare data uji: {args.lines} baris -> {args.output}")
        generate_log_file(args.output, args.lines, seed=DEFAULT_SEED)

    started = time.perf_counter()
    baseline = analyze_sequential(args.output)
    sequential_seconds = time.perf_counter() - started
    expected_total = baseline.total_lines
    expected_errors = baseline.level_counts.get("ERROR", 0)
    print(f"Baseline sequential : total={expected_total} errors={expected_errors} "
          f"({sequential_seconds:.3f} s)")

    sys.setswitchinterval(1e-6)
    mismatch_runs = 0
    worst_missing_total = 0
    worst_missing_errors = 0
    rows: list[str] = []

    for run_index in range(1, args.runs + 1):
        got_total, got_errors = run_once(args.output, args.threads)
        missing_total = expected_total - got_total
        missing_errors = expected_errors - got_errors
        ok = missing_total == 0 and missing_errors == 0
        if not ok:
            mismatch_runs += 1
        worst_missing_total = max(worst_missing_total, missing_total)
        worst_missing_errors = max(worst_missing_errors, missing_errors)
        rows.append(
            f"run {run_index:>2}: total={got_total:>7} (hilang {missing_total:>5}) "
            f"errors={got_errors:>6} (hilang {missing_errors:>5}) "
            f"{'OK' if ok else 'BEDA'}"
        )

    print("\nHasil per percobaan:")
    for row in rows:
        print("  " + row)

    print("\nRingkasan:")
    print(f"  jumlah percobaan             : {args.runs}")
    print(f"  percobaan dengan hasil salah : {mismatch_runs}")
    print(f"  selisih terbesar total baris : {worst_missing_total}")
    print(f"  selisih terbesar jumlah ERROR: {worst_missing_errors}")
    if mismatch_runs == 0:
        print("  Catatan: pada run ini race tidak teramati (non-deterministik), "
              "ulangi dengan --runs lebih banyak atau --lines lebih besar.")
    else:
        print("  Kesimpulan: update hilang (lost update) karena write tidak atomik.")
    print("=" * 54)
    return 0


if __name__ == "__main__":
    sys.exit(main())
