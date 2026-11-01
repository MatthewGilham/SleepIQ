"""Owner-defined v2 curve and missing-input contracts; synthetic inputs only."""

import pytest
from app.domain.config import SCORE
from app.domain.scoring import Consistency, score_night


def scored(deep=90 * 60, rem=120 * 60, hr=48, hrv=None, cons=None):
    return score_night(
        8 * 3600,
        0.95,
        cons or Consistency(True, score=100),
        hr,
        hrv,
        deep_seconds=deep,
        rem_seconds=rem,
    )


@pytest.mark.parametrize(
    "name,minutes,expected",
    [
        ("deep", 0, 0),
        ("deep", 15, 17.5),
        ("deep", 30, 35),
        ("deep", 45, 52.5),
        ("deep", 60, 70),
        ("deep", 67.5, 77.5),
        ("deep", 75, 85),
        ("deep", 82.5, 92.5),
        ("deep", 90, 100),
        ("deep", 200, 100),
        ("rem", 0, 0),
        ("rem", 15, 11.665),
        ("rem", 30, 23.33),
        ("rem", 45, 35),
        ("rem", 60, 46.67),
        ("rem", 75, 58.335),
        ("rem", 90, 70),
        ("rem", 97.5, 77.5),
        ("rem", 105, 85),
        ("rem", 112.5, 92.5),
        ("rem", 120, 100),
        ("rem", 200, 100),
    ],
)
def test_stage_curves(name, minutes, expected):
    result = scored(**{name: minutes * 60})
    assert result.components[name]["score"] == pytest.approx(expected)


@pytest.mark.parametrize(
    "hr,expected",
    [
        (30, 100),
        (44.9, 100),
        (45, 100),
        (46.5, 100),
        (48, 100),
        (49, 90),
        (50, 80),
        (51, 70),
        (52, 60),
        (53, 50),
        (54, 40),
        (55, 30),
        (56, 20),
        (57, 10),
        (58, 0),
        (90, 0),
    ],
)
def test_hr_continuous_curve(hr, expected):
    assert scored(hr=hr).components["sleeping_hr"]["score"] == pytest.approx(expected)


def test_formula_weights_and_hrv_independence():
    assert SCORE.version == "score-2"
    assert dict(SCORE.weights) == {
        "duration": 25,
        "consistency": 25,
        "deep": 20,
        "rem": 20,
        "sleeping_hr": 10,
    }
    assert scored().overall == 100
    assert (
        score_night(
            8 * 3600,
            0.2,
            Consistency(True, score=100),
            48,
            None,
            deep_seconds=5400,
            rem_seconds=7200,
        ).overall
        == 100
    )
    assert scored(hrv=5) == scored(hrv=100) == scored(hrv=None)
    # 100 duration, 100 consistency, 70 deep, 70 REM, 40 HR.
    assert scored(deep=3600, rem=5400, hr=54).overall == pytest.approx(82)


@pytest.mark.parametrize(
    "kwargs,missing",
    [
        ({"hr": None}, "sleeping_hr"),
        ({"deep": None}, "deep"),
        ({"rem": None}, "rem"),
        ({"cons": Consistency(False, "insufficient_history")}, "consistency:insufficient_history"),
    ],
)
def test_missing_required_inputs(kwargs, missing):
    result = scored(**kwargs)
    assert result.status == "insufficient_data" and result.overall is None
    assert result.missing == (missing,)


def test_zero_is_observed_and_components_are_bounded():
    assert (
        score_night(
            0,
            0,
            Consistency(True, score=0),
            58,
            None,
            deep_seconds=0,
            rem_seconds=0,
        ).overall
        == 0
    )
    result = scored(deep=0, rem=0, hr=90)
    assert result.overall == 50
    for deep in (0, 1, 4000, 100000):
        for hr in (20, 45, 49.5, 80):
            result = scored(deep=deep, rem=deep, hr=hr)
            assert 0 <= result.overall <= 100
            assert all(0 <= part["score"] <= 100 for part in result.components.values())
