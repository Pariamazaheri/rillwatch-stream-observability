"""Single state owner with bounded aggregates and traffic-independent timers."""

import uuid
from collections import defaultdict

from .drift import Monitor


class Engine:
    def __init__(
        self, store, start=0, report_interval=20, check_interval=15, run_id=None
    ):
        if report_interval <= 0 or check_interval <= 0:
            raise ValueError("Intervals must be positive")
        self.store = store
        self.monitor = Monitor()
        self.last = start
        self.next_report = start + report_interval
        self.next_check = start + check_interval
        self.report_interval = report_interval
        self.check_interval = check_interval
        self.total = 0
        self.bad = 0
        self.duplicates = 0
        self.run_id = run_id or uuid.uuid4().hex
        self.reset_window()

    def reset_window(self):
        self.window_clean = 0
        self.window_bad = 0
        self.stations = set()
        self.by_model = defaultdict(
            lambda: {"n": 0, "confidence": 0.0, "latency": 0.0, "low": 0}
        )

    def ingest(self, source, epoch, sequence, now, frame):
        self.tick(now)
        inserted, record, errors = self.store.ingest(
            source, epoch, sequence, now, frame.raw, frame.error
        )
        if not inserted:
            self.duplicates += 1
            return
        self.total += 1
        if errors:
            self.bad += 1
            self.window_bad += 1
        else:
            self.window_clean += 1
            self.stations.add(record["station_id"])
            stats = self.by_model[record["model_name"]]
            stats["n"] += 1
            stats["confidence"] += record["confidence_score"]
            stats["latency"] += record["response_time_ms"]
            stats["low"] += record["confidence_score"] < 0.5
            self.monitor.add(record, now)

    def tick(self, now):
        if now < self.last:
            raise ValueError("Clock must be monotonic")
        self.last = now
        while min(self.next_check, self.next_report) <= now:
            if self.next_check <= self.next_report:
                for alert in self.monitor.check(self.next_check):
                    self.store.append("alerts", {"run_id": self.run_id, **alert})
                self.next_check += self.check_interval
            else:
                self.report(self.next_report, self.report_interval, False)
                self.next_report += self.report_interval

    def report(self, now, seconds, partial):
        result = {
            "run_id": self.run_id,
            "received": now,
            "window_seconds": seconds,
            "partial": partial,
            "window_total": self.window_clean + self.window_bad,
            "window_clean": self.window_clean,
            "window_bad": self.window_bad,
            "total_records": self.total,
            "total_bad": self.bad,
            "active_stations": len(self.stations),
            "capacity_evictions": self.monitor.cap_evictions,
        }
        from .validation import MODELS

        for model in MODELS:
            stats = self.by_model[model]
            n = stats["n"]
            result[model + "_avg_confidence"] = stats["confidence"] / n if n else None
            result[model + "_avg_latency"] = stats["latency"] / n if n else None
            result[model + "_low_confidence"] = stats["low"]
        self.store.append("reports", result)
        self.reset_window()

    def finish(self, now):
        self.tick(now)
        previous = self.next_report - self.report_interval
        if now > previous or self.window_clean or self.window_bad:
            self.report(now, now - previous, True)
