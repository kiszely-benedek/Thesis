"""Writing the reference of a scope X question: each valve as its tag or as a descriptor (R8).

A reference is a sorted `list[str]`. A valve that prints a tag is that tag; a valve that prints none
is `encode_descriptor(canonical_descriptor(...))` (`qa/v2tb/descriptor.py`). A valve with no unique
descriptor cannot be named, and the question that needs it is refused rather than reworded.
"""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.v2tb.descriptor import PlantIndex, canonical_descriptor, encode_descriptor
from plantgraph.qa.v2tb.scoring_b import reference_nodes


class NamedValves(BaseModel):
    """The valves of one gold answer, written as reference items."""

    model_config = ConfigDict(frozen=True)

    #: sorted items: a tag as printed, or an encoded descriptor
    reference: list[str]
    #: untagged valves that have no unique descriptor (empty when the reference is complete)
    unnameable: tuple[str, ...]
    #: whether at least one valve of the answer prints no tag
    holds_untagged: bool


def name_valves(index: PlantIndex, valve_ids: Iterable[str]) -> NamedValves:
    """Write each valve as a tag or a descriptor; collect the ones that cannot be named."""
    items: list[str] = []
    unnameable: list[str] = []
    holds_untagged = False
    for valve_id in sorted(valve_ids):
        tag = index.tag_of(valve_id)
        if tag is not None:
            items.append(tag)
            continue
        holds_untagged = True
        descriptor = canonical_descriptor(index, valve_id)
        if descriptor is None:
            unnameable.append(valve_id)
        else:
            items.append(encode_descriptor(descriptor))
    return NamedValves(
        reference=sorted(items), unnameable=tuple(unnameable), holds_untagged=holds_untagged
    )


def require_round_trip(index: PlantIndex, named: NamedValves, valve_ids: Iterable[str]) -> None:
    """The self-test of R8: the reference resolves to exactly the gold valves.

    Raises:
        ValueError: the reference names other nodes than the gold valves (a bug on the gold side).
    """
    expected = frozenset(valve_ids)
    found = reference_nodes(index, named.reference)
    if found != expected:
        raise ValueError(
            f"expected the reference {named.reference!r} to name {sorted(expected)}, "
            f"found {sorted(found)}"
        )
