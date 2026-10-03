"""A hand-built `ItemGraph` for the primitive tests: items and edges stated by name.

Flow (`send_to`), with sheets in brackets; `~` marks an off-page crossing:

    T1[S1] -> BV1[S1] ~ P1[S2] -> CHV[S2] -> V1[S2] ~ BV1   (a cycle through the check valve)
    P1[S2] -> GV2[S2] ~ V2[S3]                               (a branch into unit 2)
    T1 -measured_by-> FT -send_signal_to-> FIC -send_signal_to-> FV -control-> BV1   (signals)

`BV1` and `GV2` are operated valves, `CHV` is a check valve (not operated).
"""

from __future__ import annotations

from plantgraph.graph import schema
from plantgraph.qa.plant_api.item_graph import ItemGraph
from plantgraph.qa.plant_api.model import ItemEdge, ItemRecord, ItemRelation
from plantgraph.qa.plant_api.primitives import PlantApi
from plantgraph.qa.plant_api.results import ItemSet, Subgraph
from plantgraph.qa.scoring import normalize_scalar

NC = schema.NodeClass

ItemSpecs = dict[str, tuple[str, str | None, tuple[str, ...]]]
EdgeSpecs = list[tuple[str, ItemRelation, str, tuple[str, ...]]]

#: tag -> (node class, unit, sheets)
_ITEMS: ItemSpecs = {
    "T1": (NC.TANK.value, "1", ("S1",)),
    "BV1": (NC.BALL_VALVE.value, "1", ("S1",)),
    "P1": (NC.CENTRIFUGAL_PUMP.value, "1", ("S2",)),
    "CHV": (NC.CHECK_VALVE.value, "1", ("S2",)),
    "V1": (NC.PRESSURE_VESSEL.value, "1", ("S2",)),
    "GV2": (NC.GLOBE_VALVE.value, "2", ("S2",)),
    "V2": (NC.PRESSURE_VESSEL.value, "2", ("S3",)),
    "FT": (NC.PROCESS_SIGNAL_GENERATING_FUNCTION.value, "1", ("S1",)),
    "FIC": (NC.PROCESS_INSTRUMENTATION_FUNCTION.value, "1", ("S1",)),
    "FV": (NC.ACTUATING_FUNCTION.value, "1", ("S1",)),
}
#: (source tag, relation, target tag, off-page stubs crossed)
_EDGES: EdgeSpecs = [
    ("T1", "send_to", "BV1", ()),
    ("BV1", "send_to", "P1", ("S1:out1", "S2:in1")),
    ("P1", "send_to", "CHV", ()),
    ("CHV", "send_to", "V1", ()),
    ("V1", "send_to", "BV1", ("S2:out3", "S1:in3")),
    ("P1", "send_to", "GV2", ()),
    ("GV2", "send_to", "V2", ("S2:out2", "S3:in2")),
    ("T1", "measured_by", "FT", ()),
    ("FT", "send_signal_to", "FIC", ()),
    ("FIC", "send_signal_to", "FV", ()),
    ("FV", "control", "BV1", ()),
]


def item_id(tag: str) -> str:
    """The toy's opaque id for a tag (never shown to a model; tests check that)."""
    return f"id-{tag.lower()}"


def build_graph(items: ItemSpecs, edges: EdgeSpecs) -> ItemGraph:
    """An `ItemGraph` from tag-keyed specs shaped like `_ITEMS` and `_EDGES`."""
    records = [
        ItemRecord(
            item_id=item_id(tag),
            tag=tag,
            node_class=node_class,
            labels=schema.labels_for(node_class),
            unit_id=unit,
            sheets=sheets,
            occurrence_keys=(f"{sheets[0]}:{tag.lower()}",),
            properties={"tag": tag},
        )
        for tag, (node_class, unit, sheets) in items.items()
    ]
    item_edges = [
        ItemEdge(source=item_id(a), target=item_id(b), relation=relation, via=via)
        for a, relation, b, via in edges
    ]
    ids_by_tag = {normalize_scalar(tag): (item_id(tag),) for tag in items}
    return ItemGraph(records, item_edges, ids_by_tag)


def toy_graph() -> ItemGraph:
    return build_graph(_ITEMS, _EDGES)


def toy_api(max_items: int = 50) -> PlantApi:
    return PlantApi(toy_graph(), max_items=max_items)


def set_tags(result: ItemSet) -> list[str | None]:
    """The tags of an `ItemSet`'s listed items, in result order."""
    return [item.tag for item in result.items]


def member_tags(result: Subgraph) -> list[str | None]:
    """The tags of a `Subgraph`'s members, in result order (start items excluded)."""
    return [member.item.tag for member in result.members]
