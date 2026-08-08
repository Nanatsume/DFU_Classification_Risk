"""Unit tests for auth.py's pure logic (hashing, session validity) against an isolated DB.
API-level login/logout/session behavior is covered in test_api.py."""
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture()
def authmod(tmp_db, monkeypatch):
    import auth
    monkeypatch.setattr(auth, "db", tmp_db)  # auth.py does `import db` — point it at the same isolated db
    return auth


def test_hash_verify_round_trip(authmod):
    h = authmod._hash("correct horse battery staple")
    assert authmod._verify("correct horse battery staple", h) is True


def test_verify_rejects_wrong_password(authmod):
    h = authmod._hash("right-password")
    assert authmod._verify("wrong-password", h) is False


def test_hash_uses_a_random_salt_each_time(authmod):
    h1 = authmod._hash("same-password")
    h2 = authmod._hash("same-password")
    assert h1 != h2  # different salt -> different stored string
    assert authmod._verify("same-password", h1) is True
    assert authmod._verify("same-password", h2) is True


def test_verify_rejects_garbage_stored_value(authmod):
    assert authmod._verify("anything", "not-a-valid-hash-string") is False
    assert authmod._verify("anything", "") is False


def test_bootstrap_password_from_env_var(authmod, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "my-team-password")
    authmod.bootstrap_password()
    stored = authmod.db.get_setting("password_hash")
    assert stored is not None
    assert authmod._verify("my-team-password", stored) is True


def test_bootstrap_password_env_var_overwrites_existing(authmod, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "first-password")
    authmod.bootstrap_password()
    monkeypatch.setenv("APP_PASSWORD", "second-password")
    authmod.bootstrap_password()
    stored = authmod.db.get_setting("password_hash")
    assert authmod._verify("second-password", stored) is True
    assert authmod._verify("first-password", stored) is False


def test_bootstrap_password_generates_once_when_no_env_and_no_existing(authmod, monkeypatch, capsys):
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert authmod.db.get_setting("password_hash") is None
    authmod.bootstrap_password()
    first_hash = authmod.db.get_setting("password_hash")
    assert first_hash is not None
    out = capsys.readouterr().out
    assert "Generated a one-time team password" in out

    # calling it again with still no env var must NOT regenerate / print again — a restart
    # shouldn't silently invalidate the password everyone was just given.
    authmod.bootstrap_password()
    assert authmod.db.get_setting("password_hash") == first_hash


def test_session_valid_true_for_fresh_session(authmod):
    token, _ = authmod._new_session()
    assert authmod._session_valid(token) is True


def test_session_valid_false_for_unknown_token(authmod):
    assert authmod._session_valid("token-that-was-never-issued") is False


def test_session_valid_false_for_none(authmod):
    assert authmod._session_valid(None) is False


def test_session_valid_false_and_purged_once_expired(authmod):
    expired = (authmod._now() - timedelta(hours=1)).isoformat()
    authmod.db.create_session("expired-token", expired)
    assert authmod._session_valid("expired-token") is False
    # _session_valid() deletes an expired session as a side effect once it notices
    assert authmod.db.get_session("expired-token") is None
