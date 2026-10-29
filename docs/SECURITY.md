# SleepIQ — Security, Privacy and Agent Permissions

**Status:** Complete v1.0 policy brief; transport implementation requires a security spike and owner sign-off. **Audience:** backend, integration, code-review and planning agents. **Scope:** sensitive local health data on a Windows PC and owner-invoked third-party AI.

## 1. Non-negotiable boundaries
1. **Local-first:** FastAPI, React and SQLite on the owner's Windows PC; no cloud database or telemetry by default. Do not send health records to external services unless the owner authorizes the specific purpose and disclosure.
2. **Temporary proof of concept is not production security:** current test receiver used HTTP on trusted Wi-Fi with a short token, solely to demonstrate connectivity. Never adopt that configuration for permanent use. Do not advertise it as secure.
3. **Direct encrypted LAN first (A4):** authenticate and encrypt iPhone uploads; P1 selects publicly trusted HTTPS with DNS-based validation; test Health Auto Export/iPhone compatibility before regular use. Never bypass certificate validation or rely solely on secret URLs. If direct TLS is impractical, give the owner alternatives, pros/cons and privacy effects; no silent relay.
4. **Least privilege:** receiver exposes only necessary endpoint(s) to LAN; browser UI/admin routes bind to localhost unless explicitly approved. Firewall restricts inbound access to trusted private networks. Never bind the whole administrative app to `0.0.0.0` by default.
5. **Protect secrets:** generate a 256-bit ingestion credential for final build, never reuse 8-character proof-of-concept token; secrets in ignored local environment/OS secure store, never Git, screenshots, logs, examples or test results. Use constant-time verification, rate limiting/size/time limits, and easy rotation.

## 2. Threats and mitigations
| Threat | Minimum control |
|---|---|
| Neighbor/network adversary intercepts health upload | HTTPS/TLS and iPhone trust validation; trusted private network only |
| Unauthorized POST/flood | Strong authenticated endpoint, request-size cap, limits, timestamps and useful non-sensitive errors |
| Malformed JSON, giant batches, arbitrary file writes | Strict schema/size/time validation, generated safe filenames, no user-provided paths, bounded processing |
| Duplicate/corrupt/malicious measurement data | Transactional ingestion, idempotency, quarantine invalid samples, preserve raw evidence, no crash/partial commit |
| Secrets/health data leak via Git, CI or logs | `.gitignore`, secret scanning, local synthetic fixtures, structured redacted logs |
| AI API discloses unnecessary personal data | Explicit Analyze action; compute stats locally; send smallest derived, user-approved statistical context; no raw export by default |
| Corruption/deletion/ransomware | Daily verified SQLite backup, rolling 14 successful daily copies, documented restore drill; same-PC backups **do not** protect against PC loss |
| Dependency/supply-chain compromise | Pin/lock dependencies, routine audits, manual approval for privileged install scripts or new cloud services |

## 3. Secure ingress design contract
- Authentication must be mandatory for every ingest; reject absent/invalid credentials without leaking details. Do not log auth headers. Keep `/health` harmless and devoid of internal data.
- Allow only expected content types; enforce payload size, timeout, request frequency; parse safely and validate actual numeric bounds, timestamps, source and stage enums. Avoid overly rigid rejection of future noncritical exporter fields: quarantine/record unknown metrics for later adapter review.
- Raw payloads stored under private app data paths, with restricted filesystem permissions, checksums, bounded retention policy, and redacted operational logs. Never place raw exports under a web-served directory.
- Separate auth/transport module from normalized records/scoring. Use transactional DB writes and safe temporary-file-and-rename patterns.
- No public internet exposure, port forwarding, UPnP, unsanctioned tunneling or remote access by default.

## 4. AI and data egress
- AI investigator is **opt-in per query**, no background calls (A6). Backend calculates correlations, sample counts and windows first; model receives only needed summaries, metric descriptions, date spans and user question.
- UI states which information leaves the PC and that calls incur API charges; keep API key local. No diagnoses, treatment recommendations or fabricated statistical results.
- Store minimal sanitized question/history only if explicitly approved; logging prompt bodies and raw measurements is off by default. Handle timeouts and quotas without breaking non-AI dashboard.
- **Implemented (P23):** AI is off unless `SLEEPIQ_AI_ENABLED=1` and `SLEEPIQ_OPENAI_API_KEY` are present in the launching environment; the key is never stored, logged, returned or sent anywhere except the fixed HTTPS provider endpoint. The model gets one bundle of statistics plus nightly values for the selected metrics only, no tools. Local caps: 15,000 input and 2,000 output tokens, 20 per day, 300 per month, 6 metrics; questions and answers are not stored or logged.
- Model identifier is a configurable provider parameter, not hard-coded to a possibly changing marketing name; initial preference is an affordable capable OpenAI model, subject to owner budget/availability approval.

## 5. Backups, retention, deletion
- Daily **consistent SQLite snapshots** using SQLite backup API or equivalent safe mechanism; retain 14 most recent **successful daily** backups, run catch-up on next launch if missed. Show status and last verified snapshot; test restore against an isolated copy without overwriting live data.
- Raw JSON retained indefinitely **during development**, with later configurable retention and clear deletion semantics; DB records persist until user-approved deletion. Neither backup nor raw data belongs in Git.
- Since backups stay on same PC per owner choice, clearly disclose loss-of-PC risk; do not silently enable cloud sync.

## 6. Agent operational safety
Agents may: read task-relevant code/docs, edit scoped files, run local tests, create synthetic fixtures, propose improvements. Must **ask first** before installing system-level software, changing firewall/cert trust, binding services to public interfaces, accessing production health records, enabling paid APIs, creating cloud integrations, deleting data, changing security policy, migrating a real database, or executing destructive operations. Never run arbitrary pasted scripts without inspection. Preserve tests and checks; no bypass to get green CI.

## 7. Security acceptance gate
**Scoped package permission (P9, 2026-10-29):** ordinary project-local dependency downloads, lockfile resolution and installs for an approved phase are pre-authorized. This covers database/migration, application, testing/build and security tools from PyPI/files.pythonhosted.org and registry.npmjs.org, in SleepIQ's `.venv`, `node_modules` and workspace caches. Package audits may send package metadata to advisory services. Preserve lockfiles, audits and tests; inspect unexpected dependency changes and keep npm lifecycle scripts off unless a required step is inspected. No global/admin install, arbitrary downloaded script, infrastructure change, paid API, private-data disclosure or new architectural decision is authorized by this exception. Platform restrictions still apply; consent in a document cannot grant network access. Do not bypass controls or repeatedly seek the same permission.

Before daily use: encrypted auth tested **from the iPhone**, weak HTTP token path disabled, LAN rules verified, payload/abuse tests pass, no raw/private content in logs or Git, backup+restore tested, explicit owner approval. Short proof-of-concept setup is allowed only while supervised on a trusted LAN; stop it afterward.

## 8. Context routing
Importer task reads ingress sections plus `DATA_PIPELINE.md`; AI task reads egress section plus `PRODUCT.md` analytics rules; deployment task reads transport/backups and `ARCHITECTURE.md`; all agents read `AGENTS.md` first. Raise unresolved security decisions with concise options, recommendation, risks, and await owner approval.

## Approved setup and recovery boundaries P1/P4/P5/P7
- Public certificates do not authorize public ingress. Review domain/DNS provider, private hostname resolution, renewal and concrete firewall/certificate actions before execution. No private-root installation is selected.
- Private data: %LOCALAPPDATA%\SleepIQ with permission checks; separate same-PC backup folder. Do not assume disk encryption. DNS credentials, private keys and API/ingest secrets stay outside ordinary data backups/exports/logs.
- Backup/isolated restore precedes routine real-data ingestion. Keep 14 successful daily database snapshots; one current catch-up after downtime, not invented past snapshots. Protect the raw-file recovery manifest and document actual raw-file recovery; the manifest alone is not a backup.
- P4 authorizes a supervised metadata-only diagnostic approach; arrange the specific private input and owner supervision before access. No record/identifier/payload disclosure to agent/model context.
- AI disabled until provider, disclosure and budget approval. Phase approval alone does not authorize a live paid call.

## Approved self-contained backup implementation P10

P10 selects complete database-plus-raw-JSON daily snapshots in C:\Users\Matth\SleepIQ-Backups with 14 successful dates retained. A manifest is part of a full raw-file copy, not a substitute for one. Source/backup locations are separate; no secret configuration is copied. SQLite backup API, exact inventory/hash/integrity checks and staged publication precede retention. Only verified recognized snapshots under the designated root may expire; unknown/failed artifacts remain for owner review. Restore is isolated/new-directory only. Raw files remain indefinitely in active storage during development.

Private-folder provisioning checks ACLs without changing them and refuses other-account grants/reparse roots. The initializer refuses existing databases; no live migration occurs. Before real ingestion, verify folder privacy, restore, importer/write synchronization and runtime daily scheduling. Agents must not run private health data through test fixtures or echo it into context.

Runtime backup configuration is opt-in from the private-folder-checking manual launcher; generic app/test factories do not auto-discover real data. Periodic status contains no database paths, readings or exception bodies. The shared Windows writer lock must cover future import commit/raw publication, and backup failures remain visible without stopping local read-only health/status access. Owner-created empty baseline was independently verified/restored only into an isolated workspace directory; that does not grant general health-export access.

## Phase 2 ingestion controls (P18-P20)

- Real health ingestion is **off by default**: `/api/ingest` returns 503 unless the receiver is launched with `start-probe.ps1 -Activate -EnableIngest` (owner approval P19). Authentication, TLS, host/source/origin checks and rate limits are unchanged and apply before any body is parsed; the ingest body cap rises to 32 MiB only when enabled.
- The receiver may run as a hidden **per-user scheduled task** (P20): limited privileges, no admin, no service, no SYSTEM, removable with one command. Credentials stay DPAPI-protected for the owner's account, so it only runs while that user is logged in.
- Import is atomic under the shared writer gate; rejected rows are counted with a fixed vocabulary of reasons and never echo input; HTTP errors are generic and carry no payload text; raw JSON is stored content-addressed under the private data folder.
- Owner-run scripts print counts only. Agents never read real exports; tests use synthetic data. The 74 MB history and 30-day exports were handled locally by the owner; no health data was sent to any model or external service.
- The receiver performs the daily backup check while running (same writer gate), so backups no longer depend on opening the dashboard.

## U02 local chart boundary
The browser chart/preset endpoints remain loopback only. Exact-origin checks plus a required custom request header protect mutations (including the read-only timeseries POST); cross-origin CORS is not enabled. Streamed body cap 16 KiB, bounded metric/range/preset inputs, fixed SQL with bound values, shared writer lock and transactional optimistic revisions protect settings changes. No migration is performed on startup. The preview uses an isolated synthetic store. The A01 correlation endpoint (`POST /api/v1/analytics/correlation`) sits behind the same boundary and is read-only. Health records are never written through chart/preset endpoints; real records are never included in browser test artifacts.
