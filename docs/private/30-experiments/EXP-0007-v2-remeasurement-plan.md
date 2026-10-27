---
exp: 0007
date: 2026-10-27
question: Does the scale dependence measured on v1 (EXP-0001 ladder, EXP-0002 sealed test) reproduce on realistic v2 plants, with the system frozen at F1?
status: plan and pre-registration (proposed; R3 measured, everything else not run)
protocol: ADR-0060 (proposed), applying ADR-0054 to R4 and ADR-0053 to R5; design generator-v2-realism.md §13, generator-v2-pid-vocabulary.md §14.5
---

# EXP-0007 — v2 re-measurement R1–R5: plan and pre-registration

## 0. Recommendation

1. Run the free gates first, in this order: R0 (in progress), R1, R2, and R3 (done here, §4).
2. Build four small tasks (§10). The one that matters is **RM-T1**: ADR-0058's accepted CLASS_NAME list for v2,
   which does not exist at HEAD.
3. Re-run the F1 replay guards at the new commit.
4. Run the 10-question paid pilot on D100g2 (cap $0.10).
5. The user makes the freeze commit **E7**.
6. Run R4 (the ladder, ContextRAG at high effort only), then R5 (sealed, plus the required d0/d50 points).

Pre-pilot estimate: **R4 ≈ $10.4–16.0, R5 ≈ $2.4–7.2.** Pre-pilot caps: R4 $20.81 (incl. the $0.10 pilot), R5 $9.49. The R4 gate stops
at a projected ContextRAG remainder above $15. Most of R4's cost is one cell: ContextRAG at H30g2, ≈ $8.0–11.9.

## 1. What each run answers (link to the claim)

| Run | Paid | Answers | Claim it serves |
|---|---|---|---|
| R1 composition | no | v2 is realistic by the declared bands (ADR-0059) | precondition: the corpus is defensible |
| R2 availability | no | every k-bin and family still has candidates on v2 (ADR-0029) | precondition: the x-axis exists |
| R3 prompt size | no | what ContextRAG costs on v2 and where it stops fitting | X5 (the wall), cost of R4 |
| pilot | yes, ≤ $0.10 | t_v2 / t_v1 for the two tiers | caps of R4 and R5 |
| R4 ladder | yes | does the single-sheet end reproduce on realistic sheets (X1–X5) | the "function of corpus scale" half |
| R5 sealed | yes | does the plant-scale end reproduce (Q4 primary; K1–K3, Q5; d0/d50) | the "inverts at plant scale" half |

R0 (scale smoke) and R6 (resolver on v2 variants) are not part of this plan. R0 is being run by the main session;
R6 is free and comes later.

## 2. F1 at HEAD: what is frozen and how it is identified

**Frozen** (F1 = commit `07d4029`, `data/runs/sealed/F1.commit`):
- code on the system side;
- the eight prompt templates;
- the pins and params in `data/runs/sealed/inputs/*.json` (hashes in `F1.sha256`);
- the policies `src/plantgraph/qa/cascade/policies/*.json`, with `cascade_v3` as the primary;
- cutoff 120 s, concurrency 4, deadlines 120 s for the tiers and 300 s for ContextRAG.

**Measured today at HEAD `917b4c3` (no API call, no Neo4j):**

| Check | Result | How |
|---|---|---|
| System-side paths changed since F1 | only `qa/final_answer.py` (CLASS_NAME pinned to `V1_NODE_CLASSES`, text-identical on v1); gold side `qa/harness/{gold,family_meta,need_gold}.py` | `git diff --name-only 07d4029 HEAD --` over the list below |
| Prompt hashes of a run at HEAD | all eight equal to ST-AG-H100's `run_config.json` (e.g. `final_answer.txt` `f9e22b90…`, `cypher_query.txt` `117d36cd…`, `agent_graph_system.txt` `59a6a950…`) | replay `run_config.json` |
| Cache-only replay ST-AG-H100 (580 rows, sealed cache copy) | **byte-identical** | harness without `--allow-paid-calls` into the session scratchpad, then `cmp` after the run-id/from_cache normalisation of `lib.sh replay()` |
| Replays E1-CTXH-H1 (70), E1-CTXH-H30 (96), E1-AG-H1 (70), E1-AG-H30 (96) | **all byte-identical** | same, with a copy of `cache_exp0001.sqlite` |
| Cypher tier replay | **not run** (needs Neo4j) | gate S0-d below |

Neither the sealed records nor the EXP-0001 records were touched: the replays wrote only to the scratchpad.

**System-side path list** (must show no diff since F1 except the named file):
- directories: `src/plantgraph/qa/{strategies,agent,plant_api,prompts,cascade,need}/`, `src/plantgraph/llm/`,
  `src/plantgraph/store/`;
- modules: `src/plantgraph/qa/{serialize,schema_text,neo4j_view,cypher,graph_view,final_answer,primer,fit,scoring,
  context_render,context_budget,anchors,routing,sheet_selection,unit_router,local_timer}.py`;
- the harness: `src/plantgraph/qa/harness/`, except `gold.py`, `family_meta.py` and `need_gold.py`;
- named exception: `qa/final_answer.py`, for RM-T1 only.

**What differs by design on v2 corpora:**
- the Cypher schema text: `qa/schema_text.py` is unchanged code, and it lists the labels of the corpus's load plan;
- the CLASS_NAME list, after RM-T1.

Both are inputs, not code. The sha256 of each v2 corpus's CLASS_NAME instruction and schema text is written into
`E7.sha256` / `T7.sha256`.

**Gates S0 (free; re-run at commit E7, because RM-T1 touches `final_answer.py`):**
- (a) the path check above;
- (b) `sha256sum -c data/runs/sealed/F1.sha256`; the four input files `cmp`-equal to `data/runs/sealed/inputs/`;
  `git diff --quiet 07d4029 E7 -- src/plantgraph/qa/cascade/policies`;
- (c) the five replays above, byte-identical;
- (d) load EXP-0001's H1 alone (`ingest synthetic --headline --target-sheets 1 --seed 104 --store-profile plant
  --fresh-database`), then replay E1-CYP-H1 cache-only: byte-identical;
- (e) Luna's listing equal to `inputs/listing_E7.json`. Read today, it equals `exp0001/inputs/listing_E.json`:
  $0.10/M prompt, $0.50/M completion, step at 272,000 prompt tokens to $0.20 / $0.75, max prompt 922,000,
  `input_cache_write` $0.125/M.

Any failure stops the protocol (ADR-0053 §10).

## 3. Free gates R1 and R2 (main session; commands)

Outputs go to `data/runs/exp0007/{r1,r2}/`. Each run note goes to `30-experiments/`.

**R1 — composition and S16.**
```
.venv/Scripts/python -m plantgraph.benchmark.v2.composition --target-sheets 100 --seeds 1 2 3 --corpus --json data/runs/exp0007/r1/D100g2_s123.json
.venv/Scripts/python -m plantgraph.benchmark.v2.composition --target-sheets 1000 --seeds 1 --corpus --coverage --json data/runs/exp0007/r1/D1000g2.json
.venv/Scripts/python -m plantgraph.ingest synthetic --headline-v2 --target-sheets 100 --seed 1 --check --no-neo4j --out data/runs/exp0007/r1/D100g2
.venv/Scripts/python -m plantgraph.ingest synthetic --headline-v2 --target-sheets 1000 --seed 1 --check --no-neo4j --out data/runs/exp0007/r1/D1000g2
```
- **Pass:** every pass/fail band of ADR-0059 / vocabulary §14.6 passes, and coverage at D1000g2 is 77 / 77.
- **Pass:** `ingest.json` shows `gate_equal == true`, and `resolution_score.identity` precision = recall = 1.0
  (G1 and S16).
- A failing band becomes tuning round 2 (2 rounds left), never a silent edit.
- The `--check` ingests double as R2's input. If R0 already wrote them, reuse those.

**R2 — availability (ADR-0029 per-bin gate), dev families only.**
```
.venv/Scripts/python -m plantgraph.qa.questions --corpus-id D100g2 --ingest-json data/runs/exp0007/r1/D100g2/ingest.json --seed 1 --n-per-bin 97 --n-unanswerable 97 --out data/runs/exp0007/r2/D100g2
.venv/Scripts/python -m plantgraph.qa.questions --corpus-id D1000g2 --ingest-json data/runs/exp0007/r1/D1000g2/ingest.json --seed 1 --n-per-bin 97 --n-unanswerable 97 --out data/runs/exp0007/r2/D1000g2
```
- **Pass:** bins 0, 1 and 2 are powered (≥ 97 candidates after the per-anchor cap) at both sizes.
- **Pass:** every dev family has ≥ 20 candidates at D100g2, and the ten pilot families (§5) have ≥ 1.
- Reported, not gated: the k and u histograms, the highest powered bin, and the build seconds. ADR-0029's
  criterion is 600 s at ~1,000 sheets; the stale pre-T13 R0 measured 2,736 s for D1000g2 question generation,
  vocabulary §14.5.
- Held-out families cannot be counted here: `sealed_set` refuses dev ids by design (ADR-0035). Their counts
  appear in `availability.json` at T7 under the pre-registered rule of §7.

## 4. R3 — ContextRAG prompt size on v2 (measured 2026-10-27; free)

**Method.**
- Corpora built with `ingest synthetic --headline-v2 --target-sheets N --seed S --no-neo4j`, into the session
  scratchpad.
- Serialized with the frozen `serialize_occurrence_graph(NetworkxGraphView(...))`, exactly the EXP-0001 gate's
  code path.
- **Prompt chars** = serialized chars + 2,087. That is the measured prompt frame: real EXP-0001 prompt chars minus
  serialized chars, 2,089 at H1 and 2,085 at H30. PROMPT-04's 768 predates the primer.
- **Tokens** = 0.39414 × prompt chars − 185. This is a least-squares fit over all 348 EXP-0001 ContextRAG calls,
  which gives 2.54 chars per token (X5's r).
- **Validated** on the v1 EXP-0001 corpora: H1 35 nodes and H30 1,223 nodes, both equal to the report. H30 gives
  16,403 chars per sheet, against X5's fitted 16,435.

**Seeds — no test seed was used.**
- 1-sheet: the first three seeds in 600–899 whose one-unit plan is one sheet (`first_single_sheet_seed`): 604,
  615 and 616.
- 3 / 10 / 30 / 100 sheets: seeds 1, 2 and 3, with nested prefixes per seed like the H-ladder.
- These are dev seeds (ADR-0059: 0–999). The registered test corpora (5100, 5001, 5002, 5003) were not generated,
  so no record now contains a test plant.
- **The difference this makes:** the figures below are a sample of v2 plants of the same size and preset, not the
  exact test plants. The exact prompt size of every H corpus is computed by the free gate at E7 / T7, after the
  freeze and before the first paid call. That figure replaces these for the caps.

| Corpus | Sheets | Occurrence nodes | Prompt chars | Chars / sheet | Chars / node | Est. prompt tokens | > 272k | Fits 922k |
|---|---|---|---|---|---|---|---|---|
| X1g2s604 | 1 | 111 | 46,925 | 46,925 | 403.9 | 18,310 | no | yes |
| X1g2s615 | 1 | 80 | 34,838 | 34,838 | 409.4 | 13,546 | no | yes |
| X1g2s616 | 1 | 104 | 44,649 | 44,649 | 409.2 | 17,413 | no | yes |
| D3g2 | 3 | 246 | 101,171 | 33,724 | 402.8 | 39,691 | no | yes |
| X3g2s2 | 3 | 225 | 93,597 | 31,199 | 406.7 | 36,705 | no | yes |
| X3g2s3 | 4 | 263 | 108,729 | 27,182 | 405.5 | 42,669 | no | yes |
| D10g2 | 10 | 993 | 400,617 | 40,062 | 401.3 | 157,714 | no | yes |
| X10g2s2 | 11 | 1,140 | 460,609 | 41,874 | 402.2 | 181,359 | no | yes |
| X10g2s3 | 10 | 816 | 330,481 | 33,048 | 402.4 | 130,071 | no | yes |
| D30g2 | 31 | 2,976 | 1,208,249 | 38,976 | 405.3 | 476,034 | **yes** | yes |
| X30g2s2 | 31 | 3,191 | 1,294,186 | 41,748 | 404.9 | 509,905 | **yes** | yes |
| X30g2s3 | 31 | 2,680 | 1,089,503 | 35,145 | 405.8 | 429,232 | **yes** | yes |
| D100g2 | 100 | 9,694 | 3,948,282 | 39,483 | 407.1 | 1,555,991 | yes | **no** |
| X100g2s2 | 101 | 9,830 | 4,002,955 | 39,633 | 407.0 | 1,577,540 | yes | **no** |
| X100g2s3 | 100 | 9,116 | 3,714,719 | 37,147 | 407.3 | 1,463,934 | yes | **no** |

**Reading.**
- **A v2 sheet serializes to about 2.4× a v1 sheet.** At 100 sheets it is 37,147–39,633 chars, against 16,435
  on v1. Characters per node are unchanged (401–409 against v1's ~400, PROMPT-04), so the growth is node count:
  96.9 occurrence nodes per sheet on D100g2 against 40.2 on v1 H100 (4,059 / 101, PROMPT-04).
- **The context wall moves from ~143 sheets (v1, X5) to ~56–63 sheets** (59.3 at D100g2's density).
  - At 922,000 tokens the wall is 2,339,740 prompt chars.
  - H100g2 does not fit; that is measured on three 100-sheet plants, not assumed.
  - H1000g2 is not measured here. Extrapolated at ~39k chars per sheet it is ~39M chars, far past the window.
    The main session can measure it free by running the R3 script on R0's D1000g2 `ingest.json`.
- **The 272,000-token price step falls at ~16.5–18.6 sheets** (690,579 chars). On v1 it fell at about 42 sheets.
  H10g2 stays below it and H30g2 is above it, so H30g2's ContextRAG questions are billed at the higher step price.
- The script is `scratchpad/r3_chars.py` in this session. RM-T3 ports it as a `prompt-size` subcommand so the
  E7 / T7 gates run the same computation.

## 5. Pilot — t_v2 / t_v1 (paid, staged, ≤ $0.10)

- **Corpus:** D100g2 (dev, seed 1). It is loaded alone into Neo4j with the plant profile for the Cypher tier; the
  agent tier reads `ingest.json`.
- **Questions:** one per family from 10 dev families, drawn once.
  - Draw: `python -m plantgraph.qa.questions --corpus-id D100g2 … --seed 1 --n-per-bin 97 --n-unanswerable 97`,
    then `per_family --n 1 --seed 20261101`, filtered to the 10 families.
  - Families:
    - the five most token-heavy for the agent on v1: UPSTREAM_ISOLATION, CROSS_UNIT, UPSTREAM_SOURCES,
      LOOPS_NEAR_ITEM, DOWNSTREAM_IN_UNIT;
    - three where v2 changes the answer's neighbourhood: FLOW_PATH (fittings stepped over),
      INSTRUMENTS_OF_ITEM, LOOP_MEASURED_EQUIPMENT;
    - two light ones: LOOKUP_TYPE (exercises RM-T1) and SHEETS_OF_TAG (A/B spares).
  - Reserve, in order, if R2 shows a family with 0 candidates: NEIGHBOURS_DOWNSTREAM, SAME_UNIT, CONNECTED.
- **Arms:** both frozen tiers, `P7-CYP-D100g2` and `P7-AG-D100g2`, with the sealed pins and params, concurrency
  4, deadline 120 s.
  - Each tier runs a 2-question smoke (cap $0.01), then the full 10 questions (cap $0.05).
  - Pilot total cap: **$0.10**. Expected spend: 10 × ($0.00042 + $0.00063) × [1, 3] = $0.011–0.032.
- **v1 baseline:** no new calls (ADR-0060 6B). The per-family means of all calls of `data/runs/cv1/runs/AGL3-D100`
  and `CYPL2-D100` (10 questions per family, F1 prompt hashes, Luna pins), over the 10 pilot families:
  - agent Σ t̄_v1 = **99,407** tokens: 16,824 + 15,022 + 14,226 + 12,615 + 11,042 + 8,624 + 5,538 + 7,363 + 4,194
    + 3,959;
  - Cypher Σ t̄_v1 = **20,787**: 2,468 + 2,060 + 1,760 + 2,090 + 2,569 + 2,621 + 1,674 + 1,891 + 1,890 + 1,764.
- **Estimator, per tier:** R_tier = Σ_f T_v2(f) / Σ_f t̄_v1(f). T counts prompt + completion tokens of every call
  of the question (`answers.jsonl` fields plus `retrieval_usage`). The same ratio is also computed on $, and the
  larger of the two goes into the caps.
- **Stop rules:**
  - the health rule fails (PROVIDER_ERROR + PARSE_FAILURE > 10 %, or RETRIEVAL_ERROR > 60 %) → stop, read the
    logs, ask;
  - R_tier > 3.0 → recompute every cap, show it, ask before E7.
- Correctness is recorded, but no system change may follow before R5 (F1; ADR-0057 Q2).

## 6. R4 — the ladder on v2 (ADR-0054 protocol)

- **Corpora:** registered test seeds from `TEST_SEEDS_V2`, at preset duplication 0.25:
  - H1g2 = seed 5100, recorded in ADR-0059 before generation;
  - H3g2, H10g2, H30g2 = seed 5001, one plant with nested prefixes.
  - Each is built after E7 with `--check --no-neo4j`. G1 and identity P = R = 1.0 are asserted, and the script
    dies otherwise.
- **Questions:** the EXP-0001 recipe unchanged:
  - `sealed_set --seed 41 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 1 --sample-seed
    20261101`, then `per_family --only-splits dev-old,dev-new,held-out --n 4 --seed 20261101`;
  - **at most 92 per size** (23 families × 4; FIRST_MEETING_POINT unavailable);
  - v1 had 70 / 87 / 95 / 96 including FIRST_MEETING_POINT 0 / 1 / 4 / 4 (`data/runs/exp0001/questions/*`);
  - drawn once and hashed into `E7.sha256` before any call.
- **Arms:** `E7-CTXH-<c>` (context_rag, `pin_agent_luna_final_high`), `E7-CYP-<c>`, `E7-AG-<c>`, and cascade_v3
  as an offline join. **No ctx-low** (ADR-0060 4B). No EX01.
- **Claims:**
  - X1 (primary), X2, X3 and X4 exactly as EXP-0001 design §7, on the v2 ladder ids and the common-family scope;
  - X5 with r and c measured on the v2 runs, and the H100g2 / H1000g2 chars from the T7 corpora;
  - X6 "not run on v2 (ADR-0060), see EXP-0001";
  - stage C "not applicable on v2: H100g2 does not fit (R3, then T7)";
  - LOOP_ACTUATED_VALVE stays out of the headline and appears in the per-family tables (ADR-0044 U2).
  - Reported, not claimed: v2 − v1 per arm and size (unpaired, Wilson CIs).
- **Commands:**
  - `data/runs/exp0007/make_set.sh` (free; after E7; writes `E7.commit`, `E7.sha256`, `caps_r4.json` hash);
  - `data/runs/exp0007/run_ladder.sh` (paid). Copied from `data/runs/exp0001/run_exp0001.sh` with these changes:
    v2 ids, the `ingest synthetic --headline-v2` load with `--store-profile plant --fresh-database --neo4j-home
    "$H"`, the ctx-low and EX01 steps removed, the ContextRAG smoke extended to H30g2, and caps read from
    `caps_r4.json`.
  - Order:
    1. S0 guards;
    2. Cypher tier per size, one corpus in Neo4j at a time, each with its replay;
    3. agent tier;
    4. ContextRAG smoke, 2 questions at H1g2 and 2 at H30g2, then the gate;
    5. full ContextRAG H1g2 → H3g2 → H10g2 → H30g2, each with a cache-only replay;
    6. report: `python -m plantgraph.qa.exp0001 report --root data/runs/exp0007/ladder --sizes
       H1g2,H3g2,H10g2,H30g2 --wall-chars …` (RM-T3);
    7. the `cascade report` cross-check;
    8. restore D1000 (v1, plant), as every earlier script did.

## 7. R5 — the sealed test on v2 (ADR-0053 protocol)

- **Corpora**, generated only at R5 time, at commit E7, by `data/runs/exp0007/make_test_set.sh`:
  - H100g2 = seed 5002, H1000g2 = seed 5003;
  - H100g2d0 and H100g2d50 = seed 5002 at duplication 0 and 0.5 (`--headline-duplication-rate`);
  - all with `--check --no-neo4j`, asserting G1 and identity P = R = 1.0.
- **Questions:** the EXP-0002 recipe unchanged:
  - `sealed_set --seed 31 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 10 --sample-seed
    20261031`, on each of the four corpora;
  - C1 subset: `per_family --only-splits dev-old,dev-new,held-out --n 2 --seed 20261031` on H1000g2, 46
    questions;
  - expected **560 per corpus**: 18 dev × 20, 5 held-out × 20, 10 wordings × 10;
  - headline scope ≈ 440: without wordings, LOOP_ACTUATED_VALVE and FIRST_MEETING_POINT;
  - a family with fewer than 20 candidates uses all of them and n is reported; a family with 0 is dropped and
    reported before any run (ADR-0053 decision 3, §10 point 4).
- **Arms:** `S7-CYP-<c>` and `S7-AG-<c>` on all four corpora, plus `S7-AG-H1000g2-C1` at concurrency 1 with its own
  cache. ContextRAG is not run: the fit check records `DID_NOT_FIT` at H100g2 and H1000g2 (ADR-0038, measured by
  R3 / T7).
- **Claims:** ADR-0053 decision 6 on H100g2 → H1000g2.
  - **Q4 for cascade_v3 is primary.** K1, K2, K3, Q4′ and Q5 are secondary.
  - Every claim is computed on the headline set and again on the five held-out families.
  - Reported, not claimed:
    - acc@120 of cascade_v3 at d0 / d25 / d50 with Wilson CIs, and the paired Δ on common question stems
      (RM-T3);
    - v2 − v1 per policy.
- **Commands:**
  - `make_test_set.sh` (free; writes `T7.sha256` and `caps_r5.json`);
  - `run_sealed.sh` (paid). Copied from `data/runs/sealed/run_sealed.sh` with this order: H100g2 Cypher smoke →
    full → replay, H1000g2 Cypher, d0 and d50 Cypher; agent smoke → H100g2, H1000g2, C1, d0, d50; replays;
    restore D1000;
  - `python -m plantgraph.qa.cascade report --sealed-claims … --corpus H100g2 --corpus H1000g2` (the d0 / d50
    corpora go into a second, descriptive report).

## 8. Cost estimate, caps and stop rules

**Measured inputs** (computed from the run files, all calls of a question included):

| Input | Value | Source |
|---|---|---|
| Cypher tier $/q, v1 | 0.00040–0.00042 (ladder), 0.00042 / 0.00041 (H100 / H1000) | `data/runs/exp0001/runs/E1-CYP-*`, `data/runs/sealed/runs/ST-CYP-*` answers.jsonl |
| Agent tier $/q, v1 | 0.00033–0.00056 (ladder), 0.00063 / 0.00069 | `E1-AG-*`, `ST-AG-*` |
| ctx-high mean completion tokens, v1 | 234 / 611 / 1,192 / 1,326 (H1 / H3 / H10 / H30) | `E1-CTXH-*` |
| Billed prices below the step | **$0.125/M prompt, $0.50/M completion** (least squares over 513 ContextRAG rows; equals the listing's `input_cache_write`, not its $0.10 prompt) | `E1-CTX*` answers.jsonl; listing read 2026-10-27 |
| Price above 272k tokens | listed $0.20/M prompt, $0.75/M completion. **Billed: unmeasured.** The range uses $0.20 (low) to $0.25 (×1.25 as below the step, high) | listing |
| v2 prompt tokens per size | 13,546–18,310 / 36,705–42,669 / 130,071–181,359 / 429,232–509,905 | R3, §4 |

**Pre-pilot ranges** (a range from v1 numbers and R3, not a measurement). The tier correction factor is assumed to
lie in [1.0, 3.0]. The anchor is the measured node-density ratio of 2.41 (§4), with a 1.25 margin.

| Stage | Formula | Range |
|---|---|---|
| ContextRAG-high H1g2 | n × (tokens × p_in + completion × p_out); n 70–92, completion × 1–2 | $0.13–0.23 |
| H3g2 | n 86–92 | $0.42–0.55 |
| H10g2 | n 91–92 | $1.53–2.20 |
| **H30g2** | n 92, above the step | **$7.99–11.91** |
| R4 tiers | 4 sizes × n × c_q,v1 × [1, 3] | Cypher $0.14–0.46, agent $0.19–0.62 |
| **R4 total** (incl. pilot) | | **≈ $10.4–16.0** |
| R5 H100g2 + H1000g2 | 560 × (c_cyp + c_ag)_v1 × [1, 3] | $1.20–3.61 |
| R5 d0 + d50 | 2 × 560 × (c_cyp + c_ag)_H100 × [1, 3] | $1.18–3.53 |
| R5 C1 control | 46–48 × c_ag × [1, 3] | $0.02–0.10 |
| **R5 total** | | **≈ $2.4–7.2** |

For comparison, the dropped ctx-low arms (H1g2 + H10g2) are estimated at $1.61–2.34.

**Caps.** Pre-pilot values are below. The final values come from the formula
cap = ceil₀.₀₅(1.3 × n × ĉ_q), with:
- ĉ_q for the tiers = c_q,v1 × max(R_pilot on tokens, R_pilot on $); for R5, R4's measured v2 tier $/q at H30g2
  instead of the pilot, if it is larger;
- ĉ_q for ContextRAG = the E7 gate's exact prompt tokens × the smoke's billed price.

The values are written to `caps_r4.json` / `caps_r5.json`, hashed, and shown to the user before the stage. The
harness then writes each into `run_config.json` before its first call.

| Run | Pre-pilot cap |
|---|---|
| Pilot (2 tiers: smoke + full) | $0.10 |
| E7-CYP-H*g2 ×4 (+ H1g2 smoke $0.01) | $0.15 each |
| E7-AG-H*g2 ×4 (+ smoke $0.02) | $0.20 each |
| ctx smoke H1g2 (2 q) / H30g2 (2 q) | $0.03 / $0.30 |
| E7-CTXH-H1g2 / H3g2 / H10g2 / H30g2 | $0.30 / $0.75 / $2.90 / $15.00 |
| **R4 sum of caps (incl. pilot)** | **$20.81** |
| S7-CYP-H100g2 / H1000g2 / d0 / d50 | $0.90 each |
| S7-AG-H100g2 / d0 / d50 | $1.40 each |
| S7-AG-H1000g2 | $1.50 |
| smokes (2) / C1 | $0.02 each / $0.15 |
| **R5 sum of caps** | **$9.49** |

**Stop rules.**
1. **Listing changed.** The listing differs from `listing_E7.json` on the run day → stop, re-estimate, ask.
2. **Pilot.** The pilot fails health, or R > 3.0 → stop and ask.
3. **Cap reached.** A full-stage run reaching its cap (exit 3) → stop. It resumes under the same id only after the
   user approves a higher cap. A smoke ending at its cap is normal.
4. **ContextRAG gate.** It runs after the two smokes and projects the remaining ContextRAG cost from the measured
   billed price, the output tokens and the exact E7 prompt sizes. Projection > **$15.00**, or a billed
   above-step prompt price > $0.25/M → stop and ask.
5. **Health and abort.** Tiers follow the sealed rule. For ContextRAG, PROVIDER_ERROR > 10 % stops the run;
   PARSE_FAILURE > 50 % in a smoke stops it; TIMED_OUT and DID_NOT_FIT are results. A second technical abort on
   the same run stops the protocol (ADR-0053 §10, EXP-0001 §9.4).
6. **Balance.** The OpenRouter balance must cover a stage's sum of caps before the stage starts.

## 9. Sealed-test hygiene (R4 and R5)

1. **Seeds fixed before generation.**
   - `TEST_SEEDS_V2` = {1: 5100, 3/10/30: 5001, 100: 5002, 1000: 5003} is committed (917b4c3) and recorded in
     ADR-0059.
   - Each make script asserts the table and refuses if a seed in 5000–5999 appears in any earlier
     `run_config.json` / `ingest.json` under `data/` (`grep`), which is ADR-0059's revisit trigger.
   - R3 used dev seeds only.
2. **Generated once, after the freeze.**
   - The H-ladder is generated after E7 and H100g2 / H1000g2 / d0 / d50 at R5 time, at E7.
   - The scripts never overwrite: they refuse if `E7.sha256` / `T7.sha256` exists.
3. **Frozen before any system sees them.**
   - `questions.jsonl`, `splits.json`, `availability.json`, every `ingest.json`, the per-corpus CLASS_NAME and
     schema-text hashes, and `caps_*.json` are hashed into `E7.sha256` / `T7.sha256` by the same script that drew
     them, before any harness call.
   - The run scripts check `sha256sum -c` in preflight.
4. **Pre-registered here.**
   - FIRST_MEETING_POINT is unavailable on v2, because streams join at tees, not items (ADR-0059 point 6). It is not
     redefined or replaced.
   - The held-out comparison runs over the other five held-out families.
   - The headline scope also excludes LOOP_ACTUATED_VALVE.
5. **Who may look at what.**
   - The coder never opens test corpora or questions.
   - Until the frozen report code has produced the report, the main session and the architect read only outcome
     counts (health) and `availability.json` counts, never answers or correctness.
   - The composition CLI's `--allow-test-seed` is used only after R5's report exists, labelled descriptive.
   - No LLM call on a test question outside the registered runs; the demo stays on dev corpora.
   - No `src` change between E7 and the end of R5.
6. **No system change between R4 and R5,** whatever R4 shows (F1; ADR-0057 Q2). A v2 legend is a separately labelled
   system after R5.

## 10. Coder tasks (Sonnet, one at a time; v1 goldens and replays unchanged)

| # | Task | Files | Acceptance | Size |
|---|---|---|---|---|
| RM-T1 | CLASS_NAME on v2 (ADR-0058 point 5): a v2 corpus lists the node classes present in its load plan; v1 and Proteus-v1 keep the exact pinned text | `qa/final_answer.py` + the narrowest path that hands it the corpus's classes; every system file touched is named in the hand-over | existing pin tests; a v2 fixture lists its classes; S0 replays byte-identical | S–M |
| RM-T2 | `sealed_set` accepts `H<sheets>g2[d<rate>]`; still refuses D / X ids | `qa/questions/sealed_set.py` | tests for both | S |
| RM-T3 | EXP-0001 report on v2 (`--sizes` exists; add `--wall-chars ID=N,…`; X6 "not run" when no ctx-low); `prompt-size` subcommand (the R3 method); d0 / d50 paired-stem table | `qa/exp0001/*` | v1 report reproduced byte-identical from the EXP-0001 runs | M |
| RM-T4 | Scripts `data/runs/exp0007/{lib.sh,guards.sh,pilot.sh,make_set.sh,run_ladder.sh,make_test_set.sh,run_sealed.sh}` from the EXP-0001 / sealed templates | scripts only | `guards.sh` passes at the commit; dry run of every make script on X seeds into a temp folder | M |

## 11. Order of steps (the user commits)

1. R0 → R1 → R2. R3 is done.
2. RM-T1 … RM-T4, each committed by the user.
3. `guards.sh`, free.
4. Pilot, paid at $0.10 at most. Then `caps_r4.json`.
5. The user's **E7** commit: plan note and ADR-0060 accepted, scripts in.
6. `make_set.sh` → R4, paid, with the gate inside.
7. `caps_r5.json` → `make_test_set.sh` → R5, paid.
8. Run notes and `_results.md` rows.

## 12. Open questions (for the user)

1. **Accept ADR-0060**, in particular ContextRAG at high effort only on v2 (saves an estimated $1.6–2.3; X6 stays
   a v1 result). The recommendation is yes.
2. **Budget:** what is the OpenRouter balance now? R4's sum of caps is $20.81 (incl. pilot) and R5's is $9.49 (estimates $10.4–16.0
   and $2.4–7.2). The recommendation is a balance of at least $21 before R4 and at least $10 before R5.
3. **R4 ContextRAG gate at $15:** accept? It sits at the top of the pre-pilot range.
4. **d0 / d50 with the full 560-question recipe** (≈ $1.2–3.5), so they pair with H100g2. The alternative is 10 per
   family, about half the cost with wider CIs. The recommendation is the full recipe.
5. **EX01 on the v2 vocabulary** (`EX01v2`, ≈ $0.10, descriptive) is not planned; it is not a v2 plant. Add it?
   The recommendation is no.
6. **R0's question-generation time at D1000g2.** The stale figure is 2,736 s, against ADR-0029's 600 s. If the
   re-take is still above 600 s, it is reported as a deviation; it blocks nothing.

## 13. Sources

- Run files:
  - `data/runs/sealed/{F1.commit,F1.sha256,inputs/,runs/ST-*}`;
  - `data/runs/exp0001/{lib.sh,run_exp0001.sh,make_set.sh,inputs/listing_E.json,runs/E1-*,report/report.md}`;
  - `data/runs/cv1/runs/{AGL3-D100,CYPL2-D100}`.
- Notes: EXP-0001 and EXP-0002; `_results.md` PROMPT-04, AVAIL-01 and INFRA-1.
- R3, pilot baseline and price fit: scripts `r3_chars.py`, `tok_fit.py`, `ctx_rate.py` and `cost_stats.py` in this
  session's scratchpad, run 2026-10-27 at `917b4c3`.
- Luna listing: OpenRouter `models/openai/gpt-6-luna/endpoints`, read 2026-10-27.
