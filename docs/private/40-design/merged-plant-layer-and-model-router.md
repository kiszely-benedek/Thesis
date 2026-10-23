---
component: (A) a merged plant layer in Neo4j beside the occurrence layer, loaded by profile, with a gold check and a Cypher arm on it; (B) a Jev model-choice router arm computed offline from fixed-model runs
status: draft — awaiting review
related: [ADR-0036, ADR-0037 (proposed); ADR-0014, ADR-0019 (reserved, answer pin), ADR-0022, ADR-0026, ADR-0030, ADR-0032, ADR-0033, ADR-0034, ADR-0035; kg-construction.md §5.4, §7; qa-system.md §2.1, §5, §7; question-aware-retrieval.md §3, §5.5, §9, §10; hierarchical-and-jev.md §5, §6]
date: 2026-10-02
author: architect (Opus 5.5)
---

# Design — the plant layer in the store, and a model-choice router

## 0. Recommendation

| # | Item | Decision | ADR |
|---|---|---|---|
| A1 | Two graphs | `(:PlantItem)` layer beside the occurrence layer, **same `corpus_id`**, linked by `drawn_as`; built only from `Resolution` | 0036 |
| A2 | Isolation | load **profiles** `occurrence` / `plant` / `both`; each LLM arm runs on the profile its schema text describes; `ingest` default `both` | 0036 |
| A3 | Faithfulness | load verify (counts, built) + gold-free invariant queries; free gold check **PLANT-01** (id-exact, by tag, sheets, units, and equality with the in-memory `ItemGraph`) | 0036 |
| A4 | Arms | ContextRAG, Hierarchical, need variants, plant-API agents unchanged; `cypher_rag` on `occurrence`; **new `cypher_rag_plant`**; `cypher_agent` on `plant`; claim **Q6** | 0036 |
| B1 | Model router | Jev `noul` difficulty → cheap or strong pinned model, wrapping `hierarchical`; **offline** over fixed-model runs | 0037 |
| B2 | Baselines | always-cheap, always-strong, oracle, random at the same mix, self-signal cascade, label-probability and rules deciders; claims M1, M2; futility stop | 0037 |

Coder tasks: 6 (§C), one Sonnet coder at a time; all acceptance offline. Paid steps: 2 (Part B), each **run by the
user, paid, logged**. Part A costs nothing until `cypher_rag_plant` joins the EXP-0006 paid runs.

## 1. Which part of the claim each piece serves

- **Part A** is the title's "knowledge-graph construction": the plant layer is the constructed KG, the occurrence layer
  its provenance. Q6 measures whether that construction matters to an LLM that writes queries — crossing a sheet costs
  one relationship instead of three, so the gap should grow with `k`, the scale axis of ADR-0029.
- It also cleans ADR-0035's Q5: with `cypher_agent` on the plant layer, typed vs free-form is compared on one graph.
- **Part B** adds the cost axis the user asked for ("high quality at low cost"): the cheapest adequate model per
  question, per corpus size. Novelty budget: none spent on the router mechanism (boring, offline); the domain and the
  scale axis are the point.

## 2. What the built code says (read 2026-10-02)

| # | Finding | Where | Consequence |
|---|---|---|---|
| F1 | The store holds the occurrence graph only; one `CREATE` per label set / type; verify = label and type counts | `store/neo4j_rows.py`, `neo4j_plan.py`, `neo4j_loader.py` | the plant layer is more rows in the same plan; verify needs no change for counts |
| F2 | `Resolution.plant` is the merged plant: nodes = identity homes + unpaired stubs, intra-sheet edges via representatives, each pair reconnected with the out-stub edge's attributes; G1-equal to gold at H100/H1000 | `resolution/merge.py`; `_results.md` SMOKE-04b | the plant rows are built from it; no third merge implementation |
| F3 | `ItemGraph` is a second, independent construction (with `via`); API-01 P = R = 1.0 at H1000, 35,532 items, 38,286 edges | `qa/plant_api/contraction.py`; `_results.md` API-01 | a free cross-check: stored layer = `ItemGraph` |
| F4 | `ItemGraph` keeps four relations; `related_to` edges (EX01 `GenericItem`s, ADR-0016) are skipped | `contraction.py` `_outgoing_topology` | the plant layer keeps `related_to`; PLANT-01 compares the four and reports `related_to` apart |
| F5 | `merge.py` assumes a stub's neighbour is a real item (no stub chains); `contraction.py` walks chains | `merge.py` `_add_reconnected_edges` | plant rows raise on a chain instead of guessing |
| F6 | `NetworkxGraphView`'s equality test and `qa/corpus.py` call `build_load_plan` with no profile | `graph_view.py` docstring; `corpus.py` lines 149, 174 | the function default stays `occurrence`, byte-identical |
| F7 | CypherRAG's pre-check compares the database with the plan's counts and refuses a mismatch | `harness/cypher_setup.py`, `neo4j_view.check_store` | a wrong profile is refused by the built check; only the hint text changes |
| F8 | One plant in the user's Neo4j at a time (`check_single_corpus`; user rule 2026-10-02) | `neo4j_view.py` | same `corpus_id`, one `DrawingSet`, one wipe for both layers |
| F9 | The answer pin reaches strategies at construction (`LlmDeps`, `CypherDeps`) and the final step per call | `harness/registry.py`, `strategies/base.py` | a live per-question model switch would need harness changes; Part B avoids them |

---

## Part A — the merged plant layer

### A.1 Store shape (additions only; the occurrence layer is unchanged)

| Element | Neo4j | Properties | Profiles |
|---|---|---|---|
| plant item | `(:CorpusNode:PlantItem:<labels_for(node_class)>)`; `GenericItem`: `dexpi_labels` chain first, as occurrences | `uid`, `corpus_id`, the home occurrence's visible properties (`node_class`, `tag`, `unit_id`, `plant_id`, `loop_tag`, `measured_variable`, `piping_component_name`, `dexpi_*`) | plant, both |
| unresolved line end | `(:CorpusNode:PlantItem:UnresolvedOffPageConnector:<stub chain>)` | the stub's visible properties (`connector_number`, `referenced_drawing_number`, …) | plant, both |
| item topology | `send_to`, `send_signal_to`, `control`, `measured_by`, `related_to` between `PlantItem`s | visible edge properties (`line_number`, `fluid_code`, `dexpi_label`); `crossed_sheets: list[str]` (only if no sheet draws the edge whole); `via_connector_uids: list[str]` (every stub pair that produced it); `asserted_by` | plant, both |
| item → sheet | `(:PlantItem)-[:is_drawn_on]->(:Sheet)` | — | plant, both |
| item → unit | `(:PlantItem)-[:is_located_in]->(:PlantSection)` (the ADR-0026 nodes) | — | plant, both |
| item → drawing | `(:PlantItem)-[:drawn_as]->(occurrence)` | `asserted_by` | both |

- **Shared structure:** `DrawingSet`, `Sheet`, `PlantSection`, `ProcessPlant` and their edges are written once.
  In `plant`, `PlantSection` rows are derived from the plant items' `unit_id`s (a test checks the set equals the
  occurrence-derived one).
- **Paired stubs are not items.** They survive in `both` as occurrences and in every plant edge's `via_connector_uids`.
- **Hidden from LLMs:** `uid`, `corpus_id`, `via_connector_uids` (`neo4j_view._HIDDEN_PROPERTIES`), `CorpusNode`.

### A.2 `graph/schema.py` additions

```python
class Relation(str, Enum):
    ...
    DRAWN_AS = "drawn_as"   # plant item -> each drawn occurrence of it (ADR-0036); structural

PLANT_ITEM_LABEL = "PlantItem"
UNRESOLVED_CONNECTOR_LABEL = "UnresolvedOffPageConnector"   # = plant_api.model.UNRESOLVED_CONNECTOR_CLASS
PLANT_EDGE_PROVENANCE_PROPERTIES: frozenset[str] = frozenset({"crossed_sheets"})  # model-facing
```
No new `NodeClass` (that would touch `KNOWN_CLASSES` and every validator). `TOPOLOGY_RELATIONS` is unchanged, so
`DRAWN_AS` cannot appear in a sheet. The coder greps tests that count `Relation` members and updates them.
`plant_api/model.py` imports the label constant instead of repeating the string.

### A.3 Uid

`item_uid(corpus_id, home_key) = uid(corpus_id, f"item:{home_key}")`, e.g. `H1000|item:S0042:a1b2c3d4e5f6`.
The home key is `resolution`'s representative (most properties, tie by `sheet_id`, `kg-construction.md` §5.3), so
it is deterministic across reloads. An unpaired stub's item uid uses its own key. `check_unique_uids` runs over all
rows of the plan, so any collision with `unit:`/`plant:`/occurrence uids raises.

### A.4 Rows — `store/plant_rows.py` (new, pure, no driver)

```python
StoreProfile = Literal["occurrence", "plant", "both"]

def plant_node_rows(corpus_id: str, resolution: Resolution) -> list[NodeRow]: ...
def plant_relationship_rows(corpus_id: str, sheets: Sequence[SheetGraph], resolution: Resolution,
                            asserted_by: Literal["resolver", "oracle"]) -> list[RelationshipRow]: ...
def drawn_as_rows(corpus_id: str, sheets: Sequence[SheetGraph], resolution: Resolution,
                  asserted_by: Literal["resolver", "oracle"]) -> list[RelationshipRow]: ...
```
1. **Members.** `member_of(key)` = `group.home` for each reference, the key itself for every other non-paired-stub
   occurrence; paired stubs map to nothing.
2. **Nodes** = `resolution.plant.nodes` with their attributes (already the home's, never a union, §5.4); labels from
   `_occurrence_labels` (made shared, not copied) with `PlantItem` inserted; unpaired stubs get
   `UnresolvedOffPageConnector`.
3. **Edges** = `resolution.plant.edges`. For each pair `(out, in)`: `pred(out)` and `succ(in)` on their sheets
   (raise if either is a stub: chain, F5) → plant edge `(member_of(pred), member_of(succ))` gains `[uid(out), uid(in)]`
   in `via_connector_uids` (pairs in `(from_key, to_key)` order). An edge also drawn whole on some sheet (both ends'
   drawings on one sheet, joined there) gets no `crossed_sheets`; otherwise `crossed_sheets = [sheet(out), sheet(in)]`
   of its first pair. This mirrors `contraction._dedupe` (fewest stubs, then smallest `via`).
4. **`is_drawn_on`**: one row per (item, distinct sheet of its members). **`is_located_in`**: one per item whose node
   has a string `unit_id`. **`drawn_as`**: one per member.
5. Import ban: `tests/test_resolution_imports.py` (or a sibling) also covers `store/plant_rows.py`: no
   `benchmark.splitter`, `benchmark.rejoin`, `eval`, `SplitManifest`, `OccurrenceMap`.

### A.5 Load plan and verify

```python
def build_load_plan(corpus_id, sheets, resolution, asserted_by="resolver", batch_size=5000,
                    profile: StoreProfile = "occurrence") -> LoadPlan: ...

class LoadPlan(BaseModel):
    ...                                    # unchanged fields
    profile: StoreProfile = "occurrence"
    invariant_statements: list[CypherStatement] = []   # each returns one row {"violations": int}; expected 0
```
- `occurrence`: today's rows exactly (golden test: plan JSON hash at a toy corpus equals today's).
  `plant`: structure rows + plant rows. `both`: occurrence rows + plant rows + `drawn_as`.
- **Loader:** after the count verify, run each invariant statement read-only; raise on any non-zero, naming it.
- **Invariants** (Neo4j 5 syntax, to be verified on the user's DBMS; `$c` = corpus):

| Id | Profile | Checks |
|---|---|---|
| INV-1 | both | every `PlantItem` has ≥ 1 `drawn_as` |
| INV-2 | both | every occurrence that is not a `PlantItem`, `Sheet`, structure node or paired stub has exactly one incoming `drawn_as` |
| INV-3 | both | no paired stub (an endpoint of `continues_as`) has a `drawn_as` |
| INV-4 | both | per item, the `is_drawn_on` sheets equal the sheets of its `drawn_as` occurrences |
| INV-5 | both | the distinct `via_connector_uids` values number 2 × `count(continues_as)`, and none occurs on two plant edges |
| INV-6 | plant, both | no topology relationship joins a `PlantItem` and a non-`PlantItem` |
| INV-7 | plant, both | every `PlantItem` with a `unit_id` has exactly one `is_located_in`, to the `PlantSection` with that `unit_id` |

  These are gold-free, so they run on EX01 (`ingest proteus`) too.
- **CLI:** `python -m plantgraph.ingest synthetic|proteus … --store-profile occurrence|plant|both` (default `both`);
  `IngestResult` records the profile and per-layer counts.
- **Size at H1000, arithmetic** (from SMOKE-05b 42,044 nodes / 120,914 relationships; API-01 35,532 items / 38,286
  edges; PROMPT-04 40,532 occurrences; SMOKE-04b 2,159 pairs, 1,001 sheets, 509 units — **not measured**):
  `drawn_as` = 40,532 − 2 × 2,159 = 36,214; item `is_drawn_on` = 36,214 if no item has two drawings on one sheet (the
  identity rule excludes such keys, §5.3); `both` = 77,576 nodes and 231,628 + (one `is_located_in` per item with a
  unit) relationships; `plant` = 37,044 nodes. SMOKE-08 measures the real counts and time.

### A.6 PLANT-01 — the stored layer against gold (free, harness side)

`store/plant_readback.py` (read-only session): reads `PlantItem` nodes, item-to-item relationships, `is_drawn_on`,
`is_located_in`, `drawn_as` for one corpus → `StoredPlantLayer` (an `nx.DiGraph` keyed by home key + three maps).

`qa/harness/plant_layer_fidelity.py`, `python -m plantgraph.qa.harness.plant_layer_fidelity --corpus-id … --ingest-json …`
(rebuilds `CorpusArtifacts` as API-01 does):

| Part | Check | Pass |
|---|---|---|
| a | `graph_differences(to_original_ids(visible(stored), occurrence_map), visible_view(gold))` | `[]` |
| b | edges by tag, precision / recall (reuse `api_fidelity` logic on stored edges) | 1.0 / 1.0 |
| c | per item: stored sheets = gold sheets of its original node (all its occurrences in the manifest) | share 1.0 |
| d | per item: stored `PlantSection.unit_id` = gold `unit_id` | share 1.0 |
| e | stored layer = in-memory `ItemGraph`: item ids, (source, target, relation) edges, `crossed_sheets` vs first `via`, sheets, unit | identical (four relations; `related_to` count reported) |

Row in `_results.md` as **PLANT-01** per corpus (H100, H1000), with load time and counts from SMOKE-08.

### A.7 What CypherRAG is told

`schema_text.build_schema_text(plan)` picks the paragraph by `plan.profile`: `occurrence` → today's paragraph
unchanged; `plant` → the paragraph below; `both` → `ValueError` (no LLM arm reads `both`). Label and type lists come
from the plan as today (minus `CorpusNode`); relationship properties add `crossed_sheets`.

```
How the graph is organised:
- Every plant item (equipment, valve, instrument function) is one (:PlantItem) node, however many sheets it
  is drawn on. It also has its class labels, a specific class and the general ones above it, for example
  :PlantItem:CentrifugalPump:Pump:Equipment, so MATCH on a general label such as :Equipment to cover a family.
- Material flows along -[:send_to]->: (a)-[:send_to]->(b) means flow runs from a to b, also when a and b are
  drawn on different sheets: lines that continue on another sheet are already joined. Instrument wiring uses
  send_signal_to, control and measured_by. A relationship that crosses sheets has crossed_sheets, the two
  sheets it joins.
- (item)-[:is_drawn_on]->(:Sheet {sheet_id}) for every sheet the item appears on;
  (:DrawingSet)-[:has_sheet]->(:Sheet).
- (item)-[:is_located_in]->(:PlantSection {unit_id})-[:is_located_in]->(:ProcessPlant {plant_id}).
  unit_id is also an item property.
- tag is the identifier printed next to an item, for example P-101. piping_component_name is the printed name
  of an imported valve. Signal items carry loop_tag.
- A (:PlantItem:UnresolvedOffPageConnector) is a line end whose continuation was not found; the line stops there.
```

The same flow-path question, as the model would have to write it:
- occurrence: the hop alternates `send_to` and `continues_as`, and a repeated drawing joins its home by
  `same_tagged_item_as`, which points reference → home, not along the flow; a directed variable-length pattern over
  `send_to|continues_as` misses identity joins, and an undirected one loses direction.
- plant: `MATCH p = shortestPath((a:PlantItem {tag:'P-101'})-[:send_to*]->(b:PlantItem {tag:'TK-5-2'}))
  RETURN [n IN nodes(p) | n.tag]`.

MP-T5 (should) measures this free: one canonical Cypher query per dev family on each profile, its correctness against
the reference functions, and its length — the "simpler queries" claim as a number, not an assertion.

### A.8 Who reads what

| Consumer | Reads | Change |
|---|---|---|
| ContextRAG | in-memory occurrence view (ADR-0022 S1) | none |
| Hierarchical (ADR-0030 pair) | in-memory occurrence view | none |
| `hierarchical_need_*` (QAR-T4, being built) | occurrence view + in-memory `ItemGraph` | none |
| `graph_agent`, `hier_agent` | in-memory `ItemGraph` (D9; `qa/plant_api/` frozen at F1) | none; PLANT-01 (e) proves it equals the stored layer |
| `cypher_rag` | Neo4j, `occurrence` profile | profile made explicit |
| **`cypher_rag_plant`** (new) | Neo4j, `plant` profile; same `cypher_query.txt`, same `timeout_s`, `row_cap` | new arm |
| `cypher_agent` (should, QAR-T7) | Neo4j, `plant` profile | design change (ADR-0034 §5.5) |
| questions, references, `k`, gold sheets | gold plant + manifest | none — never the store |
| demo (ADR-0024), the user, the professor | Neo4j, `both` | new |

Why the plant API does not switch to reading Neo4j: same content (proven), more latency, a new dependency, and a
change to frozen files. The boring option is to keep D9.

Comparisons this enables (EXP-0006, ADR-0035 + Q6):

| Comparison | Isolates |
|---|---|
| `cypher_rag_plant` vs `cypher_rag` (**Q6**) | merged vs as-drawn representation, free-form single query |
| `graph_agent` vs `cypher_agent` | typed vs free-form, same graph, iteration equal |
| `cypher_agent` vs `cypher_rag_plant` | iteration, same graph and interface |
| `graph_agent` vs `cypher_rag` (Q5, unchanged) | the combined effect |

Harness rule: one Cypher profile per run; a run naming `cypher_rag` and `cypher_rag_plant` together is refused before
the freeze, with the two commands to run instead.

### A.9 Tests (offline unless marked)

| Component | Tests |
|---|---|
| plant rows | split toy plants at duplication 0.0 and 0.5: item count = `len(resolution.plant)`, edges = its edges; a reference merges into its home (one item, two `drawn_as`); a pair yields one edge with both stub uids and `crossed_sheets`; an edge drawn whole on a reference's sheet has no `crossed_sheets`; an unpaired stub becomes an `UnresolvedOffPageConnector` item; a hand-built stub chain raises |
| plan | `occurrence` plan identical to today (golden hash); `expected_*` per profile equal counts taken independently from `Resolution`; all labels from the whitelist; uids unique across layers |
| schema text | `plant` paragraph present for a `plant` plan; `both` raises; lists contain no `CorpusNode`, `uid`, `via_connector_uids` |
| readback + PLANT-01 | parts a–e on a toy against the stored rows replayed through a fake reader; one injected row error makes (a) and (e) fail |
| integration (opt-in, Neo4j) | load a 4-unit corpus in each profile as `pytest-plant-*`, verify + invariants pass, wipe in `finally` |
| harness | mixed-profile run refused; `check_store` hint names `--store-profile` |

---

## Part B — the model-choice router arm

### B.1 What it is

`model_routed_<decider>`: for each question, a decider scores *"will the cheap model answer this correctly?"* from the
question text and the fixed corpus line ("The plant has N sheets and M units."); cheap if p ≥ τ = 0.5, else strong.
The answer is the fixed (S, m) run's answer for that question. S = `hierarchical` (ADR-0030 pair).

### B.2 Candidates and reproducibility

- Two pinned models, each with its own ADR-0014 pin (model id, provider, parameters, prompt hashes) and its own
  measured `ContextWall` (the pilot). One is ADR-0019's answer pin.
- Each fixed run is single-model, so ADR-0014 point 4 holds for every sweep; the routed arm is a separate row that
  lists its strong share per corpus and k-bin.
- Decisions are cached (`decisions.sqlite` for Jev, the chat cache for the label-probability readout) and replayable.

### B.3 Deciders and free comparisons

| Name | How | Cost |
|---|---|---|
| `jev` | System One `noul`, pinned `jev-1.13`, resolved id checked (ADR-0032) | tiny, paid |
| `labelprob` | same yes/no to the classifier pin (glm-5.3-flash, `logprobs` listed in the snapshot); p from top log-probabilities | tiny, paid |
| `rules` | ADR-0033 rules need label: `ITEM`, neighbour labels, `UNIT` → easy (p = 1); others and `GENERIC` → hard (p = 0) | free |
| `cascade_selfsignal` | cheap answer, escalate if `not_present`, `PARSE_FAILURE` or `DID_NOT_FIT`; cost = cheap + strong on escalated | free |
| `random_mix` | strong for a random share equal to `jev`'s, 1,000 seeded draws → mean and CI | free |
| `oracle` | correct if any candidate is; cost of the cheapest correct one (else the cheapest) | free |
| `always_cheap`, `always_strong` | the fixed runs | already paid |

Each decider reports its own accuracy: AUROC of p against "cheap model correct", and the confusion at τ.

### B.4 When it is free of answer calls, and when it is not

Offline holds when, for every routed question: a fixed answer exists for the chosen model; both fixed runs share the
F1 hashes, strategy parameters, question set and repeat index; and the decision used no model output. Then
"routed answer = fixed (S, m(q)) answer" is exact, because a live routed run would hit the same cache key (pin +
messages) and replay the same response. `qa/model_router/join.py` refuses otherwise and prints the missing question
ids per model and the harness command that fills them.

New paid calls are needed for: (1) the second model's fixed run on the routed slice; (2) the decisions; (3) a third
candidate; (4) a question that mixes models (cheap retrieval or agent steps, strong final step) — a new combination,
never in the cache; (5) any frozen prompt or parameter change (every fixed run must be redone).

### B.5 Metrics and claims

Per corpus and k-bin: accuracy [95 % CI], mean total cost per question (answer calls as first billed + decision),
strong share, cost saved and accuracy lost vs always-strong, regret vs oracle, AUROC per decider. Claims M1, M2 and the
futility stop are pre-registered in ADR-0037.

### B.6 Budget — estimates, not measurements

Assumptions as `question-aware-retrieval.md` §10.4 (4 characters per token; Hierarchical-type prompt 40,000 characters
+ 1,000 output tokens), plus an upper case at 100,000 characters (ADR-0030's lowest probe budget; HIER-CTX-01).
Strong example at the snapshot's `anthropic/claude-sonnet-5.5` price, $2 / $10 per million tokens:
10,000 × 2e-6 + 1,000 × 1e-5 = **$0.03** to 25,000 × 2e-6 + 1,000 × 1e-5 = **$0.06** per question. Cheap: the
ADR-0019 pin's run, already paid in EXP-0006. Decisions: label-probability ≈ 300 input tokens at $0.15 per million ≈
$0.00005 per question; Jev at the vendor's unverified $0.042 per million input, negligible.

| Slice (H1000, `hierarchical`) | strong-model run (estimate) |
|---|---|
| 120 questions (stage 1) | $3.6–$7.2 |
| 240 questions (stage 2, only if stage 1 is informative and the futility stop does not fire) | $7.2–$14.4 |

`hier_agent` with the same strong model: 36,000 × 2e-6 + 4,000 × 1e-5 ≈ $0.11 per question (estimate) — could-tier.
Every paid step passes `--max-spend-usd` (QAR-T1) at 1.5 × its estimate, and the balance is read after.

### B.7 Files

| File | New / changed | Holds |
|---|---|---|
| `src/plantgraph/qa/model_router/deciders.py` | new | `DifficultyDecider` protocol; `JevDifficulty`, `LabelProbDifficulty`, `RulesDifficulty`; state text |
| `src/plantgraph/qa/model_router/decide.py` | new | CLI: questions → `decisions.jsonl`; `--allow-paid-calls`, `--max-spend-usd` |
| `src/plantgraph/qa/model_router/join.py` | new | offline join of fixed runs' `answers.jsonl` + decisions; refusal on gaps |
| `src/plantgraph/qa/model_router/report.py` | new | routed, oracle, random mix, cascade, AUROC, CIs → CSV + markdown |
| `src/plantgraph/qa/prompts/difficulty_easy.txt` | new | the yes/no wording (hashed with the other prompts) |

Import ban: `qa/model_router/deciders.py` imports nothing from `qa.questions`, `qa.harness`, `qa.corpus`; the report
side may read `answers.jsonl` (gold `correct` flags) — it is analysis, like `route_report`.

---

## C. Ordered coder tasks (one Sonnet coder at a time; each ends green on ruff, mypy --strict, pytest, offline)

| # | Task | Depends on | Collision with QAR-T4 | Size (estimate) |
|---|---|---|---|---|
| **MP-T1** | schema additions (§A.2); `store/plant_rows.py` (§A.4); `StoreProfile`, `build_load_plan(profile=…)`, golden test for `occurrence`; import-ban extension; plan tests (§A.9) | — | none (`graph/schema.py`, `store/`) | M |
| **MP-T2** | `LoadPlan.invariant_statements` + loader runs them (§A.5); `ingest --store-profile` (default `both`), `IngestResult` profile and per-layer counts; opt-in integration test per profile | MP-T1 | none (`store/`, `ingest/`) | S/M |
| — | *Main session: **SMOKE-08** (free): `ingest synthetic --headline --target-sheets 1000 --seed 0 --check --store-profile both`, counts, invariants, time; tell the user which corpus replaced `smoke05b-h1000`* | MP-T2 | — | minutes |
| **MP-T3** | `store/plant_readback.py`; `qa/harness/plant_layer_fidelity.py` PLANT-01 parts a–e (§A.6) | MP-T2 | none (new files) | M |
| — | *Main session: **PLANT-01** on H100 and H1000 (free); `_results.md` rows* | MP-T3 | — | minutes |
| **MP-T4** | `schema_text.py` plant paragraph by profile; `_HIDDEN_PROPERTIES` += `via_connector_uids`; `CypherRag` gains a `profile` and registry entry `cypher_rag_plant`; `corpus.py` plan per profile; `cypher_setup.py` profile check, mixed-profile refusal, hint text | MP-T3 | **yes: `harness/registry.py`** — start only after QAR-T4 is committed | S/M |
| **MP-T5** (should) | `qa/harness/cypher_expressiveness.py`: one canonical Cypher per dev family per profile, correctness and length (§A.7) | MP-T4, Neo4j | none | S/M |
| — | *Main session: **CYPHER-02** (free) on H100, H1000; and add `qa/schema_text.py` to F1's file list (`question-aware-retrieval.md` §9)* | MP-T5 | — | minutes |
| **MR-T1** | `qa/model_router/` (§B.7): deciders (Jev and label-probability through J-T1's clients, fakes in tests), rules decider, τ policy, `decide` CLI, offline `join` with gap refusal, report with oracle, random mix, cascade, AUROC; toy `answers.jsonl` tests | J-T1, QAR-T4 (rules classifier), QAR-T1 | none (reads `qa/need/` only) | M |
| — | ***MR-P1:** strong-model fixed `hierarchical` run on the 120-question H1000 slice, after F1 and ADR-0019 — **run by the user, paid, logged**, cap 1.5 × estimate* | MR-T1, QAR-P3 (cheap run) | — | §B.6 |
| — | ***MR-P2:** decisions (`jev`, `labelprob`) on the slice — **run by the user, paid, logged*** | MR-T1, J-P1 | — | cents |
| — | *Main session: **MROUTE-01** (free) report; futility check; stage 2 only on the user's approval* | MR-P1, MR-P2 | — | minutes |

S < ~150 changed lines including tests; M ~150–400.

**Order rationale.** MP-T1–T3 give a free, early partial result — the plant KG in the store and PLANT-01 — and touch no
file QAR-T4 is editing. MP-T4 waits for QAR-T4 because both edit the strategy registry. MR-T1 waits for J-T1 (its
clients) and QAR-T4 (its rules decider); its paid steps come last because they consume fixed runs that do not exist yet.

## D. ADRs proposed

- **ADR-0036** — merged plant layer, profiles, PLANT-01, `cypher_rag_plant`, `cypher_agent` on `plant`, Q6.
- **ADR-0037** — model-choice router arm, offline over fixed runs, claims M1/M2, futility stop.

On acceptance the main session updates: `kg-construction.md` §7.1–§7.2 (pointer to ADR-0036), `qa-system.md` §2.1
consumer table and §7 CypherRAG schema paragraph, `question-aware-retrieval.md` §5.5 and §9 (F1 list),
`hierarchical-and-jev.md` §5 "Not in scope" line, `00-index.md`, `40-design/README.md`.

## E. Open questions and user decisions

- **U1 — default store profile.** `both` (recommended: the store is the two graphs the user asked for) or
  `occurrence` (today's behaviour; the plant layer only on request).
- **U2 — reload vs databases.** Reload the matching profile before a CypherRAG run (recommended; one plant, one
  database) or one database per profile (no reloads; three copies of the plant in the DBMS; ADR-0036 option F).
- **U3 — the strong model** for Part B, chosen with the ADR-0019 pilot (the user does not sideline good models,
  2026-10-02). The estimate above uses Claude Sonnet 5.5's listed price as an example only.
- **U4 — Part B slice.** 120 questions at H1000 first (≈ $3.6–$7.2, estimate), extended to 240 only if informative.
- **U5 — Part B tier.** Should-item after EXP-0006's fixed runs (recommended), not before.
- **O1 — novelty (researcher).** Model routing and cascades for cost; citations owed (FrugalGPT, RouteLLM are
  candidates, **not read**).
- **O2 — `related_to` in the plant API.** Out of scope here; matters only for imported files (F4).
- **O3 — Cypher syntax.** `COUNT { }` subqueries in INV-2/INV-4 assume Neo4j 5+ syntax; verified on the user's DBMS
  in MP-T2's integration test.

## F. Figures in this note and their sources

| Figure | Source |
|---|---|
| 42,044 nodes / 120,914 relationships, 509 `PlantSection`, 1 `ProcessPlant`, 26.27 s at H1000 | `_results.md` SMOKE-05b |
| 35,532 items, 38,286 edges, P = R = 1.0 at H1000 | `_results.md` API-01 |
| 40,532 occurrences at H1000 | `_results.md` PROMPT-04 |
| 2,159 pairs, 1,001 sheets, G1 equal at H100/H1000 | `_results.md` SMOKE-04b |
| 36,214 / 77,576 / 231,628 / 37,044 | arithmetic on the rows above — **not measured** |
| ROUTE-01 / HIER-CTX-01 context sizes, 100,000-character budget | `_results.md` ROUTE-01, HIER-CTX-01 |
| per-question costs for cheap pins, CypherRAG $0.0004–$0.0045 | `question-aware-retrieval.md` §10.4 (estimates) |
| Claude Sonnet 5.5 $2 / $10 per million; glm-5.3-flash $0.15 / $0.50 and `logprobs` listed | `30-experiments/openrouter-models-2026-10-02.json`, read 2026-10-02 |
| $25 balance, staging, spend cap | user memory `project_openrouter_budget.md` (2026-10-02) |
| Strong-model slice costs, `hier_agent` $0.11 | arithmetic under §B.6's assumptions — **estimates** |
| Jev price $0.042 per million input | vendor claim, unverified (ADR-0032) |
| F1–F9 code findings | `store/`, `resolution/merge.py`, `qa/plant_api/`, `qa/graph_view.py`, `qa/corpus.py`, `qa/neo4j_view.py`, `qa/schema_text.py`, `qa/harness/cypher_setup.py`, `qa/harness/registry.py`, `qa/strategies/base.py`, read 2026-10-02 |
