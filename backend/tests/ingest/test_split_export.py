import json
from datetime import date
from pathlib import Path

import pytest
from app.ingest import store
from app.ingest.split import split
from factories import block, merge, new_store, night_blocks, payload
from sqlalchemy import text


def dump(engine) -> list[tuple[object, ...]]:  # type: ignore[no-untyped-def]
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT fingerprint, status FROM observations ORDER BY fingerprint")
        )
        nights = conn.execute(
            text("SELECT wake_date, asleep_s, hr_mean, hrv_mean FROM nightly_metrics ORDER BY 1")
        )
        return [tuple(r) for r in rows] + [tuple(r) for r in nights]


def test_split_loses_nothing_and_importing_the_pieces_equals_importing_the_whole(
    scratch: Path,
) -> None:
    days = [
        date(2026, 1, 30),
        date(2026, 1, 31),
        date(2026, 2, 1),
        date(2026, 2, 2),
        date(2026, 3, 1),
    ]
    blocks = merge(*[night_blocks(d) for d in days])
    blocks.append(block("steps", "count", [{"x": 1}]))  # unmapped data is kept, not dropped
    blocks.append(block("respiratory_rate", "count/min", [{"start": "junk", "qty": 14}]))
    whole = scratch / "whole.json"
    whole.write_bytes(payload(blocks))
    counts = split(whole, scratch / "parts")
    assert set(counts) == {"2026-01", "2026-02", "2026-03", "other"}
    total = sum(len(b["data"]) for b in blocks)  # type: ignore[arg-type]
    assert sum(counts.values()) == total
    (scratch / "a").mkdir()
    (scratch / "b").mkdir()
    data_a, engine_a = new_store(scratch / "a")
    data_b, engine_b = new_store(scratch / "b")
    store.import_bytes(engine_a, data_a, whole.read_bytes())
    for part in sorted((scratch / "parts").glob("*.json"), reverse=True):  # any order
        store.import_bytes(engine_b, data_b, part.read_bytes())
    assert dump(engine_a) == dump(engine_b)
    assert json.loads((scratch / "parts" / "export-other.json").read_bytes())["data"]["metrics"]


def test_split_refuses_to_overwrite_and_rejects_bad_input(scratch: Path) -> None:
    source = scratch / "export.json"
    source.write_bytes(payload([block("respiratory_rate", "count/min", [])]))
    (scratch / "taken").mkdir()
    (scratch / "taken" / "keep.txt").write_text("x")
    with pytest.raises(ValueError, match="new or empty"):
        split(source, scratch / "taken")
    source.write_text("[]")
    with pytest.raises((TypeError, KeyError)):
        split(source, scratch / "fresh")
