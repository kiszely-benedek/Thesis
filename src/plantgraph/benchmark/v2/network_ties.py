"""The process side of the networks (v2.2, handbook on): tie-ins, sub-headers, drains (design 7).

Relief outlets, hydrocarbon drains, fuel-gas bleeds and utility stubs end open on a v2.1 sheet. Here
each of them is tied into a **sub-header**: one short local pipe per (process sheet, service) that
leaves the sheet through a single connector toward the network sheet. This is the usual "PSV
outlets join the unit flare sub-header" and it bounds the added stubs per sheet by the number of
services on it. The pass runs once, after the plant boundary is closed and before sheets are final,
and only *adds* lines, so every existing part keeps its id and tag. Two exceptions: a hydrocarbon
drain loses its cap (`_drain_to_closed_drain`) and a drain or bleed line is renumbered into the
network's service. It draws nothing: the sub-header layout follows from the tie-ins, and the new
numbers come from the unit's own counters.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from plantgraph.benchmark.v2.config import SheetKnobs
from plantgraph.benchmark.v2.config_v22 import NETWORK_SERVICES
from plantgraph.benchmark.v2.hidden_state import FluidClass, PressureLevel
from plantgraph.benchmark.v2.network_models import (
    FLUID_CLASS_OF_SERVICE,
    SERVICE_DIRECTION,
    Crossing,
    TieDirection,
)
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.plan_models import LineItemSpec, LineSpec, StreamKindV2
from plantgraph.benchmark.v2.pressure_levels import assign_levels_of_plans
from plantgraph.benchmark.v2.sheets import assign_unit_sheets
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimDraft, TrimPlan
from plantgraph.benchmark.v2.trims_extra import tee_part
from plantgraph.benchmark.v2.trims_utility import utility_style
from plantgraph.graph.schema import NodeClass

#: the line ends that relieve to the flare: a PSV outlet (with or without its outlet block)
_FLARE_END_ROLES = frozenset({"psv_outlet_block", "psv", "compressor_discharge_psv"})
_BLEED_ROLE = "dbb_bleed_valve"  # the bleed of a fuel-gas double block and bleed: hydrocarbon
_DRAIN_CAP_ROLE = re.compile(r"_drain_(cap|open_drain)$")
_UTILITY_RETURNS = frozenset({"CWR", "CD"})  # stubs that end open and flow out of the process
_SERVICE_FIELD = 1  # `size-service-number-spec-insulation`

_HEADER_SIZE, _SUB_HEADER_SIZE, _TIE_IN_SIZE = 6, 4, 2


@dataclass(frozen=True)
class _Tie:
    """One open line end that belongs on a network: the part to tie to, and the service."""

    service: str
    node_id: str


def add_network_ties(
    instances: Sequence[PatternInstance],
    trims: Sequence[TrimContext],
    train_nos: Sequence[int],
    services: Sequence[str],
    sheets: SheetKnobs,
) -> tuple[list[PatternInstance], list[Crossing]]:
    """Every instance with its network tie-ins and sub-headers, and the crossings to the networks.

    `trims[i]` is the trim context unit `i` was built with (its numbering continues); `services`
    are the networks that exist (`HandbookKnobs.network_services`).
    """
    tied: list[PatternInstance] = []
    crossings: list[Crossing] = []
    levels = assign_levels_of_plans([instance.plan for instance in instances])
    for instance, trim, train_no in zip(instances, trims, train_nos, strict=True):
        unit_no = trim.unit_no
        grounded = _with_open_ends_routed(instance, services, levels)
        new_instance, found = _tie_unit(grounded, trim, unit_no, train_no, services, sheets)
        tied.append(new_instance)
        crossings += found
    return tied, crossings


# ---- drains (TOG141) ----------------------------------------------------------------------------


def _with_open_ends_routed(
    instance: PatternInstance, services: Sequence[str], levels: Mapping[str, PressureLevel]
) -> PatternInstance:
    """Every drain ends where its fluid class says, and a fuel-gas bleed becomes a flare line.

    A hydrocarbon drain goes to the closed drain, unless it drains a vacuum line: nothing can flow
    from vacuum into an atmospheric header, so that one stays capped (a declared maintenance end).
    """
    # rule TOG141-DRAIN-DESTINATION: hydrocarbon drains go to the closed drain (Toghraei 2019 p.141)
    plan = instance.plan
    lines = list(plan.lines)
    roles = dict(plan.roles)
    kinds = dict(plan.stream_kinds)
    for index, line in enumerate(lines):
        if _is_fuel_gas_bleed(line, plan):
            if "FL" in services:
                lines[index] = _retargeted(line, "FL", kinds)
        elif not _is_capped_drain(line, plan):
            continue
        elif FLUID_CLASS_OF_SERVICE[line.fluid_code] is not FluidClass.HYDROCARBON:
            lines[index] = _drain_to_open_drain(line, roles)
        elif "CHD" in services and levels[line.line_number] > PressureLevel.VAC:
            lines[index] = _drain_to_closed_drain(line, roles, kinds)
    routed = plan.model_copy(update={"lines": tuple(lines), "roles": roles, "stream_kinds": kinds})
    return instance.model_copy(update={"plan": routed})


def _is_fuel_gas_bleed(line: LineSpec, plan: TrimPlan) -> bool:
    """The bleed line of a fuel-gas double block and bleed: one open valve (hydrocarbon)."""
    return (
        line.dst_id is None
        and bool(line.items)
        and plan.roles.get(line.items[-1].node_id) == _BLEED_ROLE
        and line.fluid_code != "FL"
    )


def _is_capped_drain(line: LineSpec, plan: TrimPlan) -> bool:
    if line.dst_id is not None or not line.items:
        return False
    return bool(_DRAIN_CAP_ROLE.search(plan.roles.get(line.items[-1].node_id, "")))


def _drain_to_closed_drain(
    line: LineSpec, roles: dict[str, str], kinds: dict[str, StreamKindV2]
) -> LineSpec:
    """The drain without its cap or funnel, now a line of the closed drain (service `CHD`)."""
    roles.pop(line.items[-1].node_id)  # the cap is gone, so its role goes with it
    shortened = line.model_copy(update={"items": line.items[:-1]})
    return _retargeted(shortened, "CHD", kinds)


def _retargeted(line: LineSpec, service: str, kinds: dict[str, StreamKindV2]) -> LineSpec:
    """The line renumbered into `service`: it now carries the header's fluid at the header's level.

    Without the new number the level would drop in the middle of a pipe class (a spec break is
    where it may), so the whole branch from the tee or vessel belongs to the network.
    """
    number = _with_service(line.line_number, service)
    kinds[number] = kinds.pop(line.line_number)
    return line.model_copy(update={"line_number": number, "fluid_code": service})


def _drain_to_open_drain(line: LineSpec, roles: dict[str, str]) -> LineSpec:
    """A water or steam drain is innocent: it ends in a funnel over an open drain."""
    cap = line.items[-1]
    if cap.node_class == NodeClass.FUNNEL.value:
        return line
    funnel = cap.model_copy(update={"node_class": NodeClass.FUNNEL.value})
    roles[cap.node_id] = roles[cap.node_id].replace("_cap", "_open_drain")
    return line.model_copy(update={"items": (*line.items[:-1], funnel)})


def _with_service(line_number: str, service: str) -> str:
    """`6-P-120017-A1A-N` with its service field replaced."""
    fields = line_number.split("-")
    fields[_SERVICE_FIELD] = service
    return "-".join(fields)


# ---- finding the ties ---------------------------------------------------------------------------


def _find_ties(instance: PatternInstance, services: Sequence[str]) -> list[_Tie]:
    """The open ends that belong on a network, in plan order."""
    plan = instance.plan
    ties: list[_Tie] = []
    for line in plan.lines:
        tie = _tie_of(line, plan)
        if tie is not None and tie.service in services:
            ties.append(tie)
    return ties


def _tie_of(line: LineSpec, plan: TrimPlan) -> _Tie | None:
    if not line.items:
        return None
    kind = plan.stream_kinds.get(line.line_number)
    first, last = line.items[0], line.items[-1]
    if kind is StreamKindV2.UTILITY_STUB:
        return _utility_tie(line, first, last)
    if line.dst_id is not None:
        return None
    role = plan.roles.get(last.node_id, "")
    if line.fluid_code == "CHD":  # a drain `_drain_to_closed_drain` routed
        return _Tie("CHD", last.node_id)
    if role == _BLEED_ROLE and line.fluid_code == "FL":  # hydrocarbon: never open to the air
        return _Tie("FL", last.node_id)
    if role in _FLARE_END_ROLES and line.fluid_code == "FL":
        return _Tie("FL", last.node_id)
    return None


def _utility_tie(line: LineSpec, first: LineItemSpec, last: LineItemSpec) -> _Tie | None:
    """A utility stub ends open on one side only: the supply at its start, the return at its end."""
    # rule TOG360-UTILITY-NETWORKS: a utility stub joins its header (Toghraei 2019 p.360)
    if line.src_id is None and SERVICE_DIRECTION.get(line.fluid_code) is TieDirection.DISTRIBUTION:
        return _Tie(line.fluid_code, first.node_id)
    if line.dst_id is None and line.fluid_code in _UTILITY_RETURNS:
        return _Tie(line.fluid_code, last.node_id)
    return None


# ---- one unit -----------------------------------------------------------------------------------


def _tie_unit(
    instance: PatternInstance,
    trim: TrimContext,
    unit_no: int,
    train_no: int,
    services: Sequence[str],
    sheets: SheetKnobs,
) -> tuple[PatternInstance, list[Crossing]]:
    ties = _find_ties(instance, services)
    if not ties:
        return instance, []
    # the sheet of every part is known before the sub-headers exist: they add no symbol
    sheet_of = assign_unit_sheets(unit_no, instance, sheets).sheet_of
    by_group: dict[tuple[str, str], list[str]] = defaultdict(list)
    for tie in ties:
        by_group[(sheet_of[tie.node_id], tie.service)].append(tie.node_id)
    added: list[TrimPlan] = []
    crossings: list[Crossing] = []
    for (sheet, service), nodes in sorted(by_group.items(), key=_group_order):
        plan, feeder_node = _sub_header(trim, service, nodes)
        added.append(plan)
        crossings.append(Crossing(
            train_no=train_no, unit_no=unit_no, sheet=sheet, service=service, node_id=feeder_node
        ))  # fmt: skip
    return _with_added_plans(instance, added), crossings


def _group_order(item: tuple[tuple[str, str], list[str]]) -> tuple[tuple[int, ...], int]:
    (sheet, service), _ = item
    return tuple(int(part) for part in sheet.split(":")), NETWORK_SERVICES.index(service)


def _with_added_plans(instance: PatternInstance, added: list[TrimPlan]) -> PatternInstance:
    plan = instance.plan
    lines = (*plan.lines, *(line for part in added for line in part.lines))
    roles = {**plan.roles, **{n: r for part in added for n, r in part.roles.items()}}
    kinds = {**plan.stream_kinds, **{n: k for part in added for n, k in part.stream_kinds.items()}}
    merged = plan.model_copy(update={"lines": lines, "roles": roles, "stream_kinds": kinds})
    return instance.model_copy(update={"plan": merged})


# ---- the sub-header -----------------------------------------------------------------------------


def _sub_header(trim: TrimContext, service: str, nodes: list[str]) -> tuple[TrimPlan, str]:
    """The local sub-header of one (sheet, service) and the part its connector line attaches to.

    One tie-in needs no header. With several, a sub-header pipe carries one tee per extra tie-in
    and each tie-in runs into its tee through a short branch (a collection one flows into the
    header, a distribution one flows out of it).
    """
    # rule TOG32-NETWORK-SHEETS: one sub-header, one connector per service per sheet (TOG p.32–34)
    kind = _stream_kind(service)
    style = utility_style(LineStyle(size=_SUB_HEADER_SIZE), service)
    draft = TrimDraft(trim, style)
    if len(nodes) == 1:
        return draft.finish(), nodes[0]
    branch = style.branch(size=_TIE_IN_SIZE)
    tees = [tee_part(draft, "sub_header_tee") for _ in nodes[1:]]
    if SERVICE_DIRECTION[service] is TieDirection.COLLECTION:
        draft.line(nodes[0], list(tees), None, kind, style)
        for node, tee in zip(nodes[1:], tees, strict=True):
            draft.line(node, [], tee.node_id, kind, branch)
        return draft.finish(), tees[-1].node_id
    draft.line(None, list(tees), nodes[-1], kind, style)
    for tee, node in zip(tees, nodes[:-1], strict=True):
        draft.line(tee.node_id, [], node, kind, branch)
    return draft.finish(), tees[0].node_id


def _stream_kind(service: str) -> StreamKindV2:
    utility = service not in ("FL", "CHD")
    return StreamKindV2.UTILITY_STUB if utility else StreamKindV2.TRIM


def tie_in_counts(crossings: Sequence[Crossing]) -> dict[str, int]:
    """Crossings per service, for reports."""
    counts: dict[str, int] = defaultdict(int)
    for crossing in crossings:
        counts[crossing.service] += 1
    return dict(counts)
