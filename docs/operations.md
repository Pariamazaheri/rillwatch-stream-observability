# Operating contract

## Input and identity

UTF-8 JSON objects are newline-delimited over TCP. The seven required fields are documented in `data/contract.json`. Extra fields are retained and allowed. Empty lines are invalid JSON events, not silently discarded. ISO timestamps with a date and time are accepted, including naive local strings for compatibility; UTC offsets are recommended. Numeric epochs must be positive and representable. Receipt time is monotonic relative to the run and drives all windows.

Each connection has an independent framer and a random epoch. The local identity is `(configured source, connection epoch, frame sequence)`. `reading_id` is validated as a positive integer but is not assumed globally unique across producers or restarts. Replaying exactly the same local identity and payload is idempotent; a different payload under that identity raises an error. This is local journal idempotence, not cross-connection business-event deduplication.

Frames larger than 65,536 bytes produce one quarantined prefix, and their tail is discarded through the next newline. Incomplete connection tails are quarantined with an explicit reason. Full bytes are retained for normal-sized frames, encoded as base64 in quarantine exports. The oversized-frame bound intentionally prevents retention of an arbitrary-length payload.

## Persistence and failure

SQLite WAL and FULL synchronization commit raw bytes and classification together. CSVs are derived exports; a CSV export can be regenerated from the journal. The journal does not acknowledge or replay data at the producer. Bytes in transit, read buffers, or the queue before commit remain vulnerable to failure. End-to-end losslessness requires a durable producer/broker, replay offsets, acknowledgements after sink commit, and stable business-event identity.

Storage errors fail processing visibly rather than becoming bad-input records. Existing committed records survive ordinary process restart subject to SQLite/filesystem guarantees; the last uncommitted transaction may not. Derived counters and monitoring state rewarm on restart; they are not exactly-once checkpointed with input. Use one database per recorded experiment and regenerate analyses from a journal if a run is interrupted.

## Reporting and monitoring

The 20-second report interval is receipt-time based, with empty windows emitted during silence. A final partial window records its actual duration. Active stations are counted only from valid records. Means are null for absent models; low-confidence counts use confidence strictly below .5. Totals describe the current engine run, while an existing database may contain earlier epochs.

The 60-second baseline freezes only samples before its boundary. If fewer than 50 valid samples arrive during that period, that model remains insufficient for monitoring; it does not expand the baseline indefinitely. Recent windows include only post-baseline records and discard expired samples on timer checks even when traffic is quiet. Two consecutive eligible checks and a 60-second metric cooldown gate alerts. A low-sample check resets persistence. Baseline and recent sample caps are 10,000; cap evictions are counted, and results under eviction must be treated as subsampled diagnostics.

The latency/confidence score is not a calibrated probability or formal z-test. No actual-outcome labels are present. A detector alert requests investigation; it does not establish a real leak or deteriorating predictive accuracy.

## Runtime limits

One async event loop and one writer provide simple state ownership. Database commits are synchronous and can block the loop, creating natural queue/socket backpressure at higher rates. This is deliberate for the measured low-rate workload. Queues and monitoring memory are bounded; journal size is not. Operators must manage disk retention and capacity. The simulator binds to loopback by default and should not be exposed as an authenticated public service.
