"""A resolver-határ szerződésének ellenőrzése — a `localize()` kimenetének kapuja.

`check_contract` mindazokat a szivárgásokat keresi, amelyeket `localize.py`-nak
zárnia kellett (design §4.1): nyers splitter-kimenet ezen mindig elbukik, a
`localize()` kimenete sosem. A `resolve()` (T4) ezt hívja először, hogy egy
elfelejtett `localize()` hívás azonnal, beszédes hibával bukjon el, ne csendben
szivárogtassa tovább a válaszkulcsot.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema


def check_contract(sheets: Sequence[SheetGraph]) -> None:
    """Elbukik, ha a lapok bármelyike a resolver-határ szerződését sérti.

    Raises:
        ValueError: a sértő lapot és csomópontot/élt megnevezve, ha
            - egy csomópont-id egynél több lapon fordul elő (L1),
            - egy csomópont vagy él a V-fehérlistán kívüli tulajdonságot hordoz
              (L2/L6),
            - egy lap `connectors` listája nem üres (L2),
            - egy `sheet_id` duplikált vagy ':'-t tartalmaz.
    """
    _check_sheet_ids(sheets)
    for sheet in sheets:
        _check_no_connectors(sheet)
        _check_node_properties(sheet)
        _check_edge_properties(sheet)
    _check_node_ids_unique_across_sheets(sheets)


def _check_sheet_ids(sheets: Sequence[SheetGraph]) -> None:
    """A ':' a local-key elválasztója (`localize.py`) — egy sheet_id sosem tartalmazhatja."""
    seen: set[str] = set()
    for sheet in sheets:
        if ":" in sheet.sheet_id:
            raise ValueError(f"sheet_id {sheet.sheet_id!r} contains ':', the local-key separator")
        if sheet.sheet_id in seen:
            raise ValueError(f"duplicate sheet_id {sheet.sheet_id!r}")
        seen.add(sheet.sheet_id)


def _check_no_connectors(sheet: SheetGraph) -> None:
    """L2 szivárgás: `OffPageConnector.partner_tag`/`partner_sheet_id` a párosítás válaszkulcsa."""
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
    """L1 szivárgás: a splitter egy reference-előfordulásnak a home-éval azonos id-t ad."""
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
