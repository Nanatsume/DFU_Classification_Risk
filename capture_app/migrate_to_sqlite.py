"""One-off migration: data/crf/*.json, data/roi/*.json, data/meta/*.json, data/manifest.csv
-> data/app.db (SQLite).

Idempotent — every write is an upsert, so running this twice produces no duplicate rows. Not run
automatically on server startup (a migration should never fire as a side effect of just booting
the app); run it by hand once before the first auth-gated boot:

    cd capture_app
    .venv\\Scripts\\activate
    python migrate_to_sqlite.py

Safe to re-run any time — e.g. after restoring flat-file backups, or to double check nothing was
missed.
"""
from __future__ import annotations

import csv
import json

import db

BASE = db.BASE
DATA_DIR = db.DATA_DIR


def migrate_crf() -> int:
    crf_dir = DATA_DIR / "crf"
    if not crf_dir.exists():
        return 0
    n = 0
    for p in sorted(crf_dir.glob("P*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  skip {p.name}: invalid JSON")
            continue
        pid = rec.get("pid") or p.stem
        data = rec.get("data") or {}
        db.save_crf(
            pid=pid,
            nurse=rec.get("nurse", ""),
            nurse2=rec.get("nurse2", ""),
            saved_at=rec.get("savedAt", ""),
            fields=data.get("fields", {}),
            derived=data.get("derived", {}),
            schema_version=rec.get("schema_version", "1.0"),
        )
        n += 1
    return n


def migrate_meta() -> int:
    """data/meta/{rid}.json — one file per committed case, written by POST /api/commit.
    Populates cases, captures, preprocessing."""
    meta_dir = DATA_DIR / "meta"
    if not meta_dir.exists():
        return 0
    n = 0
    for p in sorted(meta_dir.glob("P*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  skip {p.name}: invalid JSON")
            continue
        rid = rec.get("research_id") or p.stem
        captured_at = rec.get("captured_at", "")
        db.upsert_case(rid, created_at=captured_at)

        podo = rec.get("podoscope") or {}
        if podo.get("raw"):
            db.save_capture(rid, "podoscope", podo["raw"], captured_at)
        prepro = podo.get("preprocessing") or {}
        for side in ("L", "R"):
            if prepro.get(side):
                db.save_preprocessing(rid, side, prepro[side])

        thermal = rec.get("thermal") or {}
        if thermal.get("image"):
            db.save_capture(rid, "thermal", thermal["image"], captured_at)

        n += 1
    return n


def migrate_manifest() -> int:
    """data/manifest.csv — the committed-case append log. Populates the `commits` table
    (podo_raw/podo_prepro/thermal are reconstructed from captures/preprocessing at read time,
    see db.list_commits(), so they aren't stored again here)."""
    path = DATA_DIR / "manifest.csv"
    if not path.exists():
        return 0
    n = 0
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rid = row.get("research_id", "").strip()
            if not rid:
                continue
            db.upsert_case(rid, created_at=row.get("captured_at", ""))
            db.save_commit(
                research_id=rid,
                status=row.get("status", ""),
                committed_at=row.get("captured_at", ""),
                operator="",
            )
            n += 1
    return n


def migrate_roi() -> int:
    roi_dir = DATA_DIR / "roi"
    if not roi_dir.exists():
        return 0
    n = 0
    for p in sorted(roi_dir.glob("P*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"  skip {p.name}: invalid JSON")
            continue
        rid = rec.get("rid") or p.stem
        db.save_roi(
            rid=rid,
            saved_at=rec.get("savedAt", ""),
            summary=rec.get("summary", {}),
            project=rec.get("project", {}),
        )
        n += 1
    return n


def main() -> None:
    db.init_db()
    print(f"DB at {db.DB_PATH}")

    n_crf = migrate_crf()
    print(f"crf_forms:  {n_crf} record(s) from data/crf/*.json")

    n_meta = migrate_meta()
    print(f"meta:       {n_meta} record(s) from data/meta/*.json (-> cases/captures/preprocessing)")

    n_manifest = migrate_manifest()
    print(f"commits:    {n_manifest} row(s) from data/manifest.csv")

    n_roi = migrate_roi()
    print(f"roi:        {n_roi} record(s) from data/roi/*.json")

    with db.tx() as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                  for t in ("cases", "crf_forms", "captures", "preprocessing", "commits",
                            "roi_annotations", "nurses")}
    print("\nDB row counts:")
    for t, c in counts.items():
        print(f"  {t:16s} {c}")


if __name__ == "__main__":
    main()
