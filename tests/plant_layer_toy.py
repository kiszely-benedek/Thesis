"""A generated toy plant with its gold side, and a fake readback source (no database).

`ReplaySource` answers the readback queries from the rows the loader would
write (`store/plant_rows.py`), so the readback and PLANT-01 run on exactly what
Neo4j would hold. No "test_" prefix: pytest does not collect it.
"""

from __future__ import annotations

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.plant_layer_fidelity import PlantLayerFidelity, check_plant_layer
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve
from plantgraph.store import plant_readback as rb
from plantgraph.store.neo4j_rows import NodeRow, RelationshipRow
from plantgraph.store.plant_rows import drawn_as_rows, plant_node_rows, plant_relationship_rows

CORPUS = "toy"


class ReplaySource:
    """Answers each readback query from in-memory rows, in the shape Neo4j would return."""

    def __init__(self, nodes: list[NodeRow], relationships: list[RelationshipRow]) -> None:
        self.nodes = nodes
        self.relationships = relationships

    def read(self, query: str, corpus_id: str) -> list[rb.Record]:
        if query == rb.ITEMS_QUERY:
            return [
                {"uid": n.uid, "labels": list(n.labels), "properties": dict(n.props)}
                for n in self.nodes
            ]
        if query == rb.EDGES_QUERY:
            return [
                {
                    "source": r.source_uid,
                    "target": r.target_uid,
                    "relation": r.rel_type,
                    "properties": dict(r.props),
                }
                for r in self.relationships
                if r.rel_type not in ("is_drawn_on", "is_located_in", "drawn_as")
            ]
        by_query = {
            rb.SHEETS_QUERY: "is_drawn_on",
            rb.UNITS_QUERY: "is_located_in",
            rb.DRAWN_AS_QUERY: "drawn_as",
        }
        wanted = by_query[query]
        return [
            {"item": r.source_uid, "value": self._value(wanted, r.target_uid)}
            for r in self.relationships
            if r.rel_type == wanted
        ]

    @staticmethod
    def _value(relation: str, target_uid: str) -> str:
        """What the query returns: a sheet id, a unit id, or (drawn_as) the occurrence uid.

        In this corpus a sheet's uid tail is its id and a unit's is `unit:<id>`.
        """
        tail = target_uid.split("|", 1)[1]
        if relation == "is_located_in":
            return tail.removeprefix("unit:")
        return tail if relation == "is_drawn_on" else target_uid


class Toy:
    """A generated 4-unit plant split on small sheets, with its gold side."""

    def __init__(self, duplication_rate: float) -> None:
        config = GeneratorConfig(seed=7)
        builder = GraphPlantBuilder(config.plant_id)
        plan_plant(config, builder)
        split_config = SplitConfig(
            sheet_equipment_budget=2, seed=7, duplication_rate=duplication_rate
        )
        sheets, _manifest = split(builder.graph, split_config)
        self.gold = builder.graph
        self.sheets: list[SheetGraph]
        self.sheets, self.occurrence_map = localize(sheets)
        self.resolution: Resolution = resolve(self.sheets)

    def item_graph(self) -> ItemGraph:
        return build_item_graph(NetworkxGraphView(CORPUS, self.sheets, self.resolution))

    def source(self) -> ReplaySource:
        nodes = plant_node_rows(CORPUS, self.sheets, self.resolution)
        relationships = plant_relationship_rows(CORPUS, self.sheets, self.resolution, "resolver")
        relationships += drawn_as_rows(CORPUS, self.sheets, self.resolution, "resolver")
        return ReplaySource(nodes, relationships)

    def check(self, source: ReplaySource) -> PlantLayerFidelity:
        layer = rb.read_plant_layer(source, CORPUS)
        return check_plant_layer(layer, self.gold, self.occurrence_map, self.item_graph(), CORPUS)
