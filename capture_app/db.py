"""SQLite data layer for capture_app — one authoritative database instead of the five flat-file
formats (data/crf/*.json, data/roi/*.json, data/meta/*.json, data/manifest.csv, data/crf_manifest.csv)
this replaces.

FastAPI runs sync route handlers in a thread pool, so even a single `uvicorn` process can have more
than one thread touching SQLite at once. Every call here opens its own connection
(check_same_thread=False, a busy_timeout, and WAL) rather than sharing one global connection — that
is what actually makes concurrent access safe, not a config option to skip.

Backup note: with WAL enabled, a consistent backup means copying `app.db` *and* the sidecar
`app.db-wal` / `app.db-shm` files (or running `PRAGMA wal_checkpoint(TRUNCATE)` first to fold the
WAL back into the main file) — copying app.db alone can miss recently committed rows.

research_id format is fixed at "P%04d" (e.g. P0001) throughout the app — next_research_id() below
must keep producing that exact shape.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterator, Optional

TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    research_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crf_forms (
    research_id    TEXT PRIMARY KEY REFERENCES cases(research_id),
    nurse          TEXT,
    nurse2         TEXT,
    saved_at       TEXT,
    fields_json    TEXT,
    derived_json   TEXT,
    schema_version TEXT
);

CREATE TABLE IF NOT EXISTS captures (
    research_id TEXT REFERENCES cases(research_id),
    modality    TEXT CHECK(modality IN ('podoscope','thermal')),
    raw_path    TEXT,
    captured_at TEXT,
    PRIMARY KEY (research_id, modality)
);

CREATE TABLE IF NOT EXISTS preprocessing (
    research_id TEXT REFERENCES cases(research_id),
    side        TEXT CHECK(side IN ('L','R')),
    path        TEXT,
    PRIMARY KEY (research_id, side)
);

CREATE TABLE IF NOT EXISTS commits (
    research_id  TEXT PRIMARY KEY REFERENCES cases(research_id),
    status       TEXT,
    committed_at TEXT,
    operator     TEXT
);

CREATE TABLE IF NOT EXISTS roi_annotations (
    research_id  TEXT PRIMARY KEY REFERENCES cases(research_id),
    saved_at     TEXT,
    summary_json TEXT,
    project_json TEXT
);

CREATE TABLE IF NOT EXISTS nurses (
    name TEXT PRIMARY KEY
);

-- Separate from `nurses` (which is scoped to CRF exam nurse dropdown only) — the photographer
-- field in capture.html can be any of the 4 nurses OR a research team member, so it needs its
-- own roster rather than reusing/extending nurses. Deliberately no "add via web form" UI for
-- either table (see docs/notes) — names are added directly against this table when the roster
-- changes, since it's a small fixed list, not user-facing data entry.
CREATE TABLE IF NOT EXISTS operators (
    name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    created_at TEXT,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT,
    research_id TEXT,
    action      TEXT,
    detail      TEXT
);
"""

SEED_NURSES = [
    "กรรณิการ์ ทองพูล",
    "พิมพ์ลภัส ศรีสมบูรณ์",
    "ธนกฤต อินทรสุวรรณ",
    "สุภาวดี แก้วประเสริฐ",
]

# ผู้ถ่ายภาพ = พยาบาลทั้ง 4 คนข้างบน + ทีมวิจัยอีก 3 คน (ณัฐพงศ์ = หัวหน้าโครงการ)
SEED_OPERATORS = SEED_NURSES + [
    "ณัฐพงศ์ ภักดีบุญ",
    "ณบุญ วงศ์วิทย์",
    "กนธีร์ คลังทอง",
]


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def tx() -> Iterator[sqlite3.Connection]:
    """One connection, one transaction — commits on success, rolls back on error, always closes."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with tx() as conn:
        conn.executescript(SCHEMA)
        existing = {r["name"] for r in conn.execute("SELECT name FROM nurses")}
        for n in SEED_NURSES:
            if n not in existing:
                conn.execute("INSERT OR IGNORE INTO nurses(name) VALUES (?)", (n,))
        existing_ops = {r["name"] for r in conn.execute("SELECT name FROM operators")}
        for n in SEED_OPERATORS:
            if n not in existing_ops:
                conn.execute("INSERT OR IGNORE INTO operators(name) VALUES (?)", (n,))


# ---------- cases / id minting ----------
def upsert_case(research_id: str, created_at: Optional[str] = None) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) "
            "ON CONFLICT(research_id) DO NOTHING",
            (research_id, created_at or now_iso()),
        )


def next_research_id() -> str:
    with tx() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(research_id, 2) AS INTEGER)) AS m FROM cases "
            "WHERE research_id GLOB 'P[0-9]*'"
        ).fetchone()
        n = (row["m"] or 0) + 1
        return f"P{n:04d}"


def list_cases_with_status() -> list[dict]:
    """Feeds GET /api/cases — every case that has a CRF form, joined with capture status."""
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT c.research_id, f.nurse, f.derived_json,
                   EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='podoscope') AS has_podo,
                   EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='thermal') AS has_thermal
            FROM cases c JOIN crf_forms f ON f.research_id = c.research_id
            ORDER BY c.research_id
            """
        ).fetchall()
    out = []
    for r in rows:
        derived = json.loads(r["derived_json"]) if r["derived_json"] else {}
        out.append({
            "research_id": r["research_id"],
            "nurse": r["nurse"] or "",
            "iwgdf": {"L": (derived.get("L") or {}).get("category"),
                      "R": (derived.get("R") or {}).get("category")},
            "has_podo": bool(r["has_podo"]),
            "has_thermal": bool(r["has_thermal"]),
        })
    return out


# ---------- CRF ----------
def has_crf(pid: str) -> bool:
    with tx() as conn:
        return conn.execute("SELECT 1 FROM crf_forms WHERE research_id=?", (pid,)).fetchone() is not None


def get_crf(pid: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute("SELECT * FROM crf_forms WHERE research_id=?", (pid,)).fetchone()
    return _crf_row_to_dict(row) if row else None


def list_crf() -> list[dict]:
    with tx() as conn:
        rows = conn.execute("SELECT * FROM crf_forms ORDER BY research_id DESC").fetchall()
    return [_crf_row_to_dict(r) for r in rows]


def _crf_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "pid": row["research_id"],
        "nurse": row["nurse"] or "",
        "nurse2": row["nurse2"] or "",
        "savedAt": row["saved_at"] or "",
        "data": {
            "fields": json.loads(row["fields_json"]) if row["fields_json"] else {},
            "derived": json.loads(row["derived_json"]) if row["derived_json"] else {},
        },
        "schema_version": row["schema_version"] or "1.0",
    }


def save_crf(pid: str, nurse: str, nurse2: str, saved_at: str, fields: dict, derived: dict,
             schema_version: str) -> None:
    """fields_json and derived_json are written together in one statement — derived is a cache of
    evalSide() output and must never drift out of sync with fields."""
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) "
            "ON CONFLICT(research_id) DO NOTHING",
            (pid, saved_at),
        )
        conn.execute(
            """
            INSERT INTO crf_forms(research_id, nurse, nurse2, saved_at, fields_json, derived_json, schema_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(research_id) DO UPDATE SET
                nurse=excluded.nurse, nurse2=excluded.nurse2, saved_at=excluded.saved_at,
                fields_json=excluded.fields_json, derived_json=excluded.derived_json,
                schema_version=excluded.schema_version
            """,
            (pid, nurse, nurse2, saved_at, json.dumps(fields, ensure_ascii=False),
             json.dumps(derived, ensure_ascii=False), schema_version),
        )


def delete_crf(pid: str) -> bool:
    with tx() as conn:
        cur = conn.execute("DELETE FROM crf_forms WHERE research_id=?", (pid,))
        return cur.rowcount > 0


# ---------- captures / preprocessing / commits ----------
def has_capture(research_id: str, modality: str) -> bool:
    with tx() as conn:
        return conn.execute(
            "SELECT 1 FROM captures WHERE research_id=? AND modality=?", (research_id, modality)
        ).fetchone() is not None


def save_capture(research_id: str, modality: str, raw_path: str, captured_at: str) -> None:
    with tx() as conn:
        # defensive upsert, same pattern as save_crf()/save_roi() — captures.research_id is a
        # foreign key into cases, so this must exist first. In practice server.py always creates
        # the case via save_crf() before a capture can happen (the 409 gate on has_crf()), but
        # this function should not silently depend on caller ordering to avoid a FK IntegrityError.
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) ON CONFLICT(research_id) DO NOTHING",
            (research_id, captured_at),
        )
        conn.execute(
            """
            INSERT INTO captures(research_id, modality, raw_path, captured_at) VALUES (?, ?, ?, ?)
            ON CONFLICT(research_id, modality) DO UPDATE SET
                raw_path=excluded.raw_path, captured_at=excluded.captured_at
            """,
            (research_id, modality, raw_path, captured_at),
        )


def get_capture(research_id: str, modality: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute(
            "SELECT * FROM captures WHERE research_id=? AND modality=?", (research_id, modality)
        ).fetchone()
    return dict(row) if row else None


def save_preprocessing(research_id: str, side: str, path: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) ON CONFLICT(research_id) DO NOTHING",
            (research_id, now_iso()),
        )
        conn.execute(
            """
            INSERT INTO preprocessing(research_id, side, path) VALUES (?, ?, ?)
            ON CONFLICT(research_id, side) DO UPDATE SET path=excluded.path
            """,
            (research_id, side, path),
        )


def get_preprocessing(research_id: str) -> dict:
    with tx() as conn:
        rows = conn.execute(
            "SELECT side, path FROM preprocessing WHERE research_id=?", (research_id,)
        ).fetchall()
    return {r["side"]: r["path"] for r in rows}


def save_commit(research_id: str, status: str, committed_at: str, operator: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) ON CONFLICT(research_id) DO NOTHING",
            (research_id, committed_at),
        )
        conn.execute(
            """
            INSERT INTO commits(research_id, status, committed_at, operator) VALUES (?, ?, ?, ?)
            ON CONFLICT(research_id) DO UPDATE SET
                status=excluded.status, committed_at=excluded.committed_at, operator=excluded.operator
            """,
            (research_id, status, committed_at, operator),
        )


def list_commits() -> list[dict]:
    """Feeds GET /api/manifest — joins commits with captures/preprocessing to reconstruct the same
    podo_raw / podo_prepro / thermal shape the frontend has always expected from manifest.csv."""
    with tx() as conn:
        rows = conn.execute("SELECT * FROM commits ORDER BY committed_at DESC").fetchall()
        out = []
        for r in rows:
            podo = conn.execute(
                "SELECT raw_path FROM captures WHERE research_id=? AND modality='podoscope'",
                (r["research_id"],),
            ).fetchone()
            thermal = conn.execute(
                "SELECT raw_path FROM captures WHERE research_id=? AND modality='thermal'",
                (r["research_id"],),
            ).fetchone()
            prepro = conn.execute(
                "SELECT 1 FROM preprocessing WHERE research_id=? LIMIT 1", (r["research_id"],)
            ).fetchone()
            out.append({
                "research_id": r["research_id"],
                "captured_at": r["committed_at"],
                "status": r["status"],
                "podo_raw": podo["raw_path"] if podo else "",
                "podo_prepro": "yes" if prepro else "",
                "thermal": thermal["raw_path"] if thermal else "",
            })
    return out


def committed_max() -> int:
    """Highest numeric id among committed cases only (mirrors the old manifest.csv-based scan)."""
    with tx() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(research_id, 2) AS INTEGER)) AS m FROM commits "
            "WHERE research_id GLOB 'P[0-9]*'"
        ).fetchone()
        return row["m"] or 0


def crf_max() -> int:
    """Highest numeric id among cases that have a saved CRF form."""
    with tx() as conn:
        row = conn.execute(
            "SELECT MAX(CAST(SUBSTR(research_id, 2) AS INTEGER)) AS m FROM crf_forms "
            "WHERE research_id GLOB 'P[0-9]*'"
        ).fetchone()
        return row["m"] or 0


# ---------- ROI ----------
def get_roi(rid: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute("SELECT * FROM roi_annotations WHERE research_id=?", (rid,)).fetchone()
    if not row:
        return None
    return {
        "rid": row["research_id"],
        "savedAt": row["saved_at"] or "",
        "summary": json.loads(row["summary_json"]) if row["summary_json"] else {},
        "project": json.loads(row["project_json"]) if row["project_json"] else {},
    }


def list_roi() -> list[dict]:
    """Summaries only — no project blob, matching the old file-based contract (project can be large)."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT research_id, saved_at, summary_json FROM roi_annotations ORDER BY research_id DESC"
        ).fetchall()
    return [{"rid": r["research_id"], "savedAt": r["saved_at"] or "",
             "summary": json.loads(r["summary_json"]) if r["summary_json"] else {}} for r in rows]


def save_roi(rid: str, saved_at: str, summary: dict, project: dict) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) ON CONFLICT(research_id) DO NOTHING",
            (rid, saved_at),
        )
        conn.execute(
            """
            INSERT INTO roi_annotations(research_id, saved_at, summary_json, project_json)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(research_id) DO UPDATE SET
                saved_at=excluded.saved_at, summary_json=excluded.summary_json, project_json=excluded.project_json
            """,
            (rid, saved_at, json.dumps(summary, ensure_ascii=False), json.dumps(project, ensure_ascii=False)),
        )


def delete_roi(rid: str) -> bool:
    with tx() as conn:
        cur = conn.execute("DELETE FROM roi_annotations WHERE research_id=?", (rid,))
        return cur.rowcount > 0


# ---------- nurses ----------
def list_nurses() -> list[str]:
    with tx() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM nurses ORDER BY name")]


def add_nurse(name: str) -> None:
    with tx() as conn:
        conn.execute("INSERT OR IGNORE INTO nurses(name) VALUES (?)", (name,))


# ---------- operators (photographer dropdown on capture.html — nurses + research team) ----------
def list_operators() -> list[str]:
    with tx() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM operators ORDER BY name")]


def add_operator(name: str) -> None:
    with tx() as conn:
        conn.execute("INSERT OR IGNORE INTO operators(name) VALUES (?)", (name,))


# ---------- settings ----------
def get_setting(key: str) -> Optional[str]:
    with tx() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ---------- sessions ----------
def create_session(token: str, expires_at: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO sessions(token, created_at, expires_at) VALUES (?, ?, ?)",
            (token, now_iso(), expires_at),
        )


def get_session(token: str) -> Optional[dict]:
    with tx() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE token=?", (token,)).fetchone()
    return dict(row) if row else None


def delete_session(token: str) -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))


def purge_expired_sessions() -> None:
    with tx() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now_iso(),))


# ---------- audit ----------
def log_audit(research_id: Optional[str], action: str, detail: str = "") -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO audit_log(ts, research_id, action, detail) VALUES (?, ?, ?, ?)",
            (now_iso(), research_id, action, detail),
        )
