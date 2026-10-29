$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & .\.venv\Scripts\python.exe scripts/scan_source.py
    if ($LASTEXITCODE) { throw "Secret scan failed" }
    & .\.venv\Scripts\python.exe -m pip_audit --cache-dir .cache/pip-audit --timeout 10
    if ($LASTEXITCODE) { throw "Python dependency audit failed or unavailable" }
    & npm.cmd --cache .cache/npm --prefix frontend audit
    if ($LASTEXITCODE) { throw "Frontend dependency audit failed or unavailable" }
} finally { Pop-Location }
