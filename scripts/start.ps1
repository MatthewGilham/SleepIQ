$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot 'private-folders.ps1')
$previousDataRoot = $env:SLEEPIQ_DATA_ROOT
$previousBackupRoot = $env:SLEEPIQ_BACKUP_ROOT
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if (!(Test-Path frontend/dist/index.html)) { throw "Build the frontend first; see docs/SETUP.md." }
    $dataRoot = Join-Path $env:LOCALAPPDATA 'SleepIQ'
    $backupRoot = 'C:\Users\Matth\SleepIQ-Backups'
    if (Test-Path -LiteralPath (Join-Path $dataRoot 'sleepiq.sqlite3')) {
        Assert-PrivateFolder $dataRoot
        Assert-PrivateFolder (Join-Path $dataRoot 'raw')
        Assert-PrivateFolder $backupRoot
        $env:SLEEPIQ_DATA_ROOT = $dataRoot
        $env:SLEEPIQ_BACKUP_ROOT = $backupRoot
    } else {
        $env:SLEEPIQ_DATA_ROOT = $null
        $env:SLEEPIQ_BACKUP_ROOT = $null
    }
    # Foreground ownership: Ctrl+C stops this app's server without looking up or killing other PIDs.
    & .\.venv\Scripts\python.exe -m uvicorn app.start:app --app-dir backend --host 127.0.0.1 --port 8765 --no-access-log
    if ($LASTEXITCODE) { throw "Server stopped with an error. Check whether port 8765 is already in use." }
} finally {
    $env:SLEEPIQ_DATA_ROOT = $previousDataRoot
    $env:SLEEPIQ_BACKUP_ROOT = $previousBackupRoot
    Pop-Location
}
