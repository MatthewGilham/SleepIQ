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
