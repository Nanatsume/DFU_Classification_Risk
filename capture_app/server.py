"""Local capture server — real disk writes, auto preprocessing, USB swap-in later.

Layout on disk (modality-first, one folder per patient) — image bytes still live as files;
db.py (SQLite, data/app.db) is the source of truth for everything else (case metadata, CRF
forms, ROI annotations, commit status, sessions):

    data/
      podo/P0001/raw/P0001_podo.png
      podo/P0001/preprocessing/P0001_podo_L.png   P0001_podo_R.png   (S1, auto)
      thermal/P0001/image/P0001_thermal.png
      thermal/P0001/radiometric/P0001_thermal.tiff                    (once the SDK is wired)
      meta/P0001.json          non-authoritative mirror of the commit record, for manual inspection
      app.db                   SQLite — cases, crf_forms, captures, preprocessing, commits,
                                roi_annotations, nurses, sessions, settings, audit_log

Podoscope capture auto-runs the preprocessing pipeline (preprocessing.py) and saves the L/R
result for QC and reuse. The raw image is the source of truth; the preprocessed files are a cache
that can be regenerated from raw when the pipeline settings change.

First run (once): migrate any existing flat-file data, then start the server —
    pip install -r requirements.txt
    python migrate_to_sqlite.py
    uvicorn server:app --host 127.0.0.1 --port 8000
    # open http://127.0.0.1:8000/
Set APP_PASSWORD in the environment to choose the shared team login password; if unset, a
one-time random password is generated and printed to the console on first boot.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from PIL import Image
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import db
from capture_source import get_source
from preprocessing import preprocess_foot_image
from crf_store import router as crf_router, nurses_router
from roi_store import router as roi_router

APP_VERSION = "2.0"
SCHEMA_VERSION = "2.0"
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
STATIC_DIR = BASE / "static"
META_DIR = DATA_DIR / "meta"
MODALITIES = ("podoscope", "thermal")

app = FastAPI(title="Foot capture (local)")
SOURCE = get_source()

db.init_db()
db.purge_expired_sessions()
auth.bootstrap_password()

require_session = Depends(auth.require_session)


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


# ----- paths -----
def raw_path(rid: str, modality: str) -> Path:
    if modality == "podoscope":
        return DATA_DIR / "podo" / rid / "raw" / f"{rid}_podo.png"
    return DATA_DIR / "thermal" / rid / "image" / f"{rid}_thermal.png"


def prepro_path(rid: str, side: str) -> Path:
    return DATA_DIR / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}.png"


def prepro_full_path(rid: str, side: str) -> Path:
    """Full-resolution, CLAHE-enhanced but un-resized copy — for ROI annotation display only.
    The 224x224 file from prepro_path() is what training actually uses; this one exists purely
    because a human needs to see fine detail that survives shrinking to the model's input size."""
    return DATA_DIR / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}_full.png"


def prepro_original_path(rid: str, side: str) -> Path:
    """Color, post-segmentation, pre-grayscale/CLAHE copy — the "original" reference frame for
    XAI overlay later (Grad-CAM etc. rescale back onto this, not the raw camera photo, since the
    model only ever sees one segmented foot at a time). Same (H, W) as prepro_full_path() by
    construction, so ROI boxes marked on that file line up on this one with no rescaling."""
    return DATA_DIR / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}_original.png"


def rel(p: Path) -> str:
    return p.relative_to(DATA_DIR).as_posix()


def url(p: Path) -> str:
    return "/api/file/" + rel(p)


# ----- API -----
class CaptureReq(BaseModel):
    rid: str
    modality: str


class RidReq(BaseModel):
    rid: str


class CommitReq(BaseModel):
    rid: str
    operator: str = ""


class OperatorReq(BaseModel):
    name: str


@app.get("/api/operators", dependencies=[require_session])
def operators():
    """Photographer dropdown source for capture.html — nurses + research team, seeded directly
    (see db.SEED_OPERATORS); deliberately no "add via web form" UI for this, same as /api/nurses."""
    return db.list_operators()


@app.post("/api/operators", dependencies=[require_session])
def add_operator(req: OperatorReq):
    name = req.name.strip()
    if not name:
        raise HTTPException(400, "name required")
    db.add_operator(name)
    return db.list_operators()


@app.get("/api/health")
def health():
    """Unauthenticated — every page's LIVE/DEMO probe and the login page itself call this
    before a session exists."""
    return {"ok": True, "source": type(SOURCE).__name__,
            "next_id": db.next_research_id(), "count": db.committed_max(),
            "crf_count": db.crf_max()}


@app.get("/api/cases", dependencies=[require_session])
def cases():
    """Cases that have a CRF form, with capture status — feeds the capture station's picker.
    A case must have a form before it can be photographed (see /api/capture)."""
    return db.list_cases_with_status()


@app.post("/api/session/new", dependencies=[require_session])
def session_new():
    """Mints the next research id and reserves it immediately (a case can exist with neither a
    CRF form nor a photo yet, right after this call) so the id counter stays monotonic even if
    the form is abandoned before saving."""
    rid = db.next_research_id()
    db.upsert_case(rid)
    return {"research_id": rid, "started_at": now_iso()}


@app.post("/api/capture", dependencies=[require_session])
def capture(req: CaptureReq):
    if req.modality not in MODALITIES:
        raise HTTPException(400, f"modality must be one of {MODALITIES}")
    if not db.has_crf(req.rid):
        raise HTTPException(409, f"no CRF form for {req.rid} yet — fill in the case record form first")
    png = SOURCE.grab(req.modality, req.rid)
    p = raw_path(req.rid, req.modality)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(png)
    db.save_capture(req.rid, req.modality, rel(p), now_iso())
    db.log_audit(req.rid, "capture", req.modality)
    return {"rid": req.rid, "modality": req.modality, "url": url(p)}


@app.post("/api/preprocess", dependencies=[require_session])
def preprocess(req: RidReq):
    """Auto-run after a podoscope capture. Segments, separates L/R, CLAHE — saves both sides."""
    raw = raw_path(req.rid, "podoscope")
    if not raw.exists():
        raise HTTPException(404, "no podoscope capture to preprocess")
    try:
        result = preprocess_foot_image(str(raw))
    except Exception as e:  # segmentation / separation can fail on a bad capture
        return {"status": "failed", "error": f"{type(e).__name__}: {e}"}
    if result is None:
        return {"status": "failed", "error": "could not separate two feet — check the capture"}
    out = {}
    for side, key in (("L", "left_foot"), ("R", "right_foot")):
        side_word = "left" if side == "L" else "right"

        p = prepro_path(req.rid, side)
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray((result[key] * 255).astype(np.uint8)).save(p)
        db.save_preprocessing(req.rid, side, rel(p))
        out[side] = url(p)

        # full-resolution sibling for ROI annotation (VIA loads this, not the 224x224 training
        # file) — same preprocessing.py call already computed it, just save it too
        pf = prepro_full_path(req.rid, side)
        Image.fromarray(result[f"{side_word}_foot_full"]).save(pf)

        # color, pre-grayscale/CLAHE sibling — the "original" reference frame for XAI overlay
        # later; same (H, W) as the _full.png above so ROI boxes line up with no rescaling
        po = prepro_original_path(req.rid, side)
        Image.fromarray(result[f"{side_word}_foot_original"]).save(po)

    return {"status": "ok", "left_url": out["L"], "right_url": out["R"]}


@app.get("/api/file/{path:path}", dependencies=[require_session])
def get_file(path: str):
    p = (DATA_DIR / path).resolve()
    if DATA_DIR.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p)


@app.post("/api/commit", dependencies=[require_session])
def commit(req: CommitReq):
    podo_raw = raw_path(req.rid, "podoscope")
    ther_img = raw_path(req.rid, "thermal")
    if not podo_raw.exists() and not ther_img.exists():
        raise HTTPException(404, f"no captures for {req.rid}")
    prepro = {s: rel(prepro_path(req.rid, s)) for s in ("L", "R") if prepro_path(req.rid, s).exists()}
    status = "complete" if (podo_raw.exists() and ther_img.exists()) else "partial"
    captured_at = now_iso()
    record = {
        "schema_version": SCHEMA_VERSION,
        "research_id": req.rid,
        "captured_at": captured_at,
        "operator": req.operator,
        "podoscope": {
            "raw": rel(podo_raw) if podo_raw.exists() else None,
            "preprocessing": prepro or None,
        },
        "thermal": {
            "image": rel(ther_img) if ther_img.exists() else None,
            "radiometric": None,
        },
        "status": status,
        "app_version": APP_VERSION,
    }
    # SQLite is the source of truth; the JSON file is kept only as a non-authoritative mirror
    # for manual inspection — if the two ever disagree, the DB wins.
    META_DIR.mkdir(parents=True, exist_ok=True)
    (META_DIR / f"{req.rid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    db.upsert_case(req.rid)
    db.save_commit(req.rid, status, captured_at, req.operator)
    db.log_audit(req.rid, "commit", status)
    return record


@app.get("/api/manifest", dependencies=[require_session])
def manifest():
    return db.list_commits()


app.include_router(auth.router)
app.include_router(crf_router, dependencies=[require_session])
app.include_router(nurses_router, dependencies=[require_session])
app.include_router(roi_router, dependencies=[require_session])

# ----- front-end (mounted last so /api/* wins) -----
# via/ is third-party vendored (VIA 2 + our _via_dfu.js connector) and lives outside STATIC_DIR
# so `vite build`'s emptyOutDir doesn't wipe it on every rebuild of the React frontend.
VIA_DIR = BASE / "via_static"
if VIA_DIR.exists():
    app.mount("/via", StaticFiles(directory=VIA_DIR, html=True), name="via")
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
