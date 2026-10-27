"""Small helpers for the patterns with motor-driven machines: compressors, mixers, agitators.

A **machine** here is any equipment a motor drives. Its tag comes from the class (`K-1203` for a
compressor, `M-1204` for an agitator); the motor itself is a component the DEXPI builder adds
(`has_motor`), not a node of its own. An **agitator** is the stirrer inside a vessel; the plan
records the vessel-to-agitator link, and both must sit in the same drawing group (S20).
"""

from __future__ import annotations

from plantgraph.benchmark.v2.instruments import machine_monitor
from plantgraph.benchmark.v2.instruments_extra import machine_start_stop
from plantgraph.benchmark.v2.patterns.assembly import quiet, spared_set
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.plan_models import LinkSpec
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.graph.schema import CLASS_SPECS, NodeClass, Relation


def type_code_of(node_class: str) -> str:
    """The tag letters of an equipment class (`K` for a compressor); raises if it has none."""
    prefix = CLASS_SPECS[NodeClass(node_class)].tag_prefix
    if prefix is None:
        raise ValueError(f"expected an equipment class with a tag prefix, got {node_class!r}")
    return prefix


def machine_plan(
    ctx: PatternContext, node_class: str, role: str, has_motor: bool = False
) -> TrimPlan:
    """A plan holding one machine of `node_class` (port `equipment`); no lines."""
    (machine,) = spared_set(ctx, node_class, type_code_of(node_class), 1, has_motor=has_motor)
    return TrimPlan(
        equipment=(machine,), roles={machine.node_id: role}, ports={"equipment": machine.node_id}
    )


def agitator_plan(ctx: PatternContext, vessel_id: str) -> TrimPlan:
    """A motor-driven agitator (port `equipment`) and the `has_agitator` link from its vessel."""
    agitator = machine_plan(ctx, NodeClass.AGITATOR.value, "agitator", has_motor=True)
    link = LinkSpec(
        relation=Relation.HAS_AGITATOR, source_id=vessel_id, target_id=agitator.ports["equipment"]
    )
    return agitator.model_copy(update={"links": (link,)})


def with_line_end(plan: TrimPlan, line_number: str, dst_id: str) -> TrimPlan:
    """The plan with the open end of line `line_number` joined to the node `dst_id`.

    Used when a pump set's discharge, which a pattern ends open by default, feeds a machine of
    the same pattern. Raises if the line is not in the plan or is already joined.
    """
    found = [line for line in plan.lines if line.line_number == line_number]
    if len(found) != 1 or found[0].dst_id is not None:
        raise ValueError(
            f"expected one line {line_number!r} open at its end, found "
            f"{[(line.line_number, line.dst_id) for line in found]}"
        )
    lines = tuple(
        line.model_copy(update={"dst_id": dst_id}) if line.line_number == line_number else line
        for line in plan.lines
    )
    return plan.model_copy(update={"lines": lines})


def motor_drive(ctx: PatternContext, machine_id: str) -> TrimPlan:
    """Start/stop with running status, and with `p_motor_current` the motor current `IT -> II`."""
    parts = [machine_start_stop(ctx.trim, ctx.style, ctx.instruments, machine_id)]
    if ctx.chance(ctx.density.p_motor_current):
        parts.append(machine_monitor(ctx.trim, ctx.style, machine_id, "motor_current"))
    return combine(*(quiet(part) for part in parts))
