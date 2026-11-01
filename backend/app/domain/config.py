"""Owner-editable derivation and scoring parameters. Changing a value requires a version bump."""

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DeriveConfig:
    version: str = "derive-1"
    gap_seconds: int = 30 * 60  # P3: maximum gap joined into one session
    min_night_asleep_seconds: int = 3 * 3600  # shorter blocks are naps (D2), kept but ignored
    preferred_source: str = "watch"  # D4: case-insensitive substring of the source label
    qty_tolerance_seconds: int = 120  # stage `qty` hours vs timestamps cross-check
    completion_lookahead_seconds: int = 30 * 60  # later data must start this long after wake


@dataclass(frozen=True)
class ScoreConfig:
    version: str = "pilot-1"
    weights: tuple[tuple[str, int], ...] = (
        ("duration", 30),
        ("consistency", 25),
        ("efficiency", 15),
        ("deep", 10),
        ("rem", 10),
        ("physiology", 10),
    )
    neutral: float = 75.0  # P2: Deep, REM and combined HR/HRV are neutral in the pilot
    # (hours, score); below the first point P2 extends the 6->7 h slope, floored at zero.
    duration_points: tuple[tuple[float, float], ...] = ((6.0, 40.0), (7.0, 75.0), (8.0, 100.0))
    duration_slope_per_hour: float = 35.0
    # (efficiency percent, score); capped at the last point.
    efficiency_points: tuple[tuple[float, float], ...] = (
        (0.0, 0.0),
        (80.0, 60.0),
        (90.0, 85.0),
        (95.0, 100.0),
    )
    penalty_per_minute: float = 0.5  # S13: 10 points per 20 minutes
    baseline_days: int = 30
    min_baseline_nights: int = 7
    provisional_below_nights: int = 14
    min_resultant_length: float = 0.1  # below this the circular mean is undefined (P3 edge)

    def config_hash(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()


DERIVE = DeriveConfig()
PILOT_SCORE = ScoreConfig()  # Immutable pilot-1 definition retained for reproducibility.


@dataclass(frozen=True)
class ScoreV2Config(ScoreConfig):
    version: str = "score-2"
    weights: tuple[tuple[str, int], ...] = (
        ("duration", 25),
        ("consistency", 25),
        ("deep", 20),
        ("rem", 20),
        ("sleeping_hr", 10),
    )
    # Owner preferences, not medical thresholds. Units: minutes and bpm respectively.
    deep_points: tuple[tuple[float, float], ...] = (
        (0, 0),
        (30, 35),
        (60, 70),
        (75, 85),
        (90, 100),
    )
    rem_points: tuple[tuple[float, float], ...] = (
        (0, 0),
        (30, 23.33),
        (60, 46.67),
        (90, 70),
        (105, 85),
        (120, 100),
    )
    hr_points: tuple[tuple[float, float], ...] = (
        (45, 100),
        (48, 100),
        (50, 80),
        (52, 60),
        (54, 40),
        (56, 20),
        (58, 0),
    )


SCORE = ScoreV2Config()
SCORE_VERSIONS = {PILOT_SCORE.version: PILOT_SCORE, SCORE.version: SCORE}
