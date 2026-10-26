"""A small v2 corpus, built once per process (not a test module: no `test_` prefix).

`corpus(n_sheets)` runs the real path, as `ingest synthetic --headline-v2` does: plan, generate,
split, localize, resolve. About 30 sheets is large enough to hold identity groups and signal cuts.
"""

from __future__ import annotations

from functools import cache

from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus

SEED = 1


@cache
def corpus(n_sheets: int = 30) -> SyntheticCorpus:
    """The headline-preset v2 corpus of at least `n_sheets` sheets, seed 1."""
    preset = HeadlinePresetV2()
    n_units = smallest_n_units_v2(n_sheets, preset, SEED).n_units
    return build_synthetic_corpus(preset.generator_config(n_units, SEED), preset.split_config(SEED))
