$ErrorActionPreference = "Stop"
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    if (!(Test-Path .venv/Scripts/python.exe)) {
        & uv --cache-dir .cache/uv venv --python 3.13 --no-python-downloads .venv
        if ($LASTEXITCODE) { throw "Environment creation failed" }
    }
    & uv --cache-dir .cache/uv sync --locked --python .venv/Scripts/python.exe
    if ($LASTEXITCODE) { throw "Locked dependency installation failed" }
    & npm.cmd --cache .cache/npm --prefix frontend ci --ignore-scripts
    if ($LASTEXITCODE) { throw "Frontend dependency installation failed" }
} finally { Pop-Location }
