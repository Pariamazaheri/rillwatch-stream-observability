# Synthetic data only

The new compatibility simulator creates three prediction-service outputs across ST-01 through ST-10. It does not execute trained models and does not contain real sensor or customer data. Full generated journals and CSVs live in ignored `data/runs/` directories.

`contract.json` documents the validation contract, and `examples/` provides a valid object and a deliberately invalid multi-error object. Quarantine records represent input failures, not fabricated sensor anomalies. Benchmark seeds and corruption probability are documented in the source simulator and report. No source-folder data or original scripts are redistributed.
