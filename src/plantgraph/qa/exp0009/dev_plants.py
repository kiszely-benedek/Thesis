"""Build a v2.2 plant of about `target_sheets` sheets, with the tagging of every document forced.

EXP-0009's sealed plants draw (or stratify) which documents print no tag on their manual valves
(`handbook.document_untagged`). The free gates and the availability table need both extremes on the
same plant shape, so this helper forces every document one way, or leaves the draw alone.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.ingest.headline_v2 import smallest_n_units_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus

#: more flags than any plant has documents (a 1,000-sheet plant has about 10); extras go unused
_FLAGS_PER_PLANT = 64


def forced_config(target_sheets: int, seed: int, *, untagged: bool | None) -> GeneratorConfigV22:
    """The v2.2 config of a plant sized for `target_sheets`; `untagged` forces every document.

    Args:
        target_sheets: the plant's size in sheets (the size search lands within its band).
        seed: the plant's seed.
        untagged: True = every document prints no manual-valve tags, False = every one does,
            None = the documents' own draw.
    """
    preset = HeadlinePresetV22()
    n_units = smallest_n_units_v2(target_sheets, preset, seed).n_units
    config = preset.generator_config(n_units, seed)
    if untagged is None:
        return config
    knobs = config.handbook.model_copy(update={"document_untagged": (untagged,) * _FLAGS_PER_PLANT})
    return config.model_copy(update={"handbook": knobs})


def dev_corpus(target_sheets: int, seed: int, *, untagged: bool | None) -> SyntheticCorpus:
    """Generate, split and resolve the plant of `forced_config` (no Neo4j, no model)."""
    config = forced_config(target_sheets, seed, untagged=untagged)
    return build_synthetic_corpus(config, HeadlinePresetV22().split_config(seed))
