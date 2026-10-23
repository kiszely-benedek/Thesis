---
component: Hierarchical strategy with two routing and two over-budget modes (QA-T13); EXP-0004 tag-variant identity with interchangeable deciders; Jev (TypeSafe System One) as a measured decider and strategy router
status: draft — awaiting review
related: [ADR-0030, ADR-0031, ADR-0032 (all proposed); ADR-0013, ADR-0014, ADR-0022, ADR-0025–0029; qa-system.md §5, §7, §13.3 C4, §17, §18 T12/T13/T18–T20, §19 D5; kg-construction.md §5.3, §6]
date: 2026-10-02
---

# Design — Hierarchical routing variants, and the Jev arm

## 0. Recommendation

| # | Item | Decision | ADR |
|---|---|---|---|
| A1 | Routing between anchors | Build both: `route="sheet_graph"` (undirected sheet graph, **with identity links added**) and `route="flow_path"` (weighted shortest directed item path). A free dev metric picks the default | 0030 |
| A2 | Route too long for the budget | Build both: `budget="drop_rings"` and `budget="through_line"`. Same selection procedure | 0030 |
| A3 | Measurement | Strict routing recall (as built) **plus** relaxed routing hit (FLOW_PATH) and evidence-node recall after budget; all free, on every corpus | 0030 |
| A4 | Dev corpus for the choice | New **D1000** (seed 1, headline preset): only a ~1,000-sheet corpus reaches the far bins where the modes differ | 0030 |
| B1 | EXP-0004 | Variant generator (format + naming families) → blocking → six deciders on the same candidates; the naming family held out of all tuning | 0031 |
| B2 | Jev in EXP-0004 | `noul` per candidate pair, pinned `jev-1.13`, next to a **label-probability chat-LLM readout** (novelty audit) | 0032 |
| B3 | Jev router | `choice` over strategies from question text + a fixed corpus descriptor; compared with every fixed strategy, a static dev-best policy and the oracle. **Strategy only, not the model** (ADR-0014 freeze). Should-tier | 0032 |
| B4 | Reproducibility | Separate `SystemOneClient` behind the same paid-call guard; decision cache with replay; resolved-model-id check | 0032 |

Coder tasks: 9, one Sonnet coder at a time (§10). Paid steps: 6, each **run by the user, paid, needs approval**.

**Expected outcome, from the probe (§2), not a decision:** `flow_path` wins routing and `through_line` wins the
budget. The pre-registered rule on D1000 decides; if it picks otherwise, the rule stands.

## 1. Which part of the claim each piece serves

- **Hierarchical is C4** (`qa-system.md` §13.3): "the hierarchy survives past the wall". If it routes past the
  evidence, it loses for a reason unrelated to scale. Routing recall separates "wrong context" from "wrong
  reading", per k-bin — the claim's x-axis (ADR-0013, ADR-0029).
- **EXP-0004 is supporting contribution 2** (`00-index.md`): cross-sheet identity is what joins sheets into one
  plant. Under inexact tags, every `k_identity` crossing (ADR-0028) is invisible to every strategy.
- **The router arm** tests the claim from the other side: if the best strategy depends on scale, a per-question
  router with the corpus size in view should approach the oracle, and a fixed strategy should not.

## 2. Evidence: architect probe, 2026-10-02 (scratch, not in the repo)

**Method.** `route_probe.py` and `throughline_probe.py` in the session scratchpad. They call
`build_synthetic_corpus` with `HeadlinePreset()` (seed 0; H100 = 51 units / 101 sheets, H1000 = 509 units / 1,001
sheets, as SMOKE-04b), `NetworkxGraphView`, and `flow_path_candidates(..., seed=1)`. Sample: 3,000 FLOW_PATH
candidates per corpus (seeded). Anchors are taken from the reference path, i.e. **anchor extraction assumed
perfect**; hop ring 0; no budget. Prototype routes, imitating §3.2–§3.3:
- `a_cont`: §7 as written — undirected sheet graph from `continues_as` only;
- `a_cont_id`: the same with identity links (home sheet ↔ reference sheet);
- `b_flow`: weighted multi-source Dijkstra over the occurrence graph (§3.3).

"strict" = `evidence_sheets ⊆ S` (the harness's built `routing_hit`). "relaxed" = some `send_to` path from source to
target lies on nodes drawn on `S` (§3.7). Every figure is re-measured by ROUTE-01 (§10) on the real code.

**Sheet graph connectivity**

| Corpus | Sheet edges, `continues_as` only | Components | With identity links | Components | Sheet pairs joined only by identity |
|---|---|---|---|---|---|
| H100 | 86 | 15 | 109 | 1 | 23 |
| H1000 | 896 | 117 | 1,103 | 1 | 207 |

**Routing, H100** (n per bin from the 3,000 sample; "found" = a route exists)

| k-bin | n | `a_cont` found / strict / relaxed | `a_cont_id` found / strict / relaxed | `b_flow` found / strict / relaxed | \|S\| median (max), `b_flow` |
|---|---|---|---|---|---|
| 0 | 1,721 | 1.000 / 0.987 / 1.000 | 1.000 / 0.987 / 1.000 | 1.000 / 0.987 / 1.000 | 1 (3) |
| 1 | 615 | 0.870 / 0.912 / 1.000 | 1.000 / 0.912 / 1.000 | 1.000 / 0.912 / 1.000 | 2 (4) |
| 2 | 328 | 0.652 / 0.561 / 0.671 | 1.000 / 0.793 / 0.973 | 1.000 / 0.823 / 1.000 | 3 (5) |
| 3–4 | 214 | 0.626 / 0.393 / 0.575 | 1.000 / 0.654 / 0.981 | 1.000 / 0.692 / 1.000 | 4 (5) |
| 5–8 | 98 | 0.571 / 0.316 / 0.388 | 1.000 / 0.571 / 0.786 | 1.000 / 0.806 / 1.000 | 6 (9) |
| 9–16 | 24 | 0.125 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 | 1.000 / 0.542 / 1.000 | 10 (12) |

**Routing, H1000** (33,546 FLOW_PATH candidates; 3,000 sampled)

| k-bin | n | `a_cont` found / strict / relaxed | `a_cont_id` found / strict / relaxed | `b_flow` found / strict / relaxed | \|S\| median (max), `b_flow` |
|---|---|---|---|---|---|
| 0 | 1,787 | 1.000 / 0.992 / 1.000 | 1.000 / 0.992 / 1.000 | 1.000 / 0.992 / 1.000 | 1 (3) |
| 1 | 591 | 0.904 / 0.931 / 1.000 | 1.000 / 0.929 / 1.000 | 1.000 / 0.929 / 1.000 | 2 (4) |
| 2 | 283 | 0.753 / 0.622 / 0.710 | 1.000 / 0.866 / 0.958 | 1.000 / 0.912 / 1.000 | 3 (5) |
| 3–4 | 189 | 0.603 / 0.444 / 0.497 | 1.000 / 0.778 / 0.958 | 1.000 / 0.831 / 1.000 | 4 (6) |
| 5–8 | 103 | 0.466 / 0.291 / 0.369 | 1.000 / 0.592 / 0.942 | 1.000 / 0.650 / 1.000 | 6 (9) |
| 9–16 | 44 | 0.477 / 0.159 / 0.159 | 1.000 / 0.409 / 0.591 | 1.000 / 0.614 / 1.000 | 10 (15) |
| 17–32 | 3 | 0.333 / 0.000 / 0.000 | 1.000 / 0.000 / 0.000 | 1.000 / 0.667 / 1.000 | 18 (19) |

`a_cont`'s route sets reach 31–34 sheets at k = 1–8 (maximum): with 117 components, the routes it does find are
long detours. Probe wall-clock 2,313.9 s at H1000, almost all in the prototype's unoptimised per-question search;
not a measure of the real code.

**Context size of the `b_flow` route, H100** (40 sampled per bin, 25 in 9–16; `serialize_graph` characters)

| k-bin | route sheets median (max) | full sheets: median (max) | through-line: median (max) |
|---|---|---|---|
| 0 | 1 (3) | 20,646 (44,250) | 20,646 (44,250) |
| 1 | 2 (3) | 37,822 (67,608) | 37,822 (67,608) |
| 2 | 3 (3) | 51,131 (67,608) | 36,825 (53,232) |
| 3–4 | 4 (5) | 79,134 (113,661) | 43,611 (77,773) |
| 5–8 | 6 (9) | 118,717 (169,905) | 46,640 (81,913) |
| 9–16 | 10 (12) | 177,057 (209,641) | 54,827 (83,520) |

**Findings**

- **F1 — the §7 sheet graph is broken at duplication 0.25.** A duplicated item replaces a cut (ADR-0028), so some
  sheets touch only through an identity link (H100: 15 components, H1000: 117). `a_cont` finds no route for 13 % of
  k = 1 and 87.5 % of k = 9–16 questions at H100, and for 9.6 % and 52.3 % at H1000. Fix, in both modes: identity
  links join the home sheet and each reference sheet (1 component at both sizes).
- **F2 — `k` counts crossings, not distinct sheets.** Flow paths go back and forth between the sheets of a unit.
  The shortest *sheet* path skips sheets the flow visits. With identity links, the undirected route's relaxed hit
  falls to 0.786 (H100) / 0.942 (H1000) at k = 5–8 and to 0.000 / 0.591 at k = 9–16. The flow route covers a valid
  path for every sampled question in every bin at both sizes (relaxed 1.000), including the 3 at k = 17–32 (median
  18 sheets).
- **F3 — strict recall under-counts.** `evidence_sheets` lists *every* sheet an evidence node is drawn on,
  including reference sheets a path never uses (`evidence.py` `evidence_sheets`), and the scorer accepts any valid
  path, not only the gold one (`scoring.py` `_is_valid_ordered_path`). Strict recall is 0.987 (H100) / 0.992
  (H1000) even at k = 0, for every route. Two
  added metrics (§3.7) fix the reading; strict stays as pre-registered (§17).
- **F4 — through-line keeps the context nearly flat in route length.** From k = 2 to k = 9–16 the full-sheet median
  grows 51,131 → 177,057 characters, the through-line median 36,825 → 54,827. The full-sheet growth per route
  sheet matches PROMPT-04's ≈16,730 characters per sheet (arithmetic: 16,746,349 / 1,001).

**What the probe does not show.** Anchor extraction from text (assumed perfect), families other than FLOW_PATH,
accuracy (no model call), and whether a model reads a through-line as well as a full sheet. Those are ROUTE-01
(free) and the paid ablation (§10).

## 3. Part A — Hierarchical (QA-T13)

### 3.1 Steps

1. **Anchors** (unchanged from §7): tag tokens, adjacent token pairs, `find_by_tag` (also `piping_component_name`);
   `unit <id>` against `unit_ids()`. Anchors are ordered by **first position in the question text**.
2. **Router fallback** (unchanged, D5): no anchor → one LLM call over a plant map → unit ids. Counted.
3. **Core sheets** `C`: every sheet of every anchor occurrence (`find_by_tag` returns home and reference
   occurrences), plus `sheets_of_unit` for unit anchors.
4. **Route** (two or more tag anchors): from anchor 1 to each other anchor, by `route` mode (§3.2, §3.3). Route
   sheets `R` join the core: `C ← C ∪ R`.
5. **Ring**: the `sheet_hops`-hop neighbours of the anchor sheets in the sheet graph (§3.2), as ring sets
   `H₁ … H_h`.
6. **Budget** (§3.4) over `C` and the rings.
7. **Serialize** with `serialize_graph` on `view.subgraph(...)` (full sheets) or on the through-line node set
   (§3.4); connectors whose partner is outside keep their visible labels (§7 step 5).

### 3.2 `route = "sheet_graph"` (a)

- **Sheet graph** = undirected; an edge for every `continues_as` pair (sheet of `from_key` – sheet of `to_key`)
  **and** for every identity group (home sheet – each reference sheet). Built in `qa/routing.py` from
  `view.edges()` (`continues_as`, `same_tagged_item_as`), **not** from `GraphView.sheet_neighbours`, whose
  documented meaning (`continues_as` only) stays unchanged — so the protocol does not move under the CypherRAG
  coder.
- Route = BFS shortest path from the set of anchor-1 sheets to the nearest sheet of the other anchor; ties by
  sorted sheet id. No path → `trace["route_found"]=False`; `C` keeps the anchor sheets only.

### 3.3 `route = "flow_path"` (b)

- **Weighted directed graph** over occurrences (local keys), built once per corpus:

| Edge in the occurrence graph | Direction followed | Weight |
|---|---|---|
| `send_to` from a non-stub, or into an outgoing stub | forward | 1 |
| `send_to` leaving an incoming stub | forward | 0 |
| `continues_as` (outgoing stub → incoming stub) | forward | 0 |
| `same_tagged_item_as` (reference → home) | both ways | 0 |

  A cut `X → out-stub → in-stub → Y` then costs 1, as the plant edge `X → Y` does, so distances equal plant
  `send_to` hops (the metric FLOW_PATH's gold uses, `families_flow.py`). Signal relations are not followed.
- **Search**: multi-source Dijkstra from every occurrence of anchor 1 to the nearest occurrence of anchor j; ties
  by sorted local key. If no directed path, try anchor j → anchor 1. If neither, use mode (a) for that pair and
  record `trace["route_fallback"]="sheet_graph"` (expected for `NO_PATH` and for branches that meet only upstream).
- **Route sheets** = the sheets of every occurrence on the path. **Through-line** (used by §3.4 b) = for each
  route sheet that is not in the anchor core, the path's occurrences on it (entry stub or reference → items → exit
  stub or reference).
- One anchor: no route, ring only (both modes). Unit anchors: `sheets_of_unit`, no route.

### 3.4 Budget

`L(S)` = the serialized length. The budget is `max_context_chars`.

| Step | `budget="drop_rings"` (a) | `budget="through_line"` (b) |
|---|---|---|
| 1 | drop rings `H_h`, then `H_{h−1}` …, until `L ≤ budget` | same |
| 2 | drop unit-anchor sheets that are neither tag-anchor nor route sheets, highest sheet id first | same |
| 3 | stop; never drop a tag-anchor or route sheet | replace each non-anchor route sheet by its through-line, farthest from both anchors first, until `L ≤ budget` |
| 4 | if still `L > budget`: send anyway, `trace["over_budget"]=True`; the shared fit check (§7 `fit.py`) decides `DID_NOT_FIT` | same |

Step 4 is deliberate: whether compression rescues long routes is the question; hiding an over-budget core behind a
silent cut would answer it wrongly. Through-line needs a flow path; under `route="sheet_graph"` it uses, per
intermediate sheet, the shortest undirected within-sheet path between the stubs or reference occurrences linking it
to its route predecessor and successor (ties by local key).

### 3.5 Parameters (all tuned on dev corpora only)

| Parameter | Values | Set by |
|---|---|---|
| `route` | `"sheet_graph"`, `"flow_path"` | ADR-0030 selection rule on D1000 |
| `budget` | `"drop_rings"`, `"through_line"` | ADR-0030 selection rule on D1000 |
| `sheet_hops` | 0, 1, 2 | the highest value whose D1000 over-budget rate stays at 0 for k ≤ 2; ties → lower |
| `max_context_chars` | int | `ContextWall.max_ok_chars` of the pinned model minus the fixed template overhead (768 characters, PROMPT-04) minus a 5 % margin |
| `fallback_pin` | `ModelPin` | the run's answer pin (no second model) |
| ~~`max_sheets`~~ | removed | the character budget binds; a sheet cap would be a second dial (ADR-0030 item 4) |

### 3.6 Trace (in `RetrievalResult.trace`)

| Key | Type | Meaning |
|---|---|---|
| `routed_sheets` | `list[str]` | every sheet with any content in the context (full or through-line) — read by the built `routing_hit` |
| `through_line_sheets` | `list[str]` | the subset serialized as through-line |
| `serialized_keys` | `list[str]` | local keys of every serialized occurrence (for evidence-node recall) |
| `anchors` | `list[str]` | anchor tags and unit ids as found |
| `route_mode`, `budget_mode` | `str` | the parameters |
| `route_found` | `bool \| None` | `None` with fewer than two tag anchors |
| `route_fallback` | `str \| None` | `"sheet_graph"` when the flow search found no directed path |
| `rings_dropped`, `truncated`, `over_budget` | `int`, `bool`, `bool` | budget outcome; `truncated` = anything dropped or compressed |
| `fallback_used` | `bool` | router fallback (D5) |
| `context_chars` | `int` | as ContextRAG |

### 3.7 Measurement (harness, gold side; strategies never see it)

| Metric | Definition | Families |
|---|---|---|
| **strict routing recall** (built) | `evidence_sheets ⊆ routed_sheets` | all answerable |
| **relaxed routing hit** (new) | some `send_to` path from a source-tag node to a target-tag node of the gold plant lies on nodes drawn on `routed_sheets` (BFS restricted by `SheetIndex.sheets_of`) | `FLOW_PATH`; equals strict elsewhere |
| **evidence-node recall** (new) | share of evidence nodes (gold ids) with at least one occurrence among `serialized_keys`, mapped through `occurrence_map` | all answerable |
| over-budget, truncation, route-fallback, router-fallback rates | from the trace | all |

All are broken down by k-bin and by `u` (ADR-0029). They need no model call: `qa/route_report.py` (§10 H-T4)
computes them for all four combinations by running `retrieve` only.

### 3.8 Comparison protocol (pre-registered here, before ROUTE-01)

1. **ROUTE-01 (free, main session):** the 2×2 on D100, D1000 (dev, seed 1) and H100, H1000 (test, seed 0), each with
   its question set (`--n-per-bin 97`), at `max_context_chars` from the pilot (or, before the pilot, at three fixed
   probe budgets of 100,000 / 200,000 / 400,000 characters, labelled "pre-pilot"; they are probe points, not
   estimates of any model's wall).
2. **Selection** on D1000 only, by ADR-0030's rule. Test-corpus numbers are reported, never used to choose.
3. **Headline:** the chosen pair is "Hierarchical" (C4).
4. **Paid ablation (should, run by the user, paid, needs approval):** all four combinations at H1000 at the floor
   count, under the frozen pin; paired bootstrap per §13.3. Reported as ablation; it never re-selects.

**Reach to note.** AVAIL-01 (H1000, seed 1): powered bins up to 9–16 (359 candidates), 17–32 holds 41, 33+ none.
At ≈16,730 characters per full sheet (PROMPT-04 arithmetic), a 17-sheet route costs ≈ 284,000 characters and a
32-sheet route ≈ 535,000 (arithmetic, not measured). Whether those fit is the pilot's wall, not this note's guess.

### 3.9 Interfaces with the parallel CypherRAG work (QA-T12)

- Hierarchical reads only `GraphView.items()`, `edges()`, `sheets()`, `find_by_tag`, `unit_ids`, `sheets_of_unit`,
  `subgraph` on `NetworkxGraphView` (D9). **No protocol change is needed.** Request to the CypherRAG coder: do not
  change those signatures; adding methods to `GraphView` is fine.
- `qa/harness/registry.py` gains `hierarchical` (H-T2) and `routed` (J-T6) **after** QA-T12 has added
  `cypher_rag`, to avoid a conflicting edit.
- The router arm needs only `CypherRag.name` and a constructor callable from the registry.

## 4. Part B1 — EXP-0004: tag-variant identity with interchangeable deciders

### 4.1 Question

At H100-V and H1000-V, with every reference occurrence's tag written as a variant, what identity P/R/F1 does each
decider reach on the same candidate pairs, at what cost and latency — separately for a variant family that was
tuned on and one that was not?

### 4.2 Variant generator (`benchmark/tag_variants.py`, new)

Generated tags have the form `{prefix}-{unit_no}-{seq}` (`generator.py` `_next_tag`), e.g. `P-7-3`.

| Family | Operator | Example | Grounding |
|---|---|---|---|
| format | `drop_separators` | `P-7-3` → `P73` | OPEN100 `RC-P102A` (no separator before the number) |
| format | `swap_separator` | `P-7-3` → `P 7 3`, `P.7.3`, `P7-3` | ChatP&ID's `SV 104.01` (space and dot styles) |
| format | `zero_pad` | `P-7-3` → `P-07-003` | declared (no source read) |
| format | `case` | `P-7-3` → `p-7-3` | the legacy `_tag_variant` |
| naming | `class_synonym` | `P-7-3` → `PU-7-3`; `E-7-3` → `HX-7-3` | OPEN100 `RCS-PU-102A` vs `RC-P102A` (verified); `CVCS-HX-111` (HX = heat exchanger is our reading, unverified) |
| naming | `unit_prefix` | `P-7-3` → `U7-P-3`, `7-P-3` | OPEN100 system-code prefixes (`RC`/`RCS`, `CND`, `CVCS`) |

- Each variant reference draws one operator (seeded, `random.Random(f"{seed}:{local_key}")`) from the enabled
  families; `variant_rate` of references are varied (EXP-0004: 1.0).
- **Natural hard negatives.** `drop_separators` makes `P-7-31` and `P-73-1` both `P731` (H1000 has 509 units), so
  the format family is not solvable by stripping separators. That is what real dropped separators do.
- `SplitConfig`: `tag_variant_profile: Literal["legacy", "exp0004"] = "legacy"`, `variant_families:
  tuple[str, ...] = ("format", "naming")`, `variant_rate: float = 1.0`. `legacy` keeps `_tag_variant` byte for
  byte (RESOLVE-01 stays reproducible).
- `SplitManifest` gains `variant_family: dict[str, str]` (reference occurrence key → family; gold, never visible),
  so results split by family. `IdentityGroup` is unchanged, because the resolver emits the same class.

### 4.3 Candidates (blocking) — `resolution/identity_candidates.py`

- Over non-connector occurrences of `EQUIPMENT_CLASSES` with a non-empty tag.
- **Key** = `(node_class, digits of the tag with every "0" removed)`; `P-07-003` → `("CentrifugalPump", "73")`,
  `P73` → same. References keep `node_class` exactly (`splitter.py`), so the class is safe to block on.
- Pairs = occurrences sharing a key, on **different sheets**, excluding pairs already joined by exact tag
  (those go straight through, as today).
- **Blocking metrics** (scored against the manifest, eval side): pair completeness (gold links surviving
  blocking ÷ gold links), reduction ratio (1 − candidates ÷ all cross-sheet pairs), candidate count. Revisit
  trigger: completeness < 0.99 on D100-V (ADR-0031).

### 4.4 Pair card (one text, identical for every context-using decider)

```
Occurrence A: tag "P-7-3"; class CentrifugalPump; sheet S041; unit 7; drawn next to: GV-7-12 (sends to), E-7-2 (receives from)
Occurrence B: tag "PU-7-3"; class CentrifugalPump; sheet S042; unit not printed; units on sheet S042: 7; drawn next to: TK-7-1 (sends to)
Sheets S041 and S042 are joined by 3 off-page connectors.
```

Built only from visible properties of localized sheets plus the resolver's own pairs; never `uid`, gold ids, the
manifest or the variant family. Neighbours: 1 hop, at most 6, sorted by tag. A reference has no `unit_id`
(ADR-0026), so its sheet's units are listed instead (one unit per sheet, ADR-0025).

### 4.5 Deciders (`PairDecider` protocol: `decide(pair) -> PairDecision(score: float, accept: bool)`)

| Id | Decider | Input | Threshold | Cost |
|---|---|---|---|---|
| D0 | exact tag (today) | tags | — | free |
| D1 | string: generic normaliser (upper-case, keep alphanumerics, strip leading zeros per digit run) + `difflib.SequenceMatcher` ratio | tags | τ₁ on dev | free |
| D2 | D1 score + context rule: accept iff score ≥ τ₂ **and** (sheets joined by a connector **or** unit printed on A equals a unit on B's sheet) | card fields | τ₂ on dev | free |
| D3 | label-probability chat LLM: card + "Answer with one token: yes or no"; score = P(yes) from `top_logprobs` | card | τ₃ on dev | paid |
| D4 | free-text chat LLM: card + JSON `{"same_item": bool, "reason": str}`; score = 1/0 | card | none | paid |
| D5 | Jev `noul`: `state` = card, question `same_item` = "Do occurrences A and B denote the same physical item?"; score = `noul` | card | τ₅ on dev | paid |

- D1's normaliser is written from this table, **before** any variant is generated, and has no synonym table: a
  synonym list would encode the naming family (circular).
- D3 and D4 use the same pin; the pin must support `logprobs`/`top_logprobs` on OpenRouter (listing
  `supported_parameters`; checked in the pilot). If no pinned model supports them, D3 becomes a constrained
  single-token answer scored 1/0, and the thesis says so.
- D3 vs D5 isolates the typed readout (arXiv 2609.32160's question); D4 vs D3 isolates readout style; D2 vs D1 shows
  what context adds without a model.

### 4.6 Groups and scoring

- Accepted pairs plus exact-tag pairs → union-find components → `IdentityGroup`s; home = most properties, tie by
  sheet id (§5.3, unchanged). A component holding two occurrences on one sheet is **split** by dropping its
  lowest-score accepted links until it holds none; the count is reported (`identity_conflicts`).
- Scored with the built `score_identity_groups` (pairwise, `kg-construction.md` §6), plus pair-level P/R/F1 on the
  candidate set (decider quality without blocking and closure effects).
- Per decider × corpus × family: P, R, F1 [95 % CI, bootstrap over identity groups, seeded], blocking completeness,
  cost (provider-billed), latency (client-side wall clock per call: p50, p95), calls, cache hits.

### 4.7 Protocol (pre-registered here)

1. Corpora: **D100-V** (dev, seed 1), **H100-V**, **H1000-V** (test, seed 0); headline preset with
   `exact_match_tags=False`, `tag_variant_profile="exp0004"`, `variant_rate=1.0`.
2. Tuning: τ₁, τ₂, τ₃, τ₅ maximise F1 on **D100-V generated with `variant_families=("format",)` only**; ties → the
   higher τ (precision first). Prompts and the card format are frozen before any test call.
3. Test: H100-V and H1000-V with both families; every metric split by family. The **naming** family is unseen by
   every decider.
4. Report also the IDBLOCK-01 counts (§10), and the G1 gate result when each decider's groups replace exact grouping
   (`_check_gate`): an end-to-end "does the plant rebuild" per decider.
5. If the candidate count at H1000-V prices the paid deciders out, sample candidates stratified by family and by
   gold label, and report the sampling (ADR-0031 revisit).

### 4.8 Real strings, qualitative only

The three OPEN100 strings (`RCS-PU-102A`, `RC-P102A`, `RC-P100-X001`, `open100-annotation.md` line 90) and the
unverified `CND-HTR-161`/`FWS-HTR-161` pair (line 132) are run through D1, D3, D4, D5 as text-only cards (no
neighbours) and the outputs quoted in the thesis as an illustration. Never a metric: five items, no graphml anchor.

## 5. Part B2 — the router arm (should-tier)

- **`RoutedStrategy`** (`qa/strategies/routed.py`): `name="routed_<decider>"`, holds `{name: Strategy}` for the
  fixed strategies of the run and a `StrategyChooser`. `retrieve(question_text)` → `chooser.choose(text)` →
  `inner[choice].retrieve(text)`; trace adds `router_choice`, `router_scores`, `router_decider`.
- **State** = question text + one fixed corpus line: "The plant has N sheets and M units." Corpus size is a system
  fact the ingest knows, the same for every question, not an evidence field; family, `k` and answer type stay
  unseen (the `Strategy` protocol takes a string only).
- **Criteria** (Jev `choice`) = one neutral line per strategy saying **what it does, not when it wins**, frozen
  before any run, e.g. `context_rag`: "puts the whole plant graph in the prompt"; `cypher_rag`: "writes one
  database query and answers from its rows"; `hierarchical`: "finds the named items and sends only the sheets
  between them".
- **Choosers:** `JevChooser` (`choice`, pinned `jev-1.13`); `ChatLabelProbChooser` (same text, options as letters,
  one token, probabilities from `top_logprobs`); `StaticDevBest` (the fixed strategy with the best dev accuracy at
  the nearest dev size — a scale-aware, question-blind policy; free).
- **No extra answer calls.** A routed question's final prompt equals the chosen fixed strategy's prompt, so it is a
  cache hit from the fixed-strategy run under the same pin. Only router decisions cost.
- **Metrics:** accuracy and cost per question vs every fixed strategy (paired bootstrap, §13.3 machinery); the
  **oracle** (correct if any fixed strategy was correct; cost of the cheapest correct one), computed from the fixed
  runs' `answers.jsonl` with no call; regret = oracle − routed; choice distribution per corpus size and k-bin.
- **Position** (novelty log 2026-10-02): GraphRAG-Router (arXiv 2604.16401) routes per query over GraphRAG methods
  and LLMs with an RL-trained router on Wikipedia QA. Ours is zero-shot, over strategies whose optimum is claimed to
  change with plant scale, on P&IDs; cite it as the closest work.
- **Not in scope:** choosing the answering model per question (ADR-0014 point 4; ADR-0032 option D). Jev as
  Hierarchical's unit-router fallback (D5): up to 509 units at H1000 as `choice` criteria, with no documented limit
  on criteria count — not designed.

## 6. Jev client, cache and guard (`llm/systemone.py`, `llm/decision_models.py`, `llm/decision_cache.py`)

```python
class DecisionPin(BaseModel):            # frozen
    backend: Literal["openrouter_systemone"]
    model_id: Literal["jev-1.13"]        # validator refuses "jev-latest" and "typesafe/jev-router"
    expected_resolved_model: str | None  # frozen from the first live response, e.g. "typesafe/jev-1.13-20260917"

class NoulQuestion(BaseModel):   type: Literal["noul"]; instructions: str
class ChoiceQuestion(BaseModel): type: Literal["choice"]; instructions: str; criteria: dict[str, str]

class DecisionRequest(BaseModel):        # frozen; no credential field
    pin: DecisionPin; state: str
    questions: dict[str, NoulQuestion | ChoiceQuestion]
    purpose: Literal["identity_decide", "route"]

class DecisionResponse(BaseModel):
    answers: dict[str, float | str]      # noul -> probability; choice -> criterion key
    resolved_model: str; provider_response_id: str | None
    input_tokens: int; output_tokens: int; cost_usd: float | None
    latency_s: float                     # client-side wall clock; the endpoint reports none
    from_cache: bool; created_at: datetime
```

- **Transport:** `POST {base_url}/systemone` with `Authorization: Bearer <key>`, reusing `OpenRouterSettings`;
  `httpx2` directly (the OpenAI SDK has no such endpoint).
- **Guard:** same as `ChatClient` — `allow_network` only from `--allow-paid-calls`; a cache miss without it raises
  `CacheMiss`; transport-only retries; `_redact` on every error text; one `CallRecord`-shaped line per call in
  `calls.jsonl` (a `DecisionCallRecord` with the same fields).
- **Cache:** `data/llm-cache/decisions.sqlite`, `live`/`replay`, key = `canonical_hash` of `pin`, `state`,
  `questions` (not `purpose`, as in ADR-0014's chat key). A separate file leaves the chat cache's keys untouched.
- **Parsing:** `noul` as documented (`{"type": "noul", "noul": 0.98}`). `choice`: **unknown shape**; the parser
  accepts only the shape the paid smoke records (§10 J-P1) and otherwise raises `ProviderError`.
- **Resolved-id check:** a live response whose `model` differs from `expected_resolved_model` raises
  `ProviderError`.
- **Chat log-probabilities (for D3 and `ChatLabelProbChooser`):** `ChatRequest.top_logprobs: int | None = None`;
  `ChatResponse.top_logprobs: list[dict[str, float]] | None = None`. The cache key adds the field **only when not
  `None`**, so every existing chat key is unchanged (tested).

**Reproducibility and threats** (stated in the thesis): pinned `jev-1.13` with the resolved dated id; call dates in
`calls.jsonl`; every decision cached and replayable; determinism unknown → repeatability probe (J-P2); vendor
dependence (withdrawal stops extension, not replay); possibly subsidised price (vendor's words) → cost reported as
billed with the date; vendor latency and price claims are quoted as claims and compared with our measurement.

## 7. Novelty (`10-literature/_novelty-log.md`, 2026-10-02 entry)

- **Verdict: claim still open.** No Jev × P&ID / DEXPI / engineering-drawing work; no new multi-sheet P&ID GraphRAG
  paper since 2026-09-26.
- **"Using Jev" is not novel by itself.** arXiv 2609.32160 (Tang, Zheng) audits 28 papers from Jev's first days: the
  typed readout shows no independent accuracy advantage over comparable label-probability readouts; the gains are
  latency and cost. Its **14-item evaluation checklist** is to be followed; the items are not yet transcribed here —
  `/paper-intake 2609.32160` is owed before J-T5 starts, and this note gains a checklist-to-design table then.
- arXiv 2609.37647 benchmarks jev-1.13.0 on 37 datasets (346,009 requests): general benchmark, no drawings.
- arXiv 2604.16401 (GraphRAG-Router): per-query routing over GraphRAG methods + LLMs, RL-trained, Wikipedia QA.
- **Defensible novelty:** the domain and the measurement — cross-sheet equipment-tag identity on P&IDs with a
  generated answer key, and routing whose optimum changes with plant scale.

## 8. Files

| File | New / changed | Holds |
|---|---|---|
| `src/plantgraph/qa/routing.py` | new | sheet graph with identity links; flow graph and weighted search; through-line extraction; anchor extraction |
| `src/plantgraph/qa/strategies/hierarchical.py` | new | `Hierarchical` (§3.1–§3.6) |
| `src/plantgraph/qa/harness/gold.py`, `runner.py`, `summary.py` | changed | relaxed routing hit, evidence-node recall, rates |
| `src/plantgraph/qa/route_report.py` | new | free 2×2 report (ROUTE-01) |
| `src/plantgraph/benchmark/tag_variants.py`, `split_models.py`, `splitter.py`, `models.py` | new / changed | variant operators, config fields, `SplitManifest.variant_family` |
| `src/plantgraph/resolution/identity_candidates.py`, `identity_decide.py` | new | blocking, pair card, `PairDecider`, D0–D2, grouping |
| `src/plantgraph/llm/decision_models.py`, `decision_cache.py`, `systemone.py`, `fake_systemone.py` | new | §6 |
| `src/plantgraph/llm/models.py`, `client.py`, `cache.py` | changed | `top_logprobs` |
| `src/plantgraph/exp0004/` (`__main__.py`, `deciders.py`, `runner.py`, `report.py`) | new | D3–D5, tuning, scoring, CLI |
| `src/plantgraph/qa/strategies/routed.py`, `qa/router_report.py` | new | router arm, oracle, static policy |

`resolution/` imports nothing from `llm/` (the import-ban test is extended to say so).

## 9. Testing (every coder acceptance offline: fake transports, replay cache, no network)

| Component | Tests |
|---|---|
| sheet graph | a toy where two sheets touch only by an identity group: `a_cont`-style graph has 2 components, ours 1 |
| flow route | a hand-built 4-sheet toy: weights give plant-hop distances; a back-and-forth path (k = 4 over 2 sheets) is found whole; reverse direction used when forward fails; `NO_PATH` toy falls back and records it |
| through-line | intermediate sheets serialize only path occurrences; anchor sheets whole; the result is deterministic |
| budget | ring dropping order; over-budget core sent with `over_budget=True`; through-line applied farthest-first |
| Hierarchical | §18 T13's checks (tags with a space, `piping_component_name`, EX01-shaped corpus without `unit_id`, fallback counted) plus all trace keys present |
| harness metrics | relaxed hit true for an alternative valid path, false for a broken one; evidence-node recall on a toy with a duplicated item |
| variants | each operator on fixed inputs; `legacy` byte-identical manifest to today (golden hash); hard-negative collision exists on a 2-unit toy (`P-7-31` / `P-73-1` style) |
| blocking | completeness 1.0 and the expected pair count on a toy; same-sheet pairs excluded |
| deciders | D1/D2 table cases; union-find split of a same-sheet conflict; D3–D5 with scripted fakes |
| Jev client | scripted `noul`; unknown `choice` shape → `ProviderError`; resolved-id mismatch → `ProviderError`; `allow_network=False` miss → `CacheMiss`, zero requests; key hygiene as `qa-system.md` §16; pin validator refuses `jev-latest` |
| chat log-probs | existing chat cache keys unchanged (fixture of 3 keys) |
| router | a scripted chooser routes; final prompt equals the fixed strategy's (cache hit in a toy run); oracle and regret on a synthetic `answers.jsonl` |

## 10. Ordered coder tasks (one Sonnet coder at a time; each ends green on ruff, mypy --strict, pytest, offline)

| # | Task | Depends on | Size (estimate) |
|---|---|---|---|
| **H-T1** | `qa/routing.py`: sheet graph with identity links, flow graph + weighted search with reverse and fallback, through-line extraction, anchor extraction (§3.1–§3.3) | — | M |
| **H-T2** | `strategies/hierarchical.py` + budget modes + trace + registry entry + router fallback via `ChatClient` (fake) (§3.4–§3.6) | H-T1, **QA-T12 merged** (registry) | M |
| **H-T3** | harness: relaxed routing hit, evidence-node recall, rates in `summary.py`; D1000 dev-corpus recipe in the corpus docs (§3.7) | H-T2 | S |
| **H-T4** | `qa/route_report.py`: the free 2×2 over a corpus and its question set, retrieve only → CSV + markdown (§3.8) | H-T3 | S |
| — | *Main session: **ROUTE-01** on D100, D1000, H100, H1000 (free); apply ADR-0030's selection rule; `_results.md` row* | H-T4 | minutes |
| **J-T1** | `llm/decision_models.py`, `decision_cache.py`, `systemone.py`, `fake_systemone.py`; `top_logprobs` on the chat path; `--live-llm` smoke test for System One (§6) | — | M |
| — | ***J-P1:** System One smoke (one `noul`, one `choice`) — **run by the user, paid, needs approval**; records the `choice` shape and the resolved id* | J-T1 | one call each |
| **J-T2** | `benchmark/tag_variants.py` + `SplitConfig` fields + `SplitManifest.variant_family`; `legacy` unchanged (§4.2) | — | M |
| **J-T3** | `resolution/identity_candidates.py`, `identity_decide.py`: blocking, card, D0–D2, grouping, blocking metrics (§4.3–§4.6) | J-T2 | M |
| — | *Main session: **IDBLOCK-01** (free): candidate counts, completeness, reduction ratio on D100-V, H100-V, H1000-V; D0–D2 scores* | J-T3 | minutes |
| **J-T4** | `exp0004/`: D3–D5, threshold tuning on dev (format family), scoring, report, CLI with `--allow-paid-calls` (§4.5–§4.7) | J-T1 (+ J-P1 for the `choice` parser only), J-T3 | M |
| — | ***J-P2:** Jev repeatability probe (a few hundred `noul` decisions asked twice, cache bypassed) — **run by the user, paid, needs approval*** | J-T4 | — |
| — | ***J-P3:** EXP-0004 dev tuning on D100-V (D3–D5) — **run by the user, paid, needs approval*** | J-T4, pilot pin (ADR-0019) for D3/D4 | — |
| — | ***J-P4:** EXP-0004 test on H100-V, H1000-V — **run by the user, paid, needs approval*** | J-P3 | — |
| — | *Owed before J-T5: `/paper-intake 2609.32160`; checklist table added to §7* | — | — |
| **J-T5** | `qa/strategies/routed.py` + `JevChooser`, `ChatLabelProbChooser`, `StaticDevBest`; `qa/router_report.py` (oracle, regret); registry entry (§5) | J-T1, H-T2, QA-T12 | M |
| — | ***J-P5:** paid ablation of Hierarchical's 2×2 at H1000 (should) — **run by the user, paid, needs approval*** | headline pin, H-T4 | — |
| — | ***J-P6:** router run on H100, H1000 after the fixed-strategy runs (should) — **run by the user, paid, needs approval*** | J-T5, fixed runs | — |

S < ~150 changed lines including tests; M ~150–400. Estimates.

**Order rationale.** H-T1…H-T4 first: QA-T13 is a must (C4), and ROUTE-01 is a free partial result. J-T1 next,
because J-P1 (the user's smoke) unblocks the `choice` parser while J-T2/J-T3 proceed. The router (J-T5) is last:
it needs the fixed-strategy runs.

## 11. ADRs proposed

- **ADR-0030** — Hierarchical's two routing and two over-budget modes, chosen by a pre-registered free measurement on
  D1000.
- **ADR-0031** — EXP-0004 as blocking + interchangeable deciders, naming family held out.
- **ADR-0032** — Jev pinned to `jev-1.13` as a measured decider and router; never `jev-router`/`jev-latest`, never the
  answer model.

On acceptance the main session updates: `qa-system.md` §7 (steps 3–4, parameter row), §17 (two metrics), §18 T13
(points to H-T1…H-T4); `kg-construction.md` §5.3 (pointer to ADR-0031); `00-index.md`.

## 12. Open questions

1. **User — router tier.** Should-item after the headline (recommended), or must? It adds no answer calls, only
   router decisions.
2. **User — corpus line in the router state.** Recommended (it lets the router use scale, which is the claim).
   Without it, the router can only use question wording.
3. **User — `variant_rate = 1.0`.** Every reference varied is the cleanest decider comparison; the real frequency is
   unknown (ADR-0028). A 0.5 sensitivity at H100-V is a cheap should-item.
4. **Pilot.** Does the pinned chat model support `top_logprobs` on OpenRouter? If not, D3 degrades as §4.5 says.
5. **J-P1.** The `choice` answer shape, and whether `criteria` has a count limit.
6. **Researcher.** Citations owed: blocking metrics (pair completeness, reduction ratio) and pairwise ER scoring
   (Menestrina et al., VLDB 2010 is a candidate, not read — `kg-construction.md` §6).

## 13. Figures in this note and their sources

| Figure | Source |
|---|---|
| H100/H1000 sheet-graph components, routing found/strict/relaxed, route sheets, context characters | architect probe 2026-10-02 (§2 method; scratchpad `route_probe.py`, `throughline_probe.py`); re-measured by ROUTE-01 |
| RESOLVE-01 identity recall 0.125 / 0.0 / 0.0 | `30-experiments/_results.md` |
| AVAIL-01 bins (H1000 9–16: 359; 17–32: 41), build 75.5 s | `_results.md` AVAIL-01 rows |
| 16,746,349 characters / 1,001 sheets; 768-character template overhead | `_results.md` PROMPT-04 |
| 14.44 equipment per sheet; 1,001 sheets | `_results.md` SMOKE-07 |
| 614 identity groups / 750 references at H1000 | `_results.md` SMOKE-04b |
| ≈16,730 characters per sheet; ≈284,000 / ≈535,000 characters for 17 / 32 sheets; ≈1.0 × 10⁸ all-pairs | arithmetic on the rows above |
| Jev facts: release date, request shape, endpoint, model ids, vendor claims | emergent.sh/news/what-is-jev and openrouter.ai/docs/guides/community/typesafe-sdk, gathered 2026-10-02 (brief); example response with `typesafe/jev-1.13-20260917`, no seed/temperature, no latency, `choice` response shape absent: same docs page, read by the architect 2026-10-02 |
| `typesafe/jev-router` price −1, adaptive | `30-experiments/openrouter-models-2026-10-02.json` |
| Novelty verdict, 2609.32160, 2609.37647, 2604.16401 | `10-literature/_novelty-log.md` 2026-10-02 |
| OPEN100 tag strings | `40-design/open100-annotation.md` lines 85–132 |
| Tag format `{prefix}-{unit_no}-{seq}`; class prefixes | `benchmark/generator.py` `_next_tag`; `graph/schema.py` `CLASS_SPECS` |
