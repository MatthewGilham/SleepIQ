import math

import pytest
from app.domain.scoring import (
    Consistency,
    Score,
    circular_distance,
    circular_mean,
    consistency,
    duration_score,
    efficiency_score,
    score_night,
)

H = 3600


def test_duration_anchors_tails_and_plateau() -> None:
    assert duration_score(6 * H) == 40
    assert duration_score(7 * H) == 75
    assert duration_score(8 * H) == 100
    assert duration_score(9 * H) == 100 == duration_score(14 * H)  # S20 plateau
    assert duration_score(int(6.5 * H)) == pytest.approx(57.5)
    assert duration_score(int(7.5 * H)) == pytest.approx(87.5)
    assert duration_score(5 * H) == pytest.approx(5)  # P2: 40 + 35 * (5 - 6)
    assert duration_score(int(4.5 * H)) == 0  # clamped, not negative
    assert duration_score(0) == 0


def test_efficiency_curve() -> None:
    assert efficiency_score(0.0) == 0
    assert efficiency_score(0.4) == pytest.approx(30)
    assert efficiency_score(0.8) == pytest.approx(60)
    assert efficiency_score(0.9) == pytest.approx(85)
    assert efficiency_score(0.95) == pytest.approx(100)
    assert efficiency_score(1.0) == 100


def test_circular_distance_wraps_midnight() -> None:
    assert circular_distance(23 * 60 + 50, 10) == 20
    assert circular_distance(10, 23 * 60 + 50) == 20
    assert circular_distance(0, 720) == 720
    assert circular_distance(100, 100) == 0


def test_circular_mean_across_midnight() -> None:
    mean, length = circular_mean([23 * 60 + 50, 10])
    assert circular_distance(mean, 0) < 1e-6 and length > 0.99


def test_consistency_penalty_is_half_a_point_per_minute() -> None:
    prior = [(23 * 60.0, 7 * 60.0)] * 7
    assert consistency(23 * 60, 7 * 60, prior).score == pytest.approx(100)
    # onset 20 min late (-10), wake 40 min early (-20): (90 + 80) / 2
    result = consistency(23 * 60 + 20, 6 * 60 + 20, prior)
    assert result.score == pytest.approx(85)
    assert (result.onset_deviation, result.wake_deviation) == pytest.approx((20, 40))
    assert result.provisional and result.nights == 7
    assert consistency(11 * 60, 0, prior).score == pytest.approx(0)  # 0 floor
    assert consistency(23 * 60, 7 * 60, [(23 * 60.0, 7 * 60.0)] * 14).provisional is False


def test_consistency_needs_seven_prior_nights_and_a_stable_baseline() -> None:
    assert consistency(0, 0, [(0.0, 0.0)] * 6) == Consistency(
        False, "insufficient_history", nights=6
    )
    antipodal = [(0.0, 420.0)] * 4 + [(720.0, 420.0)] * 4
    assert consistency(0, 420, antipodal).reason == "no_stable_baseline"


def full(
    duration: int, efficiency: float, cons: float, hr: float | None, hrv: float | None
) -> Score:
    return score_night(duration, efficiency, Consistency(True, score=cons, nights=30), hr, hrv)


def test_owner_worked_examples() -> None:
    best = full(8 * H, 0.95, 100, 55, 40)
    assert best.status == "scored" and best.overall == pytest.approx(92.5, abs=1e-9)
    typical = full(7 * H, 0.90, 90, 55, 40)
    assert typical.overall == pytest.approx(80.25, abs=1e-9)
    assert best.components["deep"] == {"score": 75.0, "weight": 10, "neutral": True}
    assert math.isclose(sum(float(c["weight"]) for c in best.components.values()), 100)  # type: ignore[arg-type]


def test_missing_required_input_withholds_score_without_imputation() -> None:
    for hr, hrv, label in ((None, 40, "sleeping_hr"), (55, None, "overnight_hrv")):
        result = full(8 * H, 0.95, 100, hr, hrv)
        assert (result.status, result.overall) == ("insufficient_data", None)
        assert result.missing == (label,)
    unavailable = score_night(8 * H, 0.95, Consistency(False, "insufficient_history"), 55, 40)
    assert unavailable.missing == ("consistency:insufficient_history",)


def test_scores_stay_bounded_and_deterministic() -> None:
    low = full(0, 0.0, 0, 50, 50)
    assert low.overall == pytest.approx(22.5)  # theoretical eligible floor (P2)
    assert full(8 * H, 0.95, 100, 50, 50).overall == full(8 * H, 0.95, 100, 50, 50).overall
