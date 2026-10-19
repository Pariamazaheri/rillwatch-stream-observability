"""Independently written seeded synthetic prediction telemetry; no trained models."""

import json
import random
from datetime import datetime, timedelta, timezone

from .validation import MODELS


class Simulator:
    def __init__(self, seed=42, drift=True, corruption=0.025):
        if not 0 <= corruption <= 1:
            raise ValueError("Invalid corruption probability")
        self.rng = random.Random(seed)
        self.drift = drift
        self.corruption = corruption

    def record(self, index, seconds):
        rng = self.rng
        model = MODELS[index % 3]
        conf = {
            "leak_detector": 0.88,
            "pressure_drop_predictor": 0.78,
            "demand_forecaster": 0.70,
        }[model]
        latency = {
            "leak_detector": 35,
            "pressure_drop_predictor": 55,
            "demand_forecaster": 80,
        }[model]
        rate = 0.08
        if self.drift:
            if model == "leak_detector":
                conf -= 0.35 * min(1, max(0, (seconds - 75) / 85))
                rate += 0.5 * min(1, max(0, (seconds - 230) / 70))
            if model == "demand_forecaster":
                latency *= 1 + 2.5 * min(1, max(0, (seconds - 160) / 70))
        label = (
            ("leak" if rng.random() < rate else "normal")
            if model == "leak_detector"
            else (
                rng.choice(["drop", "stable"])
                if model == "pressure_drop_predictor"
                else rng.randint(1, 5000)
            )
        )
        record = {
            "reading_id": index + 1,
            "station_id": f"ST-{rng.randint(1, 10):02d}",
            "model_name": model,
            "predicted_label": label,
            "confidence_score": round(min(1, max(0, rng.gauss(conf, 0.07))), 4),
            "response_time_ms": round(max(1, rng.gauss(latency, 10)), 3),
            "timestamp": (
                datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)
            ).isoformat(),
        }
        if rng.random() < self.corruption:
            choice = index % 7
            if choice == 0:
                record["confidence_score"] = True
            elif choice == 1:
                record["model_name"] = []
            elif choice == 2:
                record["predicted_label"] = {}
            elif choice == 3:
                record["response_time_ms"] = -1
            elif choice == 4:
                record.pop("station_id")
            elif choice == 5:
                record["timestamp"] = "2026-01-01"
            else:
                record.update({"reading_id": -1, "confidence_score": 1.5})
        return record

    def line(self, index, seconds):
        return json.dumps(self.record(index, seconds), allow_nan=False).encode() + b"\n"
