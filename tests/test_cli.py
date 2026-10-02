"""Uji end-to-end CLI: banner identitas, output analisis, dan exit code."""

from __future__ import annotations

from pathlib import Path

import pytest

from log_analyzer import cli

LOG_TEXT = (
    '2026-10-02T10:15:32.123 [ERROR] 192.168.1.10 user_042 "GET /api/orders/123" 500 1234 87ms\n'
    '2026-10-02T11:15:32.123 [INFO] 192.168.1.11 user_043 "POST /login" 200 234 17ms\n'
    "baris tidak sesuai format\n"
)


@pytest.fixture()
def sample_log(tmp_path: Path) -> Path:
    """Tulis file log kecil untuk keperluan uji CLI."""
    path = tmp_path / "sample.log"
    path.write_text(LOG_TEXT, encoding="utf-8")
    return path


def test_generate_membuat_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Subcommand generate menulis file dan mencetak banner identitas."""
    output = tmp_path / "nested" / "gen.log"
    exit_code = cli.main(["generate", "--lines", "500", "--output", str(output), "--seed", "42"])
    assert exit_code == 0
    assert output.exists()
    assert len(output.read_text(encoding="utf-8").splitlines()) == 500
    captured = capsys.readouterr().out
    assert "ZHEKA BAILA ARKAN" in captured.upper() or "Zheka Baila Arkan" in captured
    assert "247006111152" in captured


@pytest.mark.parametrize("mode", ["sequential", "threads", "processes"])
def test_analyze_setiap_mode(
    sample_log: Path, capsys: pytest.CaptureFixture[str], mode: str
) -> None:
    """Tiap mode mencetak identitas, jumlah worker, dan waktu total."""
    exit_code = cli.main(["analyze", "--input", str(sample_log), "--mode", mode, "--workers", "2"])
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "ZHEKA BAILA ARKAN" in captured
    assert "247006111152" in captured
    assert "PARALLEL LOG FILE ANALYZER" in captured
    assert "Jumlah thread" in captured or "Jumlah proses" in captured
    assert "Waktu total" in captured
    assert "Throughput" in captured
    assert "2" in captured


def test_analyze_malformed_terhitung(sample_log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Baris rusak dihitung dan ringkasan statistik tampil."""
    cli.main(["analyze", "--input", str(sample_log), "--mode", "sequential"])
    captured = capsys.readouterr().out
    assert "Baris malformed  : 1" in captured
    assert "Top-5" in captured
    assert "192.168.1.10" in captured


def test_compare_menampilkan_speedup(sample_log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Compare menjalankan tiga mode dan melaporkan speedup/efisiensi."""
    exit_code = cli.main(
        ["compare", "--input", str(sample_log), "--threads", "2", "--processes", "2"]
    )
    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "Validasi ekuivalensi" in captured
    assert "IDENTIK (lulus)" in captured
    assert "Speedup" in captured
    assert "Efisiensi" in captured


def test_argumen_tidak_valid_exit_non_zero(tmp_path: Path) -> None:
    """Argumen tidak valid menghasilkan SystemExit dengan kode bukan nol."""
    with pytest.raises(SystemExit) as missing_mode:
        cli.main(["analyze", "--input", "x.log", "--mode", "quantum"])
    assert missing_mode.value.code != 0

    with pytest.raises(SystemExit) as bad_workers:
        cli.main(["analyze", "--input", "x.log", "--mode", "threads", "--workers", "0"])
    assert bad_workers.value.code != 0

    with pytest.raises(SystemExit) as bad_lines:
        cli.main(["generate", "--lines", "-5", "--output", str(tmp_path / "z.log")])
    assert bad_lines.value.code != 0

    with pytest.raises(SystemExit) as no_command:
        cli.main([])
    assert no_command.value.code != 0


def test_file_tidak_ditemukan_exit_non_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """File input yang tidak ada dilaporkan sebagai error dengan kode 1."""
    exit_code = cli.main(["analyze", "--input", str(tmp_path / "tiada.log")])
    assert exit_code == 1
    assert "ERROR" in capsys.readouterr().err


def test_directory_sebagai_input_ditolak(tmp_path: Path) -> None:
    """Menunjuk direktori alih-alih file ditolak."""
    assert cli.main(["analyze", "--input", str(tmp_path)]) == 1


def test_main_menangkap_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, sample_log: Path
) -> None:
    """Interupsi pengguna menghasilkan kode 130."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "_run", explode)
    assert cli.main(["analyze", "--input", str(sample_log)]) == 130


def test_main_menangkap_value_error(
    monkeypatch: pytest.MonkeyPatch, sample_log: Path
) -> None:
    """Kesalahan nilai tidak valid dikembalikan sebagai kode 1."""

    def explode(*_args: object, **_kwargs: object) -> object:
        raise ValueError("pecah")

    monkeypatch.setattr(cli, "_run", explode)
    assert cli.main(["analyze", "--input", str(sample_log)]) == 1
