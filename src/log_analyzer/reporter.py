"""Pelaporan hasil ke konsol: banner identitas, waktu, throughput, ringkasan."""

from __future__ import annotations

import os
from pathlib import Path

from log_analyzer.config import (
    APP_NAME,
    AUTHOR_NAME,
    AUTHOR_NIM,
    BANNER_WIDTH,
    DEFAULT_TOP_N,
)
from log_analyzer.stats import LogStats, top_n

MODE_LABELS = {
    "sequential": "sequential",
    "threads": "multithread",
    "processes": "multiprocessing",
}

WORKER_LABELS = {
    "sequential": "Jumlah proses ",
    "threads": "Jumlah thread  ",
    "processes": "Jumlah proses ",
}


def format_int(value: int | float) -> str:
    """Format angka bulat dengan pemisah ribuan gaya Indonesia (titik)."""
    return f"{int(round(value)):,d}".replace(",", ".")


def format_seconds(seconds: float) -> str:
    """Format durasi detik dengan tiga angka desimal dan pemisah ribuan."""
    return f"{seconds:,.3f}".replace(",", ".")


def print_banner() -> None:
    """Cetak banner identitas wajib pada setiap output program."""
    line = "=" * BANNER_WIDTH
    print(line)
    print(APP_NAME)
    print(f"By {AUTHOR_NAME} ({AUTHOR_NIM})")
    print(line)


def count_file_lines(path: Path | str) -> int:
    """Hitung jumlah baris file secara streaming (tanpa memuat isi ke memori)."""
    total = 0
    with open(path, "rb") as handle:
        for _ in handle:
            total += 1
    return total


def print_chunk_plan(num_chunks: int) -> None:
    """Cetak informasi pembagian file menjadi chunk."""
    print(f"[MULAI] membagi file menjadi {num_chunks} chunk")


def print_worker_done(num_workers: int) -> None:
    """Cetak daftar worker yang telah menyelesaikan bagiannya."""
    names = " ".join(f"worker-{index}" for index in range(1, num_workers + 1))
    print(f"[SELESAI] {names}")


def print_result(
    stats: LogStats,
    mode: str,
    elapsed_seconds: float,
    input_path: Path | str,
    num_workers: int = 1,
    baseline_seconds: float | None = None,
    top_n_value: int = DEFAULT_TOP_N,
    show_banner: bool = True,
) -> None:
    """Cetak laporan lengkap satu kali analisis.

    Parameter:
        stats: agregat hasil analisis.
        mode: ``sequential`` | ``threads`` | ``processes``.
        elapsed_seconds: waktu total analisis dalam detik.
        input_path: file log yang dianalisis.
        num_workers: jumlah thread/proses yang digunakan.
        baseline_seconds: waktu sequential untuk menghitung speedup.
        top_n_value: banyaknya entri teratas yang ditampilkan.
        show_banner: apakah banner identitas ikut dicetak.
    """
    if show_banner:
        print_banner()

    file_size = os.path.getsize(input_path) if Path(input_path).exists() else 0
    print(f"Mode             : {MODE_LABELS.get(mode, mode)}")
    print(f"{WORKER_LABELS.get(mode, 'Jumlah worker')} : {num_workers}")
    print(
        f"File             : {input_path} "
        f"({format_int(stats.total_lines)} baris, {format_int(file_size)} byte)"
    )
    print("-" * BANNER_WIDTH)
    print(f"Waktu total      : {format_seconds(elapsed_seconds)} detik")
    throughput = stats.total_lines / elapsed_seconds if elapsed_seconds > 0 else 0.0
    print(f"Throughput       : {format_int(throughput)} baris/detik")

    if baseline_seconds is not None and baseline_seconds > 0 and num_workers > 0:
        speedup = baseline_seconds / elapsed_seconds
        efficiency = speedup / num_workers * 100.0
        print(f"Speedup          : {speedup:.2f}x   Efisiensi: {efficiency:.1f}%")

    print("=" * BANNER_WIDTH)
    print_stat_summary(stats, top_n_value=top_n_value)


def print_stat_summary(stats: LogStats, top_n_value: int = DEFAULT_TOP_N) -> None:
    """Cetak ringkasan statistik dari sebuah LogStats."""
    print("Ringkasan Statistik")
    print("-" * BANNER_WIDTH)
    print(f"Total baris      : {format_int(stats.total_lines)}")
    print(f"Baris malformed  : {format_int(stats.malformed_lines)}")
    print(f"Baris valid      : {format_int(stats.parsed_lines)}")

    print("\nPer level:")
    for level, count in sorted(stats.level_counts.items()):
        print(f"  {level:<8}: {format_int(count):>12}")

    print(f"\nTop-{top_n_value} status code:")
    for status, count in top_n(stats.status_counts, top_n_value):
        print(f"  {status:<8}: {format_int(count):>12}")

    print(f"\nDistribusi HTTP method:")
    for method, count in top_n(stats.method_counts, 10):
        print(f"  {method:<8}: {format_int(count):>12}")

    print(f"\nTop-{top_n_value} IP address:")
    for ip, count in top_n(stats.ip_counts, top_n_value):
        print(f"  {ip:<16}: {format_int(count):>12}")

    print(f"\nTop-{top_n_value} user:")
    for user, count in top_n(stats.user_counts, top_n_value):
        print(f"  {user:<12}: {format_int(count):>12}")

    print(f"\nTop-{top_n_value} path/endpoint:")
    for path, count in top_n(stats.path_counts, top_n_value):
        print(f"  {path:<24}: {format_int(count):>12}")

    print("\nAktivitas per jam:")
    for hour in sorted(stats.hourly_counts):
        print(f"  {hour:02d}:00  {format_int(stats.hourly_counts[hour]):>12}")

    print("\nResponse time & traffic:")
    print(f"  Rata-rata : {stats.average_response_ms():.2f} ms")
    print(f"  Maksimum  : {format_int(stats.max_response_ms)} ms")
    print(f"  p95       : {stats.p95_response_ms():.2f} ms")
    print(f"  Total bytes : {format_int(stats.total_bytes)}")
    print("=" * BANNER_WIDTH)


def speedup_ratio(baseline_seconds: float, parallel_seconds: float) -> float:
    """Hitung speedup ``T_sequential / T_parallel``."""
    if parallel_seconds <= 0:
        return 0.0
    return baseline_seconds / parallel_seconds


def efficiency_percent(baseline_seconds: float, parallel_seconds: float, workers: int) -> float:
    """Hitung efisiensi ``speedup / jumlah_worker`` dalam persen."""
    if workers <= 0:
        return 0.0
    return speedup_ratio(baseline_seconds, parallel_seconds) / workers * 100.0
