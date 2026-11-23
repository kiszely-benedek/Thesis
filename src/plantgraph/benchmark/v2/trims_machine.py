"""The spec break at the discharge nozzle of a pump or compressor (v2.2 only).

A pump or compressor raises the pressure of the stream, so its discharge pipe must be a heavier
**piping class** (a pipe's material and pressure rating) than its suction pipe, and a
`PropertyBreak` right after the machine marks where the class changes (Toghraei 2019 p.82,
Table 6.5). The break stands alone on a one-part line that starts at the machine; the
discharge line proper starts at the break and carries the heavier class.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.plan_models import LineItemSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.benchmark.v2.vocabulary import LINE_SPECS
from plantgraph.graph.schema import NodeClass

#: role of the break after a machine; the pressure model reads it as "the level rises here"
DISCHARGE_BREAK_ROLE = "discharge_spec_break"


def heavier_spec(style: LineStyle) -> LineStyle:
    """`style` in the next heavier piping class (`LINE_SPECS` is in rating order)."""
    # rule PRS-SPEC-CLASS: the heavier class is on the higher-level side (ADR-0065 F8c)
    index = LINE_SPECS.index(style.spec)
    if index + 1 >= len(LINE_SPECS):
        raise ValueError(
            f"expected a piping class below {LINE_SPECS[-1]} to step up from, got {style.spec!r}"
        )
    return style.model_copy(update={"spec": LINE_SPECS[index + 1]})


def break_after_machine(
    ctx: TrimContext,
    style: LineStyle,
    machine_id: str,
    nozzle_parts: tuple[LineItemSpec, ...] = (),
) -> tuple[TrimPlan, str]:
    """The short line `machine -> nozzle parts -> PropertyBreak`, and the break's node id.

    The caller starts the discharge line at that id, in `heavier_spec(style)`. The stub line
    comes first in the returned plan, so a backend adds it before the line that starts at it.
    """
    # rule TOG82-SPEC-BREAK: a spec break where a machine raises the level (Toghraei 2019 p.82)
    draft = TrimDraft(ctx, style)
    spec_change = draft.part(NodeClass.PROPERTY_BREAK.value, DISCHARGE_BREAK_ROLE)
    draft.line(machine_id, [*nozzle_parts, spec_change], None, StreamKindV2.PROCESS, style)
    return draft.finish(), spec_change.node_id
