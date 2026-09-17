"""Back up everything the capture app owns to a cloud remote, via rclone.

    python tools/backup.py                  # normal run
    python tools/backup.py --dry-run        # show what would be uploaded, upload nothing
    python tools/backup.py --local-only     # snapshot to the staging folder, skip the upload

Run it from Task Scheduler once a night; `tools/setup_backup.ps1` registers that for you.

WHAT IS BACKED UP
    app.db          every case, CRF form, commit, audit row -- and the hand-drawn ROI
                    annotations, which are the only thing here a person cannot reproduce by
                    re-running something. Hospital numbers are stripped from the copy that is
                    uploaded (see snapshot_database) so the cloud never holds an identifier.
    podo/           raw captures (the source of truth) and their preprocessed siblings. The
                    preprocessed files are nominally a regenerable cache, but regenerating costs
                    about a minute per image and the result needs a human to QC it again, so they
                    are backed up rather than recomputed.
    thermal/        same, once the radiometric device is wired up.
    meta/           non-authoritative mirrors; tiny, and harmless to carry along.
    camera-test/    hardware smoke-test shots from the camera-test page (server.py's
                    /api/camera-test/capture) -- not a case, not a patient, but still a real
                    photograph someone took on purpose and would rather not lose.

HOW IT AVOIDS THE USUAL WAYS THIS GOES WRONG

    A live SQLite database must never be handed to a file-sync client. With WAL enabled the
    sync client can copy app.db mid-write, or restore an older copy over a newer one, and the
    result is a corrupt database. So the DB is never synced in place: sqlite3's backup API writes
    a consistent snapshot to a staging folder, and only that snapshot is uploaded. DFU_DATA_DIR
    itself should never sit inside a synced folder.

    Uploads use `rclone copy`, not `sync`: files are only ever added to the remote. A research
    archive should not lose a case in the cloud because something happened to it locally. The one
    file that legitimately changes every run is app.db, and --backup-dir keeps each previous
    version under archive/<timestamp>/ rather than overwriting it, so a database that gets
    corrupted today can still be recovered from yesterday.

    Every run writes backup_status.json next to the data. The app reads it so a backup that has
    quietly stopped shows up in the UI -- a backup you believe in but which stopped running three
    weeks ago is worse than having none at all.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stdio_utf8 import force_utf8_stdio  # noqa: E402

force_utf8_stdio()

import db  # noqa: E402  (imported after the stdio guard, like server.py)

# The rclone remote to upload into, e.g. "dfu-crypt:" for an encrypted remote wrapping OneDrive.
# Set it in the environment (setup_backup.ps1 bakes it into the scheduled task).
REMOTE = os.environ.get("DFU_BACKUP_REMOTE", "")
RCLONE = os.environ.get("RCLONE_EXE", "rclone")
# Folders under DATA_DIR that are worth uploading. `sessions` live in the DB, not on disk; nothing
# else in DATA_DIR is data we could not rebuild.
IMAGE_DIRS = ("podo", "thermal", "meta", "camera-test")
STATUS_FILENAME = "backup_status.json"


def log(msg: str) -> None:
    print(f"[backup] {msg}", flush=True)


def snapshot_database(data_dir: Path, staging: Path) -> Path:
    """Write a consistent copy of app.db into staging, leaving the live DB untouched.

    sqlite3's own backup API is used rather than copying the file: it takes a read lock and
    produces a valid database even while the server is mid-write, and it folds the WAL in, so the
    single file that lands in the cloud is complete on its own without its -wal/-shm sidecars.
    """
    src_path = data_dir / "app.db"
    if not src_path.exists():
        raise FileNotFoundError(f"no database at {src_path} — is DFU_DATA_DIR set correctly?")
    out = staging / "app.db"
    src = sqlite3.connect(str(src_path))
    try:
        src.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        dst = sqlite3.connect(str(out))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    # Blank the hospital numbers in the copy that leaves this machine. cases.hn is the one
    # directly identifying value the app holds; it exists so a transcribed CRF can be checked
    # against the hospital's own record, which is a local task. The cloud copy has no use for it,
    # and without it the uploaded dataset is pseudonymous rather than identifiable — a materially
    # different thing to be holding in someone else's storage, encrypted remote or not.
    scrubbed = sqlite3.connect(str(out))
    try:
        cols = {r[1] for r in scrubbed.execute("PRAGMA table_info(cases)")}
        if "hn" in cols:
            n = scrubbed.execute(
                "UPDATE cases SET hn=NULL WHERE hn IS NOT NULL AND hn != ''").rowcount
            scrubbed.commit()
            if n:
                log(f"removed {n} hospital number(s) from the snapshot before upload")
        scrubbed.execute("VACUUM")  # so the blanked values are not recoverable from free pages
        scrubbed.commit()
    finally:
        scrubbed.close()

    log(f"database snapshot: {out.stat().st_size / 1024:.0f} KB")
    return out


def count_cases(snapshot: Path) -> int:
    conn = sqlite3.connect(str(snapshot))
    try:
        return conn.execute("SELECT COUNT(*) FROM crf_forms").fetchone()[0]
    except sqlite3.Error:
        return -1
    finally:
        conn.close()


def rclone(args: list[str], dry_run: bool) -> subprocess.CompletedProcess:
    cmd = [RCLONE, *args]
    if dry_run:
        cmd.append("--dry-run")
    log(" ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def upload(source: Path, dest: str, archive: str, dry_run: bool) -> str:
    """copy (never sync) so the remote only ever gains files; replaced files go to `archive`."""
    result = rclone(
        ["copy", str(source), dest, "--backup-dir", archive,
         "--transfers", "4", "--checkers", "8", "--stats", "10s", "--stats-one-line"],
        dry_run,
    )
    if result.returncode != 0:
        raise RuntimeError(f"rclone failed ({result.returncode}): {result.stderr.strip()[:500]}")
    return (result.stderr or result.stdout).strip().splitlines()[-1:][0] if (
        result.stderr or result.stdout).strip() else ""


def write_status(data_dir: Path, **fields) -> None:
    status = {"updated_at": datetime.datetime.now().astimezone().isoformat(), **fields}
    (data_dir / STATUS_FILENAME).write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="show what would upload, upload nothing")
    ap.add_argument("--local-only", action="store_true", help="snapshot only, never call rclone")
    args = ap.parse_args()

    data_dir = db.DATA_DIR
    log(f"data dir: {data_dir}")
    started = datetime.datetime.now()
    stamp = started.strftime("%Y-%m-%d_%H%M%S")

    staging = Path(tempfile.mkdtemp(prefix="dfu-backup-"))
    try:
        snapshot = snapshot_database(data_dir, staging)
        cases = count_cases(snapshot)
        log(f"{cases} case(s) with a CRF form")

        if args.local_only:
            keep = data_dir / "backup-staging"
            keep.mkdir(exist_ok=True)
            shutil.copy2(snapshot, keep / "app.db")
            log(f"local-only: snapshot kept at {keep / 'app.db'}")
            write_status(data_dir, ok=True, mode="local-only", cases=cases, uploaded_bytes=0)
            return 0

        if not REMOTE:
            log("DFU_BACKUP_REMOTE is not set — run tools/setup_backup.ps1 first.")
            write_status(data_dir, ok=False, error="DFU_BACKUP_REMOTE not set", cases=cases)
            return 2

        dest = REMOTE.rstrip("/") + "/current"
        archive = REMOTE.rstrip("/") + f"/archive/{stamp}"

        upload(snapshot.parent, dest, archive, args.dry_run)      # the DB snapshot
        for name in IMAGE_DIRS:                                    # then the image tree
            folder = data_dir / name
            if folder.is_dir():
                upload(folder, f"{dest}/{name}", f"{archive}/{name}", args.dry_run)
            else:
                log(f"skipping {name}/ — not present yet")

        elapsed = (datetime.datetime.now() - started).total_seconds()
        log(f"done in {elapsed:.0f}s")
        write_status(data_dir, ok=True, mode="dry-run" if args.dry_run else "upload",
                     cases=cases, remote=REMOTE, elapsed_seconds=round(elapsed, 1))
        return 0

    except Exception as e:
        log(f"FAILED: {type(e).__name__}: {e}")
        try:
            write_status(db.DATA_DIR, ok=False, error=f"{type(e).__name__}: {e}")
        except Exception:
            pass
        return 1
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
