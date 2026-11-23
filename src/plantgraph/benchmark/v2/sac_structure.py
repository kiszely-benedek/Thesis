"""What the safety-checklist additions and checks read from a plant's structure (design 6.4).

One small graph of a plant, or of one unit of it (`Facts`): the pipe parts, the equipment and the
instruments, joined by `send_to`, `measured_by` and `send_signal_to` edges. The generator pass
that adds safety devices (`protection.py`) builds it from a unit's plan; the rule checks build it
from the oracle graph. Both ask the same questions here, so a device the pass adds is exactly a
device the check finds.

A **switch** is a safety sensor whose ISA letters have `S` second (`PSHH`: pressure, switch, high,
high). It is either the sensor itself or the bubble that a transmitter feeds.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass

import networkx as nx

from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation

_CONTROLLER = "ProcessControlFunction"
#: end fittings of a branch (a vent, a relief valve): the route stops there
_BRANCH_END_SUFFIXES = ("SafetyValve", "BreatherValve", "RuptureDisc")
#: `skillet_blind` is a spectacle blind: it isolates like a valve
_ISOLATING_ROLES = frozenset({"skillet_blind"})
_PASS_THROUGH_EQUIPMENT = frozenset(
    {"TubularHeatExchanger", "PlateHeatExchanger", "AirCoolingSystem"}
)


@dataclass(frozen=True)
class Facts:
    """A plant (or one unit) as a graph, with the role of each node."""

    graph: nx.DiGraph[str]
    piping: nx.DiGraph[str]
    roles: dict[str, str]

    def node_class(self, node: str) -> str:
        """The schema class of a node."""
        return str(self.graph.nodes[node]["node_class"])

    def role(self, node: str) -> str | None:
        """The role the plan gave the node."""
        return self.roles.get(node)


def facts_of_graph(graph: nx.DiGraph[str], piping: nx.DiGraph[str], roles: dict[str, str]) -> Facts:
    """The facts of a whole plant, from the oracle graph the rule view already holds."""
    return Facts(graph=graph, piping=piping, roles=roles)


def facts_of_plan(plan: TrimPlan) -> Facts:
    """The facts of one unit's plan; a line end that names another unit's part is left out."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    for equipment in plan.equipment:
        graph.add_node(equipment.node_id, node_class=equipment.node_class)
    for line in plan.lines:
        for item in line.items:
            graph.add_node(item.node_id, node_class=item.node_class)
    for instrument in plan.instruments:
        graph.add_node(instrument.node_id, node_class=instrument.node_class, tag=instrument.tag)
    piping: nx.DiGraph[str] = nx.DiGraph()
    for line in plan.lines:
        chain = [line.src_id, *(i.node_id for i in line.items), line.dst_id]
        known = [n for n in chain if n is not None and n in graph]
        piping.add_edges_from(zip(known, known[1:], strict=False))
    graph.add_edges_from(piping.edges, relation=Relation.SEND_TO.value)
    for link in plan.links:
        graph.add_edge(link.source_id, link.target_id, relation=link.relation.value)
    return Facts(graph=graph, piping=piping, roles=dict(plan.roles))


# ---- switches ------------------------------------------------------------------------------------


def _letters(facts: Facts, node: str) -> str:
    return str(facts.graph.nodes[node].get("tag") or "").split("-")[0]


def _sensors_on(facts: Facts, node: str) -> list[str]:
    return [
        t for _, t, d in facts.graph.out_edges(node, data=True)
        if d["relation"] == Relation.MEASURED_BY.value
    ]  # fmt: skip


def _fed_bubbles(facts: Facts, sensor: str) -> list[str]:
    return [
        t for _, t, d in facts.graph.out_edges(sensor, data=True)
        if d["relation"] == Relation.SEND_SIGNAL_TO.value
    ]  # fmt: skip


def switch_letters_on(facts: Facts, node: str) -> list[str]:
    """The ISA letters of every switch on `node`: its sensors and the bubbles they feed."""
    found = []
    for sensor in _sensors_on(facts, node):
        for member in (sensor, *_fed_bubbles(facts, sensor)):
            letters = _letters(facts, member)
            if len(letters) >= 3 and letters[1] == "S":
                found.append(letters)
    return found


def has_switch(facts: Facts, node: str, variable: str, direction: str) -> bool:
    """True when `node` has a switch of that variable (`P`, `L`, `T`) and direction (`H`, `L`)."""
    return any(s[0] == variable and s[2] == direction for s in switch_letters_on(facts, node))


def has_level_loop(facts: Facts, vessel: str) -> bool:
    """True when a level transmitter on the vessel feeds a controller: a loop holds its level."""
    for sensor in _sensors_on(facts, vessel):
        if _letters(facts, sensor) != "LT":
            continue
        if any(facts.node_class(b) == _CONTROLLER for b in _fed_bubbles(facts, sensor)):
            return True
    return False


# ---- routes --------------------------------------------------------------------------------------


def is_isolating(facts: Facts, node: str) -> bool:
    """True for a block or regulating valve, or a spectacle blind: a part that can shut the pipe."""
    if facts.role(node) in _ISOLATING_ROLES:
        return True
    name = facts.node_class(node)
    return "Valve" in name and not name.endswith(_BRANCH_END_SUFFIXES)


def valve_free_equipment(facts: Facts, start: str) -> set[str]:
    """The equipment reached from `start` along pipe with no isolating part on the way.

    Heat exchangers are passed through (a condenser between a column and its drum); any other
    equipment ends the route and is returned.
    """
    reached: set[str] = set()
    seen = {start}
    queue: deque[str] = deque([start])
    while queue:
        for nxt in facts.piping.successors(queue.popleft()):
            if nxt in seen:
                continue
            seen.add(nxt)
            if _extends(facts, nxt, reached):
                queue.append(nxt)
    reached.discard(start)
    return reached


def _extends(facts: Facts, node: str, reached: set[str]) -> bool:
    """True when the route continues past `node`; an equipment end is added to `reached`."""
    name = facts.node_class(node)
    if name in EQUIPMENT_CLASSES:
        if name in _PASS_THROUGH_EQUIPMENT:
            return True
        reached.add(node)
        return False
    return not is_isolating(facts, node) and not name.endswith(_BRANCH_END_SUFFIXES)


def reaches_safety_valve(facts: Facts, node: str) -> bool:
    """True when a safety device hangs on `node` over pipe parts only (a branch or its outlet)."""
    seen, queue = {node}, deque([node])
    while queue:
        for nxt in facts.piping.successors(queue.popleft()):
            if facts.node_class(nxt).endswith(("SafetyValve", "BreatherValve", "RuptureDisc")):
                return True
            if nxt not in seen and facts.node_class(nxt) not in EQUIPMENT_CLASSES:
                seen.add(nxt)
                queue.append(nxt)
    return False


def nodes_with_role(facts: Facts, roles: Iterable[str]) -> list[str]:
    """The nodes whose role is one of `roles`, in id order."""
    wanted = set(roles)
    return sorted(n for n, r in facts.roles.items() if r in wanted and n in facts.graph)
