"""Every v2.1 invariant check (S1-S24) under one import path (design 3.3).

The checks live in four modules so none grows past the size limit; this facade is what tests and
the registry import. Their behaviour is exactly what it was in `tests/v2/`: an `AssertionError`
naming the offender, or the number of things checked. S13-S16 and S20 on corpora, S17 and S18
are tests, not checks over a plant, and stay where they are.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.checks_v21_instruments import (
    check_s4,
    check_s7,
    check_s8,
    check_s9,
    check_s22,
)
from plantgraph.benchmark.v2.rules.checks_v21_machines import check_s19, check_s20
from plantgraph.benchmark.v2.rules.checks_v21_naming import check_s21, check_s23, check_s24
from plantgraph.benchmark.v2.rules.checks_v21_plant import (
    check_s1,
    check_s2,
    check_s3,
    check_s5,
    check_s6,
    check_s10,
    check_s11,
    check_s12,
)

__all__ = [
    "check_s1", "check_s2", "check_s3", "check_s4", "check_s5", "check_s6", "check_s7",
    "check_s8", "check_s9", "check_s10", "check_s11", "check_s12", "check_s19", "check_s20",
    "check_s21", "check_s22", "check_s23", "check_s24",
]  # fmt: skip
