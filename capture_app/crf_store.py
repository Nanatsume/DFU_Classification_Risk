"""CRF API — the paper form, now backed by SQLite (data/app.db) instead of data/crf/*.json.

Route contracts are unchanged from the file-based version except for two additions:
  - GET /api/crf/{pid}   single-record fetch (the split multi-page frontend no longer preloads
                          every record into one in-memory array, so each page fetches only what
                          it needs)

Research IDs are minted when the form is SAVED, not when it is opened: POST /api/crf with no
`pid` mints the next id inside the same transaction that writes the form (db.save_crf). Opening
the form page and walking away therefore burns no id. Ids are counted across both CRF-only and
photographed-only cases — a case whose form is filled at the clinic must not have its id reused
by the capture station later that day. See db.py for the authoritative counter.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db

SCHEMA_VERSION = "1.0"
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

router = APIRouter(prefix="/api/crf", tags=["crf"])


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def crf_max() -> int:
    return db.crf_max()


class CrfRecord(BaseModel):
    pid: str = ""      # empty = new case, server mints the id
    savedAt: str = ""
    data: dict


@router.get("")
def list_records():
    """Every saved form, newest id first. Feeds crf-list.html."""
    return db.list_crf()


@router.get("/{pid}")
def get_record(pid: str):
    rec = db.get_crf(pid)
    if not rec:
        raise HTTPException(404, f"no form for {pid}")
    return rec


@router.post("")
def save_record(rec: CrfRecord):
    """Create or overwrite one case. Overwrite is intended — editing a case is normal.

    Omit `pid` to create a new case: the server mints the research id and returns it in the saved
    record, which is the only place the client learns it. Sending a `pid` edits that case."""
    if rec.pid and not rec.pid.startswith("P"):
        raise HTTPException(400, "pid must look like P0001")
    saved_at = rec.savedAt or now_iso()
    data = rec.data or {}
    pid = db.save_crf(
        pid=rec.pid or None, saved_at=saved_at,
        fields=data.get("fields", {}), derived=data.get("derived", {}),
        schema_version=SCHEMA_VERSION,
    )
    db.log_audit(pid, "crf_save")
    return db.get_crf(pid)


def _has_photos(pid: str) -> bool:
    """A case that already has podoscope or thermal captures must keep its form — deleting it
    would leave those images without an owning record."""
    return db.has_capture(pid, "podoscope") or db.has_capture(pid, "thermal")


@router.delete("/{pid}")
def delete_record(pid: str):
    if not db.get_crf(pid):
        raise HTTPException(404, f"no form for {pid}")
    if _has_photos(pid):
        raise HTTPException(409, f"{pid} already has captures — delete the images first")
    db.delete_crf(pid)
    db.log_audit(pid, "crf_delete")
    return {"deleted": pid}
