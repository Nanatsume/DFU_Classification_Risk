"""Shared fixtures. The one thing every test here must get right: never touch the real
data/app.db or data/ folder — capture_app has no built-in "test mode", so isolation is done by
monkeypatching db.py's module-level DATA_DIR/DB_PATH (and server.py's own DATA_DIR/META_DIR,
which are separate constants pointing at the same folder by default) to a pytest tmp_path before
anything imports or touches them.
"""
from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Isolated SQLite DB for tests that only need db.py — no server/app import."""
    import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "app.db")
    db.init_db()
    return db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A FastAPI TestClient wired to a fresh, isolated DB + data folder per test.

    server.py runs db.init_db() / auth.bootstrap_password() at *module import time* (not in a
    startup event), so the DB path must be patched before server.py is (re)imported — patching
    after the fact would leave the already-created connections pointed at the old path.
    """
    import db

    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "app.db")
    monkeypatch.setenv("APP_PASSWORD", "test-password-123")
    # Point the demo folder at an empty directory so SimulatedSource falls back to the small
    # sample/P001.png. The committed rig captures are 1920x1080 and tripled the suite's runtime
    # the moment they existed — tests should exercise the path, not the megapixels.
    #
    # setattr, not setenv: capture_source reads DEMO_IMAGE_DIR once at import, and it is already
    # imported by the time this fixture runs (only `server` is re-imported below).
    import capture_source

    monkeypatch.setattr(capture_source, "DEMO_IMAGE_DIR", str(tmp_path / "no-demo-images"))
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")

    # server.py (and its `import db` inside) must be (re)imported now, against the patched path.
    sys.modules.pop("server", None)
    server = importlib.import_module("server")

    # Nothing else to redirect: server_paths resolves db.DATA_DIR on every call, so patching it
    # above covers the image and meta-json writes too, in this process and in the preprocessing
    # child (server hands it across as DFU_DATA_DIR). It was not always so — server.py and
    # server_paths each kept their own copy captured at import, the copies went stale when only
    # db's was patched, and the suite wrote patient image files into the live data/ directory
    # while the database went to tmp_path. One source, read late, is what stops that recurring.

    from fastapi.testclient import TestClient

    with TestClient(server.app) as c:
        yield c

    sys.modules.pop("server", None)  # don't leak the patched module into other test files


@pytest.fixture()
def auth_client(client):
    """Same as `client`, already logged in (cookie carried on the session)."""
    r = client.post("/api/login", json={"password": "test-password-123"})
    assert r.status_code == 200
    return client
