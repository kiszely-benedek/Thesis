---
component: tuning of the Q&A system on v2 plants — a separately labelled system V2T (tuned Cypher tier, tuned graph agent, cascade_v4), accuracy first
status: draft — awaiting review
related: [ADR-0061 (proposed); ADR-0060 (status amendment: tune before R4/R5), ADR-0057 Q2, ADR-0053, ADR-0048, ADR-0036, ADR-0029, ADR-0044]
date: 2026-10-27
author: architect (Opus 5.5)
---

# Design — tuning the Q&A system on v2 plants (V2T)

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| R1 | What is built | A new, separately labelled system **V2T**. Additive only: new strategy names, prompt files, params, policies and one new store profile. F1 and every v1 number stay; F1 replays stay byte-identical (§5.3). |
| R2 | Untagged fittings | A **line view** in both tiers: an item-to-item flow relation that passes through fittings and inline components (`line_to` in Neo4j, relation group `"line"` in the plant API), a `kind` on every item, a `Valve` umbrella label, and `[no inflow]` / `[no outflow]` markers. `send_to` stays (§4.1). |
| R3 | Cypher timeouts | Query-shape rules in a new prompt, the smaller `line_to` graph, timeout 30 s → 120 s, repair on timeout. No hop caps. Values fixed by a free shape bench first (QT-0). |
| R4 | Cypher syntax errors | **One repair round** with the database's error message (also on timeout and memory errors). |
| R5 | Cascade | **cascade_v4** = tuned Cypher → tuned agent, Cypher accepted only if answered, not abstained, has rows **and was not cut at the row cap**. **No 120 s cutoff**: a 900 s hang guard only. `cascade_v4_iso` (first-valve questions start at the agent) is chosen or rejected by a rule fixed now (§7.4). |
| R6 | Gold definitions | **No change.** UPSTREAM_SOURCES, "equipment items and valves" and anchor exclusion are kept; the reasons are in §3. |
| R7 | Protocol | Tuning set T = **X100g2s211**; held-back validation V = **X100g2s212 + X1000g2s213**. At most 3 rounds on T, then V once. Estimate **$1.8–3.7**, caps **≈ $5.5**. Then E7 freezes V2T (§7). |
| R8 | Headline metric for V2T | Accuracy without a deadline is primary. acc@120, median and p90 latency are reported, not claimed (consultant via user, 2026-10-27). |

## 1. Evidence

Sources: `data/runs/exp0007/dev_check/report/{dev_report.md,dev_report.json,failures.jsonl}`, run records
`data/runs/exp0007/dev_check/runs/Q7-{CYP,AG}-D100g2/{answers,calls,timings}.jsonl`, questions
`data/runs/exp0007/dev_check/questions/D100g2/questions.jsonl`, v1 references `data/runs/cv1/infra/runs/INF-AGL3-D100`,
`INF-CYPL2-D100`. "Computed" = architect scratch computation 2026-10-27 over these files. Gold-graph facts come from
the rebuilt D100g2 corpus (`load_corpus_artifacts`, offline, no Neo4j).

| Fact | Value | Source |
|---|---|---|
| Accuracy D100g2 (n = 163): Cypher / agent / cascade_v3@120 | 0.595 / 0.840 / 0.896 | dev_report.md |
| Same, v1 D100 (n = 180) | 0.733 / 0.972 / — | INF-CYPL2-D100, INF-AGL3-D100 (computed) |
| Cypher right & agent right / only agent / only Cypher / neither | 86 / 51 / 11 / 15 | computed |
| cascade_v3 without the cutoff | 148 correct = the two-tier oracle (148) | computed: 17 failures − 2 late but correct |
| Cypher retrieval errors | 39: 23 syntax, 15 timeouts, 1 memory pool | answers.jsonl `cypher_error` |
| v1 D100 Cypher retrieval errors | 31, all syntax, no timeouts | INF-CYPL2-D100 (computed) |
| Agent questions with a truncated step / correct among them | 44 / 28 | computed (`agent_steps[].truncated`) |
| Agent stops on prompt budget / wrong among them | 8 / 5 | computed (`stop_reason`) |
| Agent `filter` calls refused for label `"Valve"` | in 6 of the wrong answers | traces (§2.3) |
| Dev references longer than 50 tags | 8 (6 DOWNSTREAM_IN_UNIT, 2 FLOW_PATH); longest 326 tags, k = 58 | questions.jsonl (computed) |
| Late but correct isolation answers | EA-4401: Cypher 39.3 s + agent 92.0 s; EA-1701: 41.2 s + 80.8 s | timings.jsonl `wall_s` |
| Cost per question, Cypher / agent (harness mean) | **$0.000475 / $0.000866** | Q7 logs `mean_total_cost_usd` |
| Agent, first 140 questions | $0.00089 | `caps_dev_resume.json` basis line |
| Cypher query-writing call, mean | $0.000384 | answers.jsonl `cypher_call` (computed) |
| Agent cost: truncated questions / the rest / prompt-budget stops | $0.002062 / $0.000424 / $0.003978 mean | computed |
| Gold graph D100g2 | 9,325 nodes, 9,886 edges; untagged flow fittings ≈ 2,690 (PipeTee 1,043, BlindFlange 921, FlangedConnection 244, …); tagged inline components: ConicalStrainer 122, RestrictionOrifice 43, FlowMeasuringElement 30, … | computed |
| Loop heads | LSHH-10004, LSHH-34002, CSHH-53014, HS-43036, PI-20022 are `ProcessInstrumentationFunction`; FIC-4061 is `ProcessControlFunction`; T-401 is a `ProcessColumn` | gold graph |
| Neo4j | Kernel 2026.09.0 enterprise, heap max 1 GiB; transaction pool limit 716.8 MiB | `guards/logs/load_H1.json`; the memory error text |

**The key fact.** Without its cutoff, cascade_v3 already picks the right tier wherever one tier is right (148 =
oracle). A better policy can win back only the 2 late answers. The other 15 failures are wrong in **both** tiers, so
only tier fixes raise accuracy.

## 2. Classification

Classes: **S** = system defect, **G** = gold-definition question, **C** = scoring issue, **P** = policy/deadline.

### 2.1 The 17 cascade failures

| Family (n) | Question(s) | Trace evidence | Class |
|---|---|---|---|
| NEIGHBOURS_DOWNSTREAM (7) | BFV-16005, K-3801, T-1601, PSV-29012, PSV-6017, PSV-25010 | The direct successor is an untagged `PipeTee`/`FlangedConnection`. Cypher filters `send_to` targets to equipment and valves: 0 rows (T-1601: the 5 direct ones of 10). The agent's `neighbours` returns the fitting; it answers `[]`. | S: no fitting look-through |
| | GTV-12009 | GTV → flange → **STR-12010** (`ConicalStrainer`) → flange → P-1203. Agent answers STR-12010. | S (taxonomy unknown to the system); G2 |
| UPSTREAM_SOURCES (3) | F-201A | Cypher: stray last line `ાયર` (syntax). Agent adds TK-101/TK-102, which have inflow (TK-101 ← YV-1002). | S; G1 |
| | F-1402, P-4102 | Cypher: timeout / stray token. Agent: traverse cut at 50 items, prompt budget; answers tanks instead of the 11 / 41 line-start valves. | S: truncation, no line-start marker; G1 |
| DOWNSTREAM_IN_UNIT (3) | E-3301 | Cypher has no unit filter, 200 rows, cut; the cascade accepts it. Agent: refused label `"Valve"`, list cut at 50, not_present. | S; accept rule |
| | P-4002, P-1602 | Cypher = gold **plus the anchor itself** (on a recycle; 7 of 10 dev anchors sit on a cycle). Agent: lists cut at 50. | S (anchor convention); G3 |
| FLOW_PATH (2) | BFV-27007→T-3301 | Cypher: timeout (unbounded path bound to a variable). Agent: lists 4 strainers, so the path fails `score_path` (a strainer pair is not a valid edge). | S; G2 |
| | CHV-12001→XV-54011 | 326-tag path. Cypher: one row per position, cut at 200 rows → not_present. Agent: path result cut at 4,000 chars → not_present. | S: caps |
| UPSTREAM_ISOLATION (2) | EA-4401, EA-1701 | Agent correct, Cypher + agent wall time 131.3 s / 122.0 s > 120 s. | P |

### 2.2 The Cypher tier: 39 errors and 27 wrong answers

| Class | n | Families | Evidence |
|---|---|---|---|
| E1 stray last token after a complete query | 21 | LOOP_ACTUATED_VALVE 7, INSTRUMENTS_OF_ITEM 3, LOOP_MEASURED_EQUIPMENT 2, LOOPS_NEAR_ITEM 2, UPSTREAM_SOURCES 2, CONNECTED 2, NO_PATH 2, LOOKUP_UNIT 1 | `THOOK`, `veg`, `ક્ષણ`, `Winvalid`, `TS: stop`, a lone ```` ``` ````… on the last line. S (model output). v1 had 31 syntax errors on D100 too: this predates v2. |
| E2 alias with spaces | 2 | CONNECTED, NO_PATH | `AS can_reach E-501`, `AS tags in order`. S |
| E3 timeout | 15 | UPSTREAM_ISOLATION 9, FLOW_PATH 2, NO_PATH 2, CONNECTED 1, UPSTREAM_SOURCES 1 | Every one is an unbounded `send_to*`, mostly bound to `p` and `UNWIND nodes(p)`. That enumerates every path. v2's recycles, spares and bypasses make this explode; v1 had none. S |
| E4 memory pool | 1 | CONNECTED | `OPTIONAL MATCH path = …*1..` with the path returned. S |
| W1 fittings | 8 | NEIGHBOURS_DOWNSTREAM | as §2.1. S |
| W2 v1 instrument vocabulary | 8 | LOOPS_NEAR_ITEM 6, LOOP_MEASURED_EQUIPMENT 1, LOOP_ACTUATED_VALVE 1 | The query requires `:ProcessControlFunction`; the v2 heads LSHH/CSHH/PI are `ProcessInstrumentationFunction`. T-401 is matched as `:Tank` but is a column. PI-20022 sits one `send_signal_to` hop past the sensor. The schema text still describes v1's single chain. S |
| W3 `unit_id` as an integer | 2 | CROSS_UNIT | `{unit_id: 17}`; stored values are strings. S |
| W4 reach semantics | 4 | DOWNSTREAM_IN_UNIT | 2 without a unit filter (one also cut at 200 rows), 2 with the anchor included. S |
| W5 isolation semantics | 1 | UPSTREAM_ISOLATION | E-403: every upstream valve, not the first operated valve per route. **8 of the 9 timed-out isolation queries have the same wrong semantics.** S |
| W6 row cap | 1 | FLOW_PATH | as §2.1. S |
| W7 unknown tag answered `[]` | 3 | UNANSWERABLE_TAG (NEIGHBOURS wording) | 0 rows, and the final step cannot tell "no such tag" from "no neighbours". S |

**Consequence of W5.** If only the timeouts were fixed, isolation questions would turn from escalated errors
(the agent then answers correctly, 10/10) into **accepted wrong answers**. That is why §4.4 keeps an isolation
route variant.

### 2.3 The agent tier: 26 wrong (for the fixes; 15 overlap §2.1)

| Class | n | Evidence |
|---|---|---|
| A1 fittings | 7 | NEIGHBOURS_DOWNSTREAM, as §2.1 |
| A2 inline components listed on a path | 5 | FLOW_PATH: STR-…, MX-29003 (`InLineMixer`) in the answer. The parallel-pump route itself is accepted: `score_path` takes any valid path. |
| A3 large result sets | 8 | DOWNSTREAM_IN_UNIT 6, FLOW_PATH 2 (k = 22, 58). Lists cut at 50 items / 4,000 chars, label `"Valve"` refused, `walk_only` unused. |
| A4 sources | 6 | UPSTREAM_SOURCES: traverse cut, tanks named despite "nothing flowing into them", missed line starts. |

No agent failure is a scoring issue (C). The FLOW_PATH ties are scored correctly.

## 3. Gold-definition questions (decided before any v2 test set is drawn; not from test outputs)

| # | Question | Options | Recommendation and reporting |
|---|---|---|---|
| G1 | UPSTREAM_SOURCES: is the "source" the open-line-start valve (gold) or the tank? | A. keep: the question text itself says "with nothing flowing into them". B. Redefine as "the first equipment item with no equipment upstream": this needs new wording, which is a rewording. C. Accept both: the score then no longer measures the question. | **A.** The v1 gold is the same rule (v1 D100 answers name `V-1-1` and `GV-1-x`), so v1/v2 stay comparable. On v2, tanks have inflow (TK-101 ← YV-1002). Report it as a v2 effect in the per-family table. |
| G2 | Are strainers and inline mixers "equipment items or valves"? | A. keep the DEXPI taxonomy (gold): they are piping components, passed through. B. Scoring strips tagged inline components from path answers, as it strips connectors. C. Count them as path items: needs a rewording ("every tagged item"). | **A**, plus the system fix (R2). B would make sets and paths inconsistent (sets would stay strict), and it was proposed after seeing outputs. If the user prefers B, it is v2-only (v1 has no such items, so v1 scores are unchanged) and is reported as a scoring rule. |
| G3 | DOWNSTREAM_IN_UNIT: should the anchor be listed when it lies on a recycle? | A. keep: the anchor is excluded, which is the natural reading. B. Include it: this changes the v1 gold too, and that is forbidden. | **A**, plus a final-answer rule (§4.4). The inside-unit walk equals any-route reach on all 10 dev questions (computed), so the unit rule is not an issue. |

No gold code changes, so no question set is regenerated. `qa/questions/*` and `qa/harness/gold.py` stay untouched.

## 4. Tuning options

### 4.1 (a) Seeing through untagged fittings

| Option | How | Effect / risk |
|---|---|---|
| F-A prompt only | Describe the fittings. The Cypher prompt gets a quantified-path pattern; the agent is told to use `traverse` with `stop_at`. | Cheap, but it relies on a low-effort writer composing QPP with long label lists. No `Valve` label exists to stop at (the agent tried `"Valve"` and was refused). |
| **F-B line view (chosen)** | `graph/line_view.py` (pure): `fold_line_edges(classes, tags, flow_edges) -> list[LineEdge]`, `kind_of(node_class) -> Kind`. Line items are `EQUIPMENT_CLASSES ∪ VALVE_CLASSES` (`graph/schema.py`); everything else on a pipe is passed through and recorded in `via_tags` (tagged inline components) and `n_fittings`. Agent: relation group `"line"`, filter field `kind`, label alias `Valve`, kind in item lines, line-end markers. Neo4j profile `plant_lines`: `(:PlantItem)-[:line_to {via_tags, n_fittings}]->(:PlantItem)`, an extra `:Valve` label, a `kind` property. | Answers the question the way it is asked, in both arms, by one rule. About 2,690 nodes leave the line graph, which also shrinks path searches. Risk: the same class sets as the gold. These are schema facts, not answers (§5.2), and the system builds them from the drawings, not the plant. |
| F-C fold fittings out entirely | Replace `send_to`. | Loses pipe-level detail (strainers, blinds) that demo users and other questions need. |
| F-D route those needs to the agent | Need-label routing. | Fixes neither tier. |

### 4.2 (b) Cypher timeouts

| Option | Effect / risk |
|---|---|
| T-A timeout 30 → 120 s only | Exponential enumeration is unlikely to finish. Unmeasured: QT-0 measures it for free. |
| **T-B query-shape rules (chosen)** | A new prompt says: never bind an unbounded variable-length path. For a set, use `DISTINCT` end nodes; for a route, `shortestPath` / `SHORTEST 1`; for reachability, `EXISTS` with `line_to`. Also one short generic example per shape (no family wording). Risk: overfitting the prompt; held-out families in R5 guard against it. |
| **T-C `line_to` (from F-B)** | A smaller graph for every path query. |
| **T-F repair on timeout (from 4.3)** | The error text says "did not finish in N s; rewrite without enumerating paths". |
| T-D hop caps `*..N` | Rejected: cuts correct long answers (k = 58 exists; ADR-0029 has no hop cap). |
| T-E route path needs to the agent | Kept only as the isolation variant (§4.4), because of W5. |

Chosen: T-B + T-C + T-F with **timeout 120 s, row cap 1,000**. The QT-0 bench may change both numbers before round 1.

### 4.3 (c) Syntax errors

| Option | Effect / risk |
|---|---|
| **S-A one repair round (chosen)** | On a syntax, timeout, memory or write-clause error: one more query-writing call with the failed query, the first 400 characters of the error and a fixed hint per error class. Covers E1–E4 with one mechanism. Cost: +$0.000384 per repaired question (mean writing call). The trace keeps both attempts. |
| S-B deterministic trim (drop a last line that `EXPLAIN` rejects) | Free and fixes E1. But it is a heuristic, it misses E2–E4, and it hides a model defect. Revisit if repair succeeds on < 80 % of E1 on T. |
| S-C higher effort for query writing (low → medium) | Effect on stray tokens unknown; costs more on every question. A round-2 knob only. |
| S-D resample without the error | Strictly weaker than S-A. |

### 4.4 (d) Cascade policy, accuracy first

| Option | Effect / risk |
|---|---|
| keep cascade_v3 at 120 s | Loses the 2 late answers (§2.1). |
| **cascade_v4 (chosen)**: tuned tiers; Cypher accept = answered ∧ not abstained ∧ rows ∧ **complete** (no row-cap cut); fallback as v3; no cutoff, 900 s hang guard | The complete rule would have escalated E-3301. Removing the cutoff restores 148/148 of the oracle on the dev set. |
| **cascade_v4_iso (candidate)**: v4, with need label `UPSTREAM_TO_FIRST_VALVE` / `DOWNSTREAM_TO_FIRST_VALVE` starting at the agent | Protects against W5 once timeouts are fixed (precedent: `cascade_v3_iso`, ADR-0048). Chosen by rule §7.4. |
| always agent | 0.840 on dev; loses the 11 Cypher-only answers. |
| verify by running both and arbitrating | Costs both tiers on every question; on dev the cascade already equals the oracle. Revisit only if the oracle gap on T exceeds 3 questions. |

Final-answer rules (new file `final_answer_v2t.txt`, V2T strategies only):
1. A list of "equipment items and valves" names only those; fittings and inline components are passed through.
2. The item the question starts from is not listed among the items it feeds or is fed by.
3. If the evidence says a named tag does not exist, answer not present.

Agent params (`params_agent_v2t.json`): observation 4,000 → **32,000** chars, items 50 → **400**, prompt budget
150,000 → **600,000** chars; max_steps 40, final_reserve 30 s and low step effort unchanged. Basis: longest dev
reference 326 tags; 8 references over 50 tags; 44 truncated questions. Worst case per question ≈ 600,000 / 3.93
chars per token (measured median, final calls) × $0.125/M (billed, EXP-0007 plan §8) ≈ $0.019. The mean is far
lower; see §7.5.

Cypher tier also gets: the v2 schema paragraph (loop heads are PCF or PIF, matched by `loop_tag` on `:PlantItem`;
measured_by reaches the sensor, the head is further along the signal chain; `unit_id` is a string; fittings and
`line_to`). It also gets a **free tag existence check**: the question's tag-like anchors (`anchors.py`) are looked
up, and "named tags found / not found" is prepended to the context. This uses the question text only.

## 5. The V2T system

### 5.1 Inputs, outputs, data model

- `graph/line_view.py`: `Kind = Literal["equipment","valve","instrument","actuator","connector","inline"]`;
  `LineEdge(BaseModel, frozen)`: `source: str`, `target: str`, `via_tags: tuple[str, ...]`, `n_fittings: int`.
- `qa/plant_api/model.py`: `RelationGroup` gains `"line"`; `ItemFilter.kind: Kind | None`; `ItemRecord.kind: Kind`.
  `"Valve"` is accepted as a label alias for `kind = "valve"`.
- `qa/cascade/models.py`: `AcceptRule.COMPLETE = "complete"`; `Signals.truncated: bool | None = None`.
- `qa/agent/models.py`: no new fields. V2T values come from a params file. The docstring "fixed by design" now
  cites ADR-0061 for V2T.
- Strategies `cypher_rag_lines` and `graph_agent_lines` (registry). Store profile `plant_lines`. Policies
  `cascade_v4.json`, `cascade_v4_iso.json`. Pins: the two Luna pins of F1, unchanged.

### 5.2 Fairness

The line view reads only the resolved drawings (`Resolution` / `ItemGraph`) and the schema's class sets. The AST
import ban on gold modules (`tests/test_qa_graph_view_imports.py`) extends to `graph/line_view.py`. The gold keeps
its own `next_path_items`. A free fidelity gate compares the two independent implementations (§6).

### 5.3 How v1 and F1 stay reproducible

Every change is additive: new names, new files, or new optional fields whose default reproduces F1. The proof is
behavioural, as ADR-0060 1B: at every round commit and at E7, cache-only replays of ST-AG-H100, E1-AG-H1/H30,
E1-CTXH-H1/H30 and E1-CYP-H1 must be byte-identical, with F1's eight prompt hashes. The full test suite must pass
with v1 goldens unchanged. The unchanged-path list of ADR-0060 no longer gates the headline, which now runs on V2T;
the replays keep v1 reproducible.

## 6. Measurement (each component reports its own accuracy)

| Component | Measure | Gate |
|---|---|---|
| line view | Per line item: system line successors equal gold `next_path_items` (by tag), on D100g2, T, V | P = R = 1.0 |
| plant API `"line"` | canonical programs (API-02) with `"line"`, all dev families | = gold on D100g2 |
| shape rules | QT-0 bench: runtime and rows of the 15 recorded timeouts and of the generic shapes at 30/120/300 s | each shape finishes at 120 s on D100g2 and X1000g2s213 |
| repair | share of E1–E4 fixed by the repair round, per class | reported |
| tiers and cascade | accuracy per family, paired vs the previous round; oracle gap (oracle − policy) | §7.3 |

## 7. Tuning protocol

### 7.1 Corpora and questions (dev and tuning seeds only)

- **T** = X100g2s211 (tuning); **V** = X100g2s212 and X1000g2s213 (held back, run once). Seeds 1–90 were used for
  generator plan tuning (ADR-0059) and 2, 3, 604, 615, 616 appear in records, so 211–213 are fresh. The hygiene
  check refuses 5000–5999.
- Questions: the dev recipe of `dev_check.sh` (R2-style draw, then `per_family --n 10 --seed 20261101`), the 18 dev
  families only. **Held-out families are never drawn** before R5; they measure whether tuning generalises.
- D100g2's 163 questions are **in-sample** (the classification used them). They are re-run once at the end,
  reported as "fixed in-sample", and never used to choose.
- Neo4j: a temporary database (`E7_NEO4J_DATABASE`), one corpus at a time, `--store-profile plant_lines`. The user's
  `neo4j` database is never the target.

### 7.2 Rounds

Round 0 is free: QT-0 bench, line-view fidelity, API-02, F1 replays. Round r (r ≤ 3) is paid: both V2T tiers on T
(a cached tier costs nothing when unchanged), then the cascade join and the tuning report. Between rounds, only
fixes for a class in §2 or a new class seen on T, each traced to a T question.

### 7.3 Stop rules (fixed now)

1. Stop after round 3.
2. Stop early when the last round fixed fewer than 3 T questions in the cascade (uncut).
3. A change that lowers any family by ≥ 2 T questions without a traced reason is reverted.
4. An F1 replay that is not byte-identical stops everything until fixed.
5. Health as ADR-0053: PROVIDER_ERROR + PARSE_FAILURE > 10 % stops a run.
6. A run at its cap stops; it resumes only on a higher cap approved by the user.

### 7.4 Choices fixed before T is seen

- `cascade_v4_iso` replaces v4 iff its uncut accuracy on T is ≥ v4's.
- Cypher effort stays low unless E1 repair success on T is < 80 %; then one round tests medium.

### 7.5 Paid runs and cost (estimate, from measured per-question costs)

V2T per question:
- **Cypher $0.00057–0.00086**: $0.000475 + repair share × $0.000384, with the share from 24 % (D100g2) to 100 %.
- **Agent $0.00087–0.0025**: low end = the F1 mean; high end = the 44 truncated questions at 4× their measured
  $0.002062, the rest at $0.000424. This ×4 is an assumption, matching the 4× larger caps.

| Stage | Runs | Estimate |
|---|---|---|
| Rounds 1–3 on T (≈ 163 q each) | ≤ 6 tier runs | $0.70–1.64 |
| V, V2T (2 × 163 q) | 4 | $0.47–1.10 |
| V, F1 tiers (paired baseline) | 4 | $0.44 (F1 means; +10 % margin for X1000 in the cap) |
| D100g2 in-sample re-run | 2 | $0.23–0.55 |
| **Total** | ≤ 16 + smokes | **$1.8–3.7** |

Caps: per run ceil₀.₀₅(1.3 × n × ĉ_high), ×1.1 on X1000: Cypher $0.20 / agent $0.55 per T run, V2T on V $1.60,
F1 on V $0.70, D100g2 re-run $0.75, 8 smokes × $0.02; sum **$5.46**. After
round 1 the measured V2T means replace the ranges.

### 7.6 Freeze at E7

E7 holds the V2T code, params, prompts, policies, this note, ADR-0061 and `E7.system = V2T` with the sha256 of every
V2T prompt, params, policy and pin file and the store profile id. At E7 the F1 replays (§5.3) and a cache-only
replay of the V runs must be byte-identical; the second proves that the frozen system is the validated one. R4 and
R5 caps are recomputed from V's measured V2T costs. No `src` change between R4 and R5 (ADR-0060 3B).

## 8. Coder tasks (Sonnet, one at a time, files ≤ 400 lines)

| Id | Task | Size |
|---|---|---|
| QT-0 | Shape bench: replay a query file against a temp database at given timeouts (extend `infra_cypher_replay_cli.py`); record time, rows, error | S |
| QT-1 | `graph/line_view.py` + tests against gold `next_path_items` on a small v2 plant; fidelity command | M |
| QT-2a | Plant API: `"line"` group, `kind` filter, `Valve` alias, kind in item lines, line-end markers (new render helper; `results.py` is at 324 lines) | L |
| QT-2b | `graph_agent_lines` + `agent_graph_system_v2t.txt` + `params_agent_v2t.json` | S |
| QT-3 | Store profile `plant_lines` (`line_to`, `:Valve`, `kind`), ingest flag, schema paragraph and invariants | L |
| QT-4 | `cypher_rag_lines`: `cypher_query_v2t.txt`, one repair round, tag existence check, `params_cypher_v2t.json` | M |
| QT-5 | `final_answer_v2t.txt` selected by strategy (new module; `final_answer.py` is at 356 lines) | S |
| QT-6 | `AcceptRule.COMPLETE`, `Signals.truncated`, `cascade_v4*.json`, report: uncut primary, acc@120 / @300 secondary | M |
| QT-7 | `data/runs/exp0007/tune.sh` (corpora, questions, caps, rounds, V, re-run), tuning report, 900 s guard, label V2T | M |
| QT-8 | Guards at each round commit: F1 replays, line-view fidelity, API-02 on v2 | S |

Order: QT-0, QT-1, QT-8 (free gates) → QT-2a/b, QT-3, QT-4, QT-5, QT-6 → QT-7.

## 9. Open questions (for the user, in Hungarian)

1. **Elfogadod a V2T-csomagot** (vonalnézet mindkét ágban, egy javító kör a Cypher-hibákra, 120 s-os lekérdezési
   idő, új záró szabályok, cascade_v4 határidő nélkül)? *Javaslat: igen.*
2. **Fő mérőszám a V2T-re a határidő nélküli pontosság** (900 s csak a lefagyás ellen), az acc@120 és a késleltetés
   csak riportolva? *Javaslat: igen, a konzulens iránymutatása szerint.*
3. **UPSTREAM_SOURCES**: marad a mostani definíció (forrás = amibe semmi nem folyik be, v2-n ez a vezeték eleji
   szelep)? *Javaslat: marad; v1-en is így volt, és a kérdés szövege így definiálja.*
4. **Szűrők és inline keverők**: maradjanak kívül az „equipment items and valves” listán (rendszerjavítással), vagy
   a pontozás hagyja figyelmen kívül őket útvonalválaszban? *Javaslat: maradjanak kívül, a rendszert javítjuk.*
5. **Kiinduló elem a DOWNSTREAM_IN_UNIT válaszban**: marad kizárva? *Javaslat: marad.*
6. **Validálás**: lefuttassuk az F1-et is a két V-üzemen (≈ $0.44), hogy legyen páros, tanuláson kívüli mérés a
   hangolás hatásáról? *Javaslat: igen.*
7. **Költségkeret**: becslés $1.8–3.7, a capek összege ≈ $5.5 a ≈ $30-ból. Rendben? *Javaslat: igen.*
8. **Izolációs útvonal**: a T-n eldöntendő, előre rögzített szabály szerint induljanak-e az első-szelep kérdések
   rögtön az ágensnél? *Javaslat: igen, a §7.4 szabállyal.*

## 10. Sources

Run records and reports listed in §1; `src/plantgraph/qa/questions/{common,families_flow,families_dev2_reach,
families_isolation,families_dev2_local}.py`, `qa/harness/gold.py`, `qa/scoring.py` (`score_path`),
`qa/schema_text.py`, `qa/strategies/cypher_rag.py`, `qa/agent/{models,loop}.py`, `qa/cascade/{models,policy}.py`,
`ingest/headline_v2.py`; ADR-0029, ADR-0036, ADR-0044, ADR-0048, ADR-0053, ADR-0057, ADR-0059, ADR-0060;
EXP-0007 plan §8 (billed prices).
