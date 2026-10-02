"""Parsing satu baris log menjadi record terstruktur."""

from __future__ import annotations

from typing import Any

from log_analyzer.config import LOG_LINE_PATTERN, VALID_LEVELS

_HOUR_START = 11
_HOUR_END = 13
_STATUS_MIN = 100
_STATUS_MAX = 599


def extract_hour(timestamp: str) -> int | None:
    """Ambil jam dari timestamp ISO ``YYYY-MM-DDTHH:MM:SS.mmm``.

    Parameter:
        timestamp: string timestamp pada field pertama baris log.

    Return:
        Angka jam 0-23, atau ``None`` bila format timestamp tidak valid.
    """
    if len(timestamp) < _HOUR_END or timestamp[10] != "T":
        return None
    raw_hour = timestamp[_HOUR_START:_HOUR_END]
    if not raw_hour.isdigit():
        return None
    hour = int(raw_hour)
    if hour > 23:
        return None
    return hour


def _ip_is_valid(ip: str) -> bool:
    """Cek tiap oktet IP berada di rentang 0-255.

    Regex acuan hanya memastikan pola digit, sehingga nilai seperti 999 masih
    cocok; validasi ini diperlukan agar IP tidak masuk akal dihitung malformed.
    """
    return all(0 <= int(octet) <= 255 for octet in ip.split("."))


def parse_line(line: str) -> dict[str, Any] | None:
    """Ubah satu baris log menjadi dict record.

    Parameter:
        line: satu baris log, boleh masih membawa ``\\n`` di ujung.

    Return:
        Dict berisi kunci ``ts, level, ip, user, method, path, status, bytes,
        response_ms, hour``; atau ``None`` bila baris tidak sesuai format.
        Fungsi ini tidak pernah melempar exception.
    """
    stripped = line.rstrip("\n").rstrip("\r")
    if not stripped:
        return None

    match = LOG_LINE_PATTERN.match(stripped)
    if match is None:
        return None

    level = match.group("level")
    if level not in VALID_LEVELS:
        return None

    ip = match.group("ip")
    if not _ip_is_valid(ip):
        return None

    status = int(match.group("status"))
    if not _STATUS_MIN <= status <= _STATUS_MAX:
        return None

    size_bytes = int(match.group("bytes"))
    response_ms = int(match.group("rt"))
    if size_bytes < 0 or response_ms < 0:
        return None

    hour = extract_hour(match.group("ts"))
    if hour is None:
        return None

    return {
        "ts": match.group("ts"),
        "level": level,
        "ip": ip,
        "user": match.group("user"),
        "method": match.group("method"),
        "path": match.group("path"),
        "status": status,
        "bytes": size_bytes,
        "response_ms": response_ms,
        "hour": hour,
    }
