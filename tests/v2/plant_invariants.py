"""`plant_view(seed, n_units)`: a generated v2 plant as a `RuleView`, built once per process.

Not a test module (no `test_` prefix). The checks themselves live in
`plantgraph.benchmark.v2.rules.checks_v21`; this file only caches the plants the tests share.
"""

from __future__ import annotations

from functools import cache

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view


@cache
def plant_view(seed: int, n_units: int) -> RuleView:
    """Generate the plant of `GeneratorConfigV2(seed, n_units)` once and wrap it."""
    return build_rule_view(generate_plant_v2(GeneratorConfigV2(seed=seed, n_units=n_units)))


@cache
def plant_view_v22(seed: int, n_units: int) -> RuleView:
    """The v2.2 plant (handbook rules on, every knob at its default) of the same seed and size."""
    return build_rule_view(generate_plant_v2(GeneratorConfigV22(seed=seed, n_units=n_units)))
