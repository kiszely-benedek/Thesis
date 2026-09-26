"""Four partitioning strategies: how to cut the plant graph into sheets.

Each fulfils the same contract: takes a full plant graph, a SplitConfig, and a
seeded random generator, and returns a node -> sheet-id assignment. **None of
them cuts edges** — that is done by splitter.py, based on the partition
(splitter.md section 2).

A shared step in all four: the sheet budget only counts "equipment" (a valve,
instrument, or pipe marker rides along for free — splitter.md open question 2),
so every node is first assigned to its nearest equipment (a cluster), and the
strategies decide at the cluster level. The four strategies differ only in
WHAT ORDER they let clusters onto a sheet: the actual chunking into sheets
(_chunk_by_budget) is shared code.
"""

from __future__ import annotations

import random
import statistics
from collections import deque
from collections.abc import Callable

import networkx as nx

from plantgraph.benchmark.split_models import SplitConfig

# quoted forward reference: nx.DiGraph is not subscriptable at real runtime
# (the [str] only exists in the type stub), so this must not be evaluated here
StrategyFn = Callable[["nx.DiGraph[str]", SplitConfig, random.Random], dict[str, str]]


def flow_greedy(plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random) -> dict[str, str]:
    """The default strategy: fills sheets working downstream from the feed equipment.

    Imitates how an engineer actually works (splitter.md section 3): sheet
    order follows the process flow direction, so most cross-references point
    to a neighbouring sheet number.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    order = _flow_order(owner_graph, equipment_owners)
    owner_sheets = _chunk_by_budget(order, equipment_owners, config.sheet_equipment_budget)
    return _expand_to_nodes(owner_sheets, node_owner)


def modularity(plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random) -> dict[str, str]:
    """Find Louvain communities on the equipment graph, and chunk the found groups onto sheets.

    This models "partitioning by process unit": a column together with its
    reboiler, condenser, and pumps usually falls into one community.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    undirected = owner_graph.to_undirected()
    communities = nx.community.louvain_communities(undirected, seed=rng.randint(0, 2**31 - 1))
    # sorted(...) gives a deterministic traversal order independent of the
    # internal ordering of the sets/lists it contains — without this, the "same
    # seed -> same manifest" test would occasionally fail (see the module docstring too)
    ordered_communities = sorted(sorted(community) for community in communities)
    order = [owner for community in ordered_communities for owner in community]
    owner_sheets = _chunk_by_budget(order, equipment_owners, config.sheet_equipment_budget)
    return _expand_to_nodes(owner_sheets, node_owner)


def by_unit(plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random) -> dict[str, str]:
    """Partition by the declared process unit (unit_id), not by graph community.

    modularity *guesses* something about the graph's topology from its
    structure (Louvain communities); by_unit follows the plant->unit hierarchy
    the generator already declared, directly (N6, `plant-generator.md` §5
    finding 3) — a sheet never mixes two units.

    Raises:
        ValueError: if not a single piece of equipment has a unit_id attribute.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    order = _flow_order(owner_graph, equipment_owners)
    unit_of = {owner: str(plant.nodes[owner].get("unit_id", "")) for owner in order}

    if not any(unit_of[owner] for owner in equipment_owners):
        raise ValueError("by_unit needs unit_id on equipment nodes")

    owner_sheets: list[list[str]] = []
    for unit_id in _units_in_flow_order(order, unit_of):
        owners_in_unit = [owner for owner in order if unit_of[owner] == unit_id]
        owner_sheets += _chunk_by_budget(
            owners_in_unit, equipment_owners, config.sheet_equipment_budget
        )
    return _expand_to_nodes(owner_sheets, node_owner)


def _units_in_flow_order(order: list[str], unit_of: dict[str, str]) -> list[str]:
    """List units by the flow-order position of the first owner that belongs to them."""
    seen: list[str] = []
    for owner in order:
        unit_id = unit_of[owner]
        if unit_id not in seen:
            seen.append(unit_id)
    return seen


def utility_aware(
    plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random
) -> dict[str, str]:
    """Put the high-degree (utility-like) equipment onto hub sheets first.

    flow_greedy then runs on the remainder.

    Steam, cooling-water, and instrument-air headers connect to many systems
    (splitter.md section 3, "hub sheets"); this strategy adds that structure.

    Note: not used in the experiments yet, until the generator produces a
    utility header (`plant-generator.md` §5) — without one, a "hub" would just
    be a high-degree process equipment node, not a real header.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    owner_graph = _owner_graph(plant, node_owner)
    hub_owners = _detect_hubs(owner_graph, equipment_owners)

    hub_order = sorted(hub_owners)
    hub_sheets = _chunk_by_budget(hub_order, equipment_owners, config.sheet_equipment_budget)

    rest_graph = owner_graph.copy()
    rest_graph.remove_nodes_from(hub_owners)
    rest_equipment = equipment_owners - hub_owners
    rest_order = _flow_order(rest_graph, rest_equipment)
    rest_sheets = _chunk_by_budget(rest_order, rest_equipment, config.sheet_equipment_budget)

    return _expand_to_nodes(hub_sheets + rest_sheets, node_owner)


def random_partition(
    plant: nx.DiGraph[str], config: SplitConfig, rng: random.Random
) -> dict[str, str]:
    """Control strategy: distributes equipment in random order, independent of the process.

    Deliberately unrealistic (splitter.md section 3): if this gives the same
    retrieval accuracy as flow_greedy, that is itself a finding — it would mean
    the benchmark is insensitive to how realistic the partitioning is.
    """
    equipment_owners, node_owner = _cluster_owners(plant, config.equipment_classes)
    order = sorted(set(node_owner.values()))
    rng.shuffle(order)
    owner_sheets = _chunk_by_budget(order, equipment_owners, config.sheet_equipment_budget)
    return _expand_to_nodes(owner_sheets, node_owner)


STRATEGIES: dict[str, StrategyFn] = {
    "flow_greedy": flow_greedy,
    "modularity": modularity,
    "by_unit": by_unit,
    "utility_aware": utility_aware,
    "random": random_partition,
}


def _cluster_owners(
    plant: nx.DiGraph[str], equipment_classes: set[str]
) -> tuple[set[str], dict[str, str]]:
    """Assign every node to its nearest equipment.

    Attached instruments thus travel to the same sheet as their equipment.

    The node_class attribute decides what counts as equipment (a SplitConfig
    parameter, not a hardcoded pyDEXPI class list — see splitter.md open
    question 2). If a node cannot reach any equipment at all (an isolated
    instrument subnetwork), it becomes its own cluster; a rare case, and it
    does not count against the sheet budget, since it isn't equipment.
    """
    equipment_owners = {
        node_id
        for node_id, attrs in plant.nodes(data=True)
        if attrs.get("node_class") in equipment_classes
    }
    owner: dict[str, str] = {
        equipment_id: equipment_id for equipment_id in sorted(equipment_owners)
    }

    undirected = plant.to_undirected(as_view=True)
    queue: deque[str] = deque(sorted(equipment_owners))
    while queue:
        node_id = queue.popleft()
        for neighbour in sorted(undirected.neighbors(node_id)):
            if neighbour in owner:
                continue
            owner[neighbour] = owner[node_id]
            queue.append(neighbour)

    for node_id in sorted(plant.nodes):
        if node_id not in owner:
            owner[node_id] = node_id

    return equipment_owners, owner


def _owner_graph(plant: nx.DiGraph[str], node_owner: dict[str, str]) -> nx.DiGraph[str]:
    """A condensed graph depicting the edges between clusters — every strategy decides on this."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_nodes_from(sorted(set(node_owner.values())))
    for source, target in plant.edges():
        owner_source, owner_target = node_owner[source], node_owner[target]
        if owner_source != owner_target:
            graph.add_edge(owner_source, owner_target)
    return graph


def _flow_order(owner_graph: nx.DiGraph[str], equipment_owners: set[str]) -> list[str]:
    """Depth-first preorder walk from the feed equipment (zero in-degree) downstream.

    Depth-first, not breadth-first (ADR-0017): a breadth-first walk visits one
    step of every chain before the second step of any of them, so under a
    fixed sheet budget the two ends of an edge end up dozens of chains apart —
    nearly every inter-cluster edge gets cut. Depth-first walks one chain to
    its end before starting the next, so a chain mostly stays on one sheet.
    """
    feeds = sorted(owner for owner in equipment_owners if owner_graph.in_degree(owner) == 0)
    if not feeds and owner_graph.number_of_nodes() > 0:
        # a cyclic graph has no true feed (zero in-degree node) —
        # deterministic fallback so the walk still starts somewhere
        feeds = [sorted(owner_graph.nodes)[0]]

    order: list[str] = []
    visited: set[str] = set()
    # a stack, not a queue: LIFO order gives depth-first rather than breadth-first
    stack: list[str] = list(reversed(feeds))
    while len(visited) < owner_graph.number_of_nodes():
        if not stack:
            remaining = sorted(set(owner_graph.nodes) - visited)
            stack.append(remaining[0])
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        order.append(node_id)
        # reversed so sorted() order comes off the stack first (smallest successor next)
        stack.extend(sorted(owner_graph.successors(node_id), reverse=True))
    return order


def _detect_hubs(owner_graph: nx.DiGraph[str], equipment_owners: set[str]) -> set[str]:
    """Compute from the degree distribution which equipment counts as a utility hub.

    Deliberately no separate threshold setting: the pattern observed on OPEN100
    (splitter.md section 3) would show up at a different degree on every graph,
    so outliers above mean + standard deviation are taken as hubs, not a constant.
    """
    if len(equipment_owners) < 2:
        return set()
    degrees = {owner: owner_graph.degree(owner) for owner in equipment_owners}
    mean = statistics.mean(degrees.values())
    spread = statistics.pstdev(degrees.values())
    threshold = mean + spread
    return {owner for owner, degree in degrees.items() if degree > threshold and degree > 0}


def _chunk_by_budget(order: list[str], equipment_owners: set[str], budget: int) -> list[list[str]]:
    """Chunk an ordered list of clusters onto sheets.

    Only equipment clusters count against the budget.
    """
    sheets: list[list[str]] = [[]]
    equipment_count = 0
    for owner in order:
        is_equipment = owner in equipment_owners
        if is_equipment and equipment_count >= budget and sheets[-1]:
            sheets.append([])
            equipment_count = 0
        sheets[-1].append(owner)
        if is_equipment:
            equipment_count += 1
    return sheets


def _expand_to_nodes(owner_sheets: list[list[str]], node_owner: dict[str, str]) -> dict[str, str]:
    """Extend the owner -> sheet assignment to every node, based on cluster membership."""
    owner_sheet_id = {
        owner: str(index) for index, owners in enumerate(owner_sheets) for owner in owners
    }
    return {node_id: owner_sheet_id[owner] for node_id, owner in node_owner.items()}
