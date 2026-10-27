"""Structural invariants S1-S3, S5, S6, S10-S12, S21, S23, S24 over a whole v2 plant (design 12.2).

Not a test module (no `test_` prefix). S4, S7-S9, S19 and S22 are in `instrument_invariants.py` and
`machine_checks.py`. Every `check_*` takes a `PlantView` and raises `AssertionError` naming the
offending node; it returns how many things it checked, so a test can insist it was not vacuous.

Terms a reader outside process engineering needs. A **role** is the job a part has in its pattern
(`suction_block`), kept in the plan, not in the graph the system reads. A **spare set** (A/B) is
two or three identical machines installed side by side, one running. **Downstream** follows the
flow, so a pump's discharge is downstream of it and its suction upstream.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

import networkx as nx
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel

from graph_plant_builder_v2 import GraphPlantBuilderV2
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import GeneratedPlantV2, generate_plant_v2
from plantgraph.benchmark.v2.patterns.ports import PortDirection
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.benchmark.v2.trims_vessel import PSV_VESSEL_CLASSES
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation

CENTRIFUGAL_PUMP = "CentrifugalPump"
POSITIVE_DISPLACEMENT_PUMPS = frozenset({"ReciprocatingPump", "RotaryPump"})
_PUMPS = POSITIVE_DISPLACEMENT_PUMPS | {CENTRIFUGAL_PUMP}
_BLOCK_VALVES = frozenset({"GateValve", "ButterflyValve", "BallValve", "PlugValve"})
_CHECK_VALVES = frozenset({"SwingCheckValve", "GlobeCheckValve", "CheckValve"})
_MIN_FLOW_ROLES = frozenset({"min_flow_check", "min_flow_block"})
#: S6 exemption (design 14.4): the real sheet this trim copies draws the pot with no safety valve
S6_EXEMPT_ROLE = "condensate_drain_pot"


@dataclass(frozen=True)
class PlantView:
    """One generated plant: the plan, the oracle graph, the DEXPI model and every node's role."""

    generated: GeneratedPlantV2
    graph: nx.DiGraph[str]
    roles: dict[str, str]

    @property
    def model(self) -> DexpiModel:
        """The pyDEXPI model the plan was written to."""
        return self.generated.model


@cache
def plant_view(seed: int, n_units: int) -> PlantView:
    """Generate the plant once and write its plan to the graph oracle too."""
    generated = generate_plant_v2(GeneratorConfigV2(seed=seed, n_units=n_units))
    oracle = GraphPlantBuilderV2(generated.plan.config.plant_id)
    generated.plan.write(oracle)
    roles: dict[str, str] = {}
    for unit in generated.plan.units:
        roles.update(unit.instance.plan.roles)
    return PlantView(generated=generated, graph=oracle.graph, roles=roles)


# ---- walking the piping --------------------------------------------------------------------------


def _is_equipment(graph: nx.DiGraph[str], node_id: str) -> bool:
    return graph.nodes[node_id]["node_class"] in EQUIPMENT_CLASSES


def flow(graph: nx.DiGraph[str]) -> nx.DiGraph[str]:
    """Only the piping edges (`send_to`)."""
    return nx.DiGraph(
        (s, t) for s, t, d in graph.edges(data=True) if d["relation"] == Relation.SEND_TO.value
    )


def reach(
    piping: nx.DiGraph[str], graph: nx.DiGraph[str], start: str, up: bool
) -> tuple[set[str], set[str]]:
    """What `start` reaches along the pipes without passing equipment: (parts, equipment found).

    `up` walks against the flow (the suction side of a pump), otherwise with it (the discharge).
    """
    step = piping.predecessors if up else piping.successors
    parts: set[str] = set()
    equipment: set[str] = set()
    seen, queue = {start}, deque([start])
    while queue:
        for nxt in step(queue.popleft()):
            if nxt in seen:
                continue
            seen.add(nxt)
            (equipment if _is_equipment(graph, nxt) else parts).add(nxt)
            if nxt in parts:
                queue.append(nxt)
    return parts, equipment


def comes_before(piping: nx.DiGraph[str], graph: nx.DiGraph[str], first: str, second: str) -> bool:
    """True when `second` lies downstream of `first` on the pipes, without passing equipment.

    Plain `nx.has_path` is not enough: a recycle line loops through a vessel back to the pump.
    """
    return second in reach(piping, graph, first, up=False)[0]


def _pumps(view: PlantView, classes: Iterable[str]) -> list[str]:
    wanted = set(classes)
    return sorted(n for n, d in view.graph.nodes(data=True) if d["node_class"] in wanted)


def _with_role(view: PlantView, nodes: Iterable[str], role: str) -> list[str]:
    return sorted(n for n in nodes if view.roles.get(n) == role)


# ---- S1-S3: pumps --------------------------------------------------------------------------------


def check_s1(view: PlantView) -> int:
    """S1: a centrifugal pump draws through a block valve, then a strainer (rule L2)."""
    piping, checked = flow(view.graph), 0
    for pump in _pumps(view, [CENTRIFUGAL_PUMP]):
        upstream, vessels = reach(piping, view.graph, pump, up=True)
        if not vessels:
            continue  # fed from an open line: nothing upstream to check
        blocks = _with_role(view, upstream, "suction_block")
        strainers = _with_role(view, upstream, "suction_strainer")
        in_order = [
            (b, s) for b in blocks for s in strainers if comes_before(piping, view.graph, b, s)
        ]
        assert in_order, f"{pump}: no block valve followed by a strainer on its suction"
        assert all(view.graph.nodes[b]["node_class"] in _BLOCK_VALVES for b, _ in in_order), pump
        checked += 1
    return checked


def check_s2(view: PlantView) -> int:
    """S2: every pump's discharge runs gauge tap, check valve, block valve (rules L1, L3)."""
    piping, checked = flow(view.graph), 0
    for pump in _pumps(view, _PUMPS):
        downstream, _ = reach(piping, view.graph, pump, up=False)
        (check,) = _with_role(view, downstream, "discharge_check")
        assert view.graph.nodes[check]["node_class"] in _CHECK_VALVES, pump
        blocks = _with_role(view, downstream, "discharge_block")
        assert blocks and all(comes_before(piping, view.graph, check, b) for b in blocks), pump
        for tap in _with_role(view, downstream, "pressure_gauge_tee"):
            assert not comes_before(piping, view.graph, check, tap), f"{pump}: tap after check"
        checked += 1
    return checked


def check_s3(view: PlantView) -> int:
    """S3: a positive-displacement pump has a relief from before its check valve to its suction."""
    piping, checked = flow(view.graph), 0
    for pump in _pumps(view, POSITIVE_DISPLACEMENT_PUMPS):
        upstream, _ = reach(piping, view.graph, pump, up=True)
        downstream, _ = reach(piping, view.graph, pump, up=False)
        (relief,) = _with_role(view, upstream & downstream, "pd_relief_valve")
        (start,) = piping.predecessors(relief)
        (end,) = piping.successors(relief)
        (check,) = _with_role(view, downstream, "discharge_check")
        assert start in downstream and not comes_before(piping, view.graph, check, start), pump
        assert end in upstream, f"{pump}: the relief does not return to the suction line"
        checked += 1
    return checked


# ---- S5, S6 --------------------------------------------------------------------------------------


def check_s5(view: PlantView) -> int:
    """S5: a control-valve station is two block valves and a bypass between two tees (rule L9)."""
    piping, checked = flow(view.graph), 0
    for bypass in sorted(n for n, r in view.roles.items() if r == "cv_bypass_valve"):
        (tee_in,) = piping.predecessors(bypass)
        (tee_out,) = piping.successors(bypass)
        assert view.roles[tee_in] == "cv_tee_in" and view.roles[tee_out] == "cv_tee_out", bypass
        paths = [p for p in nx.all_simple_paths(piping, tee_in, tee_out) if bypass not in p]
        assert len(paths) == 1, f"{bypass}: expected one main path beside the bypass, got {paths}"
        main = paths[0]
        assert view.roles[main[1]] == "cv_block_in" and view.roles[main[-2]] == "cv_block_out", (
            bypass
        )
        assert sum(view.roles.get(n) == "control_valve_body" for n in main) == 1, bypass
        checked += 1
    return checked


def check_s6(view: PlantView) -> int:
    """S6: a vessel or column reaches a safety valve over pipes alone (L11); drain pot exempt."""
    piping, checked = flow(view.graph), 0
    for vessel, data in sorted(view.graph.nodes(data=True)):
        if data["node_class"] not in PSV_VESSEL_CLASSES or view.roles.get(vessel) == S6_EXEMPT_ROLE:
            continue
        assert _reaches_safety_valve(view.graph, piping, vessel), f"{vessel}: no safety valve"
        checked += 1
    return checked


def _reaches_safety_valve(graph: nx.DiGraph[str], piping: nx.DiGraph[str], vessel: str) -> bool:
    seen, queue = {vessel}, deque([vessel])
    while queue:
        for nxt in piping.successors(queue.popleft()):
            if graph.nodes[nxt]["node_class"].endswith("SafetyValve"):
                return True
            if nxt not in seen and not _is_equipment(graph, nxt):
                seen.add(nxt)
                queue.append(nxt)
    return False


# ---- S10: line numbers ---------------------------------------------------------------------------


def check_s10(view: PlantView) -> int:
    """S10: line numbers parse, none repeats in the plant, and a spec break changes the spec."""
    numbers: list[str] = []
    for unit in view.generated.plan.units:
        for line in unit.instance.plan.lines:
            numbers += line.line_numbers
            if line.line_number_after_break is not None:
                before, after = (parse_line_number(n) for n in line.line_numbers)
                assert before and after and before.spec != after.spec, line.line_numbers
    assert len(numbers) == len(set(numbers)), "a line number is used twice"
    assert all(parse_line_number(number) is not None for number in numbers)
    return len(numbers)


# ---- S11, S12: spare sets and wiring -------------------------------------------------------------


def check_s11(view: PlantView) -> int:
    """S11: the members of a spare set share class, role and unit and sit in parallel (rule L8).

    Parallel: each member has the same equipment next to it on both sides, and none is fed by
    another. The minimum-flow recycle of the duty pump is left out: only that pump has one.
    """
    piping = _without_recycles(view, flow(view.graph))
    records = view.generated.record.spare_sets
    for record in records:
        members = record.node_ids
        classes = {view.graph.nodes[n]["node_class"] for n in members}
        assert len(classes) == 1, f"{members}: classes {sorted(classes)}"
        assert {view.roles[n] for n in members} == {record.role}, members
        assert {view.graph.nodes[n]["unit_id"] for n in members} == {str(record.unit_no)}, members
        for up in (True, False):
            sides = [reach(piping, view.graph, n, up)[1] for n in members]
            assert all(side == sides[0] for side in sides), f"{members}: not parallel (up={up})"
            assert not any(m in side for m, side in zip(members, sides, strict=True)), members
    return len(records)


def _without_recycles(view: PlantView, piping: nx.DiGraph[str]) -> nx.DiGraph[str]:
    rest = piping.copy()
    rest.remove_nodes_from([n for n, role in view.roles.items() if role in _MIN_FLOW_ROLES])
    return rest


def check_s12(view: PlantView) -> int:
    """S12: gas never wires into a liquid in-port; a pump feeds its suction only by recycle."""
    return _check_phases(view) + _check_no_pump_loops(view)


def _check_phases(view: PlantView) -> int:
    out_phase = {
        port.node_id: port.phase
        for unit in view.generated.plan.units
        for port in unit.instance.ports
        if port.direction is PortDirection.OUT
    }
    checked = 0
    for unit in view.generated.plan.units:
        lines = {line.line_number: line for line in unit.instance.plan.lines}
        for port in unit.instance.ports:
            source = lines[port.line_number].src_id
            if port.direction is PortDirection.OUT or source not in out_phase:
                continue
            assert out_phase[source] is port.phase, f"{source} -> {port.name}: gas meets liquid"
            checked += 1
    return checked


def _check_no_pump_loops(view: PlantView) -> int:
    piping, checked = flow(view.graph), 0
    only_pipes = _without_recycles(view, piping)
    for pump in _pumps(view, _PUMPS):
        for vessel in reach(piping, view.graph, pump, up=True)[1] - {pump}:
            blocked = {n for n in only_pipes if _is_equipment(view.graph, n)} - {pump, vessel}
            rest = only_pipes.subgraph(set(only_pipes) - blocked)
            assert not nx.has_path(rest, pump, vessel), f"{pump} discharges to its suction {vessel}"
            checked += 1
    return checked
