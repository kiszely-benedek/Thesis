---
adr: 0036
title: Store a merged plant layer (PlantItem) beside the occurrence layer under the same corpus, built only from the resolver's output, loaded by profile; add cypher_rag_plant and point cypher_agent at the plant layer
status: accepted
date: 2026-10-02
supersedes: in part — kg-construction.md §7.1 D2 (D2-a "occurrence graph only" → D2-c "both", but under the same corpus_id, not a second one); ADR-0022's premise "every strategy reads the same input" (Recommendation point 1, first Why bullet), restated below — ADR-0022's decision S1 stands. Amends ADR-0034 §5.5 (cypher_agent reads the plant layer). Extends ADR-0035 with claim Q6 and one file in the F1 list.
design: 40-design/merged-plant-layer-and-model-router.md Part A
---

# ADR-0036 — Two graphs in one store: the occurrences as drawn, and the plant

## Context

The user (2026-10-02, approved direction): "build two graphs — one is the tracking one with which we measure things
(the occurrences as drawn), the other is the final result: one big plant graph, one big knowledge graph that we can
query." The registered title is *knowledge-graph construction … for a scalable Q&A system* (`00-index.md`).

Today Neo4j holds only the occurrence graph (kg-construction §7.1 D2-a; `store/neo4j_rows.py`): every drawn symbol,
off-page stubs, `continues_as`, `same_tagged_item_as`, `PlantSection`/`ProcessPlant` (ADR-0026). The merged plant
exists twice, but only in memory:
- `Resolution.plant` (`resolution/merge.py`): identity groups collapsed to their home, stub pairs reconnected, edge
  attributes kept. Gate G1 compares it with the gold plant by original id: equal at H100 and H1000 (SMOKE-04b).
- `ItemGraph` (`qa/plant_api/contraction.py`, `item_graph.py`): the plant API's graph, with `via` (stubs crossed).
  API-01: 38,286 of 38,286 gold edges matched by tag at H1000, 35,532 items.

So a Cypher-writing LLM sees only the as-drawn graph and must cross every sheet boundary with a three-relationship
pattern (`schema_text.py`), while the plant API arms see the merged graph. ADR-0034 named that asymmetry as part of
the hypothesis; it also means Q5 (`graph_agent` − `cypher_rag`, ADR-0035) mixes two effects: typed vs free-form
querying, and merged vs as-drawn representation.

Constraint: the user's Neo4j holds one plant at a time (`check_single_corpus` refuses two `DrawingSet`s).

## Options considered

**A. Status quo** — merged graph in memory only. Nothing to build. No queryable plant KG, no Cypher arm on the merged
graph, nothing to audit in the store.

**B. Merged plant only** (kg-construction D2-b). Simple store. Loses the tracking graph: connector labels, which
sheet shows what, and the resolver's links — the things EXP-0004 and the routing metrics measure.

**C. Both layers under a second `corpus_id`** (D2-c as first written). Breaks the one-plant rule and the
single-`DrawingSet` check, and `drawn_as` would join two corpora that are wiped separately.

**D. Both layers under the same `corpus_id`, plant layer derived only from `Resolution`, loaded by profile
(`occurrence` | `plant` | `both`), each LLM arm run on the profile its schema text describes.**

**E. As D, but every LLM arm queries the `both` load.** No reloads. But the layers share class labels and relation
names: `MATCH (p:Pump)` returns plant items **and** drawings, so counts double. Disjoint vocabularies would avoid
that only by making the plant layer worse to query (no `:Pump` label) or by renaming relations.

**F. As D, one Neo4j database per profile** (Enterprise edition is installed, SMOKE-05b). No reloads, but three
copies of one plant in the user's DBMS, and `drawn_as` cannot cross databases.

## Decision

**D.**
1. **Shape.** `(:CorpusNode:PlantItem:<class chain>)` per physical item (an unpaired stub becomes
   `:PlantItem:UnresolvedOffPageConnector:<stub chain>`); item-level `send_to`, `send_signal_to`, `control`,
   `measured_by`, `related_to` between plant items, with the drawn edge's visible properties plus `crossed_sheets`
   and `via_connector_uids`; `(:PlantItem)-[:is_drawn_on]->(:Sheet)`; `(:PlantItem)-[:is_located_in]->(:PlantSection)`
   (the existing ADR-0026 nodes); `(:PlantItem)-[:drawn_as]->(occurrence)` for every drawing, `both` profile only.
2. **Source.** Rows come from `Resolution.plant`, `identity_groups` and `connector_pairs` only — never the gold plant,
   the manifest or `OccurrenceMap` (import-ban test extended to the new store module).
3. **Uid.** `f"{corpus_id}|item:{home_local_key}"`; the existing `check_unique_uids` guards collisions.
4. **Profiles.** `build_load_plan(..., profile="occurrence")` stays the default and byte-identical to today;
   `ingest --store-profile` defaults to `both`. The harness checks the database against the plan of the arm's
   profile (the built count check) and refuses a run whose arms need different profiles.
5. **Faithfulness checks.** Load: counts per label and type (built), plus gold-free invariant queries (every drawing
   in exactly one item, every stub pair in exactly one plant edge, item sheets = its drawings' sheets). Free gold
   check **PLANT-01**: the stored plant layer, read back from Neo4j, equals the gold plant by original id
   (G1's `graph_differences`), by tag (API-01 style), per item sheets and unit; and equals the in-memory `ItemGraph`.
6. **Who reads what.** ContextRAG and Hierarchical keep the in-memory occurrence view (ADR-0022 S1, ADR-0030). The
   plant API arms keep the in-memory `ItemGraph` (D9; frozen at F1), now proven equal to the stored layer.
   `cypher_rag` keeps the `occurrence` profile. **New arm `cypher_rag_plant`** on the `plant` profile, same prompt
   template, same `timeout_s`/`row_cap`, a plant schema paragraph. **`cypher_agent` (ADR-0034 should-tier) uses the
   `plant` profile**, so `graph_agent` vs `cypher_agent` compares typed vs free-form on one graph.
7. **ADR-0022, in part.** Its premise becomes: *every strategy reads the same resolver output; the representation
   (as drawn or merged) is a property of the arm and is stated per arm.* S1 for ContextRAG stands, as does its S2
   sensitivity rule.
8. **ADR-0035, extended before F1.** New pre-registered claim **Q6**: at H1000, all families,
   `cypher_rag_plant` − `cypher_rag` > 0 with a paired 95 % CI excluding 0; reported per k-bin. Wording if not:
   "free-form querying gains nothing from the merged plant layer". Q5 is unchanged and is read as the combined effect
   (typed + merged). `qa/schema_text.py` joins the F1 hash list (the plant paragraph is model-facing).

## Rationale

- The merged layer **is** the constructed knowledge graph of the title; the occurrence layer is its provenance.
  Storing both, linked by `drawn_as`, makes every plant fact traceable to the drawings it came from.
- It adds no information, only a representation: it is computed from the same `Resolution` every arm already reads,
  so it cannot leak the answer key. Building it from `Resolution.plant`, the G1-verified graph, is the boring choice;
  checking it against the independently built `ItemGraph` gives a second construction for free.
- Q6 isolates what the merged representation is worth to an LLM writing queries. Crossing a sheet costs one
  relationship in the plant layer and three (plus identity links, against flow direction) in the occurrence layer,
  so the gap should grow with `k` — the claim's scale axis.
- Profiles keep each LLM arm's database exactly equal to its schema text, which a single `both` load cannot (E).
  Reloading is cheap in the only currency that matters here, correctness; speed is not a criterion (user,
  2026-10-01).

## Consequences

- Easy: "which sheets is P-101 on" is one hop; a flow path across 30 sheets is
  `(:PlantItem)-[:send_to*]->(:PlantItem)`; the demo (ADR-0024) and the professor can query the plant directly.
- Store size at H1000, `both` (arithmetic on SMOKE-05b, API-01, SMOKE-04b, PROMPT-04 — not a measurement):
  42,044 + 35,532 = 77,576 nodes; 120,914 + 38,286 + 36,214 + 36,214 + one `is_located_in` per item with a unit
  relationships. Load time unmeasured (SMOKE-08); K-NEO (600 s) stays the only limit.
- A CypherRAG run needs the matching profile loaded; the harness refuses otherwise and names the
  `--store-profile` to reload with.
- `ItemGraph` omits `related_to` (contraction keeps four relations); the plant layer keeps it. Irrelevant on
  synthetic corpora, visible on EX01; PLANT-01 compares the four relations and reports `related_to` separately.
- Stub chains (an incoming stub feeding an outgoing stub directly) are not handled by `merge.py`; the plant rows
  raise on one rather than guess. None occur in generated corpora.
- One more paid arm in EXP-0006: about $0.19–$2.16 for 480 questions (estimate, `question-aware-retrieval.md` §10.4
  CypherRAG row × 480).
- **Revisit if** PLANT-01 shows any difference where G1 holds (a row bug, fix before any run); the invariant
  queries fail on EX01 (then the plant rows misread an imported file); or reloads between profiles cause a wrong
  database under a run despite the check (then option F).

**Accepted 2026-10-03 (user, in chat).** Default store profile `both`; before an LLM test run the right profile is reloaded into the one database (no three parallel databases — the user keeps one plant in Neo4j). `cypher_rag_plant` and claim Q6 added.

**Outcome log 2026-10-03 (user, in chat):** the **plant graph is the primary measurement target** — "üzemgráfon mérjünk főként, mert az az érdekes". The occurrence (as-drawn) graph stays as a baseline sample for comparison, not the goal. Consequences: `cypher_rag_plant` is the main CypherRAG arm (`cypher_rag` on the occurrence graph becomes the comparison arm); MP-T1…T4 move up the coder queue; strategies serialize from the plant layer where the design allows, with the occurrence view kept as the comparison point.
