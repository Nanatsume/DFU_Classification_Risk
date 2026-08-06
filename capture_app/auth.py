"""Shared-password login for capture_app — one team password, not per-nurse accounts (decided
with the user: per-record attribution already lives in the CRF form's own nurse/nurse2 fields,
so a session only needs to prove "an authenticated person", not "which person").

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


@router.post("/login")
def login(req: LoginReq, response: Response):
    stored = db.get_setting("password_hash")
    if not stored or not _verify(req.password, stored):
        time.sleep(1)  # trivial brute-force deterrent — local-network threat model, not internet-facing
        raise HTTPException(401, "wrong password")
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
