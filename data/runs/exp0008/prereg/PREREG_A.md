# EXP-0008 pre-registration, part A

Written 2026-11-10, before any EXP-0008 plant exists. Part B is written by the launcher at stage M3.

Frozen code commit: `476499d4753e32ebac8670cfc899b80f61c0d179`

Amended 2026-11-10, before any EXP-0008 plant exists: the commit was `9011adeef5de5cd3df4da123d676260beb67bf18`. The new commit changes only the freeze check (`freeze.py`, `readiness.py`, `m3_freeze.sh` and its test), so that later commits touching no frozen file, such as notes, keep this part valid; no measured behaviour changed.

Amended 2026-11-11, after the first G2 pilot and before any test plant was measured: the commit was `80c26618d4beb13c14c1a83568c2814d3b8c7d8e`. The run had passed M0, M1 (G1) and M2 and was stopped by hand in M4 while the 1-sheet ladder plant was being built; no test run had started. The first pilot printed G2 as passed on 8 of its 49 rows, which was wrong: 41 judge replies were not read (the judge wrote its working before the JSON object) and the gate counted judged rows only. Recomputed from the stored replies, G2 failed (known defects 8 of 29, controls 19 of 20). The failure path of G2 below was taken. What changed: the reply parser reads the judge's last JSON object; G2 counts every row of the pilot set, a row without a verdict as a miss; the excerpt of a VALVES_ON_PATH question now writes out the routes between its two parts (the judge could not follow routes of 100 to 490 parts from a cut excerpt); and the pilot's valve group keeps only rows whose answer is an item-level count (5 of its 21 rows were answers wrong under every reading, so not scorer defects). The pilot set is now 16 + 8 defect rows and 20 controls. The judge's prompt file and pin, and every claim, threshold, seed and gate rule of this part, are unchanged. The re-pilot runs on the same first-measurement rows only.

## 1. What is registered, and what is not

- Registered here, before any test plant exists: the claims and thresholds, the plant design and the
  aggregation, the gates G1 and G2, the audit rule, the money rule, the judge's prompt and pin, and the
  drawn test seeds.
- Measured later and registered in part B at stage M3, before the first test plant is built: the G1
  result, the identity thresholds tau1 and tau2, the judge pilot's cost per call and G2 result, the audit
  capacity that follows from it, and the E9 freeze hashes.
- A defect found after M3 is reported, not fixed, except through the audit rule of section 6.

## 2. Claims and thresholds

Every claim keeps the wording and the pass rule of its ADR; the ADR is the source, this list only names it.

| Claim | Source | Pass rule |
|---|---|---|
| Q4 (primary): 1,000 vs 100 sheets, unpaired across scales | ADR-0053 decision 6 | for `cascade_v4_iso` (carried to V2T by ADR-0060/0061): "acc diff CI contains 0 or lies above **and** e < 0.5" (sealed-test-run §9); not supported: "accuracy falls with scale" / "cost grows near-linearly with the plant" |
| K1, K2, K3, Q5 | ADR-0053 / ADR-0046 / ADR-0048 | K1 (cascade against always-agent): "acc CI contains 0 or lies above, **and** mean cost and mean latency both lower (CIs exclude 0)". K2 (self-flags against chance): "cascade − random escalation at the same tier-2 share > 0, CI excludes 0". K3 (latency bound at plant scale): "LB-1 and LB-2 met at H1000 (point estimates; CIs of median and p90 reported)", LB-1 median ≤ 10 s, LB-2 p90 ≤ 60 s. Q5 (typed API against free Cypher): "`always_g` − `always_c` > 0, CI excludes 0" (sealed-test-run §9, V2T arms `always_g_v2t` / `always_c_v2t`) |
| X1, X2 (single-sheet ladder, ContextRAG) | ADR-0054 | X1 (primary of the ladder): "the slope's 95 % CI upper bound < 0 on the common-family scope". X2: "non-inferiority at H1 (CI lower bound of Δ ≥ −0.05)" |
| I0-I4, E1-E4 (identity, end to end) | ADR-0063, `data/runs/exp0004/prereg/PREREG.md` §5 | I0 (gate): completeness ≥ 0.99 on every test corpus. I1: F1(D1, format) − F1(D1, naming) > 0, CI lower bound > 0. I2: F1(D2) − F1(D1), both families, CI lower bound > 0. I3: F1(D4, naming) − F1(D2, naming), CI lower bound > 0. I4: descriptive (F1 at the larger minus the smaller corpus per decider, with CI; candidate and cost elasticity). E1 (primary): acc(V, D0) − acc(plain), CI upper bound < 0. E2: acc(V, D2) − acc(V, D0), CI lower bound > 0. E3: acc(V, D4) − acc(V, D0), CI lower bound > 0. E4 (D2 and D4 each): acc(V, Dx) − acc(plain), CI lower bound > −0.03. "plain" is V2T-A2 on the same five 1,000-sheet plants without variants |
| M1-M7 (machine cost) | ADR-0051, `40-design/infra-cost.md` | M1 replay byte-identical to its source; M2 every infra TimingRow `clock = perf_counter`, clock resolution ≤ 1e-6; M3 per row `db_client_s + graph_api_s ≤ local_compute_s` (+1 ms), `db_server_s ≤ db_client_s`, expected 0 violations; M4 repeat spread above ×1.5 flagged, not hidden; M5 load counts equal the load plan; M6 both size sources shown; M7 every INF run spends 0 with `allow_paid_calls = false` |
| V2T - F1 (paired, on the same questions) | design 5.2; EXP-0007-R5 | **descriptive, not judged** (as in the first measurement): the paired difference acc(V2T-A2 `cascade_v4_iso`) − acc(F1 `cascade_v3`) with the two-stage interval; F1's own Q4/K1/K2/K3/Q5 are reported under the rules above |

## 3. Plant design and aggregation (design 5.1 and 5.2)

- Five independently seeded plants at 100 sheets and five at 1,000: 280 questions each (10 per family, 220
  headline). V2T-A2 and the F1 baseline answer the same questions on all ten; P4 reuses the five 1,000-sheet
  plants (tag-variant corpora, questions re-homed with a proof).
- Single-plant arms: the R4 ladder (1, 3, 10, 30 sheets; ContextRAG high on 1, 3, 10), P3 (I0-I4, on plant 1),
  duplication d0/d50 on the first 100-sheet plant, the concurrency-1 control, EX01.
- Pooled estimate: the mean of the per-plant statistics. Interval: two-stage cluster bootstrap (plants, then
  questions), the resample count and seed of the EXP-0007 claims code (5,000 resamples, seed 1: `N_RESAMPLES`, `BOOTSTRAP_SEED` in `qa/cascade/stats.py`).
  Paired claims are paired within a plant. With 5 clusters the bootstrap understates between-plant variance
  (stated limitation). The number of plants whose own estimate has the pooled sign is reported, not judged.
- Stated risk: a narrower Q4 interval makes Q4 stricter; a real small loss that passed with one plant can fail with five.

## 4. Gates

- **M0:** the ADR-0059 composition bands (a failed band stops the launcher: U4) and the pool memory probe.
- **G1 (after M1):** on both validation plants cascade_v4_iso >= F1's cascade_v3, and no dev family is below
  50 % on both plants at once. If it fails: stop (U2), one tuning round on X100g21s211 under ADR-0061, then a second fresh pair.
- **G2 (after M2b):** the judge pilot (every known first-measurement defect row of the two groups, at least 8 each, plus 20 controls) judges at least 80 % of the
  known defects `correct` or `ambiguous_question` and at least 80 % of the controls `correct`.
- **M3:** a clean tree under `src/` and the EXP-0008 scripts, and HEAD as named above.
- **Free gates of M4:** round trip and identity of each plant, LINE-01, blocking completeness I0 >= 0.99,
  ContextRAG prompt sizes, `T9.sha256` over the drawn sets.

## 5. Money (design 6)

EXP-0008 may spend at most **$40**: the runs at most $30 cumulative, the audit at most $10 including its
pilot ($2.50). A run's cap is the smallest of its dry-run cap (cache misses x cost per question x 1.5; the cost per question is the first measurement's real spend per tier, per identity arm in M8b and per plant size for ContextRAG in M5, `qa/exp0008/caps.py`), what
is left of its step's ceiling and what is left of the $30; the audit's cap is $10 or what the runs leave of
the $40. The OpenRouter balance must cover a cap before the run starts. Step ceilings: M1 $2.00, M2 $0.05,
M5 $4.90, M6a $10.00, M6b $6.27, M6c $1.44, M8a $0.80, M8b $7.28, M9 $0.25.

## 6. The scorer audit (design 5.3)

- Judge: `anthropic/claude-sonnet-5.5`, reasoning effort low, 2,048 output tokens, blind to the scorer's verdict.
  Judge prompt sha256: `b56c89d5fba7111f4270d47ef4d8cd53796eee5c499fc3cc5e1ce3d9d2312eaa`.
  Judge pin sha256: `e4794d07b865bf29c276f58309ccf35f205f3a71fabf9257260863cf2a0ea6aa`.
- Budget order: the pilot; every wrong row of the ten sealed plants (deduplicated by question and parsed
  answer); a random right sample of at least 2 per family per scale; ContextRAG's wrong rows; more right
  samples up to 5 per family per scale. The runner stops at the cap.
- Disagreements are classified by a script against the graph. A scorer or gold defect is fixed only in the
  scorer or the gold, by a rule from the question text or answer type written down before re-scoring, applied
  family-wide on every plant and arm, by code with a test. An ambiguous question accepts every defensible
  answer. No question is removed or reworded. Judge errors change nothing. The post-audit score is the
  reported result; the pre-audit score and every changed row are in one table.

## 7. Seeds

The test seeds were drawn once by `python -m plantgraph.qa.exp0008.draw_seeds --draw-seed 20261110`, before
any plant existed, from the test range minus every seed the first measurement used.

| role | seed |
|---|---|
| validation, 100 sheets | 5310 |
| validation, 1000 sheets | 5664 |
| ladder, 3/10/30 sheets | 5182 |
| ladder, 1-sheet candidates in order | 5583, 5863, 5739, 5745, 5486, 5748, 5681, 5386, 5330, 5188, 5577, 5339, 5994, 5238, 5829, 5548, 5562, 5416, 5550, 5147, 5973, 5977, 5364, 5720, 5611, 5462, 5751, 5414, 5836, 5750 |
| sealed 100 sheets, plant p1 | 5232 |
| sealed 100 sheets, plant p2 | 5582 |
| sealed 100 sheets, plant p3 | 5705 |
| sealed 100 sheets, plant p4 | 5512 |
| sealed 100 sheets, plant p5 | 5558 |
| sealed 1000 sheets, plant p1 | 5214 |
| sealed 1000 sheets, plant p2 | 5161 |
| sealed 1000 sheets, plant p3 | 5976 |
| sealed 1000 sheets, plant p4 | 5170 |
| sealed 1000 sheets, plant p5 | 5215 |

The draw seed 20261110 is the date of the draw, chosen before the draw.
