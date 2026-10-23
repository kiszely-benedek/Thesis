# Method-and-effort cascade report

Latency counts every model call of a question (final answer, retrieval and agent steps) plus local compute where recorded, summed over the tiers tried. LB-1: median <= 10 s; LB-2: p90 <= 60 s; LB-3: an answer later than C = 120 s counts as no answer (TIMED_OUT, wrong) for every arm alike, so acc@120 is the cutoff-scored accuracy. A run made under a live deadline cannot show raw accuracy beyond C.

## Pre-registered rules (S1-S3: cascade v1 record; V2-V3: cascade v2)

- **S1: INCOMPLETE** - candidates without a row for every dev runaway: need-mimo, need-low, need-default-64k
  - need-mimo: 0/35 correct (0 rows stored), cost $0.0000, mean latency 0.0 s
  - need-low: 0/35 correct (0 rows stored), cost $0.0000, mean latency 0.0 s
  - need-default-64k: 0/35 correct (0 rows stored), cost $0.0000, mean latency 0.0 s
  - dev corpora pooled: D100, D1000
- **S2: PASS** - cascade_v1 on D1000
  - accuracy 161 vs always-N 151 (needs >= 149): ok
  - cost per question $0.00209 vs $0.00322 (needs lower): ok
- **S3 cascade_v1_iso: PASS** - cascade_v1_iso vs cascade_v1 on D1000
  - +3 questions (needs >= 2): ok
  - total cost $0.4021 vs limit $0.4696 (1.25x primary): ok
- **S3 label_router_dev: INCOMPLETE** - label_router_dev or cascade_v1 is not evaluated on D1000
- **V2: SELECTED** - cascade_v2_iso on D100
  - cascade_v1: acc@120 160/180, median 5.7 s, p90 56.6 s, $0.00135/question (eligible)
  - cascade_v1_iso: acc@120 162/180, median 5.7 s, p90 71.9 s, $0.00148/question (not eligible)
  - cascade_v2: acc@120 173/180, median 5.7 s, p90 23.9 s, $0.00063/question (eligible)
  - cascade_v2_iso: acc@120 176/180, median 5.7 s, p90 26.6 s, $0.00066/question (eligible)
- **V3: PASS** - cascade_v2_iso confirmed on D1000
  - cascade_v1: acc@120 154/180, median 7.5 s, p90 107.8 s, $0.00209/question (not eligible)
  - cascade_v1_iso: acc@120 156/180, median 7.5 s, p90 126.2 s, $0.00223/question (not eligible)
  - cascade_v2: acc@120 170/180, median 7.3 s, p90 29.4 s, $0.00078/question (eligible)
  - cascade_v2_iso: acc@120 175/180, median 7.3 s, p90 30.5 s, $0.00088/question (eligible)

## Tier-3 candidates on the dev runaways (S1)

| tier-3 candidate | correct on dev runaways | rows stored | cost $ | mean latency s |
|---|---|---|---|---|
| need-mimo | 0/35 | 0 | 0.0000 | 0.0 |
| need-low | 0/35 | 0 | 0.0000 | 0.0 |
| need-default-64k | 0/35 | 0 | 0.0000 | 0.0 |

## Corpus D100 (180 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v1 | 167/180 | 160/180 | 0.2425 | 0.00135 | 5.7 / 23.3 / 56.6 / 150.2 / 196.6 | cypher-low 73%, need-default 25%, none 2% | 0.944 (118/125) | 0.837 (118/141) |
| cascade_v1_iso | 170/180 | 162/180 | 0.2663 | 0.00148 | 5.7 / 24.5 / 71.9 / 176.7 / 194.6 | cypher-low 69%, need-default 27%, none 4% | - | - |
| cascade_v2 | 173/180 | 173/180 | 0.1132 | 0.00063 | 5.7 / 11.3 / 23.9 / 32.2 / 150.2 | cypher-low 69%, agent-low-steps 31% | 0.944 (118/125) | 0.837 (118/141) |
| cascade_v2_iso | 176/180 | 176/180 | 0.1194 | 0.00066 | 5.7 / 10.8 / 26.6 / 34.8 / 83.3 | cypher-low 67%, agent-low-steps 33% | - | - |
| always_c | 141/180 | 141/180 | 0.0420 | 0.00023 | 4.8 / 6.8 / 10.6 / 14.6 / 150.2 | cypher-low 97%, none 3% | - | - |
| always_n | 157/180 | 152/180 | 0.4692 | 0.00261 | 8.7 / 35.5 / 121.6 / 174.1 / 188.0 | need-default 92%, none 8% | - | - |
| always_g | 173/180 | 173/180 | 0.1986 | 0.00110 | 7.2 / 14.5 / 35.0 / 40.9 / 120.0 | agent-low-steps 99%, none 1% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v1 | 14 | 7 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v1_iso | 15 | 8 | 0 | LB-1 PASS | LB-2 FAIL |
| cascade_v2 | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v2_iso | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_n | 20 | 5 | 0 | LB-1 PASS | LB-2 FAIL |
| always_g | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |

### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v1 | +0.056 [+0.011, +0.106] | +0.044 [+0.000, +0.094] | -0.00126 [-0.00162, -0.00092] | -12.2 [-17.3, -7.3] |
| cascade_v1_iso | +0.072 [+0.033, +0.117] | +0.056 [+0.011, +0.100] | -0.00113 [-0.00147, -0.00081] | -11.0 [-15.7, -6.5] |
| cascade_v2 | +0.089 [+0.033, +0.144] | +0.117 [+0.061, +0.172] | -0.00198 [-0.00240, -0.00155] | -24.2 [-31.1, -17.6] |
| cascade_v2_iso | +0.106 [+0.056, +0.161] | +0.133 [+0.083, +0.189] | -0.00194 [-0.00237, -0.00151] | -24.7 [-31.7, -18.1] |
| always_c | -0.089 [-0.161, -0.017] | -0.061 [-0.133, +0.011] | -0.00237 [-0.00282, -0.00195] | -28.7 [-36.0, -21.7] |
| always_g | +0.089 [+0.044, +0.139] | +0.117 [+0.072, +0.167] | -0.00150 [-0.00192, -0.00108] | -21.0 [-27.5, -14.5] |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v1 | 167 / 160 | 172 / 169 ($0.1825) | 148.4 [143, 154] / 144.1 [138, 150] ($0.1849, 55 escalated) |
| cascade_v2 | 173 / 173 | 178 / 178 ($0.0859) | 151.3 [146, 157] / 150.7 [145, 156] ($0.1024, 55 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v1 | +0.104 [+0.067, +0.143] | +0.088 [+0.047, +0.130] | +0.00032 [+0.00002, +0.00067] | +5.8 [+1.0, +11.2] |
| cascade_v2 | +0.120 [+0.081, +0.162] | +0.124 [+0.084, +0.165] | +0.00006 [-0.00006, +0.00019] | +0.1 [-1.4, +1.6] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v2 | agent-low-steps | 55 | 48 | 0 | 1 | 5 | 1 | 0 | 0 | 0 | 0 |
| cascade_v2_iso | agent-low-steps | 60 | 52 | 0 | 1 | 6 | 1 | 0 | 0 | 0 | 0 |
| always_g | agent-low-steps | 180 | 169 | 0 | 1 | 9 | 1 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v2 | 0 (0 correct) | 5 (5 correct) |
| cascade_v2_iso | 0 (0 correct) | 5 (5 correct) |
| always_g | 0 (0 correct) | 5 (5 correct) |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v1 | 12 | 0 |
| cascade_v1_iso | 12 | 0 |
| cascade_v2 | 12 | 0 |
| cascade_v2_iso | 12 | 0 |
| always_c | 12 | 0 |
| always_n | 12 | 0 |
| always_g | 12 | 0 |

### Abandoned calls: estimate against logged late charges

| run | strategy | abandoned calls | timeouts logged | late answers | estimate |
|---|---|---|---|---|---|
| CV2-AG-D100 | graph_agent_low_steps | 2 | 2 | 1 ($0.0024) | $0.0212 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v1 | cascade_v1_iso | cascade_v2 | cascade_v2_iso | always_c | always_n | always_g |
|---|---|---|---|---|---|---|---|
| DOWNSTREAM_ALL | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 8/10 |
| GENERIC | 8/10 | 8/10 | 8/10 | 8/10 | 6/10 | 10/10 | 10/10 |
| ITEM | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 |
| NEIGHBOURS_DOWNSTREAM | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 |
| PATH | 32/34 | 32/34 | 34/34 | 34/34 | 28/34 | 25/34 | 34/34 |
| SIGNAL_CHAIN | 30/30 | 30/30 | 30/30 | 30/30 | 12/30 | 30/30 | 30/30 |
| UNIT_SCOPE | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 | 20/20 |
| UPSTREAM_ALL | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 5/10 | 7/10 |
| UPSTREAM_TO_FIRST_VALVE | 1/10 | 4/10 | 5/10 | 8/10 | 0/10 | 4/10 | 8/10 |

#### By family

| group | cascade_v1 | cascade_v1_iso | cascade_v2 | cascade_v2_iso | always_c | always_n | always_g |
|---|---|---|---|---|---|---|---|
| CONNECTED | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 |
| COUNT_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| CROSS_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 |
| DOWNSTREAM_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 8/10 |
| FLOW_PATH | 9/10 | 9/10 | 10/10 | 10/10 | 7/10 | 6/10 | 10/10 |
| INSTRUMENTS_OF_ITEM | 10/10 | 10/10 | 10/10 | 10/10 | 1/10 | 10/10 | 10/10 |
| LOOKUP_TYPE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOPS_NEAR_ITEM | 8/10 | 8/10 | 8/10 | 8/10 | 6/10 | 10/10 | 10/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_MEASURED_EQUIPMENT | 10/10 | 10/10 | 10/10 | 10/10 | 1/10 | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| NO_PATH | 9/10 | 9/10 | 10/10 | 10/10 | 8/10 | 5/10 | 10/10 |
| SAME_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UPSTREAM_ISOLATION | 1/10 | 4/10 | 5/10 | 8/10 | 0/10 | 4/10 | 8/10 |
| UPSTREAM_SOURCES | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 5/10 | 7/10 |

#### By k bin

| group | cascade_v1 | cascade_v1_iso | cascade_v2 | cascade_v2_iso | always_c | always_n | always_g |
|---|---|---|---|---|---|---|---|
| k=0 | 65/68 | 65/68 | 67/68 | 67/68 | 44/68 | 66/68 | 68/68 |
| k=1-2 | 46/53 | 49/53 | 47/53 | 50/53 | 45/53 | 48/53 | 51/53 |
| k>=3 | 37/39 | 37/39 | 39/39 | 39/39 | 34/39 | 28/39 | 34/39 |
| unanswerable | 19/20 | 19/20 | 20/20 | 20/20 | 18/20 | 15/20 | 20/20 |

## Corpus D1000 (180 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v1 | 161/180 | 154/180 | 0.3757 | 0.00209 | 7.5 / 31.3 / 107.8 / 173.0 / 299.3 | cypher-low 66%, need-default 32%, none 2% | 0.921 (105/114) | 0.808 (105/130) |
| cascade_v1_iso | 164/180 | 156/180 | 0.4021 | 0.00223 | 7.5 / 37.0 / 126.2 / 178.9 / 422.1 | cypher-low 62%, need-default 34%, none 4% | - | - |
| cascade_v2 | 170/180 | 170/180 | 0.1395 | 0.00078 | 7.3 / 14.2 / 29.4 / 41.5 / 257.2 | cypher-low 63%, agent-low-steps 37% | 0.921 (105/114) | 0.808 (105/130) |
| cascade_v2_iso | 175/180 | 175/180 | 0.1590 | 0.00088 | 7.3 / 13.7 / 30.5 / 44.2 / 122.3 | cypher-low 59%, agent-low-steps 40%, none 1% | - | - |
| always_c | 130/180 | 130/180 | 0.0463 | 0.00026 | 5.1 / 7.6 / 11.4 / 15.0 / 257.2 | cypher-low 94%, none 6% | - | - |
| always_n | 151/180 | 145/180 | 0.5802 | 0.00322 | 14.9 / 51.8 / 167.4 / 253.4 / 422.1 | need-default 89%, none 11% | - | - |
| always_g | 172/180 | 172/180 | 0.2625 | 0.00146 | 9.2 / 17.8 / 38.1 / 63.3 / 122.3 | agent-low-steps 97%, none 3% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v1 | 16 | 7 | 0 | LB-1 PASS | LB-2 FAIL |
| cascade_v1_iso | 19 | 8 | 0 | LB-1 PASS | LB-2 FAIL |
| cascade_v2 | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v2_iso | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_n | 29 | 6 | 0 | LB-1 FAIL | LB-2 FAIL |
| always_g | 5 | 0 | 0 | LB-1 PASS | LB-2 PASS |

### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v1 | +0.056 [+0.006, +0.111] | +0.050 [+0.006, +0.100] | -0.00114 [-0.00154, -0.00077] | -20.5 [-32.1, -10.9] |
| cascade_v1_iso | +0.072 [+0.028, +0.122] | +0.061 [+0.017, +0.106] | -0.00099 [-0.00137, -0.00065] | -14.8 [-23.6, -7.3] |
| cascade_v2 | +0.106 [+0.050, +0.167] | +0.139 [+0.078, +0.200] | -0.00245 [-0.00317, -0.00184] | -37.6 [-50.1, -26.4] |
| cascade_v2_iso | +0.133 [+0.078, +0.194] | +0.167 [+0.106, +0.233] | -0.00234 [-0.00307, -0.00171] | -38.1 [-50.3, -27.0] |
| always_c | -0.117 [-0.194, -0.039] | -0.083 [-0.161, +0.000] | -0.00297 [-0.00371, -0.00233] | -44.1 [-57.0, -32.7] |
| always_g | +0.117 [+0.067, +0.172] | +0.150 [+0.094, +0.211] | -0.00176 [-0.00255, -0.00109] | -34.0 [-45.3, -23.7] |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v1 | 161 / 154 | 168 / 165 ($0.2305) | 141.8 [136, 148] / 135.5 [129, 143] ($0.2583, 66 escalated) |
| cascade_v2 | 170 / 170 | 180 / 179 ($0.1155) | 147.2 [141, 153] / 145.0 [139, 152] ($0.1423, 66 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v1 | +0.107 [+0.068, +0.146] | +0.103 [+0.060, +0.144] | +0.00065 [+0.00021, +0.00117] | +4.7 [-2.3, +11.7] |
| cascade_v2 | +0.127 [+0.083, +0.168] | +0.139 [+0.097, +0.180] | -0.00002 [-0.00024, +0.00019] | +0.1 [-2.0, +2.1] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v2 | agent-low-steps | 66 | 60 | 1 | 0 | 4 | 1 | 0 | 0 | 0 | 0 |
| cascade_v2_iso | agent-low-steps | 73 | 64 | 1 | 0 | 7 | 1 | 0 | 0 | 0 | 0 |
| always_g | agent-low-steps | 180 | 168 | 2 | 0 | 9 | 1 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v2 | 0 (0 correct) | 5 (5 correct) |
| cascade_v2_iso | 0 (0 correct) | 5 (5 correct) |
| always_g | 0 (0 correct) | 5 (5 correct) |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v1 | 15 | 0 |
| cascade_v1_iso | 15 | 0 |
| cascade_v2 | 15 | 0 |
| cascade_v2_iso | 15 | 0 |
| always_c | 15 | 0 |
| always_n | 15 | 0 |
| always_g | 15 | 0 |

### Abandoned calls: estimate against logged late charges

| run | strategy | abandoned calls | timeouts logged | late answers | estimate |
|---|---|---|---|---|---|
| CV2-AG-D1000 | graph_agent_low_steps | 7 | 7 | 5 ($0.0220) | $0.0742 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v1 | cascade_v1_iso | cascade_v2 | cascade_v2_iso | always_c | always_n | always_g |
|---|---|---|---|---|---|---|---|
| DOWNSTREAM_ALL | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 7/10 |
| GENERIC | 6/10 | 6/10 | 7/10 | 7/10 | 1/10 | 9/10 | 10/10 |
| ITEM | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 |
| NEIGHBOURS_DOWNSTREAM | 14/15 | 14/15 | 15/15 | 15/15 | 13/15 | 13/15 | 15/15 |
| PATH | 28/34 | 28/34 | 33/34 | 33/34 | 23/34 | 24/34 | 33/34 |
| SIGNAL_CHAIN | 30/30 | 30/30 | 30/30 | 30/30 | 12/30 | 30/30 | 30/30 |
| UNIT_SCOPE | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 | 19/20 |
| UPSTREAM_ALL | 9/10 | 9/10 | 10/10 | 10/10 | 9/10 | 3/10 | 8/10 |
| UPSTREAM_TO_FIRST_VALVE | 3/10 | 6/10 | 4/10 | 9/10 | 1/10 | 6/10 | 9/10 |

#### By family

| group | cascade_v1 | cascade_v1_iso | cascade_v2 | cascade_v2_iso | always_c | always_n | always_g |
|---|---|---|---|---|---|---|---|
| CONNECTED | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| COUNT_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| CROSS_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 |
| DOWNSTREAM_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 6/10 | 7/10 |
| FLOW_PATH | 5/10 | 5/10 | 10/10 | 10/10 | 2/10 | 4/10 | 10/10 |
| INSTRUMENTS_OF_ITEM | 10/10 | 10/10 | 10/10 | 10/10 | 2/10 | 10/10 | 10/10 |
| LOOKUP_TYPE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOPS_NEAR_ITEM | 6/10 | 6/10 | 7/10 | 7/10 | 1/10 | 9/10 | 10/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_MEASURED_EQUIPMENT | 10/10 | 10/10 | 10/10 | 10/10 | 0/10 | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 | 10/10 |
| NO_PATH | 9/10 | 9/10 | 9/10 | 9/10 | 8/10 | 7/10 | 9/10 |
| SAME_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 9/10 | 9/10 | 10/10 | 10/10 | 8/10 | 8/10 | 10/10 |
| UPSTREAM_ISOLATION | 3/10 | 6/10 | 4/10 | 9/10 | 1/10 | 6/10 | 9/10 |
| UPSTREAM_SOURCES | 9/10 | 9/10 | 10/10 | 10/10 | 9/10 | 3/10 | 8/10 |

#### By k bin

| group | cascade_v1 | cascade_v1_iso | cascade_v2 | cascade_v2_iso | always_c | always_n | always_g |
|---|---|---|---|---|---|---|---|
| k=0 | 67/69 | 68/69 | 67/69 | 67/69 | 46/69 | 68/69 | 68/69 |
| k=1-2 | 38/45 | 40/45 | 40/45 | 43/45 | 33/45 | 38/45 | 44/45 |
| k>=3 | 38/46 | 38/46 | 44/46 | 46/46 | 35/46 | 30/46 | 41/46 |
| unanswerable | 18/20 | 18/20 | 19/20 | 19/20 | 16/20 | 15/20 | 19/20 |
