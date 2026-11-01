# SleepIQ Windows operations guide

## Weighted HR rollout (P34)

Run only after the P34 full release gate is recorded as passing in PLAN.md. Phase approval is recorded, but unknown historical export settings must be resolved: `-ConfirmIndividualHR` explicitly asserts that existing HR exports were individual readings suitable for interpolation. Summarize Data off for today's configuration does not prove older files. Keep health values/review files local; do not paste them into chat.

1. Close SleepIQ's server window (Ctrl+C) and stop the receiver with `scripts/receiver-task.ps1 -Action Stop`. Do not disable/reconfigure the task, certificate, DNS or firewall. The mutating wrapper refuses listeners on 8765/8443; verify no old standalone receiver remains. Check available disk space: preparation retains a full snapshot plus isolated restore and a private comparison file, in addition to the unchanged 14 daily snapshots.
2. Prepare with `scripts/weighted-hr.ps1 -Action Prepare -ConfirmIndividualHR`. Defaults are the existing private data/backup folders; explicit `-DataRoot`/`-BackupRoot` overrides are available. This takes a fresh pre-change snapshot and verifies an isolated restore under `C:\Users\Matth\SleepIQ-Backups\hr\<checkpoint>`, explicitly applies the additive migration and builds candidate history under the writer lock. It prints only night/method counts, checkpoint ID and review token. Old calculation remains active. An old same-day daily snapshot is never reused as the rollout recovery point.
3. Review the method counts and open `hr\<checkpoint>\review.csv` inside the backup folder locally. It compares old/candidate HR and scores and HRV equality; it is private health data, never for Git/chat. Gaps are omitted from the estimated integral; sparse/ambiguous nights retain a simple mean. If uncertain or coverage is unsuitable, stop here: no activation occurred. Keep the recovery checkpoint for review; do not delete raw data or old outputs.
4. Once satisfied, run `scripts/weighted-hr.ps1 -Action Activate -ReviewToken '<token from Prepare>'`. This is the owner's explicit candidate-review acknowledgement. Input/generation/candidate/review-file changes or a damaged snapshot reject activation; prepare/review again if that happens. The active derive-2/score-3 selection changes transactionally, with v2 scoring curves unchanged. No measurement rebuild occurs during activation.
5. Restart the receiver with `scripts/receiver-task.ps1 -Action Start`, then launch SleepIQ through its normal shortcut. `scripts/weighted-hr.ps1 -Action Status` reports selected versions/generation; the dashboard status endpoint reports its captured pair and restart requirement without readings. Spot-check HR info, chart/CSV and score locally. Old upgraded processes reject requests/writes after a version change; legacy binaries must have been stopped in step 1.

Rollback: close/stop both processes again and run `scripts/weighted-hr.ps1 -Action Rollback`, then restart them. It snapshots first, rebuilds legacy derive-1/score-2 using all retained observations (including imports since activation), switches the generation and preserves weighted history/raw files. It does not delete records, downgrade schema, launch incompatible old code or destructively restore over the live store. Extra `hr` recovery checkpoints remain until the owner deliberately decides their retention; the normal 14-successful-day backup policy is unchanged. Actual release/owner-rollout evidence: [PLAN.md](PLAN.md#phase-hr-4---owner-approved-historical-recalculation-and-rollout).

For the owner, on the Windows PC that runs SleepIQ. Evidence of what has actually been demonstrated lives only in [PLAN.md](PLAN.md) (R01 sections). Setup background: [SETUP.md](SETUP.md), [SECURE_SETUP.md](SECURE_SETUP.md), [RECOVERY.md](RECOVERY.md).

## Day to day

| Task | How |
|---|---|
| Open the dashboard | Double-click the **SleepIQ** desktop shortcut (create it once with `powershell -File scripts/install-shortcut.ps1`; `-Replace` recreates it, `-Remove` deletes it). A PowerShell window opens, SleepIQ starts and Chrome (or your default browser) opens `http://127.0.0.1:8765` when it is ready. **That window is the app: keep it open; close it or press Ctrl+C to stop SleepIQ.** Clicking the shortcut again while it runs just opens another tab. The shortcut carries no AI key, so AI stays off unless you launch from a window where you set the variables. Manual fallback: `powershell -File scripts/start.ps1`, then open the address yourself. A second launch refuses to start and never kills the first. |
| Receive iPhone exports | The HTTPS receiver runs as a per-user scheduled task (P20): `scripts/receiver-task.ps1 -Action Status` (also `Start`, `Stop`, `Install`, `Remove`). The PC must be on, awake and on the home network. |
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

Certificates are free but last about 90 days. The current production certificate expires on 2027-01-27. Days remaining appear in the dashboard header (Certificate) and in `scripts/import-report.ps1`. Automatic renewal (P25) is built but **not yet switched on**:

1. In Cloudflare, give the existing DNS token an expiry date more than a year away and put it in your calendar. (Optionally restrict it to your home IP only if that address is stable; a changed IP would make renewal fail.)
2. Staging dry run (free test certificate, installs nothing): `powershell -File scripts/renew-certificate.ps1 -Environment Staging -AcceptTerms -ForceRenewal`. Expect "STAGING renewal succeeded and validated".
3. When that works and you approve, `powershell -File scripts/renewal-task.ps1 -Action Install`. It runs five minutes after each logon, does nothing unless 30 days or fewer remain, and `-Action Status` shows the expiry and last result. `-Action Run` triggers it now (a real renewal only if due) and `-Action Remove` switches it off.

If renewal fails, the live certificate is left alone, the header shows days left, and the status shows `failed` or `rolled_back`. The manual fallback is `scripts/renew-certificate.ps1 -Environment Production -AcceptTerms`. If uploads suddenly fail with a certificate error, check expiry first, and never turn off certificate checking in the exporter. If iPhone uploads suddenly start failing with a certificate error, check expiry first. Never turn off certificate checking in the exporter.

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
- [x] **A2 Wrong credential is refused.** (owner-reported passed 2026-10-29) (Optional, from the phone) a request with a wrong credential is rejected and nothing is stored.
- [ ] **A3 Downtime and retry.** (DEFERRED by owner 2026-10-29; still required before relying on unattended sync) Stop the receiver (or switch the PC off) across at least one scheduled export, restart, and confirm that the missed data arrives with no duplicates (compare night counts before and after with `scripts/import-report.ps1`).
- [x] **A4 Restore drill.** (owner ran 2026-10-29 on the 2026-10-29 snapshot; both commands succeeded) The steps above on a populated snapshot, both commands succeeding.
- [x] **A5 Launcher.** (owner confirmed 2026-10-29) `scripts/start.ps1` opens the dashboard; launching it a second time is refused; Ctrl+C stops it; no autostart entry other than the receiver task exists.
- [x] **A6 Real-store dashboard.** (owner confirmed 2026-10-29) The latest real night, charts for all configured metrics, Correlations and CSV export open without errors on your own data (nothing here sends data anywhere).
