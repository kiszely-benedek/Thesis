"""The instrument templates the real samples added (generator-v2-pid-vocabulary.md 5.1, 5.3, 13.5).

Same conventions as `instruments.py`: each function returns a `TrimPlan` of instruments and links
to be combined with the plan of the part it instruments.

| Template | Chain |
|---|---|
| `cascade_master` | master `xIC` feeding the slave controller of an existing loop |
| `split_range_loop` | one controller, two valves (off by default: `p_split_range` is 0) |
| `machine_start_stop` | `HS -> AEF -> machine`, plus a running-status `YI` on the machine |
| `speed_control_loop` | `xT -> xIC -> AEF -> machine` (variable-speed drive) |
| `ratio_speed_loop` | `FFT, FT -> FFIC -> AEF -> machine` (ratio set by pump speed) |
| `point_level_alarm` | `LSH -> LAH` or `LSL -> LAL` |
| `drain_pot_instruments` | level loop, `CT -> CSHH -> AF -> XV` tube-leak trip, `CT -> CI` |
| `multivariable_controller` | `TT, PT -> UC` on a reactor |
| `monitor_points` | the 5 to 7 nozzle-mounted gauges or transmitters of a major item |
"""

from __future__ import annotations

from typing import Literal

from plantgraph.benchmark.v2.config import InstrumentConvention, InstrumentDensity, IntRange
from plantgraph.benchmark.v2.instrument_draft import (
    InstrumentDraft,
    node_with_role,
    parsed_tag_of,
    parts_of,
)
from plantgraph.benchmark.v2.instruments import (
    control_loop,
    indicating_transmitter,
    process_trip,
    transmitter_with_bubble,
)
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind

Side = Literal["H", "L"]


# ---- cascade and split range -----------------------------------------------------------------


def cascade_master(
    ctx: TrimContext, style: LineStyle, slave_loop: TrimPlan, variable: str, location_id: str
) -> TrimPlan:
    """A master loop `xT -> xIC` whose output sets the set point of an existing slave controller.

    `slave_loop` is a `control_loop` or `flow_control_loop` plan (port `controller`). The result
    is one more PSGF and PCF and a signal line master to slave, so the slave controller has one
    sensor and one controller feeding it (invariant S22) and keeps the valve's loop tag.
    Pairs from the samples: temperature master over a steam-flow slave, level over flow,
    analyser (`variable` `A`) over temperature.
    """
    draft = InstrumentDraft(ctx, style)
    _, master = draft.sensor_and_bubble(
        f"{variable}T", f"{variable}IC", draft.new_number(), location_id, "cascade_master", True
    )
    draft.feed(master, slave_loop.ports["controller"])
    return draft.finish(master_controller=master)


def wants_split_range(ctx: TrimContext, convention: InstrumentConvention) -> bool:
    """True with chance `p_split_range`, which is 0 by default: split range is never drawn then."""
    return ctx.chance(convention.p_split_range)


def split_range_loop(
    ctx: TrimContext,
    style: LineStyle,
    first_valve: LineItemSpec,
    second_valve: LineItemSpec,
    location_id: str,
) -> TrimPlan:
    """`xT -> xIC -> AF1 -> xV-A` and `-> AF2 -> xV-B`: one controller shares its range.

    The loop number is the first valve's. The second valve keeps its own number: tags are unique
    and the grammar has no suffix, so invariant S4 exempts it.
    """
    first_plan = control_loop(ctx, style, first_valve, location_id)
    draft = InstrumentDraft(ctx, style)
    second_kind = item_kind(
        second_valve.node_class, parsed_tag_of(second_valve, ctx.unit_no).letters
    )
    if second_kind is not ItemKind.CONTROL_VALVE:
        raise ValueError(
            f"expected a control valve as the second split-range valve, got "
            f"{second_valve.node_class} tagged {second_valve.tag!r}"
        )
    controller_id = first_plan.ports["controller"]
    controller_tag = next(i.tag for i in first_plan.instruments if i.node_id == controller_id)
    actuator = draft.actuator_node(controller_tag or "", "split_range_actuator")
    draft.feed(controller_id, actuator)
    draft.operate(actuator, second_valve.node_id)
    second = draft.finish(second_actuator=actuator)
    return combine(first_plan, second)


# ---- machines --------------------------------------------------------------------------------


def machine_start_stop(
    ctx: TrimContext, style: LineStyle, convention: InstrumentConvention, machine_id: str
) -> TrimPlan:
    """`HS -> AEF -> machine` and a running-status `YI` on it, with chance `p_motor_hs`.

    An **AEF** is a machine's electrical input, the counterpart of a valve's actuator. The
    machine must be motor-driven (`has_motor`); the builder refuses it otherwise. Both bubbles
    share one number, `HS-12031` and `YI-12031`.
    """
    draft = InstrumentDraft(ctx, style)
    if not ctx.chance(convention.p_motor_hs):
        return draft.finish()
    number = draft.new_number()
    switch_tag = draft.tag("HS", number)
    switch = draft.bubble_node(switch_tag, "hand_switch")
    actuator = draft.actuator_node(switch_tag, "start_stop_actuator", electrical=True)
    draft.feed(switch, actuator)
    draft.operate(actuator, machine_id)
    status_tag = draft.tag("YI", number)
    status = draft.sensor(status_tag, status_tag, machine_id, "running_status")
    return draft.finish(hand_switch=switch, running_status=status)


def speed_control_loop(
    ctx: TrimContext, style: LineStyle, machine_id: str, location_id: str, variable: str
) -> TrimPlan:
    """`xT -> xIC -> AEF -> machine`: a variable-speed drive follows a pressure or flow loop."""
    draft = InstrumentDraft(ctx, style)
    number = draft.new_number()
    sensor, controller = draft.sensor_and_bubble(
        f"{variable}T", f"{variable}IC", number, location_id, "speed_loop", controller=True
    )
    actuator = draft.actuator_node(draft.tag(f"{variable}IC", number), "speed_actuator", True)
    draft.feed(controller, actuator)
    draft.operate(actuator, machine_id)
    return draft.finish(transmitter=sensor, controller=controller, actuator=actuator)


def ratio_speed_loop(
    ctx: TrimContext,
    style: LineStyle,
    wild_element_id: str,
    element_id: str,
    machine_id: str,
    number: int | None = None,
) -> TrimPlan:
    """`FFT, FT -> FFIC -> AEF -> machine`: a ratio controller sets a dosing pump's speed.

    The same loop as `ratio_control_loop`, with the pump's variable-speed drive in place of the
    control valve. `number` is the loop number (a fresh one by default).
    """
    draft = InstrumentDraft(ctx, style)
    loop_number = draft.new_number() if number is None else number
    sensor, controller = draft.sensor_and_bubble(
        "FT", "FFIC", loop_number, element_id, "ratio_speed", controller=True
    )
    controller_tag = draft.tag("FFIC", loop_number)
    wild = draft.sensor(
        draft.tag("FFT", loop_number), controller_tag, wild_element_id, "ratio_wild"
    )
    draft.feed(wild, controller)
    actuator = draft.actuator_node(controller_tag, "speed_actuator", True)
    draft.feed(controller, actuator)
    draft.operate(actuator, machine_id)
    return draft.finish(
        transmitter=sensor, transmitter_wild=wild, controller=controller, actuator=actuator
    )


# ---- level switches, drain pot, reactor ------------------------------------------------------


def point_level_alarm(
    ctx: TrimContext, style: LineStyle, equipment_id: str, side: Side
) -> TrimPlan:
    """`LSH -> LAH` (high) or `LSL -> LAL` (low): a level switch and its alarm bubble."""
    return transmitter_with_bubble(ctx, style, equipment_id, f"LS{side}", f"LA{side}")


def alarm_side(ctx: TrimContext, density: InstrumentDensity, side: Side) -> Side | None:
    """`side` with chance `p_indicator_alarm`, else None: whether an indicator also alarms."""
    return side if ctx.chance(density.p_indicator_alarm) else None


def drain_pot_instruments(ctx: TrimContext, style: LineStyle, pot_plan: TrimPlan) -> TrimPlan:
    """The instruments of a condensate drain pot, found in the pot's plan by role.

    A level loop `LT -> LIC -> LV` on the pot, a tube-leak trip `CT -> CSHH -> AF -> XV` (high
    conductivity means process leaked into the steam side), and a separate `CT -> CI` indicator.
    The trip has its own transmitter: a safety loop does not share a sensor with indication.
    """
    pot_id = node_with_role(pot_plan, "condensate_drain_pot")
    parts = parts_of(pot_plan)
    level_valve = parts[node_with_role(pot_plan, "pot_level_valve")]
    trip_valve = parts[node_with_role(pot_plan, "pot_trip_valve")]
    return combine(
        control_loop(ctx, style, level_valve, pot_id).with_port_prefix("level"),
        process_trip(ctx, style, trip_valve, pot_id, "C", "HH").with_port_prefix("trip"),
        indicating_transmitter(ctx, style, pot_id, "C").with_port_prefix("conductivity"),
    )


def multivariable_controller(ctx: TrimContext, style: LineStyle, reactor_id: str) -> TrimPlan:
    """`TT, PT -> UC`: one multivariable controller (`U`) reads a temperature and a pressure."""
    draft = InstrumentDraft(ctx, style)
    number = draft.new_number()
    controller_tag = draft.tag("UC", number)
    controller = draft.bubble_node(controller_tag, "multivariable", controller=True)
    for letters in ("TT", "PT"):
        sensor = draft.sensor(draft.tag(letters, number), controller_tag, reactor_id, "uc_input")
        draft.feed(sensor, controller)
    return draft.finish(controller=controller)


# ---- monitoring points -----------------------------------------------------------------------


def monitor_points(
    ctx: TrimContext, style: LineStyle, density: InstrumentDensity, equipment_id: str
) -> TrimPlan:
    """The monitoring points of one major item: `monitor_points_per_major_item` of them.

    Each is a temperature or pressure point on a nozzle of its own: a local gauge (one sensor),
    or a transmitter with an indicator. No root valve is added, so valve counts stay clean.
    """
    count = _draw(ctx, density.monitor_points_per_major_item)
    points = [_monitor_point(ctx, style, density, equipment_id) for _ in range(count)]
    return combine(*(point.with_port_prefix(f"point{i}") for i, point in enumerate(points)))


def temperature_points(
    ctx: TrimContext, style: LineStyle, equipment_id: str, points: IntRange
) -> TrimPlan:
    """`TT -> TI` at several points of one item (tray temperatures, reactor bed temperatures)."""
    count = _draw(ctx, points)
    plans = [indicating_transmitter(ctx, style, equipment_id, "T") for _ in range(count)]
    return combine(*(plan.with_port_prefix(f"point{i}") for i, plan in enumerate(plans)))


def _draw(ctx: TrimContext, span: IntRange) -> int:
    return ctx.rng.randint(span.low, span.high)


def _monitor_point(
    ctx: TrimContext, style: LineStyle, density: InstrumentDensity, equipment_id: str
) -> TrimPlan:
    weights = density.monitor_variable_weights
    variable = ctx.rng.choices(list(weights), weights=list(weights.values()))[0]
    if ctx.chance(density.p_monitor_local):
        draft = InstrumentDraft(ctx, style)
        draft.local_indicator(f"{variable}I", equipment_id, "monitor_gauge")
        return draft.finish()
    return indicating_transmitter(ctx, style, equipment_id, variable)
