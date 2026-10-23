---
exp: 0001
date: 2026-10-11
question: At single-sheet and small scale, does serializing the whole plant into the prompt (ContextRAG, ChatP&ID-style) match or beat the frozen cascade_v3 and its tiers, and where along the size axis does the ordering flip?
status: done (stages A and B; stage C not triggered)
protocol: ADR-0054 (accepted 2026-10-11), design 40-design/exp0001-single-sheet.md; freeze E = commit 7da8a48 (`data/runs/exp0001/E.commit`, `E.sha256`), system code as at F1 (07d4029)
---

## Setup

- **Size ladder:** H1 (1 sheet, seed 104 — first seed in 100–399 with a one-sheet corpus), H3 (4 sheets), H10 (10),
  H30 (30), all seed 3 except H1, headline generator settings. Questions from the generator at T, 4 per family:
  H1 70, H3 87, H10 95, H30 96 (families that a one-sheet plant cannot ask are absent at H1). Scope `common` =
  19 families present at every size; LOOP_ACTUATED_VALVE excluded throughout.
- **Arms:** ctx-high (context_rag, Luna, final effort high — the agent's final pin), ctx-low (Luna low; H1 and H10
  only), cyp (Cypher tier, frozen), ag (agent tier, frozen), cascade_v3 (offline join of cyp + ag with the frozen
  accept rules). Concurrency per the harness defaults of the scripts; deadline 120 s (tiers), cutoff 120 s.
- **EX01:** ChatP&ID's real DEXPI example, imported as is (plant profile, 39 nodes); CP11–CP15 verbatim, 3 repeats;
  arms ctx-high, ctx-low, ctx-gpt5mini (ChatP&ID's model), cyp, ag, cascade_v3. Scored blind against the frozen
  checklist (`data/runs/exp0001/inputs/ex01_checklist.json`) by the main session, key not opened before verdicts.
- **Guards:** free cache-only replay of ST-AG-H100 byte-identical before any paid call; cost gate after the
  ContextRAG smoke (projected remaining $3.58 < $6.00, chars/token 2.67 from 2 smoke rows); all 15 replays
  byte-identical. **Spend:** ladder $4.90, EX01 $0.10.

## Result

acc@120, `common` scope (n = 68 at H1, 76 elsewhere), with 95 % Wilson CI; $/question mean; median latency:

| Size | ctx-high | ctx-low | cyp | ag | cascade_v3 |
|---|---|---|---|---|---|
| H1 (1 sheet) | 0.824 [0.716, 0.896], $0.00090, 3.6 s | 0.794, $0.00084, 2.7 s | 0.794, $0.00041 | 0.882, $0.00033 | **0.941 [0.858, 0.977]**, $0.00051, 8.1 s |
| H3 (4) | 0.789, $0.00342, 4.9 s | – | 0.697 | 0.987 | **0.974**, $0.00059, 8.8 s |
| H10 (10) | 0.750, $0.00961, 5.9 s | 0.592, $0.00917 | 0.724 | 0.934 | **0.947**, $0.00061, 8.2 s |
| H30 (30) | 0.658, $0.02494, 9.0 s | – | 0.658 | 0.934 | **0.947**, $0.00062, 8.9 s |

Paired ctx-high − cascade_v3 (common): H1 −0.118 [−0.206, −0.029]; H3 −0.184 [−0.276, −0.092]; H10 −0.197
[−0.289, −0.105]; H30 −0.289 [−0.395, −0.184].

| Claim | Verdict | Value |
|---|---|---|
| X1 ContextRAG's single-sheet advantage shrinks with size | **PASS** | slope of the gap −0.110 per log10(sheets), 95 % CI [−0.197, −0.022] |
| X2 on one sheet ContextRAG is not worse than the cascade (margin −0.05) | **FAIL** | −0.118 [−0.206, −0.029] |
| X3 accuracy flip | reported | at H1, the smallest size measured: the cascade is already better on one sheet |
| X4 cost / latency flip | reported | cost: ctx-high dearer from H1 (×1.76), ×6.0 at H3, ×16.6 at H10, ×41.5 at H30; latency: ctx faster up to H10 (median ratio 0.45 → 0.87), slower at H30 (1.13) |
| X5 context wall | reported | 2.54 chars/token (348 calls), 16,435 chars/sheet → wall ≈ 143 sheets at Luna's 922,000-token window; H100 (649,255 tokens) fits, H1000 (6,591,984) does not |
| X6 effort | reported | low − high: H1 −0.029 [−0.118, +0.044] acc, −$0.00005; H10 −0.154 [−0.242, −0.066] acc, −$0.00045 |

Stage C (ContextRAG on 24 sealed H100 questions) was **not triggered**: its precondition was "no accuracy flip up
to H30", and the cascade is ahead already at H1.

**EX01 (descriptive, no claim)** — correct / 5 per repeat under the strict frozen checklist:

| Arm | r1 | r2 | r3 |
|---|---|---|---|
| ctx-high | 0 | 0 | 0 |
| ctx-low | 0 | 0 | 0 |
| ctx-gpt5mini | 1 | 1 | 1 |
| cyp | 1 | 0 | 0 |
| ag | 0 | 0 | 0 |
| cascade_v3 | 1 | 0 | 0 |

5 of 83 non-empty answers pass: CP13 three times (GPT-5-mini ContextRAG, the only arm that names 66KL21 / 75SA21 /
73KH12), CP11 twice ("no path avoids H1007"). CP12, CP14 and CP15 pass nowhere: every arm names the control valves
"C1" (their tag in the import) or "globe valve", never HV4750.01 / PV4712.02, which in the import sit on the
actuator nodes. Most CP11 answers describe the real P4712 → H1008 route as a "bypass", which the checklist
counts wrong.

## Reading

- On our question families the predicted single-sheet win of ContextRAG did **not** appear: at one sheet the
  cascade is already 11.8 points ahead and the agent alone 5.8 points ahead; only the Cypher tier alone is level
  with ContextRAG. The "inversion" of the claim is therefore not observed as a crossing inside the ladder — the
  cascade leads at every size — but the gap grows with size as claimed (X1), cost diverges by ×1.8 → ×41.5 and
  latency crosses at H30 (X4). ContextRAG is the fastest arm on small plants.
- The ChatP&ID 0.91 is not reproduced on EX01 by any arm under its own reference answers; the mismatch is mostly
  naming (actuator tags vs valve tags in the imported structure) and CP11's reference reading. EX01 cannot decide
  the single-sheet end; the synthetic ladder is the evidence.
- Context wall: ContextRAG would fit up to ~143 sheets on Luna; H100 fits, so the sealed-run wording "did not fit
  at H100" is wrong — it was not run there by decision (ADR-0038); H1000 does not fit.

## Threats

- Our question families include multi-hop and isolation questions designed for plant scale; ChatP&ID's set is
  smaller and simpler. A single-sheet win of ContextRAG on simpler lookups is not excluded by this result.
- ContextRAG ran on Luna with the agent's final pin (effort high) and the F1 serialization; another serialization or
  model could do better (GPT-5-mini named EX01's item tags where Luna did not).
- EX01 scored by one reviewer with a strict checklist; the user did not add a second review.
- n = 68–96 questions per size; one repeat on the ladder; Luna takes no temperature.
