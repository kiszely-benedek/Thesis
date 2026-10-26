"""Which unit (process section) each piping node belongs to.

A **unit** is one process section of the plant (`PlantSection`). Equipment and instruments name it
in their `parentStructure`; an inline piping part does not, so the adapter has to find it:

- **v1 rule** (`assign_valve_units`): a valve takes the unit of the equipment upstream of it.
- **v2 rule** (`read_piping_units` + `assign_piping_units`): every part of a line takes the unit of
  its `PipingNetworkSystem`'s parent. Needed because a v2 line can start open or at a pipe tee, so
  "walk upstream to the equipment" has no single answer.
"""

from __future__ import annotations

from collections.abc import Mapping

import networkx as nx
from pydexpi.dexpi_classes.pydantic_classes import DexpiModel, PipingNetworkSystem, PlantSection

from plantgraph.graph import schema


def assign_valve_units(plant: nx.DiGraph[str]) -> int:
    """A valve has no DEXPI `parentStructure`; it inherits `unit_id` by walking towards its source.

    (§3.6: "owned by the source's unit")
    """
    unresolved = 0
    for node_id in sorted(plant.nodes):
        if plant.nodes[node_id]["node_class"] not in schema.VALVE_CLASSES:
            continue
        owner = _walk_to_owning_equipment(plant, node_id)
        if owner is None or "unit_id" not in plant.nodes[owner]:
            # the owner has no unit_id either, on a file without a PlantSection (imported EX01,
            # kg-construction.md §2) — this too is an unresolved case, not a KeyError
            unresolved += 1
            continue
        plant.nodes[node_id]["unit_id"] = plant.nodes[owner]["unit_id"]
    return unresolved


def _walk_to_owning_equipment(plant: nx.DiGraph[str], node_id: str) -> str | None:
    """Walk backward along the `send_to` chain from a valve until it reaches equipment."""
    current = node_id
    while plant.nodes[current]["node_class"] in schema.VALVE_CLASSES:
        upstream = [
            source
            for source, _, attrs in plant.in_edges(current, data=True)
            if attrs["relation"] == schema.Relation.SEND_TO.value
        ]
        if len(upstream) != 1:
            return None
        current = upstream[0]
    return current


def read_piping_units(model: DexpiModel) -> dict[str, str]:
    """Piping part id -> unit number, from each line's `PipingNetworkSystem.parentStructure`."""
    if model.conceptualModel is None:
        raise ValueError("model.conceptualModel is None; there are no lines to read")
    units: dict[str, str] = {}
    for system in model.conceptualModel.pipingNetworkSystems:
        unit = _unit_of(system)
        units.update({item_id: unit for item_id in _part_ids(system)})
    return units


def _unit_of(system: PipingNetworkSystem) -> str:
    section = system.parentStructure
    code = section.plantSectionIdentificationCode if isinstance(section, PlantSection) else None
    if code is None:
        raise ValueError(
            f"piping network system {system.id!r} needs a PlantSection parent with an "
            f"identification code, found {type(section).__name__}"
        )
    return code


def _part_ids(system: PipingNetworkSystem) -> list[str]:
    return [item.id for segment in system.segments for item in segment.items]


def assign_piping_units(plant: nx.DiGraph[str], piping_units: Mapping[str, str]) -> None:
    """Write `unit_id` on every piping node from `read_piping_units`; a node without one raises."""
    for node_id in sorted(plant.nodes):
        if plant.nodes[node_id]["node_class"] not in schema.PIPING_CLASSES:
            continue
        if node_id not in piping_units:
            raise ValueError(
                f"piping node {node_id!r} is on no line of the model; expected it among "
                "the items of a PipingNetworkSystem segment"
            )
        plant.nodes[node_id]["unit_id"] = piping_units[node_id]
