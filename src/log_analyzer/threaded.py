"""Pendekatan 2: multithread dengan ThreadPoolExecutor (pola map-reduce).

Setiap thread memegang satu byte-range dan membangun LogStats lokal, lalu merge
dilakukan di thread utama. Tidak ada lock pada hot path, sehingga race condition
dan biaya sinkronisasi per baris dapat dihindari.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from log_analyzer.chunking import compute_chunks, get_file_size, process_chunk
from log_analyzer.config import MAX_ALLOWED_WORKERS
from log_analyzer.stats import LogStats, merge_all


def analyze_threaded(path: Path | str, num_threads: int) -> LogStats:
    """Analisis file menggunakan beberapa thread.

    Parameter:
        path: lokasi file log.
        num_threads: jumlah thread (>= 1); tiap thread satu chunk byte-range.

    Return:
        LogStats hasil merge seluruh chunk.

    Raise:
        ValueError: bila ``num_threads`` di luar batas yang diizinkan.
    """
    if num_threads < 1 or num_threads > MAX_ALLOWED_WORKERS:
        raise ValueError(f"num_threads harus berada di rentang 1-{MAX_ALLOWED_WORKERS}")

    chunks = compute_chunks(get_file_size(path), num_threads)
    tasks = [(str(path), start, end) for start, end in chunks if end > start]
    if not tasks:
        return LogStats()

    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        partial_results = list(pool.map(process_chunk, tasks))
    return merge_all(partial_results)
