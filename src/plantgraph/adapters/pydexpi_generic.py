"""Generic fallback for pyDEXPI classes not in the schema (ADR-0016, `kg-construction.md` §3.1).

A real drawing uses far more pyDEXPI classes than the schema (`graph.schema`)
curates (the 12+4 classes known to the generator and the splitter) — e.g.
`PipeTee`, `BlindFlange`, a reciprocating pump (`ReciprocatingPump`).
`pydexpi_adapter.py` used to silently drop these (`kg-construction.md` §2).
Under ADR-0016, none may be lost: an unknown class gets the `GenericItem`
node_class, keeping its real pyDEXPI class name (`dexpi_class`) and a curated
ancestor-chain prefix (`dexpi_labels`) as ordinary node properties.

This module lives apart from `pydexpi_adapter.py` not because it is a
conceptually different layer, but because that module is already at the
400-line file limit (§3.1 "Where the code lives") — the same situation as
between `graph/schema.py` and `graph/validation.py`.
"""

from __future__ import annotations

import collections
import re
from collections.abc import Iterable, Mapping

import networkx as nx
import pydexpi.dexpi_classes.pydantic_classes as pydexpi_classes
import pydexpi.toolkits.base_model_utils as base_model_utils
from pydantic import BaseModel

# `_relation_of` is private, but this module split off from pydexpi_adapter.py
# only because of the 400-line limit (see the module docstring) — two files of one
# adapter family. Without this import, the related_to conversion (rule 5) would
# have to re-derive the direction-flipping rule (e.g. `measured_by` flips the
# "reference"/"sensingLocation" edge), and would wrongly treat already correctly
# mapped edges as "lost".
from plantgraph.adapters.pydexpi_adapter import _relation_of, topology_node_class
from plantgraph.graph import schema

#: `_map_nodes` deliberately folds these into the structural layer
#: (`pydexpi_adapter.py` docstring) — never a generic node, even though the
#: schema doesn't recognize them either
_STRUCTURE_LABELS = frozenset({"PlantSection", "ProcessPlant"})

#: pyDEXPI ancestor class name -> schema category, treated as the "root" (§3.1 "Label cut-off").
#: Past the root, pyDEXPI's chain runs into mixin classes (`CustomAttributeOwner`, ...), which
#: are not categories — so the walk stops here, not at the end of the chain.
_CATEGORY_ROOTS: dict[str, schema.NodeCategory] = {
    "Equipment": schema.NodeCategory.EQUIPMENT,
    "PipingComponent": schema.NodeCategory.PIPING,
}

#: safe Neo4j label shape — both the curated chain and the fallback's single-item
#: chain are checked against this before the store (T6) ever receives it (§3.1 rule 7)
_LABEL_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9]*$")


class GenericInfo(BaseModel):
    """What a node translated to `GenericItem` keeps of its real pyDEXPI identity."""

    dexpi_class: str
    category: schema.NodeCategory
    labels: tuple[str, ...]


def classify(label: str) -> GenericInfo:
    """Split a pyDEXPI class name into a category and a Neo4j label chain (§3.1 rule 2).

    Walks pyDEXPI's own ancestor chain up to and including the first category
    root (`Equipment` or `PipingComponent`). Without a root, or if `label` isn't
    even a pyDEXPI class name, the category is `other` and the chain is just itself.

    Raises:
        ValueError: if a chain element is not a safe Neo4j label shape.
    """
    dexpi_class = getattr(pydexpi_classes, label, None)
    if dexpi_class is None:
        return GenericInfo(
            dexpi_class=label, category=schema.NodeCategory.OTHER, labels=_checked((label,))
        )
    chain: list[str] = []
    for ancestor in base_model_utils.get_inheritance_from_dexpi_class(dexpi_class):
        chain.append(ancestor.__name__)
        category = _CATEGORY_ROOTS.get(ancestor.__name__)
        if category is not None:
            return GenericInfo(dexpi_class=label, category=category, labels=_checked(tuple(chain)))
    return GenericInfo(
        dexpi_class=label, category=schema.NodeCategory.OTHER, labels=_checked((label,))
    )


def _checked(labels: tuple[str, ...]) -> tuple[str, ...]:
    """Enforce the Neo4j label shape on every chain element — the store (T6) relies on this."""
    for label in labels:
        if not _LABEL_PATTERN.match(label):
            raise ValueError(
                f"{label!r} is not a safe Neo4j label (expected {_LABEL_PATTERN.pattern})"
            )
    return labels


def prepare_generic(
    conceptual: nx.MultiDiGraph[str],
) -> tuple[nx.MultiDiGraph[str], dict[str, GenericInfo]]:
    """Relabel every node that would otherwise be dropped to `GenericItem`, on a copy (§3.1 rule 1).

    Schema-unknown classes thus reach `map_conceptual_graph` as an already known
    class (`GenericItem` is in `schema.IMPORTABLE_CLASSES`), instead of being
    dropped by it. Structural classes (`PlantSection`, `ProcessPlant`) are
    deliberately left untouched — the adapter processes those differently.
    """
    prepared = conceptual.copy()
    infos: dict[str, GenericInfo] = {}
    for node_id, attrs in conceptual.nodes(data=True):
        label = str(attrs.get("label"))
        if label in _STRUCTURE_LABELS or topology_node_class(label) is not None:
            continue
        infos[node_id] = classify(label)
        prepared.nodes[node_id]["label"] = schema.NodeClass.GENERIC_ITEM.value
    return prepared, infos


def annotate_generic(
    plant: nx.DiGraph[str], infos: Mapping[str, GenericInfo], conceptual: nx.MultiDiGraph[str]
) -> None:
    """Write `dexpi_class`/`category`/`dexpi_labels` and the tag onto every generic node.

    Runs between `map_conceptual_graph` and the rename to `proteusId` (§3.1 rule
    4), while node ids still match `infos` and `conceptual`'s keys.
    """
    for node_id, info in infos.items():
        if node_id not in plant.nodes:
            continue  # not dropped by this fallback — excluded for another reason (future rule?)
        attrs = plant.nodes[node_id]
        attrs["dexpi_class"] = info.dexpi_class
        attrs["category"] = info.category.value
        attrs["dexpi_labels"] = list(info.labels)
        attrs["tag"] = _generic_tag(info.category, conceptual.nodes[node_id])


def _generic_tag(category: schema.NodeCategory, source_attrs: Mapping[str, object]) -> str | None:
    """Tagging rule per category (§3.1 rule 3) — the same attribute `_tag_of` also reads.

    Within the piping category, a safety valve has no `pipingComponentNumber`, only a
    `positionNumber` (e.g. EX01's "SV 104.01" — a gap found while probing the file,
    `kg-construction.md` §10): without this fallback it would go tag-less, and `resolve()`
    would never find it by tag.
    """
    if category is schema.NodeCategory.EQUIPMENT:
        return _as_str(source_attrs.get("tagName"))
    if category is schema.NodeCategory.PIPING:
        return _as_str(source_attrs.get("pipingComponentNumber")) or _as_str(
            source_attrs.get("positionNumber")
        )
    return None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def add_related_to_edges(
    plant: nx.DiGraph[str], conceptual: nx.MultiDiGraph[str]
) -> tuple[dict[str, int], int]:
    """Add a `related_to` edge for every edge `_map_edges` dropped due to an unknown label.

    Both ends must already be mapped `plant` nodes — an edge with an unreached
    endpoint instead becomes `edges_lost_to_unmapped_endpoints`, a different
    bookkeeping entry (§3.1 rule 5).

    Returns:
        The count of added `related_to` edges by `dexpi_label`, and how many
        pairs were already an edge (`ImportReport.related_to_collapsed`) — in
        that case the duplicate is not added.
    """
    added: collections.Counter[str] = collections.Counter()
    collapsed = 0
    for source, target, attrs in conceptual.edges(data=True):
        if attrs.get("attr_name") == "parentStructure" or _relation_of(attrs) is not None:
            continue  # already resolved another way, or mapped to a known schema relation
        if source not in plant.nodes or target not in plant.nodes:
            continue
        dexpi_label = f"{attrs.get('label')}/{attrs.get('attr_name')}"
        if plant.has_edge(source, target):
            collapsed += 1
            continue
        plant.add_edge(
            source, target, relation=schema.Relation.RELATED_TO.value, dexpi_label=dexpi_label
        )
        added[dexpi_label] += 1
    return dict(added), collapsed


def count_nodes_per_dexpi_class(
    conceptual: nx.MultiDiGraph[str], mapped_ids: Iterable[str]
) -> dict[str, int]:
    """Count every mapped node by its real pyDEXPI class (§3.1 rule 6).

    For both known and generic classes alike — this is the fallback's own
    coverage check: the total must match the conceptual graph's label counts,
    minus the nodes deliberately folded into the structural layer.
    """
    labels = (str(conceptual.nodes[node_id]["label"]) for node_id in mapped_ids)
    return dict(collections.Counter(labels))
