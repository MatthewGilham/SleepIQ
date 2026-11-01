"""P34: time-weighted estimate from individual HR points, with explicit mean fallback."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import pairwise

from app.domain.config import WEIGHTED_DERIVE, WeightedDeriveConfig


@dataclass(frozen=True)
class HRReading:
    start: int
    end: int
    value: float
    source: str


@dataclass(frozen=True)
class HRResult:
    mean: float | None
    n: int
    method: str | None
    eligible_n: int
    contributing_n: int | None
    covered_s: int | None
    window_s: int
    coverage: float | None
    fallback_reason: str | None = None


def sleeping_hr(
    readings: Sequence[HRReading],
    start: int,
    end: int,
    source: str,
    cfg: WeightedDeriveConfig = WEIGHTED_DERIVE,
) -> HRResult:
    """Caller supplies active observations; coverage means interpolation support, not wear time."""
    if end <= start:
        raise ValueError("Positive sleep window required")
    if (
        cfg.hr_max_gap_seconds <= 0
        or not 0 < cfg.hr_coverage_numerator <= cfg.hr_coverage_denominator
        or cfg.hr_input_assumption != "individual_points"
    ):
        raise ValueError("Invalid HR interpolation policy")
    eligible = [
        r
        for r in readings
        if r.end >= r.start
        and 2 * start <= r.start + r.end <= 2 * end
        and math.isfinite(r.value)
        and 20 <= r.value <= 250
    ]
    n = len(eligible)
    result = HRResult(
        math.fsum(r.value for r in eligible) / n if n else None,
        n,
        "simple_mean_fallback" if n else None,
        n,
        None,
        None,
        end - start,
        None,
    )
    if not n:
        return replace(result, contributing_n=0, covered_s=0, coverage=0)
    if any(r.start != r.end for r in eligible):
        return replace(result, fallback_reason="unsupported_interval")
    streams = {r.source for r in eligible}
    watch = {s for s in streams if cfg.preferred_source.casefold() in s.casefold()}
    selected = (
        source if source and source in streams else next(iter(watch)) if len(watch) == 1 else None
    )
    if selected is None:
        return replace(result, fallback_reason="ambiguous_source")
    points: dict[int, float] = {}
    for r in eligible:
        if r.source != selected:
            continue
        if r.start in points and points[r.start] != r.value:
            return replace(result, fallback_reason="ambiguous_timestamp")
        points[r.start] = r.value
    ordered = sorted(points)
    areas: list[float] = []
    covered = 0
    contributing: set[int] = set()
    for a, b in pairwise(ordered):
        duration = b - a
        if duration <= cfg.hr_max_gap_seconds:
            areas.append((points[a] + points[b]) / 2 * duration)
            covered += duration
            contributing.update((a, b))
    result = replace(
        result,
        contributing_n=len(contributing),
        covered_s=covered,
        coverage=covered / (end - start),
    )
    if len(ordered) < 2:
        return replace(result, fallback_reason="insufficient_points")
    if not covered:
        return replace(result, fallback_reason="long_gaps")
    if cfg.hr_coverage_denominator * covered < cfg.hr_coverage_numerator * (end - start):
        return replace(result, fallback_reason="low_coverage")
    return replace(
        result, mean=math.fsum(areas) / covered, n=len(contributing), method="time_weighted_linear"
    )
