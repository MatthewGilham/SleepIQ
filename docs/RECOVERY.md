# Backup and isolated restore

P10 approves self-contained daily snapshots in `C:\Users\Matth\SleepIQ-Backups`, retaining the latest 14 successful dates. Source data belongs under `%LOCALAPPDATA%\SleepIQ`. Provisioning and private-folder checks precede live use; no real data is initialized or read merely by importing backup code. Operational status and actual evidence belong in PLAN.md.

Each published date folder contains `database.sqlite3`, original JSON exports under `raw/`, and `manifest.json` with SHA-256 hashes. SQLite's backup API creates a consistent database snapshot, including committed WAL data; copying a live database file directly is unsafe. The caller must pause importer/raw-file writes throughout backup so file references agree with the database snapshot. There is no importer yet; integrate that synchronization before real ingestion.

Backups build in a unique `.pending-*` directory on the destination filesystem. Only an inventory/checksum/SQLite-integrity-verified snapshot is renamed to its date. Failed staging folders remain for local inspection and never count as successful daily backups. They may contain private data and inherit the backup folder's permissions. There is no automatic deletion of failed/unknown folders.

One successful snapshot per local date is retained; repeated calls verify and reuse it. Missed days produce only a current snapshot on next invocation. A damaged current-date snapshot fails visibly rather than silently replacing it. Rotation happens only after a new verified snapshot is published. It removes only verified, recognized date snapshots directly below the designated backup root, never source data or unrelated folders. Corrupt/unrecognized folders are preserved for owner review. A retention error can occur after publication; inspect/verify the published date before interpreting that as a failed snapshot.

## Commands after private folders are provisioned

From the repository root in PowerShell, set the import path for this shell:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
```

Create or verify today's backup (replace explicit paths if your approved source layout differs):

```powershell
.\.venv\Scripts\python.exe -m app.db.backup_cli daily --database "$env:LOCALAPPDATA\SleepIQ\sleepiq.sqlite3" --raw "$env:LOCALAPPDATA\SleepIQ\raw" --backups 'C:\Users\Matth\SleepIQ-Backups'
```

Verify a chosen date:

```powershell
.\.venv\Scripts\python.exe -m app.db.backup_cli verify 'C:\Users\Matth\SleepIQ-Backups\2026-10-29'
```

Restore a chosen snapshot into a **new** isolated directory whose parent already exists:

```powershell
.\.venv\Scripts\python.exe -m app.db.backup_cli restore-isolated 'C:\Users\Matth\SleepIQ-Backups\2026-10-29' 'C:\Users\Matth\SleepIQ-Restore-Test'
```

This restores both database and JSON files and verifies their checksums/integrity before publication. The command refuses existing targets. No command replaces a live database; that requires a separate owner-approved recovery action with the app stopped. Never point the test at the live data folder. Secret configuration and API/certificate credentials are excluded because only the database and dedicated raw-export directory are copied.

Same-PC backups protect against some application/data failures; they do not protect against loss of the PC or its disk. They are not encrypted by this module; private-folder permissions must be verified before health data is stored. Daily launch integration and real-folder restore demonstration are required before routine ingestion.

## First-time private storage provisioning

Run `powershell -File scripts/setup-data.ps1` from the repository root in your normal non-administrator PowerShell. It creates the approved active-data and backup directories if absent, checks that their access rules allow only the current user, SYSTEM, administrators and creator-owner, then initializes a new empty database and creates/verifies its first snapshot. It changes no ACLs and refuses existing databases, nonempty raw folders, links/junctions and unexpected data-directory contents. If privacy checks fail, stop and review; never suppress the check. A failure may leave newly created empty folders or a partial initializer artifact for inspection; no existing records are deleted.

This operation has not been run by the agent against the owner's real folders. Automated backup/initialization tests use synthetic workspace directories. Launcher/daily-while-running integration and a real-folder isolated restore drill remain before B01 operational completion; the current command creates the first empty baseline only.

## Daily runtime integration

The normal start.ps1 validates private folders and explicitly opts in app.start with the approved data/backup paths. The app verifies or catches up the daily snapshot on launch, then checks hourly while running for a new local date or a retry. Shutdown stops the periodic task. No Windows autostart/service/scheduled task is installed, and no missed-day snapshots are invented. Test/app factories without explicit backup configuration do not read private folders. Restart the manually launched app to activate newly installed runtime code.

The readonly status API and setup page show verified date or a sanitized failure. Backup failure does not disable the browser health endpoint. The shared Windows writer gate coordinates backups across processes and threads; future ingestion must acquire the same gate for database commits and raw-file publication. Direct low-level create_daily callers must still pause writes. Manual daily CLI uses that gate too. Isolated verification/restore do not replace a live database.
