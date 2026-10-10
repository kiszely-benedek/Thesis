"""The plant as one graph of items, built from the resolver's output (design §3.1)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

from plantgraph.graph import schema
from plantgraph.qa.graph_view import GraphView
from plantgraph.qa.graph_view import ItemRecord as OccurrenceRecord  # one drawing of an item
from plantgraph.qa.plant_api.contraction import Contraction, contract
from plantgraph.qa.plant_api.model import (
    RELATION_GROUPS,
    UNRESOLVED_CONNECTOR_CLASS,
    Direction,
    ItemEdge,
    ItemFilter,
    ItemRecord,
    PlantApiError,
    PropertyValue,
    RelationGroup,
)
from plantgraph.qa.scoring import normalize_scalar, normalize_unit_id
from plantgraph.qa.serialize import graphml_safe

#: Home-drawing properties an item keeps; `node_class` is already a field of the record.
_ITEM_PROPERTY_KEYS = schema.VISIBLE_NODE_PROPERTIES - {"node_class"}


class ItemGraph:
    """Items and the edges between them; read-only lookups and one-hop steps."""

    def __init__(
        self,
        items: Iterable[ItemRecord],
        edges: Iterable[ItemEdge],
        ids_by_tag: Mapping[str, tuple[str, ...]],
    ) -> None:
        self._items = {item.item_id: item for item in items}
        self._edges = tuple(sorted(edges, key=lambda e: (e.source, e.target, e.relation)))
        self._ids_by_tag = dict(ids_by_tag)
        self._outgoing: dict[str, list[ItemEdge]] = defaultdict(list)
        self._incoming: dict[str, list[ItemEdge]] = defaultdict(list)
        for edge in self._edges:
            self._outgoing[edge.source].append(edge)
            self._incoming[edge.target].append(edge)
        # folded -> as written, so a refusal can list the values in the spelling a filter accepts
        self._labels = {x.lower(): x for item in self._items.values() for x in item.labels}
        self._classes = {item.node_class.lower(): item.node_class for item in self._items.values()}
        self._units = {normalize_unit_id(u): u for i in self._items.values() if (u := i.unit_id)}
        self._sheets = sorted({sheet for item in self._items.values() for sheet in item.sheets})
        self._item_of_key = {k: i.item_id for i in self._items.values() for k in i.occurrence_keys}

    @property
    def edges(self) -> tuple[ItemEdge, ...]:
        """Every edge, sorted by (source, target, relation)."""
        return self._edges

    @property
    def sheets(self) -> list[str]:
        """Every sheet any item is drawn on, sorted."""
        return list(self._sheets)

    def item(self, item_id: str) -> ItemRecord:
        """The item with this id; raises `PlantApiError` if none."""
        try:
            return self._items[item_id]
        except KeyError:
            raise PlantApiError(f"expected a known item id, found {item_id!r}") from None

    def has_item(self, item_id: str) -> bool:
        """True when `item_id` is an item id (how an untagged item is named)."""
        return item_id in self._items

    def item_of_key(self, local_key: str) -> str | None:
        """The item an occurrence key is a drawing of; `None` for a paired stub, which vanishes."""
        return self._item_of_key.get(local_key)

    def all_ids(self) -> list[str]:
        """Every item id in result order."""
        return sorted(self._items, key=self.sort_key)

    def sort_key(self, item_id: str) -> tuple[str, str]:
        """Order every result by tag, then item id (design §3.3 determinism)."""
        return (self._items[item_id].tag or "", item_id)

    def ids_for_tag(self, tag: str) -> list[str]:
        """Items whose tag or printed name matches `tag` after case/space folding."""
        return sorted(self._ids_by_tag.get(normalize_scalar(tag), ()), key=self.sort_key)

    def steps(
        self, item_id: str, direction: Direction, relations: RelationGroup
    ) -> list[tuple[str, ItemEdge]]:
        """(neighbour id, edge) for each edge leaving `item_id` in `direction`, sorted."""
        allowed = RELATION_GROUPS[relations]
        found: list[tuple[str, ItemEdge]] = []
        if direction in ("downstream", "both"):
            found += [
                (e.target, e) for e in self._outgoing.get(item_id, ()) if e.relation in allowed
            ]
        if direction in ("upstream", "both"):
            found += [
                (e.source, e) for e in self._incoming.get(item_id, ()) if e.relation in allowed
            ]
        return sorted(found, key=lambda step: (*self.sort_key(step[0]), step[1].relation))

    def select(self, where: ItemFilter, among: Iterable[str] | None = None) -> list[str]:
        """Ids matching every set field of `where`, sorted; `among` limits the candidates.

        Raises:
            PlantApiError: `where` names a label, class, unit or sheet the plant lacks.
        """
        self._check_vocabulary(where)
        candidates = self._candidates(where, among)
        matching = [i for i in candidates if self._matches(self._items[i], where)]
        return sorted(matching, key=self.sort_key)

    def _candidates(self, where: ItemFilter, among: Iterable[str] | None) -> Iterable[str]:
        """Start from the tag index when `where` has a tag, so a lookup never scans the plant."""
        pool: set[str] | None = None if among is None else set(among)
        if where.tag is None:
            return self._items if pool is None else pool
        by_tag = self.ids_for_tag(where.tag)
        return by_tag if pool is None else [i for i in by_tag if i in pool]

    @staticmethod
    def _matches(item: ItemRecord, where: ItemFilter) -> bool:
        """Every field except `tag`, which `_candidates` already applied."""
        sheets = {normalize_scalar(sheet) for sheet in item.sheets}
        checks = (
            where.label is None or where.label.lower() in {x.lower() for x in item.labels},
            where.node_class is None or where.node_class.lower() == item.node_class.lower(),
            where.unit is None or _same_unit(where.unit, item.unit_id),
            where.not_unit is None or not _same_unit(where.not_unit, item.unit_id),
            where.sheet is None or normalize_scalar(where.sheet) in sheets,
        )
        return all(checks)

    def _check_vocabulary(self, where: ItemFilter) -> None:
        """Refuse an unknown label, class, unit or sheet, listing the valid values."""
        if where.label is not None:
            self._require_label_or_class("label", where.label, self._labels, self._classes)
        if where.node_class is not None:
            self._require_label_or_class(
                "node_class", where.node_class, self._classes, self._labels
            )
        for unit in (where.unit, where.not_unit):
            if unit is not None:
                _require_known("unit", normalize_unit_id(unit), self._units, unit)
        if where.sheet is not None:
            sheets = {normalize_scalar(sheet): sheet for sheet in self._sheets}
            _require_known("sheet", normalize_scalar(where.sheet), sheets, where.sheet)

    @staticmethod
    def _require_label_or_class(
        name: str, given: str, known: dict[str, str], other: dict[str, str]
    ) -> None:
        """Like `_require_known`, plus a pointer when the value is valid for the other field."""
        folded = given.lower()
        if folded in known:
            return
        hint = ""
        if folded in other:  # e.g. "Equipment" given as a node_class: it is a label
            other_name = "label" if name == "node_class" else "node_class"
            hint = f" ({given!r} is a valid {other_name}; use that field instead)"
        _require_known(name, folded, known, given, hint)


_MAX_VALUES_LISTED = 40


def _require_known(
    name: str, folded: str, known: dict[str, str], given: str, hint: str = ""
) -> None:
    if folded in known:
        return
    values = sorted(known.values())
    shown = ", ".join(values[:_MAX_VALUES_LISTED])
    more = f", ... ({len(values)} in total)" if len(values) > _MAX_VALUES_LISTED else ""
    raise PlantApiError(
        f"expected a known {name}, found {given!r}{hint}; valid {name} values: {shown}{more}"
    )


def _same_unit(wanted: str, unit_id: str | None) -> bool:
    return unit_id is not None and normalize_unit_id(wanted) == normalize_unit_id(unit_id)


# --- building the graph from a GraphView -------------------------------------


def build_item_graph(view: GraphView) -> ItemGraph:
    """Merge the view's drawings into items and its edges into item edges (design §3.1).

    Args:
        view: the resolver-built occurrence graph; never the gold plant.

    Raises:
        ValueError: an identity group's home drawing is missing, or contraction fails.
    """
    occurrences = view.items()
    contraction = contract({o.local_key: o.node_class for o in occurrences}, view.edges())
    drawings = _drawings_by_item(occurrences, contraction)
    items = [_item_record(item_id, members) for item_id, members in drawings.items()]
    return ItemGraph(items, contraction.edges, _ids_by_tag(drawings))


def _drawings_by_item(
    occurrences: Sequence[OccurrenceRecord], contraction: Contraction
) -> dict[str, list[OccurrenceRecord]]:
    """Group drawings under their home key; paired stubs vanish, unpaired ones stay as items."""
    paired = set(contraction.partner_of_out) | set(contraction.partner_of_out.values())
    grouped: dict[str, list[OccurrenceRecord]] = defaultdict(list)
    for occurrence in occurrences:
        if occurrence.local_key in paired:
            continue
        item_id = contraction.home_of.get(occurrence.local_key, occurrence.local_key)
        grouped[item_id].append(occurrence)
    return dict(grouped)


def _item_record(item_id: str, members: list[OccurrenceRecord]) -> ItemRecord:
    home = next((m for m in members if m.local_key == item_id), None)
    if home is None:
        raise ValueError(
            f"expected the home drawing {item_id!r} among its item's drawings, "
            f"found {sorted(m.local_key for m in members)}"
        )
    is_stub = home.node_class in schema.CONNECTOR_CLASSES
    node_class = UNRESOLVED_CONNECTOR_CLASS if is_stub else home.node_class
    unit_id = next((m.unit_id for m in [home, *members] if m.unit_id), None)
    return ItemRecord(
        item_id=item_id,
        tag=home.tag or home.piping_component_name,
        node_class=node_class,
        labels=(node_class,) if is_stub else _labels(home),
        unit_id=unit_id,
        sheets=tuple(sorted({m.sheet_id for m in members})),
        occurrence_keys=tuple(sorted(m.local_key for m in members)),
        properties=_visible_properties(home, unit_id),
    )


def _visible_properties(home: OccurrenceRecord, unit_id: str | None) -> dict[str, PropertyValue]:
    """The home drawing's visible properties; a repeated drawing's unit fills a missing one."""
    found = {
        key: graphml_safe(value)
        for key, value in sorted(home.properties.items())
        if key in _ITEM_PROPERTY_KEYS and value is not None
    }
    if unit_id is not None:
        found["unit_id"] = unit_id
    return found


def _labels(occurrence: OccurrenceRecord) -> tuple[str, ...]:
    """The schema's class chain; an imported `GenericItem` brings its own, most specific first."""
    if occurrence.node_class != schema.NodeClass.GENERIC_ITEM.value:
        return schema.labels_for(occurrence.node_class)
    imported = occurrence.properties.get("dexpi_labels", [])
    extra = [label for label in imported if isinstance(label, str)]
    return tuple(dict.fromkeys([*extra, occurrence.node_class]))


def _ids_by_tag(drawings: Mapping[str, list[OccurrenceRecord]]) -> dict[str, tuple[str, ...]]:
    """Folded tag or printed name -> item ids; connector stubs are never a tag match."""
    index: dict[str, set[str]] = defaultdict(set)
    for item_id, members in drawings.items():
        for member in members:
            if member.node_class in schema.CONNECTOR_CLASSES:
                continue
            for name in (member.tag, member.piping_component_name):
                if name is not None:
                    index[normalize_scalar(name)].add(item_id)
    return {tag: tuple(sorted(ids)) for tag, ids in index.items()}
