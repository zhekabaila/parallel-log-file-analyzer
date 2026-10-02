"""Pembagian file log menjadi byte-range dan pemrosesan satu chunk.

Aturan kepemilikan baris: sebuah baris dimiliki oleh chunk tempat byte pertama
baris tersebut berada di rentang ``[start, end)``. Karena rentang antar chunk
saling lepas dan menutupi seluruh file, gabungan semua chunk menjamin tidak ada
baris yang duplikat maupun hilang, untuk jumlah chunk berapa pun.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from log_analyzer.config import LOG_ENCODING
from log_analyzer.stats import LogStats


def compute_chunks(file_size: int, num_chunks: int) -> list[tuple[int, int]]:
    """Bagi ukuran file menjadi ``num_chunks`` rentang byte ``[start, end)``.

    Parameter:
        file_size: ukuran file dalam byte (>= 0).
        num_chunks: banyaknya chunk (>= 1).

    Return:
        Daftar tuple ``(start, end)`` yang berurutan, saling lepas, dan
        menutupi tepat ``[0, file_size)``.

    Raise:
        ValueError: bila ``file_size`` negatif atau ``num_chunks`` < 1.
    """
    if file_size < 0:
        raise ValueError("file_size tidak boleh negatif")
    if num_chunks < 1:
        raise ValueError("num_chunks minimal 1")

    chunks: list[tuple[int, int]] = []
    for index in range(num_chunks):
        start = file_size * index // num_chunks
        end = file_size * (index + 1) // num_chunks
        chunks.append((start, end))
    return chunks


def iter_lines_in_range(path: Path | str, start: int, end: int) -> Iterator[str]:
    """Hasilkan baris milik rentang byte ``[start, end)``.

    File dibuka dalam mode biner lalu tiap baris didecode UTF-8 dengan
    ``errors="replace"`` supaya byte rusak tidak membuat crash.

    Parameter:
        path: lokasi file log.
        start: indeks byte pertama rentang (inklusif).
        end: indeks byte akhir rentang (eksklusif).

    Return:
        Iterator string baris tanpa newline penutup.
    """
    if end <= start:
        return

    with open(path, "rb") as handle:
        if start > 0:
            handle.seek(start - 1)
            handle.readline()

        while True:
            position = handle.tell()
            if position >= end:
                break
            raw_line = handle.readline()
            if not raw_line:
                break
            yield raw_line.decode(LOG_ENCODING, errors="replace").rstrip("\n").rstrip("\r")


def get_file_size(path: Path | str) -> int:
    """Kembalikan ukuran file dalam byte."""
    return os.path.getsize(path)


def process_chunk(args: tuple[str, int, int]) -> LogStats:
    """Langkah *map*: analisis satu byte-range menjadi LogStats lokal.

    Fungsi ini berada di level modul (top-level) agar dapat di-pickle oleh
    ``multiprocessing`` pada Windows yang memakai start method ``spawn``.

    Parameter:
        args: tuple ``(path, start, end)``; worker membaca sendiri bagiannya,
            sehingga yang dikirim antar proses hanyalah lintasan dan dua angka,
            bukan isi baris.

    Return:
        LogStats berisi agregat satu chunk saja.
    """
    path, start, end = args
    stats = LogStats()
    for line in iter_lines_in_range(path, start, end):
        consume_line(stats, line)
    return stats


def consume_line(stats: LogStats, line: str) -> None:
    """Parse satu baris dan catat ke ``stats`` (valid atau malformed)."""
    from log_analyzer.parser import parse_line

    record = parse_line(line)
    if record is None:
        stats.add_malformed()
    else:
        stats.add_record(record)
