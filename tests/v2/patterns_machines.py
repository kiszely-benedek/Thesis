"""One plant of the T14 patterns: the input of the invariant, determinism and composition tests.

Not a test module (no `test_` prefix). `build_machine_plant` writes, into one unit of a harness,
four compressor stages, three reactor systems and four blending units: they cover one cycle of the
compressor, reactor and mixer decks. With `optional_parts` the context has every optional part
switched on (`patterns_everything.all_on`, plus variable-speed drives and the multivariable
controller), so cascades, motor current and the alarms appear.
"""

from __future__ import annotations

import dataclasses

from pattern_harness import PatternHarness
from patterns_everything import ALL_ON_DENSITY, all_on

from plantgraph.benchmark.v2.patterns.blending import build_blending
from plantgraph.benchmark.v2.patterns.compression import build_compressor_stage
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.reaction import build_reactor_system

ALL_ON_MACHINES = ALL_ON_DENSITY.model_copy(update={"p_vfd": 1.0, "p_multivariable": 1.0})
BUILDS = [build_compressor_stage] * 4 + [build_reactor_system] * 3 + [build_blending] * 4


def all_on_machines(ctx: PatternContext) -> PatternContext:
    """`all_on` plus variable-speed drives and the multivariable controller."""
    return dataclasses.replace(all_on(ctx), density=ALL_ON_MACHINES)


def build_machine_plant(h: PatternHarness, optional_parts: bool = False) -> list[PatternInstance]:
    """Write eleven patterns into the harness: default knobs, or with every optional part on.

    One harness unit holds one batch only: a unit's instrument numbers stop at 999 (three digits),
    and the two batches together would use about 1,000.
    """
    ctx = all_on_machines(h.pctx) if optional_parts else h.pctx
    instances: list[PatternInstance] = []
    for build in BUILDS:
        instance = build(ctx)
        instance.plan.write(h.builder)
        instances.append(instance)
    return instances
