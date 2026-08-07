# Capture App

Local-first app for collecting paired **Podoscope + Thermal** foot images per patient at
Buddhachinaraj Hospital. Runs today with a **simulated camera** (the podoscope returns a real
sample footprint so preprocessing produces meaningful output). When the USB cameras arrive, the
**only** code to write is one capture class (`capture_source.py`).

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate     # first time only
pip install -r requirements.txt                         # first time only
uvicorn server:app --host 127.0.0.1 --port 8000
# open http://127.0.0.1:8000/
```

Opening it through the server = **live mode** (files land under `./data/`, preprocessing runs).
Opening `static/index.html` as a plain file = **demo mode** (browser-only, nothing written, no
preprocessing) — handy for the hospital pitch. The page detects which mode it is in and shows a
badge.

## Flow

1. **เริ่มเคสใหม่** → server mints the next Research ID (counts committed cases only). Write it on
   the paper form.
2. Capture **podoscope** → the preprocessing pipeline runs automatically and shows the segmented
   left/right feet for QC (catch a bad capture on the spot).
3. Capture **thermal**.
4. **ยืนยันและบันทึก** → writes the files and `meta/{rid}.json`, appends the manifest.

## On-disk layout (modality-first)

```
data/
  podo/P0001/
    raw/            P0001_podo.png              raw podoscope (source of truth)
    preprocessing/  P0001_podo_L.png  P0001_podo_R.png   S1, auto-generated
  thermal/P0001/
    image/          P0001_thermal.png
    radiometric/    P0001_thermal.tiff          once the SDK is wired
  meta/P0001.json   patient-level record (points into both modalities)
  manifest.csv      one row per committed patient
```

The **raw** image is the source of truth; the preprocessed L/R is a **regenerable cache**. When the
pipeline settings change (see below), re-run preprocessing over the raw images — do not treat the
cached L/R as archival. **S2** (left foot flipped) is not stored; it is generated from S1 at
dataset-prep time (`create_s2_dataset` in the notebook).

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

| Method | Path                  | Purpose                                        |
|--------|-----------------------|------------------------------------------------|
| GET    | `/api/health`         | mode probe, current source, next id            |
| POST   | `/api/session/new`    | mint next Research ID                           |
| POST   | `/api/capture`        | grab one modality, write raw                    |
| POST   | `/api/preprocess`     | segment + L/R + CLAHE the podoscope raw         |
| GET    | `/api/file/{path}`    | serve a stored file                             |
| POST   | `/api/commit`         | write meta JSON + append manifest               |
| GET    | `/api/manifest`       | list committed patients                         |

## Tests

Backend (pytest, isolated SQLite DB per test — never touches the real `data/`):

```bash
pip install -r requirements.txt -r requirements-dev.txt   # first time only
pytest tests/ -v
```

Frontend (vitest — currently covers `lib/crfScoring.ts`, the IWGDF scoring engine):

```bash
cd frontend
npm test
```

## Before real collection

1. Implement `UsbCameraSource.grab()` (the one TODO) once the devices are on the PC.
2. Lock PNG resolution to the podoscope's native output.
3. Point `DATA_DIR` at a folder that auto-backs-up to a second drive.
4. Dry-run 2–3 test cases and load them into training.
