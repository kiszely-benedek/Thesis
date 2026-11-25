# EXP-0009 deviation: the V2T-B sealed runs are exploratory

Date: 2026-11-25. Written after F10 and during B10, before any P1c run, while the sealed plants were still being built and none had been answered.

## What the pre-registration said

ADR-0067 and PREREG A gate B's sealed runs on two checks at P1b:
- **G1-B:** each scope X isolation family reaches at least 50% on at least one validation plant.
- **G1-B2:** B does not do worse than A2 on scope R.

If either fails, B is not run sealed, and A2 alone runs sealed.

## What P1b measured

| Measure | Result |
|---|---|
| VAL100g22, A2 | 123/160 |
| VAL100g22B, B | 138/170 |
| VAL1000g22, A2 | 124/160 |
| VAL1000g22B, B | 138/170 |
| G1 (A2) | PASS |
| G1-B2 | PASS, mean +0.0036 |
| G1-B | **FAIL**: OPEN_VALVES_TO_ISOLATE and UPSTREAM_ISOLATION_X are below 50% on every validation plant |

The launcher therefore wrote `state/b_sealed = no`, and PREREG B records "B sealed: no".

## The deviation

The user decided on 2026-11-25 to run B on the sealed plants anyway. The user originally asked for both systems (D1 = C), and the budget allows it. The main session then set `state/b_sealed` to `yes` and updated that file's hash in `state/P1b.done`. Nothing else was changed:
- the frozen code;
- the plants;
- the questions;
- the caps;
- the A2 arm.

## How the B results must be reported

- **A2 stays confirmatory.** Q4, K1–K3 and Q5 on V2T-A2 are confirmatory, exactly as pre-registered. The deviation does not touch them.
- **B is exploratory.** Q4-B, its sensitivity row, SB1, SB2, POSITION accuracy, and the audit's B stratum are **exploratory**, not confirmatory.
  - The analysis prints PASS or FAIL verdicts for them, because the frozen analysis code cannot know about this deviation.
  - Those verdicts must be read and reported as exploratory, with the failed G1-B gate stated beside them.
- **Cost.** The deviation adds B's P1c runs and the audit B stratum. The P1c projection at P1b was $7.68 for A2 alone. B adds about $8–9, estimated from the measured B costs per question at P1b. All of this stays inside the runs ledger and the $35 cap.
