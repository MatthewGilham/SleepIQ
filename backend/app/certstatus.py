"""Certificate expiry shown to the owner (P25). Reads only dates and a result word from the status file."""

import json
import math
from datetime import UTC, datetime
from pathlib import Path

DUE_DAYS = 30  # the renewal task acts at or below this
URGENT_DAYS = 14
RESULTS = frozenset({"none", "not_due", "renewed", "staging_ok", "failed", "rolled_back"})


def read(path: Path, now: datetime | None = None) -> dict[str, object]:
    """Never raises: a missing or malformed file is reported as `unknown`, not as healthy."""
    current = now or datetime.now(UTC)
    try:
        body = json.loads(path.read_text(encoding="utf-8-sig"))
        expires = datetime.fromisoformat(str(body["not_after_utc"]))
        if expires.tzinfo is None:
            raise ValueError("timezone required")
        result = str(body.get("last_result", "none"))
    except (OSError, ValueError, KeyError, TypeError):
        return {"state": "unknown", "days_left": None, "last_result": "none"}
    days = math.floor((expires - current).total_seconds() / 86400)
    if days < 0:
        state = "expired"
    elif days <= URGENT_DAYS:
        state = "urgent"
    elif days <= DUE_DAYS:
        state = "due"
    else:
        state = "ok"
    return {
        "state": state,
        "days_left": days,
        "expires": expires.date().isoformat(),
        "last_result": result if result in RESULTS else "none",
    }
