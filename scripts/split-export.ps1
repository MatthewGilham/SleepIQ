param(
    [Parameter(Mandatory = $true)][string]$ExportPath,
    [Parameter(Mandatory = $true)][string]$OutputFolder
)
# Owner-run, fully local: split one big export into monthly files. Prints counts only.
$ErrorActionPreference = 'Stop'
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    & .\.venv\Scripts\python.exe -m app.ingest.split --file $ExportPath --out $OutputFolder
    if ($LASTEXITCODE) { throw 'Split failed. Nothing was overwritten.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
