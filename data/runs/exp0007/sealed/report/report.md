# Method-and-effort cascade report

Latency counts every model call of a question (final answer, retrieval and agent steps) plus local compute where recorded, summed over the tiers tried. LB-1: median <= 10 s; LB-2: p90 <= 60 s; LB-3: an answer later than C = 120 s counts as no answer (TIMED_OUT, wrong) for every arm alike, so acc@120 is the cutoff-scored accuracy. A run made under a live deadline cannot show raw accuracy beyond C.

## T4 Claims

Claims corpus: H1000g2.

- **PASS** Q4 (primary) cascade_v4_iso [headline]: supported
  - acc@C large minus small -0.020 [-0.059, +0.018] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.033 [-0.045, 0.105] (needs < 0.5): ok
- **FAIL** K1 [headline]: the cascade saves nothing
  - acc@C +0.020 [-0.002, +0.043]: ok
  - $/question -0.00041 [-0.00060, -0.00024] (needs CI below 0): ok
  - latency s/question +3.21 [+1.33, +5.25] (needs CI below 0): not met
- **PASS** K2 [headline]: supported
  - acc@C +0.076 [+0.055, +0.098] (needs CI above 0)
- **PASS** K3 [headline]: supported
  - median 7.5 [6.8, 8.6] s (limit 10): ok
  - p90 40.8 [37.0, 46.3] s (limit 60): ok
- **PASS** Q5 [headline]: supported
  - acc@C +0.075 [+0.039, +0.111] (needs CI above 0)
- **PASS** Q4' cascade_v4 [headline]: supported
  - acc@C large minus small -0.016 [-0.055, +0.025] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.037 [-0.043, 0.110] (needs < 0.5): ok
- **PASS** Q4' always_g_v2t [headline]: supported
  - acc@C large minus small -0.039 [-0.082, +0.002] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.045 [-0.026, 0.114] (needs < 0.5): ok
- **PASS** Q4' always_c_v2t [headline]: supported
  - acc@C large minus small -0.014 [-0.066, +0.039] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.006 [-0.037, 0.055] (needs < 0.5): ok
- **PASS** Q4 (primary) cascade_v4_iso [held-out]: supported
  - acc@C large minus small -0.030 [-0.150, +0.090] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.042 [-0.089, 0.170] (needs < 0.5): ok
- **FAIL** K1 [held-out]: the cascade saves nothing
  - acc@C +0.050 [+0.000, +0.100]: ok
  - $/question -0.00084 [-0.00137, -0.00035] (needs CI below 0): ok
  - latency s/question +17.57 [+10.72, +24.59] (needs CI below 0): not met
- **PASS** K2 [held-out]: supported
  - acc@C +0.107 [+0.060, +0.157] (needs CI above 0)
- **FAIL** K3 [held-out]: the cascade is not fast enough at plant scale
  - median 19.1 [11.8, 29.0] s (limit 10): not met
  - p90 104.6 [100.3, 116.8] s (limit 60): not met
- **FAIL** Q5 [held-out]: free-form Cypher matches the typed API
  - acc@C +0.090 [-0.010, +0.180] (needs CI above 0)
- **PASS** Q4' cascade_v4 [held-out]: supported
  - acc@C large minus small -0.030 [-0.150, +0.090] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.042 [-0.089, 0.170] (needs < 0.5): ok
- **PASS** Q4' always_g_v2t [held-out]: supported
  - acc@C large minus small -0.080 [-0.210, +0.050] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.046 [-0.046, 0.132] (needs < 0.5): ok
- **PASS** Q4' always_c_v2t [held-out]: supported
  - acc@C large minus small -0.040 [-0.180, +0.100] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.033 [-0.064, 0.137] (needs < 0.5): ok
- **NOT_RUN** Q1: not run - need-aware Hierarchical was dropped (ADR-0047, ADR-0048)
- **NOT_RUN** Q2: not run - need-aware Hierarchical was dropped (ADR-0047, ADR-0048)
- **NOT_RUN** Q3: not run - hier_agent was dropped (ADR-0047)

## T1 Headline

### H100g2, scope `headline`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | 440 | 401/440 0.911 [0.881, 0.934] | 510/560 | 0.00137 | 7.1 / 14.3 / 38.0 / 47.4 / 88.3 | PASS / PASS | cypher-v2t 74%, agent-v2t 26% | - | - |
| cascade_v4 | 440 | 399/440 0.907 [0.876, 0.931] | 508/560 | 0.00140 | 7.1 / 14.6 / 38.4 / 47.7 / 88.3 | PASS / PASS | cypher-v2t 75%, agent-v2t 25% | 74.8% | 0.942 (310/329) |
| always_g_v2t | 440 | 400/440 0.909 [0.879, 0.933] | 517/560 | 0.00171 | 9.4 / 12.6 / 25.3 / 32.0 / 61.4 | PASS / PASS | agent-v2t 100%, none 0% | - | - |
| always_c_v2t | 440 | 356/440 0.809 [0.770, 0.843] | 454/560 | 0.00074 | 5.9 / 10.2 / 17.7 / 39.1 / 76.7 | PASS / PASS | cypher-v2t 93%, none 7% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v4_iso | 7.1 [6.4, 7.7] | 38.0 [30.8, 42.8] |
| cascade_v4 | 7.1 [6.4, 7.7] | 38.4 [30.6, 43.5] |
| always_g_v2t | 9.4 [8.5, 10.5] | 25.3 [21.5, 29.0] |
| always_c_v2t | 5.9 [5.5, 6.6] | 17.7 [14.7, 27.6] |

### H100g2, scope `held-out`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | 100 | 77/100 0.770 [0.678, 0.842] | 510/560 | 0.00225 | 14.9 / 28.4 / 72.5 / 82.5 / 88.3 | FAIL / FAIL | cypher-v2t 66%, agent-v2t 34% | - | - |
| cascade_v4 | 100 | 77/100 0.770 [0.678, 0.842] | 508/560 | 0.00225 | 14.9 / 28.4 / 72.5 / 82.5 / 88.3 | FAIL / FAIL | cypher-v2t 66%, agent-v2t 34% | 66.0% | 0.879 (58/66) |
| always_g_v2t | 100 | 77/100 0.770 [0.678, 0.842] | 517/560 | 0.00299 | 16.6 / 18.2 / 29.8 / 32.5 / 61.4 | FAIL / PASS | agent-v2t 100% | - | - |
| always_c_v2t | 100 | 64/100 0.640 [0.542, 0.727] | 454/560 | 0.00105 | 12.4 / 20.5 / 48.6 / 70.0 / 76.7 | FAIL / PASS | cypher-v2t 84%, none 16% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v4_iso | 14.9 [12.6, 29.2] | 72.5 [47.4, 82.5] |
| cascade_v4 | 14.9 [12.6, 29.2] | 72.5 [47.4, 82.5] |
| always_g_v2t | 16.6 [14.7, 18.4] | 29.8 [26.4, 32.5] |
| always_c_v2t | 12.4 [10.4, 13.9] | 48.6 [43.8, 70.0] |

### H1000g2, scope `headline`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | 440 | 392/440 0.891 [0.858, 0.917] | 502/560 | 0.00148 | 7.5 / 17.7 / 40.8 / 78.8 / 132.0 | PASS / PASS | cypher-v2t 74%, agent-v2t 26% | - | - |
| cascade_v4 | 440 | 392/440 0.891 [0.858, 0.917] | 502/560 | 0.00152 | 7.5 / 20.9 / 55.1 / 103.0 / 139.0 | PASS / PASS | cypher-v2t 74%, agent-v2t 26% | 73.6% | 0.951 (308/324) |
| always_g_v2t | 440 | 383/440 0.870 [0.836, 0.899] | 497/560 | 0.00189 | 10.4 / 14.5 / 27.1 / 37.4 / 119.4 | FAIL / PASS | agent-v2t 100%, none 0% | - | - |
| always_c_v2t | 440 | 350/440 0.795 [0.755, 0.831] | 451/560 | 0.00075 | 6.5 / 15.2 / 46.7 / 74.7 / 81.5 | PASS / PASS | cypher-v2t 89%, none 11% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v4_iso | 7.5 [6.8, 8.6] | 40.8 [37.0, 46.3] |
| cascade_v4 | 7.5 [6.8, 8.6] | 55.1 [41.1, 95.1] |
| always_g_v2t | 10.4 [9.0, 12.0] | 27.1 [25.3, 31.1] |
| always_c_v2t | 6.5 [5.8, 6.8] | 46.7 [38.9, 72.0] |

### H1000g2, scope `held-out`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | 100 | 74/100 0.740 [0.646, 0.816] | 502/560 | 0.00248 | 19.1 / 39.0 / 104.6 / 116.8 / 132.0 | FAIL / FAIL | cypher-v2t 63%, agent-v2t 37% | - | - |
| cascade_v4 | 100 | 74/100 0.740 [0.646, 0.816] | 502/560 | 0.00248 | 19.1 / 39.0 / 104.6 / 116.8 / 132.0 | FAIL / FAIL | cypher-v2t 63%, agent-v2t 37% | 63.0% | 0.905 (57/63) |
| always_g_v2t | 100 | 69/100 0.690 [0.594, 0.772] | 497/560 | 0.00332 | 20.0 / 21.4 / 37.8 / 43.1 / 53.2 | FAIL / PASS | agent-v2t 100% | - | - |
| always_c_v2t | 100 | 60/100 0.600 [0.502, 0.691] | 451/560 | 0.00114 | 12.6 / 29.1 / 78.0 / 78.8 / 81.5 | FAIL / FAIL | cypher-v2t 73%, none 27% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v4_iso | 19.1 [11.8, 29.0] | 104.6 [100.3, 116.8] |
| cascade_v4 | 19.1 [11.8, 29.0] | 104.6 [100.3, 116.8] |
| always_g_v2t | 20.0 [17.3, 22.1] | 37.8 [29.4, 43.1] |
| always_c_v2t | 12.6 [9.9, 17.5] | 78.0 [75.8, 78.8] |

## T2 Splits

### H100g2

| policy | dev-old | dev-new | held-out | held-out-wording |
|---|---|---|---|---|
| cascade_v4_iso | 207/220 0.941 [0.902, 0.965] | 117/120 0.975 [0.929, 0.991] | 77/100 0.770 [0.678, 0.842] | 79/90 0.878 [0.794, 0.930] |
| cascade_v4 | 205/220 0.932 [0.891, 0.958] | 117/120 0.975 [0.929, 0.991] | 77/100 0.770 [0.678, 0.842] | 79/90 0.878 [0.794, 0.930] |
| always_g_v2t | 209/220 0.950 [0.913, 0.972] | 114/120 0.950 [0.895, 0.977] | 77/100 0.770 [0.678, 0.842] | 88/90 0.978 [0.923, 0.994] |
| always_c_v2t | 192/220 0.873 [0.822, 0.910] | 100/120 0.833 [0.757, 0.889] | 64/100 0.640 [0.542, 0.727] | 68/90 0.756 [0.658, 0.833] |

### H1000g2

| policy | dev-old | dev-new | held-out | held-out-wording |
|---|---|---|---|---|
| cascade_v4_iso | 204/220 0.927 [0.885, 0.955] | 114/120 0.950 [0.895, 0.977] | 74/100 0.740 [0.646, 0.816] | 80/90 0.889 [0.807, 0.939] |
| cascade_v4 | 204/220 0.927 [0.885, 0.955] | 114/120 0.950 [0.895, 0.977] | 74/100 0.740 [0.646, 0.816] | 80/90 0.889 [0.807, 0.939] |
| always_g_v2t | 205/220 0.932 [0.891, 0.958] | 109/120 0.908 [0.843, 0.948] | 69/100 0.690 [0.594, 0.772] | 84/90 0.933 [0.862, 0.969] |
| always_c_v2t | 186/220 0.845 [0.792, 0.887] | 104/120 0.867 [0.794, 0.916] | 60/100 0.600 [0.502, 0.691] | 71/90 0.789 [0.694, 0.860] |

### Generalisation gap

| corpus | policy | dev | held-out | gap dev - held-out (unpaired 95 % CI) |
|---|---|---|---|---|
| H100g2 | cascade_v4_iso | 324/340 | 77/100 | +0.183 [+0.101, +0.273] |
| H100g2 | cascade_v4 | 322/340 | 77/100 | +0.177 [+0.094, +0.266] |
| H100g2 | always_g_v2t | 323/340 | 77/100 | +0.180 [+0.097, +0.268] |
| H100g2 | always_c_v2t | 292/340 | 64/100 | +0.219 [+0.118, +0.319] |
| H1000g2 | cascade_v4_iso | 318/340 | 74/100 | +0.195 [+0.108, +0.288] |
| H1000g2 | cascade_v4 | 318/340 | 74/100 | +0.195 [+0.108, +0.288] |
| H1000g2 | always_g_v2t | 314/340 | 69/100 | +0.234 [+0.142, +0.335] |
| H1000g2 | always_c_v2t | 290/340 | 60/100 | +0.253 [+0.150, +0.358] |

## T3 Scale

H100g2 has 100 sheets, H1000g2 has 1000; e = ln(cost ratio) / ln(sheet ratio).

| scope | policy | acc@C H100g2 | acc@C H1000g2 | H1000g2 - H100g2 (unpaired CI) | $/question | cost elasticity e (95 % CI) | latency ratio median / p90 |
|---|---|---|---|---|---|---|---|
| headline | cascade_v4_iso | 0.911 [0.881, 0.934] | 0.891 [0.858, 0.917] | -0.020 [-0.059, +0.018] | 0.00137 -> 0.00148 | 0.033 [-0.045, 0.105] | 1.05 / 1.07 |
| headline | cascade_v4 | 0.907 [0.876, 0.931] | 0.891 [0.858, 0.917] | -0.016 [-0.055, +0.025] | 0.00140 -> 0.00152 | 0.037 [-0.043, 0.110] | 1.05 / 1.43 |
| headline | always_g_v2t | 0.909 [0.879, 0.933] | 0.870 [0.836, 0.899] | -0.039 [-0.082, +0.002] | 0.00171 -> 0.00189 | 0.045 [-0.026, 0.114] | 1.11 / 1.07 |
| headline | always_c_v2t | 0.809 [0.770, 0.843] | 0.795 [0.755, 0.831] | -0.014 [-0.066, +0.039] | 0.00074 -> 0.00075 | 0.006 [-0.037, 0.055] | 1.11 / 2.64 |
| held-out | cascade_v4_iso | 0.770 [0.678, 0.842] | 0.740 [0.646, 0.816] | -0.030 [-0.150, +0.090] | 0.00225 -> 0.00248 | 0.042 [-0.089, 0.170] | 1.28 / 1.44 |
| held-out | cascade_v4 | 0.770 [0.678, 0.842] | 0.740 [0.646, 0.816] | -0.030 [-0.150, +0.090] | 0.00225 -> 0.00248 | 0.042 [-0.089, 0.170] | 1.28 / 1.44 |
| held-out | always_g_v2t | 0.770 [0.678, 0.842] | 0.690 [0.594, 0.772] | -0.080 [-0.210, +0.050] | 0.00299 -> 0.00332 | 0.046 [-0.046, 0.132] | 1.20 / 1.27 |
| held-out | always_c_v2t | 0.640 [0.542, 0.727] | 0.600 [0.502, 0.691] | -0.040 [-0.180, +0.100] | 0.00105 -> 0.00114 | 0.033 [-0.064, 0.137] | 1.01 / 1.60 |

### Tier 1 by k bin (headline questions)

| corpus | policy | k bin | n | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|
| H100g2 | cascade_v4 | k=0 | 171 | 86.0% | 0.973 (143/147) |
| H100g2 | cascade_v4 | k=1-2 | 139 | 75.5% | 0.952 (100/105) |
| H100g2 | cascade_v4 | k>=3 | 90 | 85.6% | 0.870 (67/77) |
| H100g2 | cascade_v4 | unanswerable | 40 | 0.0% | - |
| H1000g2 | cascade_v4 | k=0 | 165 | 88.5% | 0.986 (144/146) |
| H1000g2 | cascade_v4 | k=1-2 | 143 | 70.6% | 0.980 (99/101) |
| H1000g2 | cascade_v4 | k>=3 | 92 | 83.7% | 0.844 (65/77) |
| H1000g2 | cascade_v4 | unanswerable | 40 | 0.0% | - |

## Paired bootstrap sections (K1, K2, Q5; mean difference [95 % CI])

| claim | corpus | scope | policy - reference | acc@C | $/question | latency s |
|---|---|---|---|---|---|---|
| K1 | H100g2 | headline | cascade_v4_iso - always_g_v2t | +0.002 [-0.018, +0.023] | -0.00034 [-0.00049, -0.00019] | +1.73 [+0.37, +3.16] |
| K2 | H100g2 | headline | cascade_v4 - random escalation | +0.072 [+0.051, +0.094] | +0.00023 [+0.00010, +0.00036] | +1.24 [+0.47, +2.03] |
| Q5 | H100g2 | headline | always_g_v2t - always_c_v2t | +0.100 [+0.066, +0.134] | +0.00097 [+0.00080, +0.00114] | +2.42 [+1.07, +3.69] |
| K1 | H100g2 | held-out | cascade_v4_iso - always_g_v2t | +0.000 [-0.060, +0.050] | -0.00074 [-0.00119, -0.00032] | +10.14 [+5.65, +14.91] |
| K2 | H100g2 | held-out | cascade_v4 - random escalation | +0.085 [+0.040, +0.135] | +0.00018 [-0.00018, +0.00055] | +1.69 [-0.47, +3.84] |
| Q5 | H100g2 | held-out | always_g_v2t - always_c_v2t | +0.130 [+0.050, +0.220] | +0.00194 [+0.00154, +0.00234] | -2.25 [-6.77, +1.93] |
| K1 | H1000g2 | headline | cascade_v4_iso - always_g_v2t | +0.020 [-0.002, +0.043] | -0.00041 [-0.00060, -0.00024] | +3.21 [+1.33, +5.25] |
| K2 | H1000g2 | headline | cascade_v4 - random escalation | +0.076 [+0.055, +0.098] | +0.00027 [+0.00013, +0.00042] | +1.88 [+0.95, +2.86] |
| Q5 | H1000g2 | headline | always_g_v2t - always_c_v2t | +0.075 [+0.039, +0.111] | +0.00114 [+0.00093, +0.00135] | -0.70 [-2.44, +0.96] |
| K1 | H1000g2 | held-out | cascade_v4_iso - always_g_v2t | +0.050 [+0.000, +0.100] | -0.00084 [-0.00137, -0.00035] | +17.57 [+10.72, +24.59] |
| K2 | H1000g2 | held-out | cascade_v4 - random escalation | +0.107 [+0.060, +0.157] | +0.00011 [-0.00027, +0.00051] | +1.95 [-0.44, +4.45] |
| Q5 | H1000g2 | held-out | always_g_v2t - always_c_v2t | +0.090 [-0.010, +0.180] | +0.00219 [+0.00172, +0.00270] | -7.72 [-12.84, -2.72] |

## Notes

- scope `headline` leaves out the family LOOP_ACTUATED_VALVE (ADR-0044 U2)

## Corpus H100g2 (560 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | 510/560 | 510/560 | 0.7311 | 0.00131 | 6.5 / 13.3 / 36.7 / 45.5 / 88.3 | cypher-v2t 77%, agent-v2t 23% | - | - |
| cascade_v4 | 508/560 | 508/560 | 0.7436 | 0.00133 | 6.5 / 13.5 / 36.7 / 47.0 / 88.3 | cypher-v2t 78%, agent-v2t 22% | 0.934 (408/437) | 0.899 (408/454) |
| always_g_v2t | 517/560 | 517/560 | 0.8708 | 0.00155 | 9.0 / 12.3 / 24.1 / 30.3 / 61.8 | agent-v2t 100%, none 0% | - | - |
| always_c_v2t | 454/560 | 454/560 | 0.4238 | 0.00076 | 5.7 / 9.7 / 16.5 / 37.9 / 76.7 | cypher-v2t 94%, none 6% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v4_iso | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v4 | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_g_v2t | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c_v2t | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v4 | 508 / 508 | 528 / 528 ($0.7208) | 468.0 [460, 475] / 468.0 [460, 475] ($0.6152, 123 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v4 | +0.071 [+0.052, +0.091] | +0.071 [+0.052, +0.091] | +0.00023 [+0.00012, +0.00034] | +1.2 [+0.5, +1.9] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | agent-v2t | 129 | 129 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| cascade_v4 | agent-v2t | 123 | 123 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| always_g_v2t | agent-v2t | 560 | 559 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v4_iso | 0 (0 correct) | 22 (21 correct) |
| cascade_v4 | 0 (0 correct) | 22 (21 correct) |
| always_g_v2t | 0 (0 correct) | 25 (22 correct) |

### Agent tier: a tag named in the question was never touched

| policy | questions naming a tag | never touched |
|---|---|---|
| cascade_v4_iso | 100 | 9 (7 correct) |
| cascade_v4 | 94 | 9 (7 correct) |
| always_g_v2t | 463 | 13 (9 correct) |

### UPSTREAM_ISOLATION: secondary score, control valves do not isolate

Secondary only (offline re-score); the primary score is the gold key as built. Secondary reference = gold minus control valves.

| policy | primary correct | secondary correct |
|---|---|---|
| cascade_v4_iso | 15/30 | 12/30 |
| cascade_v4 | 13/30 | 11/30 |
| always_g_v2t | 18/30 | 13/30 |
| always_c_v2t | 0/30 | 0/30 |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v4_iso | 25 | 0 |
| cascade_v4 | 25 | 0 |
| always_g_v2t | 25 | 0 |
| always_c_v2t | 25 | 0 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v4_iso | cascade_v4 | always_g_v2t | always_c_v2t |
|---|---|---|---|---|
| DOWNSTREAM_ALL | 20/40 | 20/40 | 21/40 | 17/40 |
| GENERIC | 129/140 | 129/140 | 132/140 | 102/140 |
| ITEM | 88/88 | 88/88 | 88/88 | 86/88 |
| NEIGHBOURS_DOWNSTREAM | 29/29 | 29/29 | 29/29 | 29/29 |
| PATH | 69/73 | 69/73 | 70/73 | 67/73 |
| SIGNAL_CHAIN | 70/70 | 70/70 | 69/70 | 70/70 |
| UNIT_SCOPE | 75/80 | 75/80 | 80/80 | 63/80 |
| UPSTREAM_ALL | 20/20 | 20/20 | 18/20 | 20/20 |
| UPSTREAM_TO_FIRST_VALVE | 10/20 | 8/20 | 10/20 | 0/20 |

#### By family

| group | cascade_v4_iso | cascade_v4 | always_g_v2t | always_c_v2t |
|---|---|---|---|---|
| CONNECTED | 19/20 | 19/20 | 18/20 | 17/20 |
| COUNT_IN_UNIT | 30/30 | 30/30 | 30/30 | 30/30 |
| CROSS_UNIT | 25/30 | 25/30 | 30/30 | 19/30 |
| DOWNSTREAM_IN_UNIT | 18/20 | 18/20 | 18/20 | 16/20 |
| DOWNSTREAM_ISOLATION | 2/20 | 2/20 | 3/20 | 1/20 |
| FEEDING_UNITS | 20/20 | 20/20 | 20/20 | 14/20 |
| FLOW_PATH | 27/30 | 27/30 | 30/30 | 27/30 |
| INSTRUMENTS_OF_ITEM | 20/20 | 20/20 | 20/20 | 20/20 |
| LOOKUP_TYPE | 30/30 | 30/30 | 30/30 | 30/30 |
| LOOKUP_UNIT | 30/30 | 30/30 | 30/30 | 30/30 |
| LOOPS_NEAR_ITEM | 20/20 | 20/20 | 20/20 | 7/20 |
| LOOP_ACTUATED_VALVE | 30/30 | 30/30 | 29/30 | 30/30 |
| LOOP_MEASURED_EQUIPMENT | 30/30 | 30/30 | 30/30 | 27/30 |
| NEIGHBOURS_DOWNSTREAM | 29/30 | 29/30 | 30/30 | 29/30 |
| NO_PATH | 20/20 | 20/20 | 20/20 | 20/20 |
| ROUTE_AVOIDING | 20/20 | 20/20 | 18/20 | 20/20 |
| SAME_UNIT | 20/20 | 20/20 | 20/20 | 20/20 |
| SHEETS_OF_TAG | 30/30 | 30/30 | 30/30 | 28/30 |
| UNANSWERABLE_TAG | 20/20 | 20/20 | 19/20 | 20/20 |
| UNITS_REACHED | 20/20 | 20/20 | 19/20 | 20/20 |
| UPSTREAM_ISOLATION | 15/30 | 13/30 | 18/30 | 0/30 |
| UPSTREAM_SOURCES | 20/20 | 20/20 | 18/20 | 20/20 |
| VALVES_ON_PATH | 15/20 | 15/20 | 17/20 | 9/20 |

#### By k bin

| group | cascade_v4_iso | cascade_v4 | always_g_v2t | always_c_v2t |
|---|---|---|---|---|
| k=0 | 218/233 | 218/233 | 220/233 | 200/233 |
| k=1-2 | 167/188 | 166/188 | 173/188 | 136/188 |
| k>=3 | 85/99 | 84/99 | 85/99 | 78/99 |
| unanswerable | 40/40 | 40/40 | 39/40 | 40/40 |

## Corpus H1000g2 (560 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | 505/560 | 502/560 | 0.7811 | 0.00139 | 6.8 / 17.8 / 42.0 / 94.5 / 172.8 | cypher-v2t 76%, agent-v2t 24% | - | - |
| cascade_v4 | 505/560 | 502/560 | 0.8002 | 0.00143 | 6.8 / 20.3 / 51.0 / 103.1 / 172.8 | cypher-v2t 76%, agent-v2t 24% | 0.956 (409/428) | 0.907 (409/451) |
| always_g_v2t | 497/560 | 497/560 | 0.9537 | 0.00170 | 9.8 / 14.3 / 26.8 / 37.4 / 119.4 | agent-v2t 100%, none 0% | - | - |
| always_c_v2t | 451/560 | 451/560 | 0.4214 | 0.00075 | 6.2 / 14.9 / 46.3 / 75.8 / 84.0 | cypher-v2t 89%, none 11% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v4_iso | 8 | 3 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v4 | 11 | 3 | 0 | LB-1 PASS | LB-2 PASS |
| always_g_v2t | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c_v2t | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v4 | 505 / 502 | 518 / 514 ($0.7628) | 462.1 [455, 470] / 460.9 [453, 468] ($0.6449, 132 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v4 | +0.077 [+0.058, +0.096] | +0.073 [+0.055, +0.092] | +0.00028 [+0.00016, +0.00040] | +2.1 [+1.3, +3.0] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v4_iso | agent-v2t | 132 | 131 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| cascade_v4 | agent-v2t | 132 | 131 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| always_g_v2t | agent-v2t | 560 | 558 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v4_iso | 0 (0 correct) | 23 (22 correct) |
| cascade_v4 | 0 (0 correct) | 23 (22 correct) |
| always_g_v2t | 0 (0 correct) | 26 (22 correct) |

### Agent tier: a tag named in the question was never touched

| policy | questions naming a tag | never touched |
|---|---|---|
| cascade_v4_iso | 98 | 13 (12 correct) |
| cascade_v4 | 98 | 13 (12 correct) |
| always_g_v2t | 463 | 17 (13 correct) |

### UPSTREAM_ISOLATION: secondary score, control valves do not isolate

Secondary only (offline re-score); the primary score is the gold key as built. Secondary reference = gold minus control valves.

| policy | primary correct | secondary correct |
|---|---|---|
| cascade_v4_iso | 16/30 | 11/30 |
| cascade_v4 | 16/30 | 11/30 |
| always_g_v2t | 16/30 | 11/30 |
| always_c_v2t | 0/30 | 0/30 |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v4_iso | 24 | 1 |
| cascade_v4 | 24 | 1 |
| always_g_v2t | 24 | 1 |
| always_c_v2t | 24 | 0 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v4_iso | cascade_v4 | always_g_v2t | always_c_v2t |
|---|---|---|---|---|
| DOWNSTREAM_ALL | 19/40 | 19/40 | 17/40 | 15/40 |
| GENERIC | 126/140 | 126/140 | 123/140 | 108/140 |
| ITEM | 90/90 | 90/90 | 88/90 | 90/90 |
| NEIGHBOURS_DOWNSTREAM | 27/27 | 27/27 | 27/27 | 27/27 |
| PATH | 65/73 | 65/73 | 65/73 | 63/73 |
| SIGNAL_CHAIN | 70/70 | 70/70 | 69/70 | 67/70 |
| UNIT_SCOPE | 78/80 | 78/80 | 80/80 | 61/80 |
| UPSTREAM_ALL | 20/20 | 20/20 | 18/20 | 20/20 |
| UPSTREAM_TO_FIRST_VALVE | 10/20 | 10/20 | 10/20 | 0/20 |

#### By family

| group | cascade_v4_iso | cascade_v4 | always_g_v2t | always_c_v2t |
|---|---|---|---|---|
| CONNECTED | 19/20 | 19/20 | 17/20 | 18/20 |
| COUNT_IN_UNIT | 30/30 | 30/30 | 30/30 | 30/30 |
| CROSS_UNIT | 28/30 | 28/30 | 30/30 | 19/30 |
| DOWNSTREAM_IN_UNIT | 17/20 | 17/20 | 15/20 | 15/20 |
| DOWNSTREAM_ISOLATION | 2/20 | 2/20 | 2/20 | 0/20 |
| FEEDING_UNITS | 20/20 | 20/20 | 20/20 | 12/20 |
| FLOW_PATH | 23/30 | 23/30 | 25/30 | 23/30 |
| INSTRUMENTS_OF_ITEM | 20/20 | 20/20 | 20/20 | 20/20 |
| LOOKUP_TYPE | 30/30 | 30/30 | 30/30 | 30/30 |
| LOOKUP_UNIT | 30/30 | 30/30 | 30/30 | 30/30 |
| LOOPS_NEAR_ITEM | 18/20 | 18/20 | 20/20 | 11/20 |
| LOOP_ACTUATED_VALVE | 30/30 | 30/30 | 30/30 | 30/30 |
| LOOP_MEASURED_EQUIPMENT | 30/30 | 30/30 | 29/30 | 26/30 |
| NEIGHBOURS_DOWNSTREAM | 30/30 | 30/30 | 30/30 | 30/30 |
| NO_PATH | 20/20 | 20/20 | 20/20 | 19/20 |
| ROUTE_AVOIDING | 19/20 | 19/20 | 16/20 | 19/20 |
| SAME_UNIT | 20/20 | 20/20 | 19/20 | 20/20 |
| SHEETS_OF_TAG | 30/30 | 30/30 | 29/30 | 30/30 |
| UNANSWERABLE_TAG | 20/20 | 20/20 | 20/20 | 20/20 |
| UNITS_REACHED | 20/20 | 20/20 | 17/20 | 20/20 |
| UPSTREAM_ISOLATION | 16/30 | 16/30 | 16/30 | 0/30 |
| UPSTREAM_SOURCES | 20/20 | 20/20 | 18/20 | 20/20 |
| VALVES_ON_PATH | 13/20 | 13/20 | 14/20 | 9/20 |

#### By k bin

| group | cascade_v4_iso | cascade_v4 | always_g_v2t | always_c_v2t |
|---|---|---|---|---|
| k=0 | 214/225 | 214/225 | 212/225 | 201/225 |
| k=1-2 | 172/192 | 172/192 | 169/192 | 139/192 |
| k>=3 | 79/103 | 79/103 | 76/103 | 72/103 |
| unanswerable | 40/40 | 40/40 | 40/40 | 39/40 |
