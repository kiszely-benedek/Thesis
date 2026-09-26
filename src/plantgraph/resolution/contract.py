"""Checking the resolver-boundary contract — the gate on `localize()`'s output.

`check_contract` looks for every leak that `localize.py` was supposed to seal off
(design §4.1): raw splitter output always fails this check, `localize()`'s
output never does. `resolve()` (T4) calls this first, so a forgotten
`localize()` call fails immediately with a clear error, instead of silently
leaking the answer key further downstream.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema


def check_contract(sheets: Sequence[SheetGraph]) -> None:
    """Fail if any sheet violates the resolver-boundary contract.

    Raises:
        ValueError: naming the offending sheet and node/edge, if
            - a node id occurs on more than one sheet (L1),
            - a node or edge carries a property outside the V-whitelist
              (L2/L6),
            - a sheet's `connectors` list is non-empty (L2),
            - a `sheet_id` is duplicated or contains ':'.
    """
    _check_sheet_ids(sheets)
    for sheet in sheets:
        _check_no_connectors(sheet)
        _check_node_properties(sheet)
        _check_edge_properties(sheet)
    _check_node_ids_unique_across_sheets(sheets)


def _check_sheet_ids(sheets: Sequence[SheetGraph]) -> None:
    """':' is the local-key separator (`localize.py`) — a sheet_id must never contain it."""
    seen: set[str] = set()
    for sheet in sheets:
        if ":" in sheet.sheet_id:
            raise ValueError(f"sheet_id {sheet.sheet_id!r} contains ':', the local-key separator")
        if sheet.sheet_id in seen:
            raise ValueError(f"duplicate sheet_id {sheet.sheet_id!r}")
        seen.add(sheet.sheet_id)


def _check_no_connectors(sheet: SheetGraph) -> None:
    """L2 leak: `OffPageConnector.partner_tag`/`partner_sheet_id` is the pairing answer key."""
    if sheet.connectors:
        raise ValueError(
            f"sheet {sheet.sheet_id!r} still carries {len(sheet.connectors)} OffPageConnector "
            "entries; localize() must empty this list before the resolver sees the sheet"
        )


def _check_node_properties(sheet: SheetGraph) -> None:
    for node_id, attrs in sheet.graph.nodes(data=True):
        extra = sorted(set(attrs) - schema.VISIBLE_NODE_PROPERTIES)
        if extra:
            raise ValueError(
                f"sheet {sheet.sheet_id!r} node {node_id!r} carries hidden properties {extra}; "
                "only VISIBLE_NODE_PROPERTIES may reach the resolver"
            )


def _check_edge_properties(sheet: SheetGraph) -> None:
    for source, target, attrs in sheet.graph.edges(data=True):
        extra = sorted(set(attrs) - schema.VISIBLE_EDGE_PROPERTIES)
        if extra:
            raise ValueError(
                f"sheet {sheet.sheet_id!r} edge {(source, target)!r} carries hidden properties "
                f"{extra}; only VISIBLE_EDGE_PROPERTIES may reach the resolver"
            )


def _check_node_ids_unique_across_sheets(sheets: Sequence[SheetGraph]) -> None:
    """L1 leak: the splitter gives a reference occurrence the same id as its home occurrence."""
    home_sheet_of: dict[str, str] = {}
    for sheet in sheets:
        for node_id in sheet.graph.nodes:
            home_sheet = home_sheet_of.get(node_id)
            if home_sheet is not None:
                raise ValueError(
                    f"node id {node_id!r} occurs on both sheet {home_sheet!r} and "
                    f"{sheet.sheet_id!r}; localize() must rename occurrences to close this leak"
                )
            home_sheet_of[node_id] = sheet.sheet_id
