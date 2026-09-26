"""Gráf-egyenlőség eszközök a G1/G2 kapuhoz (design `kg-construction.md` §5.6).

Ez a modul — a resolverrel ellentétben — szabadon importálhatja a
válaszkulcs-tudó `OccurrenceMap`-et: a gate feladata pont az, hogy a resolver
vak kimenetét a válaszkulccsal összevesse.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.graph import schema
from plantgraph.resolution.localize import OccurrenceMap


def visible_view(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """A csomópontok/élek attribútumait a V-fehérlistára szűkíti.

    Az eredeti (split előtti) üzemgráf olyan tulajdonságokat is hordozhat
    (pl. `manufacturer`), amiket a `localize()` sosem enged át a resolverig
    (design §4.3) — enélkül a G1 kapu két, eltérő fehérlistájú gráfot
    hasonlítana össze.
    """
    view: nx.DiGraph[str] = nx.DiGraph()
    for node_id, attrs in graph.nodes(data=True):
        view.add_node(node_id, **_visible(attrs, schema.VISIBLE_NODE_PROPERTIES))
    for source, target, attrs in graph.edges(data=True):
        view.add_edge(source, target, **_visible(attrs, schema.VISIBLE_EDGE_PROPERTIES))
    return view


def _visible(attrs: dict[str, object], whitelist: frozenset[str]) -> dict[str, object]:
    return {key: value for key, value in attrs.items() if key in whitelist}


def to_original_ids(graph: nx.DiGraph[str], occurrence_map: OccurrenceMap) -> nx.DiGraph[str]:
    """Helyi kulcsokat ("sheet:occ_id") az eredeti csomópont-id-kre fordít.

    Egy azonosság-csoport home- és reference-előfordulása ugyanarra az
    eredeti id-re fordul (a splitter L1 szivárgása, design §4.1 — itt éppen
    fordítva hasznosul): ha a resolver helyesen egyesítette őket egyetlen
    reprezentánssá, a fordítás után is csak egyetlen csomópont marad.

    Raises:
        ValueError: ha két különböző helyi kulcs ugyanarra az eredeti id-re
            fordulna — ez azt jelentené, hogy a resolver egy azonosság-
            csoportot tévesen hagyott szét egyesítetlenül.
    """
    original: nx.DiGraph[str] = nx.DiGraph()
    original_id_of: dict[str, str] = {}
    for local_key, attrs in graph.nodes(data=True):
        original_id = occurrence_map.original_node_id(local_key)
        if original_id in original:
            raise ValueError(
                f"both {original_id_of[original_id]!r} and {local_key!r} map to original id "
                f"{original_id!r}; the resolver left an identity group unmerged"
            )
        original_id_of[original_id] = local_key
        original.add_node(original_id, **attrs)
    for source, target, attrs in graph.edges(data=True):
        original.add_edge(
            occurrence_map.original_node_id(source),
            occurrence_map.original_node_id(target),
            **attrs,
        )
    return original


def graph_differences(
    actual: nx.DiGraph[str], expected: nx.DiGraph[str], limit: int = 20
) -> list[str]:
    """Az `assert_graphs_equal` (`test_splitter.py`) logikája függvényként: a különbségek listája.

    Üres lista jelenti az egyezést. `limit` a jelentett eltérések felső
    korlátja, hogy egy nagy korpuszon a hibaüzenet ne fusson el.
    """
    differences = (
        _node_set_differences(actual, expected)
        + _node_attribute_differences(actual, expected)
        + _edge_set_differences(actual, expected)
        + _edge_attribute_differences(actual, expected)
    )
    return differences[:limit]


def _node_set_differences(actual: nx.DiGraph[str], expected: nx.DiGraph[str]) -> list[str]:
    missing = sorted(set(expected.nodes) - set(actual.nodes))
    extra = sorted(set(actual.nodes) - set(expected.nodes))
    return [f"missing node {node!r}" for node in missing] + [
        f"unexpected node {node!r}" for node in extra
    ]


def _node_attribute_differences(actual: nx.DiGraph[str], expected: nx.DiGraph[str]) -> list[str]:
    differences = []
    for node_id, attrs in expected.nodes(data=True):
        if node_id in actual.nodes and actual.nodes[node_id] != attrs:
            differences.append(
                f"node {node_id!r} attributes differ: {actual.nodes[node_id]} != {attrs}"
            )
    return differences


def _edge_set_differences(actual: nx.DiGraph[str], expected: nx.DiGraph[str]) -> list[str]:
    missing = sorted(set(expected.edges) - set(actual.edges))
    extra = sorted(set(actual.edges) - set(expected.edges))
    return [f"missing edge {edge!r}" for edge in missing] + [
        f"unexpected edge {edge!r}" for edge in extra
    ]


def _edge_attribute_differences(actual: nx.DiGraph[str], expected: nx.DiGraph[str]) -> list[str]:
    differences = []
    for source, target, attrs in expected.edges(data=True):
        if not actual.has_edge(source, target):
            continue
        actual_attrs = actual.edges[source, target]
        if actual_attrs != attrs:
            differences.append(
                f"edge ({source!r}, {target!r}) attributes differ: {actual_attrs} != {attrs}"
            )
    return differences
