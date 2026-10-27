"""One plant of the T13 patterns: the input of the invariant, determinism and composition tests.

Not a test module (no `test_` prefix). `build_column_heat_plant` writes, into one unit of a
harness, eight distillation columns and six exchanger trains; the second half of each list uses a
context with every optional part switched on (`patterns_everything.all_on`), so cascades, motor
current and the alarms appear. Four columns cover one cycle of the vacuum deck, three trains one
cycle of the exchanger-count deck.
"""

from __future__ import annotations

from pattern_harness import PatternHarness
from patterns_everything import all_on

from plantgraph.benchmark.v2.patterns.column import build_distillation_column
from plantgraph.benchmark.v2.patterns.heat import build_exchanger_train
from plantgraph.benchmark.v2.patterns.ports import PatternInstance


def build_column_heat_plant(h: PatternHarness) -> list[PatternInstance]:
    """Write four columns and three trains with default knobs, then again with all-on knobs."""
    instances: list[PatternInstance] = []
    for ctx in (h.pctx, all_on(h.pctx)):
        builds = [build_distillation_column] * 4 + [build_exchanger_train] * 3
        for build in builds:
            instance = build(ctx)
            instance.plan.write(h.builder)
            instances.append(instance)
    return instances
