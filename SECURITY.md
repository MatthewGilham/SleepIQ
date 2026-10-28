# SleepIQ — Security, Privacy and Agent Permissions

**Status:** Complete v1.0 policy brief; transport implementation requires a security spike and owner sign-off. **Audience:** backend, integration, code-review and planning agents. **Scope:** sensitive local health data on a Windows PC and owner-invoked third-party AI.

## 1. Non-negotiable boundaries
1. **Local-first:** FastAPI, React and SQLite on the owner's Windows PC; no cloud database or telemetry by default. Do not send health records to external services unless the owner authorizes the specific purpose and disclosure.
2. **Temporary proof of concept is not production security:** current test receiver used HTTP on trusted Wi-Fi with a short token, solely to demonstrate connectivity. Never adopt that configuration for permanent use. Do not advertise it as secure.
3. **Direct encrypted LAN first (A4):** authenticate and encrypt iPhone uploads; choose compatible HTTPS/TLS and certificate-trust approach only after a small iPhone compatibility test. Never bypass certificate validation or rely solely on secret URLs. If direct TLS is impractical, give the owner alternatives, pros/cons and privacy effects; no silent relay.
4. **Least privilege:** receiver exposes only necessary endpoint(s) to LAN; browser UI/admin routes bind to localhost unless explicitly approved. Firewall restricts inbound access to trusted private networks. Never bind the whole administrative app to `0.0.0.0` by default.
5. **Protect secrets:** generate high-entropy ingestion credential for final build, never reuse 8-character proof-of-concept token; secrets in ignored local environment/OS secure store, never Git, screenshots, logs, examples or test results. Use constant-time verification, rate limiting/size/time limits, and easy rotation.

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
- Model identifier is a configurable provider parameter, not hard-coded to a possibly changing marketing name; initial preference is an affordable capable OpenAI model, subject to owner budget/availability approval.

## 5. Backups, retention, deletion
- Daily **consistent SQLite snapshots** using SQLite backup API or equivalent safe mechanism; retain 14 most recent **successful daily** backups, run catch-up on next launch if missed. Show status and last verified snapshot; test restore against an isolated copy without overwriting live data.
- Raw JSON retained indefinitely **during development**, with later configurable retention and clear deletion semantics; DB records persist until user-approved deletion. Neither backup nor raw data belongs in Git.
- Since backups stay on same PC per owner choice, clearly disclose loss-of-PC risk; do not silently enable cloud sync.

## 6. Agent operational safety
Agents may: read task-relevant code/docs, edit scoped files, run local tests, create synthetic fixtures, propose improvements. Must **ask first** before installing system-level software, changing firewall/cert trust, binding services to public interfaces, accessing production health records, enabling paid APIs, creating cloud integrations, deleting data, changing security policy, migrating a real database, or executing destructive operations. Never run arbitrary pasted scripts without inspection. Preserve tests and checks; no bypass to get green CI.

## 7. Security acceptance gate
Before daily use: encrypted auth tested **from the iPhone**, weak HTTP token path disabled, LAN rules verified, payload/abuse tests pass, no raw/private content in logs or Git, backup+restore tested, explicit owner approval. Short proof-of-concept setup is allowed only while supervised on a trusted LAN; stop it afterward.

## 8. Context routing
Importer task reads ingress sections plus `DATA_PIPELINE.md`; AI task reads egress section plus `PRODUCT.md` analytics rules; deployment task reads transport/backups and `ARCHITECTURE.md`; all agents read `AGENTS.md` first. Raise unresolved security decisions with concise options, recommendation, risks, and await owner approval.
