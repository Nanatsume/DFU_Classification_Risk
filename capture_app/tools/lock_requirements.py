"""Regenerate requirements.lock.txt / requirements-dev.lock.txt from the current venv.

Run this from inside the venv you have actually tested:

    .venv\\Scripts\\python.exe tools\\lock_requirements.py

It splits `pip freeze` into runtime and test-only halves by asking pip to resolve
requirements.txt (without installing anything) and treating that resolution as the runtime set —
so the lock records the versions you *tested*, not whatever PyPI happens to serve today.

Pinning the six direct dependencies is not enough on its own: re-resolving requirements.txt the
day this was written already produced starlette 1.6.0 against a tested 1.4.1, under an unchanged
FastAPI pin. Transitive drift like that is invisible until something breaks in the clinic.
"""
from __future__ import annotations

import datetime
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
# Wheels that only exist on Windows; keep them optional so the lock still installs elsewhere.
WINDOWS_ONLY = {"pygrabber", "comtypes"}


def resolve_runtime_names() -> set[str]:
    """Names pip would install for requirements.txt, transitive deps included."""
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--dry-run", "--ignore-installed",
             "--quiet", "-r", str(APP_DIR / "requirements.txt"), "--report", str(report)],
            check=True, cwd=APP_DIR,
        )
        data = json.loads(io.open(report, encoding="utf-8").read())
    return {item["metadata"]["name"].lower() for item in data["install"]}


def installed_packages() -> dict[str, tuple[str, str]]:
    out = subprocess.run([sys.executable, "-m", "pip", "freeze"],
                         capture_output=True, text=True, check=True).stdout
    pkgs = {}
    for line in out.splitlines():
        if "==" in line and not line.startswith("#"):
            name, version = line.split("==", 1)
            pkgs[name.strip().lower()] = (name.strip(), version.strip())
    return pkgs


def render(names: set[str], installed: dict[str, tuple[str, str]]) -> str:
    lines = []
    for key in sorted(names):
        name, version = installed[key]
        line = f"{name}=={version}"
        if key in WINDOWS_ONLY:
            line += ' ; sys_platform == "win32"'
        lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> None:
    runtime = resolve_runtime_names()
    installed = installed_packages()

    missing = sorted(runtime - installed.keys())
    if missing:
        sys.exit(
            "Refusing to write a lock file: these runtime packages are not installed in this "
            "venv, so no tested version exists to pin: " + ", ".join(missing) +
            "\nRun `pip install -r requirements.txt` first."
        )

    py = "%d.%d" % sys.version_info[:2]
    today = datetime.date.today().isoformat()
    header = (
        "# GENERATED — do not hand-edit. Regenerate with: python tools/lock_requirements.py\n"
        "#\n"
        f"# Exact versions of EVERY package, direct and transitive, as installed on the machine\n"
        f"# this app was developed and tested on (Python {py}). requirements.txt states intent;\n"
        "# this file reproduces the tested environment, which is what a second machine needs.\n"
        "#\n"
        "# Pinning only the direct dependencies is not enough: re-resolving them can pick a newer\n"
        "# starlette/pydantic/anyio under an unchanged FastAPI pin, and that drift is silent.\n"
        "#\n"
        f"# Generated {today}.\n"
    )
    (APP_DIR / "requirements.lock.txt").write_text(
        header + render(runtime, installed), encoding="utf-8", newline="\n")

    dev_header = (
        "# GENERATED — do not hand-edit. Regenerate with: python tools/lock_requirements.py\n"
        "#\n"
        "# Test-only packages, pinned to the versions the suite was verified against. Install\n"
        "# after the runtime lock:\n"
        "#   pip install -r requirements.lock.txt -r requirements-dev.lock.txt\n"
    )
    (APP_DIR / "requirements-dev.lock.txt").write_text(
        dev_header + render(installed.keys() - runtime, installed), encoding="utf-8", newline="\n")

    print(f"requirements.lock.txt      {len(runtime)} packages")
    print(f"requirements-dev.lock.txt  {len(installed.keys() - runtime)} packages")


if __name__ == "__main__":
    main()
