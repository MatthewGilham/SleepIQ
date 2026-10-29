param([ValidateSet("Foundation", "Full")][string]$Suite = "Foundation")
$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & .\.venv\Scripts\python.exe -m ruff check backend
    if ($LASTEXITCODE) { throw "Python lint failed" }
    & .\.venv\Scripts\python.exe -m mypy
    if ($LASTEXITCODE) { throw "Python types failed" }
    & .\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
    if ($LASTEXITCODE) { throw "Backend tests failed" }
    & npm.cmd --prefix frontend test
    if ($LASTEXITCODE) { throw "Frontend tests failed" }
    & npm.cmd --prefix frontend run build
    if ($LASTEXITCODE) { throw "Frontend build failed" }
    if ($Suite -eq "Full") {
        & npm.cmd --prefix frontend run test:e2e
        if ($LASTEXITCODE) { throw "Browser tests failed" }
        & .\.venv\Scripts\python.exe scripts/perf-check.py --enforce
        if ($LASTEXITCODE) { throw "Performance budget exceeded" }
        & .\scripts\security.ps1
        if ($LASTEXITCODE) { throw "Security gate failed or unavailable" }
    }
} finally { Pop-Location }
