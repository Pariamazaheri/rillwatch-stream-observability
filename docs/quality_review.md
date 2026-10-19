# Correctness and completeness review

The reviewed implementation correctly recognized newline framing and multiple validation failures, but several behavior and reliability claims needed correction. This repository is an independent rebuild with a new simulator and new experiment results.

| Issue found | Correction | Evidence |
|---|---|---|
| Unhashable model or label values could raise a validation exception | Type checks before model/label lookup | Adversarial field/type matrix |
| Positive infinity could pass a positivity check | Reject non-finite numbers and out-of-range epochs | Numeric and timestamp tests |
| JSON accepted non-standard constants and duplicate keys | Explicit strict parsing hooks | Invalid JSON tests |
| Station regex could accept a trailing newline; date-only strings passed as timestamps | Full-match identifiers; require a time component | Schema tests |
| Frames could grow without a newline | Bounded framing with oversize quarantine and resynchronization | Oversize and packet-boundary tests |
| Periodic work depended on receiving another record | Independent idle ticks in an async consumer | Idle-window and loopback tests |
| Shutdown could wait indefinitely for another input line | Async task cancellation and queue draining | Network lifecycle tests |
| Broad handler catches could recategorize storage failures as bad input | Storage errors propagate; counters update only after persistence | Fault-injection test |
| CSV flush was described as if it were durable fsync | Transactional SQLite journal is the local durability boundary | Restart, rollback, and idempotence tests |
| Baseline collection included a boundary sample and overlapped recent traffic | Explicit disjoint receipt-time baseline/recent eligibility | Baseline-boundary test |
| Continuous score was interpreted as statistical significance | Report it as a baseline-standardized effect heuristic | Methodology and benchmark |
| Monitoring and report state could grow with volume | Per-model sample caps, a bounded queue, and fixed-size report aggregates | Capacity and eviction tests |
| Multiple streams and recovery were only architectural suggestions | Multi-source CLI plus local durable journal and collision detection | Actual two-source and restart tests |

A zero-alert stable run is an observed result, not a proof against false positives. Persistence checks use overlapping windows and do not constitute independent statistical evidence. These constraints are explicit in the measured report.
