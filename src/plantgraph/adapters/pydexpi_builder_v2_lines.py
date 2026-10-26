"""Pipe runs for the v2 DEXPI builder: inline parts, the pipes between them, the line list.

Terms: a **piping network system** is one line (one line number) in DEXPI; it holds a **segment**,
the ordered run of parts (valves, tees, flow elements) joined by **pipes**. A pipe has a source and
a target; an **open end** is a pipe with nothing attached on that side (the line enters or leaves
the drawing there). The **line list** is the plant's table of lines: size, service, pipe class,
insulation. `PipingNetworkSystem` carries those columns (design generator-v2-realism.md section 5).
"""

from __future__ import annotations

from typing import cast

import pydexpi.dexpi_classes.pydantic_classes as dexpi
from pydexpi.toolkits import piping_toolkit as piping

from plantgraph.benchmark.v2.plan_models import LineItemSpec
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.graph import schema


def dexpi_class_named(node_class: str) -> type[dexpi.DexpiBaseModel]:
    """The pyDEXPI class with the schema's `node_class` name."""
    cls = getattr(dexpi, node_class, None)
    if cls is None:
        raise ValueError(f"pydexpi has no class named {node_class!r}; check graph.schema.NodeClass")
    return cast(type[dexpi.DexpiBaseModel], cls)


def create_line_item(spec: LineItemSpec, fluid_code: str) -> dexpi.PipingNetworkSegmentItem:
    """One inline part, with its printed tag in the field its pyDEXPI class uses for it.

    A `PropertyBreak` (where the pipe spec changes) is not a pyDEXPI `PipingComponent` but sits
    in the segment like one; it has no fluid code and no tag.
    """
    _require_inline_class(spec)
    cls = dexpi_class_named(spec.node_class)
    fields: dict[str, str] = {}
    if "fluidCode" in cls.model_fields:
        fields["fluidCode"] = fluid_code
    if spec.tag is not None:
        fields[_tag_field(cls, spec)] = spec.tag
    return cast(dexpi.PipingNetworkSegmentItem, cls(id=spec.node_id, **fields))


def _require_inline_class(spec: LineItemSpec) -> None:
    if spec.node_class not in schema.PIPING_CLASSES:
        raise ValueError(
            f"expected a piping class for inline item {spec.node_id!r}, got {spec.node_class!r}"
        )


def _tag_field(cls: type[dexpi.DexpiBaseModel], spec: LineItemSpec) -> str:
    """Safety devices keep their number in `positionNumber`, other parts in the component one."""
    for name in ("positionNumber", "pipingComponentNumber"):
        if name in cls.model_fields:
            return name
    raise ValueError(f"{spec.node_class} has no tag field, but item {spec.node_id!r} has a tag")


def line_list_fields(line_number: str) -> dict[str, str]:
    """The line-list columns a line number encodes: number, pipe class, size, insulation."""
    parsed = parse_line_number(line_number)
    if parsed is None:
        raise ValueError(
            "expected a line number SIZE-SERVICE-UNITSEQUENCE-SPEC-INSULATION "
            f"(for example 6-P-120017-A1A-N), got {line_number!r}"
        )
    return {
        "lineNumber": line_number,
        "pipingClassCode": parsed.spec,
        "nominalDiameterRepresentation": str(parsed.size),
        "insulationType": parsed.insulation,
    }


def build_line_system(
    stream_id: str,
    fluid_code: str,
    section: dexpi.PlantSection,
    line_list: dict[str, str],
    items: list[dexpi.PipingNetworkSegmentItem],
    source: dexpi.Nozzle | dexpi.PipingNetworkSegmentItem | None,
    target: dexpi.Nozzle | dexpi.PipingNetworkSegmentItem | None,
) -> dexpi.PipingNetworkSystem:
    """One system with one segment: `source`, the `items` in order, `target`.

    `line_list` is the output of `line_list_fields`.

    `source` / `target` are a nozzle, an inline part of another line (a tee: a branch or a merge; a
    valve: the join to another unit) or None (open end). pyDEXPI raises `IndexError` if the first
    *item* of this line is named as the source, so an open start is passed as None and the first
    pipe is left dangling.
    """
    # pipes between the ends and the items: always one more than there are items
    pipes: list[dexpi.PipingConnection] = [
        dexpi.Pipe(id=f"{stream_id}-pp{number}") for number in range(1, len(items) + 2)
    ]
    segment_items: list[dexpi.PipingNetworkSegmentItem] = list(items)
    # pyDEXPI's hints leave out its own None default for an open end, hence the ignores
    segment = piping.construct_new_segment(
        segment_items,
        pipes,
        source_connector_item=source,  # type: ignore[arg-type]
        target_connector_item=target,  # type: ignore[arg-type]
        connectivity_convention=piping.PipingConnectionConvention.USE_ITEMS,
        id=f"{stream_id}-sg",
        fluidCode=fluid_code,
    )
    return dexpi.PipingNetworkSystem(
        id=f"{stream_id}-ps",
        fluidCode=fluid_code,
        segments=[segment],
        parentStructure=section,
        **line_list,
    )
