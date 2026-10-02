"""BUG DEMO 3 - Communication overhead: mengirim baris mentah ke worker.

Proses utama MEMBACA SELURUH baris ke memori, memecahnya menjadi list berisi
puluhan ribu string, lalu mem-pickle list tersebut untuk tiap worker. Payload
yang dikirim jauh lebih besar daripada hasil kerjanya, sehingga waktu membengkak
dibandingkan versi final yang mengirim hanya ``(path, start, end)``.

Cara menjalankan:
    python bug_demo/buggy_comm_overhead.py --lines 100000 --processes 4 --runs 3
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import pickle
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from log_analyzer.chunking import get_file_size  # noqa: E402
from log_analyzer.config import DEFAULT_SEED  # noqa: E402
from log_analyzer.generator import generate_log_file  # noqa: E402
from log_analyzer.multiproc import analyze_multiprocess  # noqa: E402
from log_analyzer.reporter import print_banner  # noqa: E402
from log_analyzer.stats import LogStats, merge_all  # noqa: E402


def count_raw_lines(lines: list[str]) -> LogStats:
    """Worker naif: terima list baris mentah, hitung lokal, kembalikan agregat."""
    stats = LogStats()
    stats.add_lines(lines)
    return stats


def queue_worker(task_queue: "mp.Queue", result_queue: "mp.Queue") -> None:
    """Worker naif versi Queue: terima SATU baris per pesan, kirim agregat sekali."""
    stats = LogStats()
    while True:
        message = task_queue.get()
        if message is None:
            break
        stats.add_lines([message])
    result_queue.put(stats)


def run_naive_queue(path: Path, num_processes: int) -> tuple[float, LogStats, int]:
    """Versi paling naif: proses utama membaca semua baris lalu mengirim tiap
    baris melalui ``multiprocessing.Queue`` (satu pesan per baris)."""
    started = time.perf_counter()
    lines = read_all_lines(path)
    payload_bytes = sum(len(pickle.dumps(line)) for line in lines)

    task_queue: "mp.Queue" = mp.Queue()
    result_queue: "mp.Queue" = mp.Queue()
    procs = [
        mp.Process(target=queue_worker, args=(task_queue, result_queue))
        for _ in range(num_processes)
    ]
    for proc in procs:
        proc.start()

    for line in lines:
        task_queue.put(line)
    for _ in procs:
        task_queue.put(None)

    partials = [result_queue.get() for _ in procs]
    for proc in procs:
        proc.join()

    return time.perf_counter() - started, merge_all(partials), payload_bytes


def read_all_lines(path: Path) -> list[str]:
    """PROSES UTAMA memuat semua baris ke memori (sumber masalah)."""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return [line.rstrip("\n") for line in handle]


def split_to_batches(lines: list[str], num_batches: int) -> list[list[str]]:
    """Bagi list baris menjadi beberapa batch string untuk dikirim ke worker."""
    batch_size = max(1, len(lines) // num_batches + (1 if len(lines) % num_batches else 0))
    return [lines[index : index + batch_size] for index in range(0, len(lines), batch_size)]


def run_naive(path: Path, num_processes: int) -> tuple[float, LogStats, int]:
    """Jalankan versi naif (Queue per baris); kembalikan (waktu, hasil, byte)."""
    return run_naive_queue(path, num_processes)


def run_final(path: Path, num_processes: int) -> tuple[float, LogStats, int]:
    """Jalankan versi final: worker membaca byte-range miliknya sendiri."""
    started = time.perf_counter()
    stats = analyze_multiprocess(path, num_processes)
    elapsed = time.perf_counter() - started
    payload_bytes = 3 * 8 + len(str(path)) * num_processes  # path + dua integer per task
    return elapsed, stats, payload_bytes


def main(argv: list[str] | None = None) -> int:
    """Bandingkan overhead komunikasi versi kirim-baris vs kirim-byte-range."""
    parser = argparse.ArgumentParser(description="Demo communication overhead")
    parser.add_argument("--lines", type=int, default=100_000)
    parser.add_argument("--processes", type=int, default=4)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "bug_comm.log")
    args = parser.parse_args(argv)

    print_banner()
    print("BUG DEMO 3 : Communication overhead, worker menerima baris mentah")
    print("-" * 54)

    if not args.output.exists() or get_file_size(args.output) == 0:
        print(f"  prepare data uji: {args.lines} baris -> {args.output}")
        generate_log_file(args.output, args.lines, seed=DEFAULT_SEED)

    if not args.output.exists():
        print(f"ERROR: file tidak ada: {args.output}", file=sys.stderr)
        return 1
    parent_pid = os.getpid()

    naive_times: list[float] = []
    final_times: list[float] = []
    naive_stats = None
    final_stats = None
    for run_index in range(1, args.runs + 1):
        naive_seconds, naive_stats, naive_payload = run_naive(args.output, args.processes)
        final_seconds, final_stats, final_payload = run_final(args.output, args.processes)
        naive_times.append(naive_seconds)
        final_times.append(final_seconds)
        print(f"  run {run_index}: naive={naive_seconds:.3f}s  final={final_seconds:.3f}s")

    naive_median = statistics.median(naive_times)
    final_median = statistics.median(final_times)
    print("\nRingkasan:")
    print(f"  proses                          : {args.processes} (pid utama {parent_pid})")
    print(f"  median waktu naive (kirim baris): {naive_median:.3f} s")
    print(f"  median waktu final (byte-range) : {final_median:.3f} s")
    print(f"  perbandingan                    : naive {naive_median / final_median:.2f}x lebih lambat")
    print(f"  payload terkirim naive          : {naive_payload / 1_000_000:.1f} MB")
    print(f"  payload terkirim final          : {final_payload / 1000:.1f} KB")
    print(f"  hasil keduanya identik          : {'YA' if naive_stats == final_stats else 'TIDAK'}")
    print("  Kesimpulan: serialisasi/deserialisasi string jutaan baris mendominasi")
    print("  waktu kerja; kirim hanya (path, start, end) dan kembalikan agregat kecil.")
    print("=" * 54)
    return 0


if __name__ == "__main__":
    sys.exit(main())
