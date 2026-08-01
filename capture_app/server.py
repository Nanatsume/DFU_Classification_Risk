"""Local capture server — real disk writes, auto preprocessing, USB swap-in later.

Layout on disk (modality-first, one folder per patient):

    data/
      podo/P0001/raw/P0001_podo.png
      podo/P0001/preprocessing/P0001_podo_L.png   P0001_podo_R.png   (S1, auto)
      thermal/P0001/image/P0001_thermal.png
      thermal/P0001/radiometric/P0001_thermal.tiff                    (once the SDK is wired)
      meta/P0001.json          patient-level record (points into both modalities)
      manifest.csv             one row per committed patient

Podoscope capture auto-runs the preprocessing pipeline (preprocessing.py) and saves the L/R
result for QC and reuse. The raw image is the source of truth; the preprocessed files are a cache
that can be regenerated from raw when the pipeline settings change.

Run:
    pip install -r requirements.txt
    uvicorn server:app --host 127.0.0.1 --port 8000
    # open http://127.0.0.1:8000/
"""
from __future__ import annotations
import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from capture_source import get_source
from preprocessing import preprocess_foot_image

APP_VERSION = "2.0"
SCHEMA_VERSION = "2.0"
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
STATIC_DIR = BASE / "static"
META_DIR = DATA_DIR / "meta"
MANIFEST = DATA_DIR / "manifest.csv"
MODALITIES = ("podoscope", "thermal")

app = FastAPI(title="Foot capture (local)")
SOURCE = get_source()


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


# ----- paths -----
def raw_path(rid: str, modality: str) -> Path:
    if modality == "podoscope":
        return DATA_DIR / "podo" / rid / "raw" / f"{rid}_podo.png"
    return DATA_DIR / "thermal" / rid / "image" / f"{rid}_thermal.png"


def prepro_path(rid: str, side: str) -> Path:
    return DATA_DIR / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}.png"


def rel(p: Path) -> str:
    return p.relative_to(DATA_DIR).as_posix()


def url(p: Path) -> str:
    return "/api/file/" + rel(p)


# ----- id minting (counts committed cases only) -----
def committed_max() -> int:
    if not MANIFEST.exists():
        return 0
    with MANIFEST.open(encoding="utf-8") as f:
        return max((int(r["research_id"][1:]) for r in csv.DictReader(f)
                    if r["research_id"][1:].isdigit()), default=0)


def next_id() -> str:
    return f"P{committed_max() + 1:04d}"


# ----- API -----
class CaptureReq(BaseModel):
    rid: str
    modality: str


class RidReq(BaseModel):
    rid: str


class CommitReq(BaseModel):
    rid: str
    operator: str = ""


@app.get("/api/health")
def health():
    return {"ok": True, "source": type(SOURCE).__name__,
            "next_id": next_id(), "count": committed_max()}


@app.post("/api/session/new")
def session_new():
    return {"research_id": next_id(), "started_at": now_iso()}


@app.post("/api/capture")
def capture(req: CaptureReq):
    if req.modality not in MODALITIES:
        raise HTTPException(400, f"modality must be one of {MODALITIES}")
    png = SOURCE.grab(req.modality, req.rid)
    p = raw_path(req.rid, req.modality)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(png)
    return {"rid": req.rid, "modality": req.modality, "url": url(p)}


@app.post("/api/preprocess")
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
        p = prepro_path(req.rid, side)
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray((result[key] * 255).astype(np.uint8)).save(p)
        out[side] = url(p)
    return {"status": "ok", "left_url": out["L"], "right_url": out["R"]}


@app.get("/api/file/{path:path}")
def get_file(path: str):
    p = (DATA_DIR / path).resolve()
    if DATA_DIR.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p)


@app.post("/api/commit")
def commit(req: CommitReq):
    podo_raw = raw_path(req.rid, "podoscope")
    ther_img = raw_path(req.rid, "thermal")
    if not podo_raw.exists() and not ther_img.exists():
        raise HTTPException(404, f"no captures for {req.rid}")
    prepro = {s: rel(prepro_path(req.rid, s)) for s in ("L", "R") if prepro_path(req.rid, s).exists()}
    record = {
        "schema_version": SCHEMA_VERSION,
        "research_id": req.rid,
        "captured_at": now_iso(),
        "operator": req.operator,
        "podoscope": {
            "raw": rel(podo_raw) if podo_raw.exists() else None,
            "preprocessing": prepro or None,
        },
        "thermal": {
            "image": rel(ther_img) if ther_img.exists() else None,
            "radiometric": None,
        },
        "status": "complete" if (podo_raw.exists() and ther_img.exists()) else "partial",
        "app_version": APP_VERSION,
    }
    META_DIR.mkdir(parents=True, exist_ok=True)
    (META_DIR / f"{req.rid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    _append_manifest(record)
    return record


def _append_manifest(rec: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["research_id", "captured_at", "status", "podo_raw", "podo_prepro", "thermal"])
        w.writerow([rec["research_id"], rec["captured_at"], rec["status"],
                    rec["podoscope"]["raw"] or "",
                    "yes" if rec["podoscope"]["preprocessing"] else "",
                    rec["thermal"]["image"] or ""])


@app.get("/api/manifest")
def manifest():
    if not MANIFEST.exists():
        return JSONResponse([])
    with MANIFEST.open(encoding="utf-8") as f:
        return JSONResponse(list(csv.DictReader(f)))


# ----- front-end (mounted last so /api/* wins) -----
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
