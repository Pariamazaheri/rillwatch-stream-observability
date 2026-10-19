import json
import math

import pytest

from rillwatch.simulator import Simulator
from rillwatch.validation import parse, validate


@pytest.fixture
def good():
    return Simulator(corruption=0).record(0, 0)


@pytest.mark.parametrize(
    "field",
    [
        "reading_id",
        "station_id",
        "model_name",
        "predicted_label",
        "confidence_score",
        "response_time_ms",
        "timestamp",
    ],
)
@pytest.mark.parametrize("value", [None, [], {}, True, "", float("inf"), float("nan")])
def test_adversarial_types_never_crash(good, field, value):
    good[field] = value
    assert validate(good)


@pytest.mark.parametrize(
    "model,label",
    [
        ("leak_detector", "normal"),
        ("pressure_drop_predictor", "drop"),
        ("demand_forecaster", 5000),
    ],
)
def test_model_labels(good, model, label):
    good.update(model_name=model, predicted_label=label)
    assert validate(good) == []


def test_multiple_errors(good):
    good.update(reading_id=-1, confidence_score=2, response_time_ms=-4)
    assert len(validate(good)) == 3


@pytest.mark.parametrize(
    "raw",
    [b"[]", b"null", b"{", b'{"x":NaN}', b'{"x":1,"x":2}', b"\xff", b'{"x":Infinity}'],
)
def test_invalid_json(raw):
    assert parse(raw)[1]


def test_overflow_is_invalid(good):
    good["response_time_ms"] = 10**1000
    assert validate(good)


def test_timestamp_requires_time(good):
    good["timestamp"] = "2026-01-01"
    assert "timestamp_invalid" in validate(good)


def test_numeric_infinity_from_json_overflow(good):
    good["response_time_ms"] = "OVERFLOW"
    raw = json.dumps(good).replace('"OVERFLOW"', "1e400").encode()
    assert "response_time_ms_invalid" in parse(raw)[1]
    good["response_time_ms"] = math.inf
    assert validate(good)
