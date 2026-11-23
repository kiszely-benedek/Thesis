"""The three ways a v2.2 pump keeps its minimum flow, by hidden power band (Toghraei 2019 p.313).

A **min-flow line** (spillback) lets a centrifugal pump return liquid to its suction vessel so it
never runs against a closed valve. How elaborate the line is depends on the pump's power, a
quantity the drawing never shows (`PumpPowerBand`, see `hidden_state.py`):

| Band | Method | Parts on the line |
|---|---|---|
| 5-20 hp | restriction orifice (RO) | orifice between flanges, check valve, gate valve |
| 20-35 hp | on-off switching valve | check valve, XV opened by a low-flow switch on an FT |
| above 35 hp | flow control loop | check valve, FV moved by an FIC fed by an FT |

(An `FT` is a flow transmitter, an `FIC` a flow indicating controller, an `FV` a flow control
valve.) Below 5 hp a pump has no min-flow line at all; that is `trims.pump_trims`'s decision.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.class_decks import MIN_FLOW_CHECK
from plantgraph.benchmark.v2.hidden_state import PumpPowerBand
from plantgraph.benchmark.v2.instruments import control_loop, process_trip
from plantgraph.benchmark.v2.plan_models import LineItemSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, combine
from plantgraph.benchmark.v2.trims_extra import on_off_valve_part, orifice_flange_set_items
from plantgraph.graph.schema import NodeClass

#: roles of the method-specific valves; the rule check finds the method by them
SWITCH_VALVE_ROLE = "min_flow_switch_valve"
CONTROL_VALVE_ROLE = "min_flow_control_valve"


def min_flow_line(
    ctx: TrimContext,
    style: LineStyle,
    band: PumpPowerBand,
    discharge_tee_id: str,
    vessel_id: str,
) -> TrimPlan:
    """The min-flow line of a pump in `band`, from its discharge tee back to the suction vessel."""
    if band is PumpPowerBand.BELOW_5:
        raise ValueError("expected a band of 5 hp or more: a pump below 5 hp has no min-flow line")
    draft = TrimDraft(ctx, style)
    parts = _line_parts(draft, band)
    draft.line(discharge_tee_id, parts, vessel_id, StreamKindV2.RECYCLE, style.branch())
    instruments = _instruments(ctx, style, band, discharge_tee_id, parts)
    return combine(draft.finish(), instruments)


def _line_parts(draft: TrimDraft, band: PumpPowerBand) -> list[LineItemSpec]:
    """The parts of the line in flow order: the method's own parts, then the check valve."""
    # rule TOG313-MINFLOW-METHOD: the min-flow method follows the pump power (Toghraei 2019 p.313)
    if band is PumpPowerBand.B5_20:
        return [
            *orifice_flange_set_items(draft),
            draft.part(MIN_FLOW_CHECK, "min_flow_check"),
            draft.part(NodeClass.GATE_VALVE.value, "min_flow_block"),
        ]
    check = draft.part(MIN_FLOW_CHECK, "min_flow_check")
    if band is PumpPowerBand.B20_35:
        return [check, on_off_valve_part(draft, SWITCH_VALVE_ROLE)]
    return [check, _flow_control_valve(draft)]


def _flow_control_valve(draft: TrimDraft) -> LineItemSpec:
    """A control valve body tagged `FV-n`, its class dealt from the control-valve deck."""
    tag = draft.ctx.numbering.instrument_tag("FV")
    return draft.tagged_part(draft.ctx.deal_class("control_valve_body"), CONTROL_VALVE_ROLE, tag)


def _instruments(
    ctx: TrimContext,
    style: LineStyle,
    band: PumpPowerBand,
    discharge_tee_id: str,
    parts: list[LineItemSpec],
) -> TrimPlan:
    """The loop on the line's valve: the transmitter reads the pump's discharge flow."""
    if band is PumpPowerBand.B5_20:
        return TrimPlan()
    valve = parts[-1]
    if band is PumpPowerBand.B20_35:
        return process_trip(ctx, style, valve, discharge_tee_id, "F", "LL")  # FT -> FSLL -> XV
    return control_loop(ctx, style, valve, discharge_tee_id)  # FT -> FIC -> FV
