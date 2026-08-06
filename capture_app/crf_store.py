"""CRF API — the paper form, now backed by SQLite (data/app.db) instead of data/crf/*.json.

Route contracts are unchanged from the file-based version except for two additions:
  - GET /api/crf/{pid}   single-record fetch (the split multi-page frontend no longer preloads
                          every record into one in-memory array, so each page fetches only what
                          it needs)
  - GET/POST /api/nurses  the nurse-name dropdown now comes from the `nurses` table instead of a
                          hardcoded JS array, so it can be edited without a code change

Research IDs are minted by db.next_research_id() (server.py's /api/session/new calls it) and
counted across both CRF-only and photographed-only cases — a case whose form is filled at the
clinic must not have its id reused by the capture station later that day. See db.py for the
authoritative counter (replaces the old dual committed_max()/crf_max() file-scan).
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db

SCHEMA_VERSION = "1.0"
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

router = APIRouter(prefix="/api/crf", tags=["crf"])
nurses_router = APIRouter(prefix="/api/nurses", tags=["nurses"])


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def crf_max() -> int:
    return db.crf_max()


class CrfRecord(BaseModel):
    pid: str
    nurse: str = ""
    nurse2: str = ""
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
    """Create or overwrite one case. Overwrite is intended — editing a case is normal."""
    if not rec.pid.startswith("P"):
        raise HTTPException(400, "pid must look like P0001")
    saved_at = rec.savedAt or now_iso()
    data = rec.data or {}
    db.save_crf(
        pid=rec.pid, nurse=rec.nurse, nurse2=rec.nurse2, saved_at=saved_at,
        fields=data.get("fields", {}), derived=data.get("derived", {}),
        schema_version=SCHEMA_VERSION,
    )
    db.log_audit(rec.pid, "crf_save")
    return db.get_crf(rec.pid)


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


# ---------- nurses (dropdown source) ----------
class NurseReq(BaseModel):
    name: str


@nurses_router.get("")
def list_nurses():
    return db.list_nurses()


@nurses_router.post("")
def add_nurse(req: NurseReq):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    db.add_nurse(name)
    return db.list_nurses()
