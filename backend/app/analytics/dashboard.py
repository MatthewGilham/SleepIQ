"""Latest-night dashboard read model. Reads derived rows and stage intervals; never writes."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, text

from app.domain.config import DERIVE, SCORE

NEUTRAL = ("deep", "rem", "physiology")
PHYSIOLOGY = (
    ("hr", "Sleeping heart rate"),
    ("hrv", "Overnight HRV"),
    ("resp", "Respiratory rate"),
    ("temp", "Sleeping wrist temperature"),
)


def ceiling() -> float:
    """Best possible overall while Deep, REM and physiology stay neutral (config-derived)."""
    weights = dict(SCORE.weights)
    total = sum(
        weight * (SCORE.neutral if name in NEUTRAL else 100.0) for name, weight in weights.items()
    )
    return total / sum(weights.values())


def _local(utc_seconds: int, offset_min: int) -> str:
    moment = datetime.fromtimestamp(utc_seconds, UTC) + timedelta(minutes=offset_min)
    return moment.strftime("%Y-%m-%dT%H:%M")


def _score(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    details = json.loads(row["details_json"])
    return {
        "status": row["status"],
        "overall": row["overall"],
        "consistency": row["consistency"],
        "version": row["score_version"],
        "ceiling": ceiling(),
        "missing": details.get("missing", []),
        "components": details.get("components", {}),
        "consistency_detail": details.get("consistency", {}),
    }


def dashboard(engine: Engine, synthetic: bool) -> dict[str, Any]:
    with engine.connect() as conn:
        night = (
            conn.execute(
                text(
                    "SELECT * FROM nightly_metrics WHERE derivation_version=:v "
                    "ORDER BY wake_date DESC LIMIT 1"
                ),
                {"v": DERIVE.version},
            )
            .mappings()
            .first()
        )
        batches = conn.execute(text("SELECT count(*), max(received_utc) FROM import_batches")).one()
        nights = conn.execute(
            text("SELECT count(*) FROM nightly_metrics WHERE derivation_version=:v"),
            {"v": DERIVE.version},
        ).scalar_one()
        result: dict[str, Any] = {
            "synthetic": synthetic,
            "versions": [DERIVE.version, SCORE.version],
            "import": {
                "batches": batches[0],
                "last_received_utc": batches[1],
                "nights": nights,
            },
            "latest": None,
            "trend": {"dates": [], "asleep_h": []},
        }
        if night is None:
            return result
        score = (
            conn.execute(
                text(
                    "SELECT * FROM nightly_scores WHERE wake_date=:d AND score_version=:s "
                    "AND derivation_version=:v"
                ),
                {"d": night["wake_date"], "s": SCORE.version, "v": DERIVE.version},
            )
            .mappings()
            .first()
        )
        start, end = night["session_start_utc"], night["session_end_utc"]
        stages = [
            {"stage": r[0], "start_s": r[1] - start, "duration_s": r[2] - r[1]}
            for r in conn.execute(
                text(
                    "SELECT stage, start_utc, end_utc FROM observations "
                    "WHERE metric='sleep_analysis' AND status='active' AND source=:src "
                    "AND start_utc>=:a AND end_utc<=:b AND stage IS NOT NULL "
                    "ORDER BY start_utc, id"
                ),
                {"src": night["source"], "a": start, "b": end},
            )
        ]
        recent = conn.execute(
            text(
                "SELECT wake_date, asleep_s FROM nightly_metrics WHERE derivation_version=:v "
                "AND wake_date>date(:d, '-29 days') AND wake_date<=:d ORDER BY wake_date"
            ),
            {"v": DERIVE.version, "d": night["wake_date"]},
        ).all()
    by_day = {r[0]: r[1] for r in recent}
    last = datetime.fromisoformat(night["wake_date"]).date()
    days = [(last - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    result["trend"] = {
        "dates": days,
        "asleep_h": [by_day[d] / 3600 if d in by_day else None for d in days],
    }
    result["latest"] = {
        "wake_date": night["wake_date"],
        "source": night["source"],
        "onset_local": _local(start, night["start_offset_min"]),
        "wake_local": _local(end, night["end_offset_min"]),
        "start_offset_min": night["start_offset_min"],
        "end_offset_min": night["end_offset_min"],
        "session_s": end - start,
        "asleep_s": night["asleep_s"],
        "core_s": night["core_s"],
        "deep_s": night["deep_s"],
        "rem_s": night["rem_s"],
        "awake_s": night["awake_s"],
        "efficiency": night["efficiency"],
        "physiology": [
            {"id": key, "label": label, "value": night[f"{key}_mean"], "n": night[f"{key}_n"]}
            for key, label in PHYSIOLOGY
        ],
        "flags": json.loads(night["flags_json"]),
        "stages": stages,
        "score": _score(score),
    }
    return result
