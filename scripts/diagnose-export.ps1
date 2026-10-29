param([Parameter(Mandatory = $true)][string]$ExportPath)
$ErrorActionPreference = 'Stop'
$previousPythonPath = $env:PYTHONPATH
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $env:PYTHONPATH = Join-Path (Get-Location) 'backend'
    & .\.venv\Scripts\python.exe -m app.diagnostics.export_shape $ExportPath
    if ($LASTEXITCODE) { throw 'Local export diagnostic failed. No export contents were printed.' }
} finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
