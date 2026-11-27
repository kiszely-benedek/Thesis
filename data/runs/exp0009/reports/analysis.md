# EXP-0009 sealed analysis (T17)

Root `data\runs\exp0009`. B ran sealed. Scope R is EXP-0008's headline set on the v2.2 plants with the five X families left out (the three headline splits, LOOP_ACTUATED_VALVE out). Scope X is the five extension families: B answers all of them, A2 only the isolation families. acc@C counts an answer correct when it arrived within setting A's 120 s cutoff. The plants of a scale are pooled with equal weight.

## Claims

| claim | arm | scope | verdict | estimate [95 % interval] | questions | rule |
|---|---|---|---|---|---|---|
| Q4 | V2T-A2 | R (EXP-0008 headline set, X families out) | PASS | +1.4 [-1.9, +4.7] | 1800 | the interval contains 0 or lies above it |
| K1 | V2T-A2 | R (EXP-0008 headline set, X families out) | FAIL | -3.1 [-5.3, -0.8] | 900 | as EXP-0008: no accuracy loss against always-agent, cost and latency clearly lower |
| K2 | V2T-A2 | R (EXP-0008 headline set, X families out) | PASS | +6.7 [+5.0, +8.5] | 900 | as EXP-0008: the interval against random escalation lies above 0 |
| K3 | V2T-A2 | R (EXP-0008 headline set, X families out) | PASS | 5.4 s [5.2, 5.6] | 900 | as EXP-0008: median latency <= 10 s and p90 <= 60 s |
| Q5 | V2T-A2 | R (EXP-0008 headline set, X families out) | PASS | +12.9 [+9.2, +16.4] | 900 | as EXP-0008: the interval of always-agent minus always-Cypher lies above 0 |
| Q4-B | V2T-B | R and X (every X family) | PASS | -0.8 [-5.1, +3.4] | - | the interval contains 0 or lies above it |
| Q4-B sensitivity (no POSITION_OF_VALVE) | V2T-B | R and X without POSITION_OF_VALVE | PASS | -0.5 [-4.6, +4.0] | - | the interval contains 0 or lies above it |
| SB1 | V2T-B minus V2T-A2 | R (EXP-0008 headline set, X families out) | DESCRIPTIVE | +0.1 [-1.7, +1.9] | 1800 | descriptive: the difference and its interval, no margin |
| SB2 | V2T-B minus V2T-A2 | X isolation families | PASS | +7.5 [+3.0, +12.2] | 400 | the interval lies above 0 |
| SB1 S100 | V2T-B minus V2T-A2 | R (EXP-0008 headline set, X families out) | DESCRIPTIVE | +1.1 [-1.2, +3.6] | 900 | descriptive: the difference and its interval, no margin |
| SB2 S100 | V2T-B minus V2T-A2 | X isolation families | DESCRIPTIVE | +8.0 [+0.0, +15.5] | 200 | descriptive: the difference and its interval, no margin |
| SB1 S1000 | V2T-B minus V2T-A2 | R (EXP-0008 headline set, X families out) | DESCRIPTIVE | -0.9 [-3.2, +1.6] | 900 | descriptive: the difference and its interval, no margin |
| SB2 S1000 | V2T-B minus V2T-A2 | X isolation families | DESCRIPTIVE | +7.0 [+2.0, +12.0] | 200 | descriptive: the difference and its interval, no margin |
| Data effect S100 | V2T-A2, v2.2 minus v2.1 | 18 shared families: CONNECTED, COUNT_IN_UNIT, CROSS_UNIT, FEEDING_UNITS, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, SHEETS_OF_TAG, UNANSWERABLE_TAG, UNITS_REACHED, VALVES_ON_PATH | DESCRIPTIVE | -7.6 [-10.1, -5.1] | 1800 | descriptive: unpaired, the same two-stage bootstrap, shared families only |
| Data effect S1000 | V2T-A2, v2.2 minus v2.1 | 18 shared families: CONNECTED, COUNT_IN_UNIT, CROSS_UNIT, FEEDING_UNITS, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, SHEETS_OF_TAG, UNANSWERABLE_TAG, UNITS_REACHED, VALVES_ON_PATH | DESCRIPTIVE | -5.6 [-8.7, -2.7] | 1800 | descriptive: unpaired, the same two-stage bootstrap, shared families only |

Differences are percentage points of acc@C (K3: seconds), 95 % two-stage cluster bootstrap (5,000 resamples, seed 1).

- **Q4**: acc@C S100 0.899 (5 plants), S1000 0.913 (5 plants) (20 runs: S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **K1**: acc@C -0.031 [-0.053, -0.008]: not met | $/question -0.00035 [-0.00056, -0.00018] (needs CI below 0): ok | latency s/question +0.52 [-0.52, +1.61] (needs CI below 0): not met (20 runs: S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **K2**: acc@C +0.067 [+0.050, +0.085] (needs CI above 0) (20 runs: S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **K3**: median 5.4 [5.2, 5.6] s (limit 10): ok | p90 30.2 [25.7, 35.8] s (limit 60): ok (20 runs: S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **Q5**: acc@C +0.129 [+0.092, +0.164] (needs CI above 0) (20 runs: S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **Q4-B**: acc@C S100 0.786 (5 plants), S1000 0.778 (5 plants) (20 runs: S9-CYP-H100g22p1B, S9-AG-H100g22p1B, S9-CYP-H100g22p2B, S9-AG-H100g22p2B, S9-CYP-H100g22p3B, S9-AG-H100g22p3B, S9-CYP-H100g22p4B, S9-AG-H100g22p4B, S9-CYP-H100g22p5B, S9-AG-H100g22p5B, S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B, S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B, S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B, S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B, S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B)
- **Q4-B sensitivity (no POSITION_OF_VALVE)**: acc@C S100 0.776 (5 plants), S1000 0.772 (5 plants) (20 runs: S9-CYP-H100g22p1B, S9-AG-H100g22p1B, S9-CYP-H100g22p2B, S9-AG-H100g22p2B, S9-CYP-H100g22p3B, S9-AG-H100g22p3B, S9-CYP-H100g22p4B, S9-AG-H100g22p4B, S9-CYP-H100g22p5B, S9-AG-H100g22p5B, S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B, S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B, S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B, S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B, S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B)
- **SB1**: (40 runs: S9-CYP-H100g22p1B, S9-AG-H100g22p1B, S9-CYP-H100g22p2B, S9-AG-H100g22p2B, S9-CYP-H100g22p3B, S9-AG-H100g22p3B, S9-CYP-H100g22p4B, S9-AG-H100g22p4B, S9-CYP-H100g22p5B, S9-AG-H100g22p5B, S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B, S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B, S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B, S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B, S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B, S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **SB2**: (40 runs: S9-CYP-H100g22p1B, S9-AG-H100g22p1B, S9-CYP-H100g22p2B, S9-AG-H100g22p2B, S9-CYP-H100g22p3B, S9-AG-H100g22p3B, S9-CYP-H100g22p4B, S9-AG-H100g22p4B, S9-CYP-H100g22p5B, S9-AG-H100g22p5B, S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B, S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B, S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B, S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B, S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B, S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **SB1 S100**: (20 runs: S9-CYP-H100g22p1B, S9-AG-H100g22p1B, S9-CYP-H100g22p2B, S9-AG-H100g22p2B, S9-CYP-H100g22p3B, S9-AG-H100g22p3B, S9-CYP-H100g22p4B, S9-AG-H100g22p4B, S9-CYP-H100g22p5B, S9-AG-H100g22p5B, S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5)
- **SB2 S100**: (20 runs: S9-CYP-H100g22p1B, S9-AG-H100g22p1B, S9-CYP-H100g22p2B, S9-AG-H100g22p2B, S9-CYP-H100g22p3B, S9-AG-H100g22p3B, S9-CYP-H100g22p4B, S9-AG-H100g22p4B, S9-CYP-H100g22p5B, S9-AG-H100g22p5B, S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5)
- **SB1 S1000**: (20 runs: S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B, S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B, S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B, S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B, S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **SB2 S1000**: (20 runs: S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B, S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B, S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B, S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B, S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B, S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5)
- **Data effect S100**: 5 v2.2 plants against 5 v2.1 plants (20 runs: S9-CYP-H100g22p1, S9-AG-H100g22p1, S9-CYP-H100g22p2, S9-AG-H100g22p2, S9-CYP-H100g22p3, S9-AG-H100g22p3, S9-CYP-H100g22p4, S9-AG-H100g22p4, S9-CYP-H100g22p5, S9-AG-H100g22p5, S7-CYP-H100g21p1, S7-AG-H100g21p1, S7-CYP-H100g21p2, S7-AG-H100g21p2, S7-CYP-H100g21p3, S7-AG-H100g21p3, S7-CYP-H100g21p4, S7-AG-H100g21p4, S7-CYP-H100g21p5, S7-AG-H100g21p5)
- **Data effect S1000**: 5 v2.2 plants against 5 v2.1 plants (20 runs: S9-CYP-H1000g22p1, S9-AG-H1000g22p1, S9-CYP-H1000g22p2, S9-AG-H1000g22p2, S9-CYP-H1000g22p3, S9-AG-H1000g22p3, S9-CYP-H1000g22p4, S9-AG-H1000g22p4, S9-CYP-H1000g22p5, S9-AG-H1000g22p5, S7-CYP-H1000g21p1, S7-AG-H1000g21p1, S7-CYP-H1000g21p2, S7-AG-H1000g21p2, S7-CYP-H1000g21p3, S7-AG-H1000g21p3, S7-CYP-H1000g21p4, S7-AG-H1000g21p4, S7-CYP-H1000g21p5, S7-AG-H1000g21p5)

### EXP-0008's own verdict lines for V2T-A2 (cost elasticity included)

- Q4 (primary) cascade_v4_iso [headline]: supported
- K1 [headline]: the cascade loses accuracy; the cascade saves nothing
- K2 [headline]: supported
- K3 [headline]: supported
- Q5 [headline]: supported
- Q4' cascade_v4 [headline]: supported
- Q4' always_g_v2t [headline]: supported
- Q4' always_c_v2t [headline]: supported

## Runs

| plant | scale | sheets | A2 runs | B runs | A2 questions | B questions |
|---|---|---|---|---|---|---|
| H100g22p1 | 100 | 110 | S9-CYP-H100g22p1, S9-AG-H100g22p1 | S9-CYP-H100g22p1B, S9-AG-H100g22p1B | 275 | 285 |
| H100g22p2 | 100 | 90 | S9-CYP-H100g22p2, S9-AG-H100g22p2 | S9-CYP-H100g22p2B, S9-AG-H100g22p2B | 275 | 285 |
| H100g22p3 | 100 | 109 | S9-CYP-H100g22p3, S9-AG-H100g22p3 | S9-CYP-H100g22p3B, S9-AG-H100g22p3B | 275 | 285 |
| H100g22p4 | 100 | 109 | S9-CYP-H100g22p4, S9-AG-H100g22p4 | S9-CYP-H100g22p4B, S9-AG-H100g22p4B | 275 | 285 |
| H100g22p5 | 100 | 100 | S9-CYP-H100g22p5, S9-AG-H100g22p5 | S9-CYP-H100g22p5B, S9-AG-H100g22p5B | 275 | 285 |
| H1000g22p1 | 1000 | 921 | S9-CYP-H1000g22p1, S9-AG-H1000g22p1 | S9-CYP-H1000g22p1B, S9-AG-H1000g22p1B | 275 | 285 |
| H1000g22p2 | 1000 | 1086 | S9-CYP-H1000g22p2, S9-AG-H1000g22p2 | S9-CYP-H1000g22p2B, S9-AG-H1000g22p2B | 275 | 285 |
| H1000g22p3 | 1000 | 1025 | S9-CYP-H1000g22p3, S9-AG-H1000g22p3 | S9-CYP-H1000g22p3B, S9-AG-H1000g22p3B | 275 | 285 |
| H1000g22p4 | 1000 | 1072 | S9-CYP-H1000g22p4, S9-AG-H1000g22p4 | S9-CYP-H1000g22p4B, S9-AG-H1000g22p4B | 275 | 285 |
| H1000g22p5 | 1000 | 1011 | S9-CYP-H1000g22p5, S9-AG-H1000g22p5 | S9-CYP-H1000g22p5B, S9-AG-H1000g22p5B | 275 | 285 |

## Descriptive tables

### Scope X: candidates and refused shares

refused = no unique descriptor for an untagged valve, or an empty gold answer

| scale | family | candidates | no descriptor | empty gold | refused | kept |
|---|---|---|---|---|---|---|
| S100 | DOWNSTREAM_ISOLATION_X | 616 | 10 | 0 | 0.016 | 606 |
| S100 | OPEN_VALVES_TO_ISOLATE | 1300 | 33 | 0 | 0.025 | 1267 |
| S100 | OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | 616 | 10 | 0 | 0.016 | 606 |
| S100 | POSITION_OF_VALVE | 7145 | 379 | 0 | 0.053 | 6766 |
| S100 | UPSTREAM_ISOLATION_X | 1300 | 33 | 0 | 0.025 | 1267 |
| S1000 | DOWNSTREAM_ISOLATION_X | 6385 | 178 | 0 | 0.028 | 6207 |
| S1000 | OPEN_VALVES_TO_ISOLATE | 13534 | 264 | 0 | 0.020 | 13270 |
| S1000 | OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | 6385 | 178 | 0 | 0.028 | 6207 |
| S1000 | POSITION_OF_VALVE | 74608 | 4366 | 0 | 0.059 | 70242 |
| S1000 | UPSTREAM_ISOLATION_X | 13534 | 264 | 0 | 0.020 | 13270 |

### Scope X sub-scopes (acc@C)

B asked every X question, A2 only the isolation families. The flags come from qpool/<plant>/scope_x/flags.json; a question without flags is in no sub-scope.

| scale | sub-scope | questions | B acc@C | A2 acc@C |
|---|---|---|---|---|
| S100 | untagged gold | 194 | 0.304 | 0.000 |
| S100 | tagged gold only | 56 | 0.464 | 0.413 |
| S100 | discriminating | 69 | 0.072 | 0.029 |
| S100 | not discriminating | 31 | 0.419 | 0.258 |
| S1000 | untagged gold | 206 | 0.306 | 0.000 |
| S1000 | tagged gold only | 44 | 0.409 | 0.500 |
| S1000 | discriminating | 54 | 0.204 | 0.074 |
| S1000 | not discriminating | 46 | 0.196 | 0.152 |
| both scales | untagged gold | 400 | 0.305 | 0.000 |
| both scales | tagged gold only | 100 | 0.440 | 0.455 |
| both scales | discriminating | 123 | 0.130 | 0.049 |
| both scales | not discriminating | 77 | 0.286 | 0.195 |

### Scope X per family (acc@C)

| family | scale | questions | B acc@C | A2 acc@C | discriminating share |
|---|---|---|---|---|---|
| DOWNSTREAM_ISOLATION_X | S100 | 50 | 0.000 | 0.000 | - |
| DOWNSTREAM_ISOLATION_X | S1000 | 50 | 0.080 | 0.060 | - |
| DOWNSTREAM_ISOLATION_X | both scales | 100 | 0.040 | 0.030 | - |
| OPEN_VALVES_TO_ISOLATE | S100 | 50 | 0.300 | 0.160 | 0.480 |
| OPEN_VALVES_TO_ISOLATE | S1000 | 50 | 0.220 | 0.120 | 0.480 |
| OPEN_VALVES_TO_ISOLATE | both scales | 100 | 0.260 | 0.140 | 0.480 |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | S100 | 50 | 0.060 | 0.040 | 0.900 |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | S1000 | 50 | 0.180 | 0.100 | 0.600 |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | both scales | 100 | 0.120 | 0.070 | 0.750 |
| POSITION_OF_VALVE | S100 | 50 | 1.000 | - | - |
| POSITION_OF_VALVE | S1000 | 50 | 0.920 | - | - |
| POSITION_OF_VALVE | both scales | 100 | 0.960 | - | - |
| UPSTREAM_ISOLATION_X | S100 | 50 | 0.340 | 0.180 | - |
| UPSTREAM_ISOLATION_X | S1000 | 50 | 0.220 | 0.140 | - |
| UPSTREAM_ISOLATION_X | both scales | 100 | 0.280 | 0.160 | - |

### POSITION_OF_VALVE: B beside the majority and the text prior

all three columns are shares of the same questions; B is acc@C

| scale | group | questions | B acc@C | majority | text prior |
|---|---|---|---|---|---|
| S100 | form: descriptor | 40 | 1.000 | 0.750 | 0.925 |
| S100 | form: tag | 10 | 1.000 | 0.500 | 0.500 |
| S100 | code: NC | 15 | 1.000 | 0.000 | 0.800 |
| S100 | code: NO | 35 | 1.000 | 1.000 | 0.857 |
| S1000 | form: descriptor | 48 | 0.917 | 0.854 | 0.833 |
| S1000 | form: tag | 2 | 1.000 | 0.000 | 1.000 |
| S1000 | code: NC | 9 | 0.889 | 0.000 | 1.000 |
| S1000 | code: NO | 41 | 0.927 | 1.000 | 0.805 |
| both scales | form: descriptor | 88 | 0.955 | 0.807 | 0.875 |
| both scales | form: tag | 12 | 1.000 | 0.417 | 0.583 |
| both scales | code: NC | 24 | 0.958 | 0.000 | 0.875 |
| both scales | code: NO | 76 | 0.961 | 1.000 | 0.829 |

### Realized named_by mix of the POSITION questions

| scale | questions | by tag | by descriptor | tag share |
|---|---|---|---|---|
| S100 | 50 | 10 | 40 | 0.200 |
| S1000 | 50 | 2 | 48 | 0.040 |
| both scales | 100 | 12 | 88 | 0.120 |

### Questions whose evidence touches a network unit

from B's file (every R and X question); a network unit's number is 9000 or more

| scale | scope | family | questions | touching | share |
|---|---|---|---|---|---|
| S100 | R | CONNECTED | 50 | 2 | 0.040 |
| S100 | R | COUNT_IN_UNIT | 50 | 0 | 0.000 |
| S100 | R | CROSS_UNIT | 50 | 1 | 0.020 |
| S100 | R | FEEDING_UNITS | 50 | 3 | 0.060 |
| S100 | R | FLOW_PATH | 50 | 2 | 0.040 |
| S100 | R | INSTRUMENTS_OF_ITEM | 50 | 0 | 0.000 |
| S100 | R | LOOKUP_TYPE | 50 | 0 | 0.000 |
| S100 | R | LOOKUP_UNIT | 50 | 0 | 0.000 |
| S100 | R | LOOPS_NEAR_ITEM | 50 | 0 | 0.000 |
| S100 | R | LOOP_MEASURED_EQUIPMENT | 50 | 0 | 0.000 |
| S100 | R | NEIGHBOURS_DOWNSTREAM | 50 | 7 | 0.140 |
| S100 | R | NO_PATH | 50 | 0 | 0.000 |
| S100 | R | ROUTE_AVOIDING | 50 | 1 | 0.020 |
| S100 | R | SAME_UNIT | 50 | 0 | 0.000 |
| S100 | R | SHEETS_OF_TAG | 50 | 0 | 0.000 |
| S100 | R | UNANSWERABLE_TAG | 50 | 0 | 0.000 |
| S100 | R | UNITS_REACHED | 50 | 7 | 0.140 |
| S100 | R | VALVES_ON_PATH | 50 | 0 | 0.000 |
| S100 | R | all | 900 | 23 | 0.026 |
| S100 | X | DOWNSTREAM_ISOLATION_X | 50 | 0 | 0.000 |
| S100 | X | OPEN_VALVES_TO_ISOLATE | 50 | 0 | 0.000 |
| S100 | X | OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | 50 | 0 | 0.000 |
| S100 | X | POSITION_OF_VALVE | 50 | 0 | 0.000 |
| S100 | X | UPSTREAM_ISOLATION_X | 50 | 0 | 0.000 |
| S100 | X | all | 250 | 0 | 0.000 |
| S1000 | R | CONNECTED | 50 | 4 | 0.080 |
| S1000 | R | COUNT_IN_UNIT | 50 | 0 | 0.000 |
| S1000 | R | CROSS_UNIT | 50 | 2 | 0.040 |
| S1000 | R | FEEDING_UNITS | 50 | 5 | 0.100 |
| S1000 | R | FLOW_PATH | 50 | 2 | 0.040 |
| S1000 | R | INSTRUMENTS_OF_ITEM | 50 | 0 | 0.000 |
| S1000 | R | LOOKUP_TYPE | 50 | 0 | 0.000 |
| S1000 | R | LOOKUP_UNIT | 50 | 1 | 0.020 |
| S1000 | R | LOOPS_NEAR_ITEM | 50 | 0 | 0.000 |
| S1000 | R | LOOP_MEASURED_EQUIPMENT | 50 | 0 | 0.000 |
| S1000 | R | NEIGHBOURS_DOWNSTREAM | 50 | 30 | 0.600 |
| S1000 | R | NO_PATH | 50 | 0 | 0.000 |
| S1000 | R | ROUTE_AVOIDING | 50 | 8 | 0.160 |
| S1000 | R | SAME_UNIT | 50 | 0 | 0.000 |
| S1000 | R | SHEETS_OF_TAG | 50 | 0 | 0.000 |
| S1000 | R | UNANSWERABLE_TAG | 50 | 0 | 0.000 |
| S1000 | R | UNITS_REACHED | 50 | 9 | 0.180 |
| S1000 | R | VALVES_ON_PATH | 50 | 0 | 0.000 |
| S1000 | R | all | 900 | 61 | 0.068 |
| S1000 | X | DOWNSTREAM_ISOLATION_X | 50 | 5 | 0.100 |
| S1000 | X | OPEN_VALVES_TO_ISOLATE | 50 | 0 | 0.000 |
| S1000 | X | OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | 50 | 5 | 0.100 |
| S1000 | X | POSITION_OF_VALVE | 50 | 0 | 0.000 |
| S1000 | X | UPSTREAM_ISOLATION_X | 50 | 0 | 0.000 |
| S1000 | X | all | 250 | 10 | 0.040 |

### rules.json summaries (build-time rule checks, per scale)

| scale | rule | plants | checked | violations | exceptions |
|---|---|---|---|---|---|
| S100 | API14C-3.4-TWO-LEVELS | 5 | 284 | 0 | 57 |
| S100 | API14C-A4-OVERPRESSURE | 5 | 429 | 0 | 21 |
| S100 | API14C-A8-FSV | 5 | 17 | 0 | 0 |
| S100 | API14C-A8-PSV | 5 | 17 | 0 | 0 |
| S100 | API14C-SAC | 5 | 3200 | 0 | 1307 |
| S100 | LIP1-1.1-SHARED-LOOP-NUMBER | 5 | 6261 | 0 | 0 |
| S100 | PLT-NETWORK-CLOSURE | 5 | 978 | 0 | 0 |
| S100 | PLT-PHASE | 5 | 1039 | 0 | 0 |
| S100 | PLT-RECYCLE-CLOSURE | 5 | 355 | 0 | 119 |
| S100 | PLT-STREAM-CLOSURE | 5 | 3351 | 0 | 3351 |
| S100 | PRS-MONOTONE | 5 | 20852 | 0 | 0 |
| S100 | PRS-SPEC-CLASS | 5 | 545 | 0 | 0 |
| S100 | TOG113-AUTOMATIC-VALVE-LETTERS | 5 | 2055 | 0 | 0 |
| S100 | TOG113-MANUAL-VALVE-TAGS | 5 | 10304 | 0 | 0 |
| S100 | TOG114-BLOCK-DEFAULT-NO | 5 | 4243 | 0 | 0 |
| S100 | TOG114-FAIL-ACTION | 5 | 1390 | 0 | 0 |
| S100 | TOG114-VENT-DRAIN-NC | 5 | 2369 | 0 | 0 |
| S100 | TOG120-CV-BYPASS-NC | 5 | 317 | 0 | 0 |
| S100 | TOG122-PV-NO-BYPASS | 5 | 114 | 0 | 0 |
| S100 | TOG141-DRAIN-DESTINATION | 5 | 1247 | 0 | 4 |
| S100 | TOG156-MERGE-CHECK | 5 | 786 | 0 | 0 |
| S100 | TOG173-PUMP-REDUCERS | 5 | 437 | 0 | 0 |
| S100 | TOG175-PUMP-TRIM | 5 | 943 | 0 | 0 |
| S100 | TOG177-MINFLOW-NEED | 5 | 437 | 0 | 0 |
| S100 | TOG177-MINFLOW-TAKEOFF | 5 | 347 | 0 | 0 |
| S100 | TOG192-PD-NO-MINFLOW | 5 | 69 | 0 | 0 |
| S100 | TOG192-RECIP-NO-CHECK | 5 | 506 | 0 | 0 |
| S100 | TOG207-HX-NO-ISOLATION | 5 | 182 | 0 | 35 |
| S100 | TOG207-HX-PSD-BOTH-SIDES | 5 | 342 | 0 | 342 |
| S100 | TOG214-FUEL-SWITCHING-VALVES | 5 | 22 | 0 | 0 |
| S100 | TOG219-PD-RELIEF | 5 | 69 | 0 | 0 |
| S100 | TOG219-VESSEL-PSV | 5 | 223 | 0 | 0 |
| S100 | TOG224-PSV-BLOCKS-CSO | 5 | 216 | 0 | 0 |
| S100 | TOG224-PSV-PIPE-CLEAN | 5 | 566 | 0 | 0 |
| S100 | TOG236-TANK-EMERGENCY-VENT | 5 | 185 | 0 | 85 |
| S100 | TOG24-NO-VISITING-STREAM | 5 | 11232 | 0 | 2 |
| S100 | TOG267-FE-UPSTREAM-FV | 5 | 277 | 0 | 0 |
| S100 | TOG270-PUMP-FLOW-CONTROLLED | 5 | 252 | 0 | 0 |
| S100 | TOG271-ONE-CV-LIQUID | 5 | 2725 | 0 | 588 |
| S100 | TOG28-SPARE-NAMING | 5 | 303 | 0 | 0 |
| S100 | TOG295-INVENTORY-ONCE | 5 | 429 | 0 | 256 |
| S100 | TOG309-SPLIT-PAIRING | 5 | 39 | 0 | 0 |
| S100 | TOG313-MINFLOW-METHOD | 5 | 437 | 0 | 0 |
| S100 | TOG314-PD-NO-THROTTLE | 5 | 69 | 0 | 0 |
| S100 | TOG316-PD-COMP-CAPACITY | 5 | 2 | 0 | 0 |
| S100 | TOG319-ANTISURGE-DYNAMIC | 5 | 2 | 0 | 0 |
| S100 | TOG32-NETWORK-SHEETS | 5 | 330 | 0 | 0 |
| S100 | TOG320-HX-NONTARGET | 5 | 111 | 0 | 0 |
| S100 | TOG322-HX-BYPASS-VARIANT | 5 | 29 | 0 | 0 |
| S100 | TOG326-STEAM-CONDENSATE | 5 | 89 | 0 | 0 |
| S100 | TOG33-INTERAREA | 5 | 2 | 0 | 0 |
| S100 | TOG34-BL-ISOLATION | 5 | 509 | 0 | 0 |
| S100 | TOG360-UTILITY-NETWORKS | 5 | 474 | 0 | 0 |
| S100 | TOG82-SPEC-BREAK | 5 | 15290 | 0 | 0 |
| S1000 | API14C-3.4-TWO-LEVELS | 5 | 3094 | 0 | 578 |
| S1000 | API14C-A4-OVERPRESSURE | 5 | 4453 | 0 | 250 |
| S1000 | API14C-A8-FSV | 5 | 242 | 0 | 0 |
| S1000 | API14C-A8-PSV | 5 | 242 | 0 | 0 |
| S1000 | API14C-SAC | 5 | 33535 | 0 | 13635 |
| S1000 | LIP1-1.1-SHARED-LOOP-NUMBER | 5 | 65573 | 0 | 0 |
| S1000 | PLT-NETWORK-CLOSURE | 5 | 10069 | 0 | 0 |
| S1000 | PLT-PHASE | 5 | 10307 | 0 | 0 |
| S1000 | PLT-RECYCLE-CLOSURE | 5 | 3426 | 0 | 1109 |
| S1000 | PLT-STREAM-CLOSURE | 5 | 34579 | 0 | 34579 |
| S1000 | PRS-MONOTONE | 5 | 216444 | 0 | 0 |
| S1000 | PRS-SPEC-CLASS | 5 | 5568 | 0 | 0 |
| S1000 | TOG113-AUTOMATIC-VALVE-LETTERS | 5 | 20647 | 0 | 0 |
| S1000 | TOG113-MANUAL-VALVE-TAGS | 5 | 106948 | 0 | 0 |
| S1000 | TOG114-BLOCK-DEFAULT-NO | 5 | 44245 | 0 | 0 |
| S1000 | TOG114-FAIL-ACTION | 5 | 14190 | 0 | 0 |
| S1000 | TOG114-VENT-DRAIN-NC | 5 | 24521 | 0 | 0 |
| S1000 | TOG120-CV-BYPASS-NC | 5 | 3126 | 0 | 0 |
| S1000 | TOG122-PV-NO-BYPASS | 5 | 1137 | 0 | 0 |
| S1000 | TOG141-DRAIN-DESTINATION | 5 | 12866 | 0 | 45 |
| S1000 | TOG156-MERGE-CHECK | 5 | 7723 | 0 | 0 |
| S1000 | TOG173-PUMP-REDUCERS | 5 | 4435 | 0 | 0 |
| S1000 | TOG175-PUMP-TRIM | 5 | 9530 | 0 | 0 |
| S1000 | TOG177-MINFLOW-NEED | 5 | 4435 | 0 | 0 |
| S1000 | TOG177-MINFLOW-TAKEOFF | 5 | 3304 | 0 | 0 |
| S1000 | TOG192-PD-NO-MINFLOW | 5 | 660 | 0 | 0 |
| S1000 | TOG192-RECIP-NO-CHECK | 5 | 5095 | 0 | 0 |
| S1000 | TOG207-HX-NO-ISOLATION | 5 | 1964 | 0 | 392 |
| S1000 | TOG207-HX-PSD-BOTH-SIDES | 5 | 3697 | 0 | 3697 |
| S1000 | TOG214-FUEL-SWITCHING-VALVES | 5 | 231 | 0 | 0 |
| S1000 | TOG219-PD-RELIEF | 5 | 660 | 0 | 0 |
| S1000 | TOG219-VESSEL-PSV | 5 | 2455 | 0 | 0 |
| S1000 | TOG224-PSV-BLOCKS-CSO | 5 | 2716 | 0 | 0 |
| S1000 | TOG224-PSV-PIPE-CLEAN | 5 | 6032 | 0 | 0 |
| S1000 | TOG236-TANK-EMERGENCY-VENT | 5 | 1748 | 0 | 797 |
| S1000 | TOG24-NO-VISITING-STREAM | 5 | 116603 | 0 | 46 |
| S1000 | TOG267-FE-UPSTREAM-FV | 5 | 2794 | 0 | 0 |
| S1000 | TOG270-PUMP-FLOW-CONTROLLED | 5 | 2620 | 0 | 0 |
| S1000 | TOG271-ONE-CV-LIQUID | 5 | 26906 | 0 | 5830 |
| S1000 | TOG28-SPARE-NAMING | 5 | 3006 | 0 | 0 |
| S1000 | TOG295-INVENTORY-ONCE | 5 | 4453 | 0 | 2621 |
| S1000 | TOG309-SPLIT-PAIRING | 5 | 477 | 0 | 0 |
| S1000 | TOG313-MINFLOW-METHOD | 5 | 4435 | 0 | 0 |
| S1000 | TOG314-PD-NO-THROTTLE | 5 | 660 | 0 | 0 |
| S1000 | TOG316-PD-COMP-CAPACITY | 5 | 59 | 0 | 0 |
| S1000 | TOG319-ANTISURGE-DYNAMIC | 5 | 59 | 0 | 0 |
| S1000 | TOG32-NETWORK-SHEETS | 5 | 3639 | 0 | 0 |
| S1000 | TOG320-HX-NONTARGET | 5 | 1266 | 0 | 0 |
| S1000 | TOG322-HX-BYPASS-VARIANT | 5 | 307 | 0 | 0 |
| S1000 | TOG326-STEAM-CONDENSATE | 5 | 965 | 0 | 0 |
| S1000 | TOG33-INTERAREA | 5 | 46 | 0 | 0 |
| S1000 | TOG34-BL-ISOLATION | 5 | 5235 | 0 | 0 |
| S1000 | TOG360-UTILITY-NETWORKS | 5 | 5114 | 0 | 0 |
| S1000 | TOG82-SPEC-BREAK | 5 | 158638 | 0 | 0 |

### Precision, recall and F1 of list answers (agent tier)

from END's offline re-score of the saved answers; list answers only

| arm | scale | plants re-scored | list answers | precision | recall | F1 |
|---|---|---|---|---|---|---|
| V2T-A2 | S100 | 5 | 534 | 0.813 | 0.763 | 0.777 |
| V2T-A2 | S1000 | 5 | 523 | 0.806 | 0.770 | 0.780 |
| V2T-A2 | both scales | 10 | 1057 | 0.809 | 0.767 | 0.778 |
| V2T-B | S100 | 5 | 569 | 0.940 | 0.801 | 0.829 |
| V2T-B | S1000 | 5 | 566 | 0.927 | 0.787 | 0.816 |
| V2T-B | both scales | 10 | 1135 | 0.933 | 0.794 | 0.822 |

### Precision, recall and F1 of list answers: the cascade's final answers

each question is scored from the tier that answered it; 'from Cypher' and 'from agent' count all final answers of that tier (list answers or not)

| arm | scale | plants re-scored (both tiers) | list answers | from Cypher | from agent | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|
| V2T-A2 | S100 | 5 | 537 | 979 | 391 | 0.783 | 0.753 | 0.749 |
| V2T-A2 | S1000 | 5 | 527 | 949 | 423 | 0.796 | 0.754 | 0.765 |
| V2T-A2 | both scales | 10 | 1064 | 1928 | 814 | 0.790 | 0.753 | 0.757 |
| V2T-B | S100 | 5 | 569 | 1020 | 404 | 0.859 | 0.777 | 0.775 |
| V2T-B | S1000 | 5 | 567 | 979 | 444 | 0.913 | 0.790 | 0.811 |
| V2T-B | both scales | 10 | 1136 | 1999 | 848 | 0.886 | 0.784 | 0.793 |

## Notes

- pooled scales: S100 (5 plants), S1000 (5 plants); the pooled value is the equal-weight mean of the plants, intervals are two-stage cluster bootstraps (plants, then questions) with the EXP-0007 seed and resample count
- with few plants the bootstrap understates between-plant variance (about 4/5 at five plants); pooled latency intervals resample questions only
- the plant-robustness table counts plants whose own acc@C difference has the pooled sign; it is descriptive and judges nothing
- H100g22p1: no splits.json beside the questions, so there is no split table and no held-out scope
- H100g22p2: no splits.json beside the questions, so there is no split table and no held-out scope
- H100g22p3: no splits.json beside the questions, so there is no split table and no held-out scope
- H100g22p4: no splits.json beside the questions, so there is no split table and no held-out scope
- H100g22p5: no splits.json beside the questions, so there is no split table and no held-out scope
- H1000g22p1: no splits.json beside the questions, so there is no split table and no held-out scope
- H1000g22p2: no splits.json beside the questions, so there is no split table and no held-out scope
- H1000g22p3: no splits.json beside the questions, so there is no split table and no held-out scope
- H1000g22p4: no splits.json beside the questions, so there is no split table and no held-out scope
- H1000g22p5: no splits.json beside the questions, so there is no split table and no held-out scope
- scope `headline` leaves out the family LOOP_ACTUATED_VALVE (ADR-0044 U2)
