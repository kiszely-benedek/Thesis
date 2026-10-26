"""The instrument templates of the base design (generator-v2-realism.md 4.4).

Each template function returns a `TrimPlan` holding only the instruments, links and small taps it
adds (never a `run`), to be joined to the plan of the part it instruments with `combine`. The
control valves, on-off valves and flow elements the loops attach to come from the trims
(`trims_valves.py`), which already numbered them; a template reads that number from the tag and
gives its own members the same one (invariant S8). The exception is `flow_control_loop`, which
renumbers the flow element planned first and so returns the combined plan.

Which loop goes where (the control schemes) is the pattern's choice, not made here.

| Template | Chain |
|---|---|
| `control_loop` | `xT -> xIC -> AF -> xV` |
| `indicating_transmitter` | `xT -> xI` or `xT -> xIAH` (alarm letters in the bubble) |
| `process_trip` | `xT -> xSHH or xSLL -> AF -> XV` |
| `flame_failure_trip` | `BE -> BSL -> AF -> XV` |
| `hand_switch` | `HS -> AF -> XV` |
| `differential_pressure` | `PDT -> PDI` |
| `totaliser` | `FT -> FQI` |
| `ratio_control_loop` | `FFT, FT -> FFIC -> AF -> FV` |
| `analyser_point` | `AT -> AI` |
| `machine_monitor` | `ST -> SI`, `VT -> VAH`, `TT -> TIAH`, `IT -> II` on a machine |
"""

from __future__ import annotations

from typing import Literal

from plantgraph.benchmark.v2.instrument_draft import (
    InstrumentDraft,
    parsed_tag_of,
    part_of,
    with_part_number,
)
from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import NodeClass

#: the trips of a process variable: high-high or low-low
TripLevel = Literal["HH", "LL"]


def _loop_number(ctx: TrimContext, valve: LineItemSpec, wanted: ItemKind) -> int:
    """The loop number of `valve`, after checking it is the kind of valve the template drives."""
    parsed = parsed_tag_of(valve, ctx.unit_no)
    if item_kind(valve.node_class, parsed.letters) is not wanted:
        raise ValueError(
            f"expected a {wanted.value} for {valve.node_id!r}, got {valve.node_class} "
            f"tagged {valve.tag!r}"
        )
    return parsed.sequence


def _actuate(draft: InstrumentDraft, bubble_id: str, bubble_tag: str, valve: LineItemSpec) -> str:
    """An actuator fed by the bubble that moves `valve`; returns the actuator's id."""
    actuator = draft.actuator_node(bubble_tag, "loop_actuator")
    draft.feed(bubble_id, actuator)
    draft.operate(actuator, valve.node_id)
    return actuator


# ---- control loop -------------------------------------------------------------------------------


def control_loop(
    ctx: TrimContext, style: LineStyle, valve: LineItemSpec, location_id: str
) -> TrimPlan:
    """`xT -> xIC -> AF -> xV`: a transmitter on `location_id` and a controller for `valve`.

    The valve's tag (`LV-12005`) sets the variable (`L`) and the number; the sensor is `LT-12005`
    and the controller `LIC-12005`. Rules L17, L18 (ADR-0044: the valve carries the loop's tag).
    """
    draft = InstrumentDraft(ctx, style)
    number = _loop_number(ctx, valve, ItemKind.CONTROL_VALVE)
    variable = valve.tag[0] if valve.tag else ""
    sensor, controller = draft.sensor_and_bubble(
        f"{variable}T", f"{variable}IC", number, location_id, "loop", controller=True
    )
    actuator = _actuate(draft, controller, draft.tag(f"{variable}IC", number), valve)
    return draft.finish(transmitter=sensor, controller=controller, actuator=actuator)


def flow_control_loop(
    ctx: TrimContext, style: LineStyle, element_plan: TrimPlan, valve_plan: TrimPlan
) -> TrimPlan:
    """A flow loop `FE, FT -> FIC -> AF -> FV` over the plans of the element and the valve.

    The element is renumbered to the valve's number so that `FE`, `FT`, `FIC` and `FV` share one.
    Returns the element's, the valve's and the loop's parts combined, element first in the `run`
    (the flow element sits upstream of the valve).
    """
    element = part_of(element_plan, "element")
    valve = part_of(valve_plan, "body")
    number = parsed_tag_of(valve, ctx.unit_no).sequence
    renumbered = with_part_number(element_plan, element.node_id, number)
    loop = control_loop(ctx, style, valve, element.node_id)
    return combine(renumbered, valve_plan, loop)


# ---- indicating transmitters ---------------------------------------------------------------------


def transmitter_with_bubble(
    ctx: TrimContext,
    style: LineStyle,
    location_id: str,
    sensor_letters: str,
    bubble_letters: str,
    number: int | None = None,
) -> TrimPlan:
    """A sensor on `location_id` feeding one bubble; any pair of letters, one shared number.

    `number` is a fresh one unless the caller has a number to share (a flow element's).
    """
    draft = InstrumentDraft(ctx, style)
    loop_number = draft.new_number() if number is None else number
    sensor, bubble = draft.sensor_and_bubble(
        sensor_letters, bubble_letters, loop_number, location_id, "monitor"
    )
    return draft.finish(transmitter=sensor, indicator=bubble)


def indicating_transmitter(
    ctx: TrimContext,
    style: LineStyle,
    location_id: str,
    variable: str,
    alarm: Literal["H", "L"] | None = None,
) -> TrimPlan:
    """`xT -> xI`, or `xT -> xIAH` / `xT -> xIAL` when the indicator also raises an alarm.

    The alarm is only letters in the bubble's tag (`LIAH-12011`), no node of its own.
    """
    bubble = f"{variable}I" if alarm is None else f"{variable}IA{alarm}"
    return transmitter_with_bubble(ctx, style, location_id, f"{variable}T", bubble)


def machine_monitor(
    ctx: TrimContext,
    style: LineStyle,
    machine_id: str,
    kind: Literal["speed", "vibration", "bearing_temperature", "motor_current"],
) -> TrimPlan:
    """A condition-monitoring instrument on a machine's own nozzle.

    `speed`: `ST -> SI`; `vibration`: `VT -> VAH`; `bearing_temperature`: `TT -> TIAH`;
    `motor_current`: `IT -> II`.
    """
    letters = {
        "speed": ("ST", "SI"),
        "vibration": ("VT", "VAH"),
        "bearing_temperature": ("TT", "TIAH"),
        "motor_current": ("IT", "II"),
    }
    sensor, bubble = letters[kind]
    return transmitter_with_bubble(ctx, style, machine_id, sensor, bubble)


# ---- trips and hand switches --------------------------------------------------------------------


def process_trip(
    ctx: TrimContext,
    style: LineStyle,
    valve: LineItemSpec,
    location_id: str,
    variable: str,
    level: TripLevel,
) -> TrimPlan:
    """`xT -> xSHH -> AF -> XV` (or `xSLL`): the valve shuts when the variable goes out of range.

    Used for tank overfill, knock-out drum high level, separator high pressure and fuel-gas low
    pressure (base 4.4). The trip and its valve share the valve's number: `LT-12030`,
    `LSHH-12030`, `XV-12030`.
    """
    return _trip(ctx, style, valve, location_id, f"{variable}T", f"{variable}S{level}")


def flame_failure_trip(
    ctx: TrimContext, style: LineStyle, valve: LineItemSpec, furnace_id: str
) -> TrimPlan:
    """`BE -> BSL -> AF -> XV`: a flame sensor on the furnace shuts the fuel-gas valve."""
    return _trip(ctx, style, valve, furnace_id, "BE", "BSL")


def _trip(
    ctx: TrimContext,
    style: LineStyle,
    valve: LineItemSpec,
    location_id: str,
    sensor_letters: str,
    switch_letters: str,
) -> TrimPlan:
    draft = InstrumentDraft(ctx, style)
    number = _loop_number(ctx, valve, ItemKind.ON_OFF_VALVE)
    sensor, switch = draft.sensor_and_bubble(
        sensor_letters, switch_letters, number, location_id, "trip"
    )
    actuator = _actuate(draft, switch, draft.tag(switch_letters, number), valve)
    return draft.finish(transmitter=sensor, trip_switch=switch, actuator=actuator)


def hand_switch(ctx: TrimContext, style: LineStyle, valve: LineItemSpec) -> TrimPlan:
    """`HS -> AF -> XV`: remote manual open and close from the control room.

    A hand switch senses nothing, so the loop has no sensor; the bubble takes the valve's number.
    """
    draft = InstrumentDraft(ctx, style)
    number = _loop_number(ctx, valve, ItemKind.ON_OFF_VALVE)
    switch_tag = draft.tag("HS", number)
    switch = draft.bubble_node(switch_tag, "hand_switch")
    actuator = _actuate(draft, switch, switch_tag, valve)
    return draft.finish(hand_switch=switch, actuator=actuator)


# ---- measurements that are not loops ------------------------------------------------------------


def differential_pressure(ctx: TrimContext, style: LineStyle, tee_id: str) -> TrimPlan:
    """`PDT -> PDI` on a tap: `tee -> needle valve -> blind flange`, the transmitter on the flange.

    A real transmitter has two taps; DEXPI gives a sensor one sensing location, so this one sits
    at the high-pressure tap and the low side is not drawn.
    """
    draft = InstrumentDraft(ctx, style)
    root = draft.part(NodeClass.NEEDLE_VALVE.value, "dp_tap_root")
    flange = draft.part(NodeClass.BLIND_FLANGE.value, "dp_tap_flange")
    draft.line(tee_id, [root, flange], None, style=style.branch())
    sensor, bubble = draft.sensor_and_bubble("PDT", "PDI", draft.new_number(), flange.node_id, "dp")
    return draft.finish(transmitter=sensor, indicator=bubble, tap_flange=flange)


def totaliser(ctx: TrimContext, style: LineStyle, element: LineItemSpec) -> TrimPlan:
    """`FT -> FQI`: a transmitter on a flow element and a totaliser (the volume that has passed).

    Both take the element's number: `FE-12050`, `FT-12050`, `FQI-12050`.
    """
    number = parsed_tag_of(element, ctx.unit_no).sequence
    return transmitter_with_bubble(ctx, style, element.node_id, "FT", "FQI", number)


def analyser_point(
    ctx: TrimContext, style: LineStyle, tee_id: str, indicator: bool = True
) -> TrimPlan:
    """An analyser tap `tee -> blind flange` with `AT -> AI`; the flange is port `flange`.

    The flange stands in for the analyser's probe flange. With `indicator` false only the tap is
    planned, for a master controller (`cascade_master` adds the `AT` and the `AIC`).
    """
    draft = InstrumentDraft(ctx, style)
    flange = draft.part(NodeClass.BLIND_FLANGE.value, "analyser_flange")
    draft.line(tee_id, [flange], None, style=style.branch())
    if not indicator:
        return draft.finish(flange=flange)
    sensor, bubble = draft.sensor_and_bubble(
        "AT", "AI", draft.new_number(), flange.node_id, "analyser"
    )
    return draft.finish(flange=flange, transmitter=sensor, indicator=bubble)


def ratio_control_loop(
    ctx: TrimContext,
    style: LineStyle,
    wild_element_id: str,
    element_plan: TrimPlan,
    valve_plan: TrimPlan,
) -> TrimPlan:
    """`FFT, FT -> FFIC -> AF -> FV`: hold the controlled flow at a set ratio to the wild flow.

    The *wild* stream (the main flow) is only measured, by `FFT` on `wild_element_id`; the
    *controlled* stream (the additive) has the element, `FT` and the valve. Both transmitters
    feed the one ratio controller, and all share the valve's number (the controlled stream's
    `FE` is renumbered). The wild transmitter is `FFT` (flow-ratio transmitter) so its tag
    differs from `FT-n`. Returns the combined plan, like `flow_control_loop`.
    """
    element = part_of(element_plan, "element")
    valve = part_of(valve_plan, "body")
    number = _loop_number(ctx, valve, ItemKind.CONTROL_VALVE)
    draft = InstrumentDraft(ctx, style)
    sensor, controller = draft.sensor_and_bubble(
        "FT", "FFIC", number, element.node_id, "ratio", controller=True
    )
    controller_tag = draft.tag("FFIC", number)
    wild = draft.sensor(draft.tag("FFT", number), controller_tag, wild_element_id, "ratio_wild")
    draft.feed(wild, controller)
    actuator = _actuate(draft, controller, controller_tag, valve)
    loop = draft.finish(
        transmitter=sensor, transmitter_wild=wild, controller=controller, actuator=actuator
    )
    renumbered = with_part_number(element_plan, element.node_id, number)
    return combine(renumbered, valve_plan, loop)
