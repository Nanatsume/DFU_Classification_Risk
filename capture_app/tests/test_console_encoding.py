"""The app must start and capture on a Thai-locale Windows console (code page cp874).

This is a subprocess test on purpose. Every other test in this suite runs under pytest's output
capture, which swaps sys.stdout for a UTF-8-capable buffer — that is exactly why the whole suite
stayed green while the app could not boot on the target machine at all. Only a real child process
with a real cp874 stdout reproduces it.

The bug it guards: preprocessing.py is exported from the research notebook and prints ✓ ÷ ├ 📂.
Line 33 runs at import time, so `import server` raised UnicodeEncodeError and uvicorn never
bound a port; preprocess_foot_image() prints three more, and server.py calls it on every
podoscope capture. See stdio_utf8.py.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent


def run_under(encoding: str, code: str, tmp_path: Path) -> subprocess.CompletedProcess:
    """Run `code` in a child process with a narrow stdout encoding and its own data directory.

    DFU_DATA_DIR is what keeps this honest. conftest.py isolates the rest of the suite by
    monkeypatching db.DATA_DIR, but a monkeypatch cannot reach into a subprocess: importing
    server there runs db.init_db() and auth.bootstrap_password() against whatever directory the
    module resolves on its own. Without this the APP_PASSWORD below was written straight into the
    real data/app.db, silently replacing the team's password with the test one on every run —
    which is exactly what happened, and how the nurse's login stopped working mid-session.
    """
    env = {
        **os.environ,
        "PYTHONIOENCODING": encoding,
        "APP_PASSWORD": "test-password-123",
        "DFU_DATA_DIR": str(tmp_path),
    }
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=APP_DIR, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )


def test_server_imports_on_a_thai_codepage_console(tmp_path):
    r = run_under("cp874", "import server", tmp_path)
    assert r.returncode == 0, f"`import server` failed under cp874:\n{r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr


def test_preprocessing_runs_on_a_thai_codepage_console(tmp_path):
    """The capture path, not just the boot path — this is the one that would have failed mid-clinic
    with a patient on the couch."""
    r = run_under("cp874", (
        "import server\n"
        "from preprocessing import preprocess_foot_image\n"
        "out = preprocess_foot_image('sample/P001.png')\n"
        "assert out['left_foot'] is not None and out['right_foot'] is not None\n"
        "print('OK')\n"
    ), tmp_path)
    assert r.returncode == 0, f"preprocessing failed under cp874:\n{r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr


@pytest.mark.parametrize("encoding", ["cp874", "cp1252", "ascii"])
def test_import_survives_any_narrow_console_encoding(encoding, tmp_path):
    """cp874 is the one that matters here, but the fix should not be specific to it."""
    r = run_under(encoding, "import server", tmp_path)
    assert r.returncode == 0, f"`import server` failed under {encoding}:\n{r.stderr}"


def test_subprocess_tests_never_touch_the_real_database(tmp_path):
    """Regression: these tests set APP_PASSWORD, and a subprocess cannot see conftest's
    monkeypatch of db.DATA_DIR. Before DFU_DATA_DIR was passed through, importing server in the
    child rewrote the real data/app.db — the team's shared password was silently replaced with
    the test one every time the suite ran, and the first anyone knew was a nurse unable to log in.

    Asserting on the real file rather than on the child's behaviour is deliberate: that is the
    thing that must not change, however the child is launched.
    """
    real_db = APP_DIR / "data" / "app.db"
    if not real_db.exists():
        pytest.skip("no real database on this machine — nothing to protect")

    import sqlite3

    def password_hash():
        conn = sqlite3.connect(str(real_db))
        try:
            row = conn.execute(
                "SELECT value FROM settings WHERE key='password_hash'").fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    before = password_hash()
    r = run_under("cp874", "import server", tmp_path)
    assert r.returncode == 0, r.stderr
    assert password_hash() == before, (
        "importing server in a subprocess rewrote the real database's password — "
        "DFU_DATA_DIR is not being passed through to the child"
    )
    # and the child really did create its own database rather than finding none at all
    assert (tmp_path / "app.db").exists()
