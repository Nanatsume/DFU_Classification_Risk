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
import os
from typing import Iterator, Optional

TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

BASE = Path(__file__).resolve().parent
# DFU_DATA_DIR relocates every byte the app owns — app.db and the image tree both live under it.
# Set it to a folder that is backed up (an external/second drive at the hospital); the default
# keeps everything inside the checkout, which is convenient for development and wrong for real
# collection. server.py reads the same variable so the two never disagree.
# NOTE with WAL enabled, a backup must copy app.db AND its -wal/-shm sidecars, or run
# `PRAGMA wal_checkpoint(TRUNCATE)` first — copying app.db alone can lose recent commits.
DATA_DIR = Path(os.environ["DFU_DATA_DIR"]).expanduser() if os.environ.get("DFU_DATA_DIR") else BASE / "data"
DB_PATH = DATA_DIR / "app.db"

SCHEMA = """
-- `hn` is the hospital number, and the only directly identifying value this app holds. It is
-- here because the workflow demands it: the nurses have no time to fill a 30-field form during
-- the clinic, so photographs are taken against an HN and the CRF is transcribed later from the
-- hospital's own annual-checkup record, which is filed by HN and carries no research id.
--
-- It is deliberately confined to this one column. It never reaches the image filenames, the
-- meta/*.json mirrors, fields_json, the CSV exports, or the cloud backup (tools/backup.py blanks
-- it in the snapshot it uploads). Keeping it at all is a considered trade: transcription by hand
-- goes wrong sometimes, and without the HN a suspect value can never be checked against the
-- source again. clear_all_hn() de-identifies the database once collection is finished.
CREATE TABLE IF NOT EXISTS cases (
    research_id TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    hn          TEXT
);

-- No examining-nurse columns, by request of the study site: staff names are personal data the
-- site does not want stored. Nothing in the app records who performed an examination or took a
-- photograph. See the note in auth.py — the shared login used to be justified by these fields
-- carrying attribution instead, and that justification no longer holds.
CREATE TABLE IF NOT EXISTS crf_forms (
    research_id    TEXT PRIMARY KEY REFERENCES cases(research_id),
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
    committed_at TEXT
);

CREATE TABLE IF NOT EXISTS roi_annotations (
    research_id  TEXT PRIMARY KEY REFERENCES cases(research_id),
    saved_at     TEXT,
    summary_json TEXT,
    project_json TEXT
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


def _add_hn_column(conn: sqlite3.Connection) -> None:
    """`cases.hn` for databases created before photograph-first capture existed."""
    if "hn" not in {r["name"] for r in conn.execute("PRAGMA table_info(cases)")}:
        conn.execute("ALTER TABLE cases ADD COLUMN hn TEXT")


def _drop_staff_name_storage(conn: sqlite3.Connection) -> None:
    """Remove staff names from a database created before the site asked us to stop storing them.

    Runs on every boot and is idempotent: the columns and tables are dropped only if still there.
    Dropping rather than blanking is deliberate — a column that exists will eventually be filled
    again, and "we do not collect this" should be true of the schema, not just of the UI.
    """
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(crf_forms)")}
    for col in ("nurse", "nurse2"):
        if col in cols:
            conn.execute(f"ALTER TABLE crf_forms DROP COLUMN {col}")
    if "operator" in {r["name"] for r in conn.execute("PRAGMA table_info(commits)")}:
        conn.execute("ALTER TABLE commits DROP COLUMN operator")
    for table in ("nurses", "operators"):
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    # The old form posted the names inside the answers blob as well as into their own columns,
    # so dropping the columns alone leaves them sitting in fields_json. Strip them there too —
    # this is the copy that a restored backup or a second machine would otherwise keep.
    for rid, blob in conn.execute("SELECT research_id, fields_json FROM crf_forms").fetchall():
        try:
            fields = json.loads(blob or "{}")
        except ValueError:
            continue
        if any(k in fields for k in ("nurse", "nurse2")):
            for k in ("nurse", "nurse2"):
                fields.pop(k, None)
            conn.execute("UPDATE crf_forms SET fields_json=? WHERE research_id=?",
                         (json.dumps(fields, ensure_ascii=False), rid))


def init_db() -> None:
    with tx() as conn:
        conn.executescript(SCHEMA)
        _add_hn_column(conn)
        _drop_staff_name_storage(conn)


# ---------- cases / id minting ----------
def upsert_case(research_id: str, created_at: Optional[str] = None) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) "
            "ON CONFLICT(research_id) DO NOTHING",
            (research_id, created_at or now_iso()),
        )


def start_case_with_hn(hn: str) -> str:
    """Mint a research id for a patient who is about to be photographed, and record their HN.

    Minting here rather than when the form is later filled in is what keeps the HN out of the
    filesystem: the images are named for the research id from the very first write, so no file
    on disk, in a backup, or in a folder listing ever carries a hospital number.
    """
    with tx() as conn:
        rid = _next_rid(conn)
        conn.execute("INSERT INTO cases(research_id, created_at, hn) VALUES (?, ?, ?)",
                     (rid, now_iso(), hn.strip()))
        return rid


def case_exists(research_id: str) -> bool:
    with tx() as conn:
        return conn.execute("SELECT 1 FROM cases WHERE research_id=?",
                            (research_id,)).fetchone() is not None


def get_hn(research_id: str) -> Optional[str]:
    with tx() as conn:
        row = conn.execute("SELECT hn FROM cases WHERE research_id=?", (research_id,)).fetchone()
    return (row["hn"] or None) if row else None


def count_cases_with_hn() -> int:
    with tx() as conn:
        return conn.execute(
            "SELECT COUNT(*) AS n FROM cases WHERE hn IS NOT NULL AND hn != ''").fetchone()["n"]


def clear_all_hn() -> int:
    """Drop every hospital number, leaving a dataset with no direct identifier in it. Meant for
    the end of data collection, once no transcription remains to be checked against source."""
    with tx() as conn:
        cur = conn.execute("UPDATE cases SET hn=NULL WHERE hn IS NOT NULL AND hn != ''")
        return cur.rowcount


def _next_rid(conn: sqlite3.Connection) -> str:
    """High-water mark over `cases`, inside a caller-supplied transaction. `cases` (not
    `crf_forms`) is the basis on purpose: deleting a form leaves its case row behind, and that row
    is what stops the id from ever being handed out a second time."""
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(research_id, 2) AS INTEGER)) AS m FROM cases "
        "WHERE research_id GLOB 'P[0-9]*'"
    ).fetchone()
    return f"P{(row['m'] or 0) + 1:04d}"


def next_research_id() -> str:
    """Peek at the id the next case would get. Callers that actually create a case must mint
    inside their own transaction (see save_crf) — this is a read-only preview and two concurrent
    callers will see the same value."""
    with tx() as conn:
        return _next_rid(conn)


def list_pending_crf() -> list[dict]:
    """Cases that have been photographed but whose CRF has not been transcribed yet.

    This is the working queue for the researcher sitting down afterwards with the hospital's own
    record: the HN is what they look the patient up by, and the timestamp is what tells two
    patients with adjacent HNs apart.
    """
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT c.research_id, c.hn, c.created_at,
                   EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='podoscope') AS has_podo,
                   EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='thermal') AS has_thermal
            FROM cases c
            LEFT JOIN crf_forms f ON f.research_id = c.research_id
            WHERE f.research_id IS NULL
              AND EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id)
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    return [{"research_id": r["research_id"], "hn": r["hn"] or "",
             "created_at": r["created_at"],
             "has_podo": bool(r["has_podo"]), "has_thermal": bool(r["has_thermal"])} for r in rows]


def list_unfinished_captures() -> list[dict]:
    """Cases started at the clinic whose photographs are not complete yet.

    Without this such a case is invisible: it has no CRF form, so it misses the transcription
    queue, and it has no form either, so it misses the capture page's other picker. The case is
    real — an id was minted and an HN recorded — but the only handle on it lived in the browser
    tab's memory, so a refresh stranded it with a patient's HN attached and no way back to it.
    """
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT c.research_id, c.hn, c.created_at,
                   EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='podoscope') AS has_podo,
                   EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='thermal') AS has_thermal
            FROM cases c
            LEFT JOIN crf_forms f ON f.research_id = c.research_id
            WHERE f.research_id IS NULL
              AND c.hn IS NOT NULL AND c.hn != ''
              AND NOT (
                EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='podoscope')
                AND EXISTS(SELECT 1 FROM captures WHERE research_id=c.research_id AND modality='thermal')
              )
            ORDER BY c.created_at DESC
            """
        ).fetchall()
    return [{"research_id": r["research_id"], "hn": r["hn"] or "",
             "created_at": r["created_at"],
             "has_podo": bool(r["has_podo"]), "has_thermal": bool(r["has_thermal"])} for r in rows]


def list_cases_with_status() -> list[dict]:
    """Feeds GET /api/cases — every case that has a CRF form, joined with capture status."""
    with tx() as conn:
        rows = conn.execute(
            """
            SELECT c.research_id, f.derived_json,
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
        "savedAt": row["saved_at"] or "",
        "data": {
            "fields": json.loads(row["fields_json"]) if row["fields_json"] else {},
            "derived": json.loads(row["derived_json"]) if row["derived_json"] else {},
        },
        "schema_version": row["schema_version"] or "1.0",
    }


def save_crf(pid: Optional[str], saved_at: str, fields: dict,
             derived: dict, schema_version: str) -> str:
    """Create or overwrite one case's form, returning its research id.

    `pid` is None/empty for a brand-new case: the id is minted *inside this transaction*, so the
    id only ever comes into existence together with the form it belongs to. Abandoning a
    half-filled form therefore costs nothing — nothing was reserved. Minting in the same
    transaction as the INSERT is also what makes two nurses saving at the same moment safe; a
    mint-then-insert in two steps would hand both of them the same number.

    fields_json and derived_json are written together in one statement — derived is a cache of
    evalSide() output and must never drift out of sync with fields."""
    with tx() as conn:
        pid = pid or _next_rid(conn)
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) "
            "ON CONFLICT(research_id) DO NOTHING",
            (pid, saved_at),
        )
        conn.execute(
            """
            INSERT INTO crf_forms(research_id, saved_at, fields_json, derived_json, schema_version)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(research_id) DO UPDATE SET
                saved_at=excluded.saved_at,
                fields_json=excluded.fields_json, derived_json=excluded.derived_json,
                schema_version=excluded.schema_version
            """,
            (pid, saved_at, json.dumps(fields, ensure_ascii=False),
             json.dumps(derived, ensure_ascii=False), schema_version),
        )
    return pid


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
        # foreign key into cases, so the case must exist first. In practice it always does: the
        # clinic flow creates it in start_case_with_hn() before any photograph is taken, and
        # /api/capture refuses an id it never issued. This stays defensive anyway rather than
        # depending on caller ordering for a FK IntegrityError not to happen.
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


def save_commit(research_id: str, status: str, committed_at: str) -> None:
    with tx() as conn:
        conn.execute(
            "INSERT INTO cases(research_id, created_at) VALUES (?, ?) ON CONFLICT(research_id) DO NOTHING",
            (research_id, committed_at),
        )
        conn.execute(
            """
            INSERT INTO commits(research_id, status, committed_at) VALUES (?, ?, ?)
            ON CONFLICT(research_id) DO UPDATE SET
                status=excluded.status, committed_at=excluded.committed_at
            """,
            (research_id, status, committed_at),
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
