"""Generator file log dummy yang realistis dan dapat direproduksi.

Hasil generate bersifat byte-identical selama seed dan jumlah baris sama, karena
seluruh keacakan memakai satu instans ``random.Random(seed)`` dengan urutan
pemanggilan yang tetap.
"""

from __future__ import annotations

import random
import time
from datetime import datetime, timedelta
from pathlib import Path

from log_analyzer.config import (
    DEFAULT_MALFORMED_RATIO,
    DEFAULT_SEED,
    GENERATOR_BATCH_SIZE,
    GENERATOR_PROGRESS_STEP_PCT,
)

NUM_IPS = 500
NUM_USERS = 200
BASE_DATE = datetime(2026, 10, 2, 0, 0, 0)

LEVELS = ("INFO", "DEBUG", "WARNING", "ERROR")
LEVEL_WEIGHTS = (70.0, 10.0, 12.0, 8.0)

METHODS = ("GET", "POST", "PUT", "DELETE", "PATCH")
METHOD_WEIGHTS = (60.0, 25.0, 8.0, 5.0, 2.0)

STATUS_BY_LEVEL: dict[str, tuple[tuple[int, ...], tuple[float, ...]]] = {
    "ERROR": ((500, 502, 503, 504), (70.0, 12.0, 10.0, 8.0)),
    "WARNING": ((400, 404, 408, 429), (40.0, 35.0, 10.0, 15.0)),
    "INFO": ((200, 201, 204, 301, 304), (65.0, 12.0, 8.0, 8.0, 7.0)),
    "DEBUG": ((200, 204, 304), (70.0, 20.0, 10.0)),
}

PATH_TEMPLATE = (
    "/api/orders",
    "/api/users",
    "/api/products",
    "/api/search",
    "/api/cart",
    "/api/payments",
    "/api/reports",
    "/api/auth/token",
    "/api/orders/{id}",
    "/api/users/{id}",
    "/api/products/{id}",
    "/login",
    "/logout",
    "/register",
    "/health",
    "/metrics",
    "/static/app.js",
    "/static/app.css",
    "/static/logo.png",
    "/images/banner.jpg",
    "/documents/terms.pdf",
    "/admin/dashboard",
    "/admin/users",
    "/profile",
    "/settings",
    "/notifications",
    "/cart/checkout",
    "/search",
    "/v2/items",
    "/v2/items/{id}",
)
PATH_WEIGHTS = (
    8.0, 7.0, 6.0, 9.0, 4.0, 3.0, 3.0, 5.0, 10.0, 7.0, 6.0, 9.0, 3.0, 2.0, 4.0, 2.0,
    6.0, 5.0, 2.0, 3.0, 2.0, 2.0, 2.0, 4.0, 3.0, 5.0, 3.0, 8.0, 4.0, 3.0,
)

MALFORMED_TEMPLATES: tuple[str, ...] = (
    "",
    "this line is not a log record at all",
    "2026-10-02T08:00:00.000 [ERROR] 192.168.1.1 user_001 \"GET /login\" xyz 1234 20ms",
    "2026-10-02T08:00:00.000 [UNKNOWN] 10.0.0.5 user_002 \"GET /health\" 200 1234 20ms",
    "2026-10-02T08:00:00.000 [INFO] 999.1.1.1 user_003 \"GET /api/search\" 200 1234 20ms",
    "2026-10-02T08:00:00.000 [INFO] 172.16.0.9 user_004 \"GET /metrics\"",
    "2026-10-02T08:00:00.000 [WARNING] 172.16.0.9 user_005 \"GET /cart/checkout\" 404",
    "#:~ malformed utf8 \x00\x01 marker",
    "2026-10-02T08:00:00.000 [INFO] 172.16.0.9 user_006 GET /search 200 1234 20ms",
)


def build_pools(rng: random.Random) -> dict[str, object]:
    """Bangun pool IP, user, path, dan bobotnya sekali di awal.

    Parameter:
        rng: instans ``random.Random`` berseed tetap.

    Return:
        Dict berisi pool dan cumulative weights yang dipakai ``rng.choices``.
    """
    ips = [
        f"{rng.randint(11, 223)}.{rng.randint(0, 255)}."
        f"{rng.randint(0, 255)}.{rng.randint(1, 254)}"
        for _ in range(NUM_IPS)
    ]
    users = [f"user_{index:03d}" for index in range(NUM_USERS)]

    # Distribusi miring: sebagian IP/user sangat aktif, sisanya jarang.
    ip_weights = [rng.uniform(0.05, 1.0) ** 3 + 0.02 for _ in ips]
    user_weights = [rng.uniform(0.05, 1.0) ** 2.5 + 0.03 for _ in users]

    return {
        "ips": ips,
        "users": users,
        "paths": PATH_TEMPLATE,
        "ip_cum": _cumulative(ip_weights),
        "user_cum": _cumulative(user_weights),
        "path_cum": _cumulative(PATH_WEIGHTS),
        "level_cum": _cumulative(LEVEL_WEIGHTS),
        "method_cum": _cumulative(METHOD_WEIGHTS),
        "status_cum": {
            level: _cumulative(weights)
            for level, (_, weights) in STATUS_BY_LEVEL.items()
        },
    }


def _cumulative(weights: tuple[float, ...] | list[float]) -> list[float]:
    """Konversi bobot menjadi cumulative weights untuk ``random.choices``."""
    total = 0.0
    result: list[float] = []
    for weight in weights:
        total += weight
        result.append(total)
    return result


def format_timestamp(moment: datetime) -> str:
    """Format datetime menjadi ``YYYY-MM-DDTHH:MM:SS.mmm``."""
    return f"{moment:%Y-%m-%dT%H:%M:%S}.{moment.microsecond // 1000:03d}"


def _make_line(rng: random.Random, pools: dict[str, object], moment: datetime) -> str:
    """Susun satu baris log valid."""
    level = rng.choices(LEVELS, cum_weights=pools["level_cum"])[0]  # type: ignore[arg-type]
    method = rng.choices(METHODS, cum_weights=pools["method_cum"])[0]  # type: ignore[arg-type]
    status_choices, status_index = STATUS_BY_LEVEL[level]
    status = rng.choices(
        status_choices,
        cum_weights=pools["status_cum"][level],  # type: ignore[arg-type,index-var]
    )[0]
    ip = rng.choices(pools["ips"], cum_weights=pools["ip_cum"])[0]  # type: ignore[arg-type]
    user = rng.choices(pools["users"], cum_weights=pools["user_cum"])[0]  # type: ignore[arg-type]
    path_template = rng.choices(pools["paths"], cum_weights=pools["path_cum"])[0]  # type: ignore[arg-type]
    path = (
        path_template.replace("{id}", str(rng.randint(1, 20000)))
        if "{id}" in path_template
        else path_template
    )
    size_bytes = rng.randint(100, 50_000)
    response_ms = _skewed_response_ms(rng, level)
    return (
        f"{format_timestamp(moment)} [{level}] {ip} {user} "
        f'"{method} {path}" {status} {size_bytes} {response_ms}ms'
    )


def _skewed_response_ms(rng: random.Random, level: str) -> int:
    """Response time 5-2000 ms dengan ekor panjang; level ERROR lebih lambat."""
    roll = rng.random()
    if level == "ERROR":
        threshold_small, threshold_mid = 0.35, 0.75
    else:
        threshold_small, threshold_mid = 0.70, 0.92
    if roll < threshold_small:
        value = rng.randint(5, 120)
    elif roll < threshold_mid:
        value = rng.randint(121, 600)
    else:
        value = rng.randint(601, 2000)
    return max(5, min(2000, value))


def _make_malformed(rng: random.Random) -> str:
    """Pilih salah satu pola baris rusak secara acak."""
    return rng.choice(MALFORMED_TEMPLATES)


def generate_log_file(
    path: Path | str,
    num_lines: int,
    seed: int = DEFAULT_SEED,
    malformed_ratio: float = DEFAULT_MALFORMED_RATIO,
) -> Path:
    """Tulis file log dummy sebanyak persis ``num_lines`` baris.

    Parameter:
        path: tujuan file; folder induk dibuat otomatis bila belum ada.
        num_lines: jumlah baris total (termasuk baris malformed).
        seed: benih keacakan agar hasil dapat direproduksi.
        malformed_ratio: proporsi baris rusak yang disengaja (0.0 - 1.0).

    Return:
        ``Path`` file yang baru ditulis.

    Raise:
        ValueError: bila ``num_lines`` negatif atau rasio malformed di luar 0-1.
    """
    if num_lines < 0:
        raise ValueError("num_lines tidak boleh negatif")
    if not 0.0 <= malformed_ratio <= 1.0:
        raise ValueError("malformed_ratio harus berada di rentang 0.0 sampai 1.0")

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    pools = build_pools(rng)

    moment = BASE_DATE
    written = 0
    reported_pct = 0
    started_at = time.perf_counter()
    batch: list[str] = []

    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        while written < num_lines:
            moment += timedelta(milliseconds=rng.randint(1, 50))
            if rng.random() < malformed_ratio:
                batch.append(_make_malformed(rng))
            else:
                batch.append(_make_line(rng, pools, moment))
            written += 1

            if len(batch) >= GENERATOR_BATCH_SIZE or written == num_lines:
                handle.write("\n".join(batch))
                handle.write("\n")
                batch.clear()

            if num_lines > 0:
                pct = int(written * 100 / num_lines)
                if pct >= reported_pct + GENERATOR_PROGRESS_STEP_PCT:
                    reported_pct += GENERATOR_PROGRESS_STEP_PCT
                    print(f"  progress generate: {pct}% ({written}/{num_lines} baris)")

    elapsed = time.perf_counter() - started_at
    print(f"Selesai generate {num_lines} baris -> {target} dalam {elapsed:.2f} detik")
    return target
