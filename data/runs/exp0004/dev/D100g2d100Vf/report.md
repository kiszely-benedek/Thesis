## D100g2d100Vf

200 candidate pairs in 84 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.828 | 0.906 | [0.855, 0.947] |
| d1 | 1.000 | format | 1.000 | 0.828 | 0.906 | [0.855, 0.947] |
| d2 | 0.857 | all | 0.979 | 0.989 | 0.984 | [0.957, 1.000] |
| d2 | 0.857 | format | 1.000 | 0.989 | 0.995 | [0.982, 1.000] |
| d4 | n/a | all | 0.895 | 0.914 | 0.904 | [0.849, 0.951] |
| d4 | n/a | format | 0.966 | 0.914 | 0.939 | [0.897, 0.975] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | 0.000 | 0.000 | n/a | 0 | 0 |
| d1 | 0.975 | 0.828 | 0.895 | 0 | 0 |
| d2 | 0.958 | 0.989 | 0.974 | 0 | 0 |
| d4 | 0.876 | 0.914 | 0.895 | 4 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 18 | 0 |
| d0 | drop_separator | 16 | 0 |
| d0 | spare_separator | 3 | 0 |
| d0 | split_number | 19 | 0 |
| d0 | swap_separator | 21 | 0 |
| d0 | unpad_sequence | 16 | 0 |
| d1 | case | 18 | 18 |
| d1 | drop_separator | 16 | 16 |
| d1 | spare_separator | 3 | 3 |
| d1 | split_number | 19 | 19 |
| d1 | swap_separator | 21 | 21 |
| d1 | unpad_sequence | 16 | 0 |
| d2 | case | 18 | 18 |
| d2 | drop_separator | 16 | 16 |
| d2 | spare_separator | 3 | 3 |
| d2 | split_number | 19 | 19 |
| d2 | swap_separator | 21 | 21 |
| d2 | unpad_sequence | 16 | 15 |
| d4 | case | 18 | 18 |
| d4 | drop_separator | 16 | 16 |
| d4 | spare_separator | 3 | 3 |
| d4 | split_number | 19 | 19 |
| d4 | swap_separator | 21 | 21 |
| d4 | unpad_sequence | 16 | 8 |

### Model calls

| decider | calls | cache hits | parse failures | spent USD | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 200 | 20 | 0 | 0.018853 | 3.594 | 6.703 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.906 | [0.855, 0.947] |
| d1|format | d0|format | 0.906 | [0.855, 0.947] |
| d2|all | d0|all | 0.984 | [0.957, 1.000] |
| d2|format | d0|format | 0.995 | [0.982, 1.000] |
| d2|all | d1|all | 0.078 | [0.042, 0.123] |
| d2|format | d1|format | 0.089 | [0.051, 0.135] |
| d4|all | d0|all | 0.904 | [0.849, 0.951] |
| d4|format | d0|format | 0.939 | [0.897, 0.975] |
| d4|all | d1|all | -0.002 | [-0.045, 0.040] |
| d4|format | d1|format | 0.033 | [0.005, 0.068] |
| d4|all | d2|all | -0.080 | [-0.127, -0.039] |
| d4|format | d2|format | -0.055 | [-0.093, -0.023] |

