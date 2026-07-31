"""Local capture server (scaffold).

Mints Research IDs, receives PNG blobs from the browser, writes per-patient folders + JSON,
and appends a running manifest. Camera access is local/USB only. No cloud, no HN.

Run:
    pip install fastapi uvicorn python-multipart
    uvicorn server:app --host 127.0.0.1 --port 8000

The thermal *radiometric* pull is the one real TODO — the browser can only send a colourised
preview, so temperature values must come from the device SDK here (see capture_thermal_radiometric).
"""
from __future__ import annotations
import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

APP_VERSION = "0.1"
SCHEMA_VERSION = "1.0"
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
COUNTER_FILE = BASE / "counter.txt"
MANIFEST = DATA_DIR / "manifest.csv"
MODALITIES = ("podoscope", "thermal")

app = FastAPI(title="Foot capture (local)")


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


def next_research_id() -> str:
    """Mint the next ID. Self-healing — the counter is reconciled against the folders already on
    disk, so it can never collide with or fall behind existing data even if counter.txt is lost.
    Numbers are consumed, never reused (gaps are acceptable)."""
    counter = int(COUNTER_FILE.read_text()) if COUNTER_FILE.exists() else 0
    existing = [int(p.name[1:]) for p in DATA_DIR.glob("P*")
                if p.is_dir() and p.name[1:].isdigit()]
    n = max([counter, *existing]) + 1
    COUNTER_FILE.write_text(str(n))
    return f"P{n:04d}"


def case_dir(rid: str) -> Path:
    d = DATA_DIR / rid
    d.mkdir(parents=True, exist_ok=True)
    return d


@app.post("/session/new")
def session_new():
    rid = next_research_id()
    return {"research_id": rid, "started_at": now_iso()}


@app.post("/capture/{rid}")
async def capture(rid: str, modality: str, file: UploadFile = File(...)):
    if modality not in MODALITIES:
        raise HTTPException(400, f"modality must be one of {MODALITIES}")
    fn = f"{rid}_{'podo' if modality == 'podoscope' else 'thermal'}.png"
    (case_dir(rid) / fn).write_bytes(await file.read())
    if modality == "thermal":
        capture_thermal_radiometric(rid)  # TODO: pull temperature array via device SDK
    return {"research_id": rid, "modality": modality, "file": fn}


def capture_thermal_radiometric(rid: str) -> None:
    """TODO: read the radiometric temperature array from the thermal USB device SDK and save it
    as {rid}_thermal.tiff (or .npy) next to the colourised PNG. The colourised preview alone
    discards the temperature values needed for analysis."""
    pass


@app.post("/commit/{rid}")
def commit(rid: str, operator: str = ""):
    d = DATA_DIR / rid
    if not d.exists():
        raise HTTPException(404, f"no captures for {rid}")
    have = {m: [p.name for p in d.glob(f"{rid}_{'podo' if m == 'podoscope' else 'thermal'}.png")]
            for m in MODALITIES}
    status = "complete" if all(have[m] for m in MODALITIES) else "partial"
    record = {
        "schema_version": SCHEMA_VERSION,
        "research_id": rid,
        "captured_at": now_iso(),
        "operator": operator,
        "images": have,
        "status": status,
        "app_version": APP_VERSION,
    }
    (d / f"{rid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
    _append_manifest(record)
    return record


def _append_manifest(record: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    new = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["research_id", "captured_at", "status", "podoscope", "thermal"])
        w.writerow([record["research_id"], record["captured_at"], record["status"],
                    ";".join(record["images"]["podoscope"]),
                    ";".join(record["images"]["thermal"])])


@app.get("/manifest")
def manifest():
    if not MANIFEST.exists():
        return JSONResponse([])
    with MANIFEST.open(encoding="utf-8") as f:
        return JSONResponse(list(csv.DictReader(f)))
