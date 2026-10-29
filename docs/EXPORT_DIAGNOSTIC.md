# Owner-supervised export diagnostic

P4 approves local structure/count inspection of an explicitly selected Health Auto Export JSON file. Do not upload the export, paste its contents into chat or put it in this repository. This tool is not the importer and does not write the database.

From ordinary project PowerShell, run:

```powershell
powershell -File scripts/diagnose-export.ps1
```

When PowerShell asks for `ExportPath`, enter the full path of a JSON export already on your PC. The script reads only that file locally (up to 64 MiB), emits a metadata-only JSON report and restores its temporary import-path environment setting. It creates no credentials, API request, log, output report file or DB record. If no export is on your PC, stop and ask for guided transfer/export instructions instead; never upload one to chat.

The output contains the six configured metric names, sample counts, presence counts for a fixed set of fields, expected-unit matches, interval-shape counts and repeated/changed string-identity counts. It excludes measurement values, actual timestamps, unknown metric/unit/field names, device/source labels, heartbeat-series contents, IDs and hashes. Errors print a generic message without payload or file path. The owner may review and share this report for planning; it is not a real-health-data fixture for Git/CI.

Presence of an ID does not prove that it remains stable across exports, and a single file cannot prove correction ordering, full-history/delta delivery or unattended recovery. Those remain explicit evidence gates. Point-versus-interval counts do not prove physiological measurement coverage; weighting rules still require careful interpretation. Do not silently activate automatic replacement or weighted HR based on this report alone.

The actual exporter adapter supports only validated field shapes. Unknown or malformed blocks in a report are reasons for a controlled adapter review, not permission to drop measurements or broaden scope. Test evidence/progress is maintained only in PLAN.md.

The report's malformed_samples count checks for non-object entries, not numeric/stage/clinical validity. Expected-unit matches apply to metric blocks, not every reading. Field presence does not establish field value/type correctness or equality of timestamp aliases. If all recognized ID fields are absent, zero repeated/changed identity counts are inconclusive. This diagnostic does not prove that records are the original Apple Health granularity or that every night is complete. Heartbeat-series presence is not validation of its contents.
