# Method-and-effort cascade report

Latency counts every model call of a question (final answer, retrieval and agent steps) plus local compute where recorded, summed over the tiers tried. LB-1: median <= 10 s; LB-2: p90 <= 60 s; LB-3: an answer later than C = 120 s counts as no answer (TIMED_OUT, wrong) for every arm alike, so acc@120 is the cutoff-scored accuracy. A run made under a live deadline cannot show raw accuracy beyond C.

## Pre-registered rules (S1-S3: cascade v1 record; V2-V3: cascade v2)

- **S1: INCOMPLETE** - candidates without a row for every dev runaway: need-mimo, need-low, need-default-64k
  - need-mimo: 0/35 correct (0 rows stored), cost $0.0000, mean latency 0.0 s
  - need-low: 0/35 correct (0 rows stored), cost $0.0000, mean latency 0.0 s
  - need-default-64k: 0/35 correct (0 rows stored), cost $0.0000, mean latency 0.0 s
  - dev corpora pooled: D100, D1000
- **S2: INCOMPLETE** - cascade_v1 or always_n is not evaluated on D1000
- **S3 cascade_v1_iso: INCOMPLETE** - cascade_v1_iso or cascade_v1 is not evaluated on D1000
- **S3 label_router_dev: INCOMPLETE** - label_router_dev or cascade_v1 is not evaluated on D1000
- **V2: INCOMPLETE** - not evaluated on D100: cascade_v1, cascade_v1_iso
- **V3: INCOMPLETE** - not evaluated on D1000: cascade_v1, cascade_v1_iso

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
| cascade_v2 | 173/180 | 173/180 | 0.1491 | 0.00083 | 5.7 / 12.1 / 29.9 / 42.2 / 150.2 | cypher-low 69%, agent-low-steps 31% | 0.944 (118/125) | 0.837 (118/141) |
| cascade_v2_iso | 175/180 | 175/180 | 0.1590 | 0.00088 | 5.7 / 11.9 / 31.0 / 42.2 / 93.9 | cypher-low 67%, agent-low-steps 33% | - | - |
| always_c | 141/180 | 141/180 | 0.0420 | 0.00023 | 4.8 / 6.8 / 10.6 / 14.6 / 150.2 | cypher-low 97%, none 3% | - | - |
| always_g | 173/180 | 173/180 | 0.2379 | 0.00132 | 7.2 / 15.5 / 36.6 / 53.1 / 120.0 | agent-low-steps 99%, none 1% | - | - |
| always_n | 157/180 | 152/180 | 0.4692 | 0.00261 | 8.7 / 35.5 / 121.6 / 174.1 / 188.0 | need-default 92%, none 8% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v2 | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v2_iso | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_g | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_n | 20 | 5 | 0 | LB-1 PASS | LB-2 FAIL |

### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v2 | +0.089 [+0.033, +0.144] | +0.117 [+0.061, +0.172] | -0.00178 [-0.00223, -0.00133] | -23.4 [-30.2, -16.9] |
| cascade_v2_iso | +0.100 [+0.050, +0.150] | +0.128 [+0.078, +0.183] | -0.00172 [-0.00217, -0.00128] | -23.5 [-30.4, -16.9] |
| always_c | -0.089 [-0.161, -0.017] | -0.061 [-0.133, +0.011] | -0.00237 [-0.00282, -0.00195] | -28.7 [-36.0, -21.7] |
| always_g | +0.089 [+0.039, +0.139] | +0.117 [+0.067, +0.167] | -0.00129 [-0.00171, -0.00084] | -20.0 [-26.5, -13.7] |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v2 | 173 / 173 | 177 / 177 ($0.0917) | 151.4 [146, 157] / 150.7 [145, 156] ($0.1145, 55 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v2 | +0.120 [+0.081, +0.162] | +0.124 [+0.084, +0.165] | +0.00019 [+0.00001, +0.00040] | +0.6 [-1.0, +2.3] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v2 | agent-low-steps | 55 | 47 | 2 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| cascade_v2_iso | agent-low-steps | 60 | 51 | 2 | 0 | 7 | 0 | 0 | 0 | 0 | 0 |
| always_g | agent-low-steps | 180 | 169 | 2 | 0 | 9 | 0 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v2 | 0 (0 correct) | 5 (5 correct) |
| cascade_v2_iso | 0 (0 correct) | 5 (5 correct) |
| always_g | 0 (0 correct) | 5 (5 correct) |

### Agent tier: a tag named in the question was never touched

| policy | questions naming a tag | never touched |
|---|---|---|
| cascade_v2 | 49 | 5 (5 correct) |
| cascade_v2_iso | 54 | 5 (5 correct) |
| always_g | 154 | 5 (5 correct) |

### UPSTREAM_ISOLATION: secondary score, control valves do not isolate

Secondary only (offline re-score); the primary score is the gold key as built. Secondary reference = gold minus control valves.

| policy | primary correct | secondary correct |
|---|---|---|
| cascade_v2 | 5/10 | 3/8 |
| cascade_v2_iso | 7/10 | 5/8 |
| always_c | 0/10 | 0/8 |
| always_g | 7/10 | 5/8 |
| always_n | 4/10 | 4/8 |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v2 | 12 | 0 |
| cascade_v2_iso | 12 | 0 |
| always_c | 12 | 0 |
| always_g | 12 | 0 |
| always_n | 12 | 0 |

### Abandoned calls: estimate against logged late charges

| run | strategy | abandoned calls | timeouts logged | late answers | estimate |
|---|---|---|---|---|---|
| CV2-AG2-D100 | graph_agent_low_steps | 4 | 4 | 2 ($0.0094) | $0.0424 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v2 | cascade_v2_iso | always_c | always_g | always_n |
|---|---|---|---|---|---|
| DOWNSTREAM_ALL | 10/10 | 10/10 | 10/10 | 9/10 | 8/10 |
| GENERIC | 8/10 | 8/10 | 6/10 | 10/10 | 10/10 |
| ITEM | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 |
| NEIGHBOURS_DOWNSTREAM | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 |
| PATH | 34/34 | 34/34 | 28/34 | 34/34 | 25/34 |
| SIGNAL_CHAIN | 30/30 | 30/30 | 12/30 | 30/30 | 30/30 |
| UNIT_SCOPE | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 |
| UPSTREAM_ALL | 10/10 | 10/10 | 9/10 | 7/10 | 5/10 |
| UPSTREAM_TO_FIRST_VALVE | 5/10 | 7/10 | 0/10 | 7/10 | 4/10 |

#### By family

| group | cascade_v2 | cascade_v2_iso | always_c | always_g | always_n |
|---|---|---|---|---|---|
| CONNECTED | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 |
| COUNT_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| CROSS_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 |
| DOWNSTREAM_IN_UNIT | 10/10 | 10/10 | 10/10 | 9/10 | 8/10 |
| FLOW_PATH | 10/10 | 10/10 | 7/10 | 10/10 | 6/10 |
| INSTRUMENTS_OF_ITEM | 10/10 | 10/10 | 1/10 | 10/10 | 10/10 |
| LOOKUP_TYPE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOPS_NEAR_ITEM | 8/10 | 8/10 | 6/10 | 10/10 | 10/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_MEASURED_EQUIPMENT | 10/10 | 10/10 | 1/10 | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| NO_PATH | 10/10 | 10/10 | 8/10 | 10/10 | 5/10 |
| SAME_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UPSTREAM_ISOLATION | 5/10 | 7/10 | 0/10 | 7/10 | 4/10 |
| UPSTREAM_SOURCES | 10/10 | 10/10 | 9/10 | 7/10 | 5/10 |

#### By k bin

| group | cascade_v2 | cascade_v2_iso | always_c | always_g | always_n |
|---|---|---|---|---|---|
| k=0 | 67/68 | 67/68 | 44/68 | 68/68 | 66/68 |
| k=1-2 | 47/53 | 49/53 | 45/53 | 50/53 | 48/53 |
| k>=3 | 39/39 | 39/39 | 34/39 | 35/39 | 28/39 |
| unanswerable | 20/20 | 20/20 | 18/20 | 20/20 | 15/20 |

## Corpus D1000 (180 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v2 | 171/180 | 171/180 | 0.1525 | 0.00085 | 7.3 / 14.6 / 33.3 / 45.4 / 257.2 | cypher-low 63%, agent-low-steps 37% | 0.921 (105/114) | 0.808 (105/130) |
| cascade_v2_iso | 176/180 | 176/180 | 0.1718 | 0.00095 | 7.3 / 14.0 / 33.3 / 47.3 / 120.9 | cypher-low 59%, agent-low-steps 40%, none 1% | - | - |
| always_c | 130/180 | 130/180 | 0.0463 | 0.00026 | 5.1 / 7.6 / 11.4 / 15.0 / 257.2 | cypher-low 94%, none 6% | - | - |
| always_g | 173/180 | 173/180 | 0.2741 | 0.00152 | 9.4 / 18.0 / 43.3 / 58.6 / 121.8 | agent-low-steps 97%, none 3% | - | - |
| always_n | 151/180 | 145/180 | 0.5802 | 0.00322 | 14.9 / 51.8 / 167.4 / 253.4 / 422.1 | need-default 89%, none 11% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v2 | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v2_iso | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c | 1 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_g | 4 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_n | 29 | 6 | 0 | LB-1 FAIL | LB-2 FAIL |

### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v2 | +0.111 [+0.056, +0.172] | +0.144 [+0.083, +0.206] | -0.00238 [-0.00309, -0.00176] | -37.2 [-49.8, -26.1] |
| cascade_v2_iso | +0.139 [+0.083, +0.200] | +0.172 [+0.111, +0.239] | -0.00227 [-0.00301, -0.00163] | -37.8 [-50.1, -26.7] |
| always_c | -0.117 [-0.194, -0.039] | -0.083 [-0.161, +0.000] | -0.00297 [-0.00371, -0.00233] | -44.1 [-57.0, -32.7] |
| always_g | +0.122 [+0.067, +0.178] | +0.156 [+0.100, +0.217] | -0.00170 [-0.00248, -0.00103] | -33.8 [-45.2, -23.4] |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v2 | 171 / 171 | 180 / 179 ($0.1176) | 147.6 [142, 154] / 145.4 [139, 152] ($0.1465, 66 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v2 | +0.130 [+0.088, +0.172] | +0.142 [+0.102, +0.183] | +0.00003 [-0.00020, +0.00025] | +0.4 [-1.7, +2.4] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v2 | agent-low-steps | 66 | 57 | 1 | 0 | 7 | 1 | 0 | 0 | 0 | 0 |
| cascade_v2_iso | agent-low-steps | 73 | 61 | 1 | 0 | 10 | 1 | 0 | 0 | 0 | 0 |
| always_g | agent-low-steps | 180 | 165 | 2 | 0 | 12 | 1 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v2 | 0 (0 correct) | 7 (7 correct) |
| cascade_v2_iso | 0 (0 correct) | 7 (7 correct) |
| always_g | 0 (0 correct) | 8 (8 correct) |

### Agent tier: a tag named in the question was never touched

| policy | questions naming a tag | never touched |
|---|---|---|
| cascade_v2 | 60 | 7 (7 correct) |
| cascade_v2_iso | 67 | 7 (7 correct) |
| always_g | 154 | 8 (8 correct) |

### UPSTREAM_ISOLATION: secondary score, control valves do not isolate

Secondary only (offline re-score); the primary score is the gold key as built. Secondary reference = gold minus control valves.

| policy | primary correct | secondary correct |
|---|---|---|
| cascade_v2 | 4/10 | 4/7 |
| cascade_v2_iso | 9/10 | 6/7 |
| always_c | 1/10 | 1/7 |
| always_g | 9/10 | 6/7 |
| always_n | 6/10 | 5/7 |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v2 | 15 | 0 |
| cascade_v2_iso | 15 | 0 |
| always_c | 15 | 0 |
| always_g | 15 | 0 |
| always_n | 15 | 0 |

### Abandoned calls: estimate against logged late charges

| run | strategy | abandoned calls | timeouts logged | late answers | estimate |
|---|---|---|---|---|---|
| CV2-AG2-D1000 | graph_agent_low_steps | 7 | 7 | 2 ($0.0113) | $0.0742 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v2 | cascade_v2_iso | always_c | always_g | always_n |
|---|---|---|---|---|---|
| DOWNSTREAM_ALL | 10/10 | 10/10 | 10/10 | 7/10 | 6/10 |
| GENERIC | 7/10 | 7/10 | 1/10 | 10/10 | 9/10 |
| ITEM | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 |
| NEIGHBOURS_DOWNSTREAM | 15/15 | 15/15 | 13/15 | 15/15 | 13/15 |
| PATH | 34/34 | 34/34 | 23/34 | 34/34 | 24/34 |
| SIGNAL_CHAIN | 30/30 | 30/30 | 12/30 | 30/30 | 30/30 |
| UNIT_SCOPE | 20/20 | 20/20 | 20/20 | 19/20 | 19/20 |
| UPSTREAM_ALL | 10/10 | 10/10 | 9/10 | 8/10 | 3/10 |
| UPSTREAM_TO_FIRST_VALVE | 4/10 | 9/10 | 1/10 | 9/10 | 6/10 |

#### By family

| group | cascade_v2 | cascade_v2_iso | always_c | always_g | always_n |
|---|---|---|---|---|---|
| CONNECTED | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| COUNT_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| CROSS_UNIT | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 |
| DOWNSTREAM_IN_UNIT | 10/10 | 10/10 | 10/10 | 7/10 | 6/10 |
| FLOW_PATH | 10/10 | 10/10 | 2/10 | 10/10 | 4/10 |
| INSTRUMENTS_OF_ITEM | 10/10 | 10/10 | 2/10 | 10/10 | 10/10 |
| LOOKUP_TYPE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOPS_NEAR_ITEM | 7/10 | 7/10 | 1/10 | 10/10 | 9/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_MEASURED_EQUIPMENT | 10/10 | 10/10 | 0/10 | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 | 9/10 | 10/10 | 9/10 |
| NO_PATH | 10/10 | 10/10 | 8/10 | 10/10 | 7/10 |
| SAME_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 10/10 | 10/10 | 8/10 | 10/10 | 8/10 |
| UPSTREAM_ISOLATION | 4/10 | 9/10 | 1/10 | 9/10 | 6/10 |
| UPSTREAM_SOURCES | 10/10 | 10/10 | 9/10 | 8/10 | 3/10 |

#### By k bin

| group | cascade_v2 | cascade_v2_iso | always_c | always_g | always_n |
|---|---|---|---|---|---|
| k=0 | 67/69 | 67/69 | 46/69 | 68/69 | 68/69 |
| k=1-2 | 40/45 | 43/45 | 33/45 | 44/45 | 38/45 |
| k>=3 | 44/46 | 46/46 | 35/46 | 41/46 | 30/46 |
| unanswerable | 20/20 | 20/20 | 16/20 | 20/20 | 15/20 |
