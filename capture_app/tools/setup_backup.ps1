# Set up nightly encrypted backup to OneDrive via rclone.
#
#   powershell -ExecutionPolicy Bypass -File tools\setup_backup.ps1
#
# Installs rclone if needed, walks you through signing in to OneDrive once, and registers a
# scheduled task that runs tools\backup.py every night. The rclone config file it produces is
# portable: copy it to the other laptop and backups work there with no second sign-in.

$ErrorActionPreference = "Stop"
Set-Location -Path (Split-Path $PSScriptRoot -Parent)

$REMOTE_NAME = "dfu-crypt"          # the encrypted remote the backup script writes to
$BASE_REMOTE = "onedrive"           # the raw OneDrive remote it wraps
$TASK_NAME   = "DFU capture app backup"

function Step($msg) { Write-Host ""; Write-Host "==> $msg" -ForegroundColor Cyan }
function Ok($msg)   { Write-Host "    $msg" -ForegroundColor Green }
function Info($msg) { Write-Host "    $msg" }

Step "Checking rclone"
$rclone = (Get-Command rclone -ErrorAction SilentlyContinue).Source
if (-not $rclone) {
    Info "not installed - installing with winget"
    winget install --id Rclone.Rclone --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User")
    $rclone = (Get-Command rclone -ErrorAction SilentlyContinue).Source
}
if (-not $rclone) {
    Write-Host "rclone still not on PATH. Install it from https://rclone.org/downloads/ and re-run." -ForegroundColor Red
    exit 1
}
Ok $rclone

Step "Checking the rclone remotes"
$remotes = & $rclone listremotes
$haveBase   = $remotes -contains "${BASE_REMOTE}:"
$haveCrypt  = $remotes -contains "${REMOTE_NAME}:"

if (-not $haveBase) {
    Write-Host ""
    Write-Host "  You need to sign in to OneDrive once. rclone config opens next." -ForegroundColor Yellow
    Write-Host "  Answer it like this:"
    Write-Host "     n                     (new remote)"
    Write-Host "     name>  $BASE_REMOTE"
    Write-Host "     Storage>  onedrive"
    Write-Host "     client_id / client_secret>  leave blank, press Enter"
    Write-Host "     region>  global"
    Write-Host "     Edit advanced config>  n"
    Write-Host "     Use auto config>  y      (a browser opens - sign in with your university account)"
    Write-Host "     Your choice>  1          (OneDrive Personal or Business)"
    Write-Host "     Chose drive to use>  0   (pick the university drive it lists)"
    Write-Host "     Is that okay>  y    then  q  to quit"
    Write-Host ""
    Read-Host "  Press Enter to open rclone config"
    & $rclone config
    $remotes = & $rclone listremotes
    if ($remotes -notcontains "${BASE_REMOTE}:") {
        Write-Host "Remote '$BASE_REMOTE' was not created. Re-run this script." -ForegroundColor Red
        exit 1
    }
}
Ok "OneDrive remote '${BASE_REMOTE}:' is configured"

if (-not $haveCrypt) {
    Write-Host ""
    Write-Host "  Now an ENCRYPTED wrapper, so the files are unreadable in the cloud." -ForegroundColor Yellow
    Write-Host "  This is patient research data - do not skip it."
    Write-Host "     n                     (new remote)"
    Write-Host "     name>  $REMOTE_NAME"
    Write-Host "     Storage>  crypt"
    Write-Host "     remote>  ${BASE_REMOTE}:dfu-backup"
    Write-Host "     filename_encryption>  standard"
    Write-Host "     directory_name_encryption>  true"
    Write-Host "     password>  choose one, then 'y' to confirm"
    Write-Host "     password2>  choose a different one (salt)"
    Write-Host ""
    Write-Host "  WRITE BOTH PASSWORDS DOWN SOMEWHERE SAFE AND OFFLINE." -ForegroundColor Red
    Write-Host "  Without them the backup cannot be restored - by you or by anyone." -ForegroundColor Red
    Write-Host ""
    Read-Host "  Press Enter to open rclone config"
    & $rclone config
    $remotes = & $rclone listremotes
    if ($remotes -notcontains "${REMOTE_NAME}:") {
        Write-Host "Remote '$REMOTE_NAME' was not created. Re-run this script." -ForegroundColor Red
        exit 1
    }
}
Ok "Encrypted remote '${REMOTE_NAME}:' is configured"

Step "Testing the connection"
& $rclone lsd "${REMOTE_NAME}:" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Could not reach ${REMOTE_NAME}: - check the config and try again." -ForegroundColor Red
    exit 1
}
Ok "reachable"
Info "config file (copy this to the other machine): $(& $rclone config file | Select-Object -Last 1)"

Step "Registering the nightly task"
$venvPy = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "No .venv found - run setup.ps1 first." -ForegroundColor Red
    exit 1
}
$script = Join-Path (Get-Location) "tools\backup.py"
$action = New-ScheduledTaskAction -Execute $venvPy -Argument "`"$script`"" -WorkingDirectory (Get-Location)
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
    -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries
try { Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false -ErrorAction Stop } catch {}
Register-ScheduledTask -TaskName $TASK_NAME -Action $action -Trigger $trigger `
    -Settings $settings -Description "Nightly encrypted backup of the DFU capture app data" | Out-Null
Ok "task '$TASK_NAME' runs daily at 02:00"

Write-Host ""
Write-Host "Backup is set up." -ForegroundColor Green
Write-Host ""
Write-Host "Set this so backup.py knows where to upload (and restart the app afterwards):"
Write-Host "  [Environment]::SetEnvironmentVariable('DFU_BACKUP_REMOTE', '${REMOTE_NAME}:', 'User')"
Write-Host ""
Write-Host "Run one now to check it end to end:"
Write-Host "  .venv\Scripts\python.exe tools\backup.py --dry-run"
Write-Host ""
Write-Host "On the other laptop: install rclone, copy the config file above to the same path,"
Write-Host "then run this script again - it will skip straight to registering the task."
