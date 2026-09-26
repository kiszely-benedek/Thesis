"""The thin resolver package: sheets (drawing pages) -> one merged plant graph, no answer key.

The input is always a `SheetGraph` — never a `SplitManifest`, never an
`OccurrenceMap` (design `kg-construction.md` §4.2, decision D1). `localize.py` and
`contract.py` seal off leaks from the splitter and the importer (§4.1) before
anything reaches this package; the resolver's own steps (pairing, identity, merge)
see only what would also be readable on a real drawing. This package therefore
never imports `plantgraph.benchmark.splitter`, `rejoin`, or `strategies`, nor
`plantgraph.eval` (§5.7) — a dedicated test enforces this.
"""

from __future__ import annotations
