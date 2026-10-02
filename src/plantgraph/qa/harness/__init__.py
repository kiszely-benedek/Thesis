"""The experiment harness: runs strategies over a question set and records scored rows.

`runner.py` is the loop (resume, replay, provider-error retry); `freeze.py`
fixes a run's configuration before its first call; `clients.py` is the
paid-call guard; `run_dir.py` is the on-disk layout; `gold.py` is the part
that reads the answer key (path scoring, routing recall); `cli.py` is the
`python -m plantgraph.qa.harness` entry point.
"""
