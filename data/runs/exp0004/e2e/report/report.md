# EXP-0004 end-to-end report

System: `cascade_v4_iso`, accuracy at the 120 s cutoff (acc@cutoff), 440 questions per arm, paired by question id.

## Pre-registered claims

| Claim | Difference | Estimate [95% CI] | Pass if | Verdict |
|---|---|---|---|---|
| E1 | acc(V,D0) - acc(R5) | -0.125 [-0.1590909090909091, -0.09090909090909091] | CI upper < 0 | PASS |
| E2 | acc(V,D2) - acc(V,D0) | 0.09318181818181819 [0.06363636363636363, 0.12272727272727273] | CI lower > 0 | PASS |
| E3 | acc(V,D4) - acc(V,D0) | 0.031818181818181815 [-0.004545454545454545, 0.06818181818181818] | CI lower > 0 | FAIL |
| E4 (D2) | acc(V,D2) - acc(R5) | -0.031818181818181815 [-0.05454545454545454, -0.00909090909090909] | CI lower > -0.03 | FAIL |
| E4 (D4) | acc(V,D4) - acc(R5) | -0.09318181818181819 [-0.125, -0.06363636363636363] | CI lower > -0.03 | FAIL |

## Accuracy per arm

| Arm | n | correct@cutoff | acc@cutoff (Wilson 95% CI) | Spend USD |
|---|---|---|---|---|
| R5 | 440 | 392 | 0.8909090909090909 [0.858325280849923, 0.9167259987056661] | 1.3735 |
| V-d0 | 440 | 337 | 0.7659090909090909 [0.7241470280156859, 0.8030680865657323] | 0.5730 |
| V-d2 | 440 | 378 | 0.8590909090909091 [0.8234648430880099, 0.8885008672014266] | 0.5366 |
| V-d4 | 440 | 351 | 0.7977272727272727 [0.7576903229960563, 0.8326103608515145] | 0.8351 |

## Accuracy per question family (correct/n)

| Family | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| CONNECTED | 19/20 (0.95) | 15/20 (0.75) | 18/20 (0.9) | 19/20 (0.95) |
| COUNT_IN_UNIT | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| CROSS_UNIT | 20/20 (1.0) | 19/20 (0.95) | 19/20 (0.95) | 19/20 (0.95) |
| DOWNSTREAM_IN_UNIT | 17/20 (0.85) | 9/20 (0.45) | 16/20 (0.8) | 6/20 (0.3) |
| DOWNSTREAM_ISOLATION | 2/20 (0.1) | 1/20 (0.05) | 2/20 (0.1) | 1/20 (0.05) |
| FEEDING_UNITS | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| FLOW_PATH | 14/20 (0.7) | 13/20 (0.65) | 15/20 (0.75) | 12/20 (0.6) |
| INSTRUMENTS_OF_ITEM | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| LOOKUP_TYPE | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| LOOKUP_UNIT | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| LOOPS_NEAR_ITEM | 18/20 (0.9) | 16/20 (0.8) | 16/20 (0.8) | 18/20 (0.9) |
| LOOP_MEASURED_EQUIPMENT | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| NEIGHBOURS_DOWNSTREAM | 20/20 (1.0) | 15/20 (0.75) | 18/20 (0.9) | 19/20 (0.95) |
| NO_PATH | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 7/20 (0.35) |
| ROUTE_AVOIDING | 19/20 (0.95) | 16/20 (0.8) | 17/20 (0.85) | 19/20 (0.95) |
| SAME_UNIT | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 19/20 (0.95) |
| SHEETS_OF_TAG | 20/20 (1.0) | 9/20 (0.45) | 16/20 (0.8) | 20/20 (1.0) |
| UNANSWERABLE_TAG | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) | 20/20 (1.0) |
| UNITS_REACHED | 20/20 (1.0) | 11/20 (0.55) | 18/20 (0.9) | 16/20 (0.8) |
| UPSTREAM_ISOLATION | 10/20 (0.5) | 10/20 (0.5) | 13/20 (0.65) | 10/20 (0.5) |
| UPSTREAM_SOURCES | 20/20 (1.0) | 12/20 (0.6) | 18/20 (0.9) | 14/20 (0.7) |
| VALVES_ON_PATH | 13/20 (0.65) | 11/20 (0.55) | 12/20 (0.6) | 12/20 (0.6) |

## Exposed vs unexposed (correct/n)

| Group | R5 | V-d0 | V-d2 | V-d4 |
|---|---|---|---|---|
| exposed (k_identity > 0) | 74/93 (0.7956989247311828) | 21/93 (0.22580645161290322) | 58/93 (0.6236559139784946) | 55/93 (0.5913978494623656) |
| unexposed (k_identity = 0 or None) | 318/347 (0.9164265129682997) | 316/347 (0.9106628242074928) | 320/347 (0.9221902017291066) | 296/347 (0.8530259365994236) |

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
- Spend is the sum of cost_usd over calls not served from the cache, over all questions of the run (not only the headline scope).
