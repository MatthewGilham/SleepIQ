# Secure LAN setup proposal (S01, not deployed)

> **Phase 2:** `/api/ingest` is implemented but disabled. It activates only if the receiver is launched with the environment variable `SLEEPIQ_INGEST_DATA` naming the private data folder (store must be at schema 0002). Enabling it for the real Health Auto Export is a separate owner-approved step; see PLAN.md.

P1 approves publicly trusted HTTPS with DNS-based validation and direct LAN ingestion. Concrete DNS/certificate/firewall actions still require owner approval. The existing browser app remains loopback-only; no ingest listener has been deployed.

## Current evidence

- Owner confirmed Porkbun registration and Cloudflare DNS access for mgilham.online. Router reported as EE Smart Hub SH32B; exact DHCP/resolver features remain unverified.
- Read-only ipconfig found current PC IPv4 192.168.1.190/24. This is not evidence of a reserved/stable address. P14 authorizes only the home connection's Private profile. Runtime tools must independently recheck address, interface, profile and DNS before activation; actual observations are recorded only in PLAN.md.
- Public A lookups for both sync.mgilham.online and sleepiq.mgilham.online returned Cloudflare addresses (104.21.25.110 and 172.67.134.16). These could be explicit entries or a wildcard. Do not replace an existing record until the owner checks the zone. Public lookup alone does not reveal the origin or prove the hostname is unused.
- Owner has not configured a saved export yet; earlier manual upload worked. E01 file diagnostics can remain pending while secure setup proceeds. Do not make an insecure test receiver or require a raw export upload to chat.

## Proposed bounded setup, subject to review

1. P11 selected sync.mgilham.online and the owner added its specific record. Public certificates appear in certificate-transparency logs, so hostname metadata is public; health records and credentials are not part of issuance.
2. P12 explicitly defers router address reservation. Recheck the current PC address before binding or DNS-related action; retain reservation as a future reliability item.
3. P11 DNS-only A record is added and PC-verified at 192.168.1.190, with existing root/email records preserved. Test lookup from phone Wi-Fi before proceeding. Some resolver/router configurations reject private answers for public names; treat that as a compatibility checkpoint, not a reason to disable protections silently. No Cloudflare proxy/tunnel or router port forwarding.
4. Use the P13-approved checksum-verified, pinned Windows lego binary in a user-owned tool folder for DNS-01 certificate issuance/renewal. Restrict Cloudflare token Zone Read/DNS Edit to this zone only, not the global account key. Keep tokens and certificate private keys local/private and out of logs, arguments, ordinary backups and chat. Renew while manually running the app, with visible expiry/failure handling; no Windows autostart task. Actual installation/issuance evidence is tracked only in PLAN.md.
5. Dedicated ingest app on the current verified LAN IPv4 (reservation deferred by P12), proposed TCP 8443, mandatory 256-bit credential and validated TLS. Windows firewall rule must be limited to that interface/address, TCP port, Private profile, local subnet and project Python executable. Confirm actual network profile and show the exact rule plus rollback before asking for approval. Never expose browser/admin routes through this listener.
6. Prove real iPhone/exporter TLS compatibility, wrong-credential rejection and browser/admin isolation with synthetic data first. Configure regular real uploads only after the relevant safety/owner gates. No plaintext fallback or validation bypass.

## Completed owner check (historical)

Owner identified a wildcard CNAME and subsequently added the specific sync A record under P11. Do not repeat this completed check or request a zone export/API key in chat. The next unresolved checkpoint is CERTIFICATE_SETUP.md.

References: [lego Cloudflare provider](https://go-acme.github.io/lego/dns/cloudflare/), [Let's Encrypt DNS challenges](https://letsencrypt.org/docs/challenge-types/), [certificate transparency](https://letsencrypt.org/docs/ct-logs/), [Cloudflare token scoping](https://developers.cloudflare.com/fundamentals/api/get-started/create-token/). These document capabilities; they do not prove this PC/router/exporter combination works. Track actual evidence and approvals only in PLAN.md.

## Owner-confirmed wildcard

Owner observed a CNAME at *.mgilham.online. Preserve it. Subject to owner approval, add one explicit DNS-only A record for sync to the confirmed private PC IPv4, TTL Auto, only if no explicit sync record exists. This overrides the wildcard for that name without deleting it or altering mail/root records. The address must be reserved/confirmed before relying on permanent delivery; test resolution from the phone before certificate/listener deployment.

## P11 executed and checked

Owner saved the approved new DNS-only A record. Read-only PC lookup returned the approved private address; current evidence is in PLAN.md. Phone resolution remains to be tested and router reservation is deferred by P12. No wildcard/root/mail record modification was requested. P13 covers certificate issuance; firewall/listener activation requires a separate concrete approval.

## P12 owner deferral

Router address reservation is explicitly deferred. Do not ask the owner to enter the hub or configure it now. Continue HTTPS preparation at the currently verified 192.168.1.190; recheck it before binding or creating any rule. An address change can break uploads until DNS/binding is updated. Reservation remains a future reliability checklist item. The owner encountered a router certificate warning and continued manually; no router setting changes or blanket certificate trust exceptions were approved.

## Prepared certificate and synthetic probe checkpoint

See CERTIFICATE_SETUP.md for the complete reviewable client/token/issuance proposal. S01 probe source and tests are implemented without launching a listener. /transport-check accepts only the fixed synthetic message; /api/ingest returns 503 rather than acknowledging discarded health data. Middleware tests enforce HTTPS scope, hostname/private source, no browser Origin, constant-time credential validation/rotation, request frequency, size/chunk/type/encoding and timeout limits. Real handshake/chain/expiry/iPhone tests remain pending; synthetic ASGI HTTPS scope is not proof of TLS compatibility. No browser/admin app is mounted in the probe.

## Reviewable synthetic receiver activation (separate approval required)

`scripts/probe-firewall.ps1` defaults to Preview (read-only). Add creates exactly one rule named `SleepIQ-Synthetic-HTTPS-8443`: inbound Allow, TCP local port 8443, local address 192.168.1.190, remote addresses 192.168.1.0/24, Private profile only, interface owning that IPv4 address only, program `C:\Users\Matth\projects\SleepIQ\.venv\Scripts\python.exe`, edge traversal Block. It refuses an existing rule rather than modifying it. It does not alter other firewall rules or start a process. Existing broad rules, if present, are not narrowed by this rule; application source/auth restrictions remain mandatory. No router forwarding, tunnel or public listener is included.

After explicit owner approval, Add/Remove require an administrator PowerShell; Preview and the receiver run as the normal owner. Full commands (do not execute activation before approval):

```powershell
# Read-only preview, normal terminal:
powershell -File "C:\Users\Matth\projects\SleepIQ\scripts\probe-firewall.ps1"
# Approved activation only, administrator terminal:
powershell -File "C:\Users\Matth\projects\SleepIQ\scripts\probe-firewall.ps1" -Mode Add
# Approved receiver only, NORMAL terminal:
powershell -File "C:\Users\Matth\projects\SleepIQ\scripts\start-probe.ps1" -Activate
# Rollback, administrator terminal:
powershell -File "C:\Users\Matth\projects\SleepIQ\scripts\probe-firewall.ps1" -Mode Remove
```

The normal-user launcher checks private certificate directories and current hostname/validity (at least one day remaining), generates a 32-byte random credential once into Windows-user-encrypted `security/ingest-token.dpapi`, and passes it only through the child process environment. It is never printed or used in command arguments. The child removes its credential environment entry, validates certificate/key pairing before binding, requires TLS >=1.2, ignores proxy headers, disables WebSockets/access logs/server header, caps concurrent requests and serves only the synthetic probe. DPAPI and directory checks do not protect against a malicious process already running as this Windows account. This launcher does not perform renewal or establish remote client trust; those remain separate verification gates.

Ctrl+C stops the foreground receiver. The firewall rule persists until removed; removal plus stopping the receiver is the test rollback. Keep the private token/certificate files for subsequent approved tests; do not delete credentials/data automatically. No startup task/service is installed. Health Auto Export must not yet send real readings here: `/api/ingest` returns 503 and `/transport-check` accepts only `{ "probe": "sleepiq" }`.

## Synthetic verification after receiver start

Keep the receiver's normal-user console open. From another normal-owner PowerShell:

```powershell
powershell -File "C:\Users\Matth\projects\SleepIQ\scripts\verify-probe.ps1"
```

The verifier rechecks the home network and reads only the local encrypted ingest credential. It sends a fixed synthetic payload, with ordinary Windows HTTPS validation and redirects disabled. Checks cover benign health JSON, authenticated POST with stored=false, missing/wrong credential rejection, hostile browser Origin rejection, absent dashboard/status/docs routes and disabled real importer. Output contains fixed labels/status codes, never credentials or response bodies. No health file, database or Cloudflare credential is used. These are PC-to-receiver tests; they do not replace phone-origin POST/exporter compatibility or negative certificate tests. After the supervised session, stop the receiver with Ctrl+C.

## Owner-operated iPhone synthetic POST

**Optional reference only; omitted by owner decision P16. Do not ask the owner to build this test Shortcut or run its credential viewer.** Check actual phone authentication through Health Auto Export once the importer is ready, before routine real ingestion. The completed Safari HTTPS test and PC authenticated POST remain distinct evidence.

Use only the approved home Wi-Fi/HTTPS receiver. Restart start-probe.ps1 -Activate in normal PowerShell only if it is stopped; do not add the firewall rule again. In Shortcuts create a test with:

1. Ask for Input, type Text, empty default, prompt “SleepIQ test credential”.
2. Get Contents of URL with the fixed literal https://sync.mgilham.online:8443/transport-check, method POST. Replace any automatically selected input in the URL field with this literal address; never put the credential in the URL.
3. Authorization header value: Bearer followed by one space and the magic Provided Input variable from Ask for Input. Do not type the actual credential into the saved header or any Text/default action.
4. Request Body JSON containing exactly one Text field: probe = sleepiq. Set Content-Type application/json if needed.
5. Show Result using the Get Contents of URL result.

Apple documents [POST and JSON request bodies](https://support.apple.com/guide/shortcuts/request-your-first-api-apd58d46713f/ios); actual field labels/permissions must be confirmed on the owner's phone. Do not grant permission for an unrelated hostname or bypass a certificate warning.

Only after the Shortcut is configured, the owner runs view-ingest-credential.ps1 -Show in normal PowerShell. The viewer reads only the existing private DPAPI ingest token, never the Cloudflare token, and starts masked in a native window. The owner can explicitly reveal it and manually type it into the Shortcut's runtime prompt. No console/clipboard/network/plaintext-file output is implemented; the window closes after three minutes or Close. Do not send screenshots/photos of it, paste it into chat/email, or run the viewer through an agent capture. Normal process/screen access by other software running as this user remains outside its protection.

Run the Shortcut with a deliberately wrong runtime input first: expect HTTP401/Unauthorized. Then rerun with the real local credential: expect status transport_ok and stored=false. Report only the sanitized result, not the credential or request headers. This is a Shortcuts test, not Health Auto Export compatibility or real-data import evidence. Close the viewer and stop the foreground receiver with Ctrl+C at the end. Existing single-rule firewall rollback remains available.
