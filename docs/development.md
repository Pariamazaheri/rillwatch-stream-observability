# Development and provenance

This independent portfolio rebuild used AI assistance to inspect correctness, implement modular components, write tests, produce figures, and prepare documentation. Reported experiments were executed locally. The simulator was written independently for this repository; no original third-party simulator, source report, proxy tooling, virtual environment, private path, organization branding, or credentials are included.

Run the lightweight core checks with `pip install '.[dev]'`, `pytest -q`, and `python scripts/validate_results.py`. Install `.[reports]` for figure/notebook regeneration. CI runs core tests, evidence validation, lint, formatting, and wheel packaging on Python 3.11 and 3.12. Local-loopback tests do not use external services.

The controlled benchmarks use a fixed effect-size policy, three seeds, short simulated periods, and synthetic independent noise. These are engineering validation scenarios rather than a representative field study. Git excludes large generated outputs; published CSV examples are capped at 25 rows, while alert/report evidence remains complete for the reference replay.
