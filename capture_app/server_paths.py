"""Where each of a case's files lives on disk.

Split out of server.py so tools/preprocess_one.py can write to exactly the same places without
importing the whole app — importing server.py boots it: init_db(), bootstrap_password(), the
static mounts. A worker process that only needs to know a filename should not do any of that.

EVERY PATH IS RESOLVED WHEN IT IS ASKED FOR, never captured at import.

That is not a style preference. The first version of this module held `DATA_DIR = db.DATA_DIR` as
a module constant, and the test suite promptly began writing patient image files into the real
data/ directory: conftest patches db.DATA_DIR and re-imports server, but server_paths was already
imported and kept the real path, so the database went to the temporary directory while the images
went to the live one. Reading db.DATA_DIR on each call means there is exactly one thing to patch
and no second copy to fall out of step with it.
"""
from __future__ import annotations

from pathlib import Path

import db


def data_dir() -> Path:
    """The directory everything else hangs off — honours DFU_DATA_DIR, and any test patch of it."""
    return db.DATA_DIR


def meta_dir() -> Path:
    return data_dir() / "meta"


def raw_path(rid: str, modality: str) -> Path:
    if modality == "podoscope":
        return data_dir() / "podo" / rid / "raw" / f"{rid}_podo.png"
    return data_dir() / "thermal" / rid / "image" / f"{rid}_thermal.png"


def prepro_path(rid: str, side: str) -> Path:
    return data_dir() / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}.png"


def prepro_full_path(rid: str, side: str) -> Path:
    """Full-resolution, CLAHE-enhanced but un-resized copy — for ROI annotation display only.
    The 224x224 file from prepro_path() is what training actually uses; this one exists purely
    because a human needs to see fine detail that survives shrinking to the model's input size."""
    return data_dir() / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}_full.png"


def prepro_original_path(rid: str, side: str) -> Path:
    """Color, post-segmentation, pre-grayscale/CLAHE copy — the "original" reference frame for
    XAI overlay later (Grad-CAM etc. rescale back onto this, not the raw camera photo, since the
    model only ever sees one segmented foot at a time). Same (H, W) as prepro_full_path() by
    construction, so ROI boxes marked on that file line up on this one with no rescaling."""
    return data_dir() / "podo" / rid / "preprocessing" / f"{rid}_podo_{side}_original.png"


def rel(p: Path) -> str:
    return p.relative_to(data_dir()).as_posix()


def url(p: Path) -> str:
    return "/api/file/" + rel(p)
