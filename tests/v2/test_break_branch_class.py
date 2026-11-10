"""Review R2: a branch off the stretch before a spec break is piped in that stretch's class.

A spec break (`PropertyBreak`) is where the pipe class steps down after a pressure drop: the
stretch before it is the heavier class. A drain, vent, bypass or tap taken off that stretch has to
match it, not the lighter class of the stretch after the break.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec, StreamKindV2
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.benchmark.v2.trim_plan import TrimPlan

_UPSTREAM = "4-P-10001-B1A-N"
_DOWNSTREAM = "4-P-10002-A1A-N"
_BRANCH = "2-P-10003-A1A-N"


def _item(node_id: str, node_class: str = "GateValve") -> LineItemSpec:
    return LineItemSpec(node_id=node_id, node_class=node_class)


def _plan_with_branches(src: str) -> TrimPlan:
    """A main line `tee_up, valve, break, tee_down` and one branch that starts at `src`."""
    main = LineSpec(
        line_number=_UPSTREAM,
        fluid_code="P",
        unit_no=1,
        src_id="vessel",
        dst_id="tank",
        items=(_item("tee_up", "PipeTee"), _item("br", "PropertyBreak"), _item("tee_down")),
        line_number_after_break=_DOWNSTREAM,
    )
    branch = LineSpec(
        line_number=_BRANCH,
        fluid_code="P",
        unit_no=1,
        src_id=src,
        dst_id=None,
        items=(_item("drain"),),
    )
    return TrimPlan(lines=(main, branch), stream_kinds={_BRANCH: StreamKindV2.TRIM})


def test_a_branch_off_the_upstream_stretch_takes_its_class_and_keeps_its_stream_kind() -> None:
    fixed = _plan_with_branches("tee_up").with_branches_on_break_class()
    branch = fixed.lines[1]
    assert branch.line_number == "2-P-10003-B1A-N"  # only the class field changed
    assert fixed.stream_kinds == {"2-P-10003-B1A-N": StreamKindV2.TRIM}


def test_a_branch_off_the_downstream_stretch_keeps_the_base_class() -> None:
    fixed = _plan_with_branches("tee_down").with_branches_on_break_class()
    assert fixed.lines[1].line_number == _BRANCH
    assert fixed.stream_kinds == {_BRANCH: StreamKindV2.TRIM}


def _wrong_class_branches(plan: PlantPlanV2) -> tuple[int, int]:
    """(branches off an upstream stretch in a lighter class than it, all such branches)."""
    wrong = total = 0
    for unit in plan.units:
        lines = unit.instance.plan.lines
        for main in (line for line in lines if line.line_number_after_break is not None):
            cut = next(i for i, p in enumerate(main.items) if p.node_class == "PropertyBreak")
            upstream = {p.node_id for p in main.items[: cut + 1]}
            spec = parse_line_number(main.line_number)
            assert spec is not None
            for line in (line for line in lines if line.src_id in upstream and line is not main):
                parsed = parse_line_number(line.line_number)
                assert parsed is not None
                total += 1
                wrong += parsed.spec != spec.spec
    return wrong, total


def test_seed_1_300_units_has_no_branch_in_a_lighter_class_than_its_upstream_stretch() -> None:
    """Before R2: 73 of 73 such branches were in the base class (measured on the HEAD plant)."""
    plan = plan_plant(GeneratorConfigV2(seed=1, n_units=300))
    assert _wrong_class_branches(plan) == (0, 73)


def test_every_renamed_line_number_is_still_a_key_of_the_stream_kinds() -> None:
    plan = plan_plant(GeneratorConfigV2(seed=1, n_units=120))
    for unit in plan.units:
        kinds = unit.instance.plan.stream_kinds
        numbers = {number for line in unit.instance.plan.lines for number in line.line_numbers}
        assert numbers <= set(kinds), f"unit {unit.slot.unit_no} lacks {numbers - set(kinds)}"
