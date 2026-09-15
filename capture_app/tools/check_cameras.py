"""Show which cameras this machine sees, and which one the podoscope resolves to.

    python tools/check_cameras.py

Run it on a new machine before the first clinic, and any time capture picks the wrong image.
Exits non-zero if the podoscope cannot be resolved, so setup scripts can react to it.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import capture_source as cs  # noqa: E402


def main() -> int:
    devices = cs.list_video_devices()
    if not devices:
        print("    (could not enumerate cameras — pygrabber not installed, or not Windows)")
    for i, name in enumerate(devices):
        print(f"    [{i}] {name}")

    try:
        index = cs.resolve_podoscope_index()
    except cs.CaptureError as e:
        print(f"    -> podoscope NOT found: {e}")
        print("       Plug it in, or set PODO_CAMERA_NAME / PODO_CAMERA_INDEX.")
        return 1

    label = devices[index] if index < len(devices) else "(index set explicitly)"
    print(f"    -> podoscope resolves to index {index}: {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
