"""Shared-password login for capture_app — one team password, not per-nurse accounts.

This was originally justified by the CRF form carrying its own nurse/nurse2 fields, so a session
only needed to prove "an authenticated person" rather than "which person". Those fields are gone:
the study site asked that staff names not be stored at all. Nothing in this app now records who
examined a patient or took a photograph, and the shared login is no longer a trade-off against
per-record attribution — there is simply no attribution anywhere. That is the site's decision to
make, but anyone adding an audit or data-quality requirement later should start here.

This protects every data-bearing endpoint (require_session as a route dependency) but the static
HTML shell itself stays reachable pre-login the way StaticFiles(html=True) already serves it —
static/js/auth.js redirects client-side to login.html, and no API call succeeds without the
session cookie regardless. That's an acceptable trade for a server bound to 127.0.0.1 only.

IMPORTANT: if this server's --host is ever changed from 127.0.0.1 to 0.0.0.0 (e.g. to let a
second workstation reach it), revisit this — an unauthenticated page shell reachable from the
LAN is a different risk than one reachable only from the same machine.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

import db

TZ = timezone(timedelta(hours=7))  # Asia/Bangkok
SESSION_COOKIE = "capture_session"
SESSION_TTL_HOURS = 12
PBKDF2_ITERATIONS = 260_000

router = APIRouter(prefix="/api", tags=["auth"])


def _hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def _verify(password: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def bootstrap_password() -> None:
    """Call once at server startup. APP_PASSWORD env var always wins (restart with a new value to
    rotate the password) — if unset and no password has ever been set, generate a one-time random
    one and print it to the console. The plaintext is never persisted, only its hash."""
    env_pw = os.environ.get("APP_PASSWORD")
    if env_pw:
        db.set_setting("password_hash", _hash(env_pw))
        print("[auth] APP_PASSWORD set from environment - password updated.")
        return
    if db.get_setting("password_hash") is None:
        generated = secrets.token_urlsafe(12)
        db.set_setting("password_hash", _hash(generated))
        print("=" * 64)
        print("[auth] No APP_PASSWORD set. Generated a one-time team password:")
        print(f"       {generated}")
        print("       Set the APP_PASSWORD environment variable to choose your own.")
        print("=" * 64)


def _now() -> datetime:
    return datetime.now(TZ)


def _new_session() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = (_now() + timedelta(hours=SESSION_TTL_HOURS)).isoformat()
    db.create_session(token, expires_at)
    return token, expires_at


def _session_valid(token: Optional[str]) -> bool:
    if not token:
        return False
    row = db.get_session(token)
    if not row:
        return False
    try:
        expires_at = datetime.fromisoformat(row["expires_at"])
    except ValueError:
        return False
    if expires_at < _now():
        db.delete_session(token)
        return False
    return True


def require_session(request: Request) -> None:
    """FastAPI route dependency — raise 401 unless the request carries a valid session cookie."""
    if not _session_valid(request.cookies.get(SESSION_COOKIE)):
        raise HTTPException(401, "not authenticated")


class LoginReq(BaseModel):
    password: str


# ---- brute-force lockout ----
# In-memory, keyed by client IP — resets on server restart, which is fine here (a restart is
# also how the password itself gets rotated, e.g. before/after a temporary tunnel session). Not
# meant to replace a real rate limiter for a permanently internet-facing deployment, but a solid
# step up from the old bare time.sleep(1) for the "expose briefly via a tunnel" case.
_failed_attempts: dict[str, list[float]] = {}
LOCKOUT_MAX_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 300  # failures older than this stop counting toward a lockout


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _is_locked_out(key: str) -> bool:
    now = time.time()
    attempts = [t for t in _failed_attempts.get(key, []) if now - t < LOCKOUT_WINDOW_SECONDS]
    _failed_attempts[key] = attempts
    return len(attempts) >= LOCKOUT_MAX_ATTEMPTS


def _record_failure(key: str) -> None:
    _failed_attempts.setdefault(key, []).append(time.time())


@router.post("/login")
def login(req: LoginReq, request: Request, response: Response):
    key = _client_key(request)
    if _is_locked_out(key):
        raise HTTPException(429, f"too many failed attempts — try again in {LOCKOUT_WINDOW_SECONDS // 60} minutes")
    stored = db.get_setting("password_hash")
    if not stored or not _verify(req.password, stored):
        _record_failure(key)
        time.sleep(2)  # brute-force deterrent, on top of the lockout above
        raise HTTPException(401, "wrong password")
    _failed_attempts.pop(key, None)
    token, _ = _new_session()
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                         max_age=SESSION_TTL_HOURS * 3600)
    db.log_audit(None, "login")
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        db.delete_session(token)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/session")
def session_status(request: Request):
    return {"authenticated": _session_valid(request.cookies.get(SESSION_COOKIE))}
