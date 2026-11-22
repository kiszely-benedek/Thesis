"""The headline corpus preset for the v2.2 generator (ADR-0066): `HeadlinePresetV2` plus handbook.

Everything but the generator config and the corpus-id tag (`g22`, e.g. `D100g22`, `H1000g22p1`) is
the v2 preset's, so the splitter, the size search and the seed plan work unchanged.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.ingest.headline_v2 import HeadlinePresetV2


class HeadlinePresetV22(HeadlinePresetV2):
    """How every v2.2 headline corpus is generated and split."""

    generation: str = "g22"

    def generator_config(self, n_units: int, seed: int) -> GeneratorConfigV22:
        """The generator settings for `n_units` units, with the handbook knobs at their defaults."""
        return GeneratorConfigV22(n_units=n_units, seed=seed)
