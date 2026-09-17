@echo off
REM Double-click this to start the capture app - no VS Code, no typing env vars by hand.
REM
REM APP_PASSWORD is deliberately NOT set here: bootstrap_password() in auth.py keeps whatever
REM password was already set in the database when the env var is absent, and only overwrites it
REM when the env var IS set. Baking a real password into a .cmd file that lives in the repo would
REM put it in plaintext in git history forever - the one-time way to set or change it is
REM `set APP_PASSWORD=...` in a terminal before running this, not editing this file.
REM
REM CAPTURE_SOURCE and DFU_DATA_DIR are not secret, so they're fixed here to match this machine's
REM setup. Change them below if this machine's data drive changes.

setlocal
cd /d "%~dp0"

set CAPTURE_SOURCE=usb
set DFU_DATA_DIR=C:\dfu-data

if not exist ".venv\Scripts\python.exe" (
  echo .venv not found - run setup.ps1 first:
  echo   powershell -ExecutionPolicy Bypass -File setup.ps1
  pause
  exit /b 1
)

echo Starting the DFU capture server on http://127.0.0.1:8000/
echo Close this window, or press Ctrl+C, to stop the server.
echo.
echo If this prints a generated one-time password below, save it - it will not be shown again.
echo (That only happens the very first time, before any password has been set.)
echo.

start "" "http://127.0.0.1:8000/"
.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000

pause
