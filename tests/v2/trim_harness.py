"""A one-unit test plant for trims, written to the graph oracle and the DEXPI builder at once.

Not a test module (no `test_` prefix). `TrimHarness` gives a `TrimContext`, host equipment to hang
trims on, and `write`, which sends a plan to both backends so a test can compare the two graphs.
"""

from __future__ import annotations

import random

import networkx as nx

from graph_plant_builder_v2 import GraphPlantBuilderV2
from plantgraph.adapters.pydexpi_adapter import ConversionReport
from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.benchmark.v2.class_decks import role_deck_variants
from plantgraph.benchmark.v2.config import TrimConvention
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, GenerationRecordV2, LineSpec
from plantgraph.benchmark.v2.trim_context import LineStyle, TrimContext
from plantgraph.benchmark.v2.trim_plan import TrimPlan, main_line
from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming, TrainConventions
from plantgraph.graph import validation
from plantgraph.graph.schema import CLASS_SPECS, NodeClass, Relation

STYLE = LineStyle(size=6)
_NODE_KEYS = ("node_class", "tag", "plant_id", "unit_id", "loop_tag", "measured_variable")
_EDGE_KEYS = ("relation", "line_number", "fluid_code")
_RECORD = GenerationRecordV2(plant_id="plant0", seed=0, generator_config="{}", pydexpi_version="t")


def convention(**overrides: object) -> TrimConvention:
    """The default trim knobs with some overridden (`p_cv_station=1.0` ...)."""
    return TrimConvention(**overrides)  # type: ignore[arg-type]


class TeeBuilder:
    """A `PlantBuilderV2` that forwards every call to several backends."""

    backend_version = "tee"

    def __init__(self, *builders: GraphPlantBuilderV2 | DexpiPlantBuilderV2) -> None:
        self.builders = builders

    def add_section(self, unit_no: int, name: str) -> None:
        for builder in self.builders:
            builder.add_section(unit_no, name)

    def add_equipment(self, spec: EquipmentSpec) -> None:
        for builder in self.builders:
            builder.add_equipment(spec)

    def add_line(self, spec: LineSpec) -> None:
        for builder in self.builders:
            builder.add_line(spec)

    def add_instrument(self, spec: object) -> None:
        for builder in self.builders:
            builder.add_instrument(spec)  # type: ignore[arg-type]

    def add_link(self, spec: object) -> None:
        for builder in self.builders:
            builder.add_link(spec)  # type: ignore[arg-type]


class TrimHarness:
    """Unit 1 of a plant0, a context for it, and both backends."""

    def __init__(
        self,
        seed: int = 0,
        config: TrimConvention | None = None,
        on_off: OnOffLetter = OnOffLetter.X,
    ) -> None:
        conventions = TrainConventions(on_off_letter=on_off, spare_naming=SpareNaming.SUFFIX)
        self.ctx = TrimContext(
            1,
            random.Random(seed),
            config or TrimConvention(),
            conventions,
            VariantDecks(seed, role_deck_variants()),
        )
        self.oracle = GraphPlantBuilderV2("plant0")
        self.dexpi = DexpiPlantBuilderV2("plant0")
        self.builder = TeeBuilder(self.oracle, self.dexpi)
        self.builder.add_section(1, "TKF Feed tank")
        self._hosts = 0

    def equipment(self, node_class: str, type_code: str | None = None) -> str:
        """Add one piece of host equipment to unit 1; returns its node id.

        `type_code` is the tag prefix; the class's own prefix when left out.
        """
        numbering = self.ctx.numbering
        type_code = type_code or CLASS_SPECS[NodeClass(node_class)].tag_prefix or "V"
        self._hosts += 1
        node_id = f"host-{self._hosts}"
        spec = EquipmentSpec(
            node_id=node_id,
            node_class=node_class,
            unit_no=1,
            tag=numbering.equipment_tag(type_code),
        )
        self.builder.add_equipment(spec)
        return node_id

    def write(self, plan: TrimPlan, src: str | None = None, dst: str | None = None) -> TrimPlan:
        """Write a plan; a plan with a `run` is closed into a line from `src` to `dst` first."""
        if plan.run:
            plan = plan.with_main_line(main_line(self.ctx, STYLE, src, plan.run, dst))
        plan.write(self.builder)
        return plan

    def dexpi_graph(self) -> tuple[nx.DiGraph[str], ConversionReport]:
        """The DEXPI backend's model read back through the v2 adapter."""
        return plant_graph_v2(self.dexpi.build(), _RECORD)


def project(graph: nx.DiGraph[str]) -> tuple[list[object], list[object]]:
    """Nodes and edges with only the properties the two backends must agree on."""
    nodes = sorted(
        (n, tuple((k, d[k]) for k in _NODE_KEYS if k in d)) for n, d in graph.nodes(data=True)
    )
    edges = sorted(
        (s, t, tuple((k, d[k]) for k in _EDGE_KEYS if k in d)) for s, t, d in graph.edges(data=True)
    )
    return nodes, edges


def assert_round_trip(harness: TrimHarness) -> nx.DiGraph[str]:
    """The DEXPI model gives the oracle's graph, loses no node or edge and validates.

    Returns the oracle graph for the caller's rule checks.
    """
    graph, report = harness.dexpi_graph()
    assert set(report.nodes_dropped_per_class) <= {"ProcessPlant", "PlantSection"}
    assert report.edges_dropped_per_label == {}
    assert project(graph) == project(harness.oracle.graph)
    assert validation.validate_plant_graph(graph) == []
    return harness.oracle.graph


def _flow(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    return nx.DiGraph(
        (s, t) for s, t, d in graph.edges(data=True) if d["relation"] == Relation.SEND_TO.value
    )


def send_to_path(graph: nx.DiGraph[str], source: str, target: str) -> list[str]:
    """The node ids along the shortest `send_to` path from `source` to `target`."""
    return list(nx.shortest_path(_flow(graph), source, target))


def all_send_to_paths(graph: nx.DiGraph[str], source: str, target: str) -> list[list[str]]:
    """Every `send_to` path from `source` to `target`, shortest first."""
    paths = nx.all_simple_paths(_flow(graph), source, target)
    return sorted((list(path) for path in paths), key=len)


def classes_of(graph: nx.DiGraph[str], node_ids: list[str]) -> list[str]:
    """The node class of each id."""
    return [graph.nodes[node_id]["node_class"] for node_id in node_ids]


def sensor_tags_on(graph: nx.DiGraph[str], node_id: str) -> list[str]:
    """The tags of the sensors located on `node_id` (its `measured_by` targets), sorted."""
    return sorted(
        graph.nodes[target]["tag"]
        for _, target, data in graph.out_edges(node_id, data=True)
        if data["relation"] == Relation.MEASURED_BY.value
    )


def ids_with_role(plan: TrimPlan, role: str) -> list[str]:
    """The plan's node ids that were planned for `role`, in id order."""
    return sorted(node_id for node_id, node_role in plan.roles.items() if node_role == role)
