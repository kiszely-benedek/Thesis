---
design: Demo upgrade from v1 (cascade_v3 on D100 / D1000) to the v2 system V2T-A (cascade_v4_iso on H100g2 / H1000g2)
date: 2026-11-05
status: proposed (with ADR-0064)
amends: 40-design/demo-app.md (accepted with ADR-0049) §5.2 "the demo refuses a label-routing policy", §6 config, §7 results
adrs: ADR-0049 (accepted, amended in part by ADR-0064), ADR-0056 (point 2 amended in part), ADR-0061 (V2T-A), ADR-0053 / ADR-0062 (R5), ADR-0063 (E8 freeze), ADR-0064 (proposed)
---

# Demo v2: the frozen V2T-A, live, on the sealed v2 plants

All facts below were read from the repository or computed with free, read-only Python on 2026-11-05 (architect
scratch; no Neo4j access, no model call, no write outside `docs/`). Line numbers refer to HEAD `c6099fc`.

## 0. Recommendation

1. **The freeze can be kept, but not by configuration alone.** The frozen live cascade refuses `cascade_v4_iso`
   outright because the policy routes by need label (§2.1). The fix is a **demo-side need router** that reproduces
   the policy's routing with two label-free derived policies, each run by the unchanged frozen `LiveCascade`. Every
   change lives in `src/plantgraph/demo/**`, `tests/test_demo_*` and a new `data/runs/exp0007/demo/` (ADR-0064 §1).
2. **Show the two sealed test plants, H1000g2 (main) and H100g2 (small)**: the plants the thesis's headline numbers
   were measured on, with R5's recorded answers next to every example (ADR-0064 §2). v1 plants leave the v2 demo.
3. **Results tab: v2 only** — R4 ladder (all-families scope), R5 headline and held-out with Wilson intervals, the F1
   cascade as the "before" bar, and an INFRA-2 table. R4/R5/F1 JSON already fits the existing readers' shapes; only
   the hard-coded scope and policy filters and the front-end names are v1-bound (§4).
4. **Seven coder tasks (3 S, 4 M)**, one Sonnet coder at a time, all offline-tested (§7). Then free checks, then a
   paid smoke of 6 questions (expected ≈ $0.015, cap $0.25) only with the user's approval.

## 1. What is v1-bound (question 1)

### 1.1 Bound to v1 — must change

| # | Item | Evidence | v1 assumption | v2 change | Task |
|---|---|---|---|---|---|
| B1 | Live policy | `qa/cascade/live.py:157-163`, called first in `live_build.py:165` | a live policy has no `start_tier_by_label` | `cascade_v4_iso.json` has `start_tier_by_label` {UPSTREAM/DOWNSTREAM_TO_FIRST_VALVE: 1} → demo-side router (§2) | T1, T2 |
| B2 | Policy name in config | `data/runs/cv1/demo/demo_config.json` `"policy": "cascade_v3"`; `config.py:146-156` resolves names only in `POLICIES_DIR` (v1 folder) | shipped name | give the path `src/plantgraph/qa/cascade/policies_v2t/cascade_v4_iso.json` (already supported, `config.py:152-153`) | T7 |
| B3 | Tier sources | config `tier_runs` = `cv1/runs/CYPL2-*`, `AGL3-*`; tier names `cypher-luna`, `agent-luna` | v1 tiers | `cypher-v2t` → `data/runs/exp0007/sealed/runs/S7-CYP-<c>`, `agent-v2t` → `S7-AG-<c>`. Verified today: `load_tier_from_run` (`live_build.py:96-117`) accepts all four, params equal the frozen inputs (`{"timeout_s": 30, "row_cap": 1000}`, agent `max_steps 40, step_effort low, …`) | T7 |
| B4 | Ingest / store profile | `corpus_runtime.py:83-84` builds view and load plan from one `ingest.json`; `live_build.py:127` checks `PROFILE_OF_NAME[strategy]`; `cypher_rag.py:108-112` maps `cypher_rag_lines` → `plant_lines` | v1 `neo4jplant/D*/ingest.json` (`plant`) | use `data/runs/exp0007/sealed/neo4jplant/<c>/ingest.json` (`store_profile: plant_lines`, H1000g2: 1,000 sheets, 91,789 nodes, 308,283 relationships, its `counts`) | T7 |
| B5 | Results config | `config.py:46-54`: one `ladder_report`, one `sealed_report`, defaults `EXP-0001-LADDER`, `EXP-0002-H100, EXP-0002-H1000` | one report of each kind | list of sealed sources, ladder scope, optional infra source (§4) | T3 |
| B6 | Ladder scope | `results.py:56` `Literal["common"]`, filter `results.py:201` | the claim's scope is `common` | R4 is reported on **all** families (`_results.md:12`), so the scope must be configurable | T3 |
| B7 | Sealed policy filter | `results.py:156-157` `SEALED_POLICIES = ("cascade_v3", "always_g_luna", "always_c_luna")`; scope `headline` only, `results.py:235` | v1 policy names | R5 names are `cascade_v4_iso`, `always_g_v2t`, `always_c_v2t`; with the v1 filter the R5 view would be **empty**; add `held-out` | T3 |
| B8 | Results front end | `static/results_data.js:9-20` (`ARM_ORDER`, `ARM_STYLE`, `ARM_OF_POLICY`, `POLICY_ORDER`); `static/strings.js:97-108` (`armNames`, `armNotes`), `:130` (`policyNames`) | v1 arm and policy names | v2 names, F1 as a distinct series, held-out chart, infra table | T4 |
| B9 | "How it works" text | `static/strings.js:254-262` | Cypher step, then agent on failure | add the `complete` rule (Cypher result not cut) and the need routing (isolation questions start at the agent) | T4 |
| B10 | Label table | `static/labels.en.json:19-28` tiers / strategies only v1; `class_names` has 14 entries vs 98 vocabulary classes (computed today: 84 missing, e.g. `AngleBallValve`, `Agitator`) | v1 vocabulary | add `cypher-v2t`, `agent-v2t`, `cypher_rag_lines`, `graph_agent_lines`, 98 class names, glossary terms (need routing, spare A/B) | T5 |
| B11 | Example files | `cv1/demo/examples/D1000.jsonl` (rule "per-family 2, seed 20261011", its provenance file) | v1 question files | regenerate with the same tool from the R5 question files (§5) | T7 |
| B12 | Presentation sequences | config `presentation` names v1 ids (`D1000:LOOKUP_TYPE:V-361-5`, …) | v1 ids | new sequences on H1000g2 / H100g2 (§5.2) | T7 |
| B13 | Drawings | only `cv1/drawings/D100`, `D1000` exist (`find … drawings.index.json`) | — | export H100g2 and H1000g2 (code already v2-aware, §1.2) | T7 |
| B14 | Shipped example config | `demo/app/demo_config.example.json:2-37` | v1 paths | v2 paths; keep a v1 example beside it | T7 |

Name trap: `data/runs/cv1/demo/demo_config.v2.json` already exists and is an **old cascade_v2 config** (policy
`cascade_v2`, tiers `cypher-low`, `agent-low-steps`), not generator v2. The new config goes to
`data/runs/exp0007/demo/demo_config.json`; the old file is left alone.

### 1.2 Works unchanged with v2 corpora

- **Drawing export.** It picks the ISO glyph style when a sheet holds a class beyond v1's (`drawing/export.py:65-68`),
  draws all 98 vocabulary classes (commit `3181573`, 2026-10-27, after the v2 vocabulary `a24630c`, 2026-10-25), and
  `tests/test_demo_glyphs_v2.py:1` lays out and renders a 10-sheet v2 corpus. The self-check `_check_against_corpus`
  (`export.py:54`, `:89`) refuses a drawing that misses symbols, flags or lines. **Not yet run on a 1,000-sheet v2
  plant** (time and PDF size unmeasured; free check F3).
- **Tags: ISA style, A/B spares, unit-prefixed numbers.** The tag lookup is a sorted prefix index with no tag
  pattern (`tag_lookup.py:24-36`); answer text matches the plant's own tags longest-first with letter/digit/hyphen
  guards, so `P-9001` is not found inside `P-9001B` (`static/tagtext.js:8-15`); evidence words use a generic pattern
  (`evidence.py:19`). Example tags in R5: `P-9001B`, `LSHH-1006`, `BFV-577002`, `TK-23602`.
- **Question families.** `family_topics` covers every `QuestionFamily`, asserted by `tests/test_demo_labels.py:58`;
  all 23 R5 families have a topic.
- **Graph view.** The demo builds `NetworkxGraphView(corpus_id, localized_sheets, resolution)`
  (`corpus_runtime.py:84`), the same call as the harness (`qa/harness/runner.py:207`).
- **Store probe and plant switch.** Profile-generic (`store_probe.py:82-88`, `store_loader.py:44-57`); the
  `DrawingSet.corpus_id` probe (`store_probe.py:53`) works for any corpus id.
- **Cost estimate and cap.** `estimate.py:28-37` reads per-tier costs from the configured tier runs under the tier's
  pin; with R5 runs it gives figures without code change (§6).
- **Examples tool.** `examples.py:76-91` (`--per-family N --seed S`) works on any `questions.jsonl`.
- **Live-only guard.** The per-ask cache emptying (`live_cascades.py:181-187`, `:230-238`) and
  `allow_paid_calls=True` (`live_cascades.py:222`) are policy-independent.

## 2. The freeze (question 2)

### 2.1 The problem

`open_live_cascade` calls `refuse_label_routing(policy)` before anything else (`live_build.py:165`), and
`LiveCascade.__init__` checks it again (`live.py:76`, `:176-178`). Run today on the frozen policy file:

```
REFUSED: expected a policy without label routing (a free-text question has no need label), found start/last_tier_by_label in 'cascade_v4_iso'
```

ADR-0049 recorded this as intended ("the demo refuses a label-routing policy", ADR-0049:109). V2T-A is
`cascade_v4_iso` (ADR-0061; `tune_select.py:23`, `:39`), and its only difference from `cascade_v4` is exactly that
routing (`policies_v2t/cascade_v4.json` vs `cascade_v4_iso.json`). Both live files are frozen (`tune_lib.sh:105`
lists `src/plantgraph/qa/cascade`; `E8.sha256` hashes `live.py`, `live_build.py`).

### 2.2 How R5 routed, and why a demo-side router is exact

- **Where the label came from.** R5's report resolves a label per question from a run trace, else from the rules
  classifier on the question text and the tags/units found in it (`qa/cascade/join.py:121-140`,
  `qa/cascade/report.py:102-111`, `:259`; invoked with `--corpora-root` in `run_sealed.sh:116-119`). Neither V2T-A
  tier writes a `need_label` into its trace (only `hierarchical_need.py:199` does), so every R5 label came from
  `classify_need(text, anchor_finder(view))` (`qa/cascade/labels.py:25-33`). The rules are free and deterministic
  (`labels.py:3-5`). Isolation is matched by wording: `\bisolat\w*\b.*\bupstream\b` and `…downstream\b`
  (`qa/need/rules.py:53-54`). So "To isolate P-8101B from all upstream equipment…" is routed, while the
  DOWNSTREAM_ISOLATION template "To cut P-6304 off from all downstream equipment…" is not — the live router must
  give the same result, which it does if it calls the same function.
- **The walk.** `start_index` = `start_tier_by_label.get(label, 0)` (`accept.py:66-74`); the walk runs
  `tiers[first : last+1]` (`accept.py:106-107`); the fallback goes to `policy.tiers[0]` only if it was tried
  (`policy.py:73-80`).
- **Derived policies.** For each start index `s` used by the policy (here 0 and 1) build in memory
  `policy.model_copy(update={"tiers": policy.tiers[s:], "start_tier_by_label": {}, "fallback_to_first_answer":
  policy.fallback_to_first_answer if s == 0 else False})`. Then for every label and every signal combination:
  - `s = 0`: same tiers, same rules, same fallback → identical walk and decision.
  - `s > 0`: same tiers tried, same acceptance; the original never falls back (tier 0 not tried, `policy.py:78`),
    the derived one has fallback off → identical `answered_by`, `tiers_tried`, cost, latency.
  - `last_tier_by_label` is empty in `cascade_v4_iso`; the router refuses a policy that sets it (out of scope).
- The derived policies have no label routing, so the frozen `refuse_label_routing` accepts them (run today:
  "derived no-route OK"), and the frozen `LiveCascade` runs them unchanged. They keep the name `cascade_v4_iso`; the
  frozen code still marks a run with a dropped Cypher tier as derived (`live_build.py:181-185`, `live.py:141-142`).

### 2.3 Changes and freeze compliance

Every change is in `src/plantgraph/demo/**`, `tests/test_demo_*.py`, and new data under `data/runs/exp0007/demo/`.
- `V2T_FROZEN_FILES` (`data/runs/exp0007/tune_lib.sh:102-121`) lists no `src/plantgraph/demo` path; `$IN` is
  `data/runs/exp0007/inputs` only (`lib.sh:11`).
- `E8.sha256` (308 lines) holds **zero** `demo` paths (`grep -c demo` = 0) and no `data/runs/exp0007/demo` path.
- The demo only *calls* frozen code: `open_live_cascade`, `load_tier_from_run`, `classify_need`, `anchor_finder`,
  and in tests `walk_question` / `decide`.
- Check after every commit: `git diff --quiet $(cat data/runs/exp0004/E8.commit) -- $V2T_FROZEN_FILES
  data/runs/exp0007/inputs` and `sha256sum -c --quiet data/runs/exp0004/E8.sha256` (free, seconds).

**Freeze gap found (no action on frozen paths).** The classifier that decides V2T-A's routing — `src/plantgraph/qa/need/`
and `src/plantgraph/qa/anchors.py` — is **not** in `V2T_FROZEN_FILES` and not hashed in `E7.sha256` / `E8.sha256`
(`grep -c` = 0 in both). It is unchanged since E7 (`git diff fdad31f HEAD -- src/plantgraph/qa/need
src/plantgraph/qa/anchors.py` empty, no working-tree change), so R5 is not affected. The demo's agreement check (T6)
records that diff each time it runs; the thesis should list these files with the frozen system. A future freeze
should add them; changing `tune_lib.sh` now is not proposed.

**Known live-vs-offline difference (pre-existing in v1, not a freeze breach).** Live, the agent after a Cypher
tier gets C minus the Cypher latency (`live.py:97-113`) and reads its remaining time before each step
(`qa/harness/attempt.py:85-91`); offline, the R5 agent row ran with the full 120 s and the join cut it afterwards.
A question that escalates may therefore stop earlier live. Routed questions start at the agent with the full C, as
offline. T6 measures the effect on replays.

## 3. Which plant (question 3)

| Option | For | Against |
|---|---|---|
| **A. H1000g2 + H100g2, the sealed test plants (recommended)** | the plants R5's 0.891 / 0.911 were measured on; tier runs, recorded answers and cost evidence on the same plant (`estimate.py:71` prefers own-corpus runs); `plant_lines` ingest ready (`sealed/neo4jplant/<c>/ingest.json`) | the sealed questions become public; the thesis must say so (below) |
| B. Validation plant X1000g2s213 (dev, run once in V2T-VAL) | not a test plant | only 163 dev-family questions; its `neo4jplant` ingest has profile `plant` (computed today), so a new `plant_lines` ingest is needed; no R5 numbers on it |
| C. A fresh dev plant (e.g. D1000g2 from the dev seed) | untouched | new ingest (INFRA-2: build total 456.2 s at 1,000 sheets), no questions or recorded runs; the demo would not show the plant the numbers come from |

**What the thesis should state.** The demo shows the sealed test plants after the sealed test ran (R5, 2026-10-31,
`_results.md:9`), on the frozen V2T-A (E7 `fdad31f`, re-identified E8 `4dfad69`); no system file changed for the
demo. Live demo answers are new model calls, not measurements; they do not change R5's numbers. Once shown, the
sealed questions are spent: any later system change needs a new sealed set (ADR-0053's rule).

**Neo4j.** The demo's plant switch wipes the other plants and loads the chosen one (`store_loader.py:44-57`), so the
one-plant rule holds by construction. H1000g2's recorded load stage is 29.86 s (`stage_seconds.load_total` in its
ingest record). Recommended end state of the user's `neo4j` database: **H1000g2** (`plant_lines`), replacing v1
D1000; this changes the standing rule "end on D1000" and needs the user's yes. The temporary database `e7tune` stays
for experiment scripts (EXP-0004's end-to-end arm); do not run the demo during a paid EXP-0004 stage (shared
Neo4j server, Cypher timings).

## 4. Results tab (question 4)

| View | Source (exists) | Shape | Reader today | Needed |
|---|---|---|---|---|
| R4 ladder | `data/runs/exp0007/ladder/report/report.json` | same keys as EXP-0001's (`cutoff_s, sizes, scope_families, cells, absent, wall_sheets`, computed today) | `ladder_view`, but scope fixed to `common` | config `scope: "all"`; arm `cascade_v4_iso` in the front end |
| R5 sealed | `data/runs/exp0007/sealed/report/report.json` | same as v1 sealed (`sealed.sheets`, `sealed.scope_rows`) | `sealed_view`, but v1 policy filter and `headline` only | config `policies`, `scopes` |
| F1 baseline | `data/runs/exp0007/sealed/report_f1_baseline/report.json` | same | policies are the v1 names, so it would read today | a second sealed source, `cascade_v3` only, labelled "F1, previous system" |
| INFRA-2 | `data/runs/exp0007/infra/report.json` | `growth`: list of `{name, from_corpus, to_corpus, from_value, to_value}` | none | small adapter: configured `growth` names → table rows, unit from the suffix (`_bytes`, `_s`, `usd`) |

Numbers the tab would show (all read from those files today):

| | H100g2 headline (n 440) | H1000g2 headline (n 440) | H100g2 held-out (n 100) | H1000g2 held-out (n 100) |
|---|---|---|---|---|
| V2T-A cascade_v4_iso | 401, 0.911 [0.881, 0.934] | 392, 0.891 [0.858, 0.917] | 77, 0.770 [0.678, 0.842] | 74, 0.740 [0.646, 0.816] |
| agent only (always_g_v2t) | 0.909 [0.879, 0.933] | 0.870 [0.836, 0.899] | 0.770 | 0.690 |
| Cypher only (always_c_v2t) | 0.809 [0.770, 0.843] | 0.795 [0.755, 0.831] | 0.640 | 0.600 |
| F1 cascade_v3 | 382, 0.868 [0.833, 0.897] | 366, 0.832 [0.794, 0.864] | 0.760 | 0.720 |
| V2T-A $/question, median / p90 s | 0.00137, 7.13 / 37.99 | 0.00148, 7.50 / 40.79 | 0.00225 | 0.00248 |

R4 all families, cascade_v4_iso: 67/70 0.957, 69/78 0.885, 80/88 0.909, 85/92 0.924 at 1 / 3 / 11 / 30 sheets;
ContextRAG high 0.686 / 0.654 / 0.614 at 1 / 3 / 11; agent tier 0.957 / 0.936 / 0.943 / 0.935; context wall 62.1
sheets (`ladder/report/report.json`, matches `_results.md:12`). INFRA-2 rows (from `growth`): H100g2 → H1000g2
store data 6,555,316 → 58,066,741 B; ingest build total 11.3 → 456.2 s; startup total 6.07 → 408.34 s, without
rebuild 0.45 → 5.31 s; app peak 346,423,296 → 1,803,264,000 B; Neo4j RSS 1,331,228,672 → 1,436,479,488 B; Cypher
database-only median 0.039 → 0.070 s.

Captions must stay honest: on R4 the agent alone is above the cascade at 3–30 sheets with overlapping intervals
(`_results.md:12`); V2T-A minus F1 (+0.043 / +0.059) is descriptive, unpaired, without an interval (`_results.md:11`).
Captions state rules, never typed-in numbers (`results.py:3-5`).

## 5. Example questions and presentation (question 5)

### 5.1 Examples

Source: the R5 question files `data/runs/exp0007/sealed/questions/<c>/questions.jsonl` (560 questions each, 23
families, 20 or 30 per family, computed today). Their template text is already English and is used **as written**
— no wording file, no rewording (user rule: natural questions only). Command per plant, with the v1 precedent's
rule (`D1000.jsonl.provenance.json`: "per-family 2, seed 20261011"):

```
python -m plantgraph.demo.app examples --from data/runs/exp0007/sealed/questions/H1000g2/questions.jsonl \
  --corpus H1000g2 --per-family 2 --seed 20261105 --out data/runs/exp0007/demo/examples/H1000g2.jsonl
```

→ 46 examples per plant, each with its provenance sidecar (`examples.py:136-145`). `recorded_runs` = `S7-CYP-<c>`,
`S7-AG-<c>`, `S7F1-CYP-<c>`, `S7F1-AG-<c>`, so each example shows how V2T-A's tiers and F1 answered it in R5.

### 5.2 Presentation sequences (config only)

Rule, declared so it is not chosen on outcome: in each sequence, for each named family, the **first** example of
that family in the seeded examples file.

- **H1000g2 — "A 1,000-sheet plant: lookup, a route across sheets, isolation, a control loop, an unknown tag"**:
  LOOKUP_TYPE, FLOW_PATH, UPSTREAM_ISOLATION (shows the need routing: starts at the agent), LOOP_ACTUATED_VALVE,
  UNANSWERABLE_TAG (abstention), results.
- **H100g2 — "A 100-sheet plant: spares and a held-out question"**: SAME_UNIT, ROUTE_AVOIDING (held-out family),
  results.

The ids are filled in after T7 writes the examples files.

## 6. Paid calls (question 6)

Computed today with the demo's own `estimate_cost` (`estimate.py:28-37`) on the R5 tier runs, cascade_v4_iso tiers:

| Plant | Cypher median / max $ | Agent median / max $ | Reservation per question (1.5 × sum of max, `estimate.py:21`) |
|---|---|---|---|
| H100g2 | 0.00056 / 0.00391 (n 560) | 0.00046 / 0.01025 (n 560) | 0.0212 |
| H1000g2 | 0.00057 / 0.01224 (n 560) | 0.00048 / 0.01899 (n 560) | 0.0469 |
| v1 D1000 (today's demo) | 0.00035 / 0.00100 | 0.00023 / 0.00736 | 0.0125 |

Per question V2T-A cost in R5: 0.00137 / 0.00148 $ (headline), 0.00225 / 0.00248 $ (held-out)
(`sealed/report/report.json`). A defence day of 40 live asks (rehearsal plus defence) ≈ 40 × 0.0025 = **$0.10**
expected; an upper bound per question at H1000g2 is the worst Cypher plus the worst agent cost seen,
0.01224 + 0.01899 = 0.03123 $, so 40 asks are bounded by about
**$1.25**. The session cap in the config ($5.0) holds about 106 reservations at H1000g2; **no guard or cap change
is needed**. The guard takes the dearest corpus's reservation (`state.py:368-371`), here H1000g2's. Today's v1 asks
cost about $0.0005 each (ADR-0056:118), so v2 asks are roughly three times dearer, still cents.

## 7. Coder tasks (question 7)

One Sonnet coder at a time; ruff, `mypy --strict`, pytest green; all tests offline (fake transport, fake store
probe, toy corpora); no paid call; no file under `V2T_FROZEN_FILES`, `data/runs/exp0007/inputs` or `E8.sha256`.

| # | Task | Size | Tests (offline) |
|---|---|---|---|
| T1 | `demo/app/need_routing.py`: `split_by_start(policy) -> RoutedPolicy`, `route_question(text, finder, routed) -> NeedRoute` (§8) | S | equivalence: for every label and every outcome / rows / abstain / truncated combination on a two-tier toy, `decide(original, label)` equals `decide(derived[start], None)` in `answered_by`, `tiers_tried`, cost, latency; refuses `last_tier_by_label`; isolation wordings route to start 1, "cut … off from all downstream" to 0 (toy view, `tests/qa_need_toy.py`) |
| T2 | Wire the router: `LiveCascadeFactory` opens one `OpenedCascade` per start index (shared cache file), `CascadeSource.route(text)`, `begin_ask(route)`; `jobs._ask_live` routes first; `DemoAnswer` gains `need_label`, `start_tier`; `reopen`/`close` handle both | M | fake transport: routed question calls only the agent; unrouted calls Cypher first; store missing → full cascade derived, routed one still evaluated; close twice harmless; status shows `cascade_v4_iso` and its tiers |
| T3 | Results sources v2: `LadderSource(scope)`, `SealedSource(policies, scopes)` list, `InfraSource(rows)`; v1 flat keys still accepted (before-validator); `SealedRow.scope`, `.result_row`; infra projection | M | v1 config still parses and gives today's view; R4-shaped fixture with `all` scope; two sealed sources merged; unknown growth name → clear error |
| T4 | Front end: v2 arm/policy names and styles, F1 series, held-out chart, infra table, "how it works" text with the `complete` rule and need routing, route line in the answer card | M | existing page tests (`tests/test_demo_page.py`) extended: names present, no `cascade_v3` label for v2 arms, infra table renders from a fixture |
| T5 | `labels.en.json`: tiers `cypher-v2t`, `agent-v2t`; strategies `cypher_rag_lines`, `graph_agent_lines`; 98 class names; glossary (need routing, spare A/B) | S | every `VOCABULARY` name has a class name; every tier of every shipped v2t policy has a tier label |
| T6 | `python -m plantgraph.demo.app replay-agreement`: the routed live cascade with `allow_paid_calls=False` on a **copy** of the R5 cache vs frozen `join_corpus` + `decide_all` with `anchor_finder`; per question answered_by / outcome / final answer equal, cache misses counted; records `git diff` of `qa/need`, `qa/anchors.py` against E7 | M | toy cascade with a fake cache: agreeing and disagreeing rows counted; a miss is reported, never sent |
| T7 | Data and config (no library code): `data/runs/exp0007/demo/demo_config.json`, example files (§5.1), presentation ids (§5.2), drawing export to `data/runs/exp0007/demo/drawings/<c>`, `demo_config.example.json` v2 plus a v1 example | S | config loads (`load_demo_config`), every presentation id exists in its examples file |

Order: T1 → T2 → T5 → T3 → T4 → T6 → T7. T1+T2 alone already give a running V2T-A demo with the v1 Results tab
switched off (partial result early). Effort estimate (not measured): 3 S + 4 M ≈ 1.5–2 coder days including review.

### 7.1 Verification after the code (free first)

| Step | What | Needs | Pass |
|---|---|---|---|
| F1 | ruff, mypy, pytest on the demo tests | nothing | green |
| F2 | freeze check (§2.3) | nothing | no diff, all hashes OK |
| F3 | drawing export H100g2, then H1000g2 | CPU; after EXP-0004 P3 ends | `DrawingReport` self-check passes; time and PDF size recorded (H1000g2 rebuild alone ≈ 402.56 s, INFRA-2 `startup.rebuild`) |
| F4 | server start with the v2 config, `/api/status`, `/api/results`, drawings, tag lookup | no Neo4j write | both plants `ready`; startup ≈ 408 s at H1000g2 (INFRA-2 `startup.total`); app RSS recorded (two agent instances, risk R2) |
| F5a | T6 on routed questions only, H100g2 and H1000g2 | nothing (agent tier needs no Neo4j) | 100 % agreement on fully cached walks |
| F5b | T6 on all 560 H100g2 questions | H100g2 `plant_lines` in temporary `e7tune`, user's yes, EXP-0004 idle | agreement on every fully cached walk; misses explained (live deadline, §2.3) |
| F6 | plant switch in the `neo4j` database: wipe v1 D1000, load H1000g2 | user's yes (rule change) | `ready`; load time recorded |
| P1 | paid smoke: 3 questions per plant (one routed isolation, one Cypher-accepted lookup, one escalated flow path) | user's approval | 6 answers, spend ≈ 6 × 0.0025 = $0.015, cap $0.25 |

## 8. Data model

```python
# src/plantgraph/demo/app/need_routing.py
class RoutedPolicy(BaseModel):            # frozen
    evaluated: CascadePolicy              # as loaded (cascade_v4_iso); shown on /api/status, never run directly
    by_start: dict[int, CascadePolicy]    # start index -> label-free derived policy run by the frozen LiveCascade
    def start_for(self, label: NeedLabel) -> int: ...   # evaluated.start_tier_by_label.get(label, 0)

class NeedRoute(BaseModel):               # frozen
    need_label: NeedLabel
    start_index: int
    start_tier: str                       # name of the first tier tried
    @property
    def routed(self) -> bool: ...         # start_index > 0

def split_by_start(policy: CascadePolicy) -> RoutedPolicy: ...          # ValueError on last_tier_by_label
def route_question(text: str, finder: AnchorFinder, routed: RoutedPolicy) -> NeedRoute: ...

# src/plantgraph/demo/app/config.py (T3)
class LadderSource(BaseModel):  report: Path; result_row: str; scope: Literal["common", "all"] = "common"
class SealedSource(BaseModel):  report: Path; result_row: str; policies: tuple[str, ...]; scopes: tuple[str, ...] = ("headline",)
class InfraSource(BaseModel):   report: Path; result_row: str; rows: tuple[str, ...]
class ResultsSources(BaseModel): ladder: LadderSource | None = None; sealed: tuple[SealedSource, ...] = (); infra: InfraSource | None = None
```

`DemoAnswer` (`api_models.py:93`) gains `need_label: str | None` and `start_tier: str | None`.

## 9. Files

New: `src/plantgraph/demo/app/need_routing.py`, `src/plantgraph/demo/app/replay_agreement.py`,
`tests/test_demo_need_routing.py`, `tests/test_demo_replay_agreement.py`, `data/runs/exp0007/demo/` (config,
examples, drawings, calls log). Changed: `demo/app/live_cascades.py`, `corpus_runtime.py`, `jobs.py`,
`api_models.py`, `config.py`, `results.py`, `state.py`, `__main__.py`, `static/results_data.js`, `results.js`,
`results_tables.js`, `strings.js`, `answer.js`, `labels.en.json`, `demo_config.example.json`, and the matching
`tests/test_demo_*.py`. Unchanged: everything under `V2T_FROZEN_FILES`, `qa/need/`, `qa/anchors.py`.

## 10. Open questions for the user (recommendation first)

1. **Routing in the demo** — demo-side router, no frozen file touched (ADR-0064 §1 A). Recommended.
2. **Plants** — H1000g2 main, H100g2 small; v1 plants out of the v2 demo (ADR-0064 §2 A). Recommended.
3. **Neo4j end state** — the `neo4j` database ends on H1000g2 instead of v1 D1000 (rule change). Recommended.
4. **Results tab** — v2 only: R4 all families, R5 headline + held-out, F1 cascade bar, INFRA-2 table. Recommended.
5. **Presentation picks** — the declared first-of-family rule (§5.2), kept even if a rehearsal answer is wrong.
   Recommended: a live miss is honest and the Results tab carries the representative numbers.
6. **v1 demo** — keep runnable via the v1 config (cheap, reproducible). Recommended.
7. **Startup ≈ 7 min at H1000g2** — accept and start the server early; a demo-side artifact cache is possible later
   but adds a staleness risk. Recommended: accept.
8. **Paid smoke P1** (≈ $0.015, cap $0.25) after F1–F6. Recommended when the free checks pass.

## 11. Risks

- R1. The live deadline effect (§2.3) makes some escalated answers differ from R5's offline walk; T6 measures it.
- R2. Two opened cascades per corpus build the agent strategy twice over the same view; memory at H1000g2
  unmeasured (INFRA-2 app peak 1,803,264,000 B with one); F4 records it.
- R3. EXP-0004 may land more data-side code under frozen directories; the demo must keep the default ingest path
  (E8 point 4 proved it unchanged, `e8_identify.sh:49-78`).
- R4. The v2 drawing at 1,000 sheets is unmeasured (F3); a self-check failure would block B13.
- R5. Provider prices may have moved since R5; the estimate reads records, the cap still bounds spend.

## 12. Sources

`src/plantgraph/qa/cascade/live.py`, `live_build.py`, `accept.py`, `policy.py`, `labels.py`, `join.py`,
`report.py`; `src/plantgraph/qa/need/rules.py`; `src/plantgraph/demo/app/*.py` and `static/*` as cited;
`data/runs/exp0007/tune_lib.sh`, `v2t_lib.sh`, `lib.sh`, `run_sealed.sh`; `data/runs/exp0004/E8.sha256`,
`e8_identify.sh`; `data/runs/exp0007/ladder/report/report.json`, `sealed/report/report.json`,
`sealed/report_f1_baseline/report.json`, `infra/report.json`, `infra/report.md:42-49`;
`docs/private/30-experiments/_results.md:9-14`; ADR-0049:109; ADR-0056:118.
