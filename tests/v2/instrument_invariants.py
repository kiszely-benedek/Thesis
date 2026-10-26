"""Invariants S4, S7, S8, S9, S22 (design realism 12.2, pid-vocabulary 8) as graph checks.

Not a test module (no `test_` prefix). Each `check_*` takes the plant graph and raises
`AssertionError` naming the offending node, so a failure says what to look at. They read only the
graph (tags, classes, `loop_tag`, edges), as a question about the drawing would.
"""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.v2.tags import ParsedTag, parse_tag
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES, Relation

_PSGF = "ProcessSignalGeneratingFunction"
_PIF = "ProcessInstrumentationFunction"
_PCF = "ProcessControlFunction"
_AF = "ActuatingFunction"
_AEF = "ActuatingElectricalFunction"
_BUBBLES = {_PIF, _PCF}
#: bubbles that read two sensors: the ratio controller and the multivariable controller
_TWO_SENSOR_LETTERS = {"FFIC", "UC"}


def _parsed(graph: nx.DiGraph[str], node_id: str) -> ParsedTag:
    parsed = parse_tag(graph.nodes[node_id].get("tag") or "")
    assert parsed is not None, f"{node_id}: tag {graph.nodes[node_id].get('tag')!r} does not parse"
    return parsed


def _neighbours(
    graph: nx.DiGraph[str], node_id: str, relation: Relation, incoming: bool
) -> list[str]:
    edges = graph.in_edges(node_id, data=True) if incoming else graph.out_edges(node_id, data=True)
    return sorted(
        (s if incoming else t) for s, t, data in edges if data["relation"] == relation.value
    )


def _of_class(graph: nx.DiGraph[str], *node_classes: str) -> list[str]:
    return sorted(n for n, d in graph.nodes(data=True) if d["node_class"] in node_classes)


def check_s4(graph: nx.DiGraph[str]) -> int:
    """S4: every AF `control` target is a valve body whose tag shares the loop's number.

    A control valve is `<variable>V` for the loop's variable; an on-off valve is `XV` or `YV`.
    Returns the number of AFs checked.
    """
    actuators = _of_class(graph, _AF)
    for actuator in actuators:
        (valve,) = _neighbours(graph, actuator, Relation.CONTROL, incoming=False)
        assert graph.nodes[valve]["node_class"] in CONTROL_VALVE_BODY_CLASSES, valve
        loop = parse_tag(graph.nodes[actuator]["loop_tag"])
        assert loop is not None, f"{actuator}: loop tag does not parse"
        parsed = _parsed(graph, valve)
        kind = item_kind(graph.nodes[valve]["node_class"], parsed.letters)
        assert kind in (ItemKind.CONTROL_VALVE, ItemKind.ON_OFF_VALVE), f"{valve}: {kind}"
        if kind is ItemKind.CONTROL_VALVE:
            assert parsed.letters == f"{loop.first}V", f"{valve} is not the {loop.letters} valve"
        assert parsed.sequence == loop.sequence, f"{valve} does not share {loop.letters}'s number"
    return len(actuators)


def check_s7(graph: nx.DiGraph[str], solenoid_of: dict[str, str | None]) -> int:
    """S7: every XV is driven by a trip switch or an HS, and has an `XY-n` solenoid in the model.

    `solenoid_of` maps a valve id to the sub-tag of its solenoid in the DEXPI model.
    Returns the number of on-off valves checked.
    """
    valves = [n for n in _of_class(graph, *CONTROL_VALVE_BODY_CLASSES) if _is_on_off(graph, n)]
    for valve in valves:
        (actuator,) = _neighbours(graph, valve, Relation.CONTROL, incoming=True)
        (driver,) = _neighbours(graph, actuator, Relation.SEND_SIGNAL_TO, incoming=True)
        letters = _parsed(graph, driver).letters
        assert letters == "HS" or "S" in letters[1:], f"{valve} is driven by {letters}, not a trip"
        tag = _parsed(graph, valve)
        assert solenoid_of.get(valve) == f"{tag.first}Y-{graph.nodes[valve]['tag'][3:]}", valve
    return len(valves)


def _is_on_off(graph: nx.DiGraph[str], node_id: str) -> bool:
    parsed = parse_tag(graph.nodes[node_id].get("tag") or "")
    if parsed is None:
        return False
    kind = item_kind(graph.nodes[node_id]["node_class"], parsed.letters)
    return kind is ItemKind.ON_OFF_VALVE


def check_s8(graph: nx.DiGraph[str]) -> int:
    """S8: each loop is one PSGF, one bubble, [one AF, one valve]; members share the number.

    Exceptions are the loops that read two sensors (ratio, multivariable) and a hand switch,
    which senses nothing. Returns the number of bubbles checked.
    """
    for bubble in _of_class(graph, *_BUBBLES):
        letters = _parsed(graph, bubble).letters
        loop_tag = graph.nodes[bubble]["tag"]
        sensors = [
            n
            for n in _neighbours(graph, bubble, Relation.SEND_SIGNAL_TO, incoming=True)
            if graph.nodes[n]["node_class"] == _PSGF
        ]
        expected = 0 if letters == "HS" else 2 if letters in _TWO_SENSOR_LETTERS else 1
        assert len(sensors) == expected, f"{bubble} ({letters}) reads {len(sensors)} sensors"
        outputs = _neighbours(graph, bubble, Relation.SEND_SIGNAL_TO, incoming=False)
        actuators = [n for n in outputs if graph.nodes[n]["node_class"] in (_AF, _AEF)]
        assert len(actuators) <= 1, f"{bubble} drives {len(actuators)} actuators"
        for member in [*sensors, *actuators]:
            assert graph.nodes[member]["loop_tag"] == loop_tag, f"{member} is not in {loop_tag}"
        for sensor in sensors:
            assert _parsed(graph, sensor).sequence == _parsed(graph, bubble).sequence, sensor
    return len(_of_class(graph, *_BUBBLES))


def check_s9(graph: nx.DiGraph[str]) -> int:
    """S9: tags are unique, parse, and their letters agree with the node's class.

    Also: a PCF's letters end in `C`. Returns the number of tags checked.
    """
    seen: set[str] = set()
    for node_id, data in sorted(graph.nodes(data=True)):
        tag = data.get("tag")
        if tag is None:
            continue
        assert tag not in seen, f"tag {tag} is used twice"
        seen.add(tag)
        letters = _parsed(graph, node_id).letters
        item_kind(data["node_class"], letters)  # raises when class and letters disagree
        if data["node_class"] == _PCF:
            assert letters.endswith("C"), f"{node_id}: controller letters {letters!r}"
    return len(seen)


def check_s22(graph: nx.DiGraph[str]) -> int:
    """S22: a cascade slave has one PSGF and one PCF in front of it and its valve has its number.

    A slave is a PCF with a PCF predecessor; its master must be fed by a PSGF of its own.
    Returns the number of slaves checked.
    """
    slaves = []
    for controller in _of_class(graph, _PCF):
        feeders = _neighbours(graph, controller, Relation.SEND_SIGNAL_TO, incoming=True)
        masters = [n for n in feeders if graph.nodes[n]["node_class"] == _PCF]
        if not masters:
            continue
        sensors = [n for n in feeders if graph.nodes[n]["node_class"] == _PSGF]
        assert len(masters) == 1 and len(sensors) == 1, f"{controller}: feeders {feeders}"
        master_sensors = _neighbours(graph, masters[0], Relation.SEND_SIGNAL_TO, incoming=True)
        assert len(master_sensors) == 1, f"master {masters[0]} has sensors {master_sensors}"
        assert _valve_numbers(graph, controller) == {_parsed(graph, controller).sequence}
        slaves.append(controller)
    return len(slaves)


def _valve_numbers(graph: nx.DiGraph[str], controller: str) -> set[int]:
    """The tag numbers of the valves the controller moves through its actuators."""
    actuators = _neighbours(graph, controller, Relation.SEND_SIGNAL_TO, incoming=False)
    valves = [v for a in actuators for v in _neighbours(graph, a, Relation.CONTROL, incoming=False)]
    assert valves, f"{controller} moves no valve"
    return {_parsed(graph, valve).sequence for valve in valves}
