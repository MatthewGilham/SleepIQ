# Local foundation setup

Status: Python/frontend dependencies installed; TypeScript/Vite build and in-process HTTP smoke checks passed. Owner confirmed the manual setup page works; foundation checks now pass. Remaining launcher/CI/security acceptance is tracked in PLAN.md. Follow progress in PLAN.md. Health storage and an authenticated ingestion path are implemented (Phase 2) but the ingestion path is off unless explicitly enabled; see SECURE_SETUP.md.

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

## Desktop shortcut (L01)

Run `powershell -File scripts/install-shortcut.ps1` once from the project folder. It puts a **SleepIQ** shortcut on your Desktop (no admin rights, no autostart, no execution-policy change). Clicking it runs `scripts/launch.ps1`: if SleepIQ is already answering it only opens the browser; otherwise it runs `start.ps1` in a visible window and opens Chrome (default browser if Chrome is not installed) once the app responds. Closing that window stops SleepIQ. `-Replace` recreates the shortcut after moving the project; `-Remove` deletes it.

## Manual launch

After a successful build:

```powershell
powershell -File scripts/start.ps1
```

Open `http://127.0.0.1:8765` in the PC browser. The setup page should report the local service connection. Keep the console open. Stop with Ctrl+C in that same console. A second launch must fail if the port is occupied; it must not terminate the existing application. The dashboard has no startup task or service. (The separate HTTPS receiver can optionally run as a per-user scheduled task under P20; see SECURE_SETUP.md.)

The implemented launcher uses a foreground console so server ownership and stopping are explicit; no separate background controller is required for F01. The browser service binds only to loopback. The separate HTTPS receiver is a synthetic probe unless started with `-EnableIngest`, which turns on Health Auto Export ingestion (P19).

## Owner-run data scripts (Phase 2)

Run from the project folder, in a normal PowerShell, on one line each. All print counts only.

- `scripts/import-export.ps1 -ExportPath "<file>" [-Migrate]` imports one export (after a verified snapshot). `-Migrate` upgrades an older store to the current schema.
- `scripts/split-export.ps1 -ExportPath "<file>" -OutputFolder "<new folder>"` splits a large export into monthly files.
- `scripts/import-report.ps1` summarises stored data and night/score counts.
- `scripts/rebuild-derived.ps1` recomputes nights and scores from stored readings (after a verified snapshot).
- `scripts/receiver-task.ps1 -Action Install|Start|Stop|Remove|Status` manages the always-on receiver.

## Optional AI analysis (Phase 4)
Off by default. To turn it on, set both environment variables in the window that launches SleepIQ (never in a file in the repository): `SLEEPIQ_AI_ENABLED=1` and `SLEEPIQ_OPENAI_API_KEY=<your key>`; optionally `SLEEPIQ_AI_MODEL` (default `gpt-6-luna`). Each Analyze click is one billable request, limited locally to 20 per day and 300 per month. The key can be stored in the git-ignored `.env`, but the launcher reads only the environment: set `SLEEPIQ_OPENAI_API_KEY` yourself in the launching window. The first Analyze click on your real data is your own decision after reading the disclosure in the panel; see DECISIONS.md P23.
