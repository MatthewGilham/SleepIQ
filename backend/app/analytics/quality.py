"""HR provenance shared by dashboard, charts and exports; no raw source identifiers."""

from collections.abc import Mapping
from typing import Any


def hr_quality(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        "method": row["hr_method"],
        "n": row["hr_n"],
        "eligible_n": row.get("hr_eligible_n"),
        "contributing_n": row.get("hr_contributing_n"),
        "covered_s": row.get("hr_covered_s"),
        "window_s": row.get("hr_window_s"),
        "coverage": row.get("hr_coverage"),
        "fallback_reason": row.get("hr_fallback_reason"),
    }
