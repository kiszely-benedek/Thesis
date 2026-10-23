---
component: (A) plant-graph rendering for Hierarchical and the need-aware variants; (B) the three shared PAID failures; (C) a cited P&ID domain primer; (D) Jev effort routing; (E) bounded concurrency in the harness
status: draft — awaiting review
related: [ADR-0039, ADR-0040, ADR-0041, ADR-0042, ADR-0043 (all proposed); ADR-0013, ADR-0014, ADR-0022, ADR-0030, ADR-0033–ADR-0038; merged-plant-layer-and-model-router.md; question-aware-retrieval.md; hierarchical-and-jev.md §3]
date: 2026-10-03
author: architect (Opus 5.5)
---

# Design — the plant graph first, a domain primer, effort routing, parallel calls

## 0. Recommendation

| # | Item | Decision | ADR |
|---|---|---|---|
| P1 | Where the Hierarchical family's context comes from | the in-memory `ItemGraph` (extended with visible properties); the Neo4j plant layer serves Cypher arms and the demo; PLANT-01 (e) checks equality | 0039 |
| P2 | Selection | unchanged (ADR-0030 pair, ADR-0033 programs); only the rendering changes: selected drawings → items, direct item edges, frontier items, `sheets` attribute | 0039 |
| P3 | Arms | `hierarchical_plant`, `hierarchical_need_rules_plant` primary; `hierarchical`, `hierarchical_need_rules`, `cypher_rag` become the occurrence baseline sample | 0039 |
| P4 | Legend | one fixed legend per representation at the top of the context, both representations, frozen at F1 | 0039 |
| P5 | Free metrics | evidence-item recall, evidence-edge hops, path in context, context items/sheets/chars | 0039 |
| P6 | LOOP_ACTUATED_VALVE | template v2: ask for the valve the loop's actuator moves | 0040 |
| P7 | Primer | ≤ 1,200 characters, written by a fresh researcher from cited rules, same text in every plant-reasoning prompt, on by design, off as ablation (claim P1) | 0041 |
| P8 | Router | effort routing (glm low vs default) primary; tiered escalation to Sonnet secondary; offline over fixed configurations (claims E1, E2) | 0042 |
| P9 | Throughput | `--concurrency N` threads, in-order commit, spend reservations; default 1 | 0043 |

Coder tasks: 7 new (§8), one Sonnet coder at a time, all acceptance offline. Paid steps: 2 before F1 (≈ $0.35–$0.50,
estimate), the rest folded into EXP-0006 after F1. One researcher task (the primer text).

## 1. Which part of the claim each piece serves

- **P1–P5** make the measured system the constructed knowledge graph (the title) and isolate the representation as one
  variable (Q7). Scale enters through `k`: the occurrence graph costs three edges per sheet crossing, the plant graph
  one, so the gap should grow with `k` — the same argument ADR-0036 made for Cypher (Q6), now for serializing arms.
- **P6** is benchmark validity: a question with two defensible answers measures the scorer.
- **P7** tests whether domain knowledge, held equal across arms, changes the ranking; it cannot change it by
  construction, only the level, which is why it is safe to add.
- **P8** is the cost axis (the user's "cheap and good"), now on the cheapest lever first.
- **P9** spends no novelty; it makes the paid steps an afternoon instead of a day.

## 2. What the evidence and the built code say (read 2026-10-03)

| # | Finding | Source | Consequence |
|---|---|---|---|
| F1 | T-11-1: both outgoing edges of `ProcessColumn T-11-1` end at `FlowOutPipeOffPageConnector`s on sheet 4; the neighbours `CHV-11-3`, `CHV-11-2` sit on sheet 5 behind `continues_as` and a `FlowIn…` stub. The need context held all of them (recall 1.0). Read literally, T-11-1 has no item neighbour, so `[]` is what a reader who does not follow stubs answers | free probe: H100 rebuilt in memory (headline preset, 51 units, seed 0), `hierarchical_need_rules` `retrieve` only, context dumped and parsed (scratch, not in repo); PAID-02/03/04 `answers.jsonl` | the plant rendering shows `T-11-1 -send_to-> CHV-11-3` directly (§A, §B.1) |
| F2 | LOOP FIC-30-6: `FIC-30-6` (sheet 70) `-send_signal_to->` out-signal stub `-continues_as->` in-signal stub (sheet 69) `-send_signal_to->` `ActuatingFunction FV-30-6` (loop_tag FIC-30-6) `-control->` `GlobeValve GV-30-4` (reference, no loop_tag). All 254 H100 actuators are tagged PV/FV/LV/TV. Wrong answers that named a tag named the actuator (FV-30-6 ×3, TV-27-1 ×1) | same probe; PAID-02/03 | two causes: a cross-sheet stub chain (fixed by P2) and a naming ambiguity (fixed by P6) |
| F3 | Hierarchical on TIC-27-1 (PAID-03): evidence-node recall 0.333, one ring dropped under the 100k budget → `not_present` | PAID-03 trace | a selection loss, not a format one; the plant rendering's smaller size may keep the ring (measured in PG-01, not assumed) |
| F4 | P-3-1: `CheckValve` labels are (`CheckValve`, `PipingComponent`), no `OperatedValve`; the reference and the need program walk through it (need_items 2); all three model runs named CHV-3-1 | `graph/schema.py`; `families_isolation.py`; PAID-02/03/04 | a domain error, not a format one (§B.2, Part C) |
| F5 | The shared final prompt says nothing about stubs or `continues_as`; CypherRAG's query writer gets a structure paragraph that does | `qa/prompts/final_answer.txt`; `qa/schema_text.py` | the legend (P4) removes the asymmetry for both representations |
| F6 | `ItemRecord` has tag, class, labels, unit, sheets, keys; `ItemEdge` has relation and `via`; no `loop_tag`, `measured_variable`, `piping_component_name`, `line_number`, `fluid_code` | `qa/plant_api/model.py` | PG-T1 adds visible properties |
| F7 | `fit_to_budget` and `build_need_context` call `serialize_graph` on occurrence subgraphs directly | `context_budget.py`, `need/context.py` | inject a renderer; the occurrence renderer stays the default |
| F8 | PLANT-01 (stored layer = gold and = `ItemGraph`) is designed, not run; API-01 (`ItemGraph` = gold by tag, H1000, P = R = 1.0) is the proof today | `merged-plant-layer-and-model-router.md` §A.6; `_results.md` API-01 | the in-memory source is proven against gold; the store equality is a pending check |
| F9 | MP-T1 is in progress: `graph/schema.py`, `qa/plant_api/model.py`, `store/*` are modified in the working tree | `git status`, 2026-10-03 | PG-T1 (edits `plant_api/model.py`) starts only after MP-T1 is committed |
| F10 | `sqlite3.connect(path)` with the default thread check; one `UsageMeter` per run; `n_cached`/`spent_usd` excluded from `answers.jsonl` | `llm/cache.py`, `harness/attempt.py`, `qa/models.py` | Part E |
| F11 | PAID-01…04 ran on H100, a **test** corpus (dev families). Not reported | `_results.md` | this note uses them only to find causes; the decisions are format and wording fixes, not tuned values. Future pilots use D100 |

## Part A — plant-graph context (ADR-0039)

### A.1 Source

| Option | For | Against |
|---|---|---|
| **in-memory `ItemGraph`** (chosen) | already the plant API's graph; free runs need no database; one plant object for selection programs and rendering | needs two fields and an index (PG-T1) |
| Neo4j plant layer at question time | literal "query the KG" | database in every free report; a run mixing `cypher_rag` (occurrence) and a plant arm would need two profiles, which ADR-0036 refuses; equality not yet measured |
| `Resolution.plant` directly | has every attribute | a third construction beside `ItemGraph` and the store rows; not reachable through `GraphView` |

### A.2 `ItemGraph` additions (PG-T1)

```python
class ItemRecord(BaseModel):              # qa/plant_api/model.py, additive
    ...
    #: Visible properties of the home drawing (schema.VISIBLE_NODE_PROPERTIES minus sheet_id), unit filled as unit_id is.
    properties: dict[str, str | int | float | bool] = {}

class ItemEdge(BaseModel):
    ...
    #: Visible edge properties (line_number, fluid_code, dexpi_label) of the drawn edge; for a contracted stub pair, the
    #: out-stub edge's, as resolution/merge.py does.
    properties: dict[str, str | int | float | bool] = {}

class ItemGraph:
    def item_of_key(self, local_key: str) -> str | None: ...   # paired stubs → None
```
- `crossed_sheets` is derived at render time: `(sheet_of_key(via[0]), sheet_of_key(via[-1]))` when `via` is non-empty
  (contraction already keeps the fewest-stub variant, so an edge drawn whole somewhere has `via = ()`).
- List values (`dexpi_labels`) are joined as `serialize._graphml_safe` does.
- API-01 (`harness/api_fidelity.py`) also compares, by tag, the item properties and edge properties against the gold
  plant's visible ones. PLANT-01 part (e) (MP-T3) compares them against the stored layer.

### A.3 Renderer (PG-T2) — `qa/context_render.py` (new)

```python
@dataclass(frozen=True)
class Rendered:
    text: str
    sheets: tuple[str, ...]              # sheets with selected content (full or through-line) — as today
    through_line_sheets: tuple[str, ...]
    keys: tuple[str, ...]                # occurrence keys behind the text (plant: every drawing of every shown item)
    items: int                           # plant only; 0 for occurrence
    frontier_items: int

class ContextRenderer(Protocol):
    def render(self, full_sheets: frozenset[str], through: Mapping[str, tuple[str, ...]]) -> Rendered: ...

class OccurrenceRenderer:  # today's subgraph_with_through_lines + serialize_graph; legend off by default
class PlantRenderer:       # holds the view's ItemGraph
```
`PlantRenderer.render`:
1. selected keys = every key on `full_sheets` ∪ every key in `through`;
2. items = `{item_of_key(k)}` over them, minus `None` (paired stubs vanish);
3. edges = item edges with both ends in items;
4. frontier = the far ends of item edges with exactly one end in items, with those edges; frontier items are written
   like any item (they are real items), their other edges are not;
5. GraphML via the shared writer: node id = item id; attributes = `properties` + `node_class` + `sheets` ("|"-joined);
   edge attributes = `relation` + `properties` + `crossed_sheets`;
6. legend first (§A.6).
- `fit_to_budget(view, selection, budget_mode, max_chars, renderer=OccurrenceRenderer(view))` and
  `build_need_context(view, core, selection, max_chars, renderer=…)` call `renderer.render` instead of
  `serialize_graph`. Same plans, same order of cuts; lengths are the rendered lengths, so a plant context is cut less.
- Golden test: with the default renderer, every existing strategy's context on a toy corpus equals the `eba87c0`
  output byte for byte.

### A.4 Strategies and names

| Name | Representation | Legend | Role |
|---|---|---|---|
| `hierarchical_plant` | plant | always | primary |
| `hierarchical_need_rules_plant` (later `_labelprob_plant`, `_jev_plant`) | plant | always | primary |
| `hierarchical`, `hierarchical_need_rules` | occurrence | param `legend` (default false) | baseline sample (EXP-0006 sets `legend: true`) |
| `context_rag` | occurrence | none | EX01 only (ADR-0038) |

The representation is fixed by the name, never a parameter, so a name means one thing in every report.
`need_strategy_name(classifier, representation)` builds both forms. The unit-router fallback is unchanged.

### A.5 Need-aware variant on the plant

Programs already run on `ItemGraph`. The core (anchor sheets whole) and the need part (`through` keys per sheet) are
built as today; `PlantRenderer` maps them to items, so the need items appear with their direct edges and no stub keys
are needed. The fallback is `hierarchical_plant`, not `hierarchical`.

### A.6 Legends (model-facing, `qa/prompts/legend_plant.txt`, `legend_occurrence.txt`)

Drafts; the coder may tighten the wording but not add content. Both are format descriptions, not domain rules.
- **Plant:** "How to read the description below. Each node is one plant item (equipment, valve or instrument
  function), even if it is drawn on several sheets; `sheets` lists every sheet it is drawn on. Each edge is a direct
  connection between two items. `send_to` is material flow from source to target, also across sheets: lines that
  continue on another sheet are already joined, and such an edge has `crossed_sheets`. `send_signal_to`, `control` and
  `measured_by` are instrument wiring. Items at the edge of this excerpt may have connections that are not shown."
- **Occurrence:** the structure paragraph of `schema_text.py` restated for GraphML: one node per drawn symbol with its
  `sheet_id`; `FlowOut… -continues_as-> FlowIn…` joins a line that leaves one sheet to where it continues; the three-
  edge crossing pattern; `same_tagged_item_as` from a repeated drawing to the main one; connectors have no tag.

### A.7 Trace additions

`representation`, `serialized_items`, `frontier_items`, `context_sheets` (union of the shown items' `sheets`). All
Hierarchical keys keep their meaning; `serialized_keys` for plant arms = every drawing key of every shown item, so the
built `add_routing_metrics` computes evidence-item recall unchanged.

### A.8 Free metrics (PG-T3)

| Metric | Definition | Both representations |
|---|---|---|
| evidence-item recall | share of evidence nodes (gold ids) with ≥ 1 drawing among `serialized_keys` (the built formula) | yes |
| evidence-edge hops | per evidence edge (u, v): shortest directed path from any shown node of u to any of v in the rendered graph, over all shown relations, `continues_as` forward, `same_tagged_item_as` both ways; report share with hops = 1, mean of finite hops, share absent | yes |
| path in context | FLOW_PATH and CONNECTED-yes: a `send_to` path source → target exists in the rendered graph (stubs and identity links followed on occurrence) | yes |
| context items, sheets, characters | from the trace | yes |
| strict / relaxed sheet routing | as built; equal across representations by construction (test) | yes |

**PG-01 (free, main session):** `retrieve` only, both representations, `hierarchical(_plant)` and
`hierarchical_need_rules(_plant)`, ROUTE-01 settings (`flow_path`, `through_line`, hops 1, 100k), on (a) the PAID-01
36-question slice (regenerated deterministically; its `question_set_sha256` must equal `0107b9e5…`) and (b) the full
H100 and D1000 dev question sets. Rows per family and k-bin. Expected direction, to be checked, not asserted: T-11-1
evidence-edge hops 3 → 1 at equal recall.

### A.9 Tests (offline)

| Component | Tests |
|---|---|
| `ItemGraph` properties | toy split plants at duplication 0.0 / 0.5: item properties = home drawing's visible ones; a contracted pair's edge keeps the out-stub edge's `line_number`; `item_of_key` maps references to the home, paired stubs to `None`; API-01 property check passes on the toy and fails on one injected change |
| `PlantRenderer` | a tank on sheet A whose two outgoing edges are both cut renders two direct `send_to` edges with `crossed_sheets`; no node of a connector class unless unpaired; frontier items present with only their boundary edge; repeated drawing → one node with both sheets; deterministic bytes |
| equivalence | with the same selection, plant evidence-item recall ≥ occurrence evidence-node recall on every toy question; selection traces (`routed_sheets`, `through_line_sheets`) equal between paired names |
| byte identity | default renderer: contexts of `hierarchical`, `hierarchical_need_rules`, `context_rag` unchanged (golden hash) |
| metrics | evidence-edge hops: 1 for a direct edge, 3 for a crossing on the occurrence toy, absent when dropped |
| import ban | `qa/context_render.py` joins the strategy-side ban list (no `qa.questions`, `qa.harness`, `qa.corpus`, gold) |

## Part B — the three shared failures

### B.1 NEIGHBOURS_DOWNSTREAM T-11-1 (both models `[]`, recall 1.0)

- **Cause, verified free (F1):** the neighbours are only reachable through a stub chain, and the prompt never explains
  stubs. Hierarchical (not need-aware) answered it correctly at default effort in PAID-02 and wrongly at low effort in
  PAID-03, so a model can follow the chain when it reasons longer.
- **Free verification of the fix:** PG-T2's renderer test (the T-11-1 shape on a toy) and PG-01's evidence-edge hops on
  the real question. Neither involves a model.
- **Paid confirmation:** PG-P1 (§9) on the same slice. The clean attribution — representation vs legend — is Q7 in
  EXP-0006, where both representations carry their legends.

### B.2 UPSTREAM_ISOLATION P-3-1 (both named check valve CHV-3-1)

- The context was complete; the error is domain knowledge (F4). The reference is correct by P&ID practice (a check
  valve is not operated), so no benchmark change.
- Fix path: the primer (Part C), only if the researcher finds a citable source for the check-valve rule. No free
  verification is possible; P1's per-family table reports it.

### B.3 LOOP_ACTUATED_VALVE (0/2 for all strategies at low effort; Hierarchical and Cypher 0/2 at default)

- **Formatting cause: yes, two.** (1) The signal chain crosses sheets through two signal stubs (F2) — removed by the
  plant rendering. (2) The loop tag sits on the actuator and the stubs, not on the valve, so a reader searching for the
  loop finds `ActuatingFunction FV-30-6` first.
- **Naming cause:** `FV-30-6` is, by the cited tag convention (L17), the loop's valve tag. Fixed by ADR-0040's v2
  wording; must land before the primer.
- **Selection cause (Hierarchical only):** TIC-27-1's ring was dropped by the budget (F3).
- Sonnet and GLM at default effort with `need_rules` got both right (PAID-02, PAID-04), so the chain is followable;
  low effort does not follow it.

## Part C — the domain primer (ADR-0041)

### C.1 Candidate topics and source status

| Topic | Repo source | Status |
|---|---|---|
| a line continuing on another sheet is mutually referenced at both ends | `pid-structural-rules.md` S1 (ISO 10628 5.3.3.2) | verified |
| signal lines are not pipes; signals continue across sheets at a reference box | C7 (ISO 10628 5.3.1 c; KLM) | verified |
| control-valve stations: block valves and a bypass, "in general" | L9 (HNF 3.2.4.2) | verified |
| instrument tag = function letters + loop number; one loop shares the number | L17 (CHE3, W-PID; ISA-5.1 text not read) | verified, secondary |
| P&IDs are used to plan lockout–tagout | TOG 1.1 | verified |
| a check valve is self-acting and cannot be closed by an operator; isolation uses operated (block) valves | L1 gives the location only; the function is marked not verified (`Notes/pid-szerkezeti-szabalyok.md` l. 103) | **source owed** |
| flow reads left to right with continuity sheet to sheet | S7 (HNF 3.2.2) | verified; likely irrelevant to a text graph — researcher decides |

### C.2 Provenance protocol (R-PR1, researcher)

Inputs: the source list, `graph/schema.py`'s class and relation names, the topic list (disclosed as influenced by
dev-family failures on H100). Not given: question templates, PAID results, this note, the sealed file. Outputs:
`qa/prompts/primer_pid_v1.txt` (≤ 1,200 characters) and `10-literature/primer-sources.md` (line → quote → source →
location). Checks before use: architect (content rules of ADR-0041 point 1 only), user (approves the text).

### C.3 Plumbing (PR-T1)

`<<PRIMER>>` slot in `final_answer.txt` and `cypher_query.txt` (agent prompts when built); removed with its blank line
when off (golden test: prompts byte-identical to today). `RunConfig.primer`, `--primer`, `prompt_hashes` include the
file. Freeze: already covered by `qa/prompts/`.

**Built 2026-10-04 (PR-T1, uncommitted at writing):** `qa/primer.py`, `prompts/primer_pid_v1.txt` (1,195 chars;
block with heading 1,280). Slot after the first paragraph under the heading "General P&ID reading conventions
(background knowledge, not facts about this plant)". CLI default on, `--no-primer` for the ablation; `RunConfig.primer`
defaults to off so old configs load unchanged. Both legends gained one reading-direction sentence (equipment
-measured_by-> transmitter -send_signal_to-> controller -send_signal_to-> actuator -control-> valve), checked against
`schema.py`, `pydexpi_adapter._relation_of` and `canonical_programs.py`. Known tension: primer line B9 (V = valve)
vs the generator tagging the *actuator* `FV-…` — see LOOP_ACTUATED_VALVE (B.3); to be solved in the generator.

### C.4 Ablation

Primer on in every EXP-0006 primary run. Off: `hierarchical_need_rules_plant` on the first-stage slice (5 per family per
test corpus) at the same pin. Claim P1 (ADR-0041). EXP-0001 runs with it off.

## Part D — effort routing (ADR-0042)

### D.1 Configurations

`glm-low` = PAID-03 pin; `glm-default` = PAID-02 pin; `sonnet` = PAID-04 pin. Each is a separate pin JSON, each fixed
run a separate run id; the router never mixes configurations inside one run (ADR-0014 point 4).

### D.2 Arms (computed offline by ER-T1)

- `effort_routed_<decider>`: p("glm-low correct") ≥ 0.5 → glm-low, else glm-default.
- `escalated_<decider>`: start as above; on a self-flag (`not_present`, PARSE_FAILURE, DID_NOT_FIT, RETRIEVAL_ERROR)
  move up one tier, up to sonnet.
- Free references: always-low, always-default, oracle (cheapest correct configuration), random at the same low share,
  oracle cascade (gold-flagged escalation, upper bound only).

### D.3 What ER-T1 changes in MR-T1's design

Candidates are `{name: ModelPin}` configurations; `join.py` joins per configuration and refuses on a gap, printing the
missing question ids and the harness command per configuration; the report adds the tiered cascade, latency (p50/p90)
next to cost, and AUROC per decider. Free deciders first (rules, oracle, random, self-signal); Jev and label-probability
after J-T1.

### D.4 Runs and cost (estimates from measured per-question means)

Per question, `hierarchical_need_rules` on H100: glm-low $0.050 / 36 = $0.00139 (PAID-03); glm-default
$0.0795 / 36 = $0.00221 (PAID-02); sonnet $0.034 mean (PAID-04). Plant contexts and H1000 differ, so these are
estimates.

| Step (after F1, H1000, `hierarchical_need_rules_plant`) | Questions | Estimate |
|---|---|---|
| ER-P1 glm-low fixed run | 120 | $0.17 (often already the EXP-0006 fixed run, then $0) |
| ER-P2 glm-default fixed run | 120 | $0.27 |
| futility check (free): default − low < 0.02 → stop | — | — |
| ER-P3 sonnet on flagged ∪ gold-wrong-at-default (needed for the cascade and the oracle) | ≤ 40 | ≤ $1.35 |
| ER-P4 (optional) sonnet on a random 36 of the 120 (always-strong anchor) | 36 | $1.21 |
| decisions: label-probability (~300 input tokens each at $0.15 per million); Jev (vendor price, unverified) | 120 | ≈ $0.01 |

Each paid step: `--max-spend-usd` at 1.5 × its estimate, the balance read after.

## Part E — bounded concurrency (ADR-0043)

Mechanism in ADR-0043 points 1–5. Files: `harness/runner.py` (pool, reorder buffer, warm-up), `harness/attempt.py`
(per-item meter and senders), `harness/usage_meter.py`, `harness/spend_cap.py` (reservations under a lock),
`harness/cli.py` (`--concurrency`), `llm/cache.py` (thread-safe connection and lock), `llm/client.py` (log lock;
should: single-flight per cache key). Tests as ADR-0043 point 6. None of these files is in MP-T1's diff.

## 8. Ordered coder tasks (one Sonnet coder at a time; each ends green on ruff, mypy --strict, pytest, offline)

Merged with the existing queue (MP-T2…T5 from `merged-plant-layer-and-model-router.md` §C; QAR-T5…T10 from
`question-aware-retrieval.md` §15). New tasks in **bold**.

| # | Task | Depends on | Collision | Size (estimate) |
|---|---|---|---|---|
| 0 | MP-T1 (in progress: `graph/schema.py`, `store/`, `plant_api/model.py`) | — | — | M |
| 1 | **PG-T1** `ItemGraph` properties, `item_of_key`, API-01 property check (§A.2) | MP-T1 committed | `plant_api/model.py` (MP-T1) | S/M |
| 2 | **PG-T2** renderer protocol, `PlantRenderer`, legends, `hierarchical_plant`, `hierarchical_need_rules_plant`, registry entries, golden byte-identity test (§A.3–A.6, A.9) | PG-T1 | `harness/registry.py` (MP-T4 later; sequential) | M |
| 3 | **PG-T3** free metrics (evidence-edge hops, path in context, context items/sheets) in `routing_gold` and `route_report` with `--representation` (§A.8) | PG-T2 | none | S/M |
| — | *Main session: **PG-01** (free), `_results.md` rows* | PG-T3 | — | minutes |
| 4 | **QB-T1** LOOP_ACTUATED_VALVE v2 template, rules-classifier pattern, question sets regenerated (ADR-0040) | — (after PG-T3 to keep PG-01 on v1 questions comparable with PAID) | `qa/need/rules.py` | S |
| 5 | **HC-T1** harness concurrency (Part E) | — | none | M |
| — | ***PG-P1:** plant arms on the 36-question slice — **run by the user, paid, logged** (§9)* | PG-T2, HC-T1 (optional) | — | ≈ $0.34 |
| 6 | MP-T2 → (SMOKE-08) → MP-T3 (PLANT-01 now includes properties) → MP-T4 (`cypher_rag_plant`) | as planned | MP-T4: registry | — |
| — | ***PG-P1b:** `cypher_rag_plant` on the slice at glm-low — **run by the user, paid, logged*** | MP-T4 | — | ≈ $0.006 |
| 7 | MP-T5 (should) | MP-T4 | — | S/M |
| 8 | **PR-T1** primer plumbing (Part C.3); the text comes from R-PR1 | R-PR1 approved, QB-T1 | prompts | S |
| 9 | QAR-T5 need report — extended: both representations, the PG-T3 metrics | PG-T3 | — | S |
| 10 | **ER-T1** (replaces MR-T1): configurations, free deciders, tiered cascade, offline join, report (Part D) | QAR-T1 (built) | none | M |
| 11 | QAR-T6 (agents), QAR-T7 (should), J-T1, QAR-T8, QAR-T9 — as planned; ER-T1's Jev and label-probability deciders after J-T1 | as planned | — | — |
| — | *F1 freeze (now also hashes `context_render.py`, legends, primer)* → QAR-T10 (sealed) | all above | — | — |
| — | ***QAR-P3** with the plant arms, baseline sample, primer-off ablation; then **ER-P1…P4** — run by the user, paid, logged* | F1 | — | §9 |

**Order rationale.** PG-T1–T3 give a free, early result (PG-01) on the user's first priority and need no database.
QB-T1 is tiny but changes question sets, so it waits until PG-01 has run on the v1 slice. HC-T1 is independent of
every MP file and makes every later paid step faster; it can move up to position 1 if the user wants PG-P1 sooner.
PR-T1 waits for an approved primer text and for QB-T1.

## 9. Paid steps (estimates; each with a hard cap at 1.5 × the estimate)

| Step | What | Estimate | Basis |
|---|---|---|---|
| PG-P1 | `hierarchical_plant`, `hierarchical_need_rules_plant` on the PAID-01 slice (36 q, H100), glm-low and glm-default, legend on, primer off | ≈ $0.34 (cap $0.50) | the occurrence arms cost $0.110 + $0.0795 (PAID-02) and $0.100 + $0.050 (PAID-03) on the same slice; plant contexts should be smaller, so an upper bound |
| PG-P1b | `cypher_rag_plant` on the slice, glm-low | ≈ $0.006 | PAID-03 cypher_rag $0.0056 |
| QAR-P3 additions | primer-off run (120 q, H1000) + occurrence baseline sample (`hierarchical_need_rules` + `cypher_rag`, 120 q per test corpus) at glm-low | ≈ $0.17 + 2 × $0.19 | PAID-03 per-question means |
| ER-P1…P4 | Part D.4 | $0.45 without Sonnet; up to ≈ $3.0 with both Sonnet steps | PAID-02/03/04 |

PG-P1 is a pipeline check on a test corpus with dev families (F11): not reported, and it chooses nothing.

## 10. ADRs proposed

ADR-0039 (plant graph first; supersedes ADR-0022 S1 in part; amends ADR-0036 point 6 and ADR-0035), ADR-0040 (loop
wording), ADR-0041 (primer), ADR-0042 (effort routing; supersedes ADR-0037 in part), ADR-0043 (concurrency).

On acceptance the main session updates: `merged-plant-layer-and-model-router.md` §A.8 (consumer table) and §C (MR-T1 →
ER-T1); `question-aware-retrieval.md` §7, §9 (F1 list), §15 (queue); `qa-system.md` §9 (template v2), §11 (concurrency);
`00-index.md`; `40-design/README.md`.

## 11. Open questions and user decisions

- **U1 — source of the plant context:** in-memory `ItemGraph` (recommended) or the Neo4j plant layer.
- **U2 — frontier items** in the plant rendering: yes (recommended; the plant analogue of a stub's sheet reference) or
  no (strictly the selected items).
- **U3 — legends on both representations** (recommended), so Q7 compares representations, not explanations.
- **U4 — LOOP_ACTUATED_VALVE:** reword to v2 (recommended), accept both tags, or leave it.
- **U5 — primer:** written by a fresh researcher from cited sources, on by design, off as ablation (recommended); the
  check-valve rule ships only with a source.
- **U6 — effort of the EXP-0006 fixed runs** (ties to ADR-0019): glm-low for every arm (recommended: PAID-03 had 1
  retrieval error where default effort had 14, and it is the cheapest and fastest), with glm-default only as the
  routed arm's second configuration.
- **U7 — Sonnet steps:** escalated set only (≤ $1.35, estimate) or also the random-36 always-strong anchor ($1.21).
- **U8 — concurrency:** default 1; recommended 4 for paid runs, raised only after a clean run.
- **U9 — PG-P1 approval** (≈ $0.34, cap $0.50).
- **O1 (researcher):** a citable source for the check-valve rule; the novelty check owed by ADR-0037 now also covers
  effort routing.
- **O2:** OpenRouter rate limits for glm-5.3-flash and Sonnet at N = 4–8 are unverified.
- **O3:** whether GLM's "default" effort is stable over time at the provider (ADR-0042 revisit trigger).

## 12. Figures in this note and their sources

| Figure | Source |
|---|---|
| 27/36, $0.050, 3.8 s (glm low); 31/36, $0.0795, 18.5 s (glm default); 33/36, $1.211, $0.034/question, 3.7 s (Sonnet); 14 vs 1 retrieval errors; $0.110/$0.100 Hierarchical, $0.145/$0.0056 CypherRAG | `_results.md` PAID-02, PAID-03, PAID-04 |
| T-11-1, P-3-1, LOOP answers and traces (FV-30-6 ×3, TV-27-1 ×1; recall 0.333 on TIC-27-1; need_items 2 on P-3-1) | `30-experiments/paid02/`, `paid03/`, `paid04/` `answers.jsonl`, read 2026-10-03 |
| T-11-1 and FIC-30-6 edge chains; 254 actuators PV/FV/LV/TV; 0 duplicate tags among 3,539 plant nodes at H100 | architect scratch probe 2026-10-03 (H100 rebuilt in memory, seed 0, no model call; not in repo) |
| 38,286 = 38,286 edges, P = R = 1.0, H1000 | `_results.md` API-01 |
| ratio ≈ 1.35 occurrence vs merged whole-plant GraphML | `_results.md` PROMPT-02 |
| ≈ 50 minutes for PAID-02 | main session's report, 2026-10-03 (not a `_results.md` row) |
| listing prices $0.15 per million input (glm-5.3-flash), $2 / $10 (Sonnet 5.5) | `30-experiments/openrouter-models-2026-10-02.json` via `merged-plant-layer-and-model-router.md` §F |
| per-question means, slice costs, primer token cost, wall-time scaling | arithmetic on the rows above — **estimates** |
