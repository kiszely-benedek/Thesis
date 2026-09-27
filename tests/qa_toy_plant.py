"""A hand-built, hand-split toy plant for QA-T6's family and evidence tests.

Deliberately not built through the real generator or splitter (`plan_plant`,
`benchmark.splitter.split`): those pick their own topology and cuts, so a
test built on their output could not state, in one line, "this edge crosses
sheets and that one doesn't". This plant and its split are chosen by hand
instead, precisely so every `k` in `test_qa_questions_families.py` can be
counted by a human reading this file (design `qa-system.md` §16, "Hand-built
plants of 10 nodes or fewer with a known split check every reference
function and every k by hand").

**Topology** (see the module docstring of `families_flow.py` and
`families_loop.py` for what each relation means):

    TANK --send_to--> VALVE --send_to--> PUMP --send_to--> VESSEL --send_to--> TANK_U2
    TANK --measured_by--> SENSOR --send_signal_to--> CONTROLLER
    CONTROLLER --send_signal_to--> ACTUATOR --control--> VALVE

**Hand-chosen split**, and the resulting cut (an edge is cut iff its two
ends land on different sheets):

    Sheet S1: TANK, SENSOR
    Sheet S2: CONTROLLER, ACTUATOR, VALVE
    Sheet S3: PUMP
    Sheet S4: VESSEL, TANK_U2

    cut = {TANK->VALVE, SENSOR->CONTROLLER, VALVE->PUMP, PUMP->VESSEL}

Node ids (`N_*`) are internal and must never appear in generated question
text; tags (`TAG_*`) are what a question names instead.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.models import ConnectorPair, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph.schema import NodeClass, Relation

# Internal node ids — never printed on a drawing, so never expected in question text.
N_TANK = "n-tank"
N_VALVE = "n-valve"
N_PUMP = "n-pump"
N_VESSEL = "n-vessel"
N_TANK_U2 = "n-tank-u2"
N_SENSOR = "n-sensor"
N_CONTROLLER = "n-controller"
N_ACTUATOR = "n-actuator"

# Printed tags — what a question names.
TAG_TANK = "TK-1-1"
TAG_VALVE = "GV-1-1"
TAG_PUMP = "P-1-1"
TAG_VESSEL = "V-1-1"
TAG_TANK_U2 = "TK-2-1"
TAG_LOOP = "FIC-1-1"  # the controller's own tag, i.e. the loop's name

SHEET_1 = "S1"
SHEET_2 = "S2"
SHEET_3 = "S3"
SHEET_4 = "S4"


def build_toy_plant() -> nx.DiGraph[str]:
    """The ground-truth graph, before any split — see the module docstring for its topology."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node(N_TANK, node_class=NodeClass.TANK.value, tag=TAG_TANK, unit_id="1")
    plant.add_node(N_VALVE, node_class=NodeClass.GLOBE_VALVE.value, tag=TAG_VALVE, unit_id="1")
    plant.add_node(N_PUMP, node_class=NodeClass.CENTRIFUGAL_PUMP.value, tag=TAG_PUMP, unit_id="1")
    plant.add_node(
        N_VESSEL, node_class=NodeClass.PRESSURE_VESSEL.value, tag=TAG_VESSEL, unit_id="1"
    )
    plant.add_node(N_TANK_U2, node_class=NodeClass.TANK.value, tag=TAG_TANK_U2, unit_id="2")
    plant.add_node(
        N_SENSOR,
        node_class=NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
        tag="FT-1-1",
        unit_id="1",
        loop_tag=TAG_LOOP,
    )
    plant.add_node(
        N_CONTROLLER,
        node_class=NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value,
        tag=TAG_LOOP,
        unit_id="1",
        loop_tag=TAG_LOOP,
    )
    plant.add_node(
        N_ACTUATOR,
        node_class=NodeClass.ACTUATING_FUNCTION.value,
        tag="FV-1-1",
        unit_id="1",
        loop_tag=TAG_LOOP,
    )

    plant.add_edge(N_TANK, N_VALVE, relation=Relation.SEND_TO.value)
    plant.add_edge(N_VALVE, N_PUMP, relation=Relation.SEND_TO.value)
    plant.add_edge(N_PUMP, N_VESSEL, relation=Relation.SEND_TO.value)
    plant.add_edge(N_VESSEL, N_TANK_U2, relation=Relation.SEND_TO.value)

    plant.add_edge(N_TANK, N_SENSOR, relation=Relation.MEASURED_BY.value)
    plant.add_edge(N_SENSOR, N_CONTROLLER, relation=Relation.SEND_SIGNAL_TO.value)
    plant.add_edge(N_CONTROLLER, N_ACTUATOR, relation=Relation.SEND_SIGNAL_TO.value)
    plant.add_edge(N_ACTUATOR, N_VALVE, relation=Relation.CONTROL.value)
    return plant


#: The edges that land on different sheets under the hand-chosen split below —
#: exactly what `evidence.connector_cut` must reconstruct from `build_toy_manifest`.
CUT_EDGES: frozenset[tuple[str, str]] = frozenset(
    {
        (N_TANK, N_VALVE),
        (N_SENSOR, N_CONTROLLER),
        (N_VALVE, N_PUMP),
        (N_PUMP, N_VESSEL),
    }
)

_SHEET_NODES: dict[str, list[str]] = {
    SHEET_1: [N_TANK, N_SENSOR],
    SHEET_2: [N_CONTROLLER, N_ACTUATOR, N_VALVE],
    SHEET_3: [N_PUMP],
    SHEET_4: [N_VESSEL, N_TANK_U2],
}


def build_toy_sheets(plant: nx.DiGraph[str]) -> list[SheetGraph]:
    """The hand-chosen split's four sheets, each holding its own node subset only."""
    return [
        SheetGraph(sheet_id=sheet_id, graph=plant.subgraph(node_ids).copy())
        for sheet_id, node_ids in _SHEET_NODES.items()
    ]


def build_toy_manifest() -> SplitManifest:
    """A `SplitManifest` recording exactly `CUT_EDGES` as cut, and nothing else.

    `from_key`/`to_key` are placeholders: no family or evidence function
    reads them, only `original_edge` (`evidence.connector_cut`).
    """
    return SplitManifest(
        source="qa_toy_plant",
        sheet_files=list(_SHEET_NODES),
        connector_pairs=[
            ConnectorPair(from_key=f"stub-out-{i}", to_key=f"stub-in-{i}", original_edge=edge)
            for i, edge in enumerate(sorted(CUT_EDGES))
        ],
    )
