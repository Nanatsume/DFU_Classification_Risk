# Capture App

Local-first app for collecting diabetic foot ulcer (DFU) risk data at Buddhachinaraj Hospital —
paired **Podoscope + Thermal** foot images per patient, a **CRF-07 case record form** that
computes the IWGDF risk category live, and **ROI annotation** (VIA 2) for later XAI/Grad-CAM
work. FastAPI + SQLite backend, React + Vite (multi-page) + Tailwind + shadcn/ui frontend.

Podoscope capture over USB works (tested on a Logitech C615); **thermal** is the one piece still
waiting on hardware, and raises `NotImplementedError` until the radiometric device arrives. A
simulated source runs the whole flow with no hardware at all — see [Cameras](#cameras).

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

1. **เข้าสู่ระบบ** — one shared team password. Note that nothing here records *who* examined a
   patient or took a photograph: the study site asked that staff names not be stored, so the
   rosters and the nurse/photographer fields were removed outright.
2. **ถ่ายภาพ** (at the clinic) — type the patient's **HN** and press เริ่มเคส. The server mints the
   Research ID (`P0001`, `P0002`, ...) there and then, so every file is named for the research id
   from its first write and no hospital number ever reaches a filename. Capturing **podoscope**
   auto-runs the preprocessing pipeline and shows the segmented left/right feet for QC on the spot;
   then capture **thermal**; **ยืนยันและบันทึก** commits the case.

   The nurses have no time to fill a 30-field form with a patient in front of them, which is why
   the photographs come first and the form follows. See "Hospital numbers" below.
3. **กรอกฟอร์มทีหลัง** (CRF-07) — the history page lists every photographed case whose form is not
   filled in yet, with its HN. Look the patient up in the hospital's own annual-checkup record by
   that HN, transcribe the answers, and save against the same Research ID. Answers for LOPS
   (monofilament), PAD (ABI/TBI), deformity, and history are scored live into an IWGDF category
   (0–3) and a Positive/Negative label per foot.

   A form can also be started without photographs (the id is then minted on save, so an abandoned
   half-filled form costs no id).
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
  app.db            SQLite — source of truth for cases (incl. the HN), CRF forms, captures,
                     preprocessing, commits, ROI annotations, sessions, settings, audit log
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

## Cameras

All capture goes through `CaptureSource.grab(modality, rid) -> PNG bytes` in `capture_source.py`.
Choose one with `CAPTURE_SOURCE`; the default is `sim`, so the real camera is never used by
accident.

- `CAPTURE_SOURCE=sim` — `SimulatedSource`. Podoscope returns `sample/P001.png` (a real footprint,
  so preprocessing produces meaningful output), thermal returns a placeholder. No hardware needed.
- `CAPTURE_SOURCE=usb` — `UsbCameraSource`. **Podoscope works** (tested against a Logitech C615:
  1920×1080 MJPG, ~190 ms/frame, ~1–2.5 MB PNG). **Thermal still raises `NotImplementedError`** —
  the radiometric device is on order.

### Picking the right camera

The podoscope camera is selected **by name, on every capture**, not by a fixed index. This is not
over-engineering: a typical workstation enumerates the built-in webcam, a Windows Hello IR sensor,
and several *virtual* cameras (OBS, Logi Capture, NVIDIA Broadcast, LSVCam). A virtual camera
opens cleanly and returns frames, so `isOpened()` and `read()` both succeed while the "photo" is a
software placeholder — and DirectShow indices shift whenever one of them starts or a USB device is
replugged. Index-based selection fails silently, filing the wrong image under a real research id.

| env var | default | what it does |
|---|---|---|
| `PODO_CAMERA_NAME` | `Logi C615` | case-insensitive substring match against the device list |
| `PODO_CAMERA_INDEX` | *(unset)* | explicit cv2 index; wins over the name lookup. Escape hatch for machines without `pygrabber` |
| `PODO_CAMERA_WIDTH` / `_HEIGHT` | `1920` / `1080` | requested capture size; a smaller actual size is logged, not fatal |
| `PODO_CAMERA_WARMUP` | `20` | frames discarded before the keeper — this camera returns black frames until auto-exposure settles |

If no matching camera is attached, capture fails with a message naming every camera it *did* see,
rather than quietly falling back to whichever device happens to be at index 0.

Capture also refuses a near-uniform frame (lens cap on, podoscope light off, virtual-camera
placeholder) instead of storing a blank image against a patient.

To see what a machine enumerates:

```bash
python -c "import capture_source; print(capture_source.list_video_devices())"
```

## API

Full per-endpoint detail (payload/response/who calls it) is in
[`docs/notes/api/`](docs/notes/api/). Summary:

| Method | Path                       | Purpose                                             |
|--------|----------------------------|------------------------------------------------------|
| GET    | `/api/health`              | mode probe, current source, next id — no auth needed |
| POST   | `/api/login` / `/api/logout` | shared team password session                       |
| GET    | `/api/session`             | is the current cookie valid — no auth needed          |
| GET    | `/api/cases`               | cases that have a CRF form, with capture status       |
| POST   | `/api/session/new`         | reserve an id up front — no longer used by the UI     |
| GET/POST/DELETE `/api/crf[/{pid}]` | CRF-07 form CRUD; POST without `pid` mints the id |
| GET/POST `/api/nurses`     | nurse-name dropdown source                            |
| POST   | `/api/capture`             | grab one modality, write raw (409 without a CRF form) |
| POST   | `/api/preprocess`          | segment + L/R + CLAHE the podoscope raw               |
| GET    | `/api/file/{path}`         | serve a stored file                                   |
| POST   | `/api/commit`              | finalize a case's captures                            |
| GET    | `/api/manifest`            | list committed cases                                  |
| GET/POST/DELETE `/api/roi[/{rid}]` | VIA 2 project JSON + region-count summary     |

## Tests

Backend (pytest, isolated SQLite DB per test — never touches the real `data/`), 98 tests:

```bash
pip install -r requirements.txt -r requirements-dev.txt   # first time only
pytest tests/ -v
```

Frontend (vitest — covers `lib/crfScoring.ts`, the IWGDF scoring engine), 39 tests:

```bash
cd frontend
npm test
```

## Moving this to another machine

Nothing in the code is tied to a particular machine — no absolute paths, no hardcoded hostnames.
What does *not* travel is `.venv/` (absolute paths inside) and `data/` (both gitignored). One
command rebuilds both:

```powershell
git clone <repo>
cd capture_app
powershell -ExecutionPolicy Bypass -File setup.ps1
```

`setup.ps1` finds Python 3.12, creates the venv, installs the **exact tested versions**, creates
the database, **runs the whole test suite to prove the install is good**, and prints the cameras
it can see. It is safe to re-run: an existing venv is reused and the migration is idempotent.

Then start it:

```powershell
$env:APP_PASSWORD  = "your-team-password"
$env:CAPTURE_SOURCE = "usb"              # omit to stay on the simulator
$env:DFU_DATA_DIR   = "D:\dfu-data"      # optional — see "Where the data lives"
.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

`npm` is **not** needed on the target machine: the built frontend is committed in `static/` and the
backend serves it directly. Only rebuild (`cd frontend && npm install && npm run build`) if you
change the UI source.

Check the cameras any time — before the first clinic, or when capture picks the wrong image:

```bash
python tools/check_cameras.py
```

### Why there are lock files

`requirements.txt` states *intent* (six direct dependencies). `requirements.lock.txt` pins **every**
package, transitive ones included, to the versions this app was actually tested on — and that is
what `setup.ps1` installs.

Pinning only the direct dependencies is not enough. Re-resolving `requirements.txt` the day the
lock was written already produced **starlette 1.6.0 where the app was tested on 1.4.1**, plus newer
pydantic, anyio and click — all under an unchanged FastAPI pin. That kind of drift is silent, and
the segmentation in `preprocessing.py` is numerically sensitive to numpy/scipy/opencv, so a fresh
install months from now must reproduce the pipeline the collected images were validated against.

Regenerate the locks after deliberately upgrading something (then re-run the tests, and re-run the
pipeline over `sample/P001.png` to confirm the output is unchanged):

```bash
.venv\Scripts\python.exe tools/lock_requirements.py
```

> **Note for Windows PowerShell 5.1**: `setup.ps1` is saved as UTF-8 **with BOM** on purpose. Without
> it, 5.1 decodes `.ps1` files using the system ANSI code page — cp874 on a Thai-locale machine —
> which mangles the non-ASCII characters in the file and breaks the parse. Keep the BOM if you edit it.

### Backing it up to OneDrive

`tools/backup.py` uploads everything the app owns to an encrypted cloud remote through rclone.
`tools/setup_backup.ps1` installs rclone, walks through the one-time sign-in, and registers a
nightly scheduled task:

```powershell
powershell -ExecutionPolicy Bypass -File tools\setup_backup.ps1
.venv\Scripts\python.exe toolsackup.py --dry-run     # check it end to end
```

The rclone config file it produces is portable — copy it to the second machine and backups work
there without signing in again.

What goes up: `app.db` (including the hand-drawn ROI annotations, the one thing here that cannot
be recomputed), plus `podo/`, `thermal/` and `meta/`. The preprocessed images travel too rather
than being regenerated on restore: regenerating costs about a minute per image and the result
needs a human to QC it again.

Three properties worth keeping if you change any of this:

- **The live database is never synced in place.** A file-sync client can copy `app.db` mid-write
  or restore an older copy over a newer one, and with WAL that corrupts it. `backup.py` writes a
  consistent snapshot with sqlite3's backup API and uploads only the snapshot. Never point
  `DFU_DATA_DIR` inside a OneDrive/Drive/Dropbox folder.
- **Uploads use `rclone copy`, never `sync`.** The remote only ever gains files, so a case cannot
  disappear from the cloud because something happened to it locally. `app.db` legitimately changes
  every run, and `--backup-dir` keeps each previous version under `archive/<timestamp>/`, so a
  database corrupted today is still recoverable from yesterday.
- **Failure is visible.** Every run writes `backup_status.json`, `/api/backup-status` serves it,
  and the home page shows a banner when the last backup failed or is more than 36 hours old. A
  backup everyone believes in but which stopped three weeks ago is worse than none.

The rclone remote is encrypted (`crypt`), so filenames and contents are unreadable in the cloud.
**Keep both crypt passwords somewhere safe and offline — without them the backup cannot be
restored by anyone, including you.**

### Hospital numbers

`cases.hn` is the only directly identifying value this app stores, and it exists because the
workflow demands it: photographs are taken against an HN at the clinic, and the CRF is transcribed
afterwards from the hospital's own annual-checkup record — which is filed by HN and carries no
research id. The HN is the only thing linking the two.

It is confined to that one column on purpose. It does **not** appear in image filenames, the
`meta/*.json` mirrors, `fields_json`, either CSV export, or the cloud backup (`tools/backup.py`
blanks it in the snapshot it uploads, then VACUUMs, so the cloud copy is pseudonymous even before
the remote's own encryption).

Keeping it at all is a considered trade rather than an oversight. The CRF is transcribed by hand,
and transcription goes wrong sometimes; without the HN a suspect value can never be checked against
the source again. When collection is finished and no such check remains, `DELETE /api/hn` drops
every hospital number at once and the dataset holds no direct identifier. That is irreversible.

`GET /api/hn` reports how many cases still carry one.

### Where the data lives

`DFU_DATA_DIR` relocates everything the app owns — `app.db` and the whole image tree. Unset, it
defaults to `./data` inside the checkout, which is fine for development and wrong for real
collection. Point it at a drive that gets backed up.

> With WAL enabled, a backup must copy `app.db` **and** its `-wal`/`-shm` sidecars, or run
> `PRAGMA wal_checkpoint(TRUNCATE)` first — copying `app.db` alone can lose recent commits.

### Thai-locale Windows

The hospital workstation runs a Thai code page (cp874) console. `preprocessing.py` (exported from
the research notebook) prints `✓ ÷ ├ 📂`, which cp874 cannot encode — that used to kill `import
server` outright and crash every podoscope capture. `stdio_utf8.force_utf8_stdio()` now runs first
thing in `server.py` and `migrate_to_sqlite.py`, so no `PYTHONIOENCODING` workaround is needed.
`tests/test_console_encoding.py` guards it in a real subprocess (pytest's own output capture hides
the bug, which is how it survived this long).

## Before real collection

1. ~~Implement `UsbCameraSource.grab()`~~ — done for the podoscope; **thermal still TODO** when the
   radiometric device arrives (colourised frame for the PNG **and** the temperature array saved to
   `thermal/{rid}/radiometric/`).
2. Confirm `PODO_CAMERA_WIDTH/HEIGHT` matches the podoscope's native output once it is mounted in
   its final rig — the C615 defaults here are the tested maximum, not necessarily the right framing.
3. Set `DFU_DATA_DIR` to a backed-up folder (see above).
4. Dry-run 2–3 test cases and load them into training.
5. Revisit `auth.py`'s note on TLS before ever serving beyond `127.0.0.1`.
