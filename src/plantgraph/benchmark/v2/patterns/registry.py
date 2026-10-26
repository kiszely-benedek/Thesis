"""Which process patterns exist: the table the flowsheet grammar draws from.

Adding a pattern is one line here; the grammar picks it up because it only draws among the
patterns listed.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.filter_package import build_filter_package
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm

PatternBuilder = Callable[[PatternContext], PatternInstance]

#: pattern id -> builder; U1, U2, U3, U5 and U8 follow in later tasks, U10 is not generated
PATTERN_BUILDERS: dict[str, PatternBuilder] = {
    "U4": build_tank_farm,
    "U6": build_flash_drum,
    "U7": build_filter_package,
}


def available_patterns() -> frozenset[str]:
    """The ids of the patterns that can be built today."""
    return frozenset(PATTERN_BUILDERS)


def build_pattern(pattern_id: str, ctx: PatternContext) -> PatternInstance:
    """Build one instance of `pattern_id`; raises with the known ids for an unknown one."""
    if pattern_id not in PATTERN_BUILDERS:
        raise ValueError(
            f"no pattern {pattern_id!r}; the available patterns are {sorted(PATTERN_BUILDERS)}"
        )
    return PATTERN_BUILDERS[pattern_id](ctx)
