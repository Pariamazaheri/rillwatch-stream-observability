# Stream quality and behavior-shift benchmark

## Measured results

Six accelerated event-clock runs contain **86,400 synthetic events**. Each covers 360 simulated seconds at 40 events/second, with seeds 42, 7 and 19 for stable controls and shifted scenarios. Schema validation is independent of the configured corruption probability.

| Scenario | Seed | Clean | Quarantined | Alert emissions | Local replay events/s |
|---|---:|---:|---:|---:|---:|
| stable | 42 | 14,071 | 329 | 0 | 22,288 |
| stable | 7 | 14,031 | 369 | 0 | 21,863 |
| stable | 19 | 14,024 | 376 | 0 | 22,351 |
| shifted | 42 | 14,071 | 329 | 9 | 21,939 |
| shifted | 7 | 14,031 | 369 | 9 | 22,077 |
| shifted | 19 | 14,024 | 376 | 9 | 21,827 |

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
