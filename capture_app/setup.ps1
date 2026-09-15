# One-command setup for a fresh machine (Windows).
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# Creates the venv, installs the EXACT tested dependency versions from requirements.lock.txt,
# initialises the database, then verifies the install by running the test suite and listing the
# cameras it can see. Safe to re-run: an existing venv is reused, and the migration is idempotent.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$REQUIRED_PY = "3.12"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "    $msg" -ForegroundColor Yellow }

Step "Checking Python"
# Probe each candidate defensively. `py.exe` ships with Windows even when no Python is registered
# with the launcher, and it then writes "No installed Python found!" to stderr — which, under
# $ErrorActionPreference = "Stop", PowerShell turns into a terminating NativeCommandError and
# kills this script before it ever reaches a perfectly good `python` on PATH. So: swallow stderr,
# check the exit code, and keep looking.
function Get-PythonVersion($exe, $extraArgs) {
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $argList = @()
        if ($extraArgs) { $argList += $extraArgs }
        $argList += @("-c", "import sys; print('%d.%d' % sys.version_info[:2])")
        $out = & $exe $argList 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { return $out.Trim() }
    } catch {
    } finally {
        $ErrorActionPreference = $prev
    }
    return $null
}

$py = $null; $pyArgs = @()
foreach ($cand in @(@("py", @("-$REQUIRED_PY")), @("python", @()), @("python3", @()))) {
    $exe = $cand[0]; $extra = $cand[1]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $ver = Get-PythonVersion $exe $extra
    if ($ver -eq $REQUIRED_PY) { $py = $exe; $pyArgs = $extra; break }
    if ($ver) { Warn "$exe is Python $ver — need $REQUIRED_PY" }
}
if (-not $py) {
    Write-Host ""
    Write-Host "Python $REQUIRED_PY not found." -ForegroundColor Red
    Write-Host "The dependency lock (numpy/scipy/opencv wheels) is built for $REQUIRED_PY."
    Write-Host "Install it from https://www.python.org/downloads/ and re-run this script."
    exit 1
}
Ok "using $py $pyArgs (Python $REQUIRED_PY)"

Step "Creating virtual environment (.venv)"
if (Test-Path ".venv\Scripts\python.exe") {
    Ok ".venv already exists — reusing it"
} else {
    & $py ($pyArgs + @("-m", "venv", ".venv"))
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Host "venv creation failed" -ForegroundColor Red; exit 1
    }
    Ok "created"
}
$VENV_PY = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Step "Installing dependencies (exact tested versions)"
& $VENV_PY -m pip install --quiet --upgrade pip
& $VENV_PY -m pip install --quiet -r requirements.lock.txt -r requirements-dev.lock.txt
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }
Ok "installed from requirements.lock.txt"

Step "Initialising the database"
& $VENV_PY migrate_to_sqlite.py
Ok "data/app.db ready"

Step "Verifying the install (test suite)"
& $VENV_PY -m pytest tests/ -q
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Tests failed — do not collect data with this install." -ForegroundColor Red
    exit 1
}
Ok "all tests passed"

Step "Cameras visible to this machine"
# Not a failure if the podoscope is absent — setup may well run before the camera is plugged in.
& $VENV_PY tools\check_cameras.py

Write-Host ""
Write-Host "Setup complete." -ForegroundColor Green
Write-Host ""
Write-Host "Start the app:"
Write-Host '  $env:APP_PASSWORD = "your-team-password"'
Write-Host '  $env:CAPTURE_SOURCE = "usb"        # omit for the simulator'
Write-Host '  $env:DFU_DATA_DIR = "D:\dfu-data"  # optional: put data on a backed-up drive'
Write-Host "  .venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000"
Write-Host ""
Write-Host "Then open http://127.0.0.1:8000/"
