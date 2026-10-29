import json

import pytest
from app.diagnostics.export_shape import UNITS, diagnose


def test_six_metric_shapes_without_disclosing_values() -> None:
    payload = {
        "data": {
            "metrics": [
                {
                    "name": name,
                    "units": unit,
                    "data": [
                        {
                            "start": "2026-10-25 01:48:29 +0100",
                            "end": "2026-10-25 01:12:31 +0000",
                            "qty": 12345.6789,
                            "source": "private-source-marker",
                            "id": "private-id-marker",
                            "heartbeatSeries": [{"private-nested-key": "private-heartbeat-marker"}],
                            "private-field-marker": "private-value-marker",
                        }
                    ],
                }
                for name, unit in UNITS.items()
            ]
        }
    }
    report = diagnose(payload)
    serialized = json.dumps(report)
    for marker in ["private-", "12345.6789", "2026-10-25"]:
        assert marker not in serialized
    assert report["measurement_values_included"] is False
    for shape in report["metrics"].values():
        assert shape["samples"] == 1
        assert shape["interval_patterns"]["positive"] == 1


def test_unknown_names_and_units_not_echoed() -> None:
    report = diagnose(
        {
            "data": {
                "metrics": [
                    {"name": "private-unknown-marker", "data": []},
                    {"name": "heart_rate", "units": "private-unit-marker", "data": []},
                ]
            }
        }
    )
    assert report["unknown_metric_blocks"] == 1
    assert "private-" not in json.dumps(report)


def test_identity_counts_do_not_claim_verified_corrections() -> None:
    row = {"id": "private-id-marker", "Avg": 50}
    report = diagnose(
        {
            "data": {
                "metrics": [
                    {
                        "name": "heart_rate",
                        "units": "count/min",
                        "data": [row, row, {**row, "Avg": 51}],
                    }
                ]
            }
        }
    )
    shape = report["metrics"]["heart_rate"]
    assert shape["repeated_identity"] == 2
    assert shape["changed_identity"] == 1
    assert report["correction_identity"] == "not_verified_by_presence_alone"
    assert "private-id-marker" not in json.dumps(report)


@pytest.mark.parametrize("payload", [None, [], {}, {"data": {}}, {"data": {"metrics": {}}}])
def test_bad_envelope_fails_safely(payload: object) -> None:
    with pytest.raises(TypeError, match="Unsupported"):
        diagnose(payload)


def test_malformed_rows_and_unzoned_samples_are_counted() -> None:
    report = diagnose(
        {
            "data": {
                "metrics": [
                    {
                        "name": "heart_rate",
                        "units": "count/min",
                        "data": [
                            None,
                            {"start": "2026-01-01T01:00:00", "end": "2026-01-01T02:00:00"},
                        ],
                    }
                ]
            }
        }
    )
    shape = report["metrics"]["heart_rate"]
    assert shape["malformed_samples"] == 1
    assert shape["interval_patterns"]["invalid_or_unzoned"] == 1
