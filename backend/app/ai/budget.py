"""Local request counter for the P23 spend limits. Stores counts and token totals only, never text."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import Connection, Engine, text

from app.ai.config import LIMITS
from app.ai.provider import AiError
from app.db.coordinator import write_guard

KEY = "ai.usage.v1"
KEEP_DAYS = 62


def _read(conn: Connection) -> dict[str, dict[str, int]]:
    value = conn.execute(
        text("SELECT value_json FROM app_settings WHERE key=:k"), {"k": KEY}
    ).scalar()
    days: dict[str, dict[str, int]] = json.loads(value) if value else {}
    return days


def _write(conn: Connection, days: dict[str, dict[str, int]]) -> None:
    kept = dict(sorted(days.items())[-KEEP_DAYS:])
    conn.execute(
        text(
            "INSERT INTO app_settings(key,value_json) VALUES(:k,:v) "
            "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json"
        ),
        {"k": KEY, "v": json.dumps(kept)},
    )


def _counts(days: dict[str, dict[str, int]], today: date) -> dict[str, int]:
    month = today.strftime("%Y-%m")
    return {
        "today": days.get(today.isoformat(), {}).get("requests", 0),
        "month": sum(d.get("requests", 0) for k, d in days.items() if k.startswith(month)),
    }


def usage(engine: Engine, today: date) -> dict[str, Any]:
    with engine.connect() as conn:
        days = _read(conn)
    return _counts(days, today) | {"tokens_today": _tokens(days, today)}


def _tokens(days: dict[str, dict[str, int]], today: date) -> dict[str, int]:
    day = days.get(today.isoformat(), {})
    return {"input": day.get("input_tokens", 0), "output": day.get("output_tokens", 0)}


def reserve(engine: Engine, data: Path, today: date) -> None:
    """Count the request before it is sent, so a failed or slow call still counts."""
    with write_guard(data), engine.begin() as conn:
        days = _read(conn)
        counts = _counts(days, today)
        if counts["today"] >= LIMITS.per_day:
            raise AiError(429, "daily_limit", f"Daily limit of {LIMITS.per_day} analyses reached.")
        if counts["month"] >= LIMITS.per_month:
            raise AiError(
                429, "monthly_limit", f"Monthly limit of {LIMITS.per_month} analyses reached."
            )
        day = days.setdefault(today.isoformat(), {})
        day["requests"] = day.get("requests", 0) + 1
        _write(conn, days)


def record_tokens(
    engine: Engine, data: Path, today: date, input_tokens: int | None, output_tokens: int | None
) -> None:
    with write_guard(data), engine.begin() as conn:
        days = _read(conn)
        day = days.setdefault(today.isoformat(), {})
        day["input_tokens"] = day.get("input_tokens", 0) + max(0, input_tokens or 0)
        day["output_tokens"] = day.get("output_tokens", 0) + max(0, output_tokens or 0)
        _write(conn, days)
