# Architecture decisions and scale-out path

## Why a local journal instead of append-only CSV

Persisting raw frames and classifications in one transaction gives a clear local commit boundary and auditable quarantine. CSV remains an interoperable delivery format. Appending multiple CSV files cannot by itself provide atomic coordination of clean/bad routes, counters, and checkpoints. `flush()` and `fsync()` are different operations; neither adds replay support to a raw TCP source.

## Why bounded multi-source ingestion

Independent source readers avoid mixing frame fragments from different connections. A bounded queue transfers ownership to one consumer, which serializes state updates and uses idle ticks for periodic work. This is sufficient for the recorded workload and simpler to reason about than parallel mutable counters. SQLite writes still block the loop; high-rate deployments need a different write path and explicit batching semantics.

## Monitoring semantics

Confidence loss, latency increase, and prediction-mix changes are operational signals. Data corruption and behavior drift are measured separately. Effect-size thresholds, minimum sample counts, persistence, and cooldown reduce some noisy alerts. They cannot rule out seasonality or real changes in network conditions. Representative historical seasonal baselines and delayed outcome labels would be needed to distinguish those causes.

## Proposed architecture beyond the measured workload

For tens of thousands of events per second, benchmark the actual payload and hardware first. A durable broker with producer acknowledgements, stable message identity, partitioned consumers, replayable offsets, and transactional/idempotent sinks provides a stronger delivery contract. Batched columnar storage can serve analytics, and a separate operational store can serve dashboards. Window state should be checkpointed consistently with consumed offsets. These are design proposals; no broker, distributed processor, or 50,000-events/second deployment is included here.

The supplied subject matter was reviewed as technical reference. The published code, simulator, documentation, and results were independently rebuilt for a portfolio. Original files remain untouched, and no association with an external organization or customer is claimed.
