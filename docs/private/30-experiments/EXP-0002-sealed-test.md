---
exp: 0002
date: 2026-10-11
question: On held-out plants H100 / H1000 never used in development, with held-out question families and wordings, how accurate, costly and fast is the frozen cascade_v3, and do accuracy and cost hold from ~100 to ~1,000 sheets?
status: done
protocol: ADR-0053 (accepted 2026-10-11), design 40-design/sealed-test-run.md (hashed into F1, not edited after F1)
---

## Setup

- **Freeze F1:** commit `07d4029` (2026-10-11T14:58:13Z), `data/runs/sealed/F1.commit`, `F1.sha256` (pins, params,
  seal hash `905c7984…f63b`, design note, ADR-0053). **Test data T:** commit `4ffd87e`, `T.commit`, `T.sha256`.
  Allowed-paths diff F1→T: question-side files only (`qa/questions/**`, `family_meta.py`, `need_gold.py`,
  `models.py` with six new enum members). All sealed run configs `git_dirty: false`.
- **Corpora:** H100 (100 sheets, seed 2), H1000 (1,001 sheets, seed 0). **Questions:** 580 per corpus = 18 dev
  families × 20 (dev-old 240, dev-new 120) + 6 held-out families × 20 (120) + 10 held-out wordings × 10 (100).
  Pool seed 31 with `--n-per-bin 500` (deviation D1, `data/runs/sealed/DEVIATIONS.md`), sample seed 20261031.
  Headline scope: all splits except held-out wordings and LOOP_ACTUATED_VALVE = 460 per corpus.
- **Runs (paid):** `ST-CYP-H100`, `ST-CYP-H1000` (cypher_rag_plant, GPT-6 Luna low, pin `acf24178…`),
  `ST-AG-H100`, `ST-AG-H1000` (graph_agent_low_steps, Luna steps low / final high, pin `ffc026d3…`), concurrency 4,
  deadline 120 s, cache `cache_sealed.sqlite`; control `ST-AG-H1000-C1` (48 questions, concurrency 1, own cache).
  Smoke stages $0.02 for the first tier runs. Spend: $1.26 in total.
- **Analysis:** `python -m plantgraph.qa.cascade report --sealed-claims` (ST-T1 code at F1), policies cascade_v3
  (primary), always_g_luna, always_c_luna, cascade_v3_iso; cutoff 120 s. Report: `data/runs/sealed/report/report.md`.
- **Reproducibility:** cache-only replays at concurrency 1 of all four tier runs: **4/4 byte-identical.**
- **Technical health (outcome counts):** Cypher H100 492 answered / 87 RETRIEVAL_ERROR / 1 PARSE_FAILURE; Cypher H1000
  466 / 114 / 0; agent H100 577 answered / 3 PARSE_FAILURE; agent H1000 579 / 1. No abort rule triggered; no rerun.

## Result

Headline scope (n = 460), acc@120 with 95 % Wilson CI, $/question, latency median / p90 (s):

| Policy | H100 | H1000 |
|---|---|---|
| **cascade_v3** | **0.937 [0.911, 0.956]**, $0.00065, 8.4 / 21.5 | **0.917 [0.889, 0.939]**, $0.00071, 8.2 / 22.5 |
| always_g_luna | 0.941 [0.916, 0.959], $0.00066, 8.8 / 23.8 | 0.924 [0.896, 0.945], $0.00074, 8.2 / 24.9 |
| always_c_luna | 0.739 [0.697, 0.777], $0.00043, 7.0 / 11.3 | 0.696 [0.652, 0.736], $0.00043, 6.3 / 11.0 |
| cascade_v3_iso (dev-tuned label variant) | 0.954 [0.931, 0.970] | 0.937 [0.911, 0.956] |

Splits, cascade_v3 (H100 / H1000): dev-old 206/220 / 207/220; dev-new 120/120 / 117/120; held-out 105/120 /
98/120; held-out wording 87/90 / 88/90. Generalisation gap dev − held-out: +0.084 [+0.025, +0.148] / +0.136
[+0.067, +0.210].

Claims (claims corpus H1000):

| Claim | Headline | Held-out |
|---|---|---|
| **Q4 (primary)** cascade_v3 holds from H100 to H1000 | **PASS**: Δacc −0.020 [−0.052, +0.013], cost elasticity 0.033 [−0.024, 0.090] | PASS: −0.058 [−0.150, +0.033], e 0.042 |
| K1 cascade cheaper and faster than always_g_luna at no accuracy loss | **FAIL**: Δ$ −0.00003 [−0.00010, +0.00003], Δlatency −0.45 s [−1.36, +0.43] | PASS: Δ$ −0.00028 [−0.00044, −0.00012], Δlatency −2.73 s [−5.00, −0.59], Δacc +0.017 [−0.050, +0.075] |
| K2 better than random escalation at the same share | PASS +0.145 [+0.118, +0.172] | PASS +0.127 |
| K3 latency bounds (median ≤ 10 s, p90 ≤ 60 s) | PASS 8.2 / 22.5 s | PASS 9.2 / 37.0 s |
| Q5 agent tier beats Cypher tier | PASS +0.228 [+0.185, +0.272] | PASS +0.158 |
| Q4′ for always_g_luna, always_c_luna, cascade_v3_iso | PASS (all) | PASS (all) |
| Q1–Q3 | not run (arms dropped, ADR-0047/0048) | |

Where cascade_v3 loses (per family, H100 / H1000): UPSTREAM_ISOLATION 17/30 / 15/30 (always_g_luna 25 / 26,
cascade_v3_iso 25 / 24); held-out DOWNSTREAM_ISOLATION 10/20 / 8/20 (always_g_luna 11 / 10); FEEDING_UNITS 17 / 16
(always_g_luna 19 / 20). Held-out families where the cascade beats the agent: FIRST_MEETING_POINT 19 / 17 (agent
16 / 12). Tier-1 accept precision: 0.948 (H100), 0.938 (H1000); 0.905 on H1000 held-out.

Concurrency-1 control (48 H1000 questions, live, own cache): same final answer as the concurrency-4 run on 45/48,
correct 47 vs 46, 3 correctness flips — run-to-run variance of Luna (no temperature) on this sample.

## Reading

- The primary claim Q4 holds: from ~100 to ~1,000 sheets cascade_v3 keeps its accuracy (difference within ±5
  points, CI contains 0) and its cost per question barely moves (elasticity ≈ 0.03 against a limit of 0.5). The same
  holds for every arm, including the held-out families.
- The cascade does not save money or time against the agent alone on the headline set (K1 fails, as forecast in
  ADR-0053 from the dev data); it does on the held-out families, where the agent alone needs more steps
  (median 14.9–15.5 s, fails LB-1) and the Cypher tier answers 70 % of questions with 0.905–0.931 precision.
- Generalisation: held-out families cost 8–14 points; held-out wordings cost little (0.967–0.978). The weak spot is
  isolation (which valves to close): the cascade's Cypher tier accepts wrong isolation answers that the agent would
  have got right; the label-routed variant avoids this, but its router is dev-tuned.
- Dev vs test for cascade_v3: dev D100/D1000 176/180, 175/180 (0.978, 0.972 on all questions); test 548/580, 540/580
  (0.945, 0.931) — the test is harder by construction (held-out families) and on dev-old questions alone 0.936–0.941.

## Threats

- Synthetic plants and generated questions; the held-out families were designed before the run but by the same
  generator team. One repeat per tier; Luna takes no temperature (control: 3/48 correctness flips).
- Offline join: the agent tier gets the full 120 s in the join, a live cascade gives it 120 s minus the Cypher
  tier's time (no answer was near the cutoff; max 92.3 s).
- Concurrency 4 for all main runs; the control is too small for a latency claim.
- ContextRAG was not run (ADR-0038): its prompt is 1.70M / 16.65M characters at 100 / 1,000 sheets (INFRA-1).
  Correction from EXP-0001 (2.54 chars/token): H100 would fit Luna's 922,000-token window (~649k tokens); only
  H1000 does not fit. ADR-0053's "did not fit at H100" wording is wrong; ADR-0053 stays unedited because it is
  hashed into F1.
- EXP-0001 (the single-sheet ChatP&ID end of the claim) has no result yet.
