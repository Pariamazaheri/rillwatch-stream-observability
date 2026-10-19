"""Build a lightweight, executable operational evidence walkthrough."""

import subprocess
import sys
from pathlib import Path

import nbformat as nbf

root = Path(__file__).resolve().parents[1]
md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
nb = nbf.v4.new_notebook(
    cells=[
        md(
            "# RillWatch: Stream Quality & Prediction Observability\n\nMeasured synthetic scenarios, real TCP verification, and explicit operating boundaries. The notebook reads released evidence; it does not launch a long-running server or train a model."
        ),
        code("""import json
from pathlib import Path

import pandas as pd
from IPython.display import Image, display

from rillwatch.framing import Framer
from rillwatch.validation import parse

ROOT = Path.cwd()
if not (ROOT / "reports").exists():
    ROOT = ROOT.parent

def read(path):
    return json.loads((ROOT / path).read_text())

summary = read("reports/summary.json")
summary"""),
        md(
            "## Strict framing and validation\n\nTCP packets do not define record boundaries. UTF-8 bytes stay buffered until a newline appears; oversized frames are quarantined and resynchronized. Multiple validation errors are retained."
        ),
        code("""framer = Framer()
assert framer.feed(b'{"x":') == []
frames = framer.feed(b'1}\\n')
assert frames[0].raw == b'{"x":1}'
record, problems = parse((ROOT / "data/examples/invalid.json").read_bytes())
assert len(problems) >= 3
problems"""),
        md(
            "## Measured event accounting\n\nEach scenario advances a deterministic receipt clock through 360 simulated seconds at 40 events/second. These replay runs are accelerated, not wall-clock TCP throughput tests."
        ),
        code("""results = read("reports/benchmark.json")
table = pd.DataFrame([{"scenario": r["scenario"], "seed": r["seed"], "events": r["events"], "clean": r["counts"]["clean"], "bad": r["counts"]["bad"], "alert_emissions": len(r["alerts"]), "local_replay_events_per_second": r["local_events_per_second"]} for r in results])
assert table["events"].sum() == 86400
assert ((table["clean"] + table["bad"]) == table["events"]).all()
display(table)
display(Image(filename=str(ROOT / "reports/figures/quality_coverage.png")))"""),
        md(
            "## Valid telemetry can still shift\n\nSchema validation and model-behavior monitoring answer different questions. Compare stable and shifted runs on confidence and latency; no actual-outcome labels are available to establish a change in prediction accuracy."
        ),
        code("""display(Image(filename=str(ROOT / "reports/figures/behavior_shifts.png")))
windows = pd.DataFrame(read("reports/shifted_windows.json"))
assert windows["window_total"].sum() == 14400
display(windows[["received", "window_total", "window_bad", "active_stations"]])"""),
        md(
            "## Detection delay and repeated alerts\n\nEffect-size gates, minimum sample counts, two consecutive checks, and cooldown are operational heuristics. Overlapping windows are correlated. Alert counts include cooldown repeats, so they must not be interpreted as independent true positives."
        ),
        code("""display(Image(filename=str(ROOT / "reports/figures/detection_evidence.png")))
alerts = pd.DataFrame(next(r for r in results if r["scenario"] == "shifted" and r["seed"] == 42)["alerts"])
display(alerts)
assert all(not r["alerts"] for r in results if r["scenario"] == "stable")"""),
        md(
            "## Independent live TCP evidence\n\nThe separate loopback run takes at least 360 real seconds. Actual throughput can be below the simulator's nominal 40 events/second because scheduling and synchronous persistence affect pacing."
        ),
        code("""live = read("reports/live_run.json")
assert live["duration_seconds"] >= 360
live"""),
        md(
            "## Delivery and scaling decisions\n\nSQLite commits each frame and its classification together. Same local event identity and bytes replay idempotently, while conflicting identities fail. This is not an end-to-end losslessness guarantee: raw TCP has no replay/acknowledgement contract, and in-memory monitoring state rewarms after restart. The local replay measurement is not a 50,000-events/second deployment claim. Broker-backed delivery, consistent state checkpoints, retention, and representative seasonal data are further engineering work."
        ),
    ]
)
nb.metadata = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}
path = root / "notebooks/operations_audit.ipynb"
nbf.write(nb, path)
subprocess.run([sys.executable, "-m", "ruff", "format", str(path)], check=True)
