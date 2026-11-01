"""Explicit chart catalog. Values come only from versioned derived records."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    id: str
    label: str
    unit: str
    method: str
    factor: float = 1
    clock: bool = False


CATALOG = [
    Metric("asleep_s", "Total asleep", "h", "Recorded sleep stages", 1 / 3600),
    Metric("awake_s", "Recorded awake", "min", "Interior recorded Awake", 1 / 60),
    Metric("core_s", "Core", "min", "Recorded Core stages", 1 / 60),
    Metric("deep_s", "Deep", "min", "Recorded Deep stages; descriptive", 1 / 60),
    Metric("rem_s", "REM", "min", "Recorded REM stages; descriptive", 1 / 60),
    Metric("efficiency", "Sleep efficiency", "%", "Stage-based asleep / recorded stages", 100),
    Metric("hr_mean", "Sleeping heart rate", "bpm", "Simple mean fallback; coverage unknown"),
    Metric("hrv_mean", "Overnight HRV", "ms", "Mean of overnight SDNN samples"),
    Metric("resp_mean", "Respiratory rate", "breaths/min", "Overnight sample mean"),
    Metric("temp_mean", "Sleeping wrist temperature", "°C", "Samples attributed by midpoint"),
    Metric("overall", "SleepIQ score", "/100", "score-2; maximum 100"),
    Metric("consistency", "Consistency", "/100", "Previous 30 calendar days"),
    Metric(
        "onset_minute",
        "Sleep onset",
        "local time",
        "Source-local clock; offsets retained",
        clock=True,
    ),
    Metric(
        "wake_minute", "Wake time", "local time", "Source-local clock; offsets retained", clock=True
    ),
]
BY_ID = {m.id: m for m in CATALOG}
