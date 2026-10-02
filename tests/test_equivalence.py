"""Uji ekuivalensi tiga pendekatan: sequential == threads == processes."""

from __future__ import annotations

import pytest

from log_analyzer.multiproc import analyze_multiprocess
from log_analyzer.sequential import analyze_sequential
from log_analyzer.stats import LogStats
from log_analyzer.threaded import analyze_threaded

WORKERS = [1, 2, 4]


@pytest.mark.parametrize("num_workers", WORKERS)
def test_threaded_sama_dengan_sequential(log_2000: object, num_workers: int) -> None:
    """Hasil multithread identik dengan sequential untuk berbagai jumlah thread."""
    assert analyze_threaded(log_2000, num_workers) == analyze_sequential(log_2000)


@pytest.mark.parametrize("num_workers", WORKERS)
def test_multiprocess_sama_dengan_sequential(log_2000: object, num_workers: int) -> None:
    """Hasil multiprocessing identik dengan sequential untuk berbagai jumlah proses."""
    assert analyze_multiprocess(log_2000, num_workers) == analyze_sequential(log_2000)


def test_ketiga_mode_identik_pada_file_lebih_besar(log_20000: object) -> None:
    """Sequential, threads, dan processes menghasilkan statistik yang sama."""
    sequential = analyze_sequential(log_20000)
    threaded = analyze_threaded(log_20000, 4)
    multiprocess = analyze_multiprocess(log_20000, 4)
    assert threaded == sequential
    assert multiprocess == threaded == sequential
    assert sequential.total_lines == 20_000


def test_hasil_konsisten_dijalankan_berulang(log_2000: object) -> None:
    """Menjalankan mode yang sama berulang kali memberi hasil identik."""
    first = analyze_multiprocess(log_2000, 3)
    second = analyze_multiprocess(log_2000, 3)
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_file_kosong_semua_mode(log_2000: object, tmp_path: object) -> None:
    """Semua mode menangani file kosong tanpa error dan menghasilkan agregat nol."""
    from pathlib import Path

    empty = Path(tmp_path) / "empty.log"  # type: ignore[arg-type]
    empty.write_bytes(b"")
    expected = LogStats()
    assert analyze_sequential(empty) == expected
    assert analyze_threaded(empty, 4) == expected
    assert analyze_multiprocess(empty, 4) == expected


@pytest.mark.parametrize("num_workers", [0, -1, 5000])
def test_workers_di_luar_batas_ditolak(log_2000: object, num_workers: int) -> None:
    """Jumlah worker tidak valid ditolak sejak awal oleh kedua modul paralel."""
    with pytest.raises(ValueError):
        analyze_threaded(log_2000, num_workers)
    with pytest.raises(ValueError):
        analyze_multiprocess(log_2000, num_workers)
