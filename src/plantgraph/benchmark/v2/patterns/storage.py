"""U4, the tank farm with transfer pumps (design realism 7.2; pid-vocabulary 13.3).

A **tank farm** is a group of storage tanks with the pumps that move their contents on. Product
arrives by one or two receipt lines, a manifold (a header with branch valves) leads it to the
tanks, and the transfer pumps draw from all of them through a common suction header. Protection:
each tank's receipt line has an on-off valve that shuts on high level (overfill trip) and one that
an operator can close from the control room; a flow controller sets the transfer rate.

Variants drawn here, one deck each (`variants.PATTERN_DECKS`): tank count 2-4, transfer pump class,
metering element (or none), manifold valve class and whether the contents are flammable. Receipt
line count is a uniform draw of 1 or 2, raised to the number of product streams the farm has to
take (`PatternContext.waiting_streams`, v2.1): a column's distillate and side draw end in a tank
farm. The pump set draws its own variants.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.instrument_draft import nodes_with_role
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    equipment_plan,
    line_between,
    part_plan,
    quiet,
    tee_plan,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    Port,
    PortDirection,
    open_end_port,
)
from plantgraph.benchmark.v2.patterns.pump_set import build_pump_set
from plantgraph.benchmark.v2.patterns.storage_parts import (
    tank_fittings,
    tank_inlet_chain,
    transfer_header,
)
from plantgraph.benchmark.v2.patterns.variants import variant_label
from plantgraph.benchmark.v2.trim_plan import TrimPlan, combine
from plantgraph.benchmark.v2.trims_valves import battery_limit
from plantgraph.graph.schema import NodeClass

PATTERN_ID = "U4"
SYSTEM_CODE = "TKF"
_TANKS_PER_GROUP = 2  # FB&D: "tanks 1 to 2" per drawing
_MAX_RECEIPT_LINES = 2  # the drawn count; a farm with more product streams waiting has more
_MERGE_ROLE = "receipt_merge_tee"


class _Choices(BaseModel):
    """What one tank farm instance drew from its decks."""

    model_config = ConfigDict(frozen=True)

    tank_count: int
    pump_class: str
    metering: str
    manifold_class: str
    flammable: bool
    receipts: int

    @property
    def label(self) -> str:
        """The choices as the answer key's variant text."""
        return variant_label(
            tanks=self.tank_count,
            transfer_pump=self.pump_class,
            metering=self.metering,
            manifold=self.manifold_class,
            service="flammable" if self.flammable else "non_flammable",
            receipts=self.receipts,
        )


def _draw_choices(ctx: PatternContext) -> _Choices:
    return _Choices(
        tank_count=int(ctx.deal("U4.tank_count")),
        pump_class=ctx.deal("U4.transfer_pump"),
        metering=ctx.deal("U4.metering"),
        manifold_class=ctx.deal("U4.manifold"),
        flammable=ctx.deal("U4.tank_service") == "flammable",
        # the draw is made first and always, so the unit's stream does not depend on the wiring
        receipts=max(ctx.trim.rng.randint(1, _MAX_RECEIPT_LINES), ctx.waiting_streams),
    )


def build_tank_farm(ctx: PatternContext) -> PatternInstance:
    """Tanks, receipt manifold, transfer pump set; ports `receipt1`, [`receipt2`], `transfer`."""
    choices = _draw_choices(ctx)
    tank_plans = [
        equipment_plan(ctx, NodeClass.TANK.value, "TK", "tank") for _ in range(choices.tank_count)
    ]
    tanks = [plan.ports["equipment"] for plan in tank_plans]
    inlets = _inlet_network(ctx, tanks, choices)
    pumps = build_pump_set(
        ctx,
        tanks[-1],  # the pumps draw from the last tank; the others feed the suction header
        choices.pump_class,
        "transfer_pump",
        header=transfer_header(ctx, choices.metering),
        feed_count=len(tanks) - 1,
    )
    viscous = choices.pump_class == NodeClass.ROTARY_PUMP.value
    fittings = [tank_fittings(ctx, tank, choices.flammable, viscous) for tank in tanks]
    outlets = _outlet_lines(ctx, tanks[:-1], pumps.feed_tee_ids, choices.manifold_class)
    parts = [*tank_plans, inlets, pumps.plan, outlets, *fittings]
    plan = with_stream_kinds(combine(*(quiet(part) for part in parts)))
    groups = _drawing_groups(tanks, pumps.pump_ids, pumps.own_sheet)
    return PatternInstance(
        pattern=PATTERN_ID,
        system_code=SYSTEM_CODE,
        variant=f"{choices.label}|{pumps.variant}",
        plan=plan,
        ports=(
            *_receipt_ports(plan, tanks, choices),
            pumps.discharge.model_copy(update={"name": "transfer"}),
        ),
        drawing_group_of=groups.group_of,
        pinned_groups=groups.pinned,
    )


def _inlet_network(ctx: PatternContext, tanks: list[str], choices: _Choices) -> TrimPlan:
    """Receipt line(s), manifold valve(s), a tee per tank but the last, and each tank's chain.

    The first receipt line runs on as the header and ends in the last tank's chain; every further
    one joins it at a merge tee of its own. Branch lines from the header tees lead to the others.
    """
    chains = [tank_inlet_chain(ctx, tank, choices.manifold_class) for tank in tanks]
    first_valve = part_plan(ctx, choices.manifold_class, "receipt_manifold_valve")
    merges = [tee_plan(ctx, _MERGE_ROLE) for _ in range(choices.receipts - 1)]
    branch_tees = [tee_plan(ctx, "tank_branch_tee") for _ in tanks[:-1]]
    header_run = combine(
        quiet(battery_limit(ctx.trim, ctx.style)),
        quiet(first_valve),
        *(quiet(merge) for merge in merges),
        *(quiet(tee) for tee in branch_tees),
        chains[-1],
    )
    parts = [close_run(ctx, header_run, None, tanks[-1])]
    for tee, chain, tank in zip(branch_tees, chains, tanks, strict=False):
        parts.append(close_run(ctx, chain, tee.ports["tee"], tank))
    for merge in merges:
        extra_valve = part_plan(ctx, choices.manifold_class, "receipt_manifold_valve")
        parts.append(quiet(close_run(ctx, extra_valve, None, merge.ports["tee"])))
    return combine(*parts)


def _outlet_lines(
    ctx: PatternContext, tanks: list[str], feed_tee_ids: tuple[str, ...], manifold_class: str
) -> TrimPlan:
    """Each tank except the last: its outlet valve and a line to a feed tee of the pump suction."""
    lines = [
        close_run(ctx, part_plan(ctx, manifold_class, "tank_outlet_block"), tank, tee_id)
        for tank, tee_id in zip(tanks, feed_tee_ids, strict=True)
    ]
    return combine(*(quiet(line) for line in lines))


def _receipt_ports(plan: TrimPlan, tanks: list[str], choices: _Choices) -> list[Port]:
    """One in-port per receipt line; each further line ends at a merge tee of the first.

    Every receipt takes a product stream of its train when the grammar finds one (`collects`).
    """
    first = line_between(plan, None, tanks[-1])
    lines = [first, *(line_between(plan, None, tee) for tee in nodes_with_role(plan, _MERGE_ROLE))]
    return [
        open_end_port(f"receipt{number}", PortDirection.IN, Phase.LIQUID, line, collects=True)
        for number, line in enumerate(lines, start=1)
    ]


def _drawing_groups(tanks: list[str], pump_ids: tuple[str, ...], own_sheet: bool) -> DrawingGroups:
    """Two tanks per group; the pumps join the group of the last tank, or a sheet of their own."""
    groups = DrawingGroups()
    for index, tank in enumerate(tanks):
        groups.put([tank], f"G{index // _TANKS_PER_GROUP + 1}")
    last = (len(tanks) - 1) // _TANKS_PER_GROUP + 1
    groups.put(pump_ids, f"G{last + 1}" if own_sheet else f"G{last}", pinned=own_sheet)
    return groups
