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


def run_under(encoding: str, code: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONIOENCODING": encoding, "APP_PASSWORD": "test-password-123"}
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=APP_DIR, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )


def test_server_imports_on_a_thai_codepage_console():
    r = run_under("cp874", "import server")
    assert r.returncode == 0, f"`import server` failed under cp874:\n{r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr


def test_preprocessing_runs_on_a_thai_codepage_console():
    """The capture path, not just the boot path — this is the one that would have failed mid-clinic
    with a patient on the couch."""
    r = run_under("cp874", (
        "import server\n"
        "from preprocessing import preprocess_foot_image\n"
        "out = preprocess_foot_image('sample/P001.png')\n"
        "assert out['left_foot'] is not None and out['right_foot'] is not None\n"
        "print('OK')\n"
    ))
    assert r.returncode == 0, f"preprocessing failed under cp874:\n{r.stderr}"
    assert "UnicodeEncodeError" not in r.stderr


@pytest.mark.parametrize("encoding", ["cp874", "cp1252", "ascii"])
def test_import_survives_any_narrow_console_encoding(encoding):
    """cp874 is the one that matters here, but the fix should not be specific to it."""
    r = run_under(encoding, "import server")
    assert r.returncode == 0, f"`import server` failed under {encoding}:\n{r.stderr}"
