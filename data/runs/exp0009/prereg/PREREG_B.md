# EXP-0009 pre-registration, part B (written by the launcher at F10)

Code commit (HEAD when the freeze was written): `91c1139d71edb2e1ecebd9efecb08eeec40badd8`

## Validation gates

- G1: **PASS**, ok
- G1-B: **FAIL**, OPEN_VALVES_TO_ISOLATE below 50% on every plant; UPSTREAM_ISOLATION_X below 50% on every plant
- G1-B2: **PASS**, mean +0.0036

B sealed: **no (G1-B or G1-B2 failed: A2 alone runs sealed, ADR-0067)**.

A2, correct/total per family:

| family | VAL1000g22 | VAL100g22 |
|---|---|---|
| CONNECTED | 10/10 | 10/10 |
| COUNT_IN_UNIT | 8/10 | 9/10 |
| CROSS_UNIT | 5/10 | 9/10 |
| FEEDING_UNITS | 9/10 | 8/10 |
| FLOW_PATH | 9/10 | 8/10 |
| LOOPS_NEAR_ITEM | 7/10 | 7/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 |
| NO_PATH | 10/10 | 10/10 |
| OPEN_VALVES_TO_ISOLATE | 2/10 | 0/10 |
| ROUTE_AVOIDING | 9/10 | 7/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 10/10 | 10/10 |
| UNITS_REACHED | 4/10 | 8/10 |
| UPSTREAM_ISOLATION_X | 3/10 | 0/10 |
| VALVES_ON_PATH | 8/10 | 7/10 |

B, correct/total per family:

| family | VAL1000g22 | VAL100g22 |
|---|---|---|
| CONNECTED | 8/10 | 9/10 |
| COUNT_IN_UNIT | 9/10 | 8/10 |
| CROSS_UNIT | 5/10 | 9/10 |
| FEEDING_UNITS | 9/10 | 9/10 |
| FLOW_PATH | 8/10 | 9/10 |
| LOOPS_NEAR_ITEM | 7/10 | 8/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 |
| NO_PATH | 10/10 | 10/10 |
| OPEN_VALVES_TO_ISOLATE | 4/10 | 2/10 |
| POSITION_OF_VALVE | 10/10 | 10/10 |
| ROUTE_AVOIDING | 10/10 | 8/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 10/10 | 10/10 |
| UNITS_REACHED | 4/10 | 7/10 |
| UPSTREAM_ISOLATION_X | 4/10 | 3/10 |
| VALVES_ON_PATH | 10/10 | 6/10 |

## B tuning log (D100g22, at most three rounds)

| round | change | B dev accuracy | B - A2 on R-dev |
|---|---|---|---|
| 1 | round 1 | 0.8647 | +0.0143 |
| 2 | round 2: descriptor guidance (next_to is the first tagged item met walking from the valve; untagged valves belong in a valve list) in the B agent prompt only; Cypher-facing format and primer as round 1 (a first round-2 attempt with it in the format text tripped the Cypher health gate, 18/170 parse failures, run kept as U9-2-CYP-D100g22B.health-stop-1) | 0.8706 | +0.0071 |

E10 candidate: round 2.

## Replay verdicts

- V9-AG-VAL1000g22B: identical
- V9-AG-VAL100g22B: identical
- V9-CYP-VAL1000g22B: prefix_equal: 143 of 170 rows
- V9-CYP-VAL100g22B: identical

## Measured dollars per question (both tiers of an arm are keyed `arm-tier-scale`)

| key | USD per question |
|---|---|
| A2-ag-100 | 0.001995 |
| A2-ag-1000 | 0.002195 |
| A2-cyp-100 | 0.000663 |
| A2-cyp-1000 | 0.000731 |
| B-ag-100 | 0.002214 |
| B-ag-1000 | 0.002618 |
| B-cyp-100 | 0.000738 |
| B-cyp-1000 | 0.000781 |

Recomputed sealed caps:

| run | cap USD |
|---|---|
| A2-ag-100 | 0.82 |
| A2-ag-1000 | 0.91 |
| A2-cyp-100 | 0.27 |
| A2-cyp-1000 | 0.30 |

Peak memory of the VAL1000g22 question pool: 2.13 GiB.

## E10 freeze

`E10.sha256` lists 650 files; its own sha256 is `bb651798ae5887f24accc4ea3381031651cc31764c25e8edba49e1ec09bb3bcd`.
`B_FILES.sha256` lists every B source file and the cascade policy.
`PREREG.sha256` covers part A, part B, the seeds, the plan, the position prior, the E10 and B hash
files and the judge prompt.
