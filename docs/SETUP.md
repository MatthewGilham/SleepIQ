# Local foundation setup

Status: Python/frontend dependencies installed; TypeScript/Vite build and in-process HTTP smoke checks passed. Owner confirmed the manual setup page works; foundation checks now pass. Remaining launcher/CI/security acceptance is tracked in PLAN.md. Follow progress in PLAN.md. No ingestion endpoint or health storage is implemented.

The backend uses Python 3.13 in the project's own `.venv`; the existing Python selected by your shell belongs to another project. Use explicit `.venv` commands rather than installing packages globally. Dependency caches stay under `.cache` in this project.

## Initial dependency resolution

The agent environment could not reach PyPI and npm had no cached packages on 2026-10-29. Lockfiles cannot be generated until package access works. From PowerShell in the project root, with ordinary package-registry access:

```powershell
uv --cache-dir .cache/uv lock
uv --cache-dir .cache/uv sync --locked --python .venv/Scripts/python.exe
npm.cmd --cache .cache/npm --prefix frontend install --ignore-scripts
powershell -File scripts/check.ps1 -Suite Foundation
```

Do not claim reproducible installation until `uv.lock` and `frontend/package-lock.json` exist and have been verified. Frontend manifest `latest` values are temporary resolution inputs; pin resolved direct versions before completing F01. Review dependency audits, frontend tests and CI before marking the ticket complete. `scripts/setup.ps1` is for subsequent locked installs and intentionally fails if lockfiles are absent.

## Manual launch

After a successful build:

```powershell
powershell -File scripts/start.ps1
```

Open `http://127.0.0.1:8765` in the PC browser. The setup page should report the local service connection. Keep the console open. Stop with Ctrl+C in that same console. A second launch must fail if the port is occupied; it must not terminate the existing application. No startup task or Windows service is registered.

The implemented launcher uses a foreground console so server ownership and stopping are explicit; no separate background controller is required for F01. The browser service binds only to loopback. The separate HTTPS receiver is currently a synthetic test probe; Health Auto Export ingestion awaits Phase 2 implementation and the relevant owner gates.
