---
run: EXP-0007 R4, the v2 ladder on the frozen system V2T-A
date: 2026-10-29
commits: E7 fdad31f, test set d72e3b5, record 87eb79e
status: done
design: EXP-0007-v2-remeasurement-plan.md; ADR-0060, ADR-0061, ADR-0062
---

# R4: V2T-A against ContextRAG from 1 to 30 sheets

**Result.** On v2 plants drawn from the registered test seeds, cascade_v4_iso answers 0.957 / 0.885 / 0.909 / 0.924
of the questions at 1 / 3 / 11 / 30 sheets. ContextRAG at high effort answers 0.686 / 0.654 / 0.614 at 1 / 3 / 11
sheets. The cascade leads from the first sheet, as it did on v1. Spend $3.25, of which ContextRAG $2.67.

## Accuracy within 120 s, all families

| Corpus | Sheets | n | ContextRAG high | Cypher tier | Agent tier | cascade_v4_iso |
|---|---|---|---|---|---|---|
| H1g2 | 1 | 70 | 0.686 [0.570, 0.782] | 0.857 [0.757, 0.921] | 0.957 [0.881, 0.985] | **0.957** [0.881, 0.985] |
| H3g2 | 3 | 78 | 0.654 [0.543, 0.750] | 0.705 [0.596, 0.795] | 0.936 [0.859, 0.972] | **0.885** [0.795, 0.938] |
| H10g2 | 11 | 88 | 0.614 [0.509, 0.709] | 0.795 [0.700, 0.867] | 0.943 [0.874, 0.975] | **0.909** [0.831, 0.953] |
| H30g2 | 30 | 92 | not run | 0.761 [0.664, 0.836] | 0.935 [0.865, 0.970] | **0.924** [0.851, 0.963] |

Brackets are Wilson 95 % intervals. n leaves out LOOP_ACTUATED_VALVE.

## Cost and latency per question

| Corpus | ContextRAG $/q | cascade $/q | ContextRAG median / p90 s | cascade median / p90 s |
|---|---|---|---|---|
| H1g2 | 0.00274 | 0.00072 | 7.6 / 34.9 | 5.5 / 22.5 |
| H3g2 | 0.00600 | 0.00084 | 11.0 / 48.1 | 7.5 / 33.7 |
| H10g2 | 0.02172 | 0.00101 | 16.1 / 59.2 | 7.6 / 35.2 |
| H30g2 | not run | 0.00104 | not run | 7.3 / 39.6 |

## Claims

| Id | Verdict | Value |
|---|---|---|
| X1, ContextRAG's single-sheet advantage shrinks with size | FAIL | slope −0.071 per log10 sheets [−0.218, +0.074] |
| X2, on one sheet ContextRAG is not worse than the cascade | FAIL | −0.271 [−0.386, −0.157], n = 70, margin −0.05 |
| X3, accuracy flip | reported | at H1g2, the smallest size |
| X4, cost and latency flip | reported | at H1g2; $/q ratio 3.79 → 7.13 → 21.57 |
| X5, context wall | reported | 62 sheets (2.56 chars/token, 37,935 chars/sheet, window 922,000 tokens) |
| X6, effort sensitivity | not run | ADR-0060 |

X1 fails because there is no ContextRAG advantage to shrink: the gap already favours the cascade on one sheet.

## Reading the numbers

- **The agent tier alone beats the cascade at 3, 11 and 30 sheets** (0.936 / 0.943 / 0.935 against 0.885 / 0.909 /
  0.924), and the intervals overlap. Tier 1 accepts some wrong Cypher answers. This is a result about the policy, not
  a bug to fix: no system change is allowed between R4 and R5 (plan §9 point 6).
- ContextRAG was not run at H30g2 (cost). From about 56–62 sheets a v2 plant no longer fits the prompt window.
- Each size has 70–92 questions, so the intervals are wide. Size-to-size differences are not significant.

## Caveats

- The H30g2 set holds FIRST_MEETING_POINT. It counts in the "all" scope above, not in the 19 common families behind
  X1 and X2. It is excluded from R5 (ADR-0062).
- The script's report step failed on wrong policy paths. The report was rebuilt with the script's own command, and
  `run_ladder.sh` now passes the paths.

## Files

`data/runs/exp0007/ladder/report/report.md`, `data/runs/exp0007/ladder/cascade_report/report.md`,
`data/runs/exp0007/ladder/tune_reports/`.
