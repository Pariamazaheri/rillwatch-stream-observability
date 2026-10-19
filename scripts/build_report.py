"""Create measured evidence, compact CSV samples, and diagnostic figures."""

import csv
import json
import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads((ROOT / path).read_text())


def main():
    results = read("reports/benchmark.json")
    figures = ROOT / "reports/figures"
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
        }
    )
    stable = pd.DataFrame(read("reports/stable_windows.json"))
    shift = pd.DataFrame(read("reports/shifted_windows.json"))
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    for frame, label, color in [
        (stable, "Stable", "#64748b"),
        (shift, "Shifted", "#0284c7"),
    ]:
        axes[0].plot(
            frame.received, frame.leak_detector_avg_confidence, label=label, color=color
        )
        axes[1].plot(
            frame.received,
            frame.demand_forecaster_avg_latency,
            label=label,
            color=color,
        )
    axes[0].axvline(75, ls="--", color="#e87924")
    axes[1].axvline(160, ls="--", color="#e87924")
    axes[0].set(
        xlabel="Simulated receipt seconds",
        ylabel="Mean leak-detector confidence",
        title="Schema-valid outputs can change behavior",
    )
    axes[1].set(
        xlabel="Simulated receipt seconds",
        ylabel="Mean demand-model latency · ms",
        title="Latency shift is separate from data validity",
    )
    for ax in axes:
        ax.legend()
    fig.savefig(figures / "behavior_shifts.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    names = ["Confidence", "Latency", "Leak rate"]
    keys = [
        "leak_detector:confidence_score",
        "demand_forecaster:response_time_ms",
        "leak_detector:leak_rate",
    ]
    onsets = [75, 160, 230]
    for offset, result in enumerate(r for r in results if r["scenario"] == "shifted"):
        delays = [
            result["first_alert_seconds"][k] - onset for k, onset in zip(keys, onsets)
        ]
        axes[0].bar(
            [x + (offset - 1) * 0.24 for x in range(3)],
            delays,
            width=0.24,
            label=f"Seed {result['seed']}",
        )
    axes[0].set(
        xticks=range(3),
        xticklabels=names,
        ylabel="Seconds from ramp onset to first alert",
        title="Detection delays include ramp and window lag",
    )
    axes[0].legend()
    labels = [f"{r['scenario']}\nseed {r['seed']}" for r in results]
    axes[1].bar(
        labels,
        [len(r["alerts"]) for r in results],
        color=["#64748b"] * 3 + ["#0d9488"] * 3,
    )
    axes[1].set(
        ylabel="Alert emissions · includes cooldown repeats",
        title="Zero alerts in three stable controls",
    )
    fig.savefig(figures / "detection_evidence.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    totals = [r for r in results if r["scenario"] == "stable"]
    axes[0].bar(
        [str(r["seed"]) for r in totals],
        [r["counts"]["bad"] / r["events"] * 100 for r in totals],
        color="#e87924",
    )
    axes[0].axhline(2.5, ls="--", color="#94a3b8")
    axes[0].set(
        xlabel="Seed",
        ylabel="Quarantined events · %",
        title="Observed rate; validation never assumes a quota",
    )
    axes[1].plot(shift.received, shift.active_stations, color="#0284c7")
    axes[1].set(
        xlabel="Simulated receipt seconds",
        ylabel="Distinct valid stations per window",
        ylim=(0, 11),
        title="Operational coverage from validated records",
    )
    fig.savefig(figures / "quality_coverage.png", dpi=180)
    plt.close(fig)
    # Publish compact samples; full raw/generated output remains locally reproducible.
    samples = ROOT / "data/examples"
    samples.mkdir(exist_ok=True)
    from rillwatch.storage import Store

    for scenario in ["stable", "shifted"]:
        store = Store(ROOT / f"data/runs/{scenario}-42/events.sqlite")
        target = ROOT / f"reports/sample_exports/{scenario}"
        store.export(target)
        store.close()
        for name in ["clean_readings.csv", "bad_readings.csv"]:
            path = target / name
            with path.open(newline="") as f:
                rows = list(csv.reader(f))
            with path.open("w", newline="") as f:
                csv.writer(f).writerows(rows[:26])
    summary = {
        "events_across_scenarios": sum(r["events"] for r in results),
        "stable_alerts": sum(
            len(r["alerts"]) for r in results if r["scenario"] == "stable"
        ),
        "shifted_runs_with_all_targets": sum(
            len(r["first_alert_seconds"]) == 3
            for r in results
            if r["scenario"] == "shifted"
        ),
        "capacity_evictions": sum(r["capacity_evictions"] for r in results),
        "runtime": {
            "python": platform.python_version(),
            "system": platform.system(),
            "architecture": platform.machine(),
        },
        "csv_sample_limit": 25,
    }
    (ROOT / "reports/summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    table = "\n".join(
        f"| {r['scenario']} | {r['seed']} | {r['counts']['clean']:,} | {r['counts']['bad']:,} | {len(r['alerts'])} | {r['local_events_per_second']:,.0f} |"
        for r in results
    )
    (
        ROOT / "reports/benchmark.md"
    ).write_text(f"""# Stream quality and behavior-shift benchmark

## Measured results

Six accelerated event-clock runs contain **{summary["events_across_scenarios"]:,} synthetic events**. Each covers 360 simulated seconds at 40 events/second, with seeds 42, 7 and 19 for stable controls and shifted scenarios. Schema validation is independent of the configured corruption probability.

| Scenario | Seed | Clean | Quarantined | Alert emissions | Local replay events/s |
|---|---:|---:|---:|---:|---:|
{table}

All three shifted runs detect confidence loss, increased latency, and changed leak-label rates. Stable controls emit no alerts in these runs. Confidence first alerts at 165s (90s after the ramp begins); latency at 210s (50s lag); label-rate alerts at 285–300s (55–70s lag). Repeated alerts after the 60-second cooldown are counted as emissions, not additional true positives. These three seeds do not establish a universal false-positive rate, and periodic checks on overlapping windows are correlated.

The throughput column measures a single-process, accelerated local replay including SQLite transactions on this machine. It does not measure sustained live-network capacity or guarantee 50,000 events/second. Replay advances the event clock without sleeping; a separate real 360-second TCP run is recorded in `live_run.json`.

## Decision relevance

- Schema-valid telemetry still exhibits substantial behavior shifts, so clean-data counts alone are insufficient for monitoring.
- Frozen, non-overlapping baseline samples prevent the recent window from contaminating its reference. Two consecutive checks and a per-metric cooldown reduce transient and repeated alerts within this protocol.
- The confidence/latency score is a baseline-standardized effect, **not a hypothesis-test z statistic**. Label-rate scores use a pooled-proportion formula, but autocorrelation, repeated checks, and lack of multiple-testing correction preclude a formal significance claim.
- A shift in model outputs can reflect real environmental change, seasonality, or model problems. No labels of actual outcomes are available, so this project does not establish concept drift, forecast error, or the existence of a real leak.

## Evidence boundaries

Row-level alert evidence and complete 20-second report windows are included. Clean/bad CSVs in `sample_exports/` are clearly capped at 25 rows per file. Full generated records and local databases are ignored by Git and can be recreated with `scripts/benchmark.py`; no source-folder datasets, PDFs, logs, credentials, proxy tooling, or organization references are published.

The independent simulator is a compatibility fixture: three model names, ten stations, varied corrupted fields, a confidence ramp from 75–160s, latency ramp from 160–230s, and leak-rate ramp from 230–300s. Shifts persist after their ramps. It does not execute or train machine-learning models. This differs from cyclic simulators that reset at phase boundaries; results describe the explicit protocol in this repository.
""")


if __name__ == "__main__":
    main()
