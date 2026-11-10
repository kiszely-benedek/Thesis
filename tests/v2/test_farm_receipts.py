"""Review R2: every receipt line of a product farm fills tanks of its own; products never mix.

Before, the second and later receipt lines joined the first at a merge tee, so a column's bottoms
and distillate could end in the same header and the same tank. Now a receipt line, with its
manifold valve, serves a group of tanks that no other line reaches.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

import pytest
from pattern_harness import PatternHarness

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm
from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.planner import plan_plant


def _farm(waiting: int, tank_card: str | None = None) -> PatternInstance:
    cards = {"U4.tank_count": (tank_card,)} if tank_card else None
    h = PatternHarness(0, deck_cards=cards)
    return build_tank_farm(replace(h.pctx, waiting_streams=waiting))


def receipts_reaching_each_tank(instance: PatternInstance) -> dict[str, int]:
    """How many receipt lines feed each tank (the walk stops at a tank: pumps recycle into one)."""
    lines = instance.plan.lines
    next_nodes: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        chain = [n for n in (line.src_id, *(i.node_id for i in line.items), line.dst_id) if n]
        for here, there in zip(chain, chain[1:], strict=False):
            next_nodes[here].add(there)
    tanks = {e.node_id for e in instance.plan.equipment if e.node_class == "Tank"}
    fed = dict.fromkeys(tanks, 0)
    for port in instance.ports:
        if port.name.startswith("receipt"):
            for tank in _tanks_reached(_line_of(lines, port.line_number), next_nodes, tanks):
                fed[tank] += 1
    return fed


def _line_of(lines: tuple[LineSpec, ...], number: str) -> LineSpec:
    return next(line for line in lines if line.line_number == number)


def _tanks_reached(start: LineSpec, next_nodes: dict[str, set[str]], tanks: set[str]) -> set[str]:
    seen, todo = set(), [start.items[0].node_id]
    while todo:
        node = todo.pop()
        if node in seen or node in tanks:  # a tank ends the receipt side
            seen.add(node)
            continue
        seen.add(node)
        todo.extend(next_nodes[node])
    return seen & tanks


@pytest.mark.parametrize("waiting", [0, 1, 2, 3, 4, 5])
def test_every_tank_has_exactly_one_receipt_line_upstream(waiting: int) -> None:
    farm = _farm(waiting)
    assert set(receipts_reaching_each_tank(farm).values()) == {1}


def test_more_streams_than_the_tank_card_raises_the_tank_count_to_one_each() -> None:
    farm = _farm(waiting=4, tank_card="2")
    assert len([e for e in farm.plan.equipment if e.node_class == "Tank"]) == 4
    assert "tanks=4|" in farm.variant and "receipts=4" in farm.variant


def test_the_tank_count_stays_the_cards_when_the_receipts_fit() -> None:
    farm = _farm(waiting=0, tank_card="4")
    assert len([e for e in farm.plan.equipment if e.node_class == "Tank"]) == 4


def test_seed_1_300_units_has_no_farm_where_two_receipts_fill_a_tank() -> None:
    """Before R2 (measured on the HEAD plant): 52 of the 60 farms had two receipt lines, all 52
    shared a header, 45 of them with two wired product streams. After: none."""
    plan = plan_plant(GeneratorConfigV2(seed=1, n_units=300))
    farms = [u.instance for u in plan.units if u.instance.pattern == "U4"]
    shared = [f for f in farms if any(n > 1 for n in receipts_reaching_each_tank(f).values())]
    assert (len(farms), len(shared)) == (60, 0)
    assert sum(sum(p.name.startswith("receipt") for p in f.ports) > 1 for f in farms) == 52
