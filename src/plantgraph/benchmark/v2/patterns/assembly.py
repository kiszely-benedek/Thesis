"""Small helpers the patterns share to put plans together.

A trim returns a `TrimPlan`; a pattern joins many of them. The rule that matters is the order of
`TrimPlan.lines`: a branch line may start at a tee of an earlier line, so a pattern closes each
main line (`close_run`) before it combines the plans whose branches hang on it.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, LineSpec, StreamKindV2
from plantgraph.benchmark.v2.trim_context import LineStyle
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan, main_line
from plantgraph.benchmark.v2.trims_extra import pressure_tap, tee_part, temperature_tap
from plantgraph.benchmark.v2.vocabulary import SpareNaming, spare_members


def equipment_plan(ctx: PatternContext, node_class: str, type_code: str, role: str) -> TrimPlan:
    """A plan holding one new piece of equipment (port `equipment`); no lines, no motor."""
    draft = TrimDraft(ctx.trim, ctx.style)
    spec = draft.equipment(node_class, type_code, role)
    return draft.finish(equipment=spec)


def spared_set(
    ctx: PatternContext, node_class: str, type_code: str, count: int, has_motor: bool = False
) -> list[EquipmentSpec]:
    """`count` identical machines of one installed set (A/B/C), numbered after the train's style.

    With the suffix style the set shares one number and the tags end in `A`, `B`, `C`
    (`P-1203A`); with the consecutive style each machine takes the next number (`P-1203`,
    `P-1204`). A single machine has a plain number under both.
    """
    numbering = ctx.trim.numbering
    naming = ctx.trim.conventions.spare_naming
    shared = numbering.equipment_tag(type_code) if naming is SpareNaming.SUFFIX else None
    machines = []
    for member in spare_members(naming, count):
        tag = shared + (member.train or "") if shared else numbering.equipment_tag(type_code)
        machines.append(
            EquipmentSpec(
                node_id=numbering.node_id(),
                node_class=node_class,
                unit_no=ctx.unit_no,
                tag=tag,
                has_motor=has_motor,
            )
        )
    return machines


def part_plan(ctx: PatternContext, node_class: str, role: str) -> TrimPlan:
    """A plan whose open `run` is one new inline part of `node_class` (port `part`)."""
    draft = TrimDraft(ctx.trim, ctx.style)
    part = draft.part(node_class, role)
    return draft.finish(run=(part,), part=part)


def tee_plan(ctx: PatternContext, role: str) -> TrimPlan:
    """A plan whose open `run` is one new `PipeTee` (port `tee`)."""
    draft = TrimDraft(ctx.trim, ctx.style)
    tee = tee_part(draft, role)
    return draft.finish(run=(tee,), tee=tee)


def local_gauge(ctx: PatternContext, letters: str, location_id: str, role: str) -> TrimPlan:
    """A local gauge `letters` (`TI`, `LG`) on `location_id`: one sensor, its own loop."""
    draft = TrimDraft(ctx.trim, ctx.style)
    draft.local_indicator(letters, location_id, role)
    return draft.finish()


def thermometer_tap(ctx: PatternContext, tee_id: str, role: str) -> TrimPlan:
    """A local `TI` on a branch from the tee `tee_id`, which must already be on a written line."""
    draft = TrimDraft(ctx.trim, ctx.style)
    temperature_tap(draft, tee_id, role)
    return draft.finish()


def pressure_gauge_tap(ctx: PatternContext, tee_id: str, role: str) -> TrimPlan:
    """A local `PI` on a branch from the tee `tee_id`: root valve, blind flange, gauge."""
    draft = TrimDraft(ctx.trim, ctx.style)
    pressure_tap(draft, tee_id, role)
    return draft.finish()


def close_run(
    ctx: PatternContext,
    plan: TrimPlan,
    src_id: str | None,
    dst_id: str | None,
    kind: StreamKindV2 = StreamKindV2.PROCESS,
    style: LineStyle | None = None,
) -> TrimPlan:
    """Put the plan's `run` into one main line `src_id -> run -> dst_id` and record its stream kind.

    The main line comes first in the plan's lines, ahead of the branches that start at its tees.
    """
    line = main_line(ctx.trim, style or ctx.style, src_id, plan.run, dst_id)
    closed = plan.with_main_line(line)
    kinds = {**closed.stream_kinds, **{number: kind for number in line.line_numbers}}
    return closed.model_copy(update={"stream_kinds": kinds})


def line_containing(plan: TrimPlan, node_id: str) -> LineSpec:
    """The one line of the plan that has `node_id` among its inline items."""
    found = [line for line in plan.lines if any(item.node_id == node_id for item in line.items)]
    if len(found) != 1:
        raise ValueError(f"expected one line with item {node_id!r}, found {len(found)}")
    return found[0]


def line_between(plan: TrimPlan, src_id: str | None, dst_id: str | None) -> LineSpec:
    """The one line of the plan that runs exactly `src_id` to `dst_id` (None is an open end)."""
    found = [line for line in plan.lines if line.src_id == src_id and line.dst_id == dst_id]
    if len(found) != 1:
        raise ValueError(f"expected one line {src_id!r} -> {dst_id!r}, found {len(found)}")
    return found[0]


def quiet(plan: TrimPlan) -> TrimPlan:
    """The plan without its ports: a sub-plan whose ports the pattern does not publish."""
    return plan.model_copy(update={"ports": {}})


def with_stream_kinds(plan: TrimPlan) -> TrimPlan:
    """The plan with `process` recorded for every line that has no stream kind yet.

    Trims record the kind of the branches they add (`trim`, `recycle`, `utility_stub`); the main
    lines they close have none, and a main line inside a pattern is a `process` stream.
    """
    kinds = dict(plan.stream_kinds)
    for line in plan.lines:
        for number in line.line_numbers:
            kinds.setdefault(number, StreamKindV2.PROCESS)
    return plan.model_copy(update={"stream_kinds": kinds})
