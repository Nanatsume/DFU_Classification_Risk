"""Force stdout/stderr to UTF-8 at process start.

Why this exists: preprocessing.py is lifted straight out of the research notebook and prints
progress with characters the notebook rendered fine — ✓, ÷, ├, 📂. On a Windows console running
the Thai code page (cp874, the default on a Thai-locale Windows — i.e. the hospital workstation
this ships to) encoding any of them raises UnicodeEncodeError. Two of those prints are fatal:

  - preprocessing.py line 33 runs at *import* time, so `import server` itself dies and uvicorn
    never binds a port. The app does not start at all.
  - preprocess_foot_image() prints three more, and server.py calls it on every podoscope
    capture — so even a server that somehow booted would crash mid-capture.

Rewriting every print is the obvious alternative, but the prints keep drifting back in each time
the notebook is re-exported, and third-party libraries print non-ASCII too. Fixing the stream
once, at the entry point, covers all of it permanently.

errors="replace" rather than "strict": a decorative glyph that cannot be represented should
degrade to "?" in the log, never take down a capture that a patient is waiting on.
"""
from __future__ import annotations

import sys


def force_utf8_stdio() -> None:
    """Call once, as early as possible, before importing anything that prints."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:  # None for a captured/replaced stream (e.g. under pytest)
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass  # already detached or not reconfigurable — nothing to do, and not fatal
