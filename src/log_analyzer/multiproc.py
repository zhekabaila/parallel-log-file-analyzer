"""Pendekatan 3: multiprocessing dengan ProcessPoolExecutor.

Worker adalah fungsi top-level ``chunking.process_chunk`` agar dapat di-pickle
pada start method ``spawn`` (default Windows). Yang dikirim ke worker hanya
``(path, start, end)`` dan yang dikembalikan hanya agregat kecil, sehingga
overhead komunikasi tetap rendah.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from log_analyzer.chunking import compute_chunks, get_file_size, process_chunk
from log_analyzer.config import MAX_ALLOWED_WORKERS
from log_analyzer.stats import LogStats, merge_all


def analyze_multiprocess(path: Path | str, num_processes: int) -> LogStats:
    """Analisis file menggunakan beberapa proses.

    Parameter:
        path: lokasi file log.
        num_processes: jumlah proses (>= 1); tiap proses satu chunk byte-range.

    Return:
        LogStats hasil merge seluruh chunk.

    Raise:
        ValueError: bila ``num_processes`` di luar batas yang diizinkan.
    """
    if num_processes < 1 or num_processes > MAX_ALLOWED_WORKERS:
        raise ValueError(f"num_processes harus berada di rentang 1-{MAX_ALLOWED_WORKERS}")

    chunks = compute_chunks(get_file_size(path), num_processes)
    tasks = [(str(path), start, end) for start, end in chunks if end > start]
    if not tasks:
        return LogStats()

    with ProcessPoolExecutor(max_workers=len(tasks)) as pool:
        partial_results = list(pool.map(process_chunk, tasks))
    return merge_all(partial_results)
