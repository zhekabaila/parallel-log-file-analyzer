"""Uji agregasi LogStats: merge, top-N, p95 histogram, pickle, dan kesetaraan."""

from __future__ import annotations

import copy
import pickle
import random

import pytest

from log_analyzer.config import RT_BUCKET_WIDTH_MS
from log_analyzer.parser import parse_line
from log_analyzer.stats import LogStats, merge_all, top_n

LINES = [
    '2026-10-02T10:15:32.123 [ERROR] 10.0.0.1 u1 "GET /a" 500 100 87ms',
    '2026-10-02T10:16:32.123 [INFO] 10.0.0.2 u2 "POST /b" 201 200 45ms',
    'baris rusak',
    '2026-10-02T23:00:00.000 [WARNING] 10.0.0.1 u1 "GET /a" 404 300 1500ms',
]


def build_stats(lines: list[str]) -> LogStats:
    """Bangun LogStats dari kumpulan baris string."""
    stats = LogStats()
    for line in lines:
        record = parse_line(line)
        if record is None:
            stats.add_malformed()
        else:
            stats.add_record(record)
    return stats


def test_add_record_dan_add_malformed() -> None:
    """Field agregat terisi sesuai baris yang dicatat."""
    stats = build_stats(LINES)
    assert stats.total_lines == 4
    assert stats.malformed_lines == 1
    assert stats.parsed_lines == 3
    assert stats.level_counts["ERROR"] == 1
    assert stats.status_counts[404] == 1
    assert stats.ip_counts["10.0.0.1"] == 2
    assert stats.hourly_counts[23] == 1
    assert stats.total_bytes == 600
    assert stats.total_response_ms == 87 + 45 + 1500
    assert stats.max_response_ms == 1500


def test_add_lines_helper() -> None:
    """Helper add_lines setara dengan loop manual."""
    manual = build_stats(LINES)
    helper = LogStats()
    helper.add_lines(LINES)
    assert helper == manual


def test_merge_komutatif() -> None:
    """A + B == B + A."""
    left = build_stats(LINES[:2])
    right = build_stats(LINES[2:])
    assert left.merge(right) == right.merge(left)


def test_merge_asosiatif() -> None:
    """(A + B) + C == A + (B + C)."""
    parts = [build_stats(chunk) for chunk in (LINES[:1], LINES[1:3], LINES[3:])]
    assert parts[0].merge(parts[1]).merge(parts[2]) == parts[0].merge(
        parts[1].merge(parts[2])
    )


def test_identity_elemen_kosong() -> None:
    """LogStats() kosong adalah elemen identitas merge."""
    stats = build_stats(LINES)
    empty = LogStats()
    assert stats.merge(empty) == stats
    assert empty.merge(stats) == stats
    assert merge_all([]) == empty
    assert merge_all([stats, empty, stats]) == stats.merge(stats)


def test_merge_tidak_mengubah_operand() -> None:
    """Merge tidak boleh memiliki efek samping pada input."""
    left = build_stats(LINES[:2])
    right = build_stats(LINES[2:])
    left_before = copy.deepcopy(left.to_dict())
    right_before = copy.deepcopy(right.to_dict())
    left.merge(right)
    assert left.to_dict() == left_before
    assert right.to_dict() == right_before


def test_merge_menolak_tipe_lain() -> None:
    """Merge dengan bukan-LogStats memunculkan TypeError."""
    with pytest.raises(TypeError):
        LogStats().merge({"total_lines": 1})  # type: ignore[arg-type]


def test_top_n_tie_break_deterministik() -> None:
    """Urutan: jumlah menurun, lalu key menaik."""
    counter = {"b": 5, "a": 5, "c": 9, "d": 1}
    assert top_n(counter, 3) == [("c", 9), ("a", 5), ("b", 5)]
    assert top_n(counter, 0) == []
    assert top_n({}, 5) == []
    assert top_n({3: 2, 10: 2}, 2) == [(3, 2), (10, 2)]


def test_p95_hasil_merge_sama_dengan_hitung_langsung() -> None:
    """p95 berbasis histogram identik setelah merge parsial."""
    rng = random.Random(42)
    lines: list[str] = []
    for _ in range(5_000):
        response_ms = rng.randint(5, 2000)
        lines.append(
            f'2026-10-02T10:15:32.123 [INFO] 10.0.0.1 u1 "GET /a" 200 100 {response_ms}ms'
        )
    whole = build_stats(lines)
    merged = merge_all([build_stats(lines[:1_700]), build_stats(lines[1_700:3_400]), build_stats(lines[3_400:])])
    assert merged == whole
    assert merged.p95_response_ms() == pytest.approx(whole.p95_response_ms())
    assert whole.p95_response_ms() > 0

    assert LogStats().p95_response_ms() == 0.0
    assert LogStats().average_response_ms() == 0.0
    assert LogStats().top_hour() is None


def test_histogram_pakai_bucket_bukan_list_jutaan() -> None:
    """Ukuran histogram dibatasi jumlah bucket, bukan jumlah record."""
    stats = build_stats(
        [f'2026-10-02T10:15:32.123 [INFO] 1.1.1.1 u "GET /a" 200 1 {value}ms' for value in (5, 2000)]
    )
    assert set(stats.rt_histogram) == {5 // RT_BUCKET_WIDTH_MS, 2000 // RT_BUCKET_WIDTH_MS}


def test_objek_dapat_di_pickle() -> None:
    """LogStats bertahan utuh setelah round-trip pickle."""
    stats = build_stats(LINES)
    restored = pickle.loads(pickle.dumps(stats))
    assert restored == stats
    assert pickle.loads(pickle.dumps((stats.merge(stats)))) == stats.merge(stats)


def test_eq_menolak_objek_lain() -> None:
    """Perbandingan dengan tipe lain mengembalikan False, bukan exception."""
    assert LogStats().__eq__(3) is NotImplemented
    assert (LogStats() == 3) is False
    assert "LogStats(" in repr(LogStats())


def test_average_dan_top_hour() -> None:
    """Rata-rata response time dan jam tersibuk dihitung benar."""
    stats = build_stats(LINES)
    assert stats.average_response_ms() == pytest.approx((87 + 45 + 1500) / 3)
    assert stats.top_hour() == 10
