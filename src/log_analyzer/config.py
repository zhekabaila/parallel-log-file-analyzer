"""Konfigurasi pusat proyek Parallel Log File Analyzer.

Seluruh konstanta identitas, format log, dan nilai default dikumpulkan di sini
agar tidak ada string yang di-hardcode berulang di modul lain.
"""

from __future__ import annotations

import re

APP_NAME = "PARALLEL LOG FILE ANALYZER"
AUTHOR_NAME = "ZHEKA BAILA ARKAN"
AUTHOR_NIM = "247006111152"
BANNER_WIDTH = 54

IDENTITY_TEXT = f"{APP_NAME}\nBy {AUTHOR_NAME} ({AUTHOR_NIM})"

VALID_LEVELS: frozenset[str] = frozenset({"INFO", "DEBUG", "WARNING", "ERROR"})

MODES: tuple[str, ...] = ("sequential", "threads", "processes")

LOG_LINE_PATTERN: re.Pattern[str] = re.compile(
    r'^(?P<ts>\S+) \[(?P<level>[A-Z]+)\] '
    r'(?P<ip>\d{1,3}(?:\.\d{1,3}){3}) '
    r'(?P<user>\S+) '
    r'"(?P<method>[A-Z]+) (?P<path>\S+)" '
    r'(?P<status>\d{3}) (?P<bytes>\d+) (?P<rt>\d+)ms$'
)

DEFAULT_SEED = 42
DEFAULT_MALFORMED_RATIO = 0.005
DEFAULT_TOP_N = 5
DEFAULT_NUM_WORKERS = 4
MAX_ALLOWED_WORKERS = 256

GENERATOR_BATCH_SIZE = 10_000
GENERATOR_PROGRESS_STEP_PCT = 25

RT_BUCKET_WIDTH_MS = 25
P95_PERCENTILE = 0.95

LOG_ENCODING = "utf-8"
