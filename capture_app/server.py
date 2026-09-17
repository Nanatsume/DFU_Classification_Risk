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
                                roi_annotations, sessions, settings, audit_log

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

from stdio_utf8 import force_utf8_stdio

force_utf8_stdio()  # must run before `import preprocessing` — see stdio_utf8.py

import asyncio
import json
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from PIL import Image
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import db
import server_paths
from server_paths import (prepro_full_path, prepro_original_path, prepro_path,
                          raw_path, rel, url)
from capture_source import (CaptureError, SimulatedSource, UsbCameraSource, demo_images,
                            get_source, list_video_devices, podoscope_preview,
                            resolve_podoscope_index)
from preprocessing import preprocess_foot_image
from crf_store import router as crf_router
from roi_store import router as roi_router

APP_VERSION = "2.0"
SCHEMA_VERSION = "2.0"
TZ = timezone(timedelta(hours=7))  # Asia/Bangkok

BASE = Path(__file__).resolve().parent
# Resolved per call, never cached — see server_paths for why a cached copy silently sent test
# images into the live data directory.
STATIC_DIR = BASE / "static"

MODALITIES = ("podoscope", "thermal")

app = FastAPI(title="Foot capture (local)")
SOURCE = get_source()

db.init_db()
db.purge_expired_sessions()
auth.bootstrap_password()

require_session = Depends(auth.require_session)


def now_iso() -> str:
    return datetime.now(TZ).replace(microsecond=0).isoformat()


# ----- API -----
class CaptureReq(BaseModel):
    rid: str
    modality: str


class RidReq(BaseModel):
    rid: str


class CommitReq(BaseModel):
    rid: str


class StartCaseReq(BaseModel):
    hn: str


class CameraModeReq(BaseModel):
    mode: str            # "sim" | "usb"


class CameraTestReq(BaseModel):
    modality: str


@app.get("/api/health")
def health():
    """Unauthenticated — every page's LIVE/DEMO probe and the login page itself call this
    before a session exists."""
    return {"ok": True, "source": type(SOURCE).__name__,
            "next_id": db.next_research_id(), "count": db.committed_max(),
            "crf_count": db.crf_max()}


@app.get("/api/backup-status", dependencies=[require_session])
def backup_status():
    """What tools/backup.py wrote on its last run, for the banner on the home page.

    A backup you believe in but which stopped running three weeks ago is worse than no backup at
    all, so the state is surfaced where someone sees it daily rather than left in a log file. The
    server only reports the file; it never runs or schedules a backup itself.
    """
    path = server_paths.data_dir() / "backup_status.json"
    if not path.exists():
        return {"configured": False}
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        return {"configured": True, "ok": False, "error": f"unreadable status file: {e}"}

    age_hours = None
    updated = status.get("updated_at")
    if updated:
        try:
            age = datetime.now(TZ) - datetime.fromisoformat(updated)
            age_hours = round(age.total_seconds() / 3600, 1)
        except ValueError:
            pass
    # 36h rather than 24h: a nightly job that runs late, or a laptop that was closed at 02:00,
    # should not cry wolf the next morning.
    return {"configured": True, "stale": age_hours is not None and age_hours > 36,
            "age_hours": age_hours, **status}


@app.get("/api/cases", dependencies=[require_session])
def cases():
    """Cases that have a CRF form, with capture status — feeds the capture station's picker.
    These are the cases that can still be photographed from the picker — ones whose form was
    filled in ahead of time. The usual clinic route does not pass through here at all: it starts
    at /api/session/start with an HN and photographs immediately."""
    return db.list_cases_with_status()


@app.post("/api/session/start", dependencies=[require_session])
def session_start(req: StartCaseReq):
    """Begin a case at the clinic: hospital number in, research id out, ready to photograph.

    The nurses cannot fill a 30-field form while a patient is in front of them, so the CRF is
    transcribed later from the hospital's own annual-checkup record — which is filed by HN and
    carries no research id. The HN entered here is the only thing linking the two, and it stays
    in the database: the images are named for the research id from the first write, so no
    hospital number ever reaches a filename, a folder listing, or a backup.
    """
    hn = req.hn.strip()
    if not hn:
        raise HTTPException(400, "ต้องกรอก HN ก่อนจึงจะถ่ายภาพได้")
    rid = db.start_case_with_hn(hn)
    db.log_audit(rid, "case_start")
    return {"research_id": rid, "hn": hn, "started_at": now_iso()}


@app.get("/api/case/{rid}", dependencies=[require_session])
def case_detail(rid: str):
    """The bits of a case the transcription form needs — chiefly the HN to look the patient up
    by in the hospital's own record."""
    if not db.case_exists(rid):
        raise HTTPException(404, f"no case {rid}")
    return {"research_id": rid, "hn": db.get_hn(rid) or ""}


@app.get("/api/camera", dependencies=[require_session])
def camera_status():
    """Is the podoscope camera actually there, and are we even in real-camera mode.

    Exists because both failure modes are silent from the capture screen. Running in `sim` looks
    identical to working — you press the button and get a photograph of a foot, just not this
    patient's foot — and a camera that is merely unplugged only announces itself after someone has
    already positioned a patient and pressed capture. Both are now visible before the first press.

    Cheap enough to poll: enumerating DirectShow devices takes milliseconds, and re-checking is
    what lets the page go green on its own when the cable goes in.
    """
    simulated = not isinstance(SOURCE, UsbCameraSource)
    if simulated:
        n = len(demo_images())
        return {"mode": "sim", "connected": True, "name": None, "devices": [],
                "demo_images": n,
                "error": ("โหมดทดสอบ — ใช้ภาพจากกล้องโพโดสโคปที่ถ่ายไว้แล้ว "
                          f"{n} ภาพ ไม่ใช่ภาพผู้ป่วยที่อยู่ตรงหน้า"
                          if n else
                          "โหมดจำลอง — ภาพที่ได้เป็นไฟล์ตัวอย่าง ไม่ใช่ภาพจากกล้องจริง")}

    devices = list_video_devices()
    try:
        index = resolve_podoscope_index()
    except CaptureError as e:
        return {"mode": "usb", "connected": False, "name": None,
                "devices": devices, "error": str(e)}
    name = devices[index] if index < len(devices) else f"index {index}"
    return {"mode": "usb", "connected": True, "name": name, "index": index,
            "devices": devices, "error": None}


@app.post("/api/camera/mode", dependencies=[require_session])
def set_camera_mode(req: CameraModeReq):
    """Switch between the real camera and the demo images without restarting the server.

    The demo source serves real captures from the podoscope rig (sample/demo), so the whole path
    — capture, segmentation, the L/R panel — can be exercised and looked at on a machine with no
    camera attached. Switching at runtime rather than through an env var is what makes that
    usable: the person who wants to see it is in the browser, not at a terminal.

    Deliberately not persisted. A restart always comes back on whatever CAPTURE_SOURCE says, so
    an afternoon of demoing cannot quietly leave the clinic station in simulation the next
    morning — which is precisely how a demo footprint got filed against a real case before.
    """
    global SOURCE
    mode = req.mode.strip().lower()
    if mode not in ("sim", "usb"):
        raise HTTPException(400, "mode must be 'sim' or 'usb'")
    SOURCE = UsbCameraSource() if mode == "usb" else SimulatedSource()
    db.log_audit(None, "camera_mode", mode)
    return camera_status()


@app.get("/api/unfinished", dependencies=[require_session])
def unfinished():
    """Cases started with an HN whose photographs are not finished — the resume list.

    The capture session used to live only in the page's memory, so closing the tab or reloading
    left the case stranded: an id and a patient's HN in the database, and nothing in the UI that
    could reach it again.
    """
    return db.list_unfinished_captures()


@app.get("/api/pending", dependencies=[require_session])
def pending():
    """The transcription queue — photographed, CRF not filled in yet."""
    return db.list_pending_crf()


@app.get("/api/hn", dependencies=[require_session])
def hn_status():
    """How many cases still carry a hospital number, for the de-identification control."""
    return {"remaining": db.count_cases_with_hn()}


@app.delete("/api/hn", dependencies=[require_session])
def clear_hn():
    """Drop every hospital number at once — the end-of-collection de-identification step.

    Irreversible by design: after this the dataset holds no direct identifier, and no transcribed
    value can be checked against the hospital record again. That is the point, but it is why the
    UI asks twice.
    """
    n = db.clear_all_hn()
    db.log_audit(None, "hn_cleared", str(n))
    return {"cleared": n}


@app.post("/api/capture", dependencies=[require_session])
def capture(req: CaptureReq):
    if req.modality not in MODALITIES:
        raise HTTPException(400, f"modality must be one of {MODALITIES}")
    # The gate used to be "this case must already have a CRF form". Photograph-first capture
    # inverts that: the case is created by /api/session/start with an HN, and the form arrives
    # later. What must still be true is that the id was issued by us and is tied to a patient —
    # otherwise the image has nothing identifying whose foot it is.
    if not db.case_exists(req.rid):
        raise HTTPException(409, f"ยังไม่ได้เริ่มเคส {req.rid} — กรอก HN แล้วกดเริ่มเคสก่อน")
    try:
        png = SOURCE.grab(req.modality, req.rid)
    except CaptureError as e:
        # These carry a message written for the nurse standing at the podoscope — which camera is
        # missing, what is holding it, to check the lens cover. Letting it escape as a 500 turns
        # all of that into "Internal Server Error" on the one screen where it is actionable.
        raise HTTPException(503, str(e))
    except NotImplementedError as e:
        raise HTTPException(501, str(e))   # thermal, until the device arrives
    p = raw_path(req.rid, req.modality)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(png)
    db.save_capture(req.rid, req.modality, rel(p), now_iso())
    db.log_audit(req.rid, "capture", req.modality)
    return {"rid": req.rid, "modality": req.modality, "url": url(p)}


@app.post("/api/camera-test/capture", dependencies=[require_session])
def camera_test_capture(req: CameraTestReq):
    """Fire the real camera with no case behind it — for staff checking that hardware still
    works before a patient sits down, without an HN, a research id, or a row in `cases`.

    Same SOURCE.grab() as /api/capture, so this proves the exact path a real capture would take,
    but the file lands under camera-test/ (server_paths.camera_test_dir) rather than podo/ or
    thermal/, which keeps it out of the cases table, the manifest, the gallery, and the backup
    allowlist. A smoke test should never be able to masquerade as a patient record.
    """
    if req.modality not in MODALITIES:
        raise HTTPException(400, f"modality must be one of {MODALITIES}")
    try:
        # While the live preview is open it already holds the only handle DirectShow will grant
        # this camera, so a still is lifted from the frame it is already holding rather than
        # opening a second one, which would fail with exactly the error this branch avoids.
        if req.modality == "podoscope" and podoscope_preview.active:
            png = podoscope_preview.capture_frame()
        else:
            png = SOURCE.grab(req.modality, "camera-test")
    except CaptureError as e:
        raise HTTPException(503, str(e))
    except NotImplementedError as e:
        raise HTTPException(501, str(e))
    d = server_paths.camera_test_dir(req.modality)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"Test-{_next_camera_test_seq(d):04d}.png"
    p.write_bytes(png)
    db.log_audit(None, "camera_test", req.modality)
    return {"modality": req.modality, "url": url(p), "name": p.stem}


_CAMERA_TEST_NAME = re.compile(r"^Test-(\d+)$")


def _next_camera_test_seq(d: Path) -> int:
    """Test-1, Test-2, ... per modality folder — a plain running count is what someone glancing
    at the page (or the folder) can actually keep track of, unlike a timestamp. Zero-padded to 4
    digits on disk so filenames still sort the same order they were taken in."""
    best = 0
    for f in d.glob("Test-*.png"):
        m = _CAMERA_TEST_NAME.match(f.stem)
        if m:
            best = max(best, int(m.group(1)))
    return best + 1


@app.get("/api/camera-test/list", dependencies=[require_session])
def camera_test_list(modality: str):
    """Previously taken smoke-test shots for one modality, newest first — so reopening the test
    page shows what was already captured instead of an empty page that forgets everything the
    moment someone navigates away."""
    if modality not in MODALITIES:
        raise HTTPException(400, f"modality must be one of {MODALITIES}")
    d = server_paths.camera_test_dir(modality)
    if not d.is_dir():
        return []
    files = sorted(d.glob("Test-*.png"), reverse=True)   # zero-padded, so this sorts newest first
    return [{"url": url(p), "name": p.stem} for p in files]


@app.get("/api/camera-test/preview", dependencies=[require_session])
async def camera_test_preview(request: Request):
    """MJPEG live view of the podoscope for the camera-test page.

    An async generator on purpose, not a sync one: it never touches cv2 itself, only the frames
    podoscope_preview.PodoscopeLivePreview is already producing in its own thread, so it can poll
    request.is_disconnected() the ordinary way instead of fighting a threadpool for it. Closing
    the <img> that consumes this (navigating away, closing the tab) ends the request, which raises
    GeneratorExit here and runs the `finally`, releasing the camera.
    """
    if not isinstance(SOURCE, UsbCameraSource):
        raise HTTPException(409, "โหมดจำลองไม่มีวิดีโอสด — สลับไปโหมดกล้องจริงก่อน (CAPTURE_SOURCE=usb)")
    podoscope_preview.acquire()

    async def frames():
        try:
            last = None
            idle_since = time.monotonic()
            while True:
                if await request.is_disconnected():
                    break
                if podoscope_preview.error:
                    break
                jpeg = podoscope_preview.latest_jpeg()
                if jpeg is None or jpeg is last:
                    if jpeg is None and time.monotonic() - idle_since > 10:
                        break   # camera never produced a first frame — give up rather than hang
                    await asyncio.sleep(0.05)
                    continue
                last = jpeg
                idle_since = time.monotonic()
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                await asyncio.sleep(0.05)
        finally:
            podoscope_preview.release()

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


# In-flight and finished preprocessing runs, keyed by research id. Segmentation takes 60-90
# seconds on a 1920x1080 capture and the request used to block for all of it, so the nurse stood
# waiting with a patient in front of them for something no one needs to watch happen. Held in
# memory on purpose: a run that was interrupted by a restart should not look finished, and
# /api/preprocess simply starts it again.
_PREPROCESS: dict[str, dict] = {}
_PREPROCESS_LOCK = threading.Lock()
# Generous: a 1920x1080 capture measures 60-90s, and the clinic machine may be slower. Long
# enough never to cut a real run short, short enough that a wedged child does not sit for ever.
PREPROCESS_TIMEOUT = int(os.environ.get("PREPROCESS_TIMEOUT", "600"))


def _run_preprocess(rid: str) -> None:
    """Run the pipeline for one case in a child process and record the outcome.

    A child rather than a thread because the server died with SIGSEGV -- a fault inside a native
    library, no Python traceback -- when the camera was used again while segmentation was running
    in-process. That is exactly what this workflow asks people to do: capture, then start the next
    patient while the first is still being processed. Three attempts to reproduce it deliberately
    all survived, so the precise interaction is still unknown; separating the two at the process
    boundary removes the shared address space they would have to fight over, without needing to
    know which library was at fault. A crash in the child also fails one case instead of taking
    the clinic's server down.
    """
    cmd = [sys.executable, str(BASE / "tools" / "preprocess_one.py"), rid]
    try:
        # Hand the data directory across explicitly. A child cannot see a monkeypatched
        # db.DATA_DIR, and inheriting a bare environment would send it to the default location —
        # which, under test, is the live one.
        env = {**os.environ, "DFU_DATA_DIR": str(server_paths.data_dir())}
        proc = subprocess.run(cmd, cwd=str(BASE), env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=PREPROCESS_TIMEOUT)
        lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
        finished = json.loads(lines[-1]) if lines else {}
        if not isinstance(finished, dict) or "status" not in finished:
            raise ValueError("worker produced no result")
        if finished["status"] == "failed" and proc.returncode == 0:
            finished["status"] = "failed"
    except subprocess.TimeoutExpired:
        finished = {"status": "failed",
                    "error": f"preprocessing เกิน {PREPROCESS_TIMEOUT} วินาที — ยกเลิกแล้ว"}
    except Exception as e:                                   # noqa: BLE001 — surfaced to the UI
        detail = (proc.stderr or "").strip()[-400:] if "proc" in dir() else ""
        finished = {"status": "failed",
                    "error": f"preprocessing ล้มเหลว: {type(e).__name__}: {e} {detail}".strip()}
    finished["finished_at"] = now_iso()
    with _PREPROCESS_LOCK:
        started = (_PREPROCESS.get(rid) or {}).get("started_at")
        if started:
            finished["started_at"] = started
        _PREPROCESS[rid] = finished


@app.post("/api/preprocess", dependencies=[require_session])
def preprocess(req: RidReq):
    """Start preprocessing a podoscope capture and return immediately.

    Returns {"status": "running"}; poll /api/preprocess/status. The work itself is unchanged —
    same pipeline, same settings, same output — it simply no longer holds the request, and the
    nurse can start the next patient while it finishes.
    """
    raw = raw_path(req.rid, "podoscope")
    if not raw.exists():
        raise HTTPException(404, "no podoscope capture to preprocess")

    with _PREPROCESS_LOCK:
        current = _PREPROCESS.get(req.rid)
        if current and current.get("status") == "running":
            return current                                  # already under way; do not start twice
        _PREPROCESS[req.rid] = {"status": "running", "started_at": now_iso()}

    threading.Thread(target=_run_preprocess, args=(req.rid,), daemon=True,
                     name=f"preprocess-{req.rid}").start()
    return {"status": "running", "rid": req.rid}


@app.get("/api/preprocess/status", dependencies=[require_session])
def preprocess_status(rid: str):
    """Where a run got to. "idle" means nothing has been started for this case in this process —
    after a restart that includes runs that were in flight, which is why it is not "ok"."""
    with _PREPROCESS_LOCK:
        state = _PREPROCESS.get(rid)
    return {"rid": rid, **(state or {"status": "idle"})}


def _preprocess_inline(req: RidReq):
    """The previous blocking implementation, kept for the tests that assert on the saved files."""
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
    root = server_paths.data_dir()
    p = (root / path).resolve()
    if root.resolve() not in p.parents or not p.is_file():
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
    meta_dir = server_paths.meta_dir()
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / f"{req.rid}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2),
                                                encoding="utf-8")
    db.upsert_case(req.rid)
    db.save_commit(req.rid, status, captured_at)
    db.log_audit(req.rid, "commit", status)
    return record


@app.get("/api/manifest", dependencies=[require_session])
def manifest():
    return db.list_commits()


app.include_router(auth.router)
app.include_router(crf_router, dependencies=[require_session])
app.include_router(roi_router, dependencies=[require_session])

# ----- front-end (mounted last so /api/* wins) -----
# via/ is third-party vendored (VIA 2 + our _via_dfu.js connector) and lives outside STATIC_DIR
# so `vite build`'s emptyOutDir doesn't wipe it on every rebuild of the React frontend.
VIA_DIR = BASE / "via_static"
if VIA_DIR.exists():
    app.mount("/via", StaticFiles(directory=VIA_DIR, html=True), name="via")
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
