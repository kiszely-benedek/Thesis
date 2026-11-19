---
exp: 0008
date: 2026-11-17
question: After the full code review (ADR-0065), do the v2 results hold on a clean re-run with a fresh freeze, five plants per scale and the registered claims?
status: done
---

## Setup

- Pre-registration: `data/runs/exp0008/prereg/PREREG_A.md` and `PREREG_B.md` (part B and the E9 freeze hashes committed in `da7b3eb`, at M3, before any test plant was built).
- Launcher: `data/runs/exp0008/run_all.sh`, stages M0 to M10b. It finished on 2026-11-17 at 19:12 UTC with the line "launcher DONE all stages: runs $26.5565 of $30; audit $5.2304 of $10".
- Plants: five at about 100 sheets (`H100g21p1..p5`) and five at about 1,000 sheets (`H1000g21p1..p5`), 280 questions each (220 headline, 50 held-out families, plus wording variants). The ladder ran at 1 / 3 / 11 / 32 sheets (`H1g21`, `H3g21`, `H10g21`, `H30g21`). The end-to-end identity arms ran on `H1000g21p1V..p5V` at D0 / D2 / D4.
- Model and settings: the same pinned GPT-6 Luna as EXP-0007 setting A, with a 30 s Cypher transaction limit and a 120 s cutoff per question.
- Reports (all under `data/runs/exp0008/reports/`):
  - `sealed/report.md`: the main T1 to T4 claims.
  - `f1_baseline/report.md`
  - `ladder/report.md`
  - `e2e/report.md`: its title wrongly reads "EXP-0004" because the report code is shared; the numbers are from EXP-0008.
  - `duplication_out/duplication.md`
  - `c1.md`
- The infrastructure report is `data/runs/exp0008/infra/report.md` and the scorer audit is `data/runs/exp0008/audit/main/report.md`.

## Result

### Main claims: about 100 against about 1,000 sheets, pooled over five plants, headline scope (`sealed/report.md`)

| Policy | acc@120 S100 | acc@120 S1000 | S1000 − S100 | $/q S100 → S1000 | Median / p90 s at S1000 |
|---|---|---|---|---|---|
| cascade_v4_iso | 1005/1100 0.914 [0.895, 0.932] | 999/1100 0.908 [0.885, 0.932] | −0.005 [−0.035, +0.025] | 0.00140 → 0.00155 | 9.3 / 51.7 |
| always_g_v2t (agent only) | 0.898 | 0.898 | +0.000 [−0.030, +0.030] | 0.00177 → 0.00198 | 15.1 / 44.7 |
| always_c_v2t (Cypher only) | 0.811 | 0.811 | +0.000 [−0.037, +0.038] | 0.00077 → 0.00075 | 7.8 / 67.7 |
| F1 cascade_v3 (`f1_baseline`) | 0.817 | 0.827 | Q4 PASS +0.010 | 0.00108 → 0.00107 | 11.3 / 62.9 |

Verdicts of the claims:

| Claim | Headline | Held-out | Detail |
|---|---|---|---|
| Q4 (primary) | PASS | PASS | Cost elasticity 0.044 [−0.016, 0.103]. |
| K1 | FAIL | FAIL | The cascade is cheaper than the agent: −0.00042 $/q [−0.00056, −0.00029]. It is not faster: +1.91 s [−3.48, +6.04]. |
| K2 | PASS | PASS | +0.072 [+0.055, +0.089] over random escalation, 5 of 5 plants. |
| K3 | PASS | FAIL | Headline: median 9.3 s, p90 51.7 s. Held-out: median 21.1 s, p90 120.6 s. |
| Q5 | PASS | PASS | The agent beats Cypher by +0.087 [+0.057, +0.117] in the headline scope and by +0.156 on held-out families. |

On the held-out families the cascade scores 0.792 at S100 and 0.784 at S1000. The dev minus held-out gap is +0.09 to +0.21 on every plant.

### Ladder: ContextRAG against the cascade (`ladder/report.md`, common families)

| Sheets | ContextRAG high | Cascade | Agent | Cypher | ContextRAG / cascade $/q | Median latency ratio |
|---|---|---|---|---|---|---|
| 1 | 0.779 | 0.985 | 0.985 | 0.824 | 3.22 | 0.68 |
| 3 | 0.566 | 0.921 | 0.934 | 0.789 | 8.91 | 1.73 |
| 11 | 0.592 | 0.855 | 0.882 | 0.763 | 23.22 | 2.50 |
| 32 | not run (registered) | 0.908 | 0.895 | 0.868 | – | – |

The ladder claims:
- X1 FAIL: the slope is −0.048 [−0.190, +0.096] per log10(sheets).
- X2 FAIL: on one sheet ContextRAG minus cascade is −0.206 [−0.309, −0.118].
- X3: accuracy already favours the cascade at the smallest size measured.
- X4: the cost flip is at H1g21 and the latency flip at H3g21.
- X5: the context wall is at W = 67 sheets (2.56 chars/token, 35,429 chars per sheet).

### Tag identity, end to end (`e2e/report.md`, 1,100 questions per arm, five plants)

| Arm | R5 (clean tags) | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| acc@120 | 0.908 [0.885, 0.932] | 0.823 [0.800, 0.845] | 0.856 [0.832, 0.880] | 0.830 [0.798, 0.862] |

| Claim | Difference | Verdict |
|---|---|---|
| E1 | V-d0 − R5 = −0.085 [−0.108, −0.065] | PASS |
| E2 | V-d2 − V-d0 = +0.034 [+0.018, +0.050] | PASS |
| E3 | V-d4 − V-d0 = +0.007 [−0.023, +0.037] | FAIL |
| E4 (D2) | −0.052 [−0.071, −0.032] | FAIL |
| E4 (D4) | −0.078 [−0.101, −0.058] | FAIL |

On exposed questions (k_identity > 0) the arms score 0.836 (R5), 0.226 (D0), 0.452 (D2) and 0.712 (D4). D4 loses on unexposed questions: 0.848 against 0.914 for D0. In particular, NO_PATH falls from 50/50 to 34/50 and DOWNSTREAM_IN_UNIT falls to 26/50.

### Descriptive checks

- **Duplication 0 / 25 / 50 %:** 0.919 / 0.923 / 0.909. The paired deltas are +0.007 [+0.000, +0.020] and −0.009 [−0.026, +0.000].
- **Concurrency-1 control, 46 agent questions:** 44 correct at concurrency 1 against 43 at concurrency 4. The verdicts agree on 45 of 46.
- **Scorer audit by an independent judge:**
  - On the right-scored sample (89 rows) the judge agrees with 84.3 %; on the wrong-scored rows (144) it agrees with 86.1 %.
  - Cohen's kappa on the decisive rows is 0.889.
  - In 4 rows the system was right and the scorer wrong.
  - Most disagreements are ambiguous questions; LOOPS_NEAR_ITEM accounts for 10 of them.

### Infrastructure (`infra/report.md`, H100g21p1 → H1000g21p1)

| Quantity | H100g21p1 | H1000g21p1 |
|---|---|---|
| Nodes | 9,449 | 93,171 |
| Relationships | 31,666 | 312,868 |
| Ingest | 9.38 s | 427.27 s (generation 390.99 s, the four Neo4j load stages 27.1 s) |
| Store on disk | 6.6 MiB | 56.2 MiB |
| Startup without rebuild | 0.63 s | 5.53 s |
| Neo4j resident memory | 1,143 MiB | 1,258 MiB |
| App process peak | 341 MiB | 1,743 MiB |
| Cypher database time, median / p90 | 0.045 / 0.88 s | 0.153 / 31.6 s |
| Agent local compute, median | 0.0016 s | 0.0016 s |

### Spend

The runs cost $26.56 of the $30 budget and the audit $5.23 of $10.

## Reading

- **The answer to the scale question is clean.** The tuned cascade keeps its accuracy from about 100 to about 1,000 sheets (0.914 to 0.908, difference consistent with zero). Its token cost per question grows by about 10 % for ten times the sheets (elasticity 0.044). This replicates EXP-0007 R5 (0.911 / 0.891) on five plants per scale instead of one.
- **Graph retrieval wins at every size measured, including one sheet.** ContextRAG trails by 21 to 36 points from 1 to 11 sheets, its cost ratio grows from 3× to 23×, and it cannot run above 67 sheets. The registered "inversion" claims (X1, X2) fail because ContextRAG has no single-sheet advantage on these questions to lose; the accuracy optimum does not move with size. What does move with size is cost and latency, which turn against ContextRAG from 1 and 3 sheets. EXP-0007 R4 showed the same pattern (X2 −0.271).
- **Across strategies, the optimal strategy depends on how much latency is allowed, not on plant size:**
  - The cascade is most accurate and cheaper than the agent alone.
  - Cypher alone is cheapest and fastest at the median, but about 10 points less accurate.
  - The cascade's escalation decision is worth about 7 points over random escalation.
- **Inconsistent tag writing costs 8.5 points.** Identity resolution D2 recovers a third of that. D4 helps exposed questions a great deal but its false merges cost unexposed ones, so the net effect is about zero.

## Threats

- The plants are generated, not real drawings, and five plants per scale is few. The two-stage bootstrap understates the between-plant variance (by about 4/5 at five plants, per the report notes).
- Held-out question families score 0.78 to 0.79, against 0.91 on the headline scope, so the headline accuracy is partly tuned.
- The latency and K3 results depend on the machine. Cypher runs had to be on mains: on battery the laptop was about 3× slower.
- Deviations are logged in `docs/private/40-design/review-fixes.md`:
  - one M6b run was re-measured after the machine slept;
  - 8 M8b runs were finished by hand with a raised per-run spend cap (a money guard only);
  - one M8b Cypher replay was repeated after battery operation, and one round re-measured;
  - one d4 replay was repeated after a near-limit timeout.
  - No replay was accepted by hand.
- In the infrastructure report, M1 failed: every agent replay fell back to the original run's timings. So the agent rows of I2 come from the source runs, not from fresh replays. M4 and M6 are flagged as in INFRA-2.
- ctx-low and ContextRAG at 32 sheets were not run, as registered.
