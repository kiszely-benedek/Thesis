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

## H100g2V

41 candidate pairs in 30 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.429 | 0.600 | [0.357, 0.788] |
| d1 | 1.000 | format | 1.000 | 0.818 | 0.900 | [0.720, 1.000] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.619 | 0.765 | [0.581, 0.897] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | 1.000 | 0.200 | 0.333 | [0.000, 0.667] |
| d4 | n/a | all | 0.947 | 0.857 | 0.900 | [0.788, 0.978] |
| d4 | n/a | format | 1.000 | 0.909 | 0.952 | [0.824, 1.000] |
| d4 | n/a | naming | 1.000 | 0.800 | 0.889 | [0.667, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.429 | 0.600 | 0 | 0 |
| d2 | 1.000 | 0.619 | 0.765 | 0 | 0 |
| d4 | 0.947 | 0.857 | 0.900 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 1 | 0 |
| d0 | class_synonym | 2 | 0 |
| d0 | drop_separator | 1 | 0 |
| d0 | spare_separator | 1 | 0 |
| d0 | split_number | 4 | 0 |
| d0 | swap_separator | 2 | 0 |
| d0 | unit_prefix | 8 | 0 |
| d0 | unpad_sequence | 2 | 0 |
| d1 | case | 1 | 1 |
| d1 | class_synonym | 2 | 0 |
| d1 | drop_separator | 1 | 1 |
| d1 | spare_separator | 1 | 1 |
| d1 | split_number | 4 | 4 |
| d1 | swap_separator | 2 | 2 |
| d1 | unit_prefix | 8 | 0 |
| d1 | unpad_sequence | 2 | 0 |
| d2 | case | 1 | 1 |
| d2 | class_synonym | 2 | 2 |
| d2 | drop_separator | 1 | 1 |
| d2 | spare_separator | 1 | 1 |
| d2 | split_number | 4 | 4 |
| d2 | swap_separator | 2 | 2 |
| d2 | unit_prefix | 8 | 0 |
| d2 | unpad_sequence | 2 | 2 |
| d4 | case | 1 | 1 |
| d4 | class_synonym | 2 | 2 |
| d4 | drop_separator | 1 | 1 |
| d4 | spare_separator | 1 | 1 |
| d4 | split_number | 4 | 4 |
| d4 | swap_separator | 2 | 2 |
| d4 | unit_prefix | 8 | 6 |
| d4 | unpad_sequence | 2 | 1 |

### Model calls

| decider | calls | cache hits | parse failures | spent USD | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 41 | 0 | 0 | 0.004883 | 4.515 | 7.985 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.600 | [0.357, 0.788] |
| d1|format | d0|format | 0.900 | [0.720, 1.000] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.765 | [0.581, 0.897] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.333 | [0.000, 0.667] |
| d2|all | d1|all | 0.165 | [0.039, 0.342] |
| d2|format | d1|format | 0.100 | [0.000, 0.280] |
| d2|naming | d1|naming | 0.333 | [0.000, 0.667] |
| d4|all | d0|all | 0.900 | [0.788, 0.978] |
| d4|format | d0|format | 0.952 | [0.824, 1.000] |
| d4|naming | d0|naming | 0.889 | [0.667, 1.000] |
| d4|all | d1|all | 0.300 | [0.121, 0.516] |
| d4|format | d1|format | 0.052 | [0.000, 0.197] |
| d4|naming | d1|naming | 0.889 | [0.667, 1.000] |
| d4|all | d2|all | 0.135 | [-0.025, 0.310] |
| d4|format | d2|format | -0.048 | [-0.176, 0.000] |
| d4|naming | d2|naming | 0.556 | [0.244, 0.933] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.900 | [0.720, 1.000] |
| d2|format | d2|naming | 0.667 | [0.333, 1.000] |
| d4|format | d4|naming | 0.063 | [-0.111, 0.286] |

## H100g2d100V

128 candidate pairs in 80 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.341 | 0.509 | [0.392, 0.619] |
| d1 | 1.000 | format | 1.000 | 0.806 | 0.892 | [0.812, 0.962] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.518 | 0.682 | [0.574, 0.768] |
| d2 | 0.857 | format | 1.000 | 0.972 | 0.986 | [0.950, 1.000] |
| d2 | 0.857 | naming | 1.000 | 0.184 | 0.310 | [0.119, 0.478] |
| d4 | n/a | all | 0.962 | 0.894 | 0.927 | [0.873, 0.970] |
| d4 | n/a | format | 1.000 | 0.917 | 0.957 | [0.899, 1.000] |
| d4 | n/a | naming | 0.977 | 0.878 | 0.925 | [0.857, 0.979] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.341 | 0.509 | 0 | 0 |
| d2 | 1.000 | 0.518 | 0.682 | 0 | 0 |
| d4 | 0.962 | 0.894 | 0.927 | 3 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 4 | 0 |
| d0 | class_synonym | 10 | 0 |
| d0 | drop_separator | 11 | 0 |
| d0 | spare_separator | 1 | 0 |
| d0 | split_number | 7 | 0 |
| d0 | swap_separator | 6 | 0 |
| d0 | unit_prefix | 39 | 0 |
| d0 | unpad_sequence | 7 | 0 |
| d1 | case | 4 | 4 |
| d1 | class_synonym | 10 | 0 |
| d1 | drop_separator | 11 | 11 |
| d1 | spare_separator | 1 | 1 |
| d1 | split_number | 7 | 7 |
| d1 | swap_separator | 6 | 6 |
| d1 | unit_prefix | 39 | 0 |
| d1 | unpad_sequence | 7 | 0 |
| d2 | case | 4 | 4 |
| d2 | class_synonym | 10 | 9 |
| d2 | drop_separator | 11 | 11 |
| d2 | spare_separator | 1 | 1 |
| d2 | split_number | 7 | 7 |
| d2 | swap_separator | 6 | 6 |
| d2 | unit_prefix | 39 | 0 |
| d2 | unpad_sequence | 7 | 6 |
| d4 | case | 4 | 4 |
| d4 | class_synonym | 10 | 10 |
| d4 | drop_separator | 11 | 11 |
| d4 | spare_separator | 1 | 1 |
| d4 | split_number | 7 | 7 |
| d4 | swap_separator | 6 | 6 |
| d4 | unit_prefix | 39 | 33 |
| d4 | unpad_sequence | 7 | 4 |

### Model calls

| decider | calls | cache hits | parse failures | spent USD | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 128 | 17 | 0 | 0.012003 | 5.703 | 9.235 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.509 | [0.392, 0.619] |
| d1|format | d0|format | 0.892 | [0.812, 0.962] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.682 | [0.574, 0.768] |
| d2|format | d0|format | 0.986 | [0.950, 1.000] |
| d2|naming | d0|naming | 0.310 | [0.119, 0.478] |
| d2|all | d1|all | 0.173 | [0.083, 0.270] |
| d2|format | d1|format | 0.094 | [0.029, 0.172] |
| d2|naming | d1|naming | 0.310 | [0.119, 0.478] |
| d4|all | d0|all | 0.927 | [0.873, 0.970] |
| d4|format | d0|format | 0.957 | [0.899, 1.000] |
| d4|naming | d0|naming | 0.925 | [0.857, 0.979] |
| d4|all | d1|all | 0.418 | [0.309, 0.531] |
| d4|format | d1|format | 0.064 | [0.013, 0.134] |
| d4|naming | d1|naming | 0.925 | [0.857, 0.979] |
| d4|all | d2|all | 0.245 | [0.152, 0.356] |
| d4|format | d2|format | -0.029 | [-0.091, 0.029] |
| d4|naming | d2|naming | 0.614 | [0.450, 0.803] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.892 | [0.812, 0.962] |
| d2|format | d2|naming | 0.676 | [0.506, 0.870] |
| d4|format | d4|naming | 0.032 | [-0.054, 0.116] |

## H1000g2V

794 candidate pairs in 349 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.430 | 0.601 | [0.537, 0.660] |
| d1 | 1.000 | format | 1.000 | 0.829 | 0.906 | [0.857, 0.946] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 0.993 | 0.626 | 0.768 | [0.716, 0.815] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | 1.000 | 0.223 | 0.365 | [0.248, 0.470] |
| d4 | n/a | all | 0.828 | 0.967 | 0.892 | [0.859, 0.920] |
| d4 | n/a | format | 0.991 | 0.946 | 0.968 | [0.940, 0.990] |
| d4 | n/a | naming | 0.990 | 0.990 | 0.990 | [0.976, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | 0.500 | 0.005 | 0.009 | 0 | 0 |
| d1 | 0.989 | 0.433 | 0.602 | 0 | 0 |
| d2 | 0.985 | 0.628 | 0.767 | 1 | 0 |
| d4 | 0.825 | 0.967 | 0.891 | 13 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 17 | 0 |
| d0 | class_synonym | 26 | 0 |
| d0 | drop_separator | 25 | 0 |
| d0 | spare_separator | 2 | 0 |
| d0 | split_number | 24 | 0 |
| d0 | swap_separator | 25 | 0 |
| d0 | unit_prefix | 77 | 0 |
| d0 | unpad_sequence | 18 | 0 |
| d1 | case | 17 | 17 |
| d1 | class_synonym | 26 | 0 |
| d1 | drop_separator | 25 | 24 |
| d1 | spare_separator | 2 | 2 |
| d1 | split_number | 24 | 24 |
| d1 | swap_separator | 25 | 25 |
| d1 | unit_prefix | 77 | 0 |
| d1 | unpad_sequence | 18 | 0 |
| d2 | case | 17 | 17 |
| d2 | class_synonym | 26 | 23 |
| d2 | drop_separator | 25 | 25 |
| d2 | spare_separator | 2 | 2 |
| d2 | split_number | 24 | 24 |
| d2 | swap_separator | 25 | 25 |
| d2 | unit_prefix | 77 | 0 |
| d2 | unpad_sequence | 18 | 18 |
| d4 | case | 17 | 17 |
| d4 | class_synonym | 26 | 26 |
| d4 | drop_separator | 25 | 25 |
| d4 | spare_separator | 2 | 2 |
| d4 | split_number | 24 | 24 |
| d4 | swap_separator | 25 | 25 |
| d4 | unit_prefix | 77 | 76 |
| d4 | unpad_sequence | 18 | 12 |

### Model calls

| decider | calls | cache hits | parse failures | spent USD | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 794 | 780 | 0 | 0.001085 | 3.469 | 6.407 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.601 | [0.537, 0.660] |
| d1|format | d0|format | 0.906 | [0.857, 0.946] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.768 | [0.716, 0.815] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.365 | [0.248, 0.470] |
| d2|all | d1|all | 0.167 | [0.122, 0.217] |
| d2|format | d1|format | 0.094 | [0.054, 0.143] |
| d2|naming | d1|naming | 0.365 | [0.248, 0.470] |
| d4|all | d0|all | 0.892 | [0.859, 0.920] |
| d4|format | d0|format | 0.968 | [0.940, 0.990] |
| d4|naming | d0|naming | 0.990 | [0.976, 1.000] |
| d4|all | d1|all | 0.291 | [0.225, 0.359] |
| d4|format | d1|format | 0.061 | [0.024, 0.105] |
| d4|naming | d1|naming | 0.990 | [0.976, 1.000] |
| d4|all | d2|all | 0.124 | [0.067, 0.185] |
| d4|format | d2|format | -0.032 | [-0.060, -0.010] |
| d4|naming | d2|naming | 0.625 | [0.521, 0.740] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.906 | [0.857, 0.946] |
| d2|format | d2|naming | 0.635 | [0.530, 0.752] |
| d4|format | d4|naming | -0.023 | [-0.052, 0.002] |

## H1000g2d100V

1923 candidate pairs in 779 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 0.997 | 0.372 | 0.542 | [0.505, 0.576] |
| d1 | 1.000 | format | 0.997 | 0.773 | 0.871 | [0.843, 0.895] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 0.992 | 0.585 | 0.736 | [0.709, 0.763] |
| d2 | 0.857 | format | 0.995 | 0.990 | 0.993 | [0.985, 0.999] |
| d2 | 0.857 | naming | 1.000 | 0.210 | 0.347 | [0.291, 0.400] |
| d4 | n/a | all | 0.938 | 0.962 | 0.950 | [0.936, 0.962] |
| d4 | n/a | format | 0.980 | 0.945 | 0.962 | [0.947, 0.975] |
| d4 | n/a | naming | 0.989 | 0.978 | 0.983 | [0.973, 0.992] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | 0.500 | 0.002 | 0.005 | 0 | 0 |
| d1 | 0.991 | 0.373 | 0.542 | 0 | 0 |
| d2 | 0.988 | 0.586 | 0.736 | 11 | 0 |
| d4 | 0.936 | 0.962 | 0.949 | 33 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 63 | 0 |
| d0 | class_synonym | 110 | 0 |
| d0 | drop_separator | 69 | 0 |
| d0 | spare_separator | 15 | 0 |
| d0 | split_number | 83 | 0 |
| d0 | swap_separator | 95 | 0 |
| d0 | unit_prefix | 338 | 0 |
| d0 | unpad_sequence | 90 | 0 |
| d1 | case | 63 | 62 |
| d1 | class_synonym | 110 | 0 |
| d1 | drop_separator | 69 | 68 |
| d1 | spare_separator | 15 | 15 |
| d1 | split_number | 83 | 83 |
| d1 | swap_separator | 95 | 93 |
| d1 | unit_prefix | 338 | 0 |
| d1 | unpad_sequence | 90 | 0 |
| d2 | case | 63 | 62 |
| d2 | class_synonym | 110 | 92 |
| d2 | drop_separator | 69 | 69 |
| d2 | spare_separator | 15 | 15 |
| d2 | split_number | 83 | 83 |
| d2 | swap_separator | 95 | 93 |
| d2 | unit_prefix | 338 | 2 |
| d2 | unpad_sequence | 90 | 89 |
| d4 | case | 63 | 63 |
| d4 | class_synonym | 110 | 110 |
| d4 | drop_separator | 69 | 69 |
| d4 | spare_separator | 15 | 15 |
| d4 | split_number | 83 | 83 |
| d4 | swap_separator | 95 | 95 |
| d4 | unit_prefix | 338 | 328 |
| d4 | unpad_sequence | 90 | 67 |

### Model calls

| decider | calls | cache hits | parse failures | spent USD | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 1923 | 529 | 0 | 0.148069 | 3.813 | 6.812 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.542 | [0.505, 0.576] |
| d1|format | d0|format | 0.871 | [0.843, 0.895] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.736 | [0.709, 0.763] |
| d2|format | d0|format | 0.993 | [0.985, 0.999] |
| d2|naming | d0|naming | 0.347 | [0.291, 0.400] |
| d2|all | d1|all | 0.194 | [0.170, 0.222] |
| d2|format | d1|format | 0.122 | [0.097, 0.149] |
| d2|naming | d1|naming | 0.347 | [0.291, 0.400] |
| d4|all | d0|all | 0.950 | [0.936, 0.962] |
| d4|format | d0|format | 0.962 | [0.947, 0.975] |
| d4|naming | d0|naming | 0.983 | [0.973, 0.992] |
| d4|all | d1|all | 0.408 | [0.372, 0.446] |
| d4|format | d1|format | 0.091 | [0.067, 0.116] |
| d4|naming | d1|naming | 0.983 | [0.973, 0.992] |
| d4|all | d2|all | 0.214 | [0.183, 0.244] |
| d4|format | d2|format | -0.031 | [-0.047, -0.016] |
| d4|naming | d2|naming | 0.636 | [0.583, 0.691] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.871 | [0.843, 0.895] |
| d2|format | d2|naming | 0.646 | [0.591, 0.702] |
| d4|format | d4|naming | -0.021 | [-0.038, -0.005] |

