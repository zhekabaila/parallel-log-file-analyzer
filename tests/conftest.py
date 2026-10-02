"""Fixture pytest: file log kecil yang dipakai banyak test."""

from __future__ import annotations

import pytest

from log_analyzer.generator import generate_log_file


@pytest.fixture(scope="session")
def log_2000(tmp_path_factory: pytest.TempPathFactory) -> object:
    """File log 2.000 baris (dibuat sekali per sesi test)."""
    path = tmp_path_factory.mktemp("logs") / "server_2k.log"
    return generate_log_file(path, 2_000, seed=42)


@pytest.fixture(scope="session")
def log_20000(tmp_path_factory: pytest.TempPathFactory) -> object:
    """File log 20.000 baris untuk uji ekuivalensi dan throughput."""
    path = tmp_path_factory.mktemp("logs") / "server_20k.log"
    return generate_log_file(path, 20_000, seed=7)
