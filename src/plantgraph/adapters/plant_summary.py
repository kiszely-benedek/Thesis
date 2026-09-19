"""A `pydexpi_adapter.plant_graph` kimenetének jellemzőit gyűjti össze (`plant-generator.md` §3.2).

Ez a modul sosem lát pyDEXPI-objektumot, csak a séma szerinti `nx.DiGraph`-ot
— attól vált külön a `pydexpi_adapter.py`-tól, hogy az ne lépje túl a 400 soros
fájlkorlátot, nem fogalmi okból: a `PlantSummary` az EXP-0002 skálázási sweep
regressziós változóit adja minden legenerált üzem mellé.
"""

from __future__ import annotations

import collections

import networkx as nx

from plantgraph.benchmark.generator_models import PlantSummary
from plantgraph.graph import schema


def summarize_plant(plant: nx.DiGraph[str]) -> PlantSummary:
    """A séma-gráf jellemzőit gyűjti — csak a `DiGraph`-ot nézi, a pyDEXPI-modellt nem (§3.2)."""
    nodes_per_class = collections.Counter(
        str(attrs.get("node_class")) for _, attrs in plant.nodes(data=True)
    )
    edges_per_relation = collections.Counter(
        str(attrs.get("relation")) for _, _, attrs in plant.edges(data=True)
    )
    line_kinds = _line_number_kinds(plant)
    equipment_nodes = [
        node_id
        for node_id, attrs in plant.nodes(data=True)
        if attrs.get("node_class") in schema.EQUIPMENT_CLASSES
    ]
    units = {
        attrs["unit_id"] for _, attrs in plant.nodes(data=True) if attrs.get("unit_id") is not None
    }

    return PlantSummary(
        n_nodes=plant.number_of_nodes(),
        n_edges=plant.number_of_edges(),
        nodes_per_class=dict(nodes_per_class),
        edges_per_relation=dict(edges_per_relation),
        n_units=len(units),
        n_equipment=len(equipment_nodes),
        n_streams=len(line_kinds),
        streams_per_kind=dict(collections.Counter(line_kinds.values())),
        n_control_loops=nodes_per_class.get(
            schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value, 0
        ),
        max_streams_out_of_one_equipment=max(
            (_send_to_out_degree(plant, node_id) for node_id in equipment_nodes), default=0
        ),
    )


def _line_number_kinds(plant: nx.DiGraph[str]) -> dict[str, str]:
    """Csővezeték (line_number) -> stream_kind, a `send_to` élek tulajdonságaiból.

    "unknown" ha egy `send_to` élnek nincs `stream_kind`-je — ez egy külső,
    `GenerationRecord` nélküli DEXPI-fájlnál (pl. EXP-0001) várható, nem hiba.
    """
    return {
        str(attrs["line_number"]): str(attrs.get("stream_kind", "unknown"))
        for _, _, attrs in plant.edges(data=True)
        if attrs.get("relation") == schema.Relation.SEND_TO.value
    }


def _send_to_out_degree(plant: nx.DiGraph[str], node_id: str) -> int:
    """Hány csővezetéket indít a csomópont — csak a `send_to` éleket számolja."""
    return sum(
        1
        for _, _, attrs in plant.out_edges(node_id, data=True)
        if attrs.get("relation") == schema.Relation.SEND_TO.value
    )
