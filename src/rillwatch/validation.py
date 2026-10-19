"""Strict, total validation: arbitrary JSON values never crash validation."""

import json
import math
import re
from datetime import datetime, timezone

MODELS = ("leak_detector", "pressure_drop_predictor", "demand_forecaster")
FIELDS = (
    "reading_id",
    "station_id",
    "model_name",
    "predicted_label",
    "confidence_score",
    "response_time_ms",
    "timestamp",
)
LABELS = {
    "leak_detector": ("leak", "normal"),
    "pressure_drop_predictor": ("drop", "stable"),
}


def finite(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def timestamp_valid(value):
    try:
        if finite(value):
            return (
                value > 0 and datetime.fromtimestamp(value, timezone.utc).year >= 1970
            )
        if not isinstance(value, str) or not re.match(
            r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", value
        ):
            return False
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except (ValueError, OverflowError, OSError):
        return False


def validate(record):
    if not isinstance(record, dict):
        return ["json_not_object"]
    errors = [f"missing:{key}" for key in FIELDS if key not in record]
    if "reading_id" in record and not (
        type(record["reading_id"]) is int and record["reading_id"] > 0
    ):
        errors.append("reading_id_invalid")
    if "station_id" in record and not (
        isinstance(record["station_id"], str)
        and re.fullmatch(r"ST-(0[1-9]|10)", record["station_id"])
    ):
        errors.append("station_id_invalid")
    model = record.get("model_name")
    if not isinstance(model, str) or model not in MODELS:
        errors.append("model_name_invalid")
    if "predicted_label" in record:
        label = record["predicted_label"]
        valid = (
            (type(label) is int and 1 <= label <= 5000)
            if model == "demand_forecaster"
            else (
                isinstance(model, str)
                and model in LABELS
                and isinstance(label, str)
                and label in LABELS[model]
            )
        )
        if not valid:
            errors.append("predicted_label_invalid")
    for name, valid in [
        ("confidence_score", lambda x: finite(x) and 0 <= x <= 1),
        ("response_time_ms", lambda x: finite(x) and x > 0),
        ("timestamp", timestamp_valid),
    ]:
        if name in record and not valid(record[name]):
            errors.append(name + "_invalid")
    return errors


def _constant(value):
    raise ValueError("non_finite_json_constant")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def parse(raw):
    try:
        record = json.loads(
            raw.decode("utf-8"), parse_constant=_constant, object_pairs_hook=_pairs
        )
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None, ["json_decode_invalid"]
    return record, validate(record)
