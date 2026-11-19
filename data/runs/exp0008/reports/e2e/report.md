# EXP-0004 end-to-end report

System: `cascade_v4_iso`, accuracy at the 120 s cutoff (acc@cutoff), 1100 questions per arm over 5 plants, paired by question id.

## Pre-registered claims

| Claim | Difference | Estimate [95% CI] | Pass if | Verdict | Plants with the pooled sign |
|---|---|---|---|---|---|
| E1 | acc(V,D0) - acc(R5) | -0.085 [-0.108, -0.065] | CI upper < 0 | PASS | 5 of 5 |
| E2 | acc(V,D2) - acc(V,D0) | 0.034 [0.018, 0.050] | CI lower > 0 | PASS | 5 of 5 |
| E3 | acc(V,D4) - acc(V,D0) | 0.007 [-0.023, 0.037] | CI lower > 0 | FAIL | 3 of 5 |
| E4 (D2) | acc(V,D2) - acc(R5) | -0.052 [-0.071, -0.032] | CI lower > -0.03 | FAIL | 5 of 5 |
| E4 (D4) | acc(V,D4) - acc(R5) | -0.078 [-0.101, -0.058] | CI lower > -0.03 | FAIL | 5 of 5 |

## Accuracy per plant

| Plant | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| H1000g21p1 | 199/220 0.905 [0.858, 0.937] | 179/220 0.814 [0.757, 0.860] | 187/220 0.850 [0.797, 0.891] | 180/220 0.818 [0.762, 0.864] |
| H1000g21p2 | 198/220 0.900 [0.853, 0.933] | 180/220 0.818 [0.762, 0.864] | 184/220 0.836 [0.782, 0.879] | 184/220 0.836 [0.782, 0.879] |
| H1000g21p3 | 195/220 0.886 [0.838, 0.922] | 181/220 0.823 [0.767, 0.868] | 190/220 0.864 [0.812, 0.903] | 178/220 0.809 [0.752, 0.856] |
| H1000g21p4 | 200/220 0.909 [0.864, 0.940] | 182/220 0.827 [0.772, 0.871] | 188/220 0.855 [0.802, 0.895] | 178/220 0.809 [0.752, 0.856] |
| H1000g21p5 | 207/220 0.941 [0.902, 0.965] | 183/220 0.832 [0.777, 0.875] | 193/220 0.877 [0.827, 0.914] | 193/220 0.877 [0.827, 0.914] |

## Accuracy per arm (pooled over the plants)

| Arm | n | correct@cutoff | acc@cutoff (two-stage bootstrap 95% CI) | New spend USD (cache misses) |
|---|---|---|---|---|
| R5 | 1100 | 999 | 0.908 [0.885, 0.932] | 3.4102 |
| V-d0 | 1100 | 905 | 0.823 [0.800, 0.845] | 1.2422 |
| V-d2 | 1100 | 942 | 0.856 [0.832, 0.880] | 1.1892 |
| V-d4 | 1100 | 913 | 0.830 [0.798, 0.862] | 2.0085 |

## Accuracy per question family (correct/n)

| Family | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| CONNECTED | 46/50 (0.920) | 37/50 (0.740) | 40/50 (0.800) | 45/50 (0.900) |
| COUNT_IN_UNIT | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) |
| CROSS_UNIT | 49/50 (0.980) | 50/50 (1.000) | 49/50 (0.980) | 48/50 (0.960) |
| DOWNSTREAM_IN_UNIT | 48/50 (0.960) | 36/50 (0.720) | 39/50 (0.780) | 26/50 (0.520) |
| DOWNSTREAM_ISOLATION | 5/50 (0.100) | 3/50 (0.060) | 5/50 (0.100) | 3/50 (0.060) |
| FEEDING_UNITS | 49/50 (0.980) | 49/50 (0.980) | 50/50 (1.000) | 47/50 (0.940) |
| FLOW_PATH | 42/50 (0.840) | 36/50 (0.720) | 38/50 (0.760) | 35/50 (0.700) |
| INSTRUMENTS_OF_ITEM | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 46/50 (0.920) |
| LOOKUP_TYPE | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 49/50 (0.980) |
| LOOKUP_UNIT | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) |
| LOOPS_NEAR_ITEM | 44/50 (0.880) | 44/50 (0.880) | 44/50 (0.880) | 41/50 (0.820) |
| LOOP_MEASURED_EQUIPMENT | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) |
| NEIGHBOURS_DOWNSTREAM | 50/50 (1.000) | 45/50 (0.900) | 47/50 (0.940) | 49/50 (0.980) |
| NO_PATH | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 34/50 (0.680) |
| ROUTE_AVOIDING | 49/50 (0.980) | 45/50 (0.900) | 45/50 (0.900) | 46/50 (0.920) |
| SAME_UNIT | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) |
| SHEETS_OF_TAG | 50/50 (1.000) | 25/50 (0.500) | 37/50 (0.740) | 49/50 (0.980) |
| UNANSWERABLE_TAG | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) | 50/50 (1.000) |
| UNITS_REACHED | 48/50 (0.960) | 35/50 (0.700) | 42/50 (0.840) | 43/50 (0.860) |
| UPSTREAM_ISOLATION | 24/50 (0.480) | 25/50 (0.500) | 27/50 (0.540) | 22/50 (0.440) |
| UPSTREAM_SOURCES | 50/50 (1.000) | 43/50 (0.860) | 45/50 (0.900) | 35/50 (0.700) |
| VALVES_ON_PATH | 45/50 (0.900) | 32/50 (0.640) | 34/50 (0.680) | 45/50 (0.900) |

## Exposed vs unexposed (correct/n)

| Group | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| exposed (k_identity > 0) | 122/146 (0.836) | 33/146 (0.226) | 66/146 (0.452) | 104/146 (0.712) |
| unexposed (k_identity = 0 or None) | 877/954 (0.919) | 872/954 (0.914) | 876/954 (0.918) | 809/954 (0.848) |

## Tier outcomes

| Arm | Tier | Outcomes (questions) |
|---|---|---|
| R5 | cypher-v2t | ANSWERED: 972, PARSE_FAILURE: 4, RETRIEVAL_ERROR: 121, TIMED_OUT: 3 |
| R5 | agent-v2t | ANSWERED: 1096, PARSE_FAILURE: 3, TIMED_OUT: 1 |
| V-d0 | cypher-v2t | ANSWERED: 1041, PARSE_FAILURE: 32, RETRIEVAL_ERROR: 25, TIMED_OUT: 2 |
| V-d0 | agent-v2t | ANSWERED: 1100 |
| V-d2 | cypher-v2t | ANSWERED: 1029, PARSE_FAILURE: 41, RETRIEVAL_ERROR: 28, TIMED_OUT: 2 |
| V-d2 | agent-v2t | ANSWERED: 1100 |
| V-d4 | cypher-v2t | ANSWERED: 970, PARSE_FAILURE: 8, RETRIEVAL_ERROR: 120, TIMED_OUT: 2 |
| V-d4 | agent-v2t | ANSWERED: 1096, PARSE_FAILURE: 3, TIMED_OUT: 1 |

## Notes

- Exposed means the question's k_identity is greater than 0; a missing (None) k_identity counts as unexposed.
- Accuracy and outcome counts cover the same questions (R5's headline scope).
- New spend is the sum of cost_usd over calls not served from the cache, over all questions of the run (not only the headline scope). The V arms reused R5's cache, so their figure counts only the calls R5 had not already paid for: it is not a cost per arm and must not be compared with R5's full spend.
- Pooled over 5 plants: the value is the equal-weight mean of the plants; intervals are two-stage cluster bootstraps (plants, then questions) with the EXP-0007 seed and resample count, and every claim uses the same draws. With few plants the bootstrap understates between-plant variance (about 4/5 at five).
- 'Plants with the pooled sign' is descriptive and judges nothing.
