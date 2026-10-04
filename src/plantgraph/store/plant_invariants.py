"""Gold-free consistency checks for a stored corpus (ADR-0036, merged-plant-layer design §A.5).

After a load, the loader's count check only proves that every row arrived. These
queries prove the *two layers agree with each other*: each plant item (one node
per physical thing) points at the drawings it was merged from, no stub symbol is
left over from a merged connector pair, and so on. Each query counts violations
and must return 0. None of them reads the answer key, so they also run on a real
imported drawing, where there is no answer key.

Pure data: no `neo4j` driver import; `neo4j_loader.py` runs the statements.
Terms: an **occurrence** is one drawn symbol on one sheet; an **item** is the
merged `PlantItem` node; `drawn_as` links an item to each of its occurrences;
an **off-page connector** is the stub drawn where a pipe continues on another
sheet, and `continues_as` joins the two stubs of one such pipe (a "paired stub").
"""

from __future__ import annotations

from pydantic import BaseModel

from plantgraph.graph import schema
from plantgraph.store.plant_rows import StoreProfile


class InvariantStatement(BaseModel):
    """One read-only query that returns a single row `{"violations": int}`; 0 means it holds."""

    invariant_id: str
    description: str
    query: str
    parameters: dict[str, object]


#: every node label that is neither an occurrence nor a plant item
_STRUCTURE_LABELS = (
    schema.NodeClass.DRAWING_SET.value,
    schema.NodeClass.SHEET.value,
    schema.NodeClass.PROCESS_PLANT.value,
    schema.NodeClass.PLANT_SECTION.value,
)
_NOT_STRUCTURE = " AND ".join(f"NOT o:{label}" for label in _STRUCTURE_LABELS)

# Relationship types go into query text, never parameters; they come from the schema whitelist.
_TOPOLOGY_TYPES = "|".join(sorted(relation.value for relation in schema.TOPOLOGY_RELATIONS))

_ITEM = schema.PLANT_ITEM_LABEL

_INV_1 = f"""
MATCH (i:{_ITEM} {{corpus_id: $corpus_id}})
WHERE NOT EXISTS {{ (i)-[:drawn_as]->() }}
RETURN count(i) AS violations"""

_INV_2 = f"""
MATCH (o:CorpusNode {{corpus_id: $corpus_id}})
WHERE NOT o:{_ITEM} AND {_NOT_STRUCTURE} AND NOT EXISTS {{ (o)-[:continues_as]-() }}
WITH o, size([(o)<-[:drawn_as]-() | 1]) AS drawings
WHERE drawings <> 1
RETURN count(o) AS violations"""

_INV_3 = f"""
MATCH (:{_ITEM} {{corpus_id: $corpus_id}})-[:drawn_as]->(stub)
WHERE EXISTS {{ (stub)-[:continues_as]-() }}
RETURN count(stub) AS violations"""

# an item's own sheets must be exactly the sheets its occurrences sit on
_INV_4 = f"""
MATCH (i:{_ITEM} {{corpus_id: $corpus_id}})
WITH i,
     [(i)-[:is_drawn_on]->(s) | s.uid] AS item_sheets,
     [(i)-[:drawn_as]->()-[:is_drawn_on]->(s) | s.uid] AS occurrence_sheets
WHERE any(s IN item_sheets WHERE NOT s IN occurrence_sheets)
   OR any(s IN occurrence_sheets WHERE NOT s IN item_sheets)
RETURN count(i) AS violations"""

# violations = connector uids shared by two plant edges + the gap to "2 uids per continues_as pair"
_INV_5 = f"""
MATCH (:{_ITEM} {{corpus_id: $corpus_id}})-[r]->(:{_ITEM})
WHERE r.via_connector_uids IS NOT NULL
UNWIND r.via_connector_uids AS via
WITH via, count(DISTINCT r) AS edges
WITH count(via) AS distinct_uids, sum(CASE WHEN edges > 1 THEN 1 ELSE 0 END) AS shared
OPTIONAL MATCH (:CorpusNode {{corpus_id: $corpus_id}})-[pair:continues_as]->()
WITH distinct_uids, shared, count(pair) AS pairs
RETURN shared + abs(distinct_uids - 2 * pairs) AS violations"""

# topology edges (send_to, ...) must stay inside one layer
_INV_6 = f"""
MATCH (a:CorpusNode {{corpus_id: $corpus_id}})-[:{_TOPOLOGY_TYPES}]->(b:CorpusNode)
WHERE (a:{_ITEM} AND NOT b:{_ITEM}) OR (b:{_ITEM} AND NOT a:{_ITEM})
RETURN count(*) AS violations"""

_INV_7 = f"""
MATCH (i:{_ITEM} {{corpus_id: $corpus_id}})
WHERE i.unit_id IS NOT NULL
WITH i,
     [(i)-[:is_located_in]->(s:PlantSection) WHERE s.unit_id = i.unit_id | s] AS right_sections,
     size([(i)-[:is_located_in]->() | 1]) AS all_links
WHERE size(right_sections) <> 1 OR all_links <> 1
RETURN count(i) AS violations"""

#: (id, profiles that must satisfy it, description, query)
_INVARIANTS: tuple[tuple[str, frozenset[str], str, str], ...] = (
    ("INV-1", frozenset({"both"}), "every plant item has at least one drawn_as", _INV_1),
    (
        "INV-2",
        frozenset({"both"}),
        "every occurrence (not a paired stub) has exactly one incoming drawn_as",
        _INV_2,
    ),
    ("INV-3", frozenset({"both"}), "no paired stub has a drawn_as", _INV_3),
    (
        "INV-4",
        frozenset({"both"}),
        "an item's is_drawn_on sheets equal the sheets of its drawn_as occurrences",
        _INV_4,
    ),
    (
        "INV-5",
        frozenset({"both"}),
        "via_connector_uids number 2 per continues_as pair and none is on two plant edges",
        _INV_5,
    ),
    (
        "INV-6",
        frozenset({"plant", "both"}),
        "no topology relationship joins a plant item and a non-item",
        _INV_6,
    ),
    (
        "INV-7",
        frozenset({"plant", "both"}),
        "an item with a unit_id has exactly one is_located_in, to that unit's PlantSection",
        _INV_7,
    ),
)


def invariant_statements(corpus_id: str, profile: StoreProfile) -> list[InvariantStatement]:
    """The invariants that apply to `profile`; none for `occurrence` (no plant layer to check)."""
    return [
        InvariantStatement(
            invariant_id=invariant_id,
            description=description,
            query=query.strip(),
            parameters={"corpus_id": corpus_id},
        )
        for invariant_id, profiles, description, query in _INVARIANTS
        if profile in profiles
    ]
