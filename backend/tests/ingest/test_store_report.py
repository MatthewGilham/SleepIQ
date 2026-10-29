from datetime import date
from pathlib import Path

from app.ingest import store
from app.ingest.report import report
from factories import block, merge, new_store, night_blocks, payload


def test_report_is_counts_only_and_explains_rejected_sleep_labels(scratch: Path) -> None:
    data, engine = new_store(scratch)
    odd = block(
        "sleep_analysis",
        "hr",
        [
            {
                "start": "2026-01-01 01:00:00 +0000",
                "end": "2026-01-01 02:00:00 +0000",
                "value": "In Bed",
                "source": "Synthetic Apple Watch",
            },
            {
                "start": "2026-01-01 01:00:00 +0000",
                "end": "2026-01-01 02:00:00 +0000",
                "value": "Private Label",
                "source": "Synthetic Apple Watch",
            },
        ],
    )
    store.import_bytes(engine, data, payload(merge(night_blocks(date(2026, 1, 3)), [odd])))
    engine.dispose()
    summary = report(data)
    assert summary["nights"] == 1 and summary["batches"] == 1
    assert summary["rejected_sleep_labels_in_raw"] == {"In Bed": 1, "other": 1}
    text_form = repr(summary)
    assert "Private Label" not in text_form and "Synthetic" not in text_form
    assert summary["sleep_sources"] == [
        {"rows": 7, "label_has_apple_watch": True, "label_has_watch": True, "label_empty": False}
    ]
    assert summary["night_range"] == ("2026-01-03", "2026-01-03")


def test_report_includes_certificate_expiry_only_as_days_and_state(tmp_path):
    import json
    from datetime import UTC, datetime, timedelta

    data, engine = new_store(tmp_path)
    engine.dispose()
    assert report(data)["certificate"] == "not recorded"
    (data / "security").mkdir()
    expires = (datetime.now(UTC) + timedelta(days=20, hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    (data / "security" / "certificate-status.json").write_text(
        json.dumps({"not_after_utc": expires, "last_result": "failed"}), encoding="utf-8"
    )
    cert = report(data)["certificate"]
    assert cert["state"] == "due" and cert["days_left"] == 20 and cert["last_result"] == "failed"
