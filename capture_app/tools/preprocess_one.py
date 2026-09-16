"""Preprocess one case's podoscope capture, in a process of its own.

    python tools/preprocess_one.py P0001

Prints a JSON result on the last line of stdout and exits 0 on success, 1 on failure.

WHY A SEPARATE PROCESS

The server crashed with SIGSEGV -- no Python traceback, so the fault was inside a native library
-- while segmentation was running in a background thread and the camera was used again from a
request thread. That combination is what the new workflow encourages: capture, then photograph
the next patient while the first one is still being processed. OpenCV's DirectShow capture and
the OpenCV/scipy work inside the pipeline then run concurrently in one address space.

The crash could not be reproduced deliberately in three attempts, so the exact interaction is
still unknown. Rather than guess at a lock that might cover it, the two are separated at the
process boundary, where no amount of native-library state can be shared: the camera lives in the
server process, segmentation lives here. A crash in this child also stays in this child -- the
case fails with a message instead of taking the clinic's server down mid-session.

The cost is a fresh interpreter and numpy/scipy/cv2 import per case, about two seconds against a
sixty-to-ninety second job.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stdio_utf8 import force_utf8_stdio  # noqa: E402

force_utf8_stdio()

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import db  # noqa: E402
import server_paths  # noqa: E402
from preprocessing import preprocess_foot_image  # noqa: E402


def main(rid: str) -> int:
    raw = server_paths.raw_path(rid, "podoscope")
    if not raw.exists():
        print(json.dumps({"status": "failed", "error": f"no podoscope capture for {rid}"}))
        return 1

    try:
        result = preprocess_foot_image(str(raw))
        if result is None:
            raise RuntimeError("could not separate two feet — check the capture")
    except Exception as e:                                   # noqa: BLE001 — reported as JSON
        print(json.dumps({"status": "failed", "error": f"{type(e).__name__}: {e}"},
                         ensure_ascii=False))
        return 1

    out = {}
    for side, key in (("L", "left_foot"), ("R", "right_foot")):
        side_word = "left" if side == "L" else "right"
        p = server_paths.prepro_path(rid, side)
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray((result[key] * 255).astype(np.uint8)).save(p)
        db.save_preprocessing(rid, side, server_paths.rel(p))
        out[side] = server_paths.url(p)
        Image.fromarray(result[f"{side_word}_foot_full"]).save(
            server_paths.prepro_full_path(rid, side))
        Image.fromarray(result[f"{side_word}_foot_original"]).save(
            server_paths.prepro_original_path(rid, side))

    print(json.dumps({"status": "ok", "left_url": out["L"], "right_url": out["R"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"status": "failed", "error": "usage: preprocess_one.py <research_id>"}))
        raise SystemExit(1)
    raise SystemExit(main(sys.argv[1]))
