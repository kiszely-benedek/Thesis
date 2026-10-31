---
run: EXP-0007 R5, the sealed v2 test of the frozen system V2T-A, with F1 as a baseline
date: 2026-10-31
commits: E7 fdad31f, test set f3c0c00, run order aeb2801, replay gate c77441d, cap raise 59b084d
status: in progress (headline done; descriptive arms d0 / d50 / C1 and the F1 baseline running)
design: EXP-0007-v2-remeasurement-plan.md; ADR-0053 (claims), ADR-0060, ADR-0061, ADR-0062
---

# R5: V2T-A on the sealed v2 corpora H100g2 and H1000g2

**Result (headline).** On the registered test seeds, cascade_v4_iso answers 401/440 = 0.911 of the headline
questions at 100 sheets and 392/440 = 0.891 at 1,000 sheets, at $0.00137 and $0.00148 per question. The primary
claim Q4 passes: ten times the sheets costs no measurable accuracy (−0.020 [−0.059, +0.018]) and almost no money
(cost elasticity 0.033). K2, K3 and Q5 pass; K1 fails on latency. On the five held-out families accuracy is 0.770 /
0.740; the gap sits almost entirely in DOWNSTREAM_ISOLATION.

Source: `data/runs/exp0007/sealed/report/report.md` (claims report, written 2026-10-31 16:20).

## Accuracy within 120 s, headline scope (dev-old + dev-new + held-out, n = 440 per corpus)

| Policy | H100g2 | H1000g2 | $/q H100g2 → H1000g2 | median / p90 s at H1000g2 |
|---|---|---|---|---|
| **cascade_v4_iso** (primary) | **401/440 0.911** [0.881, 0.934] | **392/440 0.891** [0.858, 0.917] | 0.00137 → 0.00148 | 7.5 / 40.8 |
| cascade_v4 | 399/440 0.907 [0.876, 0.931] | 392/440 0.891 [0.858, 0.917] | 0.00140 → 0.00152 | 7.5 / 55.1 |
| always_g_v2t (agent only) | 400/440 0.909 [0.879, 0.933] | 383/440 0.870 [0.836, 0.899] | 0.00171 → 0.00189 | 10.4 / 27.1 |
| always_c_v2t (Cypher only) | 356/440 0.809 [0.770, 0.843] | 350/440 0.795 [0.755, 0.831] | 0.00074 → 0.00075 | 6.5 / 46.7 |

Wilson 95 % intervals. The headline scope leaves out LOOP_ACTUATED_VALVE (ADR-0044 U2) and the 90 held-out-wording
questions.

## Claims (ADR-0053, carried over by ADR-0060/0061), claims corpus H1000g2

| Id | Scope headline | Value | Scope held-out | Value |
|---|---|---|---|---|
| **Q4 (primary)**, cascade_v4_iso | **PASS** | acc −0.020 [−0.059, +0.018]; e 0.033 [−0.045, 0.105] | PASS | −0.030 [−0.150, +0.090]; e 0.042 |
| K1, cascade vs agent only | FAIL | acc +0.020 ok, $ −0.00041 ok, latency +3.21 s [+1.33, +5.25] | FAIL | latency +17.57 s |
| K2, self-flag vs random escalation | PASS | +0.076 [+0.055, +0.098] | PASS | +0.107 [+0.060, +0.157] |
| K3, median ≤ 10 s, p90 ≤ 60 s | PASS | 7.5 s / 40.8 s | FAIL | 19.1 s / 104.6 s |
| Q5, typed agent vs free Cypher | PASS | +0.075 [+0.039, +0.111] | FAIL | +0.090 [−0.010, +0.180] |
| Q1–Q3 | not run | arms dropped (ADR-0047, ADR-0048) | | |

Q4' (the same test for the other policies) passes for all three.

## Splits and the generalisation gap (cascade_v4_iso)

| Split | H100g2 | H1000g2 |
|---|---|---|
| dev-old (220) | 0.941 | 0.927 |
| dev-new (120) | 0.975 | 0.950 |
| held-out (100) | 0.770 | 0.740 |
| held-out-wording (90) | 0.878 | 0.889 |
| gap dev − held-out | +0.183 [+0.101, +0.273] | +0.195 [+0.108, +0.288] |

Held-out families, cascade_v4_iso, H100g2 / H1000g2: DOWNSTREAM_ISOLATION 2/20 and 2/20, VALVES_ON_PATH 15/20 and
13/20, FEEDING_UNITS 20/20 and 20/20, UNITS_REACHED 20/20 and 20/20, ROUTE_AVOIDING 20/20 and 19/20. Without
DOWNSTREAM_ISOLATION, held-out at H1000g2 is 72/80. The dev family UPSTREAM_ISOLATION is 15/30 and 16/30.
**Interpretation, not a registered claim:** the weak spot is isolation questions, not tuning in general. The
report's secondary score (control valves do not isolate) lowers UPSTREAM_ISOLATION further (12/30 and 11/30), so
the gold definition itself is debatable.

## Run notes

- Order changed so the headline corpora run first (ADR-0062, `aeb2801`).
- `INF-S7-CYP-H1000g2` stopped after 231 rows, all equal to the run, on a query near the 30 s limit
  (`replays/INF-S7-CYP-H1000g2/timing_note.md`). The other three headline replays are identical.
- `S7-AG-H1000g2` hit its $1.00 cap at 535/560; resumed after the user approved $0.90 in all (`59b084d`); 559
  answered, 1 parse failure.
- Spend to S7-CYP-H100g2d0 ≈ $3.08 by the call records.

## Still to come

Descriptive arms H100g2d0 / H100g2d50 (duplication rate), the C1 subset, the F1 baseline (cascade_v3) on
H100g2 / H1000g2, the duplication and per-corpus tune reports.
