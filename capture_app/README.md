# Capture App

Local-first app for collecting diabetic foot ulcer (DFU) risk data at Buddhachinaraj Hospital —
paired **Podoscope + Thermal** foot images per patient, a **CRF-07 case record form** that
computes the IWGDF risk category live, and **ROI annotation** (VIA 2) for later XAI/Grad-CAM
work. FastAPI + SQLite backend, React + Vite (multi-page) + Tailwind + shadcn/ui frontend.

Runs today with a **simulated camera** (the podoscope returns a real sample footprint so
preprocessing produces meaningful output). When the USB cameras arrive, the **only** code to
write is one capture class (`capture_source.py`).

For a full file-by-file / API / feature breakdown, see **[`docs/notes/index.md`](docs/notes/index.md)**
(Obsidian-linked notes — open the `docs/notes/` folder as a vault to browse with clickable links
and a graph view).

## Run

Backend (first time: create the venv, install deps, migrate any old flat-file data, then boot):

```bash
python3 -m venv .venv && source .venv/bin/activate     # first time only
pip install -r requirements.txt                         # first time only
python migrate_to_sqlite.py                              # first time only, safe to re-run
APP_PASSWORD=your-team-password uvicorn server:app --host 127.0.0.1 --port 8000
```

If `APP_PASSWORD` is unset, a one-time random password is generated and printed to the console
on first boot. Open `http://127.0.0.1:8000/` and log in with it.

Frontend (only needed to rebuild the UI — the built output already lives in `static/` and is
served directly by the command above):

```bash
cd frontend
npm install        # first time only
npm run dev         # dev server with hot reload, proxies /api to the backend above
npm run build        # production build -> ../static/ (what the backend actually serves)
```

## Flow

1. **เข้าสู่ระบบ** — one shared team password (not per-nurse accounts; the CRF form's own
   nurse/nurse2 fields handle attribution).
2. **กรอกฟอร์มใหม่** (CRF-07) — server mints the next Research ID (`P0001`, `P0002`, ...). Answers
   for LOPS (monofilament), PAD (ABI/TBI), deformity, and history are scored live into an IWGDF
   category (0–3) and a Positive/Negative label per foot.
3. **ถ่ายภาพ** — a case must have a saved form first (409 otherwise). Capturing **podoscope**
   auto-runs the preprocessing pipeline and shows the segmented left/right feet for QC on the
   spot; then capture **thermal**; **ยืนยันและบันทึก** commits the case.
4. **ทำ ROI** — mark pressure-at-risk regions in VIA 2 on the full-resolution preprocessed image.
   Only feet with a Positive (or not-yet-determined) label need marking — a Negative foot has no
   LOPS/PAD by definition, so there's nothing to mark; those cases still show up in the picker,
   just tagged "ไม่ต้องทำ" rather than hidden.
5. **ประวัติการบันทึก / รายละเอียดเคส / คลังภาพ** — browse everything back: a sortable table with
   CSV export (raw form order, or per-side training rows), a single-case view with every image and
   the saved ROI boxes overlaid, and a cross-case image gallery for a quick QC sweep.

## On-disk layout (modality-first)

```
data/
  app.db            SQLite — source of truth for cases, CRF forms, captures, preprocessing,
                     commits, ROI annotations, nurses, sessions, settings, audit log
  podo/P0001/
    raw/            P0001_podo.png                        raw podoscope (source of truth)
    preprocessing/  P0001_podo_L.png       P0001_podo_R.png        S1, 224×224, training input
                    P0001_podo_L_full.png  P0001_podo_R_full.png   same CLAHE pass, full res — ROI marking (VIA)
                    P0001_podo_L_original.png  ..._R_original.png  color, pre-grayscale/CLAHE — XAI overlay "original"
  thermal/P0001/
    image/          P0001_thermal.png
    radiometric/    P0001_thermal.tiff          once the SDK is wired
  meta/P0001.json   non-authoritative mirror of the commit record, for manual inspection only
                     (SQLite wins if the two ever disagree)
```

The **raw** image is the source of truth; everything under `preprocessing/` is a **regenerable
cache**. When the pipeline settings change (see below), re-run preprocessing over the raw images —
do not treat any of the L/R variants as archival. **S2** (left foot flipped) is not stored; it is
generated from S1 at dataset-prep time (`create_s2_dataset` in the notebook).

`_full.png` and `_original.png` share the exact same (H, W) per case — grayscale/CLAHE/3-channel
conversion are pixel-wise ops that never touch image dimensions, only the 224×224 resize does (and
that only happens for the training file). ROI boxes are marked on `_full.png` in VIA, so their
coordinates line up 1:1 on `_original.png` with no rescaling — that's the reference frame Grad-CAM
etc. should be rescaled back onto for overlay/pointing-game evaluation later, not the raw camera
photo (which has both feet + background and doesn't correspond to a single per-foot prediction).

## Preprocessing = one shared module

`preprocessing.py` is extracted from `Image_Preprocessing_Pipeline.ipynb` and is the single source
of truth for the podoscope pipeline. Current settings (the tunable knobs):

| stage | setting |
|-------|---------|
| segmentation (HMRF-EM) | K=3, beta=1.5, GMM max_iter=80 |
| dilation | vertical kernel = 12% of image height (min 10px), horizontal = 5px |
| CLAHE | clip_limit=3.5, tile 8×8 |
| grayscale | 0.299R + 0.587G + 0.114B |
| resize | 224×224, bilinear |
| scaling | ÷255 → [0,1] (applied at model-load; the saved PNG is 0–255) |

Thermal has no preprocessing here — this pipeline is optical/pressure-specific. Thermal is stored
raw (+ radiometric later).

## The camera is the only thing left

All capture goes through `CaptureSource.grab(modality, rid) -> PNG bytes` in `capture_source.py`.

- `SimulatedSource` — podoscope returns `sample/P001.png`, thermal returns a placeholder. Active now.
- `UsbCameraSource` — **TODO**. Implement `grab()` and run with `CAPTURE_SOURCE=usb`. Nothing else
  changes. podoscope: `cv2.VideoCapture`; thermal: vendor SDK (colourised frame for the PNG **and**
  the radiometric array saved to `thermal/{rid}/radiometric/`).

## API

Full per-endpoint detail (payload/response/who calls it) is in
[`docs/notes/api/`](docs/notes/api/). Summary:

| Method | Path                       | Purpose                                             |
|--------|----------------------------|------------------------------------------------------|
| GET    | `/api/health`              | mode probe, current source, next id — no auth needed |
| POST   | `/api/login` / `/api/logout` | shared team password session                       |
| GET    | `/api/session`             | is the current cookie valid — no auth needed          |
| GET    | `/api/cases`               | cases that have a CRF form, with capture status       |
| POST   | `/api/session/new`         | mint next Research ID                                 |
| GET/POST/DELETE `/api/crf[/{pid}]` | CRF-07 form CRUD                              |
| GET/POST `/api/nurses`     | nurse-name dropdown source                            |
| POST   | `/api/capture`             | grab one modality, write raw (409 without a CRF form) |
| POST   | `/api/preprocess`          | segment + L/R + CLAHE the podoscope raw               |
| GET    | `/api/file/{path}`         | serve a stored file                                   |
| POST   | `/api/commit`              | finalize a case's captures                            |
| GET    | `/api/manifest`            | list committed cases                                  |
| GET/POST/DELETE `/api/roi[/{rid}]` | VIA 2 project JSON + region-count summary     |

## Tests

Backend (pytest, isolated SQLite DB per test — never touches the real `data/`), 51 tests:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # first time only
pytest tests/ -v
```

Frontend (vitest — covers `lib/crfScoring.ts`, the IWGDF scoring engine), 39 tests:

```bash
cd frontend
npm test
```

## Before real collection

1. Implement `UsbCameraSource.grab()` (the one TODO) once the devices are on the PC.
2. Lock PNG resolution to the podoscope's native output.
3. Point `DATA_DIR` at a folder that auto-backs-up to a second drive (remember: with WAL enabled,
   back up `app.db` *and* its `-wal`/`-shm` sidecar files, or `PRAGMA wal_checkpoint(TRUNCATE)` first).
4. Dry-run 2–3 test cases and load them into training.
