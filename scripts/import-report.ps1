param([string]$DataRoot = (Join-Path $env:LOCALAPPDATA 'SleepIQ'))
# Owner-run, counts-only summary of the private store. Prints no readings or timestamps.
$ErrorActionPreference = 'Stop'
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    & .\.venv\Scripts\python.exe -m app.ingest.report --data-root $DataRoot
    if ($LASTEXITCODE) { throw 'Report failed. Nothing was printed from the store.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
