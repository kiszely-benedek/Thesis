---
design: Demo upgrade from v1 (cascade_v3 on D100 / D1000) to the v2 system V2T-A2 (cascade_v4_iso at freeze E9 on H100g21p1 / H1000g21p1)
date: 2026-11-05
revision: 2, 2026-11-20 (EXP-0008 data, freeze E9, user decisions of 2026-11-20; ADR-0064 amendment)
status: accepted with ADR-0064 (2026-11-05); revision 2 goes with the ADR-0064 amendment of 2026-11-20
amends: 40-design/demo-app.md (accepted with ADR-0049) §5.2 "the demo refuses a label-routing policy", §6 config, §7 results
adrs: ADR-0049 (accepted, amended in part by ADR-0064), ADR-0056 (point 2 amended in part), ADR-0053 (sealed claims), ADR-0063 (tag identity E1–E4), ADR-0064 (accepted, amended 2026-11-20), ADR-0065 (review fixes, EXP-0008)
---

# Demo v2: the frozen V2T-A2, live, on two sealed EXP-0008 plants

All facts below were read from the repository or computed with free, read-only Python (architect scratch). There
was no Neo4j access, no model call and no write outside `docs/`. Revision 1 was computed on 2026-11-05 at
`c6099fc` against EXP-0007. Revision 2 was recomputed on 2026-11-20 at HEAD `e54a495` against EXP-0008. Two facts
make line numbers stable:

- Frozen code is unchanged since E9 `5d31cbb`: `sha256sum -c data/runs/exp0008/prereg/E9.sha256` passes, and
  `git diff` of the E9 file list is empty.
- Demo code is unchanged since `3181573`.

**Revision 2 changes, in short.**

- Plants are now H1000g21p1 (main) and H100g21p1 (small), the user's choice of 2026-11-20.
- The freeze is E9 instead of E8, and the system is V2T-A2 instead of V2T-A.
- All sources come from `data/runs/exp0008/`, and the demo's data directory is `data/runs/exp0008/demo/`.
- The Results tab now has pooled five-plant rows beside the demo plants' own rows. It also gains a tag-identity
  end-to-end table (user, 2026-11-20).
- The reader gaps of §4 were re-checked against the real EXP-0008 JSON. They differ from revision 1 in five
  places, marked **(rev 2)**.
- §6 was recomputed with `estimate_cost`.
- Check F6 is dropped, because Neo4j already holds H1000g21p1.
- T3 is split into T3a and T3b.

## 0. Recommendation

1. **The freeze can be kept, but not by configuration alone.**
   - The frozen live cascade still refuses `cascade_v4_iso` because the policy routes by need label (§2.1).
   - The fix is unchanged: a **demo-side need router**. It reproduces the policy's routing with two label-free
     derived policies, each run by the unchanged frozen `LiveCascade`.
   - Every change lives in `src/plantgraph/demo/**`, `tests/test_demo_*` and the new `data/runs/exp0008/demo/`.
     ADR-0064 §1 stands.
2. **Show two sealed EXP-0008 test plants: H1000g21p1 (main) and H100g21p1 (small).**
   - Both are plant 1 of their scale. They are also the pair the INFRA report measures.
   - The user's `neo4j` database already holds H1000g21p1. EXP-0008's last load ended there (`run_all.log`, M10b:
     "the database ends on H1000g21p1 (plant_lines)").
   - The v1 plants leave the v2 demo, and the v1 config stays runnable.
3. **Results tab: v2 only.** It has five parts, all read from report files:
   - the ladder (common families, as EXP-0008 reports it);
   - the sealed headline and held-out rows: the pooled S100 / S1000 rows, which are the thesis numbers, plus the two
     demo plants' own rows;
   - the F1 cascade as the "before" bar;
   - an INFRA table;
   - a small tag-identity end-to-end table (R5 / V-d0 / V-d2 / V-d4 with E1–E4).
   Three of the existing readers fail on EXP-0008 today: the sealed reader gives 0 rows, the F1 reader raises
   `KeyError 'H100g21p1'`, and there is no reader for infra or e2e. The ladder reader works (§4).
4. **Eight coder tasks** (T1, T2, T5, T3a, T3b, T4, T6, T7), one Sonnet coder at a time, all offline-tested (§7).
   Then come the free checks, then a paid smoke of 6 questions (expected about $0.015, cap $0.25).

## 1. What is v1-bound

### 1.1 Bound to v1 — must change

| # | Item | Evidence | v1 assumption | v2 change | Task |
|---|---|---|---|---|---|
| B1 | Live policy | `qa/cascade/live.py:157-163` (`refuse_label_routing`); called from `check_runnable` (`live.py:176-178`, run by `LiveCascade.__init__` at `live.py:76`) and first in `open_live_cascade` (`live_build.py:165`) | a live policy has no `start_tier_by_label` | `policies_v2t/cascade_v4_iso.json` has `start_tier_by_label` {UPSTREAM/DOWNSTREAM_TO_FIRST_VALVE: 1}, so a demo-side router is needed (§2). Re-run 2026-11-20: still REFUSED. | T1, T2 |
| B2 | Policy name in config | `data/runs/cv1/demo/demo_config.json` `"policy": "cascade_v3"`; `config.py:146-156` resolves names only in `POLICIES_DIR` (v1 folder) | shipped name | give the path `src/plantgraph/qa/cascade/policies_v2t/cascade_v4_iso.json` (already supported, `config.py:152-153`) | T7 |
| B3 | Tier sources | config `tier_runs` = `cv1/runs/CYPL2-*`, `AGL3-*`; tier names `cypher-luna`, `agent-luna` | v1 tiers | `cypher-v2t` = `data/runs/exp0008/m6a/runs/S7-CYP-<c>`, `agent-v2t` = `…/m6a/runs/S7-AG-<c>`. See note 1 below. | T7 |
| B4 | Ingest / store profile | `corpus_runtime.py:83-84` builds the view and the load plan from one `ingest.json`; `live_build.py:127` checks `PROFILE_OF_NAME[strategy]` | v1 `neo4jplant/D*/ingest.json` (`plant`) | `data/runs/exp0008/neo4jplant/<c>/ingest.json`. See note 2 below. | T7 |
| B5 | Results config | `config.py:46-54`: one `ladder_report`, one `sealed_report`, defaults `EXP-0001-LADDER`, `EXP-0002-H100, EXP-0002-H1000` | one report of each kind | a list of sealed sources, the ladder scope, optional infra and e2e sources (§4, §8) | T3a, T3b |
| B6 | Ladder scope | `results.py:56` `Literal["common"]`, filter `results.py:201` | the claim's scope is `common` | **(rev 2)** EXP-0008 reports its ladder and X1 / X2 on **common** (`reports/ladder/report.json` `claims`), so v1's scope is right again. Keep it configurable (`common` default, `all` allowed) | T3a |
| B7 | Sealed policy filter and sheets | `results.py:156-157` `SEALED_POLICIES = ("cascade_v3", "always_g_luna", "always_c_luna")`; `headline` only (`results.py:235`); `sheets[row.corpus_id]` (`results.py:218`) | v1 names; every row's corpus is a key of `sealed.sheets` | **(rev 2)** Run 2026-11-20: the EXP-0008 sealed report gives **0 rows**, and the F1 report raises **`KeyError 'H100g21p1'`**: `sealed.sheets` holds only the pooled ids `{S100: 100, S1000: 1001}`. Needs `policies`, `scopes`, `corpora` and a sheet count for plant rows (§4) | T3a |
| B8 | Results front end | `static/results_data.js:9-20` (`ARM_ORDER`, `ARM_STYLE`, `ARM_OF_POLICY`, `POLICY_ORDER`); `static/strings.js:85`, `:125` ("Wilson interval" captions), `armNames`, `armNotes`, `policyNames` | v1 arm and policy names; every interval is Wilson | v2 names; F1 as its own series; held-out chart; pooled-against-plant rows with the interval method named per row; infra and e2e tables; claim lines | T4 |
| B9 | "How it works" text | `static/strings.js` (section "how it works") | Cypher step, then the agent on failure | add the `complete` rule (Cypher result not cut) and the need routing (isolation questions start at the agent) | T4 |
| B10 | Label table | `static/labels.en.json`: tiers only `cypher-low`, `cypher-luna`, `agent-low-steps`, `agent-luna`; strategies only `cypher_rag_plant`, `graph_agent_low_steps`; `class_names` has 14 entries | v1 vocabulary | **(rev 2, recomputed)** `graph/schema_vocabulary.py` `VOCABULARY` has 98 classes, **86** without a label (e.g. `Pump`, `ReciprocatingPump`). Add `cypher-v2t`, `agent-v2t`, `cypher_rag_lines`, `graph_agent_lines`, 98 class names and glossary terms (§7 T5) | T5 |
| B11 | Example files | `cv1/demo/examples/D1000.jsonl` (rule "per-family 2, seed 20261011", its provenance file) | v1 question files | regenerate with the same tool from the EXP-0008 question files (§5) | T7 |
| B12 | Presentation sequences | config `presentation` names v1 ids (`D1000:LOOKUP_TYPE:V-361-5`, …) | v1 ids | new sequences on H1000g21p1 / H100g21p1 (§5.2) | T7 |
| B13 | Drawings | only `cv1/drawings/D100` and `D1000` exist | — | export H100g21p1 and H1000g21p1 to `data/runs/exp0008/demo/drawings/<c>` (code already v2-aware, §1.2) | T7 |
| B14 | Shipped example config | `demo/app/demo_config.example.json:2-37` | v1 paths | v2 paths; keep a v1 example beside it | T7 |
| B15 | Tag-identity table | — (new, user 2026-11-20) | — | reader and table for `data/runs/exp0008/reports/e2e/report.json` (§4) | T3b, T4 |
| B16 | File size limit | `demo/app/state.py` 397 lines, `results.py` 250 lines (coder rule: no file over 400) | — | before T2 or T3 adds a line to `state.py`, a cohesive part moves out of it first, with no change in behaviour. T3a splits `results.py` (§9) | T2, T3a |

Notes to the table:

1. **B3 tier runs.** Verified 2026-11-20: `load_tier_from_run` (`live_build.py:96`) accepts all four runs.
   - Cypher params are `{"timeout_s": 30, "row_cap": 1000}`, with pin effort `low`.
   - Agent params are `max_steps 40, step_effort low, observation_chars 32000, max_items_listed 400,
     max_prompt_chars_total 600000`, with pin effort `high`.
   - Both pins match the policy's `pin_sha256` (`acf24178…`, `ffc026d3…`).
   - Do **not** use `m6c/runs/S7-AG-H1000g21p1-C1` as a tier source. It is the concurrency-1 control, and the config
     allows exactly one run per tier (`config.py:31-33`).
2. **B4 ingest records.** Both have `store_profile: plant_lines`:
   - H1000g21p1: 1,000 sheets, 93,171 nodes, 312,868 relationships;
   - H100g21p1: 100 sheets, 9,449 nodes, 31,666 relationships.
   Do not use `corpora/<c>/ingest.json`. Its profile is `both`, although its generator `config` is identical
   (computed 2026-11-20).

Name trap: `data/runs/cv1/demo/demo_config.v2.json` already exists, and it is an **old cascade_v2 config**
(policy `cascade_v2`, tiers `cypher-low`, `agent-low-steps`), not generator v2. The new config goes to
`data/runs/exp0008/demo/demo_config.json`. The old file is left alone.

### 1.2 Works unchanged with v2 corpora

- **Drawing export.**
  - It picks the ISO glyph style when a sheet holds a class beyond v1's (`drawing/export.py:65-68`).
  - It draws all 98 vocabulary classes (commit `3181573`).
  - `tests/test_demo_glyphs_v2.py` lays out and renders a 10-sheet v2 corpus.
  - The self-check `_check_against_corpus` (`export.py:54`, `:89`) refuses a drawing that misses symbols, flags or
    lines.
  - It has **not yet been run on a 1,000-sheet v2 plant**: time and PDF size are unmeasured (free check F3).
- **Tags: ISA style, A/B spares, unit-prefixed numbers.**
  - The tag lookup is a sorted prefix index with no tag pattern (`tag_lookup.py:24-36`).
  - Answer text matches the plant's own tags longest-first, with letter/digit/hyphen guards
    (`static/tagtext.js:8-15`). So `P-44001A` is not found inside `P-44001AB`, and the spares `P-44001A` and
    `P-44001B` of H1000g21p1 stay distinct.
  - Evidence words use a generic pattern (`evidence.py:19`).
  - Example EXP-0008 tags: `GTV-276002`, `HS-556001`, `LSHH-330007`, `P-3401B`.
- **Question families.**
  - `family_topics` covers every `QuestionFamily`, as asserted by `tests/test_demo_labels.py:58`.
  - Each plant's file has 23 families: 13 families with 10 questions and 10 with 15 (computed 2026-11-20).
- **Graph view.** The demo builds `NetworkxGraphView(corpus_id, localized_sheets, resolution)`
  (`corpus_runtime.py:84`), the same call as the harness.
- **Store probe and plant switch.** Both are profile-generic (`store_probe.py:82-88`, `store_loader.py:44-57`).
- **Cost estimate and cap.** `estimate.py:28-37` reads per-tier costs from the configured tier runs, under the
  tier's pin. On the EXP-0008 runs it gives own-corpus figures without any code change (§6, run 2026-11-20).
- **Examples tool.** `examples.py:76-91` (`--per-family N --seed S`) works on any `questions.jsonl`. It is
  deterministic (sha256 ranking), so the picks of §5 could be computed in advance.
- **Live-only guard.** The per-ask cache emptying and `allow_paid_calls=True` (`live_cascades.py:181-187`,
  `:222`, `:230-238`) do not depend on the policy.

## 2. The freeze

### 2.1 The problem

- `open_live_cascade` calls `refuse_label_routing(policy)` before anything else (`live_build.py:165`).
- `LiveCascade.__init__` checks it again through `check_runnable` (`live.py:76`, `:176-178`).
- `check_runnable` also refuses tiers that differ from the policy's, and any pin mismatch.

Run 2026-11-20 on the frozen policy file:

```
REFUSED: expected a policy without label routing (a free-text question has no need label), found start/last_tier_by_label in 'cascade_v4_iso'
```

V2T-A2 is `cascade_v4_iso` as frozen at E9. Its policy file is unchanged since `ee8e164`. V2T-A2 is "V2T-A plus the
review fixes, no new tuning" (`review-fixes.md:128`). The policy's only difference from `cascade_v4` is exactly
that routing. E9 hashes `live.py`, `live_build.py` and the policy file (`E9.sha256`).

### 2.2 How R5 routed, and why a demo-side router is exact

- **Where the label came from.**
  - EXP-0008's sealed report was built with `--corpora-root "$ROOT/corpora"` (`stages/m10_audit_reports.sh:130-134`).
  - The report reads rules labels for label-routed policies (`qa/cascade/report.py:286-287`). A label from a stored
    trace wins first (`report.py:107-108`, `join.py:121-140`).
  - Neither V2T-A2 tier writes a `need_label` into its trace. Only `qa/strategies/hierarchical_need.py:199` does.
    So every label came from `classify_need(text, anchor_finder(view))` (`qa/cascade/labels.py:25`, `:30`).
  - The rules are free and deterministic. Isolation is matched by wording: `\bisolat\w*\b.*\bupstream\b` and
    `…downstream\b` (`qa/need/rules.py:53-54`).
  - The demo builds its view from `neo4jplant/<c>/ingest.json`. Its generator `config` is equal to that of
    `corpora/<c>/ingest.json` for both plants (computed 2026-11-20), so the anchors are the same.
- **What this routes on the demo plants (rev 2).**
  - The sealed report's need-label breakdown for `cascade_v4_iso` (`corpora[i].breakdowns["need label"]`) has
    UPSTREAM_TO_FIRST_VALVE on **10 of 280** questions on each plant, and DOWNSTREAM_TO_FIRST_VALVE on none.
  - The DOWNSTREAM_ISOLATION template ("To cut P-44001A off from all downstream equipment…") does not match.
  - Only 10 of the 15 UPSTREAM_ISOLATION questions match. The 5 wording variants ("Before maintenance on P-3701,
    which valves have to be shut to stop every incoming flow?") have no "isolat…".
  - The live router must give the same result, and it does if it calls the same function.
- **The walk.**
  - `start_index` = `start_tier_by_label.get(label, 0)` (`accept.py:66-74`).
  - The walk runs `tiers[first : last+1]` (`accept.py:107`).
  - The fallback goes to the first tier only if that tier was tried (`policy.py:73-80`, test at `:78`).
- **Derived policies.** For each start index `s` the policy uses (here 0 and 1), build in memory
  `policy.model_copy(update={"tiers": policy.tiers[s:], "start_tier_by_label": {}, "fallback_to_first_answer":
  policy.fallback_to_first_answer if s == 0 else False})`. Then, for every label and every signal combination:
  - `s = 0`: the same tiers, rules and fallback, so the walk and the decision are identical.
  - `s > 0`: the same tiers are tried with the same acceptance. The original never falls back (tier 0 is not
    tried), and the derived one has fallback off. So `answered_by`, `tiers_tried`, cost and latency are identical.
  - `last_tier_by_label` is empty in `cascade_v4_iso`. The router refuses a policy that sets it (out of scope).
- **The frozen code accepts them.** The derived policies have no label routing, so the frozen
  `refuse_label_routing` accepts both. This was run on 2026-11-20: "derived start-1 no-route OK ['agent-v2t']" and
  "derived start-0 no-route OK".
  - The derived policies keep the name `cascade_v4_iso`.
  - The start-1 policy has no Cypher tier, so `open_live_cascade` opens no Neo4j source for it
    (`live_build.py:170-172`).
  - A start-0 cascade whose store is missing becomes the frozen derived `cascade_v4_iso-no-cypher-v2t` with a notice
    (`live_build.py:181-185`).

### 2.3 Changes and freeze compliance

Every change is in `src/plantgraph/demo/**`, `tests/test_demo_*.py` and new data under `data/runs/exp0008/demo/`.

- **What E9 freezes.** `FROZEN_PATHS` = `src :!src/plantgraph/demo`, the EXP-0008 scripts and stages,
  `data/runs/exp0007/inputs`, `data/runs/exp0001/inputs` and the EX01 XML, plus `pyproject.toml` and `uv.lock`
  (`data/runs/exp0008/stages/m3_freeze.sh:14-16`, `:45`).
  - `E9.sha256` has 515 lines. None is a `demo` path (`grep -c demo` = 0), none is under `tests/`, and none is
    under `data/runs/exp0008/demo`.
  - Because `pyproject.toml` and `uv.lock` are frozen, **no task may add a dependency**.
- **The demo only *calls* frozen code:** `open_live_cascade`, `load_tier_from_run`, `classify_need`,
  `anchor_finder`, and in tests `walk_question`, `decide`, `decide_all` and `join_corpus`.
- **Check after every commit** (free, seconds; all three pass at `e54a495` today):

  ```
  sha256sum -c --quiet data/runs/exp0008/prereg/E9.sha256
  git diff --quiet $(cat data/runs/exp0008/prereg/E9.commit) -- $(cat data/runs/exp0008/freeze/frozen_files.txt)
  test -z "$(git status --porcelain -- src ':!src/plantgraph/demo' pyproject.toml uv.lock)"
  ```

  The third line catches a new untracked file under frozen `src`, which the hash list cannot see.

**Freeze gap of revision 1: closed.** E9 now hashes `src/plantgraph/qa/need/*` (six files) and
`src/plantgraph/qa/anchors.py`. T6 records the E9 check result instead of a diff against E7.

**Known live-vs-offline difference (pre-existing in v1, not a freeze breach).**
- Live, the agent after a Cypher tier gets C minus the Cypher latency (`live.py:97-113`). It reads its remaining
  time before each step (`qa/harness/attempt.py:85-91`).
- Offline, the R5 agent row ran with the full 120 s, and the join cut it afterwards.
- So a question that escalates may stop earlier live. Routed questions start at the agent with the full C, as
  offline. T6 measures the effect on replays.

## 3. Which plant (decided by the user, 2026-11-20)

| Option | For | Against |
|---|---|---|
| **A. H1000g21p1 + H100g21p1 (chosen)** | plant 1 of each EXP-0008 scale. Their own rows sit inside the pooled S1000 / S100 numbers. Tier runs, recorded answers and cost evidence come from the same plant (`estimate.py:71` prefers own-corpus runs). `plant_lines` ingest records are ready. They are the INFRA pair. H1000g21p1 is already in Neo4j | the sealed questions of these two plants become public; the thesis says so (below) |
| B. Validation plant VAL1000g21 (dev, EXP-0008 M1) | not a test plant | 163 dev questions only. Its `neo4jplant` ingest has profile `plant` (1,001 sheets), so it needs a new `plant_lines` ingest. No sealed numbers on it |
| C. A fresh dev plant (e.g. D1000g21) | untouched | its `corpora` ingest has profile `both`, so it needs a new load. It has no questions or recorded runs. The demo would not show the plants the numbers come from |

**What the thesis should state (as ADR-0064 amendment point 6).**
- The demo shows two sealed EXP-0008 test plants, H1000g21p1 and H100g21p1. It does so after the single sealed test
  run (EXP-0008 M6; the launcher finished on 2026-11-17).
- It runs the frozen V2T-A2 (E9 `5d31cbb`), and no file hashed in E9 changed for the demo.
- The sealed questions of these two plants become public when shown. Any later system change needs a new sealed
  set (ADR-0053).
- Live demo answers are new model calls, not measurements. They change no EXP-0008 number.

**Neo4j.**
- The `neo4j` database holds H1000g21p1 (`plant_lines`). That is the required end state, so **no switch is needed**.
- The demo's plant switch wipes the database and loads the chosen plant (`store_loader.py:44-57`). This keeps the
  one-plant rule by construction.
- At startup, H100g21p1 is "not in the store". Its start-0 cascade runs as the frozen derived
  `cascade_v4_iso-no-cypher-v2t`, with the notice shown, until a switch.
- To ask H100g21p1 with its Cypher tier live, switch to it, then switch back before the session ends. The recorded
  load times are `stage_seconds.load_total` 3.22 s at H100g21p1 and 32.20 s at H1000g21p1 (their `ingest.json`).
  This is optional check F6' (§7.1).
- The temporary database `e7tune` no longer exists: EXP-0008 dropped it (`lib_plants.sh:70-73`).

## 4. Results tab

### 4.1 Sources and reader gaps (shapes read 2026-11-20)

| View | Source | Shape (computed) | Reader today | Needed |
|---|---|---|---|---|
| Ladder | `data/runs/exp0008/reports/ladder/report.json` | See note 1 below | **works**: 15 common points, arms `ag, cascade_v4_iso, ctx-high, cyp`, 19 families, wall 66.72 | front-end style for `cascade_v4_iso`; `scope` config (default `common`); **(rev 2)** claim lines from `claims` |
| Sealed | `data/runs/exp0008/reports/sealed/report.json` | See note 2 below | **0 rows** (v1 policy filter) | config `policies`, `scopes`, `corpora`; sheet count for plant rows; interval method per row; claim lines from `sealed.claims` (`rule`, `status`, `headline`) |
| F1 baseline | `data/runs/exp0008/reports/f1_baseline/report.json` | same as sealed; policies `cascade_v3, always_g_luna, always_c_luna, cascade_v3_iso` | **`KeyError 'H100g21p1'`** (policy names pass the v1 filter, then the sheets lookup fails) | a second sealed source, `cascade_v3` only, labelled "F1, previous system" |
| INFRA | `data/runs/exp0008/infra/report.json` | See note 3 below | none | adapter: configured rows, **each with an explicit unit**; check lines from `checks` |
| Tag identity, end to end | `data/runs/exp0008/reports/e2e/report.json` | See note 4 below | none | reader: pooled arms, the configured plant's arms, claim lines. **(rev 2)** map `difference.mean` to `estimate` and `passed` to PASS / FAIL. Never read `spend_usd`, and never show a title |

Notes to the table:

1. **Ladder shape.**
   - Keys are `cutoff_s, n_boot, seed, sizes, scope_families{common 19, all 23}, cells, deltas, trends, claims,
     absent, wall_sheets`.
   - There are 30 cells, 15 per scope.
   - `claims` has 6 entries, each with `id, wording, value, verdict`.
   - `absent` has 5 entries: ctx-low everywhere and ctx-high at H30g21.
   - `sizes` carries extra fields.
   - The extra keys `deltas`, `trends` and `claims` are ignored by `_Parsed(extra="ignore")`.
2. **Sealed shape.**
   - `sealed.sheets` = `{S100: 100, S1000: 1001}`, with **pooled ids only**.
   - `sealed.scales` = `{S100: [5 plants], S1000: [5 plants]}`.
   - `scope_rows` has 96 rows: 12 corpus ids (10 plants plus `S100` and `S1000`) × 2 scopes (`headline`,
     `held-out`) × 4 policies (`cascade_v4_iso, cascade_v4, always_g_v2t, always_c_v2t`).
   - Pooled rows have the same keys and the same `summary` fields as plant rows.
   - `sealed.claims` has 19 entries.
3. **INFRA shape.**
   - Keys are `machine_summary, git_commit, git_dirty, checks(9), footprints(2), compute(20), growth(41),
     reference_price, money`.
   - Each `growth` row is `{name, from_corpus: H100g21p1, to_corpus: H1000g21p1, from_value, to_value}`.
4. **E2E shape.**
   - Keys are `cutoff_s, policy, n_questions 1100, n_plants 5, plants(5) {plant_id, arms}, arms(4) {label, n,
     n_correct, accuracy, spend_usd}, claims(5) {claim, description, rule, difference{mean, ci_low, ci_high},
     passed, n_plants, n_same_sign}, families(88), exposure(8), outcomes, notes(5)`.

**Surprises against revision 1's assumptions (rev 2).**

1. **Plant rows have no sheet count in the report.** `sealed.sheets` names only the pooled scales.
   - The plant's count comes from the configured demo corpus's `ingest.json` (`counts.n_sheets`).
   - A selected plant row that is neither pooled nor configured is a clear `ValueError` at startup, not a `KeyError`.
   - The five S1000 plants have 1,000 / 1,000 / 1,000 / 1,002 / 1,002 sheets (ingest records). The report writes
     the pooled scale as 1001, and the caption uses the report's figure.
2. **Two interval methods.**
   - Plant rows use Wilson intervals. This was checked: 203/220 gives [0.880, 0.951], and the ladder cells match
     Wilson to 1e-5.
   - Pooled rows are the equal-weight mean over five plants with **two-stage cluster bootstrap** intervals, which
     "understate between-plant variance (about 4/5 at five plants)" (`sealed.notes`).
   - `Interval`'s docstring "Wilson" (`results.py:24`) and the "Wilson interval" captions (`strings.js:85`, `:125`)
     become wrong for pooled rows. Each row therefore carries its method.
3. **INFRA names carry no unit suffix for times.** `ingest.build_total` and `startup.total` are seconds without
   `_s`, and `size.*` are counts. Revision 1's "unit from the suffix" rule would mislabel them. The config names
   the unit per row instead.
4. **The e2e report's differences use `mean`, not `estimate`,** and its verdict is a boolean `passed`.
5. **The ladder's scope is `common` again** (B6).

### 4.2 Numbers the tab would show (all read from those files on 2026-11-20)

Sealed, **headline** scope. Pooled rows have n 1,100 and plant rows n 220. Each cell gives correct, then acc@120
[interval].

| Policy | S100 pooled (bootstrap) | S1000 pooled (bootstrap) | H100g21p1 (Wilson) | H1000g21p1 (Wilson) |
|---|---|---|---|---|
| V2T-A2 `cascade_v4_iso` | 1005, 0.914 [0.895, 0.932] | 999, 0.908 [0.885, 0.932] | 203, 0.923 [0.880, 0.951] | 199, 0.905 [0.858, 0.937] |
| agent only `always_g_v2t` | 988, 0.898 [0.877, 0.919] | 988, 0.898 [0.875, 0.919] | 203, 0.923 [0.880, 0.951] | 197, 0.895 [0.848, 0.929] |
| Cypher only `always_c_v2t` | 892, 0.811 [0.785, 0.836] | 892, 0.811 [0.782, 0.840] | 176, 0.800 [0.742, 0.848] | 174, 0.791 [0.732, 0.839] |
| F1 `cascade_v3` (`f1_baseline`) | 899, 0.817 [0.792, 0.843] | 910, 0.827 [0.795, 0.858] | 183, 0.832 [0.777, 0.875] | 177, 0.805 [0.747, 0.852] |
| V2T-A2 $/question, median / p90 s | 0.00140, 8.17 / 44.50 | 0.00155, 9.25 / 51.67 | 0.00134, 8.11 / 44.63 | 0.00148, 9.18 / 48.15 |

Sealed, **held-out** families. Pooled rows have n 250 and plant rows n 50.

| Policy | S100 | S1000 | H100g21p1 | H1000g21p1 |
|---|---|---|---|---|
| V2T-A2 | 198, 0.792 [0.740, 0.844] | 196, 0.784 [0.716, 0.844] | 40, 0.800 [0.670, 0.888] | 38, 0.760 [0.626, 0.857] |
| agent only | 0.772 | 0.780 | 0.800 | 0.760 |
| Cypher only | 0.648 | 0.624 | 0.660 | 0.620 |
| F1 `cascade_v3` | 0.700 | 0.740 | 0.740 | 0.720 |
| V2T-A2 $/question | 0.00246 | 0.00262 | 0.00209 | 0.00249 |

**Claim lines** (`sealed.claims`):
- Headline: Q4 PASS, K1 FAIL ("the cascade saves nothing"), K2 PASS, K3 PASS, Q5 PASS.
- Held-out: the same, except K3 FAIL ("not fast enough at plant scale").
- Q1–Q3 NOT_RUN.

**Ladder** (common families, 19; n 68 / 76 / 76 / 76 at 1 / 3 / 11 / 32 sheets; `sizes.n_sheets`):

| Arm | 1 sheet | 3 | 11 | 32 |
|---|---|---|---|---|
| cascade_v4_iso | 0.985 | 0.921 | 0.855 | 0.908 |
| ContextRAG high | 0.779 | 0.566 | 0.592 | absent |
| agent | 0.985 | 0.934 | 0.882 | 0.895 |
| Cypher | 0.824 | 0.789 | 0.763 | 0.868 |

- The context wall is at 66.72 sheets (`wall_sheets`).
- The claim lines are X1 FAIL, X2 FAIL, X3 / X4 / X5 REPORTED and X6 NOT_RUN.

**INFRA** (`growth`, H100g21p1 to H1000g21p1):

| Row | H100g21p1 | H1000g21p1 |
|---|---|---|
| `size.sheets` | 100 | 1,000 |
| `store.data_bytes` | 6,891,281 B | 58,951,570 B |
| `ingest.build_total` | 9.38 s | 427.27 s |
| `startup.total` | 6.69 s | 390.64 s |
| `startup.without_rebuild` | 0.63 s | 5.53 s |
| `process.peak_bytes` | 357,908,480 B | 1,827,717,120 B |
| `neo4j.rss_bytes` | 1,198,567,424 B | 1,319,575,552 B |
| `cypher_db_only.local_median_s` | 0.045 s | 0.153 s |
| `cypher_db_only.local_p90_s` | 0.88 s | 31.60 s |

The check lines (`checks`) are M1 **FAIL**, M4 FLAG, M6 FLAG, and "Old-run rows" FLAG.

**Tag identity, end to end.** Pooled rows cover 1,100 questions per arm over 5 plants (bootstrap). The plant row
covers 220 questions (Wilson).

| Arm | Pooled | H1000g21p1 |
|---|---|---|
| R5 (clean tags) | 999, 0.908 [0.885, 0.932] | 199, 0.905 [0.858, 0.937] |
| V-d0 | 905, 0.823 [0.800, 0.845] | 179, 0.814 [0.757, 0.860] |
| V-d2 | 942, 0.856 [0.832, 0.880] | 187, 0.850 [0.797, 0.891] |
| V-d4 | 913, 0.830 [0.798, 0.862] | 180, 0.818 [0.762, 0.864] |

The claim lines are E1 PASS (−0.085), E2 PASS (+0.034), E3 FAIL (+0.007), E4 (D2) FAIL (−0.052) and E4 (D4) FAIL
(−0.078).

### 4.3 Captions must stay honest

Captions state rules and read verdicts from the files. They never contain typed-in numbers (`results.py:3-5`).

- **Ladder.**
  - X1 and X2 FAIL. The registered "inversion" did not occur: the cascade leads on accuracy at every measured size,
    including one sheet. What moves with size is cost and latency.
  - The agent alone is level with the cascade or above it from 3 to 11 sheets, and every interval overlaps.
  - ContextRAG is absent at 32 sheets and ctx-low was not run (both registered; from `absent`).
- **Sealed.**
  - Pooled intervals understate between-plant variance (`sealed.notes`).
  - The headline scope leaves out LOOP_ACTUATED_VALVE (`sealed.notes`).
  - Held-out families score lower than headline, so the headline is partly tuned.
  - No V2T-A2 minus F1 difference with an interval exists in either file. The F1 report's `paired_rows` compare F1
    only with its own references (K1, K2, Q5). The tab therefore shows both bars and **no difference**.
- **INFRA.** M1 FAILED, so the agent rows of the compute table are the source runs' timings, not fresh replays
  (`checks`, "Old-run rows"). The table shows no agent timing without this line.
- **Tag identity.**
  - The V arms ran on the variant copies `H1000g21p<k>V`, which use inconsistent tag writing. R5 ran on the clean
    plants, and the demo plant is the clean H1000g21p1.
  - D0 / D2 / D4 are the identity deciders of ADR-0063 point 3. Their wording comes from there.
  - The `spend_usd` field is not shown. The report's note says it "is not a cost per arm".
  - The report's markdown title "EXP-0004" is a known mislabel. The demo cites the JSON path and the results row
    "EXP-0008".
- **Results row** for every source: `EXP-0008` (`_results.md:9`).

## 5. Example questions and presentation

### 5.1 Examples

- **Source.** The EXP-0008 question files `data/runs/exp0008/questions/<c>/questions.jsonl`.
  - Each has 280 questions in 23 families.
  - The split of H1000g21p1 (`splits.json`) is dev-old 120, dev-new 60, held-out 50, held-out-wording 50.
  - The template text is English and is used **as written**: no wording file and no rewording (user rule: natural
    questions only).
- **Rule.** The v1 precedent's rule ("per-family 2") with the seed declared in revision 1 (20261105). The seed
  stays unchanged so that it is not chosen after seeing data.
- **Command per plant.**

  ```
  python -m plantgraph.demo.app examples --from data/runs/exp0008/questions/H1000g21p1/questions.jsonl \
    --corpus H1000g21p1 --per-family 2 --seed 20261105 --out data/runs/exp0008/demo/examples/H1000g21p1.jsonl
  ```

- **Output.** 46 examples per plant (computed 2026-11-20 with `select_per_family`), each with its provenance
  sidecar (`examples.py:136-145`).
- **`recorded_runs`.** These four runs show how V2T-A2's tiers and F1 answered each example:
  - `data/runs/exp0008/m6a/runs/S7-CYP-<c>`
  - `…/m6a/runs/S7-AG-<c>`
  - `…/m6b/runs/S7F1-CYP-<c>`
  - `…/m6b/runs/S7F1-AG-<c>`
- **Runs left out.**
  - `m6c` runs: d0 / d50 are other corpora, and `-C1` is the concurrency-1 control.
  - `m6b/superseded/`: it holds only H1000g21p3, which is not a demo plant.

### 5.2 Presentation sequences (config only)

The rule is declared so that no pick depends on an outcome. In each sequence, each named family uses the **first**
example of that family in the seeded examples file (file order). The isolation step takes the first
UPSTREAM_ISOLATION example that `route_question` sends to the agent (ADR-0064 amendment point 10). With seed
20261105 both drawn isolation examples are routed on both plants, so this equals the plain first-of-family pick.

- **H1000g21p1: "A 1,000-sheet plant: lookup, a route across sheets, isolation, a control loop, an unknown tag".**
  The expected ids (computed 2026-11-20; T7 confirms) are:
  - `H1000g21p1:LOOKUP_TYPE:LOOKUP_TYPE_P1:HS-556001`
  - `H1000g21p1:FLOW_PATH:FV-117049|GTV-134011`
  - `H1000g21p1:UPSTREAM_ISOLATION:V-1101`: shows the need routing, because it starts at the agent.
  - `H1000g21p1:LOOP_ACTUATED_VALVE:LOOP_ACTUATED_VALVE_P1:LIC-79001`: outside the headline scope; the caption
    says so.
  - `H1000g21p1:UNANSWERABLE_TAG:NEIGHBOURS_DOWNSTREAM:P-54802`: abstention.
  - then the Results tab.
- **H100g21p1: "A 100-sheet plant: spares and a held-out question".** This needs F6' for a live Cypher tier.
  - `H100g21p1:SAME_UNIT:P-1901A|E-1802`
  - `H100g21p1:ROUTE_AVOIDING:EA-5701|P-5701A|GTV-57007`: a held-out family.
  - then the Results tab.

## 6. Paid calls

Computed on 2026-11-20 with the demo's own `estimate_cost` (`estimate.py:28-37`) on the EXP-0008 tier runs and the
`cascade_v4_iso` tiers. All figures are own-corpus (`other_corpus` False). The v1 row was re-run on the same day
from `data/runs/cv1/demo/demo_config.json`.

| Plant | Cypher median / max $ | Agent median / max $ | Reservation per question (1.5 × sum of max, `estimate.py:21`) |
|---|---|---|---|
| H100g21p1 | 0.00055 / 0.00334 (n 280) | 0.00042 / 0.00865 (n 280) | 0.0180 |
| H1000g21p1 | 0.00055 / 0.01132 (n 280) | 0.00045 / 0.01943 (n 280) | 0.0461 |
| v1 D1000 (today's demo) | 0.00035 / 0.00100 (n 180) | 0.00023 / 0.00736 (n 180) | 0.0125 |

- **V2T-A2 cost per question in EXP-0008** (`sealed/report.json` `scope_rows`):
  - headline: 0.00134 $ (H100g21p1) and 0.00148 $ (H1000g21p1);
  - held-out: 0.00209 $ and 0.00249 $.
- **A defence day of 40 live asks** (rehearsal plus defence):
  - expected cost about 40 × 0.0025 = **$0.10**;
  - the upper bound per question at H1000g21p1 is the worst Cypher plus the worst agent cost seen, 0.01132 +
    0.01943 = 0.03074 $, so 40 asks are bounded by about **$1.23**.
- **The session cap needs no change.** The config's cap of $5.0 (inherited from the v1 config) holds 108
  reservations at H1000g21p1. The guard takes the dearest corpus's reservation (`state.py:368-371`), which is
  H1000g21p1's.
- **Comparison with v1.** Today's v1 asks cost about $0.0005 each (ADR-0056:118), so v2 asks are roughly three
  times dearer, still cents.

## 7. Coder tasks

**Rules for every task.**
- One Sonnet coder at a time.
- ruff, `mypy --strict` and pytest must be green. All tests are offline: fake transport, fake store probe, toy
  corpora. No paid call and no Neo4j.
- No file hashed in E9 changes, and no dependency is added (§2.3). Run the freeze check of §2.3 before handing
  over.
- Coders follow `.claude/agents/coder.md`. They also follow `.claude/skills/readable-py/SKILL.md` where it does not
  conflict with the coder rules. On comments and docstrings the coder rules win: brief comments on intent and
  mechanics, short docstrings, domain terms glossed once.

| # | Task | Size | Tests (offline) |
|---|---|---|---|
| T1 | `demo/app/need_routing.py`: `split_by_start(policy) -> RoutedPolicy`, `route_question(text, finder, routed) -> NeedRoute` (§8) | S | See test note T1 below |
| T2 | Wire the router (see task note T2) | M | fake transport: a routed question calls only the agent; an unrouted one calls Cypher first; store missing gives a derived full cascade while the routed one is still evaluated; close twice is harmless; status shows `cascade_v4_iso` and its tiers |
| T5 | `labels.en.json`: tiers `cypher-v2t`, `agent-v2t`; strategies `cypher_rag_lines`, `graph_agent_lines`; 98 class names (from `graph/schema_vocabulary.py` `VOCABULARY`); glossary terms (see task note T5) | S | every `VOCABULARY` name has a class name; every tier of every shipped v2t policy has a tier label |
| T3a | Results sources v2, ladder and sealed (see task note T3a) | M | See test note T3a below |
| T3b | INFRA and e2e readers (see task note T3b) | M | See test note T3b below |
| T4 | Front end (see task note T4) | M | existing page tests (`tests/test_demo_page.py`) extended: names present; no `cascade_v3` label on a v2 arm; pooled and plant rows name different methods; infra and e2e tables render from fixtures; no `spend_usd` text |
| T6 | `python -m plantgraph.demo.app replay-agreement` (see task note T6) | M | toy cascade with a fake cache: agreeing and disagreeing rows are counted; a miss is reported, never sent; freeze status is written |
| T7 | Data and config, no library code (see task note T7) | S | the config loads (`load_demo_config`); every presentation id exists in its examples file; the isolation step's example is routed (T1's function on the built view) |

**Task notes.**

- **T2.** Wire the router.
  - `LiveCascadeFactory` opens one `OpenedCascade` per start index, with a shared cache file.
  - Add `CascadeSource.route(text)` and `begin_ask(route)`. `jobs._ask_live` routes first.
  - `DemoAnswer` gains `need_label` and `start_tier`.
  - `reopen` and `close` handle both cascades.
  - If `state.py` (397 lines) must grow, first move a cohesive part out of it in a no-behaviour-change step.
- **T5.** The glossary terms are: need routing, spare A/B, pooled over five plants, two-stage bootstrap, and
  tag-identity deciders D0 / D2 / D4 (wording from ADR-0063 point 3).
- **T3a.** Results sources v2, ladder and sealed.
  - Add `LadderSource(scope)`, a list of `SealedSource(policies, scopes, corpora)`, and the `ClaimLine` projection.
  - The v1 flat keys are still accepted (before-validator).
  - `SealedRow` gains `scope`, `pooled`, `n_plants` and `interval_method`.
  - The sheet count of a plant row comes from the configured corpus's `ingest.json`. An unresolvable row raises
    `ValueError`.
  - Split `results.py` into `results_views.py` (API models), `results_reports.py` (parsed report shapes) and
    `results.py` (projections).
- **T3b.** INFRA and e2e readers.
  - `InfraSource(rows: (name, unit))` gives the growth rows and the check lines.
  - `E2ESource(arms, plant)` gives the pooled arms, the plant's arms and the claim lines. It maps `difference.mean`
    to `Interval.estimate` and `passed` to PASS / FAIL, and it never reads `spend_usd` or a title.
- **T4.** Front end.
  - v2 arm and policy names and styles (`cascade_v4_iso`, `always_g_v2t`, `always_c_v2t`); F1 as its own series.
  - A held-out chart, and pooled rows beside plant rows, each naming its interval method. The captions at
    `strings.js:85` and `:125` stop saying "Wilson" for every row.
  - Claim lines under each view, the infra table with its check lines, and the e2e table.
  - The "how it works" text with the `complete` rule and the need routing.
  - A route line in the answer card: the need label and the start tier.
- **T6.** `python -m plantgraph.demo.app replay-agreement`.
  - It runs the routed live cascade with `allow_paid_calls=False` on a **copy** of
    `data/runs/exp0008/m6a/cache.sqlite` (10.7 MB), and compares it with the frozen `join_corpus` + `decide_all`
    using `anchor_finder`.
  - Per question it compares `answered_by`, outcome and final answer, and it counts cache misses.
  - Its output records the result of the §2.3 E9 check.
- **T7.** Data and config, no library code.
  - `data/runs/exp0008/demo/demo_config.json` (2 plants, §1.1 B2–B4, results sources §4, cap $5.0).
  - The example files (§5.1) and the presentation ids (§5.2).
  - The drawing export to `data/runs/exp0008/demo/drawings/<c>`.
  - The calls log `data/runs/exp0008/demo/calls.jsonl`.
  - `demo_config.example.json` for v2, plus a v1 example.

**Test notes.**

- **T1.**
  - Equivalence: for every label and every outcome / rows / abstain / truncated combination on a two-tier toy,
    `decide(original, label)` equals `decide(derived[start], None)` in `answered_by`, `tiers_tried`, cost and
    latency.
  - It refuses `last_tier_by_label`.
  - "To isolate X from all upstream…" routes to start 1. "To cut X off from all downstream…" and "Before
    maintenance on X, … every incoming flow?" route to 0. The toy view is `tests/qa_need_toy.py`.
- **T3a.**
  - The v1 config still parses and gives today's view.
  - Fixtures cut from the EXP-0008 shapes:
    - pooled ids are present only in `sheets`;
    - a plant row takes its sheets from the corpus;
    - an unknown plant gives a clear error;
    - two sealed sources merge;
    - the ladder `common` and `all` scopes both work.
- **T3b.**
  - The infra fixture has `ingest.build_total` shown in s and `store.data_bytes` in bytes; an unknown name gives a
    clear error; M1 FAIL appears as a check line.
  - The e2e fixture: `mean` is mapped; `spend_usd` is absent from the view.

**Order and effort.**
- Order: T1 → T2 → T5 → T3 (T3a, then T3b) → T4 → T6 → T7.
- T1 and T2 alone already give a running V2T-A2 demo on H1000g21p1, with the v1 Results tab switched off (a partial
  result early).
- Effort estimate (not measured): 3 S + 5 M, about 2 coder days including review.

### 7.1 Verification after the code (free first)

| Step | What | Needs | Pass |
|---|---|---|---|
| F1 | ruff, mypy, pytest on the demo tests | nothing | green |
| F2 | freeze check against E9 (§2.3, three commands) | nothing | all hashes OK, no diff, no untracked frozen file |
| F3 | drawing export, H100g21p1 then H1000g21p1 | CPU | the `DrawingReport` self-check passes; time and PDF size recorded. The H1000g21p1 rebuild alone takes about 385.21 s (`infra/report.json` `growth` `startup.rebuild`) |
| F4 | server start with the v2 config; `/api/status`, `/api/results`, drawings, tag lookup | no Neo4j write | H1000g21p1 `ready`; H100g21p1 "other plant loaded", with its start-0 cascade derived and the notice shown; startup about 390.64 s at H1000g21p1 (`startup.total`); app RSS recorded (two opened cascades, risk R2) |
| F5a | T6 on routed questions only (10 per plant, §2.2) | nothing (the start-1 cascade opens no Neo4j source) | 100 % agreement on fully cached walks |
| F5b | T6 on all 280 H1000g21p1 questions | the `neo4j` database as it is (holds H1000g21p1, read-only Cypher); on mains power (EXP-0008 Threats: about 3× slower on battery) | agreement on every fully cached walk; misses explained (live deadline §2.3, Cypher timeouts near the 30 s limit) |
| F6 | ~~plant switch to the v2 main plant~~ **not needed**: Neo4j already holds H1000g21p1, the required end state (`run_all.log`, M10b) | — | — |
| F6' | optional, only to show H100g21p1 with its Cypher tier: switch to H100g21p1 in the UI, then back to H1000g21p1 | Neo4j writes; allowed by the user's rule as long as the database ends on H1000g21p1 | both `ready`; load times recorded (recorded `load_total` 3.22 s and 32.20 s); ends on H1000g21p1 |
| P1 | paid smoke: 3 questions per plant (one routed isolation, one Cypher-accepted lookup, one escalated flow path); H100g21p1 after F6' | user's approval | 6 answers; spend about 6 × 0.0025 = $0.015; cap $0.25; ends on H1000g21p1 |

**What to expect from F5.** INFRA's cache-only replays of `S7-AG-H100g21p1` and `S7-AG-H1000g21p1` were run from
the same `m6a` cache (`infra/runs/INF2-AG-<c>`).
- Their `final_answer`, `outcome` and `correct` equal the source run's on **280 / 280** questions for each plant
  (computed 2026-11-20).
- INFRA's M1 "byte-identical" check still FAILED. What differs beyond those three fields was not investigated, and
  it is outside the demo's scope.
- So the agent walks are expected to hit the cache.

## 8. Data model

```python
# src/plantgraph/demo/app/need_routing.py (T1)
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

# src/plantgraph/demo/app/config.py (T3a, T3b)
class LadderSource(BaseModel):  report: Path; result_row: str; scope: Literal["common", "all"] = "common"
class SealedSource(BaseModel):
    report: Path; result_row: str; label: str               # e.g. "V2T-A2", "F1, previous system"
    policies: tuple[str, ...]; scopes: tuple[str, ...] = ("headline",)
    corpora: tuple[str, ...]                                # pooled ids (S100, S1000) and/or configured plant ids
class InfraRow(BaseModel):      name: str; unit: Literal["count", "s", "bytes", "usd"]
class InfraSource(BaseModel):   report: Path; result_row: str; rows: tuple[InfraRow, ...]
class E2ESource(BaseModel):
    report: Path; result_row: str
    arms: tuple[str, ...] = ("R5", "V-d0", "V-d2", "V-d4"); plant: str | None = None
class ResultsSources(BaseModel):
    ladder: LadderSource | None = None; sealed: tuple[SealedSource, ...] = ()
    infra: InfraSource | None = None; e2e: E2ESource | None = None
    # before-validator: v1 flat keys (ladder_report, sealed_report, *_result_row) still accepted

# src/plantgraph/demo/app/results_views.py (T3a, T3b)
IntervalMethod = Literal["wilson", "two-stage bootstrap"]
class ClaimLine(BaseModel):  claim_id: str; verdict: str; text: str     # verdict as written (PASS/FAIL/REPORTED/NOT_RUN/FLAG)
# SealedRow gains: scope: str; source_label: str; pooled: bool; n_plants: int | None; interval_method: IntervalMethod
# SealedView: rows; claims: tuple[ClaimLine, ...]; sources: tuple[Provenance, ...]
# LadderView: scope Literal["common", "all"]; claims: tuple[ClaimLine, ...] (empty for a v1 report)
class InfraRowView(BaseModel): name: str; unit: str; from_corpus: str; to_corpus: str; from_value: float; to_value: float
class InfraView(BaseModel):    rows: tuple[InfraRowView, ...]; checks: tuple[ClaimLine, ...]; machine: str; source: Provenance
class E2EArm(BaseModel):       label: str; corpus: str; n: int; n_correct: int; accuracy: Interval; interval_method: IntervalMethod
class E2EView(BaseModel):      arms: tuple[E2EArm, ...]; claims: tuple[ClaimLine, ...]; source: Provenance
# ResultsView gains: infra: InfraView | None; e2e: E2EView | None
```

- **Row rules.** A row is `pooled` when its corpus id is a key of `sealed.scales`. Pooled rows use the two-stage
  bootstrap and plant rows Wilson; this follows the reports' notes. `n_plants` is the length of the scale's list.
- **`DemoAnswer`** (`api_models.py:93`) gains `need_label: str | None` and `start_tier: str | None`.

## 9. Files

- **New:**
  - `src/plantgraph/demo/app/need_routing.py`, `replay_agreement.py`, `results_views.py`, `results_reports.py`;
  - `tests/test_demo_need_routing.py`, `tests/test_demo_replay_agreement.py`, `tests/test_demo_results_v2.py`;
  - `data/runs/exp0008/demo/`: config, examples, drawings and calls log.
- **Changed:**
  - `demo/app/live_cascades.py`, `corpus_runtime.py`, `jobs.py`, `api_models.py`, `config.py`, `results.py`,
    `state.py` (or the module split out of it), `__main__.py`;
  - `static/results_data.js`, `results.js`, `results_tables.js`, `strings.js`, `answer.js`, `labels.en.json`;
  - `demo_config.example.json` and the matching `tests/test_demo_*.py`.
- **Unchanged:** every path hashed in `data/runs/exp0008/prereg/E9.sha256`, which includes `qa/need/`,
  `qa/anchors.py`, `qa/cascade/`, `pyproject.toml` and `uv.lock`. Also `data/runs/cv1/demo/*` (the v1 config stays
  runnable).

## 10. Open questions for the user (recommendation first)

1. **Routing in the demo**: a demo-side router, with no frozen file touched (ADR-0064 §1 A). Accepted 2026-11-05.
2. **Plants**: H1000g21p1 main, H100g21p1 small. Decided 2026-11-20.
3. **Neo4j end state**: H1000g21p1 (`plant_lines`), already reached. No switch is needed.
4. **Results tab**: v2 only. Accepted 2026-11-05, plus the e2e table (2026-11-20). The ladder scope is now
   `common`, following EXP-0008's report (ADR-0064 amendment point 9).
5. **Presentation picks**: the declared first-of-family rule, with the isolation refinement (amendment point 10).
   It is kept even if a rehearsal answer is wrong. Accepted.
6. **v1 demo**: kept runnable. Accepted.
7. **Startup of about 6.5 min at H1000g21p1** (`startup.total` 390.64 s): accepted; start the server early.
8. **Paid smoke P1** (about $0.015, cap $0.25), after F1–F5 (and F6' if H100g21p1 is shown live with Cypher).
   Recommended when the free checks pass.

None of these needs a new answer from the user.

## 11. Risks

- **R1. The live deadline.** The live deadline effect (§2.3) makes some escalated answers differ from R5's offline
  walk. T6 measures it.
- **R2. Memory.** Two opened cascades per corpus build the agent strategy twice over the same view.
  - INFRA measured one item graph at 282,534,546 B (`memory.item_graph_bytes`, H1000g21p1) and an app peak of
    1,827,717,120 B with one cascade.
  - The machine has 15.4 GiB RAM (`machine_summary`).
  - The second cascade's real cost is unmeasured. F4 records it.
- **R3. The freeze covers everything outside the demo.** E9 freezes all of `src` outside the demo, and
  `pyproject.toml` / `uv.lock`. Any helper the demo "needs" in `qa/` must be written in `demo/` instead. Any new
  library is out.
- **R4. The 1,000-sheet drawing is unmeasured.** The v2 drawing at 1,000 sheets is unmeasured (F3). A self-check
  failure would block B13.
- **R5. Provider prices.** Prices may have moved since EXP-0008. The estimate reads records, and the cap still
  bounds spend.
- **R6. The small plant runs without its Cypher tier.** H100g21p1 is not in Neo4j, so its start-0 cascade runs
  derived until F6'. A presenter must either switch, or let the card's notice explain why the Cypher tier is
  missing.

## 12. Sources

- **Frozen code:**
  - `src/plantgraph/qa/cascade/live.py`, `live_build.py`, `accept.py`, `policy.py`, `labels.py`, `join.py`,
    `report.py`, `policies_v2t/cascade_v4_iso.json`;
  - `src/plantgraph/qa/need/rules.py`;
  - `src/plantgraph/graph/schema_vocabulary.py`.
- **Demo code:** `src/plantgraph/demo/app/*.py` and `static/*`, as cited.
- **EXP-0008 scripts and freeze:**
  - `data/runs/exp0008/stages/m3_freeze.sh`, `m6_sealed.sh`, `m7_infra.sh`, `m10_audit_reports.sh`;
  - `lib.sh`, `lib_plants.sh`, `run_all.log`;
  - `prereg/E9.commit`, `prereg/E9.sha256`, `freeze/frozen_files.txt`.
- **EXP-0008 data:**
  - `questions/<c>/`, `neo4jplant/<c>/ingest.json`, `corpora/<c>/ingest.json`;
  - `m6a/runs/`, `m6b/runs/`, `infra/runs/INF2-AG-<c>`.
- **EXP-0008 reports:** `reports/sealed/report.json`, `reports/f1_baseline/report.json`,
  `reports/ladder/report.json`, `reports/e2e/report.json` (and its `report.md` title), `infra/report.json`.
- **Notes:**
  - `docs/private/30-experiments/EXP-0008-v2-rerun.md`, `_results.md:9`;
  - `docs/private/40-design/review-fixes.md:128`, `:473-481`;
  - ADR-0056:118, ADR-0063 point 3, ADR-0065 line 6.
