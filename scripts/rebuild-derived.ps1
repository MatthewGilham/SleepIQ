param(
    [string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'SleepIQ'),
    [string]$BackupRoot = 'C:\Users\Matth\SleepIQ-Backups'
)
# Owner-run: verified snapshot, then recompute nights/scores from stored observations. No import.
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'private-folders.ps1')
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    foreach ($folder in @($DataRoot, $BackupRoot, (Join-Path $DataRoot 'raw'))) {
        Assert-PrivateFolder $folder
    }
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    & .\.venv\Scripts\python.exe -m app.ingest.rebuild_cli --data-root $DataRoot --backups $BackupRoot
    if ($LASTEXITCODE) { throw 'Rebuild failed. Stored observations were not changed.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
