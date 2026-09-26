"""`resolve()` — a vékony resolver belépési pontja: lapok -> egyesített üzemgráf (design §5.5).

Az egyetlen függvény, amit egy hívónak (Neo4j-betöltő, nem-Cypher stratégia,
gate) importálnia kell — a résztvevő lépések (`pairing`, `identity`, `merge`)
saját belső eszközök.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from plantgraph.benchmark.models import UnresolvedConnector
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.resolution.connector_labels import ConnectorLabel, read_connector_labels
from plantgraph.resolution.contract import check_contract
from plantgraph.resolution.identity import group_identities
from plantgraph.resolution.merge import build_plant_graph
from plantgraph.resolution.models import Resolution, ResolutionReport
from plantgraph.resolution.pairing import pair_connectors


def resolve(sheets: Sequence[SheetGraph]) -> Resolution:
    """Lapokból üzemgráfot épít: szerződés -> feliratok -> párosítás -> azonosság -> egyesítés.

    Raises:
        ValueError: ha a bemenet sérti a resolver-határ szerződését
            (`check_contract`) — ez jelzi, ha egy hívó elfelejtette hívni a
            `localize()`-t, mielőtt ide adta a lapokat.
    """
    check_contract(sheets)
    labels, no_label_unresolved = _read_all_connector_labels(sheets)
    sheet_ids = {sheet.sheet_id for sheet in sheets}
    pairs, pairing_unresolved = pair_connectors(labels, sheet_ids)
    unresolved = no_label_unresolved + pairing_unresolved
    groups, ambiguous_tag_keys = group_identities(sheets)
    plant, edge_attribute_conflicts = build_plant_graph(sheets, pairs, groups)

    report = ResolutionReport(
        n_sheets=len(sheets),
        n_occurrences=sum(sheet.graph.number_of_nodes() for sheet in sheets),
        n_connectors=len(labels) + len(no_label_unresolved),
        pairs_by_rule=dict(Counter(pair.match_rule.value for pair in pairs)),
        unresolved_by_reason=dict(Counter(entry.reason for entry in unresolved)),
        n_identity_groups=len(groups),
        ambiguous_tag_keys=ambiguous_tag_keys,
        edge_attribute_conflicts=edge_attribute_conflicts,
    )
    return Resolution(
        plant=plant,
        connector_pairs=pairs,
        identity_groups=groups,
        unresolved=unresolved,
        report=report,
    )


def _read_all_connector_labels(
    sheets: Sequence[SheetGraph],
) -> tuple[list[ConnectorLabel], list[UnresolvedConnector]]:
    """Minden lap csatlakozóit egybegyűjti — a hiányzó hivatkozású csonkok külön listán."""
    labels: list[ConnectorLabel] = []
    unresolved: list[UnresolvedConnector] = []
    for sheet in sheets:
        sheet_labels, sheet_unresolved = read_connector_labels(sheet)
        labels += sheet_labels
        unresolved += sheet_unresolved
    return labels, unresolved
