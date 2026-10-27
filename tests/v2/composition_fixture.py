"""A hand-built plant plan of 2 units and 3 sheets, with every count worked out by hand.

Not a test module (no `test_` prefix). `test_composition.py` checks the report against these counts.

Unit 1 (a pump set draws from tank `t1` into vessel `v1`) is drawn on sheets 1:1 and 1:2; unit 2
(two tanks) on sheet 2:1. The pumps `pa` and `pb` are one installed A/B set.

Sheet 1:1: equipment `t1`, `pa`, `pb` (3); valves `g1`, `g2` and the check valve `chk` (3);
instrument: the level sensor `lt` (1); stubs 2, both crossings (`chk` -> `fe`, `pb` -> `v1`);
signal cut 1 (`lt` to the controller on 1:2). Symbols = 3 + 3 + 0 + 1 + 2 = 9.

Sheet 1:2: equipment `v1` (1); valves `g3`, `g4` (2); fittings: flow element `fe`, blind flange
`bf` (2); instruments: sensor `ft`, bubble `fi`, controller `fic` (3; the actuator `af` is not
drawn); stubs 3 = 2 crossings + 1 open end (the outlet of `g3`; the end after `g4` is closed by the
blind flange); signal cut 1. Symbols = 1 + 2 + 2 + 3 + 3 = 11.

Sheet 2:1: equipment `t2`, `t3` (2); valves `g5`, `g6` (2); instruments `lt2`, `li2` (2); stubs 1
(the open inlet before `g6`); signal cuts 0. Symbols = 2 + 2 + 0 + 2 + 1 = 7.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.flowsheet import Slot, UnitSlot
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    LinkSpec,
)
from plantgraph.benchmark.v2.planner import PlannedUnit, PlantPlanV2
from plantgraph.benchmark.v2.sheets import UnitSheets
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.graph.schema import Relation

_PSGF = "ProcessSignalGeneratingFunction"
_PIF = "ProcessInstrumentationFunction"
_PCF = "ProcessControlFunction"
_AF = "ActuatingFunction"

#: hand counts per sheet: equipment, valves, fittings, instruments, stubs, crossings, signal cuts
HAND_COUNTS: dict[str, tuple[int, int, int, int, int, int, int]] = {
    "1:1": (3, 3, 0, 1, 2, 2, 1),
    "1:2": (1, 2, 2, 3, 3, 2, 1),
    "2:1": (2, 2, 0, 2, 1, 0, 0),
}
HAND_SYMBOLS = {"1:1": 9, "1:2": 11, "2:1": 7}
#: pumps P-A and P-B are the one installed set: 2 of the plant's 6 pieces of equipment
HAND_EQUIPMENT_IN_SPARE_SETS = 2
HAND_EQUIPMENT = 6


def _equipment(node_id: str, node_class: str, unit_no: int) -> EquipmentSpec:
    return EquipmentSpec(node_id=node_id, node_class=node_class, unit_no=unit_no, tag=node_id)


def _item(node_id: str, node_class: str) -> LineItemSpec:
    return LineItemSpec(node_id=node_id, node_class=node_class)


def _line(
    number: str, unit_no: int, src: str | None, items: list[LineItemSpec], dst: str | None
) -> LineSpec:
    return LineSpec(
        line_number=number,
        fluid_code="P",
        unit_no=unit_no,
        src_id=src,
        dst_id=dst,
        items=tuple(items),
    )


def _instrument(node_id: str, node_class: str, unit_no: int) -> InstrumentSpec:
    return InstrumentSpec(
        node_id=node_id,
        node_class=node_class,
        unit_no=unit_no,
        tag=None,
        loop_tag=node_id,
        measured_variable="F",
    )


def _link(relation: Relation, source: str, target: str) -> LinkSpec:
    return LinkSpec(relation=relation, source_id=source, target_id=target)


def _unit_one_plan() -> TrimPlan:
    equipment = (
        _equipment("t1", "Tank", 1),
        _equipment("pa", "CentrifugalPump", 1),
        _equipment("pb", "CentrifugalPump", 1),
        _equipment("v1", "PressureVessel", 1),
    )
    lines = (
        _line("L1", 1, "t1", [_item("g1", "GateValve")], "pa"),
        _line("L2", 1, "t1", [_item("g2", "GateValve")], "pb"),
        _line(
            "L3",
            1,
            "pa",
            [_item("chk", "SwingCheckValve"), _item("fe", "FlowMeasuringElement")],
            "v1",
        ),
        _line("L4", 1, "pb", [], "v1"),
        _line("L5", 1, "v1", [_item("g3", "GlobeValve")], None),
        _line("L6", 1, "v1", [_item("g4", "GateValve"), _item("bf", "BlindFlange")], None),
    )
    instruments = tuple(
        _instrument(node_id, node_class, 1)
        for node_id, node_class in [
            ("lt", _PSGF),
            ("ft", _PSGF),
            ("fi", _PIF),
            ("fic", _PCF),
            ("af", _AF),
        ]
    )
    links = (
        _link(Relation.MEASURED_BY, "fe", "ft"),
        _link(Relation.SEND_SIGNAL_TO, "ft", "fi"),
        _link(Relation.SEND_SIGNAL_TO, "lt", "fic"),  # the one signal cut: 1:1 -> 1:2
        _link(Relation.CONTROL, "af", "g3"),
    )
    return TrimPlan(
        equipment=equipment,
        lines=lines,
        instruments=instruments,
        links=links,
        spare_sets=(("pa", "pb"),),
    )


def _unit_two_plan() -> TrimPlan:
    return TrimPlan(
        equipment=(_equipment("t2", "Tank", 2), _equipment("t3", "Tank", 2)),
        lines=(
            _line("L7", 2, "t2", [_item("g5", "GateValve")], "t3"),
            _line("L8", 2, None, [_item("g6", "BallValve")], "t2"),
        ),
        instruments=(_instrument("lt2", _PSGF, 2), _instrument("li2", _PIF, 2)),
        links=(_link(Relation.SEND_SIGNAL_TO, "lt2", "li2"),),
    )


def _planned_unit(
    unit_no: int, pattern: str, plan: TrimPlan, sheet_of: dict[str, str]
) -> PlannedUnit:
    slot = UnitSlot(unit_no=unit_no, train_no=1, slot=Slot.CORE, pattern_id=pattern)
    groups = {item.node_id: "G1" for item in plan.equipment}
    instance = PatternInstance(
        pattern=pattern,
        system_code="TST",
        variant="fixture",
        plan=plan,
        drawing_group_of=groups,
    )
    sheets = UnitSheets(
        group_of=dict.fromkeys(sheet_of, "G1"),
        sheet_of=sheet_of,
        sheet_count=len(set(sheet_of.values())),
    )
    return PlannedUnit(slot=slot, instance=instance, sheets=sheets)


def hand_plan() -> PlantPlanV2:
    """The 2-unit, 3-sheet plan whose counts are in the module docstring."""
    first_sheet = dict.fromkeys(["t1", "pa", "pb", "g1", "g2", "chk", "lt"], "1:1")
    first_sheet |= dict.fromkeys(["v1", "fe", "g3", "g4", "bf", "ft", "fi", "fic", "af"], "1:2")
    second_sheet = dict.fromkeys(["t2", "t3", "g5", "g6", "lt2", "li2"], "2:1")
    units = (
        _planned_unit(1, "U4", _unit_one_plan(), first_sheet),
        _planned_unit(2, "U6", _unit_two_plan(), second_sheet),
    )
    return PlantPlanV2(
        config=GeneratorConfigV2(n_units=2), trains=(), units=units, open_stub_count=0
    )
