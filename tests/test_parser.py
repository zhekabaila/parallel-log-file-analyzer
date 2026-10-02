"""Uji parser satu baris log."""

from __future__ import annotations

import pytest

from log_analyzer.parser import extract_hour, parse_line

VALID_LINE = (
    '2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042 '
    '"GET /api/orders/123" 500 1234 87ms'
)


def test_baris_valid_terparse_benar() -> None:
    """Setiap field terpetakan dengan tipe dan nilai yang benar."""
    record = parse_line(VALID_LINE)
    assert record is not None
    assert record["ts"] == "2026-10-02T10:15:32.123"
    assert record["level"] == "ERROR"
    assert record["ip"] == "192.168.1.10"
    assert record["user"] == "user_042"
    assert record["method"] == "GET"
    assert record["path"] == "/api/orders/123"
    assert record["status"] == 500
    assert record["bytes"] == 1234
    assert record["response_ms"] == 87
    assert record["hour"] == 10


def test_baris_valid_tanpa_newline_dan_dengan_newline() -> None:
    """Newline di ujung baris tidak memengaruhi hasil parse."""
    assert parse_line(VALID_LINE + "\n") == parse_line(VALID_LINE)
    assert parse_line(VALID_LINE + "\r\n") == parse_line(VALID_LINE)


@pytest.mark.parametrize(
    "line",
    [
        "",
        "   ",
        "\n",
        "2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042",
        '2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042 "GET /x" abc 1234 87ms',
        '2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042 "GET /x" 500 1234',
        '2026-10-02T10:15:32.123 [CRITICAL] 192.168.1.10 user_042 "GET /x" 500 1234 87ms',
        '2026-10-02T10:15:32.123 [INFO] 999.1.1 user_042 "GET /x" 200 1234 87ms',
        '2026-10-02T10:15:32.123 [INFO] 192.168.1.10 user_042 "get /x" 200 1234 87ms',
        '2026-10-02T10:15:32.123 [INFO] 192.168.1.10 user_042 "GET /x" 500 1234 87',
        "totally random text",
    ],
)
def test_baris_rusak_menghasilkan_None(line: str) -> None:
    """Baris malformed dikembalikan sebagai None, tanpa exception."""
    assert parse_line(line) is None


def test_unicode_aneh_tidak_membuat_crash() -> None:
    """Karakter unicode/byte rusak ditangani dengan rapi."""
    for line in [
        "2026-10-02T10:15:32.123 [INFO] 1.1.1.1 \u00e9\u4e2d\u6587 \"GET /x\" 200 1 2ms",
        "\udcff\udffe binary junk",
        "\u0000\u0001",
        "\U0001f600 " * 50,
    ]:
        assert parse_line(line) is None or isinstance(parse_line(line), dict)


def test_extract_hour() -> None:
    """Ekstraksi jam benar dan menolak timestamp tak valid."""
    assert extract_hour("2026-10-02T23:59:59.999") == 23
    assert extract_hour("2026-10-02T00:00:00.000") == 0
    assert extract_hour("2026-10-02 10:15:32") is None
    assert extract_hour("pendek") is None
    assert extract_hour("2026-10-02T99:15:32.123") is None


def test_status_di_luar_rentang_ditolak() -> None:
    """Status 600 dan 099 tidak diterima meski cocok secara regex."""
    from log_analyzer.parser import _STATUS_MAX

    assert _STATUS_MAX == 599
    line = '2026-10-02T10:15:32.123 [INFO] 1.1.1.1 u "GET /x" 600 1 2ms'
    assert parse_line(line) is None
