"""Pendekatan 1: analisis sequential sebagai baseline pengukuran."""

from __future__ import annotations

from pathlib import Path

from log_analyzer.chunking import consume_line
from log_analyzer.config import LOG_ENCODING
from log_analyzer.stats import LogStats


def analyze_sequential(path: Path | str) -> LogStats:
    """Analisis seluruh file dalam satu loop tunggal.

    File dibaca streaming dalam mode biner baris demi baris sehingga memori yang
    terpakai tetap kecil meski file berisi jutaan baris. Pemecahan baris memakai
    ``\\n`` saja, sama persis dengan worker byte-range, sehingga hasil sequential
    dan paralel dapat dibandingkan secara adil.

    Parameter:
        path: lokasi file log.

    Return:
        LogStats agregat seluruh file.
    """
    stats = LogStats()
    with open(path, "rb") as handle:
        for raw_line in handle:
            line = raw_line.decode(LOG_ENCODING, errors="replace")
            consume_line(stats, line)
    return stats
