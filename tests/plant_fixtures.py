"""Build synthetic plant graphs for the splitter's tests.

The pyDEXPI adapter (ADR-0003) does not exist yet, so these fixtures are built
directly with networkx — the splitter only requires that every node in the input
carry 'node_class' and 'tag' attributes, and every edge a 'relation' (see
splitter.md section 2, "In", and plant-generator.md §5 finding 5). No "test_"
prefix, so pytest does not collect this file as a test module.

The equipment classes use the schema's (plantgraph.graph.schema) real pyDEXPI
names, so the splitter's default equipment_classes (schema.EQUIPMENT_CLASSES)
works on this fixture without modification. 'utility_header' is the exception:
it has no schema entry, and deliberately stays a test-only class for exercising
the utility_aware strategy.

Equipment nodes also get a 'manufacturer' and a 'unit_id' attribute. The splitter
never copies 'manufacturer' onto reference occurrences — this gives a handle for
testing that a duplicated node really does carry only the tag and little else
(see test_identity_groups.py). 'unit_id' is needed by the by_unit strategy
(plant-generator.md §5 finding 3): each process chain is its own unit, and the
feed shares its unit with the first chain.
"""

from __future__ import annotations

import networkx as nx

EQUIPMENT_CLASSES = ("CentrifugalPump", "HeatExchanger", "ProcessColumn", "Tank")


def make_plant_graph(
    chain_length: int = 4, branches: int = 2, utility_fanout: int = 4
) -> nx.DiGraph:
    """A plausible plant graph: a feed, equipment chains, a utility header, and instruments on them.

    A utility header is a shared supply line (e.g. steam or cooling water) feeding
    many pieces of equipment; it is deliberately given a high degree here, as a
    real one would have (see utility_aware in strategies.py).

    Args:
        chain_length: how many pieces of equipment sit in one process chain downstream of the feed.
        branches: how many parallel process chains start from the feed.
        utility_fanout: how many pieces of equipment the utility header connects to.
    """
    plant = nx.DiGraph()
    feed = "feed-1"
    plant.add_node(
        feed, node_class="PressureVessel", tag="V-100", manufacturer="Acme", unit_id="u0"
    )

    utility = "utility-steam"
    plant.add_node(utility, node_class="utility_header", tag="STM-HDR-1")

    all_equipment = [feed]
    for branch in range(branches):
        all_equipment += _add_chain(plant, feed, branch, chain_length)

    for node_id in all_equipment[:utility_fanout]:
        plant.add_edge(utility, node_id, service="steam", relation="send_to")

    return plant


def _add_chain(plant: nx.DiGraph, feed: str, branch: int, chain_length: int) -> list[str]:
    """String one process chain downstream of the feed, with one instrument per stage."""
    equipment_ids: list[str] = []
    upstream = feed
    unit_id = f"u{branch}"
    for step in range(chain_length):
        node_class = EQUIPMENT_CLASSES[step % len(EQUIPMENT_CLASSES)]
        node_id = f"eq-{branch}-{step}"
        tag = f"{node_class[0].upper()}-{branch}{step}"
        plant.add_node(
            node_id, node_class=node_class, tag=tag, manufacturer="Acme", unit_id=unit_id
        )
        plant.add_edge(upstream, node_id, service="process", relation="send_to")
        _attach_instrument(plant, node_id, branch, step)
        equipment_ids.append(node_id)
        upstream = node_id
    return equipment_ids


def _attach_instrument(plant: nx.DiGraph, equipment_id: str, branch: int, step: int) -> None:
    """Attach an instrument to a piece of equipment.

    Never counts against the sheet budget on its own, it just needs to travel
    with its equipment.
    """
    instrument_id = f"inst-{branch}-{step}"
    plant.add_node(
        instrument_id, node_class="ProcessSignalGeneratingFunction", tag=f"FT-{branch}{step}"
    )
    plant.add_edge(equipment_id, instrument_id, service="signal", relation="measured_by")
