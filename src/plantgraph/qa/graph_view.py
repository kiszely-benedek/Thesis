"""The in-memory occurrence graph a retrieval strategy reads (design `qa-system.md` §5, §2.1, D9).

A few terms, for a reader who knows Python but not the process-engineering
domain this project is about:

- **occurrence**: one appearance of an equipment or piping symbol on one
  sheet (a single page of a *piping and instrumentation diagram*, or P&ID —
  the engineering drawing this whole project is about). The same physical
  pump drawn on two sheets is two occurrences of one pump.
- **off-page connector**: a stub symbol a drafter places where a pipe or
  signal line runs off the edge of a sheet; its label says which sheet the
  line continues on. `Resolution.connector_pairs` is the resolver's finding
  of which two stubs are the two ends of the same cut line.
- **unit**: a named group of equipment operated together, such as one
  distillation train.

`GraphView` is the read interface every retrieval strategy sees (§5): it
never hands back a raw dict or a bare networkx node, only the typed
`ItemRecord`/`EdgeRecord` below. `NetworkxGraphView` is the implementation
every strategy but CypherRAG uses (design decision D9): it holds the same
nodes, relationships and visible properties as the Neo4j store, built
straight from `localized_sheets` and the resolver's own output, with **no
database round trip**. It never reads the answer key: no `SplitManifest`, no
`OccurrenceMap`, and `_build_occurrence_graph` runs `check_contract` first, so
a caller that forgot to `localize()` its sheets fails loudly here instead of
leaking a gold id into a prompt.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.graph import schema
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.scoring import normalize_scalar
from plantgraph.resolution.contract import check_contract
from plantgraph.resolution.models import Resolution


class ItemRecord(BaseModel):
    """One occurrence: an equipment, valve, instrument or off-page-connector symbol on one sheet."""

    model_config = ConfigDict(frozen=True)

    #: The opaque per-sheet identifier `localize()` assigned, e.g. `"S3:a1b2c3d4e5f6"`.
    local_key: str
    sheet_id: str
    node_class: str
    #: Every other visible property (`tag`, `unit_id`, `piping_component_name`,
    #: an imported item's `dexpi_class`/`dexpi_labels`, …) — never `uid` or
    #: `corpus_id`, which this view never attaches to a node in the first place.
    properties: dict[str, Any] = Field(default_factory=dict)

    @property
    def tag(self) -> str | None:
        """The drawn tag, e.g. `"P-101"`; `None` for an off-page-connector stub."""
        value = self.properties.get("tag")
        return value if isinstance(value, str) else None

    @property
    def unit_id(self) -> str | None:
        """Which unit this occurrence belongs to; `None` for a stub or an EX01 import (§2.1 R1)."""
        value = self.properties.get("unit_id")
        return value if isinstance(value, str) else None

    @property
    def piping_component_name(self) -> str | None:
        """An imported valve's printed name, e.g. `"66KL21"` (ADR-0021, an identifier, not data)."""
        value = self.properties.get("piping_component_name")
        return value if isinstance(value, str) else None


class EdgeRecord(BaseModel):
    """One relationship between two occurrences: a topology edge, or a resolver-asserted link."""

    model_config = ConfigDict(frozen=True)

    source: str
    target: str
    #: `"send_to"`, `"continues_as"`, `"same_tagged_item_as"`, … (`graph.schema.Relation`).
    relation: str
    #: Any other visible edge property (`line_number`, `fluid_code`, `dexpi_label`).
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphView(Protocol):
    """The read interface a retrieval strategy sees — never a raw store record (design §5).

    `NetworkxGraphView` implements every method below; `Neo4jGraphView`
    (CypherRAG only, D9) implements `corpus_id`, `run_cypher` and its own
    schema text, and raises `NotImplementedError` for the rest until a
    strategy needs them (`qa-system.md` §18.1 point 4).
    """

    def corpus_id(self) -> str:
        """Which corpus this view was built for."""
        ...

    def items(self) -> Sequence[ItemRecord]:
        """Every occurrence in the corpus, sorted by local key."""
        ...

    def edges(self) -> Sequence[EdgeRecord]:
        """Every relationship in the corpus, sorted by (source, target)."""
        ...

    def sheets(self) -> list[str]:
        """Every sheet id in the corpus, sorted."""
        ...

    def find_by_tag(self, tag: str) -> list[ItemRecord]:
        """Occurrences whose tag (or printed name) matches, normalized (ADR-0021)."""
        ...

    def unit_ids(self) -> list[str]:
        """Every unit id an occurrence carries, sorted."""
        ...

    def sheets_of_unit(self, unit_id: str) -> list[str]:
        """The sheets showing an occurrence of this unit, sorted."""
        ...

    def sheet_neighbours(self, sheet_id: str) -> list[str]:
        """Sheets reachable by one `continues_as` hop, sorted."""
        ...

    def subgraph(self, sheet_ids: Iterable[str]) -> nx.DiGraph[str]:
        """The induced subgraph of the occurrences drawn on `sheet_ids`."""
        ...

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        """Run a read-only Cypher query; `Neo4jGraphView` only (CypherRAG, D9)."""
        ...


class NetworkxGraphView:
    """The occurrence graph held in memory, built from localized sheets and a `Resolution`.

    One node per occurrence (sheets and the corpus marker are never
    materialized as nodes — `sheet_id` is a node attribute instead, §5's
    "structure nodes are folded into attributes"), plus the sheets' own
    topology edges and the resolver's `continues_as` / `same_tagged_item_as`
    links. `qa-system.md` §2.1 proves this is the same graph the Neo4j store
    holds, by comparing label/relationship counts against
    `store.neo4j_plan.build_load_plan`'s `expected_*` fields (QA-T3's
    acceptance check).
    """

    def __init__(
        self, corpus_id: str, localized_sheets: Sequence[SheetGraph], resolution: Resolution
    ) -> None:
        self._corpus_id = corpus_id
        self._graph = _build_occurrence_graph(localized_sheets, resolution)
        self._sheet_ids = sorted({sheet.sheet_id for sheet in localized_sheets})
        self._sheet_adjacency = _sheet_adjacency(resolution)
        # Built on the first lookup, not here: a run that never looks up a tag pays nothing.
        self._lookup: _LookupIndex | None = None

    def corpus_id(self) -> str:
        """Which corpus this view was built for."""
        return self._corpus_id

    def items(self) -> list[ItemRecord]:
        """Every occurrence in the corpus, sorted by local key."""
        # Unpacked directly in the comprehension, then sorted as a plain list: handing
        # `.nodes(data=True)` itself to `sorted()` confuses its stub's overload resolution.
        unordered = [_item_record(key, attrs) for key, attrs in self._graph.nodes(data=True)]
        return sorted(unordered, key=lambda item: item.local_key)

    def edges(self) -> list[EdgeRecord]:
        """Every relationship in the corpus, sorted by (source, target)."""
        unordered = [
            _edge_record(source, target, attrs)
            for source, target, attrs in self._graph.edges(data=True)
        ]
        return sorted(unordered, key=lambda edge: (edge.source, edge.target))

    def sheets(self) -> list[str]:
        """Every sheet id in the corpus, sorted."""
        return list(self._sheet_ids)

    def find_by_tag(self, tag: str) -> list[ItemRecord]:
        """Occurrences whose `tag` or `piping_component_name` normalizes to `tag` (ADR-0021).

        Off-page-connector stubs are excluded: they are a drawing artefact,
        not a piece of plant equipment, and never carry a `tag` in the first
        place (`connectors.py`'s stubs set `connector_number` instead) — the
        check is still explicit here, since the design calls it out (§5).
        """
        keys = self._lookup_index().keys_by_tag.get(normalize_scalar(tag), ())
        return [_item_record(key, self._graph.nodes[key]) for key in sorted(keys)]

    def unit_ids(self) -> list[str]:
        """Every unit id an occurrence carries, sorted."""
        return sorted(self._lookup_index().sheets_by_unit)

    def sheets_of_unit(self, unit_id: str) -> list[str]:
        """The sheets showing an occurrence with this `unit_id` (§2.1: there are no unit nodes)."""
        return sorted(self._lookup_index().sheets_by_unit.get(unit_id, ()))

    def _lookup_index(self) -> _LookupIndex:
        if self._lookup is None:
            self._lookup = _build_lookup_index(self._graph)
        return self._lookup

    def sheet_neighbours(self, sheet_id: str) -> list[str]:
        """Sheets reachable by one `continues_as` hop, in either direction (symmetric)."""
        return sorted(self._sheet_adjacency.get(sheet_id, set()))

    def subgraph(self, sheet_ids: Iterable[str]) -> nx.DiGraph[str]:
        """The induced subgraph of the occurrences drawn on `sheet_ids`.

        An edge to a node outside `sheet_ids` is dropped along with that
        node — e.g. a `continues_as` edge whose partner stub sits on an
        excluded sheet. The stub node itself is kept, so a strategy can still
        see, from the stub's own label, that the line continues elsewhere
        (`qa-system.md` §7, Hierarchical step 5).
        """
        wanted = set(sheet_ids)
        kept = [key for key, attrs in self._graph.nodes(data=True) if attrs["sheet_id"] in wanted]
        return nx.DiGraph(self._graph.subgraph(kept))

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        """Raises `NotImplementedError`: this view holds no database (D9)."""
        raise NotImplementedError(
            "NetworkxGraphView holds no database; only Neo4jGraphView answers Cypher (D9)"
        )


def _build_occurrence_graph(
    sheets: Sequence[SheetGraph], resolution: Resolution
) -> nx.DiGraph[str]:
    """Sheets' occurrences and topology, plus the resolver's cross-sheet links.

    Raises:
        ValueError: `check_contract` fails — a caller passed sheets that
            were never `localize()`d, which would otherwise leak a gold
            node id into every downstream prompt.
    """
    check_contract(sheets)
    graph: nx.DiGraph[str] = nx.DiGraph()
    for sheet in sheets:
        _add_sheet(graph, sheet)
    _add_resolver_links(graph, resolution)
    return graph


def _add_sheet(graph: nx.DiGraph[str], sheet: SheetGraph) -> None:
    for node_id, attrs in sheet.graph.nodes(data=True):
        graph.add_node(f"{sheet.sheet_id}:{node_id}", sheet_id=sheet.sheet_id, **attrs)
    for source, target, attrs in sheet.graph.edges(data=True):
        graph.add_edge(f"{sheet.sheet_id}:{source}", f"{sheet.sheet_id}:{target}", **attrs)


def _add_resolver_links(graph: nx.DiGraph[str], resolution: Resolution) -> None:
    """`continues_as` (paired stubs) and `same_tagged_item_as` (identity groups) — §5.2/§5.3."""
    for pair in resolution.connector_pairs:
        graph.add_edge(pair.from_key, pair.to_key, relation=schema.Relation.CONTINUES_AS.value)
    for group in resolution.identity_groups:
        for reference in group.references:
            graph.add_edge(
                reference, group.home, relation=schema.Relation.SAME_TAGGED_ITEM_AS.value
            )


def _sheet_adjacency(resolution: Resolution) -> dict[str, set[str]]:
    """Undirected sheet-to-sheet adjacency from `continues_as` pairs (§7, Hierarchical step 3)."""
    adjacency: dict[str, set[str]] = defaultdict(set)
    for pair in resolution.connector_pairs:
        sheet_a, _, _ = pair.from_key.partition(":")
        sheet_b, _, _ = pair.to_key.partition(":")
        adjacency[sheet_a].add(sheet_b)
        adjacency[sheet_b].add(sheet_a)
    return adjacency


@dataclass
class _LookupIndex:
    """What a question's anchor lookup needs, built in one pass over the nodes.

    Anchor extraction asks `find_by_tag` for every token and token pair of a
    question; scanning all nodes each time cost ~1 s per question at 1,000
    sheets (H-T1 measurement), so the answers are tabulated once instead.
    """

    #: Normalized tag or printed name -> local keys of the matching non-stub occurrences.
    keys_by_tag: dict[str, set[str]]
    #: Unit id -> the sheets showing an occurrence of that unit.
    sheets_by_unit: dict[str, set[str]]


def _build_lookup_index(graph: nx.DiGraph[str]) -> _LookupIndex:
    keys_by_tag: dict[str, set[str]] = defaultdict(set)
    sheets_by_unit: dict[str, set[str]] = defaultdict(set)
    for local_key, attrs in graph.nodes(data=True):
        unit_id = attrs.get("unit_id")
        if isinstance(unit_id, str):
            sheets_by_unit[unit_id].add(attrs["sheet_id"])
        if attrs.get("node_class") in schema.CONNECTOR_CLASSES:
            continue  # stubs are a drawing artefact, never a tag match (design §5)
        for property_name in ("tag", "piping_component_name"):
            value = attrs.get(property_name)
            if isinstance(value, str):
                keys_by_tag[normalize_scalar(value)].add(local_key)
    return _LookupIndex(keys_by_tag=dict(keys_by_tag), sheets_by_unit=dict(sheets_by_unit))


def _item_record(local_key: str, attrs: Mapping[str, Any]) -> ItemRecord:
    node_class = attrs.get("node_class")
    if not isinstance(node_class, str):
        raise ValueError(f"occurrence {local_key!r} has no string node_class: {attrs!r}")
    sheet_id = attrs.get("sheet_id")
    if not isinstance(sheet_id, str):
        raise ValueError(f"occurrence {local_key!r} has no sheet_id attribute: {attrs!r}")
    excluded = ("node_class", "sheet_id")
    properties = {key: value for key, value in attrs.items() if key not in excluded}
    return ItemRecord(
        local_key=local_key, sheet_id=sheet_id, node_class=node_class, properties=properties
    )


def _edge_record(source: str, target: str, attrs: Mapping[str, Any]) -> EdgeRecord:
    relation = attrs.get("relation")
    if not isinstance(relation, str):
        raise ValueError(f"edge {(source, target)!r} has no string relation: {attrs!r}")
    properties = {key: value for key, value in attrs.items() if key != "relation"}
    return EdgeRecord(source=source, target=target, relation=relation, properties=properties)
