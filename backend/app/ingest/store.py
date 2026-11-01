"""Atomic import: durable raw file, idempotent observations, derived rebuild, one transaction.

A batch is recorded only inside the same database transaction that stores its observations and
rebuilds affected nights, so a failure at any point leaves no batch row, no partial observations
and no stale derived rows. The content-addressed raw file is removed again if this call created it.
"""

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from sqlalchemy import Connection, Engine, text

from app.db.coordinator import write_guard
from app.domain.rebuild import latest_night, rebuild
from app.domain.sessions import local_date
from app.domain.versions import ActivePair, active_pair, ensure_current
from app.ingest.parse import (
    PARSER_VERSION,
    Observation,
    ParsedBatch,
    UnsupportedExport,
    parse_payload,
)

MAX_BYTES = 64 * 1024 * 1024
INSERT = (
    "INSERT INTO observations (batch_id, metric, source, start_utc, end_utc, start_offset_min, "
    "end_offset_min, stage, qty, avg, min, max, has_heartbeat_series, fingerprint, status) "
    "VALUES (:batch, :metric, :source, :start, :end, :so, :eo, :stage, :qty, :avg, :min, :max, "
    ":hb, :fp, 'active') ON CONFLICT(fingerprint) DO NOTHING"
)


@dataclass
class ImportResult:
    status: str  # "imported" | "duplicate_batch"
    batch_id: int
    new: int = 0
    duplicate: int = 0
    conflicting: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    unmapped_metrics: dict[str, int] = field(default_factory=dict)
    rebuilt_from: str | None = None


def _write_raw(raw: Path, digest: str, body: bytes) -> bool:
    """Atomically publish raw/<sha256>.json; True if this call created it."""
    target = raw / f"{digest}.json"
    if target.exists():
        return False
    temporary = raw / f".incoming-{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def _insert(conn: Connection, batch: int, obs: Observation) -> tuple[bool, bool]:
    """Return (inserted, conflicting). First received wins; later disagreements are flagged."""
    result = conn.execute(
        text(INSERT),
        {
            "batch": batch,
            "metric": obs.metric,
            "source": obs.source,
            "start": obs.start_utc,
            "end": obs.end_utc,
            "so": obs.start_offset_min,
            "eo": obs.end_offset_min,
            "stage": obs.stage,
            "qty": obs.qty,
            "avg": obs.avg,
            "min": obs.minimum,
            "max": obs.maximum,
            "hb": int(obs.has_heartbeat_series),
            "fp": obs.fingerprint,
        },
    )
    if result.rowcount == 0:
        return False, False
    new_id = result.lastrowid
    if obs.metric == "sleep_analysis":
        # Differently segmented stage rows from an earlier batch are a revision, not new sleep.
        clash = conn.execute(
            text(
                "SELECT 1 FROM observations WHERE metric = 'sleep_analysis' AND source = :s "
                "AND status = 'active' AND batch_id < :b AND start_utc < :e AND end_utc > :st "
                "LIMIT 1"
            ),
            {"s": obs.source, "b": batch, "e": obs.end_utc, "st": obs.start_utc},
        ).first()
    else:
        clash = conn.execute(
            text(
                "SELECT 1 FROM observations WHERE metric = :m AND source = :s AND status = 'active' "
                "AND start_utc = :st AND end_utc = :e AND id < :id LIMIT 1"
            ),
            {"m": obs.metric, "s": obs.source, "st": obs.start_utc, "e": obs.end_utc, "id": new_id},
        ).first()
    if clash:
        conn.execute(
            text("UPDATE observations SET status = 'conflicting' WHERE id = :id"), {"id": new_id}
        )
    return True, clash is not None


def import_bytes(
    engine: Engine, data: Path, body: bytes, *, received_utc: int | None = None,
    expected_pair: ActivePair | None = None,
) -> ImportResult:
    """Validate and import one export body. Raises UnsupportedExport before storing anything."""
    if len(body) > MAX_BYTES:
        raise UnsupportedExport("Export too large")
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError) as error:
        raise UnsupportedExport("Export is not valid JSON") from error
    parsed = parse_payload(payload)
    digest = hashlib.sha256(body).hexdigest()
    raw = data / "raw"
    with write_guard(data):
        with engine.connect() as conn:
            pair = active_pair(conn)
            if expected_pair is not None:
                ensure_current(conn, expected_pair)
            known = conn.execute(
                text("SELECT id FROM import_batches WHERE sha256 = :d"), {"d": digest}
            ).scalar()
        if known is not None:
            return ImportResult("duplicate_batch", known)
        created = _write_raw(raw, digest, body)
        try:
            with engine.begin() as conn:
                return _commit(conn, digest, body, parsed, received_utc, pair)
        except BaseException:
            if created:
                (raw / f"{digest}.json").unlink(missing_ok=True)
            raise


def _commit(
    conn: Connection, digest: str, body: bytes, parsed: ParsedBatch, received_utc: int | None,
    pair: ActivePair,
) -> ImportResult:
    new = duplicate = conflicting = 0
    touched: list[int] = []
    batch = conn.execute(
        text(
            "INSERT INTO import_batches (sha256, received_utc, byte_count, parser_version, "
            "summary_json) VALUES (:d, :r, :n, :p, '{}')"
        ),
        {
            "d": digest,
            "r": int(time.time()) if received_utc is None else received_utc,
            "n": len(body),
            "p": PARSER_VERSION,
        },
    ).lastrowid
    assert batch is not None
    for obs in parsed.observations:
        inserted, clash = _insert(conn, batch, obs)
        if not inserted:
            duplicate += 1
            continue
        new += 1
        conflicting += int(clash)
        touched.append(obs.start_utc)
    result = ImportResult(
        "imported",
        batch,
        new,
        duplicate,
        conflicting,
        dict(parsed.rejected),
        dict(parsed.unmapped_metrics),
    )
    if touched:
        # Rebuild from just before the earliest change, or from the latest stored night so that
        # its "possibly incomplete" flag is re-evaluated against the newly arrived data.
        earliest = local_date(min(touched), 0) - timedelta(days=2)
        latest = latest_night(conn, pair.derive_config)
        start = rebuild(conn, min(earliest, latest) if latest else earliest,
                        derive=pair.derive_config, score=pair.score_config)
        result.rebuilt_from = start.isoformat()
    summary = {
        "new": new,
        "duplicate": duplicate,
        "conflicting": conflicting,
        "rejected": result.rejected,
        "unmapped_metrics": result.unmapped_metrics,
        "rebuilt_from": result.rebuilt_from,
    }
    conn.execute(
        text("UPDATE import_batches SET summary_json = :j WHERE id = :id"),
        {"j": json.dumps(summary, sort_keys=True), "id": batch},
    )
    return result
