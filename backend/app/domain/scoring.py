"""Pure, versioned SleepIQ scoring and circular consistency (SCORING.md, P2/P33)."""

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import pairwise

from app.domain.config import SCORE, ScoreConfig, ScoreV2Config

DAY_MINUTES = 1440.0


def interpolate(points: Sequence[tuple[float, float]], x: float) -> float:
    """Piecewise-linear through points; flat beyond the last point, caller handles the low tail."""
    if x >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in pairwise(points):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[0][1]


def duration_score(asleep_seconds: int, cfg: ScoreConfig = SCORE) -> float:
    hours = asleep_seconds / 3600
    first_hours, first_score = cfg.duration_points[0]
    if hours < first_hours:
        return max(0.0, first_score + cfg.duration_slope_per_hour * (hours - first_hours))
    return interpolate(cfg.duration_points, hours)


def efficiency_score(efficiency: float, cfg: ScoreConfig = SCORE) -> float:
    """`efficiency` is a 0-1 fraction of stage-based sleep / (sleep + recorded Awake)."""
    return interpolate(cfg.efficiency_points, min(max(efficiency * 100, 0.0), 100.0))


def circular_distance(a: float, b: float) -> float:
    """Minutes between two clock times, wrapping midnight; always within [0, 720]."""
    difference = abs(a - b) % DAY_MINUTES
    return min(difference, DAY_MINUTES - difference)


def circular_mean(minutes: Sequence[float]) -> tuple[float, float]:
    """(mean clock minute, resultant length R in [0, 1]); R near 0 means no stable mean."""
    sines = math.fsum(math.sin(m / DAY_MINUTES * math.tau) for m in minutes)
    cosines = math.fsum(math.cos(m / DAY_MINUTES * math.tau) for m in minutes)
    angle = math.atan2(sines, cosines) % math.tau
    return angle / math.tau * DAY_MINUTES, math.hypot(sines, cosines) / len(minutes)


@dataclass(frozen=True)
class Consistency:
    available: bool
    reason: str | None = None
    score: float | None = None
    onset_deviation: float | None = None
    wake_deviation: float | None = None
    nights: int = 0
    provisional: bool = False


def consistency(
    onset: float,
    wake: float,
    prior: Sequence[tuple[float, float]],
    cfg: ScoreConfig = SCORE,
) -> Consistency:
    """`prior` holds (onset, wake) clock minutes of eligible nights in the preceding window."""
    if len(prior) < cfg.min_baseline_nights:
        return Consistency(False, "insufficient_history", nights=len(prior))
    onset_mean, onset_r = circular_mean([p[0] for p in prior])
    wake_mean, wake_r = circular_mean([p[1] for p in prior])
    if min(onset_r, wake_r) < cfg.min_resultant_length:
        return Consistency(False, "no_stable_baseline", nights=len(prior))
    deviations = (circular_distance(onset, onset_mean), circular_distance(wake, wake_mean))
    parts = [min(max(100 - cfg.penalty_per_minute * d, 0.0), 100.0) for d in deviations]
    return Consistency(
        True,
        score=(parts[0] + parts[1]) / 2,
        onset_deviation=deviations[0],
        wake_deviation=deviations[1],
        nights=len(prior),
        provisional=len(prior) < cfg.provisional_below_nights,
    )


@dataclass(frozen=True)
class Score:
    status: str  # "scored" | "insufficient_data"
    overall: float | None
    missing: tuple[str, ...] = ()
    components: dict[str, dict[str, object]] = field(default_factory=dict)


def score_night(
    asleep_seconds: int,
    efficiency: float,
    cons: Consistency,
    hr_mean: float | None,
    hrv_mean: float | None,
    cfg: ScoreConfig = SCORE,
    *,
    deep_seconds: float | None = None,
    rem_seconds: float | None = None,
) -> Score:
    """S4: missing required inputs withhold the total; S16 HRV gating applies only to pilot-1."""
    missing: list[str] = []
    if not cons.available:
        missing.append(f"consistency:{cons.reason}")
    if hr_mean is None:
        missing.append("sleeping_hr")
    if hrv_mean is None and not isinstance(cfg, ScoreV2Config):
        missing.append("overnight_hrv")
    values: dict[str, tuple[float, bool]] = {
        "duration": (duration_score(asleep_seconds, cfg), False),
    }
    if not isinstance(cfg, ScoreV2Config):
        values.update(
            {
                "efficiency": (efficiency_score(efficiency, cfg), False),
                "deep": (cfg.neutral, True),
                "rem": (cfg.neutral, True),
                "physiology": (cfg.neutral, True),
            }
        )
    if cons.available and cons.score is not None:
        values["consistency"] = (cons.score, False)
    if isinstance(cfg, ScoreV2Config):
        for name, value, points in (
            ("deep", None if deep_seconds is None else deep_seconds / 60, cfg.deep_points),
            ("rem", None if rem_seconds is None else rem_seconds / 60, cfg.rem_points),
            ("sleeping_hr", hr_mean, cfg.hr_points),
        ):
            if value is None or not math.isfinite(value):
                if name not in missing:
                    missing.append(name)
            else:
                # Flat outside either end, including the approved HR <45 plateau.
                bounded = max(points[0][0], min(value, points[-1][0]))
                values[name] = (min(100.0, max(0.0, interpolate(points, bounded))), False)
    weights = dict(cfg.weights)
    components: dict[str, dict[str, object]] = {
        name: {"score": value, "weight": weights[name], "neutral": neutral}
        for name, (value, neutral) in values.items()
    }
    if isinstance(cfg, ScoreV2Config):
        for name, weight in weights.items():
            components.setdefault(name, {"score": None, "weight": weight, "neutral": False})
    if missing:
        return Score("insufficient_data", None, tuple(missing), components)
    overall = math.fsum(values[name][0] * weight for name, weight in weights.items()) / sum(
        weights.values()
    )
    return Score("scored", overall, (), components)
