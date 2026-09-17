@echo off
REM Double-click this to pull everything from the encrypted OneDrive backup down to this PC,
REM decrypted back to normal filenames and folders. Use it to check a backup actually has what
REM you expect, or to recover files after losing this machine.
REM
REM Needs: this machine's rclone.conf (already set up here) with the dfu-crypt remote's two
REM passwords in it. Without that file and those passwords, nobody - not even the OneDrive
REM account owner - can read what's in the backup. That is the whole point of the encryption.

setlocal
set DEST=%USERPROFILE%\Downloads\DFU-Restored

echo Downloading and decrypting everything under dfu-crypt:/current
echo into:
echo   %DEST%
echo.
echo This can take a while the first time (it copies every case, not just the latest few).
echo.

rclone copy "dfu-crypt:/current" "%DEST%" --progress
if errorlevel 1 (
  echo.
  echo Something went wrong - check the messages above.
  pause
  exit /b 1
)

echo.
echo Done. Opening the folder...
start "" "%DEST%"
pause
