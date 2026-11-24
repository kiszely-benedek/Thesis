---
component: qa/v2tb — V2T-B, a documented revision of the frozen V2T-A2 that reads valve positions and names untagged valves; run beside V2T-A2 on the same v2.2 plants in EXP-0009 (freeze E10)
status: accepted design (ADR-0067 accepted 2026-11-23); T14 built (`dd60e6c`); rulings on its report in §10 (2026-11-24)
date: 2026-11-23
related: [ADR-0066, ADR-0067 (proposed), ADR-0053, ADR-0060, ADR-0061, ADR-0065, ADR-0021, ADR-0027, ADR-0028, ADR-0029,
          40-design/generator-v2-2-handbook-rules.md (§8, §10, §11, §12), 40-design/qa-tuning-v2.md,
          30-experiments/EXP-0008-v2-rerun.md, 30-experiments/EXP-0007-V2T-validation.md]
---

# Design — V2T-B: the system revision that sees valve positions and names untagged valves

## 0. Recommendation

The user chose **D1 = C** on 2026-11-23: both systems run on the same v2.2 plants. V2T-A2 stays frozen at E9 and
measures the data. **V2T-B** is a small, additive revision that measures what the new content is worth to a system
that can see it.

V2T-B changes four things and nothing else:
1. The store of a **B corpus** keeps the valve property `operating_position` (NO, NC, CSO, ...). An A corpus of the
   same plant does not.
2. The schema text, the primer and the agent's item properties mention that property, **only on B corpora**.
3. A new answer type, **VALVE_SET**, lets an answer name an untagged valve by a **descriptor**: its class, its line
   number and the tagged item it sits next to.
4. A scorer for VALVE_SET resolves each descriptor to plant nodes and compares node sets.

Every V2T-B file is new. No E9 system-side path changes, so V2T-A2 stays byte-identical (gate G0f). V2T-B gets its
own freeze, **E10**, a tuning budget of at most three rounds on one dev plant, and its own validation pair.

**How the comparison separates data from system:**

| Effect | Comparison | Paired? |
|---|---|---|
| Data (v2.2 against v2.1) | V2T-A2 on v2.2, scope R, against V2T-A2 on v2.1 (EXP-0008), per scale, common families | no (different plants) |
| System, no harm | V2T-B − V2T-A2 on scope R, same plants, same questions | yes |
| System, new content | V2T-B − V2T-A2 on scope X (position-aware and untagged-answer isolation), same plants, same questions | yes |
| Scale (thesis claim) | Q4 on V2T-A2 (scope R) and Q4-B on V2T-B (scope R ∪ X) | no (two scales) |

What this buys the thesis claim: Q4 is then tested twice on the same handbook-checked plants, once by a system that
cannot use the new content and once by one that can. If both hold, "the scale result does not depend on how much of
the drawing the system can read" becomes a measured statement.

## 1. What stays frozen, and what relaxes for the B arm

**Rule of the paired design.** Both arms run on the **same plants**. So nothing that changes the plant data can be
done for B alone. Every data-side deferral that exists because the frozen system cannot ingest it stays deferred.

| Constraint (where it came from) | V2T-A2 | V2T-B | Why |
|---|---|---|---|
| `operating_position` not in the store (design §10, option A) | kept | **relaxed**: stored and visible on B corpora | system-side, per corpus |
| Isolation candidates whose answer holds an untagged valve are refused (§11) | kept in scope R | **relaxed** in scope X: answered with descriptors | gold side plus B's answer type |
| Gold is topological only (§11) | kept | **relaxed** for the new family OPEN_VALVES_TO_ISOLATE (§4) | a new family with its own natural wording |
| Primer (ADR-0041) explains ISA only | kept | **extended** by one paragraph on positions and untagged valves | additive file |
| Fail action (FO/FC/FL) out of the store | kept | **kept** | no question uses it; a visible field nobody asks about cannot be measured |
| TOG73 untagged branch pipes (frozen `graph/line_view.py`) | deferred | **still deferred** | the plants are shared, and A2's frozen line view must ingest them |
| Functional-only gauge tags, parallel loop numbering (resolver, ADR-0027 key) | deferred | **still deferred** | store-side, shared by both arms |
| API "S" letters (primer) | deferred | **still deferred** | the data would contradict A2's frozen primer, so A2 would be harmed by construction |
| Demo (ADR-0064) | H1000g21p1 on V2T-A2 | **no demo** | one corpus in Neo4j; the demo is not an experiment arm |

**Answer to the user's question "could TOG73 become possible?"** Not under D1 = C. It would need a change to the
frozen line view, and V2T-A2 must ingest the same plants. TOG73 would only become possible if the A2 arm were dropped,
and then nothing would separate the data effect from the system effect. It stays deferred (generator design §4.9).

## 2. Store: one plant, two corpora

- **Corpus ids.** The plant `H1000g22p1` is ingested twice: `H1000g22p1` (A view, positions stripped, as T5 does
  today) and `H1000g22p1B` (B view, positions kept). The precedent is the identity arm's `H1000g21p1V`.
- **One generation.** Both views load the same DEXPI file and the same `GenerationRecordV22`; only the adapter's
  strip step differs.
- **One corpus in Neo4j at a time** (user rule). The launcher loads A, runs A2, wipes, loads B, runs B. EXP-0008
  measured the four Neo4j load stages at 27.1 s on a 1,000-sheet plant, so the reload is cheap.
- **Where the property sits.** On the valve node (the `PipingComponent`), as `operating_position` with one of
  `NO NC LO LC CSO CSC`. Valves with no position drawn have none, which reads "normally open" (TOG p.114).

**Alternatives considered:**
- *One store with the property, and A2's schema text hiding it.* Rejected. A2's agent tools read
  `VISIBLE_NODE_PROPERTIES`, and a Cypher query can name any property. A2 would then not be the E9 system.
- *Positions as separate `:Position` nodes.* Rejected. A property is the boring option, and it is how DEXPI carries
  it (a custom attribute on the component, §8 of the generator design).

## 3. System files (all new, under `src/plantgraph/qa/v2tb/`)

| File | What it does | Basis |
|---|---|---|
| `visible.py` | `VISIBLE_NODE_PROPERTIES_B = VISIBLE_NODE_PROPERTIES \| {"operating_position"}`; the B item-property keys for `plant_api` | `graph/schema.py` unchanged |
| `schema_text_b.py` | builds A's schema text, then adds the position paragraph **iff** the corpus's `LoadPlan` holds `operating_position` | `qa/schema_text.py` unchanged |
| `primer_b.py` | A's primer plus one paragraph: what NO/NC/CSO/LO/LC/CSC mean (TOG p.114), that a valve without a position is normally open, that in some areas manual valves carry no tag, and how to name such a valve | ADR-0041 primer unchanged |
| `final_answer_b.py` | the VALVE_SET answer rules (§5) | V2T final-answer rules (ADR-0061) unchanged for other types |
| `scoring_b.py` | the descriptor resolver and set comparison (§5) | `qa/scoring.py` unchanged |
| `policy_b.py` | the cascade policy `cascade_v4_iso_b`: the same tiers and escalation rule as `cascade_v4_iso`, with VALVE_SET treated as TAG_SET in the escalation rule | ADR-0061 5C |
| `pins_b.json`, `params_b.json` | the same Luna pins and parameters as E9 | E9 |

**Selection.** The harness picks the B files when the run config names system `v2t_b`. With system `v2t_a2` nothing
new is imported. A test asserts that importing `plantgraph.qa.v2tb` changes no E9 module object.

**Schema-text paragraph (draft, the tuning may reword it):**

> Valves may carry `operating_position`: NO normally open, NC normally closed, LO/LC locked open/closed, CSO/CSC
> car-sealed open/closed. A valve without the property is normally open. Manual valves in some areas carry no tag.
> Such a valve is named by its class, its `line_number` and the tagged item it sits next to (see the answer rules).

## 4. Question families and scopes

Two draws per plant. Both are gold-side changes, made under the ADR-0060 1B pattern. The v2.1 question sets stay
byte-identical (T0 hash).

**Scope R — replication** (the EXP-0008 recipe, 280 questions per plant). The §11 rules of the generator design hold:
candidates whose answer holds an untagged valve are refused. Both arms answer R.

**Scope X — extension** (new, 50 questions per plant for B, 40 for A2):

| Family | Question (template) | Answer type | Split | Asked of |
|---|---|---|---|---|
| OPEN_VALVES_TO_ISOLATE | "Which normally open valves must be closed to cut {tag} off from everything upstream?" | VALVE_SET | dev | both |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | "... from everything downstream?" | VALVE_SET | held-out (sealed) | both |
| UPSTREAM_ISOLATION_X | the registered UPSTREAM_ISOLATION text, drawn **without** the untagged refusal and not already in R | VALVE_SET | dev | both |
| DOWNSTREAM_ISOLATION_X | the registered DOWNSTREAM_ISOLATION text, drawn the same way | VALVE_SET | held-out (sealed) | both |
| POSITION_OF_VALVE | "What is the normal operating position of valve {tag}?" | POSITION (new enum) | dev | B only |

- **Gold of OPEN_VALVES_TO_ISOLATE.** The topological walk of UPSTREAM_ISOLATION (first operated valve on every
  route), minus the valves whose position is NC, LC or CSC: a route whose first valve is already closed needs no
  action. The wording says "normally open valves", so it is a new, natural question, not a rewording of the
  registered one (user rule: natural questions only).
- **Why the registered isolation families keep topological gold.** "Which valves must be closed" includes a valve
  that is already closed: an isolation list names it so it is locked and verified. Changing its gold would change
  the meaning of a registered family.
- **Why A2 is asked the X isolation families.** A2 cannot see positions or name untagged valves. Its score on X is
  the baseline that makes B − A2 on X the value of the new content, on the same questions. A2 receives each X question
  with answer type TAG_SET, through a gold-side adapter, because A2's frozen final-answer code knows no VALVE_SET. A2
  can still be right where the gold holds only tagged valves and no closed one.
- **Why A2 is not asked POSITION_OF_VALVE.** It cannot see the property, so its score is fixed by construction, and
  its frozen code knows no POSITION type.
- **Availability.** At least 10 candidates per family per plant (ADR-0029, as §11). Under the per-document tagging
  unit (generator design §5), a 100-sheet plant is one document. On an untagged 100-sheet plant, R's two isolation
  families have no candidate, so they are **pre-registered unavailable in scope R on v2.2**, at both scales. Their
  content moves to X, where both arms are asked.
- **Reported per X question:** whether the gold holds an untagged valve, and whether OPEN_VALVES gold differs from the
  topological gold (the "discriminating share").
- **Amended by §10 R9 (2026-11-24):** the two OPEN_VALVES templates in the table above are replaced by twins of the
  registered isolation texts; see §10.4.

## 5. VALVE_SET: naming an untagged valve

**Answer item:** either `{"tag": "GTV-1203"}` or
`{"class": "GateValve", "line_number": "6\"-P-1203-A1A", "next_to": "FV-1203", "side": "upstream"}`.
`side` says on which side of `next_to` the valve sits along the flow.

**Gold.** Each untagged valve in a gold answer gets a canonical descriptor: its class, its line number, the nearest
tagged item along `send_to` on the same line (downstream first, else upstream), and the side. A candidate is
**refused** if any untagged valve in its answer has no descriptor that resolves to exactly that one node. The
refused share is reported.

**Scoring (`scoring_b.py`).**
1. Each answered item is resolved to plant nodes.
   - A tag resolves as today.
   - A descriptor resolves to every node with that class and line number that has `next_to` as its nearest tagged
     neighbour on that side, across untagged fittings and valves only.
2. An item that resolves to zero or to two or more nodes is wrong.
3. The answer is right iff the set of resolved nodes equals the gold node set.

So any description that picks out exactly the right valve counts, not only the canonical string.

**Self-tests (free, before E10):**
- the gold descriptors score 1.0 against their own gold;
- a descriptor with the wrong side, line or class scores 0;
- the A2 adapter's TAG_SET answers score as the frozen scorer does on R.

**Audit.** The scorer audit (P1) samples B's VALVE_SET and POSITION rows as their own stratum, because the scorer is
new.

**Amended by §10 R1 (2026-11-24):** the walk to the nearest tagged item follows every `send_to` edge, whatever its line
number. The descriptor still holds the valve's own class and its own line number. "On the same line" above is
superseded.

**Alternatives considered:**
- *(class, line number) only.* Rejected: the two block valves of a control-valve station share both.
- *An exact canonical string.* Rejected: it would score phrasing rather than identification.
- *Expose the store's internal uid.* Rejected: it is bookkeeping that the schema text never mentions, and no engineer
  could say it.

## 6. Tuning, freeze E10 and re-validation

- **Tuning set:** the dev plant `D100g22` only, with B's dev families plus scope R's dev families.
- **Budget:** at most three rounds (ADR-0061 precedent). The basis is EXP-0007's measured V2T tuning, about $1.30
  for three rounds (`EXP-0007-V2T-validation.md`).
- **What tuning may touch:** only the B files of §3, and each round's change is logged in ADR-0067. The held-out X
  families are never generated on a dev plant.
- **Stopping rule:** stop when a round raises B's dev accuracy by less than 1 point, or after round 3.
- **Freeze E10** (one user commit):
  - the E9 system-side path list, unchanged (checked as in ADR-0060 1B);
  - the sha256 of every B file;
  - the PREREG A of EXP-0009.

  The replays must be byte-identical at E10: one cache-only replay per A2 tier, as E9 requires, plus one per B tier
  of the B validation runs.
- **Re-validation:** B on `VAL100g22` and `VAL1000g22`, the same pair as A2.
  - **G1-B:** no dev family below 50 % on both plants (EXP-0008's G1).
  - **G1-B2:** on the pair, B − A2 on scope R ≥ −0.05 (point estimate). Otherwise B is not run sealed, and the
    finding is reported.
  - The validation pair also measures B's $/q, from which the sealed caps are recomputed.

## 7. Claims (pre-registered in EXP-0009 PREREG A)

| Claim | Arm and scope | Pass |
|---|---|---|
| Q4 (primary) | A2, scope R, S1000 − S100 | interval contains 0 or lies above (ADR-0053) |
| Q4-B | B, scope R ∪ X | the same rule |
| SB1 no harm | B − A2, scope R, paired | descriptive: the difference and its interval, no pass margin (user, 2026-11-23) |
| SB2 content value | B − A2, scope X (isolation families), paired | the interval lies above 0 |
| K1–K3, Q5 | A2, scope R | as EXP-0008 |
| Descriptive | data effect per scale; X sub-scopes (untagged gold, discriminating share); POSITION_OF_VALVE accuracy; refused shares | — |

**The SB1 margin.** The proposed margin was −0.03, about the half-width of EXP-0008's Q4 interval (−0.005, [−0.035, +0.025]). The user dropped it on 2026-11-23: SB1 is reported descriptively, as the difference and its interval, with no verdict.

## 8. How each part reports its own accuracy

| Part | Measured against | Where |
|---|---|---|
| Descriptor gold | uniqueness: refused share per family and plant | gold report |
| Scorer B | self-tests; audit stratum | G0 gate; audit report |
| Store B | resolution gate G0g on the B corpus; G0-B: the positions file equals the plan's positions node for node, and the patched plan carries exactly that many (§10 R4) | ingest report |
| Descriptor readability | a canonical program over the B view reproduces every untagged gold valve's descriptor, 100 % (§10.6, T14c criterion 9) | T14c report |
| Arm B | Q4-B, SB1, SB2 | sealed report |

## 9. Open questions

1. **The SB1 margin** is decided: descriptive only, no margin (user, 2026-11-23).
2. **Valves with no tagged neighbour.** A root valve on a network sheet of an untagged document may have only
   connectors and tees around it, none of them tagged. Such a valve has no descriptor, so a candidate whose answer
   holds it is refused (§5). I propose no special rule. The coder reports the refused share on the dev plants before
   E10. If it exceeds a quarter of an X family's candidates, the case returns to the architect.
   **Resolved by §10.1 (2026-11-24):** it did exceed a quarter on the proxy (DOWN up to 77.8 %). R1 relaxes the walk.
   The measured proxy share is then at most 5.8 %.

## 10. Rulings on the T14 report, 2026-11-24

**Inputs.**
- T14 (`dd60e6c`), its report, and the coder's scratch measurements (`refused_share.py`, `why.py`, `variant.py`).
- My read-only reading:
  - `qa/v2tb/*`, `resolution/contract.py`, `store/neo4j_plan.py`, `store/plant_rows.py`;
  - `qa/graph_view.py`, `qa/neo4j_view.py`, `qa/harness/{runner,attempt,registry}.py`, `qa/strategies/base.py`;
  - `qa/need/rules.py`, `qa/questions/templates.py`, `qa/questions/templates_heldout.py`, `qa/exp0007/paths.py`;
  - `adapters/pydexpi_valve_attributes.py`, `benchmark/v2/generate.py`.
- One measurement of my own. The coder's `variant.py` walk ran on all five seeds (architect scratch `arch_relaxed.py`,
  about 10 s per seed). Its numbers are in §10.7. Seeds 1 and 2 reproduce the coder's figures.

**Five facts that decide the rulings.**
- **F1.** A line number changes where an engineer goes on naming: at a pump's discharge spec break (generator design
  §17.13 R4), at an instrument connection, at a header tie-in. The strict walk stops there. That is why 403 of the 516
  seed-1 valves had no tagged neighbour "on their own line".
- **F2.** G0f counts every file under `qa/harness/`, `qa/strategies/`, `qa/agent/`, `qa/plant_api/`, `qa/cascade/`,
  `qa/need/`, `qa/prompts/`, `llm/` and `store/` as system side, **new files included**: `paths.changed_since` lists
  untracked files too. No B file may be created in those directories.
- **F3.** `build_load_plan` and the `NetworkxGraphView` constructor both run `check_contract`. Neither accepts a sheet
  that carries `operating_position`.
- **F4.** The frozen final step and scorer are called from `strategies/base.answer_question` and
  `harness/attempt._scored_row`, with no seam for another answer type.
- **F5.** The frozen need classifier was written from the dev templates only (`need/rules.py`).
  - The registered **dev** text "To isolate {tag} from all upstream equipment, which valves must be closed?" gets
    UPSTREAM_TO_FIRST_VALVE, so it starts at tier 1.
  - The registered **held-out** text "To cut {tag} off from all downstream equipment, which valves must be closed?"
    matches `\ball downstream\b`. It gets DOWNSTREAM_ALL and starts at tier 0, as in EXP-0008.
  - The §4 draft of the dev family OPEN_VALVES_TO_ISOLATE ("cut {tag} off from everything upstream") borrowed the
    held-out wording, and matches no rule. That was my drafting slip.

### 10.1 Issue 1: the refused-descriptor share

**R1. Relax the walk; keep the descriptor.**
- **The rule.** The nearest tagged item is found along **every `send_to` edge**, with or without a line number. The walk
  still passes only through untagged nodes, and still stops at the first tagged node on each branch.
- **What does not change.** The descriptor keeps its four keys: the valve's own class, **one of its own line numbers**,
  `next_to` and `side`. Resolution and uniqueness are as in §5, and the gold and the scorer use the same walk.
- *Why, from the engineer's side.* An engineer names an untagged valve by the nearest thing on the drawing that has a
  tag, not by the nearest thing on the same line number:
  - "the root valve of PI-1203" is the needle valve on its line, just upstream of PI-1203;
  - "the discharge block of P-101" is the gate valve on the discharge line, just downstream of P-101, across the spec
    break.

  Under R1 both are ordinary descriptors. Under the strict walk neither exists (F1).
- *Why, from the LLM's side.* `next_to` is the first tagged node along the flow. Cypher finds it with a
  variable-length `send_to` path through untagged nodes; the agent finds it by walking neighbours. Both read only
  visible fields: tags, classes, and the `line_number` edge property.
- *Measured effect* (seed 1): valves with no descriptor fall from 516 to 113. All five seeds are in §10.7.
- *Within ADR-0067 2B.* The ADR fixes the four keys and resolution to nodes, not "same line". The ADR is not
  superseded. Its revisit trigger (more than a quarter refused) fired on the proxy, and R1 is the revisit.

*Who:* T14b.

**R2. No new descriptor forms.**
- *Role forms* ("on the bypass of CV-x", "the root valve of PI-y"):
  - each needs its own resolution rule, its own prompt sentence and its own audit stratum;
  - after R1, the root-valve form is already an ordinary descriptor (`next_to` = PI-y, side upstream);
  - a CV bypass valve already gets a unique descriptor from its class and its line, so the bypass form would add an
    accepted phrasing but no coverage.
- *An ordinal* ("the second gate valve upstream of X") would name the remaining same-class valves in series.
  - It adds a fifth key and an ordering rule that is ill-defined on branching walks, and one more sentence that the
    tuning must test.
  - It would remove at most the residual of §10.7: 1.2–3.3 % of candidates up and 1.6–5.8 % down.
  - The novelty budget is not spent here.

*Who:* nobody. Revisit only on ADR-0067's existing trigger.

**R3. Accept the residual refusals, and report them by role.**
- A candidate stays refused when an untagged valve in its gold has no unique descriptor.
- T15 reports, per family and plant:
  - the refused count and share;
  - the role counts of the refusing valves.

  On the proxy these roles are mostly pump discharge blocks (DOWN) and make-up gas, battery-limit and tank-fill blocks
  (UP), so the selection stays visible.
- ADR-0067's stop rule holds. If more than a quarter of any X family's candidates are refused on a dev plant (T15) or a
  sealed plant (G0l, T13), the case returns to the architect.

*Who:* T15 (report), T13 (G0l).

### 10.2 Issue 2: how `operating_position` reaches a B corpus, and how B is wired into the harness

**R4. The source of a position is the DEXPI file, read once per B plant at ingest.**
- `qa/v2tb/positions.py: read_operating_positions(model) -> dict[str, str]` reads the `OperatingPosition` custom
  attribute of each `PipingComponent`. It is the inverse of `annotate_valves`. In the synthetic world it plays the
  digitizer that reads the position text printed beside the valve.
- **Why DEXPI and not the plan.** The thesis pipeline is DEXPI to graph. Reading the plan (`positions_of`) would check
  the plan against itself.
  - The gold side reads `positions_of(plan.unit_plans)` (T15: OPEN_VALVES and POSITION_OF_VALVE gold).
  - The store reads DEXPI.
  - Two independent paths must agree; that is G0-B below.
- **When.** At ingest, the B corpus's own generation is run once more to obtain the model (`generate_plant_v2`). Its
  positions are written to `<corpora>/<id>B/operating_positions.json` (sorted keys), and the file's sha256 goes into
  the B corpus record.
  - The run-time loader reads the file; it never generates a second time.
  - The basis for the cost is one v2.1 1,000-sheet generation, measured at 404.8 s (`H1000g21p1/ingest.json`). The
    v2.2 time is unmeasured, so T14c measures it.
- **G0-B (ingest gate)** has three checks:
  - the file equals `positions_of(plan.unit_plans)` node for node;
  - the number of node rows carrying the property in the patched plan equals the file's count;
  - every keyed node is a valve.

  This is §8's "count equals the DEXPI count", made per node.

**R5. Inject after the contract, into two places, from one map.**
- **Map.** `store_b.positions_by_local_key(positions, occurrence_map)`. Every valve has exactly one occurrence, because
  ADR-0028 duplicates only equipment, so the map is one-to-one. It raises otherwise.
  - The map reads the occurrence map, which is gold. That is the digitizer's role.
  - No strategy-facing module imports it (T14c criterion 8).
- **The plan.** `store_b.with_positions(plan, by_local_key) -> LoadPlan` returns a **new** plan. Each positioned valve's
  row gets the code: the row whose uid is `uid(corpus, key)` (occurrence layer) or `item_uid(corpus, key)` (plant
  layer).
  - This works for every profile.
  - The expected label and type counts are unchanged, so the frozen loader and `check_store` accept the plan as it is.
  - An empty map returns an equal plan.
- **The in-memory view.** `views_b.NetworkxGraphViewB(NetworkxGraphView)` runs the frozen constructor, contract
  included. It then sets the attribute on the occurrence nodes by local key, so `items()`, `find_by_tag()` and
  `subgraph()` agree. An empty map gives the frozen view.
- **The Neo4j view.** `views_b.Neo4jGraphViewB(Neo4jGraphView)` replaces only the schema text, with
  `build_schema_text_b(plan)`.
- *Rejected:*
  - changing `check_contract`, `localize` or the graph adapter: they are frozen, and A2's guarantee depends on them;
  - a wrapper view that patches only `items()`: the other methods would disagree;
  - a RunConfig field: below.

**R6. The B harness: new files under `qa/v2tb/`, chosen by entry point.**

| File | What it does | How it reuses the frozen code |
|---|---|---|
| `answer_b.py` | `run_final_step_b`, `answer_question_b` | the frozen fit check, B render and B parse (`final_answer_b.py`), A's V2T template through `template_path_for(<A name>)` |
| `strategies_b.py` | `cypher_rag_lines_b` (B schema text, B primer in the query prompt) and `graph_agent_lines_b` (`build_item_graph_b(view, line_view=True)`, B primer in the system prompt, `ITEM_PROPERTY_KEYS_B`) | subclasses of `CypherRagLines` and `GraphAgentLines`. Where a frozen class has no seam smaller than one method, that one method is copied, and its docstring names the original |
| `registry_b.py` | B strategy names to constructors | |
| `runner_b.py`, `__main__.py` | `python -m plantgraph.qa.v2tb run --config …` | imports every frozen helper it can. It copies only the functions that call a B-different function: corpus load, strategy build, answer, score. Each copy names its original |

- **The runner's rules.**
  - It accepts only corpus ids that end in `B` and only `*_b` strategy names.
  - It scores with `score_answer_b`, over one `PlantIndex` built from the gold plant per corpus.
- **Selection by entry point, not by a RunConfig field.** A new field would enter every A run's dumped config, and
  could break E10's byte-identical A replays. B runs are told apart by their corpus ids (`…B`) and strategy names
  (`*_b`).
- **The cascade.** The frozen offline cascade evaluation is given `policy_b()` as an object. No JSON file goes into
  `cascade/policies_v2t/`, because that directory is system side (F2).

**R7. Who does what.**
- **T14c** builds R4–R6. It is new; see §10.6.
  - All of it is B system code. Tuning may touch it, and E10 hashes it, so it belongs with the B files and their
    import-isolation test, not in the launcher.
  - It comes after T15, so its expressiveness check can run on real X questions.
- **T13** only orchestrates:
  - per plant: load A, run A2, wipe, load B with the patched plan, run B;
  - `write_positions_file` in the two-view ingest, and G0-B in the plant gates;
  - the file's sha256 in the B corpus record and in PREREG A;
  - the B tier runs through the B entry point;
  - the S3 relabel of R and X questions.

  T13 writes no B system code.

### 10.3 Issue 3: descriptors in the frozen types

**R8. Confirmed: a descriptor travels as its sorted-key JSON string (`encode_descriptor`).**
- *Rejected:*
  - widening `AnswerValue` in `qa/models.py`: frozen code reads list items as strings, and a dict item reaching it
    would fail where no test looks;
  - a B subclass of `FinalAnswer` inside frozen row types: the row types would serialize it unpredictably.
- **How T15 writes an X reference.** A `list[str]`, sorted, with one item per gold valve:
  - a tagged valve is its tag as printed;
  - an untagged valve is `encode_descriptor(canonical_descriptor(index, node))`.
- **Self-test.** `reference_nodes` maps each reference to exactly its gold node set (§5).
- **The A2 adapter's copy.** Its reference is the same list, with answer type TAG_SET.
- **An OPEN_VALVES candidate whose gold is empty** (every first valve is already closed) is refused, and counted.
  - The answer protocol cannot tell "none to close" (`[]`) from an abstention (`not_present`), so such a row would
    measure the protocol, not the content.
  - Its count is reported beside the discriminating share.

*Who:* T15.

### 10.4 Issue 4: routing of the X question texts

**R9. Word each new family as the twin of its registered family, in the same split's register.**

| Family | Split | Text | Label (frozen rules) | Start tier, both arms |
|---|---|---|---|---|
| OPEN_VALVES_TO_ISOLATE | dev | "To isolate {tag} from all upstream equipment, which normally open valves must be closed?" | UPSTREAM_TO_FIRST_VALVE | 1 |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | held-out | "To cut {tag} off from all downstream equipment, which normally open valves must be closed?" | DOWNSTREAM_ALL | 0 |
| UPSTREAM_ISOLATION_X | dev | registered, unchanged | UPSTREAM_TO_FIRST_VALVE | 1 |
| DOWNSTREAM_ISOLATION_X | held-out | registered, unchanged | DOWNSTREAM_ALL | 0 |

- **Each twin differs from its registered text by two words, "normally open".**
  - Within a split, OPEN against ISOLATION_X then differs only in the position effect.
  - Routing is equal by construction in both arms, because `policy_b` copies A's start tiers.
- **Why this is not a mechanical rewording.**
  - The user's rule is natural questions only, never reworded to dodge a failure.
  - No X question has been generated or answered. This corrects a design draft, not a registered question.
  - "Isolate" is the engineer's word for exactly this operation.
  - The dev register is by construction the wording the dev rules were written from (F5).
  - The held-out twin keeps the held-out register and takes whatever the frozen rules give it, as its registered
    family did in EXP-0008.
- *Rejected:*
  - **A B-only need classifier** (a new B file). B would route X differently from A2, so SB2 would mix routing with
    content. That would be a fifth change outside §0's four.
  - **Keeping the draft wording.** Both arms would start the dev family at tier 0 only because of the wording, against
    its registered twin's tier 1. That measures the classifier's vocabulary.
- **Test (T15).** `classify_need` of each new template equals that of its registered twin, on the same tag.

*Who:* T15.

### 10.5 Confirmations

- **R10a. A tag item must resolve to exactly one node. Confirmed.** Gold tags are unique in the unsplit plant: ADR-0028
  duplicates only across sheets, and the deferred functional-only gauge tags are not drawn. A gold tag that resolves to
  two nodes is a gold bug, and `reference_nodes` raises on it.
- **R10b. Spelling is folded, and an extra key is ignored. Confirmed, with two additions (T14b):**
  - **Fold guard.** Building a `PlantIndex` raises if two printed line numbers of the plant fold to one key. Otherwise
    `line_as_written` would pick one silently, and a descriptor could be ambiguous without the scorer knowing.
  - **A tag wins.** An object item with a non-empty string `tag` is that tag, whatever other keys it holds. The scorer
    judges identification. A tagged valve named by its tag plus context is identified.
- **R10c. The canonical line number is the one printed on the valve's `send_to` edges. Confirmed.**
  - A valve where the line number changes has two. It is indexed under both, the scorer accepts either, and the
    canonical one is the first in folded order that gives a unique descriptor.
  - A valve whose `send_to` edges carry no line number has no descriptor. It is counted separately: 0 on the seed-1
    proxy, measured.
- **R10d. POSITION accepts plain words as well as the codes. Confirmed.** "Open" alone is still refused, because it does
  not tell NO from LO or CSO.

### 10.6 T14b and T14c

**T14b (S, before T15). The descriptor walk and its wording.** Every §13 task rule applies: green suite, goldens
unchanged, no Neo4j, no paid call, one commit proposal.
1. **Walk (R1).**
   - `PlantIndex` walks every `send_to` edge, with or without a line number.
   - `nearest_tagged(node_id, *, forward)` loses its line parameter, and its cache key loses it too.
   - The descriptor keeps the valve's own class and one of its own line numbers.
2. **Fold guard (R10b).** Two printed line numbers that fold to one key raise `ValueError` (test).
3. **Tag wins (R10b).** `_read_item` returns the tag for any object with a non-empty string `tag` (test).
4. **Wording.** Three texts say "the nearest tagged item along the flow (the line number may change on the way)":
   - the VALVE_SET format sentence (`final_answer_b.py`);
   - the schema paragraph (`schema_text_b.py`);
   - the primer paragraph (`primer_b.py`).

   They stay drafts, and the tuning may reword them.
5. **Toy-plant tests.**
   - A spec break between a pump and its discharge block: the block gets `next_to` = the pump, side downstream.
   - An instrument root valve gets `next_to` = the gauge, side upstream.
   - A control-valve bypass globe valve gets a unique descriptor.
   - Two same-class valves in series between the same tagged items stay refused.
   - The §5 self-tests still pass.
6. **Measurement.**
   - Re-run the proxy on the forced-untagged 100-sheet seeds 1–5. The counts must equal §10.7 exactly; if they do not,
     report why.
   - Then run seed 7 at 1,000 sheets (drawn tagging), with the same columns and the machine time.
   - Descriptive only: on seed 1, the number of hops from each untagged valve to its canonical `next_to` (median,
     max).
7. **Gates.** G0f is `[]`, and the import-isolation test is green.

**T14c (M, after T15, before T13). The B ingest step and the B harness (R4–R6).** The same task rules apply.
1. **Files.** `positions.py`, `store_b.py`, `views_b.py`, `answer_b.py`, `strategies_b.py`, `registry_b.py`,
   `runner_b.py` and `__main__.py`, all under `src/plantgraph/qa/v2tb/` and none in a system-side directory (F2).
2. **Positions (R4).**
   - `read_operating_positions` round-trips `annotate_valves` on the small real v2.2 plant (`tests/v2tb/plants_b.py`),
     and equals `positions_of(plan.unit_plans)`.
   - `write_positions_file` writes the sorted-key JSON and returns its sha256.
   - The G0-B check function passes on forced-untagged seed 1, and fails on one deleted or altered entry (tests).
3. **Plan patch (R5).**
   - For the occurrence, plant and plant_lines profiles, every positioned valve's row or rows carry the code.
   - The expected counts are unchanged.
   - An empty map gives an equal plan (`model_dump` equal).
   - A key with no row raises.
4. **Views (R5).**
   - `NetworkxGraphViewB` with an empty map equals the frozen view on `items()`, `edges()` and `subgraph()`.
   - With the map, exactly the positioned valves gain the property.
   - `Neo4jGraphViewB.schema_text()` equals `build_schema_text_b(plan)`, with no database.
5. **Strategies (R6).**
   - Both B strategies use the B primer and the B final step.
   - A test shows a B agent tool output for a positioned valve containing `operating_position`.
   - If a frozen plant-API tool filters the property out and no subclass seam exists, stop and report.
6. **Runner equivalence.** On an A corpus with the primer off, a scripted fake sender and TAG_SET questions, the B
   runner's rows equal the frozen runner's rows byte for byte, apart from the strategy name.
7. **Cascade.** On fake tier rows, the frozen offline evaluation with `policy_b()` gives the same decisions as with
   `cascade_v4_iso`.
8. **Gold isolation.** An AST test shows that `strategies_b`, `views_b`, `answer_b` and `registry_b` import neither
   `qa.corpus` nor anything under `benchmark/`.
9. **Expressiveness (design for measurement).**
   - On forced-untagged seed 1, with T15's dev X questions, a canonical program over `NetworkxGraphViewB` reproduces the
     canonical descriptor of every untagged gold valve. It may read only visible properties and must cross
     `continues_as` pairs.
   - The bar is 100 %. Any miss means the gold names something B cannot read, so T14c stops and reports the misses by
     role.
10. **Cost.** Report the machine time of `write_positions_file` at 100 and at 1,000 sheets (seed 7). T13 adds it to
    generator design §12.3.

### 10.7 Refused shares after the rulings

**Measured** (architect, 2026-11-24, `arch_relaxed.py`): the R1 walk, on forced-untagged 100-sheet dev plants. It is
still the proxy, the isolation walks drawn without the untagged refusal, because T15's X families are not built.

| Seed | Untagged operated valves with no descriptor | UP isolation refused | DOWN isolation refused |
|---|---|---|---|
| 1 | 113 / 1,494 = 7.6 % | 9 / 273 = 3.3 % | 8 / 137 = 5.8 % |
| 2 | 131 / 1,545 = 8.5 % | 8 / 277 = 2.9 % | 5 / 123 = 4.1 % |
| 3 | 96 / 1,386 = 6.9 % | 7 / 261 = 2.7 % | 2 / 126 = 1.6 % |
| 4 | 109 / 1,458 = 7.5 % | 4 / 269 = 1.5 % | 3 / 126 = 2.4 % |
| 5 | 74 / 1,402 = 5.3 % | 3 / 254 = 1.2 % | 4 / 126 = 3.2 % |

- **The valves still without a descriptor.** Seed 1, the ten largest (role, class) groups, which hold 101 of the 113:
  - tank inlet blocks 27 (gate 21, plug 6);
  - receipt-manifold valves 24 (gate 18, plug 6);
  - steam-supply PI roots 14 (ball 8, needle 6);
  - battery-limit gate blocks 13;
  - CV outlet gate blocks 9;
  - network root gate blocks 8;
  - discharge gate blocks 6.
- **The valves that cause refusals.** Seed 1, each valve counted once per refused candidate:
  - DOWN: discharge blocks 6, compressor discharge blocks 2;
  - UP: battery-limit blocks 5, make-up gas blocks 4.

**Derived, not measured:**
- **OPEN_VALVES families.** On the same candidate pool, refusals are at most those of the ISOLATION_X family in the same
  direction, because their gold is a subset. The empty-gold refusals of R8 come on top, and they are unmeasured.
- **POSITION_OF_VALVE.** No descriptor refusals by construction: it is anchored on a tagged valve and answered with a
  code.
- **A tagged 100-sheet plant** (one of the five sealed plants per scale). No descriptor refusals by construction: every
  manual valve prints its tag.

**Estimated:**
- **1,000-sheet plants.** I expect shares like the 100-sheet ones, because the walk is local and the trains repeat the
  same valve roles. This is an estimate. T14b measures seed 7 at 1,000 sheets, and T15 measures the real X families on
  the dev plants.
