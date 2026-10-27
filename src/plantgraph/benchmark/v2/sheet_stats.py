"""What each planned sheet holds: the measurement behind the sheet bands (design realism 12.1).

Measured on the plan, before the splitter: how many equipment, valves, instruments and symbols each
sheet has, and how many **off-page stubs**. A stub (pid-vocabulary 13.8 Q7 A) is a pipe end that
leaves the drawing: a line end that is open (a utility stub, a relief line to the flare, an open gas
outlet, an unwired port) or a line that crosses to another sheet. A vent or drain closed by a blind
flange or a funnel, and an atmospheric vent, are not stubs. Signal lines that cross sheets are
counted apart (`signal_cuts`): the design reports them with no band.

The counting rule itself is in `symbols.py`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.symbols import SymbolKind, plan_node_classes, symbol_kind
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.graph.schema import NodeClass, Relation

#: parts that close a line end without leaving the drawing
CLOSED_END_CLASSES: frozenset[str] = frozenset(
    {NodeClass.BLIND_FLANGE.value, NodeClass.FUNNEL.value, NodeClass.VENTILATION_DEVICE.value}
)
_SIGNAL_RELATIONS = frozenset({Relation.MEASURED_BY, Relation.SEND_SIGNAL_TO, Relation.CONTROL})


class SheetStats(BaseModel):
    """The composition of one sheet."""

    model_config = ConfigDict(frozen=True)

    sheet_group: str  # `3:1`
    equipment: int
    valves: int
    fittings: int  # fittings and primary elements, junctions excluded
    instruments: int  # sensors and bubbles
    symbols: int  # equipment + valves + fittings + instruments, without stubs
    stubs: int  # off-page stubs: open ends that are not closed, plus crossings
    crossings: int  # the part of `stubs` that is a line passing to or from another sheet
    signal_cuts: int


def sheet_stats(plan: PlantPlanV2) -> list[SheetStats]:
    """The stats of every sheet of the plant, in unit order then sheet order."""
    sheet_of = {node: sheet for unit in plan.units for node, sheet in unit.sheets.sheet_of.items()}
    classes: dict[str, str] = {}
    open_ends: Counter[str] = Counter()
    crossings: Counter[str] = Counter()
    signal_cuts: Counter[str] = Counter()
    for unit in plan.units:
        unit_plan = unit.instance.plan
        classes.update(plan_node_classes(unit_plan))
        for line in unit_plan.lines:
            open_ends.update(_open_end_stubs(line, sheet_of, classes))
            crossings.update(_crossing_stubs(line, sheet_of))
        signal_cuts.update(_signal_cuts(unit_plan, sheet_of))
    counts = _kind_counts(sheet_of, classes)
    return [
        _stats_of(
            sheet,
            counts[sheet],
            open_ends[sheet] + crossings[sheet],
            crossings[sheet],
            signal_cuts[sheet],
        )
        for sheet in _sheets_in_order(sheet_of.values())
    ]


def _sheets_in_order(sheets: Iterable[str]) -> list[str]:
    """`2:1`, `2:2`, `10:1`: by unit number, then sheet number (not as text)."""
    unique = set(sheets)
    return sorted(unique, key=lambda sheet: tuple(int(part) for part in sheet.split(":")))


def _kind_counts(
    sheet_of: Mapping[str, str], classes: Mapping[str, str]
) -> dict[str, Counter[SymbolKind]]:
    counts: dict[str, Counter[SymbolKind]] = {}
    for node_id, sheet in sheet_of.items():
        counts.setdefault(sheet, Counter())[symbol_kind(classes[node_id])] += 1
    return counts


def _stats_of(
    sheet: str, kinds: Counter[SymbolKind], stubs: int, crossings: int, signal_cuts: int
) -> SheetStats:
    fittings = kinds[SymbolKind.FITTING] + kinds[SymbolKind.PRIMARY_ELEMENT]
    drawn = kinds[SymbolKind.EQUIPMENT] + kinds[SymbolKind.VALVE] + fittings
    return SheetStats(
        sheet_group=sheet,
        equipment=kinds[SymbolKind.EQUIPMENT],
        valves=kinds[SymbolKind.VALVE],
        fittings=fittings,
        instruments=kinds[SymbolKind.INSTRUMENT],
        symbols=drawn + kinds[SymbolKind.INSTRUMENT] + stubs,
        stubs=stubs,
        crossings=crossings,
        signal_cuts=signal_cuts,
    )


# ---- stubs ---------------------------------------------------------------------------------------


def _chain(line: LineSpec) -> list[str]:
    """The nodes a line joins, in flow order (open ends left out)."""
    nodes = [line.src_id, *(item.node_id for item in line.items), line.dst_id]
    return [node for node in nodes if node is not None]


def _open_end_stubs(
    line: LineSpec, sheet_of: Mapping[str, str], classes: Mapping[str, str]
) -> list[str]:
    chain = _chain(line)
    stubs = []
    if line.src_id is None and classes[chain[0]] not in CLOSED_END_CLASSES:
        stubs.append(sheet_of[chain[0]])
    if line.dst_id is None and classes[chain[-1]] not in CLOSED_END_CLASSES:
        stubs.append(sheet_of[chain[-1]])
    return stubs


def _crossing_stubs(line: LineSpec, sheet_of: Mapping[str, str]) -> list[str]:
    """One stub on each side where the line passes from one sheet to another."""
    chain = _chain(line)
    stubs: list[str] = []
    for upstream, downstream in zip(chain, chain[1:], strict=False):
        if sheet_of[upstream] != sheet_of[downstream]:
            stubs += [sheet_of[upstream], sheet_of[downstream]]
    return stubs


def _signal_cuts(plan: TrimPlan, sheet_of: Mapping[str, str]) -> list[str]:
    cuts: list[str] = []
    for link in plan.links:
        crossing = link.relation in _SIGNAL_RELATIONS
        if crossing and sheet_of[link.source_id] != sheet_of[link.target_id]:
            cuts += [sheet_of[link.source_id], sheet_of[link.target_id]]
    return cuts


# ---- summary -------------------------------------------------------------------------------------


class Spread(BaseModel):
    """Mean, minimum and maximum of one per-sheet quantity."""

    model_config = ConfigDict(frozen=True)

    mean: float
    low: int
    high: int


def spread(values: Sequence[int]) -> Spread:
    """The mean and range of `values` (at least one)."""
    if not values:
        raise ValueError("expected at least one sheet, got none")
    return Spread(mean=sum(values) / len(values), low=min(values), high=max(values))


def share_at_most(values: Sequence[int], limit: int) -> float:
    """The fraction of `values` that is at most `limit`."""
    return sum(value <= limit for value in values) / len(values)
