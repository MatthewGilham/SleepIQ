# SleepIQ Windows operations guide

For the owner, on the Windows PC that runs SleepIQ. Evidence of what has actually been demonstrated lives only in [PLAN.md](PLAN.md) (R01 sections). Setup background: [SETUP.md](SETUP.md), [SECURE_SETUP.md](SECURE_SETUP.md), [RECOVERY.md](RECOVERY.md).

## Day to day

| Task | How |
|---|---|
| Open the dashboard | `powershell -File scripts/start.ps1`, then `http://127.0.0.1:8765` in the PC browser. Keep the console open; stop with Ctrl+C. A second launch refuses to start and never kills the first. |
| Receive iPhone exports | The HTTPS receiver runs as a per-user scheduled task (P20): `scripts/receiver-task.ps1 -Action Status` (also `Start`, `Stop`, `Install`, `Remove`). The PC must be on, awake and on the home network. |
| Turn on AI (optional) | Set `SLEEPIQ_AI_ENABLED=1` and `SLEEPIQ_OPENAI_API_KEY` in the launching window only. Off by default; every Analyze click is one billable request (20/day, 300/month caps). |
| Import an export file by hand | `scripts/import-export.ps1 -ExportPath "<file>"` (takes a verified snapshot first). |
| Recompute nights and scores | `scripts/rebuild-derived.ps1` (snapshot first; reads stored readings only). About 4 s for five years of synthetic nights. |
| Check what is stored | `scripts/import-report.ps1` (counts only). |
| Check the project is healthy | `powershell -File scripts/check.ps1 -Suite Full` (see below). |

Nothing starts by itself except the receiver task, and nothing is exposed outside your home network.

## Backups

A verified snapshot of the database and the original JSON files is made when the app launches and hourly while it runs, one per day, keeping the latest 14, in `C:\Users\Matth\SleepIQ-Backups`. The dashboard header shows the last verified date. If it says the backup failed, nothing is deleted; fix the cause (usually disk space) and relaunch. These backups are on the same PC: they do not protect against losing the PC. Copy the backup folder to an external drive or another trusted location now and then. They are not encrypted.

## Restore drill (owner step; never overwrites live data)

1. Stop SleepIQ and the receiver task.
2. From the project folder:
   ```powershell
   $env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
   .\.venv\Scripts\python.exe -m app.db.backup_cli verify 'C:\Users\Matth\SleepIQ-Backups\<date>'
   .\.venv\Scripts\python.exe -m app.db.backup_cli restore-isolated 'C:\Users\Matth\SleepIQ-Backups\<date>' 'C:\Users\Matth\SleepIQ-Restore-Test'
   ```
3. Both must finish without error; `restore-isolated` verifies checksums and integrity itself. Optionally compare night counts with the live store using `scripts/import-report.ps1`.
4. Delete `SleepIQ-Restore-Test` when finished; it contains a copy of your health data.

Replacing the live store from a snapshot is a separate, deliberate recovery action with the app stopped; ask before doing it.

## When the PC is off or the phone cannot reach it

Health Auto Export keeps unsent data and retries. When the PC is back, the next export is imported idempotently: re-sent readings are counted as duplicates, nothing is doubled, and the affected nights are recomputed. Check `scripts/import-report.ps1` or the dashboard header's Sync indicator afterwards. The receiver task does not run the daily backup; launch the dashboard to take it. A gap in the chart means those nights have no stored sleep, not zero sleep.

## Certificate renewal

**The current production certificate expires on 2027-01-27 and renewal is not yet integrated or demonstrated.** Re-run `scripts/request-certificate.ps1 -Environment Production` (details in [CERTIFICATE_SETUP.md](CERTIFICATE_SETUP.md)) well before then, and restart the receiver so it loads the new certificate. This is an open operational limitation recorded in PLAN.md. If iPhone uploads suddenly start failing with a certificate error, check expiry first. Never turn off certificate checking in the exporter.

## Troubleshooting

| Symptom | Likely cause and action |
|---|---|
| Launcher says the port is in use | SleepIQ is already running; use that console. |
| Dashboard shows the labelled synthetic preview | No data store configured for this launch; start with `scripts/start.ps1`, not the preview script. |
| Latest night missing | The watch has not synced that night yet, or the phone has not exported it. The latest night stays visible even without a score. |
| Latest night marked "possibly incomplete" | No later reading has arrived yet; it clears when the next export lands. |
| Uploads rejected | Credential mismatch (`scripts/view-ingest-credential.ps1`), certificate expiry, PC address changed (reservation was deferred in P12; recheck `192.168.1.190` and the DNS record), or the receiver task is stopped. |
| Backup failed | Check free disk space and that the backup folder still exists; relaunch. |

## Quality gate: `scripts/check.ps1 -Suite Full`

Runs, in order: Ruff, Mypy, all backend tests, frontend unit tests, strict TypeScript build, the Playwright browser tests (Microsoft Edge, isolated synthetic store on port 8766), the performance budgets (`scripts/perf-check.py --enforce`, about half a minute), then `scripts/security.ps1` (secret scan, `pip-audit`, `npm audit`). The audits contact package-advisory services using package names only; if they are unreachable the gate fails rather than passing. Everything uses synthetic data; the suite never opens your real store.

## Owner acceptance checklist (R01)

These cannot be done by the agent. Tick each only when you have seen it work, then tell the agent so it can record the evidence in PLAN.md.

- [x] **A1 Real encrypted ingest.** (owner-reported 2026-10-29: import-report batches rose 16 to 17) Health Auto Export on the iPhone, on home Wi-Fi, sends a real export to `https://sync.mgilham.online:8443/api/ingest`; the receiver accepts it and the dashboard shows the new night.
- [ ] **A2 Wrong credential is refused.** (Optional, from the phone) a request with a wrong credential is rejected and nothing is stored.
- [ ] **A3 Downtime and retry.** Stop the receiver (or switch the PC off) across at least one scheduled export, restart, and confirm that the missed data arrives with no duplicates (compare night counts before and after with `scripts/import-report.ps1`).
- [x] **A4 Restore drill.** (owner ran 2026-10-29 on the 2026-10-29 snapshot; both commands succeeded) The steps above on a populated snapshot, both commands succeeding.
- [x] **A5 Launcher.** (owner confirmed 2026-10-29) `scripts/start.ps1` opens the dashboard; launching it a second time is refused; Ctrl+C stops it; no autostart entry other than the receiver task exists.
- [x] **A6 Real-store dashboard.** (owner confirmed 2026-10-29) The latest real night, charts for all configured metrics, Correlations and CSV export open without errors on your own data (nothing here sends data anywhere).
