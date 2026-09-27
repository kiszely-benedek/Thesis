"""`python -m plantgraph.ingest` — the CLI that takes a corpus from source to Neo4j.

Two ways in: `synthetic` (generator + splitter, which also has an answer key
to check the resolver against) and `proteus` (one real DEXPI drawing, which
does not). Both funnel through the same `localize -> resolve -> build_load_plan`
steps, so that EXP-0001 (single-sheet) and EXP-0002 (plant-scale) enter the
pipeline through the same door (design `kg-construction.md` §1, §8).

`pipeline.py` holds the orchestration (no argv, no printing), `__main__.py`
holds argument parsing, environment lookup, and printing, and `models.py`
holds `IngestResult`, the one JSON object the CLI prints.
"""

from __future__ import annotations
