"""Bounded baseline-versus-recent behavior monitoring, with explicit heuristics."""

from collections import defaultdict, deque
from dataclasses import dataclass
from math import sqrt
from statistics import mean, pstdev


@dataclass(frozen=True)
class Policy:
    baseline_seconds: float = 60
    recent_seconds: float = 45
    minimum_samples: int = 50
    capacity: int = 10000
    confidence_drop: float = 0.15
    latency_rise: float = 0.25
    spread_threshold: float = 3
    label_change: float = 0.1
    persistence: int = 2
    cooldown_seconds: float = 60

    def __post_init__(self):
        if (
            min(
                self.baseline_seconds,
                self.recent_seconds,
                self.minimum_samples,
                self.capacity,
                self.persistence,
            )
            <= 0
            or self.capacity < self.minimum_samples
            or self.cooldown_seconds < 0
        ):
            raise ValueError("Invalid monitoring policy")


class Monitor:
    def __init__(self, policy=Policy()):
        self.policy = policy
        self.states = {}
        self.cap_evictions = 0

    def add(self, record, now):
        model = record["model_name"]
        p = self.policy
        state = self.states.setdefault(
            model,
            {
                "first": now,
                "baseline_samples": [],
                "baseline": None,
                "recent": deque(),
                "streak": defaultdict(int),
                "last": {},
                "last_time": now,
            },
        )
        if now < state["last_time"]:
            raise ValueError("Receipt clock must be monotonic")
        state["last_time"] = now
        sample = (
            now,
            record["confidence_score"],
            record["response_time_ms"],
            record["predicted_label"],
        )
        if now < state["first"] + p.baseline_seconds:
            if len(state["baseline_samples"]) < p.capacity:
                state["baseline_samples"].append(sample)
            else:
                self.cap_evictions += 1
            return
        if state["baseline"] is None:
            base = state["baseline_samples"]
            state["baseline"] = {
                "n": len(base),
                "confidence": mean(x[1] for x in base) if base else 0,
                "confidence_std": pstdev(x[1] for x in base) if base else 0,
                "latency": mean(x[2] for x in base) if base else 0,
                "latency_std": pstdev(x[2] for x in base) if base else 0,
                "label_rate": mean(x[3] == "leak" for x in base) if base else 0,
            }
            state["baseline_samples"] = []
        recent = state["recent"]
        while recent and recent[0][0] <= now - p.recent_seconds:
            recent.popleft()
        if len(recent) >= p.capacity:
            recent.popleft()
            self.cap_evictions += 1
        recent.append(sample)

    def check(self, now):
        alerts = []
        p = self.policy
        for model, s in self.states.items():
            b = s["baseline"]
            recent = s["recent"]
            while recent and recent[0][0] <= now - p.recent_seconds:
                recent.popleft()
            if (
                b is None
                or b["n"] < p.minimum_samples
                or len(recent) < p.minimum_samples
            ):
                s["streak"].clear()
                continue
            candidates = []
            for metric, index, direction, threshold, key in [
                ("confidence_score", 1, -1, p.confidence_drop, "confidence"),
                ("response_time_ms", 2, 1, p.latency_rise, "latency"),
            ]:
                value = mean(x[index] for x in recent)
                base = b[key]
                effect = (value - base) / base if base else 0
                spread = (value - base) / max(b[key + "_std"], 1e-6)
                trigger = (
                    direction * effect >= threshold
                    and direction * spread >= p.spread_threshold
                )
                candidates.append(
                    (
                        metric,
                        trigger,
                        base,
                        value,
                        spread,
                        "baseline_standardized_effect",
                    )
                )
            if model == "leak_detector":
                current = mean(x[3] == "leak" for x in recent)
                base = b["label_rate"]
                pooled = (base * b["n"] + current * len(recent)) / (
                    b["n"] + len(recent)
                )
                se = sqrt(pooled * (1 - pooled) * (1 / b["n"] + 1 / len(recent)))
                score = (current - base) / se if se else 0
                candidates.append(
                    (
                        "leak_rate",
                        abs(current - base) >= p.label_change
                        and abs(score) >= p.spread_threshold,
                        base,
                        current,
                        score,
                        "pooled_proportion_score",
                    )
                )
            for metric, trigger, base, value, score, kind in candidates:
                s["streak"][metric] = s["streak"][metric] + 1 if trigger else 0
                if (
                    s["streak"][metric] >= p.persistence
                    and now - s["last"].get(metric, float("-inf")) >= p.cooldown_seconds
                ):
                    alerts.append(
                        {
                            "received": now,
                            "model_name": model,
                            "metric": metric,
                            "baseline_mean": base,
                            "recent_mean": value,
                            "score": score,
                            "score_kind": kind,
                            "baseline_n": b["n"],
                            "recent_n": len(recent),
                            "consecutive_checks": s["streak"][metric],
                        }
                    )
                    s["last"][metric] = now
        return alerts
