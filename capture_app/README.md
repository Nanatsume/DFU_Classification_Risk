# Capture App — data collection scaffold

Local-first app for collecting paired **Podoscope + Thermal** foot images per patient at
Buddhachinaraj Hospital. Front-end runs in the browser, back-end is a local server that mints the
Research ID and writes files to disk. No cloud, no PHI in the image data.

## Architecture

```
 ┌─────────────┐  localhost   ┌──────────────────────┐   writes    ┌──────────┐
 │  Browser UI │ ───────────► │  Local server (this) │ ──────────► │  ./data/ │
 │ (front-end) │ ◄─────────── │  FastAPI + OpenCV     │             └──────────┘
 └─────────────┘  JSON/PNG    └──────────────────────┘
```

- **Podoscope** is an ordinary USB webcam. The browser can grab frames via `getUserMedia`
  and POST the PNG, or the server can grab it with OpenCV. Either works.
- **Thermal** is a radiometric USB device. The browser only ever sees a colourised preview,
  so the **temperature values must be pulled server-side through the device SDK** and saved
  alongside the PNG. This is the one capture path that cannot live purely in the browser.

## Research ID = single source of truth

The server owns a persistent counter (`counter.txt`). The browser never types the ID and never
sees the HN. The HN ↔ Research ID link exists only on the paper form, so everything under
`./data/` is de-identified.

A cancelled session consumes its number (gaps are fine, numbers are never reused).

## On-disk layout

```
data/
  P0001/
    P0001_podo.png        # lossless PNG
    P0001_thermal.png     # colourised preview
    P0001_thermal.tiff    # radiometric temperature array (from SDK)  [TODO]
    P0001.json            # per-patient manifest (see schema below)
  P0002/
    ...
  manifest.csv            # one row appended per committed patient
```

## Per-patient JSON (schema_version 1.0)

```json
{
  "schema_version": "1.0",
  "research_id": "P0001",
  "captured_at": "2026-07-27T14:32:10+07:00",
  "operator": "",
  "images": { "podoscope": ["P0001_podo.png"], "thermal": ["P0001_thermal.png"] },
  "status": "complete",
  "app_version": "demo-0.1"
}
```

`status` is `complete` or `partial` (a modality was skipped, e.g. thermal device down that day).
Saving is never blocked when one modality is missing — the flag records it instead.

## API (see server.py)

| Method | Path              | Purpose                                   |
|--------|-------------------|-------------------------------------------|
| POST   | `/session/new`    | mint next Research ID                     |
| POST   | `/capture/{rid}`  | store one PNG blob for a modality         |
| POST   | `/commit/{rid}`   | write JSON + append manifest, close case  |
| GET    | `/manifest`       | list committed patients (completeness)    |

## Before real collection

1. Confirm both cameras enumerate as USB video devices on the collection PC.
2. Wire the thermal SDK into `capture_thermal_radiometric()` (the only real TODO).
3. Lock PNG resolution to whatever the podoscope outputs natively.
4. Point `DATA_DIR` at a folder that is auto-backed-up to a second drive.
5. Dry-run 2–3 test cases end-to-end and load them into the preprocessing pipeline.

The front-end demo (`../capture_app_demo.html`) shows the intended UI and can run standalone with
simulated capture for the hospital presentation.
