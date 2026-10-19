"""Accelerated event-clock scenarios, distinct from the live TCP evidence."""

import json
import time
from pathlib import Path

from rillwatch.engine import Engine
from rillwatch.framing import Frame
from rillwatch.simulator import Simulator
from rillwatch.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def run(name, seed, drift):
    directory = ROOT / f"data/runs/{name}-{seed}"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "events.sqlite"
    if path.exists():
        raise FileExistsError("Use a fresh benchmark directory")
    store = Store(path)
    engine = Engine(store, run_id=f"{name}-{seed}")
    sim = Simulator(seed, drift)
    start = time.perf_counter()
    for index in range(14400):
        now = index / 40
        engine.ingest(
            "synthetic",
            f"{name}-{seed}",
            index,
            now,
            Frame(sim.line(index, now).strip()),
        )
    engine.finish(360)
    elapsed = time.perf_counter() - start
    alerts = [json.loads(r[0]) for r in store.db.execute("SELECT payload FROM alerts")]
    reports = [
        json.loads(r[0]) for r in store.db.execute("SELECT payload FROM reports")
    ]
    first = {}
    for a in alerts:
        first.setdefault(a["model_name"] + ":" + a["metric"], a["received"])
    result = {
        "scenario": name,
        "seed": seed,
        "simulated_seconds": 360,
        "events": 14400,
        "counts": store.counts(),
        "alerts": alerts,
        "first_alert_seconds": first,
        "wall_seconds": elapsed,
        "local_events_per_second": 14400 / elapsed,
        "capacity_evictions": engine.monitor.cap_evictions,
    }
    assert sum(result["counts"].values()) == 14400
    assert sum(r["window_total"] for r in reports) == 14400
    if seed == 42:
        store.export(ROOT / f"reports/sample_exports/{name}")
        (ROOT / f"reports/{name}_windows.json").write_text(
            json.dumps(reports, indent=2) + "\n"
        )
    store.close()
    return result


def main():
    results = []
    for drift in [False, True]:
        for seed in [42, 7, 19]:
            result = run("shifted" if drift else "stable", seed, drift)
            results.append(result)
            print(
                result["scenario"],
                seed,
                result["counts"],
                len(result["alerts"]),
                flush=True,
            )
    (ROOT / "reports/benchmark.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
