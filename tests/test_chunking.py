"""Uji chunking byte-range: cakupan penuh tanpa duplikat atau baris hilang."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from log_analyzer.chunking import (
    compute_chunks,
    get_file_size,
    iter_lines_in_range,
    process_chunk,
)
from log_analyzer.stats import LogStats, merge_all


def write_raw(path: Path, payload: bytes) -> Path:
    """Tulis byte mentah ke file lalu kembalikan path-nya."""
    path.write_bytes(payload)
    return path


@pytest.mark.parametrize("num_chunks", list(range(1, 17)))
def test_gabungan_chunk_sama_dengan_seluruh_baris(num_chunks: int, tmp_path: Path) -> None:
    """Berapapun jumlah chunk, hasil gabungan selalu identik dengan file utuh."""
    lines = [f'2026-10-02T0{hour % 10}:00:00.000 [INFO] 1.2.3.4 u{index} "GET /p{index}" 200 {index + 1} {index + 2}ms'
             for index, hour in enumerate(range(200))]
    payload = "\n".join(lines) + "\n"
    path = write_raw(tmp_path / "a.log", payload.encode("utf-8"))

    size = get_file_size(path)
    collected: list[str] = []
    for start, end in compute_chunks(size, num_chunks):
        collected.extend(iter_lines_in_range(path, start, end))

    assert collected == lines


@pytest.mark.parametrize("num_chunks", [1, 2, 3, 8, 16])
def test_stats_dari_chunk_sama_dengan_sequential(num_chunks: int, tmp_path: Path) -> None:
    """Merge LogStats per chunk == LogStats satu rentang penuh."""
    lines = [
        f'2026-10-02T1{index % 9}:00:00.123 [ERROR] 10.0.0.{index % 50} u{index} "GET /x" 500 {index + 1} {index + 3}ms'
        for index in range(300)
    ]
    path = write_raw(tmp_path / "b.log", ("\n".join(lines) + "\n").encode("utf-8"))
    size = get_file_size(path)

    whole = process_chunk((str(path), 0, size))
    parts = [process_chunk((str(path), start, end)) for start, end in compute_chunks(size, num_chunks)]
    assert merge_all(parts) == whole


def test_file_kosong(tmp_path: Path) -> None:
    """File kosong menghasilkan nol baris untuk jumlah chunk berapa pun."""
    path = write_raw(tmp_path / "empty.log", b"")
    assert compute_chunks(get_file_size(path), 4) == [(0, 0), (0, 0), (0, 0), (0, 0)]
    for num_chunks in (1, 4, 12):
        lines: list[str] = []
        for start, end in compute_chunks(get_file_size(path), num_chunks):
            lines.extend(iter_lines_in_range(path, start, end))
        assert lines == []


def test_satu_baris(tmp_path: Path) -> None:
    """File satu baris tetap terbaca sekali meski dipecah banyak chunk."""
    path = write_raw(tmp_path / "one.log", b"hello world\n")
    size = get_file_size(path)
    for num_chunks in (1, 2, 5):
        lines = []
        for start, end in compute_chunks(size, num_chunks):
            lines.extend(iter_lines_in_range(path, start, end))
        assert lines == ["hello world"]


def test_tanpa_newline_di_akhir(tmp_path: Path) -> None:
    """Baris terakhir tanpa newline tetap dimiliki tepat satu chunk."""
    payload = b"alpha\nbravo\ncharlie"
    path = write_raw(tmp_path / "nonl.log", payload)
    size = get_file_size(path)
    for num_chunks in (1, 2, 3, 7):
        lines = []
        for start, end in compute_chunks(size, num_chunks):
            lines.extend(iter_lines_in_range(path, start, end))
        assert lines == ["alpha", "bravo", "charlie"]


def test_chunk_lebih_byanyak_dari_baris(tmp_path: Path) -> None:
    """Chunk tanpa baris menghasilkan LogStats kosong (identitas merge)."""
    path = write_raw(tmp_path / "few.log", b"a\nb\n")
    size = get_file_size(path)
    parts = [process_chunk((str(path), start, end)) for start, end in compute_chunks(size, 64)]
    assert sum(1 for part in parts if part.total_lines == 0) > 0
    merged = merge_all(parts)
    assert merged.total_lines == 2
    assert merged.malformed_lines == 2


def test_baris_panjang_melintasi_batas_chunk(tmp_path: Path) -> None:
    """Baris panjang yang melintasi batas byte tidak terpotong atau ganda."""
    long_line = "x" * 50_000
    payload = f"short1\n{long_line}\nshort2\n".encode("utf-8")
    path = write_raw(tmp_path / "long.log", payload)
    size = get_file_size(path)
    for num_chunks in (2, 3, 5, 11):
        lines = []
        for start, end in compute_chunks(size, num_chunks):
            lines.extend(iter_lines_in_range(path, start, end))
        assert lines == ["short1", long_line, "short2"]


def test_compute_chunks_menutupi_seluruh_file() -> None:
    """Rentang chunk berurutan, saling lepas, dan menutupi [0, size)."""
    for size in (1, 7, 100, 999_999):
        for num_chunks in (1, 2, 3, 8, 16):
            chunks = compute_chunks(size, num_chunks)
            assert len(chunks) == num_chunks
            assert chunks[0][0] == 0
            assert chunks[-1][1] == size
            for (start, end), (next_start, _next_end) in zip(chunks, chunks[1:]):
                assert end == next_start
                assert end >= start


def test_compute_chunks_validasi() -> None:
    """Ukuran negatif atau jumlah chunk nol ditolak."""
    with pytest.raises(ValueError):
        compute_chunks(-1, 4)
    with pytest.raises(ValueError):
        compute_chunks(100, 0)


def test_decode_byte_rusak_tidak_crash(tmp_path: Path) -> None:
    """Byte tidak valid didecode dengan errors=replace."""
    path = write_raw(tmp_path / "bin.log", b"ok line\n\xff\xfe junk\n")
    size = get_file_size(path)
    lines = list(iter_lines_in_range(path, 0, size))
    assert len(lines) == 2
    assert "\ufffd" in lines[1]


def test_process_chunk_menghitung_malformed(tmp_path: Path) -> None:
    """Worker mengembalikan agregat kecil yang picklable."""
    payload = (
        '2026-10-02T05:00:00.000 [INFO] 1.1.1.1 u "GET /a" 200 10 5ms\n'
        "rusak\n"
    ).encode("utf-8")
    path = write_raw(tmp_path / "c.log", payload)
    stats = process_chunk((str(path), 0, os.path.getsize(path)))
    assert isinstance(stats, LogStats)
    assert stats.total_lines == 2
    assert stats.malformed_lines == 1
    assert stats.hourly_counts == {5: 1}


def test_iter_range_rentang_kosong(tmp_path: Path) -> None:
    """Rentang kosong tidak menghasilkan baris."""
    path = write_raw(tmp_path / "d.log", b"a\nb\n")
    assert list(iter_lines_in_range(path, 2, 2)) == []
    assert list(iter_lines_in_range(path, 3, 1)) == []
