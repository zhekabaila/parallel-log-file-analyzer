"""Agregasi statistik log yang dapat di-merge (pola map-reduce).

Semua field bersifat aditif atau berbasis counter, sehingga ``merge`` bersifat
asosiatif dan komutatif. Respons time tidak disimpan sebagai list jutaan nilai,
melainkan sebagai histogram bucket agar objek tetap kecil, picklable, dan aman
dikirim antar proses.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any

from log_analyzer.config import P95_PERCENTILE, RT_BUCKET_WIDTH_MS

COUNTER_NAMES: tuple[str, ...] = (
    "level_counts",
    "status_counts",
    "method_counts",
    "ip_counts",
    "user_counts",
    "path_counts",
    "hourly_counts",
)


class LogStats:
    """Kumpulan agregat hasil analisis satu atau lebih baris log."""

    def __init__(self) -> None:
        """Inisialisasi agregat kosong (elemen identitas operasi merge)."""
        self.total_lines = 0
        self.malformed_lines = 0
        self.level_counts: dict[str, int] = {}
        self.status_counts: dict[int, int] = {}
        self.method_counts: dict[str, int] = {}
        self.ip_counts: dict[str, int] = {}
        self.user_counts: dict[str, int] = {}
        self.path_counts: dict[str, int] = {}
        self.hourly_counts: dict[int, int] = {}
        self.total_bytes = 0
        self.total_response_ms = 0
        self.max_response_ms = 0
        self.parsed_lines = 0
        self.rt_histogram: dict[int, int] = {}

    def _bump(self, counter: dict[Any, int], key: Any) -> None:
        """Naikkan counter satu key sebanyak satu."""
        counter[key] = counter.get(key, 0) + 1

    def add_record(self, record: Mapping[str, Any]) -> None:
        """Catat satu baris valid.

        Parameter:
            record: dict hasil ``parser.parse_line``.
        """
        self.total_lines += 1
        self.parsed_lines += 1
        self._bump(self.level_counts, record["level"])
        self._bump(self.status_counts, record["status"])
        self._bump(self.method_counts, record["method"])
        self._bump(self.ip_counts, record["ip"])
        self._bump(self.user_counts, record["user"])
        self._bump(self.path_counts, record["path"])
        self._bump(self.hourly_counts, record["hour"])
        self.total_bytes += record["bytes"]
        response_ms = record["response_ms"]
        self.total_response_ms += response_ms
        if response_ms > self.max_response_ms:
            self.max_response_ms = response_ms
        self._bump(self.rt_histogram, response_ms // RT_BUCKET_WIDTH_MS)

    def add_malformed(self) -> None:
        """Catat satu baris yang tidak sesuai format."""
        self.total_lines += 1
        self.malformed_lines += 1

    def add_lines(self, lines: Iterable[str]) -> None:
        """Catat kumpulan baris, memisahkan yang valid dan yang malformed.

        Parameter:
            lines: iterable string baris log (sudah didecode).
        """
        from log_analyzer.parser import parse_line

        for line in lines:
            record = parse_line(line)
            if record is None:
                self.add_malformed()
            else:
                self.add_record(record)

    def merge(self, other: "LogStats") -> "LogStats":
        """Kembalikan LogStats baru hasil gabungan ``self`` dan ``other``.

        Operasi ini asosiatif dan komutatif; ``LogStats()`` kosong adalah elemen
        identitas. Metode ini tidak mengubah kedua operand.
        """
        if not isinstance(other, LogStats):
            raise TypeError(f"merge menerima LogStats, bukan {type(other).__name__}")
        if other.total_lines == 0:
            return self.copy()

        result = self.copy()
        result.total_lines += other.total_lines
        result.malformed_lines += other.malformed_lines
        result.parsed_lines += other.parsed_lines
        result.total_bytes += other.total_bytes
        result.total_response_ms += other.total_response_ms
        if other.max_response_ms > result.max_response_ms:
            result.max_response_ms = other.max_response_ms
        for name in COUNTER_NAMES:
            target = getattr(result, name)
            for key, value in getattr(other, name).items():
                target[key] = target.get(key, 0) + value
        for bucket, value in other.rt_histogram.items():
            result.rt_histogram[bucket] = result.rt_histogram.get(bucket, 0) + value
        return result

    def copy(self) -> "LogStats":
        """Kembalikan salinan dangkal namun dengan dict counter terpisah."""
        clone = LogStats()
        clone.total_lines = self.total_lines
        clone.malformed_lines = self.malformed_lines
        clone.parsed_lines = self.parsed_lines
        clone.total_bytes = self.total_bytes
        clone.total_response_ms = self.total_response_ms
        clone.max_response_ms = self.max_response_ms
        for name in COUNTER_NAMES:
            setattr(clone, name, dict(getattr(self, name)))
        clone.rt_histogram = dict(self.rt_histogram)
        return clone

    def to_dict(self) -> dict[str, Any]:
        """Serialisasi seluruh agregat menjadi dict biasa (untuk perbandingan)."""
        payload: dict[str, Any] = {
            "total_lines": self.total_lines,
            "malformed_lines": self.malformed_lines,
            "parsed_lines": self.parsed_lines,
            "total_bytes": self.total_bytes,
            "total_response_ms": self.total_response_ms,
            "max_response_ms": self.max_response_ms,
        }
        for name in COUNTER_NAMES:
            counter: dict[Any, int] = getattr(self, name)
            payload[name] = {str(key): counter[key] for key in sorted(counter)}
        histogram = self.rt_histogram
        payload["rt_histogram"] = {
            str(bucket): histogram[bucket] for bucket in sorted(histogram)
        }
        return payload

    def __eq__(self, other: object) -> bool:
        """Bandingkan dua LogStats berdasarkan seluruh agregat."""
        if not isinstance(other, LogStats):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __hash__(self) -> int:
        """Hash berbasis jumlah baris; objek ini mutable sehingga hash lemah."""
        return hash((self.total_lines, self.malformed_lines, self.parsed_lines))

    def __repr__(self) -> str:
        """Representasi ringkas untuk debugging."""
        return (
            f"LogStats(total_lines={self.total_lines}, "
            f"malformed_lines={self.malformed_lines}, "
            f"distinct_ip={len(self.ip_counts)})"
        )

    def average_response_ms(self) -> float:
        """Rata-rata response time (ms) atas baris valid."""
        if self.parsed_lines == 0:
            return 0.0
        return self.total_response_ms / self.parsed_lines

    def p95_response_ms(self) -> float:
        """Perkiraan persentil-95 response time dari histogram bucket.

        Estimasi dilakukan dengan interpolasi linear di dalam bucket tempat
        peringkat 95% jatuh, sehingga hasil merge beberapa worker tetap sama
        dengan perhitungan histogram langsung atas seluruh data.
        """
        total = sum(self.rt_histogram.values())
        if total == 0:
            return 0.0
        target_rank = math.ceil(P95_PERCENTILE * total)
        cumulative = 0
        for bucket in sorted(self.rt_histogram):
            count = self.rt_histogram[bucket]
            if cumulative + count >= target_rank:
                lower = bucket * RT_BUCKET_WIDTH_MS
                position_in_bucket = target_rank - cumulative
                return float(
                    lower
                    + RT_BUCKET_WIDTH_MS * position_in_bucket / (count + 1)
                )
            cumulative += count
        return float(self.max_response_ms)

    def top_hour(self) -> int | None:
        """Jam dengan aktivitas terbanyak (tie-break: jam terkecil)."""
        if not self.hourly_counts:
            return None
        ranked = top_n(self.hourly_counts, 1)
        return int(ranked[0][0]) if ranked else None


def merge_all(stats_list: Iterable[LogStats]) -> LogStats:
    """Gabungkan kumpulan LogStats menjadi satu agregat.

    Parameter:
        stats_list: iterable LogStats (boleh kosong).

    Return:
        LogStats gabungan; bila input kosong menghasilkan agregat nol.
    """
    result = LogStats()
    for stats in stats_list:
        result = result.merge(stats)
    return result


def top_n(counter: Mapping[Any, int], n: int) -> list[tuple[Any, int]]:
    """Ambil n entri teratas dengan tie-break deterministik.

    Urutan: hitungan menurun, kemudian key menaik.

    Parameter:
        counter: pemetaan key ke jumlah.
        n: banyaknya entri yang diminta (<= 0 menghasilkan list kosong).

    Return:
        List tuple ``(key, jumlah)``.
    """
    if n <= 0:
        return []

    def order_key(item: tuple[Any, int]) -> tuple[int, Any]:
        """Angka diurutkan numerik, key lain berdasarkan string; hitungan menurun."""
        key, count = item
        if isinstance(key, bool):
            return (-count, 1, str(key))
        if isinstance(key, (int, float)):
            return (-count, 0, key)
        return (-count, 1, str(key))

    items = sorted(counter.items(), key=order_key)
    return items[:n]
