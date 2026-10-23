# Method-and-effort cascade report

## Pre-registered rules S1-S3

- **S1: SELECTED** - tier 3 = need-default-64k (21/35 correct)
  - need-mimo: 19/35 correct (35 rows stored), cost $0.5307, mean latency 89.8 s
  - need-low: 14/35 correct (35 rows stored), cost $0.0823, mean latency 16.9 s
  - need-default-64k: 21/35 correct (35 rows stored), cost $0.6057, mean latency 296.9 s
  - dev corpora pooled: D100, D1000
- **S2: PASS** - cascade_v1 on D1000
  - accuracy 161 vs always-N 151 (needs >= 149): ok
  - cost per question $0.00209 vs $0.00322 (needs lower): ok
- **S3 cascade_v1_iso: PASS** - cascade_v1_iso vs cascade_v1 on D1000
  - +3 questions (needs >= 2): ok
  - total cost $0.4021 vs limit $0.4696 (1.25x primary): ok
- **S3 label_router_dev: FAIL** - label_router_dev vs cascade_v1 on D1000
  - +0 questions (needs >= 2): not met
  - total cost $0.1166 vs limit $0.4696 (1.25x primary): ok

## Tier-3 candidates on the dev runaways (S1)

| tier-3 candidate | correct on dev runaways | rows stored | cost $ | mean latency s |
|---|---|---|---|---|
| need-mimo | 19/35 | 35 | 0.5307 | 89.8 |
| need-low | 14/35 | 35 | 0.0823 | 16.9 |
| need-default-64k | 21/35 | 35 | 0.6057 | 296.9 |

## Corpus D100 (180 questions)

### Policies

| policy | correct | total $ | $/question | latency s median / mean / p90 | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|
| always_c | 141/180 | 0.0420 | 0.00023 | 1.5 / 3.3 / 6.0 | cypher-low 97%, none 3% | - | - |
| always_n | 157/180 | 0.4692 | 0.00261 | 7.8 / 34.9 / 121.5 | need-default 92%, none 8% | - | - |
| cascade_v1 | 167/180 | 0.2425 | 0.00135 | 2.3 / 19.2 / 52.0 | cypher-low 73%, need-default 25%, none 2% | 0.944 (118/125) | 0.837 (118/141) |
| cascade_v1_iso | 170/180 | 0.2663 | 0.00148 | 2.4 / 20.9 / 71.9 | cypher-low 69%, need-default 27%, none 4% | - | - |
| cascade_v1_t3_glm64k | 172/180 | 0.3619 | 0.00201 | 2.3 / 28.6 / 52.0 | cypher-low 69%, need-default 25%, need-default-64k 5%, none 1% | 0.944 (118/125) | 0.837 (118/141) |
| cascade_v1_t3_glmlow | 169/180 | 0.2564 | 0.00142 | 2.3 / 20.2 / 52.0 | cypher-low 69%, need-default 25%, need-low 6% | 0.944 (118/125) | 0.837 (118/141) |
| cascade_v1_t3_mimo | 170/180 | 0.3299 | 0.00183 | 2.3 / 21.2 / 52.0 | cypher-low 69%, need-default 25%, need-mimo 6% | 0.944 (118/125) | 0.837 (118/141) |
| label_router_dev | 167/180 | 0.1458 | 0.00081 | 2.0 / 11.3 / 12.5 | cypher-low 69%, need-default 25%, none 6% | - | - |
| n_first_v1_t3_glm64k | 170/180 | 0.6356 | 0.00353 | 7.8 / 46.8 / 121.5 | need-default 92%, need-default-64k 8%, none 1% | 0.952 (157/165) | 1.000 (157/157) |
| n_first_v1_t3_glmlow | 165/180 | 0.4940 | 0.00274 | 7.8 / 36.4 / 121.5 | need-default 92%, need-low 8% | 0.952 (157/165) | 1.000 (157/157) |
| n_first_v1_t3_mimo | 167/180 | 0.6279 | 0.00349 | 7.8 / 38.8 / 121.5 | need-default 92%, need-mimo 8% | 0.952 (157/165) | 1.000 (157/157) |

### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])

| policy | accuracy | $/question | latency s/question |
|---|---|---|---|
| always_c | -0.089 [-0.161, -0.017] | -0.00237 [-0.00282, -0.00195] | -31.6 [-39.0, -24.6] |
| cascade_v1 | +0.056 [+0.011, +0.106] | -0.00126 [-0.00162, -0.00092] | -15.6 [-20.9, -10.7] |
| cascade_v1_iso | +0.072 [+0.033, +0.117] | -0.00113 [-0.00147, -0.00081] | -13.9 [-18.6, -9.4] |
| cascade_v1_t3_glm64k | +0.083 [+0.033, +0.133] | -0.00060 [-0.00121, +0.00013] | -6.3 [-15.5, +4.6] |
| cascade_v1_t3_glmlow | +0.067 [+0.017, +0.117] | -0.00118 [-0.00155, -0.00083] | -14.7 [-20.1, -9.6] |
| cascade_v1_t3_mimo | +0.072 [+0.022, +0.128] | -0.00077 [-0.00127, -0.00023] | -13.7 [-19.4, -8.2] |
| label_router_dev | +0.056 [+0.006, +0.106] | -0.00180 [-0.00223, -0.00140] | -23.6 [-30.2, -17.5] |
| n_first_v1_t3_glm64k | +0.072 [+0.039, +0.111] | +0.00092 [+0.00040, +0.00156] | +12.0 [+4.6, +21.4] |
| n_first_v1_t3_glmlow | +0.044 [+0.017, +0.078] | +0.00014 [+0.00006, +0.00022] | +1.6 [+0.7, +2.6] |
| n_first_v1_t3_mimo | +0.056 [+0.022, +0.089] | +0.00088 [+0.00041, +0.00140] | +3.9 [+1.6, +6.7] |

### References (never deployable)

| policy | correct | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v1 | 167 | 172 ($0.1825) | 148.4 [143, 154] ($0.1849, 55 escalated) |
| cascade_v1_t3_glm64k | 172 | 177 ($0.2811) | 149.9 [144, 155] ($0.2346, 55 escalated) |
| cascade_v1_t3_glmlow | 169 | 175 ($0.1906) | 148.4 [142, 154] ($0.1924, 55 escalated) |
| cascade_v1_t3_mimo | 170 | 175 ($0.2472) | 148.9 [143, 154] ($0.2327, 55 escalated) |

- n_first_v1_t3_glm64k: no references - expected a row for question 'D100:CONNECTED:E-10-1|E-28-2' in tier 'need-default-64k' (policy 'n_first_v1_t3_glm64k' reaches it), found none
- n_first_v1_t3_glmlow: no references - expected a row for question 'D100:CONNECTED:E-10-1|E-28-2' in tier 'need-low' (policy 'n_first_v1_t3_glmlow' reaches it), found none
- n_first_v1_t3_mimo: no references - expected a row for question 'D100:CONNECTED:E-10-1|E-28-2' in tier 'need-mimo' (policy 'n_first_v1_t3_mimo' reaches it), found none

### Paired bootstrap vs random escalation

| policy | accuracy | $/question | latency s/question |
|---|---|---|---|
| cascade_v1 | +0.104 [+0.067, +0.143] | +0.00032 [+0.00002, +0.00067] | +5.4 [+0.6, +10.8] |
| cascade_v1_t3_glm64k | +0.123 [+0.084, +0.165] | +0.00071 [+0.00013, +0.00139] | +11.1 [+2.2, +21.9] |
| cascade_v1_t3_glmlow | +0.115 [+0.075, +0.155] | +0.00036 [+0.00002, +0.00074] | +5.8 [+0.7, +11.7] |
| cascade_v1_t3_mimo | +0.117 [+0.079, +0.158] | +0.00054 [+0.00003, +0.00113] | +6.1 [+0.5, +12.7] |

### Breakdowns (correct / questions)

#### By need label

| group | always_c | always_n | cascade_v1 | cascade_v1_iso | cascade_v1_t3_glm64k | cascade_v1_t3_glmlow | cascade_v1_t3_mimo | label_router_dev | n_first_v1_t3_glm64k | n_first_v1_t3_glmlow | n_first_v1_t3_mimo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DOWNSTREAM_ALL | 10/10 | 8/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 8/10 | 8/10 |
| GENERIC | 6/10 | 10/10 | 8/10 | 8/10 | 8/10 | 8/10 | 8/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| ITEM | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 | 43/43 |
| NEIGHBOURS_DOWNSTREAM | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 | 13/13 |
| PATH | 28/34 | 25/34 | 32/34 | 32/34 | 34/34 | 32/34 | 34/34 | 28/34 | 32/34 | 29/34 | 32/34 |
| SIGNAL_CHAIN | 12/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 |
| UNIT_SCOPE | 20/20 | 19/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 | 19/20 | 19/20 |
| UPSTREAM_ALL | 9/10 | 5/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 8/10 | 7/10 | 7/10 |
| UPSTREAM_TO_FIRST_VALVE | 0/10 | 4/10 | 1/10 | 4/10 | 4/10 | 3/10 | 2/10 | 4/10 | 7/10 | 6/10 | 5/10 |

#### By family

| group | always_c | always_n | cascade_v1 | cascade_v1_iso | cascade_v1_t3_glm64k | cascade_v1_t3_glmlow | cascade_v1_t3_mimo | label_router_dev | n_first_v1_t3_glm64k | n_first_v1_t3_glmlow | n_first_v1_t3_mimo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CONNECTED | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 |
| COUNT_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| CROSS_UNIT | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 | 9/10 |
| DOWNSTREAM_IN_UNIT | 10/10 | 8/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 8/10 | 8/10 |
| FLOW_PATH | 7/10 | 6/10 | 9/10 | 9/10 | 10/10 | 9/10 | 10/10 | 7/10 | 8/10 | 6/10 | 8/10 |
| INSTRUMENTS_OF_ITEM | 1/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_TYPE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOPS_NEAR_ITEM | 6/10 | 10/10 | 8/10 | 8/10 | 8/10 | 8/10 | 8/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_MEASURED_EQUIPMENT | 1/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| NO_PATH | 8/10 | 5/10 | 9/10 | 9/10 | 10/10 | 9/10 | 10/10 | 8/10 | 10/10 | 9/10 | 10/10 |
| SAME_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UPSTREAM_ISOLATION | 0/10 | 4/10 | 1/10 | 4/10 | 4/10 | 3/10 | 2/10 | 4/10 | 7/10 | 6/10 | 5/10 |
| UPSTREAM_SOURCES | 9/10 | 5/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 8/10 | 7/10 | 7/10 |

#### By k bin

| group | always_c | always_n | cascade_v1 | cascade_v1_iso | cascade_v1_t3_glm64k | cascade_v1_t3_glmlow | cascade_v1_t3_mimo | label_router_dev | n_first_v1_t3_glm64k | n_first_v1_t3_glmlow | n_first_v1_t3_mimo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| k=0 | 44/68 | 66/68 | 65/68 | 65/68 | 66/68 | 67/68 | 66/68 | 65/68 | 67/68 | 68/68 | 67/68 |
| k=1-2 | 45/53 | 48/53 | 46/53 | 49/53 | 47/53 | 46/53 | 46/53 | 49/53 | 49/53 | 48/53 | 48/53 |
| k>=3 | 34/39 | 28/39 | 37/39 | 37/39 | 39/39 | 37/39 | 38/39 | 35/39 | 34/39 | 30/39 | 32/39 |
| unanswerable | 18/20 | 15/20 | 19/20 | 19/20 | 20/20 | 19/20 | 20/20 | 18/20 | 20/20 | 19/20 | 20/20 |

## Corpus D1000 (180 questions)

### Policies

| policy | correct | total $ | $/question | latency s median / mean / p90 | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|
| always_c | 130/180 | 0.0463 | 0.00026 | 1.6 / 3.5 / 3.8 | cypher-low 94%, none 6% | - | - |
| always_n | 151/180 | 0.5802 | 0.00322 | 14.6 / 51.1 / 167.0 | need-default 89%, none 11% | - | - |
| cascade_v1 | 161/180 | 0.3757 | 0.00209 | 2.5 / 26.6 / 104.0 | cypher-low 66%, need-default 32%, none 2% | 0.921 (105/114) | 0.808 (105/130) |
| cascade_v1_iso | 164/180 | 0.4021 | 0.00223 | 2.6 / 33.0 / 122.5 | cypher-low 62%, need-default 34%, none 4% | - | - |
| cascade_v1_t3_glm64k | 163/180 | 0.5304 | 0.00295 | 2.5 / 41.0 / 104.0 | cypher-low 64%, need-default 32%, need-default-64k 3%, none 1% | 0.921 (105/114) | 0.808 (105/130) |
| cascade_v1_t3_glmlow | 163/180 | 0.4057 | 0.00225 | 2.5 / 27.6 / 104.0 | cypher-low 63%, need-default 32%, need-low 5% | 0.921 (105/114) | 0.808 (105/130) |
| cascade_v1_t3_mimo | 164/180 | 0.5245 | 0.00291 | 2.5 / 30.5 / 104.0 | cypher-low 63%, need-default 32%, need-mimo 5% | 0.921 (105/114) | 0.808 (105/130) |
| label_router_dev | 161/180 | 0.1166 | 0.00065 | 2.0 / 13.9 / 17.4 | cypher-low 67%, need-default 26%, none 7% | - | - |
| n_first_v1_t3_glm64k | 159/180 | 1.0194 | 0.00566 | 14.6 / 96.9 / 283.3 | need-default 89%, need-default-64k 8%, none 3% | 0.944 (151/160) | 1.000 (151/151) |
| n_first_v1_t3_glmlow | 157/180 | 0.6377 | 0.00354 | 14.6 / 52.9 / 171.4 | need-default 89%, need-low 11% | 0.944 (151/160) | 1.000 (151/151) |
| n_first_v1_t3_mimo | 160/180 | 0.9522 | 0.00529 | 14.6 / 64.6 / 231.5 | need-default 89%, need-mimo 11%, none 1% | 0.944 (151/160) | 1.000 (151/151) |

### Paired bootstrap vs always_n (policy minus always_n, mean [95% CI])

| policy | accuracy | $/question | latency s/question |
|---|---|---|---|
| always_c | -0.117 [-0.194, -0.039] | -0.00297 [-0.00371, -0.00233] | -47.6 [-60.5, -36.0] |
| cascade_v1 | +0.056 [+0.006, +0.111] | -0.00114 [-0.00154, -0.00077] | -24.5 [-36.1, -14.7] |
| cascade_v1_iso | +0.072 [+0.028, +0.122] | -0.00099 [-0.00137, -0.00065] | -18.2 [-26.9, -10.7] |
| cascade_v1_t3_glm64k | +0.067 [+0.017, +0.122] | -0.00028 [-0.00106, +0.00058] | -10.1 [-26.3, +6.2] |
| cascade_v1_t3_glmlow | +0.067 [+0.017, +0.122] | -0.00097 [-0.00140, -0.00056] | -23.5 [-35.2, -13.7] |
| cascade_v1_t3_mimo | +0.072 [+0.022, +0.128] | -0.00031 [-0.00102, +0.00046] | -20.7 [-33.0, -9.9] |
| label_router_dev | +0.056 [+0.006, +0.106] | -0.00258 [-0.00333, -0.00193] | -37.2 [-48.0, -27.2] |
| n_first_v1_t3_glm64k | +0.044 [+0.017, +0.078] | +0.00244 [+0.00138, +0.00361] | +45.8 [+25.1, +68.9] |
| n_first_v1_t3_glmlow | +0.033 [+0.011, +0.061] | +0.00032 [+0.00017, +0.00049] | +1.7 [+0.8, +2.9] |
| n_first_v1_t3_mimo | +0.050 [+0.022, +0.083] | +0.00207 [+0.00116, +0.00308] | +13.5 [+7.0, +21.2] |

### References (never deployable)

| policy | correct | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v1 | 161 | 168 ($0.2305) | 141.8 [136, 148] ($0.2583, 66 escalated) |
| cascade_v1_t3_glm64k | 163 | 170 ($0.4640) | 140.7 [134, 147] ($0.4188, 66 escalated) |
| cascade_v1_t3_glmlow | 163 | 172 ($0.2571) | 139.9 [133, 147] ($0.2795, 66 escalated) |
| cascade_v1_t3_mimo | 164 | 171 ($0.3822) | 141.0 [134, 148] ($0.3952, 66 escalated) |

- n_first_v1_t3_glm64k: no references - expected a row for question 'D1000:CONNECTED:E-19-2|C-395-7' in tier 'need-default-64k' (policy 'n_first_v1_t3_glm64k' reaches it), found none
- n_first_v1_t3_glmlow: no references - expected a row for question 'D1000:CONNECTED:E-19-2|C-395-7' in tier 'need-low' (policy 'n_first_v1_t3_glmlow' reaches it), found none
- n_first_v1_t3_mimo: no references - expected a row for question 'D1000:CONNECTED:E-19-2|C-395-7' in tier 'need-mimo' (policy 'n_first_v1_t3_mimo' reaches it), found none

### Paired bootstrap vs random escalation

| policy | accuracy | $/question | latency s/question |
|---|---|---|---|
| cascade_v1 | +0.107 [+0.068, +0.146] | +0.00065 [+0.00021, +0.00117] | +4.3 [-2.7, +11.3] |
| cascade_v1_t3_glm64k | +0.124 [+0.084, +0.165] | +0.00062 [-0.00028, +0.00155] | +2.1 [-14.5, +18.1] |
| cascade_v1_t3_glmlow | +0.128 [+0.087, +0.169] | +0.00070 [+0.00020, +0.00128] | +4.8 [-2.5, +12.1] |
| cascade_v1_t3_mimo | +0.128 [+0.088, +0.167] | +0.00072 [-0.00012, +0.00160] | +3.3 [-6.1, +12.6] |

### Breakdowns (correct / questions)

#### By need label

| group | always_c | always_n | cascade_v1 | cascade_v1_iso | cascade_v1_t3_glm64k | cascade_v1_t3_glmlow | cascade_v1_t3_mimo | label_router_dev | n_first_v1_t3_glm64k | n_first_v1_t3_glmlow | n_first_v1_t3_mimo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| DOWNSTREAM_ALL | 10/10 | 6/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 6/10 | 8/10 |
| GENERIC | 1/10 | 9/10 | 6/10 | 6/10 | 6/10 | 6/10 | 6/10 | 9/10 | 9/10 | 9/10 | 9/10 |
| ITEM | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 | 41/41 |
| NEIGHBOURS_DOWNSTREAM | 13/15 | 13/15 | 14/15 | 14/15 | 14/15 | 14/15 | 14/15 | 13/15 | 13/15 | 13/15 | 13/15 |
| PATH | 23/34 | 24/34 | 28/34 | 28/34 | 30/34 | 30/34 | 31/34 | 23/34 | 29/34 | 29/34 | 30/34 |
| SIGNAL_CHAIN | 12/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 | 30/30 |
| UNIT_SCOPE | 20/20 | 19/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 20/20 | 19/20 | 19/20 | 19/20 |
| UPSTREAM_ALL | 9/10 | 3/10 | 9/10 | 9/10 | 9/10 | 9/10 | 9/10 | 9/10 | 4/10 | 3/10 | 4/10 |
| UPSTREAM_TO_FIRST_VALVE | 1/10 | 6/10 | 3/10 | 6/10 | 3/10 | 3/10 | 3/10 | 6/10 | 6/10 | 7/10 | 6/10 |

#### By family

| group | always_c | always_n | cascade_v1 | cascade_v1_iso | cascade_v1_t3_glm64k | cascade_v1_t3_glmlow | cascade_v1_t3_mimo | label_router_dev | n_first_v1_t3_glm64k | n_first_v1_t3_glmlow | n_first_v1_t3_mimo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CONNECTED | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| COUNT_IN_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| CROSS_UNIT | 10/10 | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 | 9/10 |
| DOWNSTREAM_IN_UNIT | 10/10 | 6/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 8/10 | 6/10 | 8/10 |
| FLOW_PATH | 2/10 | 4/10 | 5/10 | 5/10 | 6/10 | 7/10 | 7/10 | 2/10 | 5/10 | 6/10 | 6/10 |
| INSTRUMENTS_OF_ITEM | 2/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_TYPE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOKUP_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOPS_NEAR_ITEM | 1/10 | 9/10 | 6/10 | 6/10 | 6/10 | 6/10 | 6/10 | 9/10 | 9/10 | 9/10 | 9/10 |
| LOOP_ACTUATED_VALVE | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| LOOP_MEASURED_EQUIPMENT | 0/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| NEIGHBOURS_DOWNSTREAM | 9/10 | 9/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 9/10 | 9/10 | 9/10 | 9/10 |
| NO_PATH | 8/10 | 7/10 | 9/10 | 9/10 | 10/10 | 10/10 | 10/10 | 8/10 | 10/10 | 10/10 | 10/10 |
| SAME_UNIT | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| SHEETS_OF_TAG | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 | 10/10 |
| UNANSWERABLE_TAG | 8/10 | 8/10 | 9/10 | 9/10 | 9/10 | 8/10 | 9/10 | 8/10 | 9/10 | 8/10 | 9/10 |
| UPSTREAM_ISOLATION | 1/10 | 6/10 | 3/10 | 6/10 | 3/10 | 3/10 | 3/10 | 6/10 | 6/10 | 7/10 | 6/10 |
| UPSTREAM_SOURCES | 9/10 | 3/10 | 9/10 | 9/10 | 9/10 | 9/10 | 9/10 | 9/10 | 4/10 | 3/10 | 4/10 |

#### By k bin

| group | always_c | always_n | cascade_v1 | cascade_v1_iso | cascade_v1_t3_glm64k | cascade_v1_t3_glmlow | cascade_v1_t3_mimo | label_router_dev | n_first_v1_t3_glm64k | n_first_v1_t3_glmlow | n_first_v1_t3_mimo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| k=0 | 46/69 | 68/69 | 67/69 | 68/69 | 67/69 | 67/69 | 67/69 | 68/69 | 68/69 | 68/69 | 68/69 |
| k=1-2 | 33/45 | 38/45 | 38/45 | 40/45 | 38/45 | 38/45 | 38/45 | 41/45 | 38/45 | 39/45 | 39/45 |
| k>=3 | 35/46 | 30/46 | 38/46 | 38/46 | 39/46 | 40/46 | 40/46 | 36/46 | 34/46 | 32/46 | 34/46 |
| unanswerable | 16/20 | 15/20 | 18/20 | 18/20 | 19/20 | 18/20 | 19/20 | 16/20 | 19/20 | 18/20 | 19/20 |
