"""Hand-written micro plans, one per construct, runnable on any `PlantBuilderV2`.

Each `plan_*` function adds only its own nodes to the equipment of `plan_base` (unit 1: tanks
`eq1`, `eq3`, pump `eq2`, vessel `eq4`). Node ids are prefixed per construct and tag numbers do
not overlap, so any set of plans can share one plant (`plan_all`). No test module: pytest does not
collect it.
"""

from __future__ import annotations

from collections.abc import Callable

from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    InstrumentSpec,
    LineItemSpec,
    LineSpec,
    LinkSpec,
    PlantBuilderV2,
)
from plantgraph.benchmark.v2.tags import (
    format_equipment_tag,
    format_instrument_tag,
    format_line_number,
    format_safety_tag,
    format_valve_tag,
)
from plantgraph.graph.schema import Relation

_PSGF = "ProcessSignalGeneratingFunction"
_PIF = "ProcessInstrumentationFunction"
_AF = "ActuatingFunction"


def item(node_id: str, node_class: str, tag: str | None = None) -> LineItemSpec:
    """One inline part."""
    return LineItemSpec(node_id=node_id, node_class=node_class, tag=tag)


def line(
    seq: int,
    src: str | None,
    items: tuple[LineItemSpec, ...],
    dst: str | None,
    unit: int = 1,
    service: str = "P",
) -> LineSpec:
    """A line whose number is unique per `seq`."""
    return LineSpec(
        line_number=format_line_number(4, service, unit, seq, "A1A", "N"),
        fluid_code=service,
        unit_no=unit,
        src_id=src,
        dst_id=dst,
        items=items,
    )


def instrument(node_id: str, node_class: str, tag: str | None, loop: str) -> InstrumentSpec:
    """One instrument node of unit 1; the measured variable is the loop tag's first letter."""
    return InstrumentSpec(
        node_id=node_id,
        node_class=node_class,
        unit_no=1,
        tag=tag,
        loop_tag=loop,
        measured_variable=loop[0],
    )


def link(builder: PlantBuilderV2, relation: Relation, source: str, target: str) -> None:
    """Add one link."""
    builder.add_link(LinkSpec(relation=relation, source_id=source, target_id=target))


def plan_base(builder: PlantBuilderV2) -> None:
    """Unit 1 with two tanks, a pump and a vessel."""
    builder.add_section(1, "TKF Feed tank")
    for node_id, node_class, code, seq in (
        ("eq1", "Tank", "TK", 1),
        ("eq2", "CentrifugalPump", "P", 1),
        ("eq3", "Tank", "TK", 2),
        ("eq4", "PressureVessel", "V", 1),
    ):
        tag = format_equipment_tag(code, 1, seq)
        builder.add_equipment(
            EquipmentSpec(node_id=node_id, node_class=node_class, unit_no=1, tag=tag)
        )


def plan_straight(builder: PlantBuilderV2) -> None:
    """eq1 -> gate valve -> eq2."""
    valve = item("st-v1", "GateValve", format_valve_tag("GTV", 1, 1))
    builder.add_line(line(1, "eq1", (valve,), "eq2"))


def plan_branch(builder: PlantBuilderV2) -> None:
    """A tee on a main line with a branch that ends open."""
    main = (
        item("br-v1", "GateValve", format_valve_tag("GTV", 1, 2)),
        item("br-t1", "PipeTee"),
        item("br-v2", "GateValve", format_valve_tag("GTV", 1, 3)),
    )
    builder.add_line(line(2, "eq2", main, "eq3"))
    branch = (item("br-v3", "GateValve", format_valve_tag("GTV", 1, 4)),)
    builder.add_line(line(3, "br-t1", branch, None))


def plan_merge(builder: PlantBuilderV2) -> None:
    """Two lines end at one tee; the main line starts open at that tee."""
    main = (item("mg-t1", "PipeTee"), item("mg-v3", "GateValve", format_valve_tag("GTV", 1, 5)))
    builder.add_line(line(4, None, main, "eq3"))
    first = (item("mg-v1", "GateValve", format_valve_tag("GTV", 1, 6)),)
    second = (item("mg-v2", "GateValve", format_valve_tag("GTV", 1, 7)),)
    builder.add_line(line(5, "eq1", first, "mg-t1"))
    builder.add_line(line(6, "eq2", second, "mg-t1"))


def plan_open_end(builder: PlantBuilderV2) -> None:
    """Vessel, block valve, relief valve, nothing after."""
    valve = item("oe-v1", "GateValve", format_valve_tag("GTV", 1, 8))
    relief = item("oe-psv", "SpringLoadedGlobeSafetyValve", format_safety_tag("PSV", 1, 40))
    builder.add_line(line(7, "eq4", (valve, relief), None))


def plan_open_start(builder: PlantBuilderV2) -> None:
    """A cooling-water stub that enters the drawing and ends at eq1."""
    valve = item("os-v1", "GateValve", format_valve_tag("GTV", 1, 9))
    builder.add_line(line(8, None, (valve,), "eq1", service="CWS"))


def plan_control_loop(builder: PlantBuilderV2) -> None:
    """Flow element on a line, transmitter, controller, actuator and a globe control valve."""
    parts = (
        item("cl-fe", "FlowMeasuringElement", format_instrument_tag("FE", 1, 14)),
        item("cl-fv", "GlobeValve", format_instrument_tag("FV", 1, 14)),
    )
    builder.add_line(line(9, "eq2", parts, "eq3"))
    loop = format_instrument_tag("FIC", 1, 14)
    builder.add_instrument(instrument("cl-ft", _PSGF, format_instrument_tag("FT", 1, 14), loop))
    builder.add_instrument(instrument("cl-fic", _PIF, loop, loop))
    builder.add_instrument(instrument("cl-af", _AF, None, loop))
    link(builder, Relation.MEASURED_BY, "cl-fe", "cl-ft")
    link(builder, Relation.SEND_SIGNAL_TO, "cl-ft", "cl-fic")
    link(builder, Relation.SEND_SIGNAL_TO, "cl-fic", "cl-af")
    link(builder, Relation.CONTROL, "cl-af", "cl-fv")


def plan_nozzle_sensing(builder: PlantBuilderV2) -> None:
    """Level transmitter on the vessel (a sensing nozzle) with an indicator."""
    loop = format_instrument_tag("LI", 1, 21)
    builder.add_instrument(instrument("ns-lt", _PSGF, format_instrument_tag("LT", 1, 21), loop))
    builder.add_instrument(instrument("ns-li", _PIF, loop, loop))
    link(builder, Relation.MEASURED_BY, "eq4", "ns-lt")
    link(builder, Relation.SEND_SIGNAL_TO, "ns-lt", "ns-li")


def plan_taps(builder: PlantBuilderV2) -> None:
    """Pressure tap (root valve, blind flange) and temperature tap (blind flange only)."""
    main = (item("tp-t1", "PipeTee"), item("tp-t2", "PipeTee"))
    builder.add_line(line(10, "eq2", main, "eq3"))
    pressure = (
        item("tp-bv", "BallValve", format_valve_tag("BV", 1, 10)),
        item("tp-bf1", "BlindFlange"),
    )
    builder.add_line(line(11, "tp-t1", pressure, None))
    builder.add_line(line(12, "tp-t2", (item("tp-bf2", "BlindFlange"),), None))
    for node_id, letters, seq, location in (
        ("tp-pt", "PT", 22, "tp-bf1"),
        ("tp-tt", "TT", 23, "tp-bf2"),
    ):
        indicator = format_instrument_tag(letters[0] + "I", 1, seq)
        builder.add_instrument(
            instrument(node_id, _PSGF, format_instrument_tag(letters, 1, seq), indicator)
        )
        builder.add_instrument(instrument(node_id + "i", _PIF, indicator, indicator))
        link(builder, Relation.MEASURED_BY, location, node_id)
        link(builder, Relation.SEND_SIGNAL_TO, node_id, node_id + "i")


def plan_trip(builder: PlantBuilderV2, letter: str = "X") -> None:
    """Level trip: transmitter, high-high switch, actuator, on-off valve with a position switch."""
    valve_tag = format_instrument_tag(letter + "V", 1, 30)
    builder.add_line(line(13, "eq1", (item("tr-xv", "BallValve", valve_tag),), "eq4"))
    loop = format_instrument_tag("LSHH", 1, 30)
    builder.add_instrument(instrument("tr-lt", _PSGF, format_instrument_tag("LT", 1, 30), loop))
    builder.add_instrument(instrument("tr-lshh", _PIF, loop, loop))
    builder.add_instrument(instrument("tr-af", _AF, None, loop))
    zso = format_instrument_tag("ZSO", 1, 30)
    builder.add_instrument(instrument("tr-zso", _PSGF, zso, zso))
    link(builder, Relation.MEASURED_BY, "eq1", "tr-lt")
    link(builder, Relation.SEND_SIGNAL_TO, "tr-lt", "tr-lshh")
    link(builder, Relation.SEND_SIGNAL_TO, "tr-lshh", "tr-af")
    link(builder, Relation.CONTROL, "tr-af", "tr-xv")
    link(builder, Relation.MEASURED_BY, "tr-xv", "tr-zso")


def plan_hand_switch(builder: PlantBuilderV2) -> None:
    """Hand switch -> actuator -> on-off valve."""
    valve_tag = format_instrument_tag("XV", 1, 31)
    builder.add_line(line(14, "eq3", (item("hs-xv", "BallValve", valve_tag),), "eq1"))
    switch = format_instrument_tag("HS", 1, 31)
    builder.add_instrument(instrument("hs-hs", _PIF, switch, switch))
    builder.add_instrument(instrument("hs-af", _AF, None, switch))
    link(builder, Relation.SEND_SIGNAL_TO, "hs-hs", "hs-af")
    link(builder, Relation.CONTROL, "hs-af", "hs-xv")


def plan_local_instrument(builder: PlantBuilderV2) -> None:
    """A pressure gauge on the vessel: one sensor, no bubble (convention I-2)."""
    tag = format_instrument_tag("PI", 1, 21)
    builder.add_instrument(instrument("li-pi", _PSGF, tag, tag))
    link(builder, Relation.MEASURED_BY, "eq4", "li-pi")


#: every construct plan, by name; each is meant to run after `plan_base`
CONSTRUCT_PLANS: dict[str, Callable[[PlantBuilderV2], None]] = {
    "straight": plan_straight,
    "branch": plan_branch,
    "merge": plan_merge,
    "open_end": plan_open_end,
    "open_start": plan_open_start,
    "control_loop": plan_control_loop,
    "nozzle_sensing": plan_nozzle_sensing,
    "taps": plan_taps,
    "trip": plan_trip,
    "hand_switch": plan_hand_switch,
    "local_instrument": plan_local_instrument,
}


def plan_all(builder: PlantBuilderV2) -> None:
    """The base equipment and every construct in one plant."""
    plan_base(builder)
    for build_construct in CONSTRUCT_PLANS.values():
        build_construct(builder)
