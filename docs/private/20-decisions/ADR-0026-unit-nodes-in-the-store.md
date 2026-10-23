---
adr: 0026
title: Store the plant → unit hierarchy as nodes — PlantSection and ProcessPlant with is_located_in, plus a unit_id index
status: accepted
date: 2026-10-01
supersedes: none (closes the deferral in kg-construction.md §7.2 "Deferred: is_located_in, PlantSection and ProcessPlant")
---

# ADR-0026 — Units in Neo4j

**Question.** Today a unit exists in Neo4j only as the `unit_id` property of item occurrences. It is not indexed and
there are no unit nodes (`store/neo4j_plan.py`: indexes on `uid`, `corpus_id`, `tag` only). Once a unit spans several
sheets (ADR-0025), unit-level questions and Hierarchical routing go through the unit. Should the store represent it?

**User priority (2026-10-01).** Load speed does not matter. What matters is that the right, faithful content is
loaded, and that the knowledge graph can be queried with proper query methods at plant scale. ContextRAG is the
baseline to beat, not the system.

**Options**
- **N0** Keep `unit_id` as a property only. Cypher filters on it (`{unit_id: '7'}`) with no index. The hierarchy
  stays implicit.
- **N1** N0 plus `CREATE INDEX corpus_node_unit_id … ON (n.unit_id)`. A one-line change, but still no unit to traverse.
- **N2** N1 plus explicit structure nodes, derived **only from visible properties** of the localized sheets:
  `(:CorpusNode:PlantSection {uid, corpus_id, unit_id})` per distinct `unit_id`;
  `(:CorpusNode:ProcessPlant {uid, corpus_id, plant_id})` per distinct `plant_id`; `(item)-[:is_located_in]->(:PlantSection)`;
  `(:PlantSection)-[:is_located_in]->(:ProcessPlant)`.

**Decision: N2.**
- **Uids.** `f"{corpus_id}|unit:{unit_id}"` and `f"{corpus_id}|plant:{plant_id}"`. Neither can collide with an
  occurrence's local key, because occurrence keys are `sheet:occ_id`.
- **Edges.** Only occurrences that carry `unit_id` get `is_located_in`. Reference occurrences (duplication,
  ADR-0028) and connector stubs carry none, as on a real drawing. They reach their unit through
  `same_tagged_item_as` → home.
- **Labels and relations.** `schema.NodeClass.PLANT_SECTION`, `PROCESS_PLANT` and `Relation.IS_LOCATED_IN` already
  exist. The loader's verify step counts the new labels and relationships like any other.
- **In memory.** The networkx view and the ContextRAG serializer keep folding structure into attributes
  (`qa-system.md` §5). QA-T3's equality check leaves `PlantSection` and `ProcessPlant` out, as it already leaves out
  `DrawingSet` and `Sheet`.
- **CypherRAG schema paragraph.** "`unit_id` is a property (there are no unit nodes)" becomes "an item
  `-[:is_located_in]->` its `PlantSection {unit_id}`".

**Why.** The generated DEXPI model holds the hierarchy: every `TaggedPlantItem` has `parentStructure =
PlantSection`, and the adapter folds it into a property (`plant-generator.md` §3.6). N2 puts back what the source
holds. The thesis's Hierarchical strategy routes plant → unit → sheet. N2 makes that path a queryable structure in
the store, not a string filter. N1 alone only speeds a filter, and speed is explicitly not the criterion.

**Costs.**
- **Code.** About 2 store modules, the verify counts and the T3 exclusion list.
- **Store size, arithmetic on the H1000 probe** (320 units, 39,231 plant nodes; not a measurement): +321 nodes.
  The `is_located_in` edges number one per occurrence that carries a `unit_id`. Their exact count comes from
  SMOKE-05b.
- **Answer-key leak: none.** The `unit_id` is already visible.

**Revisit if** a strategy needs sheet → unit as a direct edge. A sheet's title block names its unit (`pid-structural-rules.md`
S12, P5), so `(:Sheet)-[:is_located_in]->(:PlantSection)` would be the faithful form. Today it is derivable.

**Accepted 2026-10-01 (user, in chat).** As written.
