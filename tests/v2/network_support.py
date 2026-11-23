"""Plants the network tests share (not a test module: no `test_` prefix)."""

from __future__ import annotations

from functools import cache

from t9_support import units_for_30_sheets

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view


@cache
def view_one_train_per_area(seed: int) -> RuleView:
    """The 30-sheet plant with every train its own area, so trains meet over interarea sheets."""
    knobs = HandbookKnobs(trains_per_area=1)
    config = GeneratorConfigV22(seed=seed, n_units=units_for_30_sheets(seed), handbook=knobs)
    return build_rule_view(generate_plant_v2(config))
