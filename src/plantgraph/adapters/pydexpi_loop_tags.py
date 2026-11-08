"""Loop tags: which control loop each instrument node belongs to, and local instruments.

A **loop** is a sensor, the bubble that reads it and the actuator that acts on it; every member
carries the bubble's tag as `loop_tag` and the tag's first letter (`F` for flow) as
`measured_variable`; a tagged sensor keeps its own first letter (a `UC`'s `TT` measures T).

A **local instrument** is a gauge or indicator drawn as one bubble with one tag (design convention
I-2). pyDEXPI reaches a sensor (`ProcessSignalGeneratingFunction`) only through a bubble
(`ProcessInstrumentationFunction`), so the v2 builder wraps a local sensor in an untagged
**carrier** bubble. The graph shows one node per drawn bubble, so the adapter leaves the carrier
out and treats the sensor as its own loop.
"""

from __future__ import annotations

from collections.abc import Mapping

import networkx as nx

from plantgraph.graph.schema import NodeClass

#: the classes of a bubble: an indicator, switch or alarm, or a controller (`PCF`, v2)
BUBBLE_CLASSES = frozenset(
    {NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value, NodeClass.PROCESS_CONTROL_FUNCTION.value}
)
#: what a bubble pulls into its loop; another bubble is never pulled in, because in a cascade the
#: master and the slave are two loops that happen to be wired together
_LOOP_MEMBER_CLASSES = frozenset(
    {
        NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value,
        NodeClass.ACTUATING_FUNCTION.value,
        NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value,  # a machine's start/stop joins its HS's loop
    }
)
#: pyDEXPI edge labels that carry a signal (a measurement or a command) between instruments
SIGNAL_LABELS = frozenset(
    {"MeasuringLineFunction", "SignalLineFunction", "SignalConveyingFunction"}
)
_BUBBLE_LABEL = NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
_TAG_FIELDS = (
    "processInstrumentationFunctionCategory",
    "processInstrumentationFunctionModifier",
    "processInstrumentationFunctionNumber",
    "processInstrumentationFunctions",
)


def assign_loop_tags(plant: nx.DiGraph[str]) -> None:
    """Write each bubble's tag onto itself and its sensor/actuator neighbours as `loop_tag`."""
    for node_id in sorted(plant.nodes):
        if plant.nodes[node_id]["node_class"] not in BUBBLE_CLASSES:
            continue
        loop_tag = plant.nodes[node_id].get("tag")  # an untagged bubble has no tag key
        variable = loop_tag[0] if loop_tag else None
        neighbours = [*plant.predecessors(node_id), *plant.successors(node_id)]
        members = [node_id] + [
            member
            for member in neighbours
            if plant.nodes[member]["node_class"] in _LOOP_MEMBER_CLASSES
        ]
        for member in members:
            plant.nodes[member]["loop_tag"] = loop_tag
            plant.nodes[member]["measured_variable"] = _variable_of(plant, member, variable)


def _variable_of(plant: nx.DiGraph[str], member: str, loop_variable: str | None) -> str | None:
    """A sensor's own tag letter wins: the `TT` and `PT` feeding a `UC` measure T and P, not U."""
    attrs = plant.nodes[member]
    own_tag = attrs.get("tag")
    is_sensor = attrs["node_class"] == NodeClass.PROCESS_SIGNAL_GENERATING_FUNCTION.value
    return own_tag[0] if is_sensor and own_tag else loop_variable


def find_carrier_sensors(conceptual: nx.MultiDiGraph[str]) -> dict[str, list[str]]:
    """Carrier bubble id -> ids of the sensors it holds.

    A carrier is a bubble with no tag field that signals nowhere: a bubble that sends a signal
    onward is a real instrument whose tag is merely missing, so it stays a node.
    """
    sends_signal = {
        source
        for source, _, attrs in conceptual.edges(data=True)
        if attrs.get("label") in SIGNAL_LABELS
    }
    sensors: dict[str, list[str]] = {
        node_id: []
        for node_id in sorted(conceptual.nodes)
        if _is_carrier(conceptual.nodes[node_id]) and node_id not in sends_signal
    }
    for source, target, attrs in conceptual.edges(data=True):
        if target in sensors and attrs.get("label") == "MeasuringLineFunction":
            sensors[target].append(source)
    return sensors


def _is_carrier(attrs: Mapping[str, object]) -> bool:
    has_tag_field = any(field in attrs for field in _TAG_FIELDS)
    return attrs.get("label") == _BUBBLE_LABEL and not has_tag_field


def assign_local_loop_tags(plant: nx.DiGraph[str], sensor_ids: list[str]) -> None:
    """A local sensor is its own loop: `loop_tag` is its tag, the variable its first letter."""
    for sensor_id in sensor_ids:
        tag = plant.nodes[sensor_id].get("tag")
        if tag is None:
            continue  # an untagged sensor has nothing to name its loop
        plant.nodes[sensor_id]["loop_tag"] = tag
        plant.nodes[sensor_id]["measured_variable"] = tag[0]
