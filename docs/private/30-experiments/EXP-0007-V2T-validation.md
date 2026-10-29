---
run: EXP-0007 V2T tuning and held-back validation
date: 2026-10-29
commits: tuning rounds 785316e / e478c24 / 59c7eb9; validation runs from a11425c–860981e (V2T system files frozen since round 3, 7ab54fb)
status: done (V run once; data/runs/exp0007/tune/final/DONE)
design: 40-design/qa-tuning-v2.md; ADR-0061
---

# V2T: tuning on T, validation on held-back plants

**Result.** On two plants the tuning never saw, the tuned system V2T answers 154/163 (100 sheets) and
156/163 (1,000 sheets) dev questions correctly with cascade_v4_iso, against 145/163 and 144/163 for the frozen
F1 system (cascade_v3, 120 s) on the same questions. Accuracy does not fall from 100 to 1,000 sheets. Spend:
tuning ≈ $1.30, validation $1.32.

## Tuning on T = X100g2s211 (163 dev questions, 18 families)

| Round | cascade_v4_iso, A (within 120 s) | B (uncut) | fixed / broke vs previous | spend |
|---|---|---|---|---|
| 1 | 140 | 140 | — | ≈ $0.44 |
| 2 | 158 | 158 | 19 / 4 | $0.43 |
| 3 | 159 | 158 | A 3 / 1, B 3 / 2 | $0.43 |

Stop rule 1 (three rounds) ended tuning. The coded variant rule chose cascade_v4_iso in every round. Round-1
regressions traced to the round-1 final-answer wording (start item dropped from paths; no path answered as an
empty list) were fixed in round 2; round 3 added the loop-head rule.

## Validation on V (run once)

| Plant | System | Cypher tier | Agent tier | Cascade |
|---|---|---|---|---|
| X100g2s212 (100 sheets) | F1 | 96 (58.9 %) | 133 (81.6 %) | cascade_v3 @120 s: 145 (89.0 %) |
| | V2T-A | 128 (78.5 %) | 152 (93.3 %) | cascade_v4_iso @120 s: **154 (94.5 %)** |
| | V2T-B | 128 (78.5 %) | 152 (93.3 %) | cascade_v4_iso uncut: **154 (94.5 %)** (@120 s: 149) |
| X1000g2s213 (1,000 sheets) | F1 | 88 (54.0 %) | 135 (82.8 %) | cascade_v3 @120 s: 144 (88.3 %) |
| | V2T-A | 139 (85.3 %) | 153 (93.9 %) | cascade_v4_iso @120 s: **156 (95.7 %)** |
| | V2T-B | 139 (85.3 %) | 153 (93.9 %) | cascade_v4_iso uncut: **156 (95.7 %)** (@120 s: 145) |

All counts of 163. Oracle (either V2T tier correct): 157 (100 sheets), 158 (1,000 sheets). Cypher retrieval
errors: F1 42 / 50, V2T-A 6 / 13, V2T-B 6 / 10 (100 / 1,000 sheets).

## Caveats

- Dev families only; the five held-out families and the registered test seeds are untouched (R4/R5).
- LOOPS_NEAR_ITEM's gold was redefined on v2 after round 3 and before V was drawn (ADR-0061, "After tuning").
- The X1000g2s213 V2T Cypher-A run was interrupted once by a provider reply without choices (TypeError in
  the client) after 79 rows and resumed under the same id and cap.
- The report step of `tune.sh --final-v` failed on a missing folder; the reports were built by hand with the
  script's own commands (`tune-report`, `dev-report`), and the script now creates the folder.
- API-02 (report-only) on X1000g2s213 was stopped after several hours and is not recorded.
