"""The corpus half of the composition report: what the sheet graphs show (design vocabulary 14.3).

The report states every band on the **plan** (the planner's own count, `sheet_stats`), because
pyDEXPI's graph keeps no node for an open pipe end and the plan does not depend on the duplication
rate. Two things only exist on the graphs the system reads, and are measured here:

- the share of instruments that touch exactly one other node (degree 1);
- whether one unit shows per sheet.

A third check ties the two counts together. With **duplication 0** every sheet graph must equal the
plan exactly: its drawn symbols (connectors excluded) are the plan's symbols without stubs, its pipe
connectors are the plan's crossings, its signal connectors are the plan's signal cuts. At the
preset's rate a quarter of the equipment is drawn again as a **reference copy** on a neighbouring
sheet (ADR-0028); the two deltas that causes are reported, with no band.

Pure functions over sheet graphs: `split_sheets` is the only one that runs the splitter.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

import networkx as nx

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.splitter import split
from plantgraph.benchmark.v2.sheet_stats import SheetStats
from plantgraph.benchmark.v2.symbols import SymbolKind, is_symbol, symbol_kind
from plantgraph.graph.schema import NodeClass
from plantgraph.ingest.headline_v2 import HeadlinePresetV2

_PIPE_CONNECTORS = frozenset(
    {
        NodeClass.FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR.value,
        NodeClass.FLOW_IN_PIPE_OFF_PAGE_CONNECTOR.value,
    }
)
_SIGNAL_CONNECTORS = frozenset(
    {
        NodeClass.FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR.value,
        NodeClass.FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR.value,
    }
)


def split_sheets(
    plant: nx.DiGraph[str], preset: HeadlinePresetV2, seed: int, duplication_rate: float
) -> list[SheetGraph]:
    """The sheet graphs of `plant` at `duplication_rate`, in drawing order."""
    at_rate = HeadlinePresetV2(
        duplication_rate=duplication_rate,
        sheet_equipment_budget=preset.sheet_equipment_budget,
        connector_label_detail=preset.connector_label_detail,
        exact_match_tags=preset.exact_match_tags,
    )
    sheets, _manifest = split(plant, at_rate.split_config(seed))
    return sorted(sheets, key=lambda sheet: int(sheet.sheet_id))  # the splitter sorts as text


# ---- per-sheet counts ----------------------------------------------------------------------------


def _classes(sheet: SheetGraph) -> list[str]:
    return [str(data["node_class"]) for _, data in sheet.graph.nodes(data=True)]


def symbol_count(sheet: SheetGraph) -> int:
    """Drawn symbols on the sheet graph; connectors and junctions are not symbols."""
    return sum(is_symbol(node_class) for node_class in _classes(sheet))


def pipe_connector_count(sheet: SheetGraph) -> int:
    """Pipe off-page connectors on the sheet."""
    return sum(node_class in _PIPE_CONNECTORS for node_class in _classes(sheet))


def signal_connector_count(sheet: SheetGraph) -> int:
    """Signal off-page connectors on the sheet."""
    return sum(node_class in _SIGNAL_CONNECTORS for node_class in _classes(sheet))


def _units_on(sheet: SheetGraph) -> set[str]:
    """The units of the nodes that carry one (reference copies and connectors carry none)."""
    units = (data.get("unit_id") for _, data in sheet.graph.nodes(data=True))
    return {str(unit) for unit in units if unit is not None}


def instrument_degrees(sheets: Sequence[SheetGraph]) -> list[int]:
    """The degree (edges in and out) of every instrument node on every sheet graph."""
    return [
        sheet.graph.degree(node_id)
        for sheet in sheets
        for node_id, data in sheet.graph.nodes(data=True)
        if symbol_kind(str(data["node_class"])) is SymbolKind.INSTRUMENT
    ]


# ---- rows ----------------------------------------------------------------------------------------


def corpus_rows(
    stats: Sequence[SheetStats],
    exact: Sequence[SheetGraph],
    at_preset: Sequence[SheetGraph],
) -> list[tuple[str, float]]:
    """`(quantity, value)` of every corpus row; the caller attaches the bands (`CORPUS_BANDS`).

    `exact` are the sheet graphs at duplication 0, `at_preset` at the preset's rate.

    Raises:
        ValueError: if a split does not have one sheet graph per planned sheet.
    """
    _require_same_length(stats, exact, "duplication 0")
    _require_same_length(stats, at_preset, "the preset rate")
    degrees = instrument_degrees(at_preset)
    return [
        ("instruments with sheet-graph degree 1 (share)", _share(d == 1 for d in degrees)),
        (
            "sheets that show one unit (share)",
            _share(len(_units_on(sheet)) == 1 for sheet in at_preset),
        ),
        _exact_row(
            "corpus symbols = plan symbols",
            (stats, exact),
            symbol_count,
            lambda s: s.symbols - s.stubs,
        ),
        _exact_row(
            "pipe connectors = plan crossings",
            (stats, exact),
            pipe_connector_count,
            lambda s: s.crossings,
        ),
        _exact_row(
            "signal connectors = plan signal cuts",
            (stats, exact),
            signal_connector_count,
            lambda s: s.signal_cuts,
        ),
        (
            "preset duplication: reference copies added per sheet",
            _mean(
                symbol_count(g) - (s.symbols - s.stubs)
                for s, g in zip(stats, at_preset, strict=True)
            ),
        ),
        (
            "preset duplication: crossings absorbed per sheet",
            _mean(
                s.crossings - pipe_connector_count(g) for s, g in zip(stats, at_preset, strict=True)
            ),
        ),
    ]


def _exact_row(
    what: str,
    paired: tuple[Sequence[SheetStats], Sequence[SheetGraph]],
    on_graph: Callable[[SheetGraph], int],
    on_plan: Callable[[SheetStats], int],
) -> tuple[str, float]:
    """The share of sheets where the graph's count equals the plan's (duplication 0)."""
    stats, sheets = paired
    matches = (on_graph(g) == on_plan(s) for s, g in zip(stats, sheets, strict=True))
    return f"dup 0: sheets with {what} (share)", _share(matches)


def _require_same_length(
    stats: Sequence[SheetStats], sheets: Sequence[SheetGraph], what: str
) -> None:
    if len(stats) != len(sheets):
        raise ValueError(
            f"expected {len(stats)} sheet graphs ({what}: one per planned sheet), got {len(sheets)}"
        )


def _share(flags: Iterable[bool]) -> float:
    values = list(flags)
    return sum(values) / len(values)


def _mean(numbers: Iterable[int]) -> float:
    values = list(numbers)
    return sum(values) / len(values)
