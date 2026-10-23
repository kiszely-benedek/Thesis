# Method-and-effort cascade report

Latency counts every model call of a question (final answer, retrieval and agent steps) plus local compute where recorded, summed over the tiers tried. LB-1: median <= 10 s; LB-2: p90 <= 60 s; LB-3: an answer later than C = 120 s counts as no answer (TIMED_OUT, wrong) for every arm alike, so acc@120 is the cutoff-scored accuracy. A run made under a live deadline cannot show raw accuracy beyond C.

## T4 Claims

Claims corpus: H1000.

- **PASS** Q4 (primary) cascade_v3 [headline]: supported
  - acc@C large minus small -0.020 [-0.052, +0.013] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.033 [-0.024, 0.090] (needs < 0.5): ok
- **FAIL** K1 [headline]: the cascade saves nothing
  - acc@C -0.007 [-0.030, +0.015]: ok
  - $/question -0.00003 [-0.00010, +0.00003] (needs CI below 0): not met
  - latency s/question -0.45 [-1.36, +0.43] (needs CI below 0): not met
- **PASS** K2 [headline]: supported
  - acc@C +0.145 [+0.118, +0.172] (needs CI above 0)
- **PASS** K3 [headline]: supported
  - median 8.2 [7.7, 8.7] s (limit 10): ok
  - p90 22.5 [19.6, 26.3] s (limit 60): ok
- **PASS** Q5 [headline]: supported
  - acc@C +0.228 [+0.185, +0.272] (needs CI above 0)
- **PASS** Q4' always_g_luna [headline]: supported
  - acc@C large minus small -0.017 [-0.050, +0.015] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.050 [-0.017, 0.116] (needs < 0.5): ok
- **PASS** Q4' always_c_luna [headline]: supported
  - acc@C large minus small -0.043 [-0.100, +0.015] (needs the interval to contain 0 or lie above): ok
  - cost elasticity -0.006 [-0.026, 0.013] (needs < 0.5): ok
- **PASS** Q4' cascade_v3_iso [headline]: supported
  - acc@C large minus small -0.017 [-0.046, +0.013] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.030 [-0.028, 0.089] (needs < 0.5): ok
- **PASS** Q4 (primary) cascade_v3 [held-out]: supported
  - acc@C large minus small -0.058 [-0.150, +0.033] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.042 [-0.072, 0.148] (needs < 0.5): ok
- **PASS** K1 [held-out]: supported
  - acc@C +0.017 [-0.050, +0.075]: ok
  - $/question -0.00028 [-0.00044, -0.00012] (needs CI below 0): ok
  - latency s/question -2.73 [-5.00, -0.59] (needs CI below 0): ok
- **PASS** K2 [held-out]: supported
  - acc@C +0.127 [+0.077, +0.178] (needs CI above 0)
- **PASS** K3 [held-out]: supported
  - median 9.2 [8.7, 10.5] s (limit 10): ok
  - p90 37.0 [25.8, 52.9] s (limit 60): ok
- **PASS** Q5 [held-out]: supported
  - acc@C +0.158 [+0.067, +0.250] (needs CI above 0)
- **PASS** Q4' always_g_luna [held-out]: supported
  - acc@C large minus small -0.050 [-0.142, +0.050] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.034 [-0.047, 0.118] (needs < 0.5): ok
- **PASS** Q4' always_c_luna [held-out]: supported
  - acc@C large minus small -0.058 [-0.175, +0.058] (needs the interval to contain 0 or lie above): ok
  - cost elasticity -0.005 [-0.030, 0.019] (needs < 0.5): ok
- **PASS** Q4' cascade_v3_iso [held-out]: supported
  - acc@C large minus small -0.058 [-0.150, +0.033] (needs the interval to contain 0 or lie above): ok
  - cost elasticity 0.042 [-0.072, 0.148] (needs < 0.5): ok
- **NOT_RUN** Q1: not run - need-aware Hierarchical was dropped (ADR-0047, ADR-0048)
- **NOT_RUN** Q2: not run - need-aware Hierarchical was dropped (ADR-0047, ADR-0048)
- **NOT_RUN** Q3: not run - hier_agent was dropped (ADR-0047)

## T1 Headline

### H100, scope `headline`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v3 | 460 | 431/460 0.937 [0.911, 0.956] | 548/580 | 0.00065 | 8.4 / 11.5 / 21.5 / 30.4 / 77.5 | PASS / PASS | cypher-luna 71%, agent-luna 29% | 71.3% | 0.948 (311/328) |
| always_g_luna | 460 | 433/460 0.941 [0.916, 0.959] | 551/580 | 0.00066 | 8.8 / 12.3 / 23.8 / 33.5 / 67.1 | PASS / PASS | agent-luna 100%, none 0% | - | - |
| always_c_luna | 460 | 340/460 0.739 [0.697, 0.777] | 433/580 | 0.00043 | 7.0 / 7.4 / 11.3 / 13.5 / 19.3 | PASS / PASS | cypher-luna 85%, none 15% | - | - |
| cascade_v3_iso | 460 | 439/460 0.954 [0.931, 0.970] | 556/580 | 0.00066 | 8.4 / 11.5 / 21.3 / 29.8 / 77.5 | PASS / PASS | cypher-luna 69%, agent-luna 31% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v3 | 8.4 [8.0, 8.8] | 21.5 [18.3, 24.9] |
| always_g_luna | 8.8 [8.0, 9.7] | 23.8 [20.3, 27.9] |
| always_c_luna | 7.0 [6.7, 7.3] | 11.3 [10.8, 12.2] |
| cascade_v3_iso | 8.4 [8.0, 8.8] | 21.3 [18.4, 24.8] |

### H100, scope `held-out`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v3 | 120 | 105/120 0.875 [0.804, 0.923] | 548/580 | 0.00097 | 9.9 / 16.2 / 35.9 / 49.4 / 77.5 | PASS / PASS | cypher-luna 72%, agent-luna 28% | 72.5% | 0.931 (81/87) |
| always_g_luna | 120 | 102/120 0.850 [0.775, 0.903] | 551/580 | 0.00124 | 15.5 / 19.9 / 37.8 / 52.7 / 67.1 | FAIL / PASS | agent-luna 99%, none 1% | - | - |
| always_c_luna | 120 | 84/120 0.700 [0.613, 0.775] | 433/580 | 0.00053 | 8.6 / 9.1 / 12.4 / 14.2 / 19.3 | PASS / PASS | cypher-luna 85%, none 15% | - | - |
| cascade_v3_iso | 120 | 105/120 0.875 [0.804, 0.923] | 556/580 | 0.00097 | 9.9 / 16.2 / 35.9 / 49.4 / 77.5 | PASS / PASS | cypher-luna 72%, agent-luna 28% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v3 | 9.9 [9.2, 11.0] | 35.9 [24.9, 44.0] |
| always_g_luna | 15.5 [14.0, 16.7] | 37.8 [30.7, 48.5] |
| always_c_luna | 8.6 [8.3, 9.2] | 12.4 [12.0, 13.6] |
| cascade_v3_iso | 9.9 [9.2, 11.0] | 35.9 [24.9, 44.0] |

### H1000, scope `headline`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v3 | 460 | 422/460 0.917 [0.889, 0.939] | 540/580 | 0.00071 | 8.2 / 11.8 / 22.5 / 33.7 / 92.3 | PASS / PASS | cypher-luna 67%, agent-luna 33% | 66.7% | 0.938 (288/307) |
| always_g_luna | 460 | 425/460 0.924 [0.896, 0.945] | 545/580 | 0.00074 | 8.2 / 12.3 / 24.9 / 36.5 / 86.0 | PASS / PASS | agent-luna 100%, none 0% | - | - |
| always_c_luna | 460 | 320/460 0.696 [0.652, 0.736] | 405/580 | 0.00043 | 6.3 / 7.1 / 11.0 / 13.0 / 38.1 | PASS / PASS | cypher-luna 82%, none 18% | - | - |
| cascade_v3_iso | 460 | 431/460 0.937 [0.911, 0.956] | 549/580 | 0.00070 | 8.2 / 11.8 / 22.5 / 31.8 / 92.3 | PASS / PASS | cypher-luna 64%, agent-luna 36% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v3 | 8.2 [7.7, 8.7] | 22.5 [19.6, 26.3] |
| always_g_luna | 8.2 [7.6, 8.9] | 24.9 [21.9, 27.6] |
| always_c_luna | 6.3 [6.0, 6.7] | 11.0 [10.1, 11.6] |
| cascade_v3_iso | 8.2 [7.7, 8.7] | 22.5 [19.8, 25.5] |

### H1000, scope `held-out`

| policy | n | acc@120 (95 % Wilson CI) | all-question acc@120 | $/question | latency s median / mean / p90 / p95 / max | LB-1 / LB-2 | answered by | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|---|---|---|---|
| cascade_v3 | 120 | 98/120 0.817 [0.738, 0.876] | 540/580 | 0.00107 | 9.2 / 16.9 / 37.0 / 54.8 / 92.3 | PASS / PASS | cypher-luna 70%, agent-luna 30% | 70.0% | 0.905 (76/84) |
| always_g_luna | 120 | 96/120 0.800 [0.720, 0.862] | 545/580 | 0.00134 | 14.9 / 19.6 / 40.2 / 46.2 / 60.7 | FAIL / PASS | agent-luna 100% | - | - |
| always_c_luna | 120 | 77/120 0.642 [0.553, 0.722] | 405/580 | 0.00052 | 8.4 / 9.1 / 12.1 / 14.7 / 38.1 | PASS / PASS | cypher-luna 81%, none 19% | - | - |
| cascade_v3_iso | 120 | 98/120 0.817 [0.738, 0.876] | 549/580 | 0.00107 | 9.2 / 16.9 / 37.0 / 54.8 / 92.3 | PASS / PASS | cypher-luna 70%, agent-luna 30% | - | - |

Latency, 95 % bootstrap intervals (s):

| policy | median | p90 |
|---|---|---|
| cascade_v3 | 9.2 [8.7, 10.5] | 37.0 [25.8, 52.9] |
| always_g_luna | 14.9 [13.2, 16.9] | 40.2 [31.6, 44.5] |
| always_c_luna | 8.4 [8.0, 8.7] | 12.1 [10.8, 14.7] |
| cascade_v3_iso | 9.2 [8.7, 10.5] | 37.0 [25.8, 52.9] |

## T2 Splits

### H100

| policy | dev-old | dev-new | held-out | held-out-wording |
|---|---|---|---|---|
| cascade_v3 | 206/220 0.936 [0.896, 0.962] | 120/120 1.000 [0.969, 1.000] | 105/120 0.875 [0.804, 0.923] | 87/90 0.967 [0.907, 0.989] |
| always_g_luna | 214/220 0.973 [0.942, 0.987] | 117/120 0.975 [0.929, 0.991] | 102/120 0.850 [0.775, 0.903] | 88/90 0.978 [0.923, 0.994] |
| always_c_luna | 167/220 0.759 [0.698, 0.811] | 89/120 0.742 [0.657, 0.812] | 84/120 0.700 [0.613, 0.775] | 68/90 0.756 [0.658, 0.833] |
| cascade_v3_iso | 214/220 0.973 [0.942, 0.987] | 120/120 1.000 [0.969, 1.000] | 105/120 0.875 [0.804, 0.923] | 87/90 0.967 [0.907, 0.989] |

### H1000

| policy | dev-old | dev-new | held-out | held-out-wording |
|---|---|---|---|---|
| cascade_v3 | 207/220 0.941 [0.902, 0.965] | 117/120 0.975 [0.929, 0.991] | 98/120 0.817 [0.738, 0.876] | 88/90 0.978 [0.923, 0.994] |
| always_g_luna | 215/220 0.977 [0.948, 0.990] | 114/120 0.950 [0.895, 0.977] | 96/120 0.800 [0.720, 0.862] | 90/90 1.000 [0.959, 1.000] |
| always_c_luna | 157/220 0.714 [0.651, 0.769] | 86/120 0.717 [0.630, 0.790] | 77/120 0.642 [0.553, 0.722] | 63/90 0.700 [0.599, 0.785] |
| cascade_v3_iso | 216/220 0.982 [0.954, 0.993] | 117/120 0.975 [0.929, 0.991] | 98/120 0.817 [0.738, 0.876] | 88/90 0.978 [0.923, 0.994] |

### Generalisation gap

| corpus | policy | dev | held-out | gap dev - held-out (unpaired 95 % CI) |
|---|---|---|---|---|
| H100 | cascade_v3 | 326/340 | 105/120 | +0.084 [+0.025, +0.148] |
| H100 | always_g_luna | 331/340 | 102/120 | +0.124 [+0.059, +0.190] |
| H100 | always_c_luna | 256/340 | 84/120 | +0.053 [-0.039, +0.148] |
| H100 | cascade_v3_iso | 334/340 | 105/120 | +0.107 [+0.051, +0.169] |
| H1000 | cascade_v3 | 324/340 | 98/120 | +0.136 [+0.067, +0.210] |
| H1000 | always_g_luna | 329/340 | 96/120 | +0.168 [+0.093, +0.244] |
| H1000 | always_c_luna | 243/340 | 77/120 | +0.073 [-0.024, +0.172] |
| H1000 | cascade_v3_iso | 333/340 | 98/120 | +0.163 [+0.094, +0.235] |

## T3 Scale

H100 has 100 sheets, H1000 has 1001; e = ln(cost ratio) / ln(sheet ratio).

| scope | policy | acc@C H100 | acc@C H1000 | H1000 - H100 (unpaired CI) | $/question | cost elasticity e (95 % CI) | latency ratio median / p90 |
|---|---|---|---|---|---|---|---|
| headline | cascade_v3 | 0.937 [0.911, 0.956] | 0.917 [0.889, 0.939] | -0.020 [-0.052, +0.013] | 0.00065 -> 0.00071 | 0.033 [-0.024, 0.090] | 0.97 / 1.05 |
| headline | always_g_luna | 0.941 [0.916, 0.959] | 0.924 [0.896, 0.945] | -0.017 [-0.050, +0.015] | 0.00066 -> 0.00074 | 0.050 [-0.017, 0.116] | 0.93 / 1.05 |
| headline | always_c_luna | 0.739 [0.697, 0.777] | 0.696 [0.652, 0.736] | -0.043 [-0.100, +0.015] | 0.00043 -> 0.00043 | -0.006 [-0.026, 0.013] | 0.91 / 0.97 |
| headline | cascade_v3_iso | 0.954 [0.931, 0.970] | 0.937 [0.911, 0.956] | -0.017 [-0.046, +0.013] | 0.00066 -> 0.00070 | 0.030 [-0.028, 0.089] | 0.97 / 1.06 |
| held-out | cascade_v3 | 0.875 [0.804, 0.923] | 0.817 [0.738, 0.876] | -0.058 [-0.150, +0.033] | 0.00097 -> 0.00107 | 0.042 [-0.072, 0.148] | 0.94 / 1.03 |
| held-out | always_g_luna | 0.850 [0.775, 0.903] | 0.800 [0.720, 0.862] | -0.050 [-0.142, +0.050] | 0.00124 -> 0.00134 | 0.034 [-0.047, 0.118] | 0.96 / 1.06 |
| held-out | always_c_luna | 0.700 [0.613, 0.775] | 0.642 [0.553, 0.722] | -0.058 [-0.175, +0.058] | 0.00053 -> 0.00052 | -0.005 [-0.030, 0.019] | 0.97 / 0.97 |
| held-out | cascade_v3_iso | 0.875 [0.804, 0.923] | 0.817 [0.738, 0.876] | -0.058 [-0.150, +0.033] | 0.00097 -> 0.00107 | 0.042 [-0.072, 0.148] | 0.94 / 1.03 |

### Tier 1 by k bin (headline questions)

| corpus | policy | k bin | n | tier-1 accept share | tier-1 accept precision |
|---|---|---|---|---|---|
| H100 | cascade_v3 | k=0 | 165 | 76.4% | 0.992 (125/126) |
| H100 | cascade_v3 | k=1-2 | 154 | 78.6% | 0.926 (112/121) |
| H100 | cascade_v3 | k>=3 | 101 | 80.2% | 0.914 (74/81) |
| H100 | cascade_v3 | unanswerable | 40 | 0.0% | - |
| H1000 | cascade_v3 | k=0 | 158 | 69.6% | 0.982 (108/110) |
| H1000 | cascade_v3 | k=1-2 | 142 | 78.9% | 0.875 (98/112) |
| H1000 | cascade_v3 | k>=3 | 120 | 70.8% | 0.965 (82/85) |
| H1000 | cascade_v3 | unanswerable | 40 | 0.0% | - |

## Paired bootstrap sections (K1, K2, Q5; mean difference [95 % CI])

| claim | corpus | scope | policy - reference | acc@C | $/question | latency s |
|---|---|---|---|---|---|---|
| K1 | H100 | headline | cascade_v3 - always_g_luna | -0.004 [-0.028, +0.020] | -0.00001 [-0.00006, +0.00005] | -0.77 [-1.60, +0.01] |
| K2 | H100 | headline | cascade_v3 - random escalation | +0.138 [+0.113, +0.165] | +0.00003 [-0.00001, +0.00008] | +0.52 [-0.20, +1.26] |
| Q5 | H100 | headline | always_g_luna - always_c_luna | +0.202 [+0.159, +0.246] | +0.00023 [+0.00017, +0.00029] | +4.82 [+4.00, +5.72] |
| K1 | H100 | held-out | cascade_v3 - always_g_luna | +0.025 [-0.033, +0.083] | -0.00027 [-0.00043, -0.00011] | -3.72 [-6.06, -1.52] |
| K2 | H100 | held-out | cascade_v3 - random escalation | +0.132 [+0.081, +0.185] | +0.00010 [-0.00003, +0.00025] | +1.56 [-0.53, +3.87] |
| Q5 | H100 | held-out | always_g_luna - always_c_luna | +0.150 [+0.058, +0.242] | +0.00071 [+0.00056, +0.00087] | +10.74 [+8.54, +13.15] |
| K1 | H1000 | headline | cascade_v3 - always_g_luna | -0.007 [-0.030, +0.015] | -0.00003 [-0.00010, +0.00003] | -0.45 [-1.36, +0.43] |
| K2 | H1000 | headline | cascade_v3 - random escalation | +0.145 [+0.118, +0.172] | +0.00003 [-0.00002, +0.00009] | +0.63 [-0.14, +1.44] |
| Q5 | H1000 | headline | always_g_luna - always_c_luna | +0.228 [+0.185, +0.272] | +0.00031 [+0.00024, +0.00040] | +5.16 [+4.22, +6.19] |
| K1 | H1000 | held-out | cascade_v3 - always_g_luna | +0.017 [-0.050, +0.075] | -0.00028 [-0.00044, -0.00012] | -2.73 [-5.00, -0.59] |
| K2 | H1000 | held-out | cascade_v3 - random escalation | +0.127 [+0.077, +0.178] | +0.00014 [-0.00001, +0.00031] | +1.93 [-0.26, +4.20] |
| Q5 | H1000 | held-out | always_g_luna - always_c_luna | +0.158 [+0.067, +0.250] | +0.00082 [+0.00065, +0.00100] | +10.54 [+8.46, +12.69] |

## Notes

- scope `headline` leaves out the family LOOP_ACTUATED_VALVE (ADR-0044 U2)

## Corpus H100 (580 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v3 | 548/580 | 548/580 | 0.3619 | 0.00062 | 8.1 / 11.3 / 21.8 / 30.4 / 84.5 | cypher-luna 73%, agent-luna 27% | 0.953 (404/424) | 0.933 (404/433) |
| always_g_luna | 551/580 | 551/580 | 0.3640 | 0.00063 | 8.5 / 11.8 / 22.5 / 31.7 / 67.1 | agent-luna 99%, none 1% | - | - |
| always_c_luna | 433/580 | 433/580 | 0.2438 | 0.00042 | 6.7 / 7.5 / 11.6 / 13.6 / 84.5 | cypher-luna 85%, none 15% | - | - |
| cascade_v3_iso | 556/580 | 556/580 | 0.3627 | 0.00063 | 8.1 / 11.3 / 21.6 / 30.4 / 84.5 | cypher-luna 71%, agent-luna 29% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v3 | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_g_luna | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c_luna | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v3_iso | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v3 | 548 / 548 | 565 / 565 ($0.3791) | 465.7 [457, 475] / 465.7 [457, 475] ($0.3416, 156 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v3 | +0.142 [+0.117, +0.166] | +0.142 [+0.117, +0.166] | +0.00003 [-0.00000, +0.00007] | +0.6 [-0.0, +1.3] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v3 | agent-luna | 156 | 153 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| always_g_luna | agent-luna | 580 | 571 | 0 | 0 | 5 | 4 | 0 | 0 | 0 | 0 |
| cascade_v3_iso | agent-luna | 166 | 163 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v3 | 0 (0 correct) | 36 (36 correct) |
| always_g_luna | 3 (0 correct) | 46 (43 correct) |
| cascade_v3_iso | 0 (0 correct) | 36 (36 correct) |

### Agent tier: a tag named in the question was never touched

| policy | questions naming a tag | never touched |
|---|---|---|
| cascade_v3 | 132 | 23 (23 correct) |
| always_g_luna | 483 | 33 (30 correct) |
| cascade_v3_iso | 142 | 23 (23 correct) |

### UPSTREAM_ISOLATION: secondary score, control valves do not isolate

Secondary only (offline re-score); the primary score is the gold key as built. Secondary reference = gold minus control valves.

| policy | primary correct | secondary correct |
|---|---|---|
| cascade_v3 | 17/30 | 11/26 |
| always_g_luna | 25/30 | 14/26 |
| always_c_luna | 3/30 | 2/26 |
| cascade_v3_iso | 25/30 | 14/26 |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v3 | 36 | 0 |
| always_g_luna | 36 | 0 |
| always_c_luna | 36 | 0 |
| cascade_v3_iso | 36 | 0 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v3 | always_g_luna | always_c_luna | cascade_v3_iso |
|---|---|---|---|---|
| DOWNSTREAM_ALL | 30/40 | 29/40 | 22/40 | 30/40 |
| GENERIC | 157/160 | 150/160 | 120/160 | 157/160 |
| ITEM | 89/89 | 88/89 | 84/89 | 89/89 |
| NEIGHBOURS_DOWNSTREAM | 28/28 | 28/28 | 18/28 | 28/28 |
| PATH | 70/73 | 73/73 | 59/73 | 70/73 |
| SIGNAL_CHAIN | 70/70 | 70/70 | 47/70 | 70/70 |
| UNIT_SCOPE | 76/80 | 78/80 | 69/80 | 76/80 |
| UPSTREAM_ALL | 20/20 | 19/20 | 13/20 | 20/20 |
| UPSTREAM_TO_FIRST_VALVE | 8/20 | 16/20 | 1/20 | 16/20 |

#### By family

| group | cascade_v3 | always_g_luna | always_c_luna | cascade_v3_iso |
|---|---|---|---|---|
| CONNECTED | 20/20 | 20/20 | 18/20 | 20/20 |
| COUNT_IN_UNIT | 29/30 | 30/30 | 26/30 | 29/30 |
| CROSS_UNIT | 30/30 | 29/30 | 27/30 | 30/30 |
| DOWNSTREAM_IN_UNIT | 20/20 | 18/20 | 17/20 | 20/20 |
| DOWNSTREAM_ISOLATION | 10/20 | 11/20 | 5/20 | 10/20 |
| FEEDING_UNITS | 17/20 | 19/20 | 16/20 | 17/20 |
| FIRST_MEETING_POINT | 19/20 | 16/20 | 9/20 | 19/20 |
| FLOW_PATH | 27/30 | 30/30 | 25/30 | 27/30 |
| INSTRUMENTS_OF_ITEM | 20/20 | 20/20 | 10/20 | 20/20 |
| LOOKUP_TYPE | 30/30 | 29/30 | 27/30 | 30/30 |
| LOOKUP_UNIT | 30/30 | 30/30 | 29/30 | 30/30 |
| LOOPS_NEAR_ITEM | 20/20 | 20/20 | 14/20 | 20/20 |
| LOOP_ACTUATED_VALVE | 30/30 | 30/30 | 25/30 | 30/30 |
| LOOP_MEASURED_EQUIPMENT | 30/30 | 30/30 | 19/30 | 30/30 |
| NEIGHBOURS_DOWNSTREAM | 30/30 | 30/30 | 25/30 | 30/30 |
| NO_PATH | 20/20 | 20/20 | 13/20 | 20/20 |
| ROUTE_AVOIDING | 20/20 | 20/20 | 19/20 | 20/20 |
| SAME_UNIT | 20/20 | 20/20 | 17/20 | 20/20 |
| SHEETS_OF_TAG | 30/30 | 29/30 | 29/30 | 30/30 |
| UNANSWERABLE_TAG | 20/20 | 20/20 | 12/20 | 20/20 |
| UNITS_REACHED | 20/20 | 19/20 | 18/20 | 20/20 |
| UPSTREAM_ISOLATION | 17/30 | 25/30 | 3/30 | 25/30 |
| UPSTREAM_SOURCES | 20/20 | 19/20 | 13/20 | 20/20 |
| VALVES_ON_PATH | 19/20 | 17/20 | 17/20 | 19/20 |

#### By k bin

| group | cascade_v3 | always_g_luna | always_c_luna | cascade_v3_iso |
|---|---|---|---|---|
| k=0 | 221/223 | 219/223 | 172/223 | 222/223 |
| k=1-2 | 181/199 | 185/199 | 151/199 | 184/199 |
| k>=3 | 106/118 | 107/118 | 85/118 | 110/118 |
| unanswerable | 40/40 | 40/40 | 25/40 | 40/40 |

## Corpus H1000 (580 questions)

### Policies

| policy | correct | acc@120 | total $ | $/question | latency s median / mean / p90 / p95 / max | answered by | tier-1 accept precision | tier-1 accept recall |
|---|---|---|---|---|---|---|---|---|
| cascade_v3 | 540/580 | 540/580 | 0.3840 | 0.00066 | 7.9 / 11.0 / 20.4 / 30.7 / 92.3 | cypher-luna 68%, agent-luna 32% | 0.947 (373/394) | 0.921 (373/405) |
| always_g_luna | 545/580 | 545/580 | 0.3992 | 0.00069 | 8.0 / 11.7 / 22.8 / 31.8 / 86.0 | agent-luna 100%, none 0% | - | - |
| always_c_luna | 405/580 | 405/580 | 0.2401 | 0.00041 | 5.9 / 6.8 / 10.7 / 13.0 / 38.1 | cypher-luna 80%, none 20% | - | - |
| cascade_v3_iso | 549/580 | 549/580 | 0.3824 | 0.00066 | 7.9 / 11.0 / 21.1 / 28.7 / 92.3 | cypher-luna 66%, agent-luna 34% | - | - |

### Latency bound

| policy | over C = 120 s | correct lost to C | latency without local compute | median <= 10 s | p90 <= 60 s |
|---|---|---|---|---|---|
| cascade_v3 | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_g_luna | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| always_c_luna | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |
| cascade_v3_iso | 0 | 0 | 0 | LB-1 PASS | LB-2 PASS |

### References (never deployable)

| policy | correct / acc@120 | oracle cascade | random escalation, same share |
|---|---|---|---|
| cascade_v3 | 540 / 540 | 557 / 557 ($0.4007) | 450.0 [440, 460] / 450.0 [440, 460] ($0.3680, 186 escalated) |


### Paired bootstrap vs random escalation

| policy | accuracy | acc@120 | $/question | latency s/question |
|---|---|---|---|---|
| cascade_v3 | +0.155 [+0.132, +0.180] | +0.155 [+0.132, +0.180] | +0.00003 [-0.00002, +0.00007] | +0.5 [-0.1, +1.2] |

### Agent tier: stop reasons

| policy | tier | questions tried | done | deadline | runaway | prompt_budget | errors | max_steps | overflow | timed_out | unrecorded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cascade_v3 | agent-luna | 186 | 183 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |
| always_g_luna | agent-luna | 580 | 569 | 0 | 0 | 11 | 0 | 0 | 0 | 0 | 0 |
| cascade_v3_iso | agent-luna | 197 | 194 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 |

### Agent tier: answers without evidence gathered

| policy | no tool call | no plant item touched |
|---|---|---|
| cascade_v3 | 0 (0 correct) | 42 (42 correct) |
| always_g_luna | 0 (0 correct) | 49 (49 correct) |
| cascade_v3_iso | 0 (0 correct) | 42 (42 correct) |

### Agent tier: a tag named in the question was never touched

| policy | questions naming a tag | never touched |
|---|---|---|
| cascade_v3 | 158 | 31 (31 correct) |
| always_g_luna | 483 | 40 (40 correct) |
| cascade_v3_iso | 169 | 31 (31 correct) |

### UPSTREAM_ISOLATION: secondary score, control valves do not isolate

Secondary only (offline re-score); the primary score is the gold key as built. Secondary reference = gold minus control valves.

| policy | primary correct | secondary correct |
|---|---|---|
| cascade_v3 | 15/30 | 9/20 |
| always_g_luna | 26/30 | 16/20 |
| always_c_luna | 4/30 | 1/20 |
| cascade_v3_iso | 24/30 | 15/20 |

### Made-up yes (BOOLEAN questions whose gold is no)

| policy | gold-no questions | answered yes |
|---|---|---|
| cascade_v3 | 38 | 0 |
| always_g_luna | 38 | 0 |
| always_c_luna | 38 | 0 |
| cascade_v3_iso | 38 | 0 |

### Breakdowns (correct / questions)

#### By need label

| group | cascade_v3 | always_g_luna | always_c_luna | cascade_v3_iso |
|---|---|---|---|---|
| DOWNSTREAM_ALL | 27/40 | 29/40 | 19/40 | 27/40 |
| GENERIC | 152/160 | 146/160 | 112/160 | 152/160 |
| ITEM | 88/88 | 88/88 | 78/88 | 88/88 |
| NEIGHBOURS_DOWNSTREAM | 29/29 | 29/29 | 19/29 | 29/29 |
| PATH | 73/73 | 73/73 | 61/73 | 73/73 |
| SIGNAL_CHAIN | 70/70 | 70/70 | 38/70 | 70/70 |
| UNIT_SCOPE | 76/80 | 79/80 | 65/80 | 76/80 |
| UPSTREAM_ALL | 18/20 | 15/20 | 13/20 | 18/20 |
| UPSTREAM_TO_FIRST_VALVE | 7/20 | 16/20 | 0/20 | 16/20 |

#### By family

| group | cascade_v3 | always_g_luna | always_c_luna | cascade_v3_iso |
|---|---|---|---|---|
| CONNECTED | 20/20 | 20/20 | 15/20 | 20/20 |
| COUNT_IN_UNIT | 30/30 | 30/30 | 24/30 | 30/30 |
| CROSS_UNIT | 30/30 | 29/30 | 28/30 | 30/30 |
| DOWNSTREAM_IN_UNIT | 19/20 | 19/20 | 17/20 | 19/20 |
| DOWNSTREAM_ISOLATION | 8/20 | 10/20 | 2/20 | 8/20 |
| FEEDING_UNITS | 16/20 | 20/20 | 13/20 | 16/20 |
| FIRST_MEETING_POINT | 17/20 | 12/20 | 15/20 | 17/20 |
| FLOW_PATH | 30/30 | 30/30 | 27/30 | 30/30 |
| INSTRUMENTS_OF_ITEM | 20/20 | 20/20 | 12/20 | 20/20 |
| LOOKUP_TYPE | 30/30 | 30/30 | 25/30 | 30/30 |
| LOOKUP_UNIT | 30/30 | 30/30 | 25/30 | 30/30 |
| LOOPS_NEAR_ITEM | 20/20 | 20/20 | 12/20 | 20/20 |
| LOOP_ACTUATED_VALVE | 30/30 | 30/30 | 22/30 | 30/30 |
| LOOP_MEASURED_EQUIPMENT | 30/30 | 30/30 | 11/30 | 30/30 |
| NEIGHBOURS_DOWNSTREAM | 30/30 | 30/30 | 22/30 | 30/30 |
| NO_PATH | 20/20 | 20/20 | 16/20 | 20/20 |
| ROUTE_AVOIDING | 18/20 | 17/20 | 11/20 | 18/20 |
| SAME_UNIT | 20/20 | 20/20 | 17/20 | 20/20 |
| SHEETS_OF_TAG | 30/30 | 30/30 | 26/30 | 30/30 |
| UNANSWERABLE_TAG | 20/20 | 20/20 | 12/20 | 20/20 |
| UNITS_REACHED | 20/20 | 18/20 | 20/20 | 20/20 |
| UPSTREAM_ISOLATION | 15/30 | 26/30 | 4/30 | 24/30 |
| UPSTREAM_SOURCES | 18/20 | 15/20 | 13/20 | 18/20 |
| VALVES_ON_PATH | 19/20 | 19/20 | 16/20 | 19/20 |

#### By k bin

| group | cascade_v3 | always_g_luna | always_c_luna | cascade_v3_iso |
|---|---|---|---|---|
| k=0 | 214/217 | 215/217 | 151/217 | 216/217 |
| k=1-2 | 164/185 | 175/185 | 130/185 | 170/185 |
| k>=3 | 122/138 | 115/138 | 96/138 | 123/138 |
| unanswerable | 40/40 | 40/40 | 28/40 | 40/40 |
