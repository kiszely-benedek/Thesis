# EXP-0004 end-to-end report

System: `cascade_v4_iso`, accuracy at the 120 s cutoff (acc@cutoff), 440 questions per arm, paired by question id.

## Pre-registered claims

| Claim | Difference | Estimate [95% CI] | Pass if | Verdict |
|---|---|---|---|---|
| E1 | acc(V,D0) - acc(R5) | -0.125 [-0.159, -0.091] | CI upper < 0 | PASS |
| E2 | acc(V,D2) - acc(V,D0) | 0.093 [0.064, 0.123] | CI lower > 0 | PASS |
| E3 | acc(V,D4) - acc(V,D0) | 0.032 [-0.005, 0.068] | CI lower > 0 | FAIL |
| E4 (D2) | acc(V,D2) - acc(R5) | -0.032 [-0.055, -0.009] | CI lower > -0.03 | FAIL |
| E4 (D4) | acc(V,D4) - acc(R5) | -0.093 [-0.125, -0.064] | CI lower > -0.03 | FAIL |

## Accuracy per arm

| Arm | n | correct@cutoff | acc@cutoff (Wilson 95% CI) | New spend USD (cache misses) |
|---|---|---|---|---|
| R5 | 440 | 392 | 0.891 [0.858, 0.917] | 1.3735 |
| V-d0 | 440 | 337 | 0.766 [0.724, 0.803] | 0.5730 |
| V-d2 | 440 | 378 | 0.859 [0.823, 0.889] | 0.5366 |
| V-d4 | 440 | 351 | 0.798 [0.758, 0.833] | 0.8351 |

## Accuracy per question family (correct/n)

| Family | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| CONNECTED | 19/20 (0.950) | 15/20 (0.750) | 18/20 (0.900) | 19/20 (0.950) |
| COUNT_IN_UNIT | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| CROSS_UNIT | 20/20 (1.000) | 19/20 (0.950) | 19/20 (0.950) | 19/20 (0.950) |
| DOWNSTREAM_IN_UNIT | 17/20 (0.850) | 9/20 (0.450) | 16/20 (0.800) | 6/20 (0.300) |
| DOWNSTREAM_ISOLATION | 2/20 (0.100) | 1/20 (0.050) | 2/20 (0.100) | 1/20 (0.050) |
| FEEDING_UNITS | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| FLOW_PATH | 14/20 (0.700) | 13/20 (0.650) | 15/20 (0.750) | 12/20 (0.600) |
| INSTRUMENTS_OF_ITEM | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| LOOKUP_TYPE | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| LOOKUP_UNIT | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| LOOPS_NEAR_ITEM | 18/20 (0.900) | 16/20 (0.800) | 16/20 (0.800) | 18/20 (0.900) |
| LOOP_MEASURED_EQUIPMENT | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| NEIGHBOURS_DOWNSTREAM | 20/20 (1.000) | 15/20 (0.750) | 18/20 (0.900) | 19/20 (0.950) |
| NO_PATH | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 7/20 (0.350) |
| ROUTE_AVOIDING | 19/20 (0.950) | 16/20 (0.800) | 17/20 (0.850) | 19/20 (0.950) |
| SAME_UNIT | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 19/20 (0.950) |
| SHEETS_OF_TAG | 20/20 (1.000) | 9/20 (0.450) | 16/20 (0.800) | 20/20 (1.000) |
| UNANSWERABLE_TAG | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) | 20/20 (1.000) |
| UNITS_REACHED | 20/20 (1.000) | 11/20 (0.550) | 18/20 (0.900) | 16/20 (0.800) |
| UPSTREAM_ISOLATION | 10/20 (0.500) | 10/20 (0.500) | 13/20 (0.650) | 10/20 (0.500) |
| UPSTREAM_SOURCES | 20/20 (1.000) | 12/20 (0.600) | 18/20 (0.900) | 14/20 (0.700) |
| VALVES_ON_PATH | 13/20 (0.650) | 11/20 (0.550) | 12/20 (0.600) | 12/20 (0.600) |

## Exposed vs unexposed (correct/n)

| Group | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| exposed (k_identity > 0) | 74/93 (0.796) | 21/93 (0.226) | 58/93 (0.624) | 55/93 (0.591) |
| unexposed (k_identity = 0 or None) | 318/347 (0.916) | 316/347 (0.911) | 320/347 (0.922) | 296/347 (0.853) |

## Tier outcomes

| Arm | Tier | Outcomes (questions) |
|---|---|---|
| R5 | cypher-v2t | ANSWERED: 391, PARSE_FAILURE: 2, RETRIEVAL_ERROR: 47 |
| R5 | agent-v2t | ANSWERED: 439, PARSE_FAILURE: 1 |
| V-d0 | cypher-v2t | ANSWERED: 414, PARSE_FAILURE: 17, RETRIEVAL_ERROR: 9 |
| V-d0 | agent-v2t | ANSWERED: 439, PARSE_FAILURE: 1 |
| V-d2 | cypher-v2t | ANSWERED: 392, PARSE_FAILURE: 1, RETRIEVAL_ERROR: 47 |
| V-d2 | agent-v2t | ANSWERED: 438, PARSE_FAILURE: 2 |
| V-d4 | cypher-v2t | ANSWERED: 394, PARSE_FAILURE: 4, RETRIEVAL_ERROR: 42 |
| V-d4 | agent-v2t | ANSWERED: 438, PARSE_FAILURE: 2 |

## Notes

- Exposed means the question's k_identity is greater than 0; a missing (None) k_identity counts as unexposed.
- Accuracy and outcome counts cover the same questions (R5's headline scope).
- New spend is the sum of cost_usd over calls not served from the cache, over all questions of the run (not only the headline scope). The V arms reused R5's cache, so their figure counts only the calls R5 had not already paid for: it is not a cost per arm and must not be compared with R5's full spend.
