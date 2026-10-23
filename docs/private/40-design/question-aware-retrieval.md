---
component: question-aware context selection (fifth Hierarchical variant), a graph-tool agent over generic primitives, their combination, new question families with a sealed held-out set, and per-question cost/latency accounting (EXP-0006)
status: draft — awaiting review
related: [ADR-0033, ADR-0034, ADR-0035 (all proposed); ADR-0013, ADR-0014, ADR-0021, ADR-0022, ADR-0028, ADR-0029, ADR-0030, ADR-0032; qa-system.md §7, §8, §11, §17, §18 T20, §19 D4; hierarchical-and-jev.md §3, §5, §6; heldout-families.sealed.md (sealed)]
date: 2026-10-02
author: architect (Opus 5.5)
---

# Design — retrieval by information need, a graph-tool agent, and how they generalise

## 0. Recommendation

| # | Item | Decision | ADR |
|---|---|---|---|
| R1 | One vocabulary for "what to fetch" | A **plant API** of six generic, composable primitives over the resolver's plant graph: `find`, `neighbours`, `traverse`, `path`, `filter`, `aggregate`. New question types are compositions, never new tools | 0034 |
| R2 | Question-aware Hierarchical (fifth variant) | A closed set of 11 **need labels** (subgraph shapes, derived from schema relations × direction, not from question families); a classifier maps the question text to one label; a fixed primitive program fetches that subgraph across sheets; anchor sheets always stay whole; `GENERIC` or low confidence → today's Hierarchical | 0033 |
| R3 | Need classifiers, all built | rules (free) · label-probability chat LLM (paid, cheap) · Jev `choice` (paid, cheap) · oracle label (analysis only, harness side) | 0033 |
| R4 | Graph-tool agent | the LLM composes primitives in a bounded loop (6 steps, 4,000-character observations, result handles); plain JSON actions, not native tool calling; observations go to the **shared final step** | 0034 |
| R5 | Fair control for the agent | `cypher_agent`: the same loop with one tool, `cypher(query)`. Then typed-vs-free-form and single-vs-iterative are separable | 0034 |
| R6 | Combination | `hier_agent`: the agent starts from a compact need-aware map and fetches the rest with primitives. Plus a **cascade** computed offline from the two runs (no extra calls) | 0034 |
| R7 | Many question types | 12 existing families (dev-old) + 6 new **visible** families (dev-new, the user's examples) + 6 **sealed held-out** families and 10 held-out wordings, opened only after a hash-recorded freeze | 0035 |
| R8 | Cost and speed | fix the harness so a question's cost and latency include **every** call (today only the final call counts, §2 F1); local compute time in a side file; a cost–accuracy frontier and a cost-elasticity figure per arm | 0035 |
| R9 | Budget rule | **free metrics choose, paid runs confirm** (as ADR-0030): every variant is built and measured free where it can be; paid runs go to the free-metric winner and the named contrasts | 0033–0035 |

Coder tasks: 10, one Sonnet coder at a time (§15). Paid steps: 3, each **run by the user, paid, logged**.

**The one idea behind all of it.** Question *types* are open-ended; the *shapes of evidence* a topology question can
need are few: one item, its neighbours, a chain, a path, a closure up or down (with or without a stop), a unit. Part 1
picks the shape with a classifier and fetches it with a fixed program. Part 2 lets an LLM compose the same primitives
freely. CypherRAG lets an LLM write any query. The arms differ in **who composes** the retrieval, over **one**
vocabulary, so the measurement compares planners, not APIs.

| Who composes the retrieval | Single shot | Iterative |
|---|---|---|
| fixed rules / a classifier over need labels | `hierarchical_need_*` (Part 1) | — |
| an LLM, typed primitives | — | `graph_agent` (Part 2); `hier_agent` (Part 3) |
| an LLM, free-form Cypher | `cypher_rag` (built) | `cypher_agent` (control) |

## 1. Which part of the claim each piece serves

- **The claim** (`00-index.md`): the retrieval optimum is a function of corpus scale. The user's vision adds a second
  axis: question type. This note measures **strategy × scale × question family**, with held-out families as the test
  of whether a strategy is a system or a fit to the benchmark.
- **C4** (`qa-system.md` §13.3, the hierarchy survives past the wall): a hierarchy that cuts the wrong subgraph for a
  question type loses for a reason unrelated to scale. Need-aware selection removes that confound for known types.
  The confound is already measured: at H100, the generic Hierarchical covers only 0.760 of `UPSTREAM_ISOLATION`'s
  evidence nodes under every route, budget and limit it has (ROUTE-01 H100 part; §2 F4).
- **The cost frontier** turns "fast, efficient, low cost" into numbers per corpus size: whole-graph prompting grows
  with the plant (PROMPT-04: 1,649,451 → 16,746,349 characters from H100 to H1000); a bounded agent should not.
- **Novelty budget:** retrieval at scale is the contribution, so this is in budget. The plant API, the loop and the
  classifiers are deliberately boring (standard graph operations, a JSON loop, existing classifiers).

## 2. What the built code says (read 2026-10-02)

| # | Finding | Where | Consequence |
|---|---|---|---|
| F1 | **A question's cost, tokens and latency are the final call's only.** CypherRAG's query call (`trace["cypher_call"]`) and Hierarchical's router call (`router_call`) are in the trace but never summed. `qa-system.md` §11 specifies "summed over all calls for the question" | `harness/runner.py` `_attempt` (fields from `step.response`) | an agent's cost would be almost entirely invisible. QAR-T1 fixes it; it also corrects the headline's CypherRAG cost column |
| F2 | Retrieval-side calls are logged **without a question id** | `runner.py` `_sender_factory` comment | `calls.jsonl` cannot be joined per question. QAR-T1 fixes it in the harness (the strategy still never sees the id) |
| F3 | The final step words the answer format from the **gold** `answer_type` | `strategies/base.py` `answer_question`; `final_answer.py` | shared by every strategy, so fair; but a held-out family must not need a new `AnswerType`. `BOOLEAN` is therefore added with the **visible** dev-new families (QAR-T3), before the freeze |
| F4 | With one tag anchor Hierarchical sends the anchor sheets plus `sheet_hops` rings; `UPSTREAM_ISOLATION` reach depends on rings. **Measured (ROUTE-01 H100 part):** on 76 `UPSTREAM_ISOLATION` questions, strict routing hit 0.421 and evidence-node recall 0.760, **identical for all four route × budget combinations and all three budgets** (100k/200k/400k characters), at `sheet_hops` 1 | `sheet_selection.py`; ADR-0030 Consequences; `_results.md` ROUTE-01 (H100 part) | the loss is the anchor-based selection itself, not compression: no budget or route setting recovers it. This is the user's isolation example, measured. Need label `UPSTREAM_TO_FIRST_VALVE` follows the flow instead of a radius; NEED-01 tests it free (§11, gate N1) |
| F4b | Same run, all families at 100k: node recall 0.90 (`sheet_graph`) / 0.95 (`flow_path`); FLOW_PATH (148 questions) relaxed hit and node recall 1.000 under `flow_path` at every budget; `drop_rings` over budget on 45–49 % of FLOW_PATH at 100k, `through_line` on 0 %; **5.1 % of questions fail retrieval for want of an anchor** (no router in the free report) | `_results.md` ROUTE-01 (H100 part) | for `PATH` questions the generic Hierarchical (flow route + through-line) already covers the evidence; Part 1's gain must come from the other shapes. No-anchor questions go to the router fallback in every Part 1 variant (§4.3 rule 3), so Part 1 cannot change that 5.1 % |
| F5 | In the 2026-10-02 listing snapshot, `openai/gpt-5-mini` does **not** list `logprobs` among `supported_parameters`; `z-ai/glm-5.3-flash` and `deepseek/deepseek-v4-flash` do | `30-experiments/openrouter-models-2026-10-02.json` | the label-probability classifier cannot run on gpt-5-mini; it needs a separate small pin (§10.4, user decision U3) |
| F6 | J-T1 (System One client, `top_logprobs` on the chat path) is not built yet | `src/plantgraph/llm/` | QAR-T8 (paid classifiers) waits for J-T1; rules and oracle variants do not |

## 3. The plant API — `qa/plant_api/` (shared by Parts 1–3)

### 3.1 The item graph (what the primitives walk)

`ItemGraph` is the plant-level view of the **resolver's** occurrence graph (never the gold plant, never the manifest):

- **Identity contraction:** occurrences joined by `same_tagged_item_as` become one item; its id is the home occurrence's
  local key; it keeps every occurrence key and every sheet it is drawn on.
- **Stub contraction:** `X -send_to-> out-stub -continues_as-> in-stub -send_to-> Y` becomes one edge `X -send_to-> Y`
  with `via = (out_stub_key, in_stub_key)`; signal stubs likewise for `send_signal_to`. An **unpaired** stub stays as a
  pseudo-item of class "unresolved off-page connector": a walk that reaches it reports "line continues off-page,
  partner unknown" (none exist where G1 holds, SMOKE-04b).
- Built once per corpus from `GraphView.items()` and `edges()`; `functools.cached_property` on the strategy, as
  `RoutingGraphs` does.

```python
class ItemRecord(BaseModel):            # frozen; qa/plant_api/model.py
    item_id: str                        # home local key; opaque, never printed to a model
    tag: str | None                     # tag, else piping_component_name
    node_class: str
    labels: tuple[str, ...]             # schema.labels_for chain, e.g. ("BallValve", "OperatedValve", "PipingComponent")
    unit_id: str | None
    sheets: tuple[str, ...]             # every sheet it is drawn on, sorted
    occurrence_keys: tuple[str, ...]    # for serialization and evidence-node recall

class ItemEdge(BaseModel):              # frozen
    source: str; target: str            # item ids
    relation: Literal["send_to", "send_signal_to", "control", "measured_by"]
    via: tuple[str, ...] = ()           # stub keys when the edge crosses a sheet boundary
```

### 3.2 The filter (the only predicate language)

```python
class ItemFilter(BaseModel):            # all fields optional, AND-ed; frozen
    label: str | None = None            # any label in the class chain: "Pump", "OperatedValve", "Equipment", …
    node_class: str | None = None       # exact class name
    unit: str | None = None
    not_unit: str | None = None
    sheet: str | None = None
    tag: str | None = None              # normalized as find_by_tag does
```

Labels are the same names CypherRAG's schema text lists (`schema_text.py`), so both arms see one vocabulary.

### 3.3 The six primitives

Relation groups: `flow` = {`send_to`}; `signal` = {`send_signal_to`, `control`, `measured_by`}; `any` = both.
"downstream" follows edge direction, "upstream" reverses it, "both" ignores it.

| Primitive | Signature | Returns | Graph operation |
|---|---|---|---|
| `find` | `find(where: ItemFilter, limit: int = 50)` | `ItemSet` (sorted by tag; total count even when truncated) | selection |
| `neighbours` | `neighbours(of: ItemRef \| Handle, direction, relations, where: ItemFilter \| None = None)` | `Subgraph` (items + the edges used) | one-hop expansion of an item or a set |
| `traverse` | `traverse(start: ItemRef \| Handle, direction, relations, stop_at: ItemFilter \| None = None, walk_only: ItemFilter \| None = None, max_hops: int \| None = None)` | `Subgraph` with hop distance per item; stop items marked; nothing beyond a stop item is entered | transitive closure with a stop predicate and a restriction |
| `path` | `path(source: ItemRef, target: ItemRef, relations = "flow", directed: bool = True)` | `PathResult`: ordered items, hop count, sheets in order, or "no path" | shortest path (ties by tag sequence, as `FLOW_PATH`) |
| `filter` | `filter(items: Handle, where: ItemFilter)` | `ItemSet` | restriction |
| `aggregate` | `aggregate(items: Handle, group_by: Literal["node_class", "unit", "sheet"])` | `Table`: group → count, tags (truncated) | grouping and counting |

- `ItemRef` = a tag string; resolved with `find_by_tag` (so `SV 104.01` and `66KL21` work as in `anchors.py`).
- `Handle` = `"$r<n>"`, a previous result's item set. Handles are what make the primitives composable.
- **Completeness argument (why six, written before any new family):** the schema has items with
  {tag, class-label chain, unit, sheet} and four directed topology relations. The six are the standard graph-query
  operations over exactly that: select, expand, close (with stop and restriction), shortest path, restrict, group.
  Anything they cannot express needs either data (out of scope, ADR-0021) or an operation outside this algebra (for
  example "a path avoiding X"); such questions are a measured boundary, not a reason to add a tool.
- Deterministic: every result is sorted; ties broken by tag, then item id.
- Every result exposes `touched_keys` (occurrence keys of every item and every `via` stub it contains) for the trace.
- **Rendering** (`render(max_chars, max_items)`): one line per item `TAG (Class, unit U, sheets S1,S2)`, one line per
  edge `A -send_to-> B [crosses S3→S4]`, a header with the total count and "(N more not shown; narrow with filter or
  aggregate)" when truncated. Never an item id.

### 3.4 How the plant API reports its own accuracy (free)

- **API-01 fidelity:** on every corpus, the `ItemGraph`'s edges by tag equal the gold plant's `send_to` and signal
  edges by tag (precision and recall). Expected 1.0 wherever G1 holds; anything else is a resolver or contraction bug.
- **API-02 expressiveness:** for every **dev** family, a hand-written *canonical program* (a fixed sequence of
  primitive calls, in `tests/` and in `qa/harness/canonical_programs.py`, gold side) computes the answer with no model.
  Its accuracy against the reference functions on the dev question sets is the API's coverage; it should be 1.0 on
  dev families. After the unseal (§9), canonical programs for held-out families are written **as analysis**, and the
  share of held-out families that admit one is reported. This is also a free "perfect planner" upper bound for the
  agent.

## 4. Part 1 — `NeedAwareHierarchical` (the fifth Hierarchical variant)

### 4.1 Need labels (closed, frozen before any held-out family is opened)

Rule that fixes the set: one label per evidence **shape** the schema allows, each directional shape in both
directions, plus `GENERIC`. The only stop predicate built in is "first operated valve", the canonical isolation
boundary on a P&ID (block valves, `pid-structural-rules.md`; ChatP&ID's isolation question). By the symmetry rule it
exists upstream and downstream.

| Label | Program (primitives; slots filled from anchors) | Neutral description (the classifier text) |
|---|---|---|
| `ITEM` | the anchors only (their sheets) | "the named items themselves" |
| `NEIGHBOURS_DOWNSTREAM` | `neighbours(a, downstream, flow)` per tag anchor | "items directly after the named item in the flow" |
| `NEIGHBOURS_UPSTREAM` | `neighbours(a, upstream, flow)` | "items directly before the named item in the flow" |
| `SIGNAL_CHAIN` | `traverse(a, both, signal, max_hops=3)` | "the instruments, controllers and valves linked to the named item by signal lines" |
| `PATH` | `path(a1, aj)` for each other anchor; if none directed, `path(aj, a1)` | "the flow route between two named items" |
| `UPSTREAM_TO_FIRST_VALVE` | `traverse(a1, upstream, flow, stop_at={label: OperatedValve})` | "every branch flowing into the named item, back to the first operated valve on each" |
| `DOWNSTREAM_TO_FIRST_VALVE` | `traverse(a1, downstream, flow, stop_at={label: OperatedValve})` | "every branch flowing out of the named item, up to the first operated valve on each" |
| `UPSTREAM_ALL` | `traverse(a1, upstream, flow)`; `walk_only={unit: U}` if a unit anchor is present | "everything that flows into the named item, however far back" |
| `DOWNSTREAM_ALL` | `traverse(a1, downstream, flow)`; same unit slot | "everything the named item's flow reaches, however far" |
| `UNIT_SCOPE` | `find({unit: U})` ∪ `neighbours($units, both, flow)` (the boundary) | "all items of the named unit and the lines crossing its boundary" |
| `GENERIC` | none — delegate to `Hierarchical` with the ADR-0030 parameters | "none of the above" |

### 4.2 Input, classifiers and decision

```python
class NeedInput(BaseModel):              # built from question text + the view only; frozen
    text: str                            # the question as given
    masked_text: str                     # tags -> "<TAG>", units -> "<UNIT>" (from extract_anchors)
    n_tag_anchors: int; n_unit_anchors: int

class NeedDecision(BaseModel):           # frozen
    label: NeedLabel
    score: float | None                  # probability of `label`; None for rules and Jev `choice`
    scores: dict[str, float] | None      # per-label probabilities when the classifier gives them
    classifier: str
    call: dict[str, Any] | None          # usage of the classifier call, for the trace

class NeedClassifier(Protocol):
    name: str
    def classify(self, need_input: NeedInput) -> NeedDecision: ...
```

| Classifier | How | Confidence | Cost |
|---|---|---|---|
| `RuleNeedClassifier` | an ordered table of `(regex over masked_text, anchor-count condition) → label`, first match wins, else `GENERIC`. **Written only from the dev templates** (`templates.py` + the dev-new templates, §8.2) | none | free |
| `LabelProbNeedClassifier` | one chat call: question + "names N items and M units" + the 11 descriptions as letters A–K; one-token answer; probabilities from `top_logprobs` (J-T1) | `P(top letter)` | paid |
| `JevNeedClassifier` | Jev `choice`, `state` = question text + the same count line, `criteria` = label → description (ADR-0032 pin, client and cache) | none (choice shape unknown until J-P1) | paid |
| `OracleNeedClassifier` | the family's gold label, looked up by question text in the **harness** (`qa/harness/need_gold.py`); never importable from `qa/strategies/` or `qa/need/` | 1.0 | free, analysis only |

Decision rule: use the label's program if `label ≠ GENERIC` **and** (`score is None` or `score ≥ τ`); otherwise
fall back.

### 4.3 Graceful degradation for unforeseen question types

1. Classifier says `GENERIC`, or its score is below `τ` → generic `Hierarchical` (ADR-0030 pair).
   `trace["need_fallback_reason"] = "generic" | "low_confidence"`.
2. The program's precondition fails (`PATH` with fewer than two tag anchors; a traversal with no tag anchor;
   `UNIT_SCOPE` with no unit anchor) → generic `Hierarchical`; reason `"precondition"`.
3. No anchor at all → generic `Hierarchical`, whose router fallback (D5) applies unchanged; reason `"no_anchor"`.
4. The program returns nothing (no neighbours, no path) → the context is the anchor sheets alone (never empty).
- **Invariant:** the need-aware context always contains every tag-anchor sheet in full. So for a misread question it
  degrades to at least Hierarchical with ring 0, and with rules 1–3 to Hierarchical itself.

### 4.4 Context and budget (`qa/need/context.py`)

- **Core** = every tag-anchor sheet and unit-anchor sheet, whole (as `SheetSelection.tag_sheets ∪ unit_sheets`).
- **Need part** = for each selected item on a sheet outside the core, its occurrence keys, plus the `via` stub keys of
  selected edges: serialized as a through-line on that sheet (the existing `_subgraph_with_through_lines` idea), so
  cross-sheet edges stay visible through their stubs.
- **Budget** (`max_context_chars`, the same value as Hierarchical): drop need items farthest from the anchors first
  (hop distance from `traverse`/`path`; ties by tag); never drop the core; if the core alone is over, send and flag
  `over_budget` (the shared fit check decides, as §3.4 of `hierarchical-and-jev.md`).
- Same serializer (`serialize_graph`), so Part 1 stays "ContextRAG on a selected subset" (D8).

### 4.5 Trace (in `RetrievalResult.trace`)

Every key of Hierarchical's trace (`routed_sheets`, `serialized_keys`, `context_chars`, `over_budget`, `truncated`,
`anchors`, …) plus: `need_label`, `need_score`, `need_scores`, `need_classifier`, `need_used: bool`,
`need_fallback_reason: str | None`, `need_program: list[str]` (the primitive calls as text), `need_items: int`,
`need_items_dropped: int`, `classifier_call` (usage, when paid).

### 4.6 Parameters (dev corpora only)

| Parameter | Values | Set by |
|---|---|---|
| `classifier` | `rules`, `labelprob`, `jev` | each is its own strategy name: `hierarchical_need_rules`, `_labelprob`, `_jev` |
| `fallback` | Hierarchical params | ADR-0030's selection (ROUTE-01) |
| `max_context_chars` | int | same as Hierarchical |
| `tau` | 0.0, 0.5, 0.7, 0.9 | `labelprob` only: the value with the highest mean evidence-node recall on D1000 dev-family questions; ties → higher `tau` (more fallback) |
| `classifier_pin` | `ModelPin` | user decision U3 (§17) |

## 5. Part 2 — the graph-tool agent (`qa/agent/`)

### 5.1 Loop (`qa/agent/loop.py`)

- Messages: system = `prompts/agent_graph_system.txt` with the **tool reference generated from the primitive
  registry** (name, one line, argument JSON schema from the Pydantic models) and the rules; user = a one-line plant
  summary ("The plant has N sheets and M units. Item labels: …. Relations: flow, signal.") + the question.
- Each step: one `ChatRequest(json_mode=True, purpose="agent_step")`. The reply must be
  `{"call": {"tool": "...", "args": {...}}}` or `{"done": true}`. The result of call *n* is saved as `$r<n>`.
- Observation = the result rendered (§3.3) to at most `observation_chars`; appended as the next user message
  `Result $r<n>:\n…`.
- Errors (unknown tool, invalid arguments, unknown handle, unparseable reply) become an observation
  `error: …` and count as `tool_errors` / `invalid_actions`; two consecutive errors stop the loop.
- Stop reasons: `done`, `max_steps`, `prompt_budget` (cumulative prompt characters over `max_prompt_chars_total`),
  `errors`.
- **Final context** = "Tool results gathered for this question:" + each call line and its observation, in order. It
  goes to the **shared final step** (`answer_question` unchanged). The agent never writes the answer itself.

```python
class AgentParams(BaseModel):            # frozen; fixed by design, not tuned (§5.4)
    max_steps: int = 6
    observation_chars: int = 4_000
    max_items_listed: int = 50
    max_prompt_chars_total: int = 150_000
    seed_chars: int = 12_000             # hier_agent only (§6)

class AgentStep(BaseModel):              # frozen; one per step, kept in the trace
    index: int; reply_text: str
    tool: str | None; args: dict[str, Any] | None
    observation_chars: int; error: str | None
    touched_keys: tuple[str, ...]
    usage: dict[str, Any]                # tokens, cost, latency, from_cache
```

### 5.2 Why plain JSON actions and not native tool calling (ADR-0034 sub-decision)

The chat client, its cache key (pin, `json_mode`, messages) and the fake transport need no change; the protocol is
identical for every model the user wants to try; parsing is deterministic. Every candidate model in the snapshot also
lists `tools` (F5 table source), so native calling stays a real alternative: **revisit if** the invalid-action rate on
the dev pilot (QAR-P2) exceeds 10 %.

### 5.3 Trace and measurement

`agent_steps: list[AgentStep]`, `stop_reason`, `n_steps`, `tool_errors`, `invalid_actions`, `routed_sheets` (sheets of
every touched item), `serialized_keys` (= union of `touched_keys`), `context_chars`. So strict/relaxed routing hit and
evidence-node recall work for agents unchanged (`routing_gold.py`), and so does the cost meter (§10).

### 5.4 Parameters

Fixed by design, not tuned: tuning loop parameters is paid at every point, and the budget goes to confirmation runs
(R9). The dev pilot QAR-P2 reports step use, stop reasons and error rates. **Revisit if** `max_steps` stops more than
10 % of dev questions, or observations are truncated on more than 20 % of steps.

### 5.5 `cypher_agent` — the free-form control

The same loop, one tool: `cypher(query: str)` → rows as JSON lines (CypherRAG's `format_context`), read-only,
`timeout_s` and `row_cap` as CypherRAG, write clauses rejected unsent. System prompt = CypherRAG's schema text + the
loop rules (`prompts/agent_cypher_system.txt`). Needs Neo4j (harness pre-check unchanged).

| Comparison | Isolates |
|---|---|
| `graph_agent` vs `cypher_agent` | typed primitives vs free-form query, iteration equal |
| `cypher_agent` vs `cypher_rag` | iteration, interface equal |
| `graph_agent` vs `hierarchical_need_*` | an LLM composing vs a fixed program per label |

Stated asymmetry: the primitives hide off-page connectors and identity links (they **are** the resolver's output);
Cypher sees them and must join through them. That is the hypothesis under test ("a typed plant API beats free-form
querying"), not a bias to remove. A second asymmetry: agents see a compact text rendering, Part 1 sees GraphML;
stated as a threat.

## 6. Part 3 — combinations

### 6.1 `hier_agent` (the user's hypothesis)

- Step 0, free: anchors + the **rules** classifier (no paid classifier inside the agent) + the label's program →
  a **seed map** in the compact rendering, capped at `seed_chars`; with `GENERIC`, the seed is the anchors' item
  records only.
- The seed map is the first user message's second part; the agent may answer `{"done": true}` at once (one call) or
  fetch more. Final context = seed map + observations.
- Trace: `seed_label`, `seed_chars`, then the agent keys.

### 6.2 Cascade (offline, no extra calls)

`cascade_<classifier>` = per question, the `hierarchical_need_<classifier>` row if its need was used (not a fallback),
else the `graph_agent` row. Computed in `qa/frontier_report.py` from the two runs' `answers.jsonl`; cost = the chosen
row's cost **plus** the classifier's cost. It tests "cheap selection when the type is known, an agent otherwise" with
no call. The Jev router arm (ADR-0032 J-T5) may list the new arms as further options; nothing here depends on it.

### 6.3 How the measurement can confirm or refute "the combination is the scalable answer"

Pre-registered in ADR-0035 as **Q3** (primary). In short: at H1000 on the held-out families, `hier_agent` must be
not worse than `graph_agent` **and** not worse than the best `hierarchical_need_*`, better than at least one of them
(paired CI excludes 0), and no more expensive per question than `graph_agent`. It is **refuted** if any arm beats it
with a CI excluding 0 at lower or equal mean cost. Anything else is reported as "not confirmed". Q4 adds the scale
side: accuracy H1000 − H100 and the cost elasticity per arm (§10.3).

## 7. What each arm sends to the final step

| Arm | Retrieval calls | Final context | Typical size driver |
|---|---|---|---|
| `hierarchical` (ADR-0030 pair) | 0 (1 if router fallback) | GraphML of routed sheets | route length (HIER-CTX-01) |
| `hierarchical_need_rules` | 0 | GraphML: anchor sheets + need through-lines | anchor sheets + need size |
| `hierarchical_need_labelprob` / `_jev` | 1 small | same | same |
| `graph_agent` | ≤ 6 | compact text of observations | steps × observation cap |
| `hier_agent` | ≤ 6 (often fewer) | seed map + observations | same, seed first |
| `cypher_rag` | 1 | query + rows | rows |
| `cypher_agent` | ≤ 6 | queries + rows | steps × row cap |

## 8. Question families

### 8.1 Splits

| Split | Families | Visible to strategy authors | Used for |
|---|---|---|---|
| **dev-old** | the 12 built: `LOOKUP_TYPE`, `LOOKUP_UNIT`, `NEIGHBOURS_DOWNSTREAM`, `LOOP_ACTUATED_VALVE`, `LOOP_MEASURED_EQUIPMENT`, `FLOW_PATH`, `UPSTREAM_ISOLATION`, `CROSS_UNIT`, `COUNT_IN_UNIT`, `UNANSWERABLE_TAG`, `NO_PATH`, `SHEETS_OF_TAG` | yes | rules, prompts, tuning (dev corpora), test |
| **dev-new** | 6 new (§8.2), the user's examples | yes | same |
| **held-out** | 6 families, sealed (§9) | **no** — opened only after F1 | test only (H100, H1000) |
| **held-out wordings** (should) | one new wording per answerable dev-old family, sealed | **no** | test only: wording vs need generalisation |

`qa/harness/family_meta.py` (harness side) holds per family: `split`, `gold_need: frozenset[NeedLabel]` (acceptable
labels). Strategies cannot import it (import-ban test, §13).

### 8.2 Dev-new families (visible; topology only, ADR-0021)

| Family | Template | Answer type | Reference (ground truth) | Evidence | Gold need |
|---|---|---|---|---|---|
| `CONNECTED` | "Can process flow reach {B} from {A}?" | `BOOLEAN` | `"yes"` iff `B ∈ desc(A)` over `send_to` | yes: shortest path; no: BFS tree of `desc(A)` | `PATH` |
| `DOWNSTREAM_IN_UNIT` | "Which equipment items and valves in unit {U} receive flow from {X}, directly or indirectly?" (`U` = unit of `X`) | `TAG_SET` | items reached from `X` walking only through items of unit `U`; equipment and valves; `X` excluded | walked edges | `DOWNSTREAM_ALL` |
| `INSTRUMENTS_OF_ITEM` | "Which instruments measure {X}?" | `TAG_SET` | tags of `v` with `(X, v)` `measured_by`; candidates: equipment with at least one | those edges | `SIGNAL_CHAIN` |
| `UPSTREAM_SOURCES` | "Which source items, with nothing flowing into them, ultimately feed {X}?" | `TAG_SET` | `{v ∈ anc(X) : v has no send_to predecessor}` | BFS tree of `anc(X)` | `UPSTREAM_ALL` |
| `SAME_UNIT` | "Are {A} and {B} in the same unit?" | `BOOLEAN` | `unit(A) == unit(B)`; pairs drawn half from the same unit, half from a unit joined to it by a `send_to` edge (seeded) | nodes `A`, `B`, no edges (k = 0) | `ITEM` |
| `LOOPS_NEAR_ITEM` | "Which control loops act on valves directly connected to {X}?" | `TAG_SET` | loop tags (controller tags) whose actuator controls a valve that is a `send_to` neighbour of `X`, either direction | `X`–valve edges + valve ← actuator ← controller edges | `GENERIC` (composite) |

- Per-anchor cap and k-bins as ADR-0029; `CONNECTED` and `SAME_UNIT` alternate yes/no within a bin (seeded).
- **`AnswerType.BOOLEAN`**: reference stored as `"yes"`/`"no"` (`AnswerValue` unchanged); the final-step instruction
  `Answer with "yes" or "no".`; scoring accepts JSON `true`/`false` or the strings, case-folded.

### 8.3 EXP-0006 question sets

- Per corpus and family: `n_per_family` questions (seeded), dealt round-robin over the family's available k-bins
  (so the long bins are present where they exist). `n_per_family` is user decision U1 (§17); minimum plan 10.
- Files under a separate root, `data/questions-exp0006/<corpus_id>/questions.jsonl`, passed as the harness's
  `questions_root` (no harness change).
- Dev corpora (D100, D1000): dev-old + dev-new only. Test corpora (H100, H1000): all splits, held-out added after F1.

## 9. Freeze and the sealed held-out set (ADR-0035)

- **Sealed file:** `docs/private/40-design/heldout-families.sealed.md`,
  **sha256 `905c7984dfc1d346cb696c47590d972d545455fd1149517534ad2309955ff63b`** (computed 2026-10-02 after writing).
  It holds 6 families and 10 wordings, each with a reference definition, evidence, answer type and gold need labels.
  This note names none of them on purpose.
- **Who may open it:** only the coder of QAR-T10, after F1. The main session hands it over; no strategy task receives
  it. The user may read it at any time (the user writes no strategy code).
- **Freeze F1** (main session, before QAR-T10): `data/freeze/qar-freeze.json` with the sha256 of every file under
  `qa/plant_api/`, `qa/need/`, `qa/agent/`, `qa/strategies/`, `qa/prompts/`, and of `qa/anchors.py`, `routing.py`,
  `sheet_selection.py`, `context_budget.py`, `serialize.py`, `final_answer.py`, `graph_view.py`; the parameter values
  (`tau`, `AgentParams`, Hierarchical's); the git commit (the user commits first). A test (QAR-T10) asserts the hashes.
- **After F1**, a change to a frozen file makes every held-out number "post hoc", reported separately, and needs a new
  ADR.
- **Stated threat:** the architect wrote the need labels, the primitives and the sealed families in the same session.
  The label set is fixed by a stated rule (shape × direction from the schema, §4.1) and the primitives by a stated
  completeness argument (§3.3), both written into this note; the professor can judge whether the families were fitted
  to them. One sealed family is expected to fall outside the primitives on purpose (a boundary probe).
- **Should-tier strengthening:** after F1, a second held-out set written by a fresh `researcher` session that has
  never seen this note or the code, from external sources (ChatP&ID App. Table 1's topology questions, PIDQA's question
  categories), under the same constraints. Not designed further here.

## 10. Cost and speed

### 10.1 Total per-question accounting (QAR-T1)

```python
class CallUsage(BaseModel):              # frozen; qa/models.py
    n_calls: int; n_cached: int
    prompt_tokens: int; completion_tokens: int
    cost_usd: float | None               # sum as billed when first made (cache keeps it, §6); None if any call lacked cost
    n_cost_missing: int
    llm_latency_s: float                 # sum of recorded call latencies
    spent_usd: float                     # cost of the calls not served from cache in this invocation
```

- `QuestionResult` gains `retrieval_usage: CallUsage | None = None`. The existing token/cost/latency fields keep their
  meaning (final call); `report.py` derives `total_cost_usd`, `total_tokens`, `total_llm_latency_s`.
- `harness/usage_meter.py`: `UsageMeter.begin(question_id)` / `record(response, seconds_in_call)` / `end() -> CallUsage`.
  The runner's per-strategy senders log with `question_id=meter.question_id` (fixes F2) and record into the meter;
  `_attempt` brackets each item. The strategy still receives only the text.
- **Local compute time** (retrieval work outside model calls) = wall time of `answer_question` − time inside every
  send. It is wall-clock, so it goes to `data/runs/<run_id>/timings.jsonl`, **not** to `answers.jsonl` (the replay
  test stays byte-identical).
- Latency per question = `llm_latency_s` (retrieval) + final `latency_s` + local compute.

### 10.2 Metrics (per arm × corpus × split, and per family)

End-to-end accuracy [95 % CI]; generalisation gap = accuracy(dev-old ∪ dev-new) − accuracy(held-out), unpaired
bootstrap; need accuracy, confusion matrix and fallback rate (Part 1); steps, stop reasons, tool-error and
invalid-action rates (agents); evidence-node recall (all arms); total cost per question (mean, p50); total tokens;
latency p50/p90; context characters; did-not-fit, parse-failure, retrieval-error rates as today.

### 10.3 Frontier and elasticity (`qa/frontier_report.py`)

- Per corpus: (mean total cost per question, end-to-end accuracy) per arm, the Pareto frontier marked, latency p50 as
  a third column; the cascade and the oracle-need variant added as computed points.
- **Cost elasticity** per arm: `e = ln(cost_H1000 / cost_H100) / ln(sheets_H1000 / sheets_H100)`; `e = 1` is linear
  in plant size, `e = 0` flat. Bootstrap CI over questions.

### 10.4 Budget — estimates, not measurements

Prices from the listing snapshot (`openrouter-models-2026-10-02.json`, per million tokens, input / output):
gpt-5-mini 0.25 / 2.00; glm-5.3-flash 0.15 / 0.50; deepseek-v4-flash 0.042 / 0.084. The gpt-5-mini price reproduces
LLM-SMOKE-01's billed cost exactly (13 × 0.25 + 63 × 2.00 per million = $0.00012925). **Assumptions (estimates):**
4 characters per token (rule of thumb; the pilot measures GraphML); Hierarchical-type final prompt 40,000 characters
(between the probe's H100 medians of 20,646 at k = 0 and 51,131 at k = 2) + 1,000 output tokens; agent 36,000 input +
4,000 output tokens per question including the final step (6 steps × ≤ 4,000-character observations, reasoning tokens
counted as output per LLM-SMOKE-01); CypherRAG 6,000 / 1,500 over its two calls.

| Arm, per question (estimate) | gpt-5-mini | glm-5.3-flash | deepseek-v4-flash |
|---|---|---|---|
| Hierarchical-type | $0.0045 | $0.0020 | $0.0005 |
| agent (`graph_agent`, `hier_agent`) | $0.0170 | $0.0074 | $0.0018 |
| `cypher_rag` | $0.0045 | $0.0017 | $0.0004 |

**Minimum EXP-0006 plan** (`n_per_family = 10`, 24 families × 2 test corpora = 480 questions per arm; arms:
`hierarchical`, `hierarchical_need_rules`, `hierarchical_need_labelprob`, `graph_agent`, `hier_agent`, `cypher_rag`;
cascade and oracle computed free): ≈ **$25.0** (gpt-5-mini), **$10.8** (glm-5.3-flash), **$2.7** (deepseek-v4-flash).
Arithmetic: 1,440 Hierarchical-type + 960 agent + 480 CypherRAG questions × the table. The dev pilot QAR-P2 adds
≈ $3.1 / $1.3 / $0.3. **With the $5 balance this fits only a deepseek-v4-flash-class answer pin**, and the headline
sweep needs money from the same balance. The answer pin is ADR-0019's (the pilot's) decision, not this note's. User
decision U2.

## 11. EXP-0006 protocol (pre-registered in ADR-0035)

1. **Free first, on every corpus:** NEED-01 (need report: rules and oracle classifiers × dev families, then
   held-out after F1) and API-01/API-02. Rows in `_results.md`.
   - **Gate N1 (free, pre-registered):** on H100 at the ROUTE-01 settings (`sheet_hops` 1, 100k budget), the
     evidence-node recall of `hierarchical_need_rules` on `UPSTREAM_ISOLATION` must exceed the generic
     Hierarchical's 0.760 (ROUTE-01 H100 part). If it does not, the need program or the rules are wrong, and no paid
     Part 1 run starts until it is understood. Reported either way, with the oracle-label value beside it (which
     separates a classifier miss from a program miss).
   - **Gate N2 (free):** on FLOW_PATH, `hierarchical_need_rules` must not fall below the generic flow route's 1.000
     node recall by more than 0.01 (it should reach the same path through `path`).
2. **Paid classifiers (QAR-P1):** `labelprob` and `jev` on the D100/D1000 dev questions → need accuracy, `tau`
   selection. Then on test after F1.
3. **Agent dev pilot (QAR-P2):** `graph_agent`, `hier_agent` on D100, 5 questions per dev family; reports only the
   revisit triggers (§5.4). Never selects an arm.
4. **F1 freeze**, unseal, QAR-T10.
5. **Test runs (QAR-P3):** the arms of §10.4 on H100 and H1000 under the ADR-0019 pin, one repeat.
6. **Report:** Q1–Q5 (ADR-0035), the frontier and elasticity, per-family tables, the cascade.

## 12. Files

| File | New / changed | Holds |
|---|---|---|
| `src/plantgraph/qa/plant_api/model.py`, `item_graph.py`, `primitives.py`, `results.py`, `tool_registry.py` | new | §3 |
| `src/plantgraph/qa/need/labels.py`, `rules.py`, `classifiers.py`, `programs.py`, `context.py` | new | §4 |
| `src/plantgraph/qa/strategies/hierarchical_need.py` | new | `NeedAwareHierarchical` |
| `src/plantgraph/qa/agent/loop.py`, `graph_tools.py`, `cypher_tools.py`, `seed.py` | new | §5–§6 |
| `src/plantgraph/qa/strategies/graph_agent.py`, `cypher_agent.py` | new | `GraphAgent`, `HierAgent`, `CypherAgent` |
| `src/plantgraph/qa/prompts/agent_graph_system.txt`, `agent_cypher_system.txt`, `need_classify.txt` | new | prompts (hashed by `freeze.py`) |
| `src/plantgraph/qa/harness/usage_meter.py`; `runner.py`, `registry.py` | new / changed | §10.1; registry entries |
| `src/plantgraph/qa/harness/family_meta.py`, `need_gold.py`, `canonical_programs.py` | new | gold side |
| `src/plantgraph/qa/models.py` | changed | `CallUsage`, `QuestionResult.retrieval_usage`, `AnswerType.BOOLEAN`, dev-new `QuestionFamily` members |
| `src/plantgraph/llm/models.py` | changed | `CallPurpose` + `"agent_step"`, `"need_classify"` |
| `src/plantgraph/qa/scoring.py`, `final_answer.py` | changed | `BOOLEAN` |
| `src/plantgraph/qa/questions/families_dev2.py`, `templates.py` | new / changed | §8.2 |
| `src/plantgraph/qa/need_report.py`, `frontier_report.py` | new | §10.3, §11 |
| `src/plantgraph/qa/questions/families_heldout.py`, `templates_heldout.py` | new, **QAR-T10 only** | sealed spec |
| `data/freeze/qar-freeze.json` | new (F1) | freeze manifest |

## 13. Testing (every coder acceptance offline: fake transport, replay cache, no network)

| Component | Tests |
|---|---|
| item graph | on split toy plants at duplication 0.0 and 0.5: edges by tag equal the gold plant's (test-side mapping through `occurrence_map`); a reference occurrence merges into its home; a stub pair contracts to one edge with `via`; an unpaired stub becomes the pseudo-item |
| primitives | hand-built toy with branches, a cycle and a check valve: each primitive's result by hand; `stop_at` stops after including; `walk_only` never enters; handles compose; truncation header counts; deterministic order |
| canonical programs | every dev family's program equals its reference function on a toy corpus's question set (API-02 at 1.0) |
| rules classifier | every dev template (old and new) maps to its gold label; an anchor-count condition decides `PATH` vs `ITEM` for two anchors; text matching no rule → `GENERIC` |
| need programs + context | core sheets always whole; farthest items dropped first; over-budget core flagged; precondition failures fall back with the right reason; the fallback context equals `Hierarchical`'s byte for byte |
| paid classifiers | scripted fakes: letter probabilities → label and score; `tau` fallback; Jev `choice` via the fake System One client |
| agent loop | scripted replies: a two-step composition with a handle; invalid JSON → `invalid_actions` and recovery; two consecutive errors stop; `max_steps` and `prompt_budget` stop; final context lists every call; trace keys present |
| `hier_agent` | seed map built from the rules label; `done` at step 1 sends the seed map to the final step |
| `cypher_agent` | write clause rejected unsent; rows rendered; same stop rules |
| usage meter | CypherRAG's query call and the final call both counted; retrieval calls logged with the question id; a cached call adds to `cost_usd`, not to `spent_usd`; replay of a toy run gives a byte-identical `answers.jsonl`; `timings.jsonl` written |
| dev-new families | hand-built split toy: reference, evidence, `k`, `u` by hand; yes/no balance; same seed → identical JSONL |
| `BOOLEAN` | `true`/`"Yes"`/`"no"` scored; final-step instruction present |
| import ban | `qa/plant_api/`, `qa/need/`, `qa/agent/`, the new strategies import nothing from `qa.questions`, `qa.harness`, `qa.corpus`, `benchmark.splitter`, `benchmark.rejoin`, `eval` (extends `qa-system.md` §16's test) |

## 14. How each component reports its own accuracy

| Component | Metric against ground truth |
|---|---|
| item graph | API-01 edge precision/recall by tag vs the gold plant |
| primitives | API-02 canonical-program accuracy per family (coverage of the API) |
| need classifier | need accuracy vs `gold_need` (acceptable set), confusion matrix, fallback rate |
| need context | evidence-node recall, routing hit, context characters, over-budget rate |
| agents | evidence-node recall of the observations, steps, stop reasons, tool-error and invalid-action rates |
| usage meter | per-question sums equal the matching `calls.jsonl` lines (test) |
| every arm | end-to-end accuracy, total cost, latency — per family and split |

## 15. Ordered coder tasks (one Sonnet coder at a time; each ends green on ruff, mypy --strict, pytest, offline)

| # | Task | Depends on | Size (estimate) |
|---|---|---|---|
| **QAR-T1** | `CallUsage`, `UsageMeter`, runner wiring, question id on retrieval calls, `timings.jsonl`; `report`/`summary` read totals (§10.1) | **H-T4 finished** (it edits `harness/cli.py`, the runner's neighbour) | S |
| **QAR-T2** | `qa/plant_api/`: item graph, filter, six primitives, results and rendering, tool registry; API-01 check function (§3) | — | M |
| **QAR-T3** | `AnswerType.BOOLEAN` (scoring, final-step line); six dev-new families + templates; `family_meta.py`, `need_gold.py` for dev-old and dev-new; `canonical_programs.py` for all 18 dev families (API-02) (§8.2, §3.4) | QAR-T2 (canonical programs) | M |
| **QAR-T4** | `qa/need/`: labels, rules classifier (from dev templates only), programs, context and budget; `NeedAwareHierarchical` + registry entry `hierarchical_need_rules`; `OracleNeedClassifier` in the harness only (§4) | QAR-T2, QAR-T3, H-T2 (built) | M |
| **QAR-T5** | `qa/need_report.py`: free retrieve-only report per family × classifier (rules, oracle) vs `hierarchical`: need accuracy, fallback, evidence-node recall, chars, local time → CSV + markdown (§11.1) | QAR-T4 | S |
| — | *Main session: **NEED-01**, **API-01/02** on D100, D1000, H100, H1000 (free); `_results.md` rows* | QAR-T5 | minutes |
| **QAR-T6** | `qa/agent/` loop + graph tools + seed; `GraphAgent`, `HierAgent`; prompts; registry entries (§5, §6.1) | QAR-T1, QAR-T4 | M |
| **QAR-T7** | `CypherAgent` + `agent_cypher_system.txt` (§5.5) — should | QAR-T6 | S |
| **QAR-T8** | `LabelProbNeedClassifier`, `JevNeedClassifier`, `need_classify.txt`; registry `hierarchical_need_labelprob`, `_jev`; `tau` selection in `need_report.py` (§4.2) | **J-T1** | S |
| **QAR-T9** | `qa/frontier_report.py`: totals, frontier, elasticity, generalisation gap, cascade and oracle points, per-family tables (§6.2, §10.3) | QAR-T1 | S/M |
| — | ***QAR-P1:** paid classifiers on dev questions (D100, D1000) — **run by the user, paid, logged*** | QAR-T8, J-P1 (Jev `choice` shape) | ≈ 2 × 1,000 small calls |
| — | ***QAR-P2:** agent dev pilot on D100 — **run by the user, paid, logged*** | QAR-T6 | 180 questions |
| — | *Main session: **F1 freeze** — hashes, parameters, commit (the user commits)* | QAR-T1…T9, QAR-P1, QAR-P2 | — |
| **QAR-T10** | **Sealed:** open `heldout-families.sealed.md`; held-out families and wordings, generated on H100/H1000 only; freeze-manifest test | F1 | M |
| — | ***QAR-P3:** EXP-0006 test runs on H100, H1000 under the ADR-0019 pin — **run by the user, paid, logged*** | QAR-T10, ADR-0019 | §10.4 |

S < ~150 changed lines including tests; M ~150–400.

**Order rationale.** QAR-T1 first: it corrects a cost gap that also affects the headline's CypherRAG column, and the
agent cannot be costed without it. QAR-T2–T5 give a **free partial result early** (NEED-01, API-01/02) with no model
call. The agent (T6) and the paid classifiers (T8) follow; T8 waits for J-T1. The sealed task comes last by
construction. Where these tasks sit in the queue relative to the J-tasks (EXP-0004) and the pilot is the user's call
(U4).

## 16. ADRs proposed

- **ADR-0033** — select context by a classified information need over a closed set of evidence shapes, with
  interchangeable classifiers and fallback to Hierarchical.
- **ADR-0034** — a graph-tool agent over six generic composable primitives, plain JSON actions, bounded loop, shared
  final step; `cypher_agent` as the free-form control; `hier_agent` and the offline cascade as the combinations.
- **ADR-0035** — EXP-0006: sealed held-out families with a hash-recorded freeze, total per-question cost accounting,
  and the pre-registered claims Q1–Q5.

On acceptance the main session updates: `qa-system.md` §7 (fairness rule "runs once per question": agents are the
stated exception; D4 now names the built agent arms), §11 (total cost), §17 (new component metrics), §18 T20 (points
here); `00-index.md`; `40-design/README.md`.

## 17. Open questions and user decisions

- **U1 — `n_per_family`.** 10 (minimum plan, pooled 60 questions per held-out split per corpus, ≈ ±12.6 points
  half-width at worst case, arithmetic `1.96 × √(0.25/60)`) or 20 (≈ ±8.9 points, double the cost).
- **U2 — money.** At listing prices, the minimum plan costs ≈ $2.7–$25 depending on the answer pin (§10.4,
  estimate); the balance is $5 and also pays for the headline. Either a deepseek-v4-flash-class pin for EXP-0006, a
  top-up, or fewer arms (drop `hierarchical_need_labelprob` first: its context differs from `_rules` only where the
  labels differ, which NEED-01 counts for free).
- **U3 — classifier pin.** The label-probability classifier needs `logprobs` (F5): not gpt-5-mini; glm-5.3-flash or
  deepseek-v4-flash per the snapshot. A small, separate pin is recommended (classifier calls are tiny).
- **U4 — queue position.** Recommended: QAR-T1 now (after H-T4), then QAR-T2–T5 (free result), then the J-tasks as
  planned, then QAR-T6–T9.
- **U5 — `cypher_agent`.** Should-tier (recommended) or must. It is the cleanest test of "typed API vs free-form
  query".
- **O1 (pilot).** The 4-characters-per-token assumption and the Hierarchical-type prompt size; the pilot measures both.
- **O2 (researcher).** A citation for "standard graph-query operations" (regular path queries / graph query language
  surveys) is owed before the thesis text cites §3.3's completeness argument; none was read for this note.

## 18. Figures in this note and their sources

| Figure | Source |
|---|---|
| 1,649,451 / 16,746,349 ContextRAG characters at H100 / H1000 | `_results.md` PROMPT-04 |
| Hierarchical context medians 174,500 / 209,368 characters at H1000, k ≥ 5 | `_results.md` HIER-CTX-01 |
| H100 probe medians 20,646 (k = 0) and 51,131 (k = 2) characters | `_results.md` ROUTE-00; `hierarchical-and-jev.md` §2 |
| UPSTREAM_ISOLATION strict 0.421 / node 0.760 (76 questions, identical across all combinations and budgets); all-family node recall 0.90 / 0.95; FLOW_PATH relaxed and node 1.000 under `flow_path`; `drop_rings` over budget 45–49 % at 100k; 5.1 % no-anchor failures | `_results.md` ROUTE-01 (H100 part), 2026-10-02 |
| gpt-5-mini billed $0.00012925 for 13 in / 63 out; reasoning tokens counted as output; 2.74 s / 2.58 s latency | `_results.md` LLM-SMOKE-01 |
| Prices, context lengths, `logprobs` / `tools` support | `30-experiments/openrouter-models-2026-10-02.json`, read by the architect 2026-10-02 |
| $5 balance, standing approval | user memory `project_openrouter_budget.md` (2026-10-02) |
| G1 holds at H100/H1000 (no unpaired stubs) | `_results.md` SMOKE-04b |
| Per-question costs, plan totals, ±12.6 / ±8.9 points | arithmetic on the rows above under the stated assumptions — **estimates** |
| Sealed file sha256 | `sha256sum`, run by the architect 2026-10-02 after the last edit |
| F1–F4 code findings | `harness/runner.py`, `strategies/base.py`, `final_answer.py`, `sheet_selection.py`, read 2026-10-02 |
