"""Independent release evidence validation; requires only the standard library."""

import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((root / name).read_text())


results = read("reports/benchmark.json")
assert len(results) == 6
assert sum(r["events"] for r in results) == 86400
for r in results:
    assert sum(r["counts"].values()) == r["events"] == 14400
    assert r["capacity_evictions"] == 0
    if r["scenario"] == "stable":
        assert not r["alerts"]
    else:
        first = {}
        for alert in r["alerts"]:
            first.setdefault(
                alert["model_name"] + ":" + alert["metric"], alert["received"]
            )
            assert alert["consecutive_checks"] >= 2
            assert alert["baseline_n"] >= 50 and alert["recent_n"] >= 50
        assert first == r["first_alert_seconds"] and len(first) == 3
for scenario in ["stable", "shifted"]:
    windows = read(f"reports/{scenario}_windows.json")
    assert len(windows) == 18
    assert sum(w["window_total"] for w in windows) == 14400
    assert all(
        w["window_clean"] + w["window_bad"] == w["window_total"] for w in windows
    )
    r = next(r for r in results if r["scenario"] == scenario and r["seed"] == 42)
    assert sum(w["window_bad"] for w in windows) == r["counts"]["bad"]
    for name in ["clean_readings.csv", "bad_readings.csv"]:
        with (root / f"reports/sample_exports/{scenario}/{name}").open() as f:
            assert len(list(csv.DictReader(f))) == 25
live = read("reports/live_run.json")
assert live["duration_seconds"] >= 360
assert live["counts"]["clean"] > 10000 and live["counts"]["bad"] > 0
assert live["alert_count"] >= 3 and live["capacity_evictions"] == 0
live_windows = read("reports/live_windows.json")
assert len(live_windows) == live["report_count"]
assert sum(w["window_total"] for w in live_windows) == sum(live["counts"].values())
assert sum(w["window_bad"] for w in live_windows) == live["counts"]["bad"]
assert len(read("reports/live_alerts.json")) == live["alert_count"]
assert read("reports/summary.json")["events_across_scenarios"] == 86400
notebook = read("notebooks/operations_audit.ipynb")
for cell in notebook["cells"]:
    if cell["cell_type"] == "code":
        assert cell["execution_count"] is not None
        assert not any(o["output_type"] == "error" for o in cell["outputs"])
print(
    "Benchmark accounting, drift evidence, live run, CSV samples and notebook validated."
)
