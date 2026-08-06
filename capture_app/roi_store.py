"""ROI API — VIA 2 annotation results, now backed by SQLite (data/app.db) instead of
data/roi/*.json. Route contracts are unchanged from the file-based version.

The VIA project is stored in full (project_json) so a case can be reopened in VIA and edited
further; `summary` is a small derived view so the list page can render without pulling every
project blob.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db

TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

router = APIRouter(prefix="/api/roi", tags=["roi"])


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


class RoiPayload(BaseModel):
    rid: str
    project: dict            # full VIA project (reopenable in VIA)
    summary: dict = {}       # {"L": {"region_count": 2, "has_risk_area": "yes"}, "R": {...}}


@router.get("")
def list_roi():
    """Summaries only, no project blob — the list page doesn't need it and the blob can be large."""
    return db.list_roi()


@router.get("/{rid}")
def get_roi(rid: str):
    rec = db.get_roi(rid)
    if not rec:
        raise HTTPException(404, f"no ROI for {rid}")
    return rec


@router.post("/{rid}")
def save_roi(rid: str, payload: RoiPayload):
    if rid != payload.rid:
        raise HTTPException(400, "rid in URL and body do not match")
    saved_at = now_iso()
    db.save_roi(rid=rid, saved_at=saved_at, summary=payload.summary, project=payload.project)
    db.log_audit(rid, "roi_save")
    return {"rid": rid, "savedAt": saved_at, "summary": payload.summary}


@router.delete("/{rid}")
def delete_roi(rid: str):
    if not db.get_roi(rid):
        raise HTTPException(404, f"no ROI for {rid}")
    db.delete_roi(rid)
    db.log_audit(rid, "roi_delete")
    return {"deleted": rid}
