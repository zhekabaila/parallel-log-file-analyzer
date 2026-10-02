"""Uji generator log dummy: jumlah baris, determinisme, dan rasio malformed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from log_analyzer.config import LOG_LINE_PATTERN
from log_analyzer.generator import generate_log_file


def _read_lines(path: Path) -> list[str]:
    """Baca seluruh baris file sebagai list string."""
    return path.read_text(encoding="utf-8").splitlines()


@pytest.mark.parametrize("num_lines", [0, 1, 1_000, 20_000])
def test_jumlah_baris_persis(tmp_path: Path, num_lines: int) -> None:
    """Generator menulis tepat sejumlah baris yang diminta."""
    path = generate_log_file(tmp_path / f"n{num_lines}.log", num_lines, seed=42)
    assert len(_read_lines(path)) == num_lines


def test_seed_sama_menghasilkan_file_identik(tmp_path: Path) -> None:
    """Seed dan jumlah baris sama => isi file byte-identical."""
    first = generate_log_file(tmp_path / "a.log", 1_000, seed=42)
    second = generate_log_file(tmp_path / "b.log", 1_000, seed=42)
    assert first.read_bytes() == second.read_bytes()


def test_seed_beda_menghasilkan_isi_beda(tmp_path: Path) -> None:
    """Seed berbeda => isi file berbeda."""
    first = generate_log_file(tmp_path / "a.log", 1_000, seed=42)
    second = generate_log_file(tmp_path / "b.log", 1_000, seed=99)
    assert first.read_bytes() != second.read_bytes()


def test_rasio_malformed_mendekati_target(tmp_path: Path) -> None:
    """Proporsi baris rusak mendekati rasio yang diminta."""
    path = generate_log_file(tmp_path / "ratio.log", 20_000, seed=42, malformed_ratio=0.005)
    lines = _read_lines(path)
    malformed = [line for line in lines if LOG_LINE_PATTERN.match(line) is None]
    ratio = len(malformed) / len(lines)
    assert 0.003 <= ratio <= 0.008


def test_baris_valid_lolos_regex_acuan(tmp_path: Path) -> None:
    """Seluruh baris yang bukan rusak harus cocok dengan regex acuan."""
    path = generate_log_file(tmp_path / "valid.log", 2_000, seed=42)
    valid_count = sum(1 for line in _read_lines(path) if LOG_LINE_PATTERN.match(line))
    assert valid_count > 1_900


def test_regex_acuan_mencocokan_contoh_di_spec() -> None:
    """Regex mem-parse baris contoh pada spesifikasi tugas."""
    sample = (
        '2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042 '
        '"GET /api/orders/123" 500 1234 87ms'
    )
    match = LOG_LINE_PATTERN.match(sample)
    assert match is not None
    assert match.group("level") == "ERROR"
    assert match.group("status") == "500"


def test_folder_induk_dibuat_otomatis(tmp_path: Path) -> None:
    """Generator membuat direktorioutput yang belum ada."""
    target = tmp_path / "dalam" / "lebih_dalam" / "log.txt"
    path = generate_log_file(target, 10, seed=1)
    assert path.exists()


def test_argumen_negatif_ditolak(tmp_path: Path) -> None:
    """Jumlah baris negatif dan rasio di luar rentang ditolak."""
    with pytest.raises(ValueError):
        generate_log_file(tmp_path / "bad.log", -1)
    with pytest.raises(ValueError):
        generate_log_file(tmp_path / "bad2.log", 10, malformed_ratio=1.5)


def test_timestamp_naik_monotonik(tmp_path: Path) -> None:
    """Timestamp pada baris VALID selalu menaik."""
    from log_analyzer.parser import parse_line

    path = generate_log_file(tmp_path / "ts.log", 2_000, seed=42)
    stamps = []
    for line in _read_lines(path):
        record = parse_line(line)
        if record is not None:
            stamps.append(record["ts"])
    assert stamps == sorted(stamps)
    assert len(stamps) > 1_900
