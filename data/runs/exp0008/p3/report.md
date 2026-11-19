## H100g21p1V

35 candidate pairs in 21 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.125 | 0.222 | [0.000, 0.571] |
| d1 | 1.000 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.125 | 0.222 | [0.000, 0.571] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.700 | 0.875 | 0.778 | [0.500, 0.952] |
| d4 | n/a | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d4 | n/a | naming | 1.000 | 0.857 | 0.923 | [0.667, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.125 | 0.222 | 0 | 0 |
| d2 | 1.000 | 0.125 | 0.222 | 0 | 0 |
| d4 | 0.700 | 0.875 | 0.778 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | drop_separator | 1 | 0 |
| d0 | unit_prefix | 7 | 0 |
| d1 | drop_separator | 1 | 1 |
| d1 | unit_prefix | 7 | 0 |
| d2 | drop_separator | 1 | 1 |
| d2 | unit_prefix | 7 | 0 |
| d4 | drop_separator | 1 | 1 |
| d4 | unit_prefix | 7 | 6 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 35 | 0 | 0 | 0.004901 | 3.765 | 6.797 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.222 | [0.000, 0.571] |
| d1|format | d0|format | 1.000 | [1.000, 1.000] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.222 | [0.000, 0.571] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.000 | [0.000, 0.000] |
| d2|format | d1|format | 0.000 | [0.000, 0.000] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.778 | [0.500, 0.952] |
| d4|format | d0|format | 1.000 | [1.000, 1.000] |
| d4|naming | d0|naming | 0.923 | [0.667, 1.000] |
| d4|all | d1|all | 0.556 | [0.143, 0.889] |
| d4|format | d1|format | 0.000 | [0.000, 0.000] |
| d4|naming | d1|naming | 0.923 | [0.667, 1.000] |
| d4|all | d2|all | 0.556 | [0.143, 0.889] |
| d4|format | d2|format | 0.000 | [0.000, 0.000] |
| d4|naming | d2|naming | 0.923 | [0.667, 1.000] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 1.000 | [1.000, 1.000] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | 0.077 | [0.000, 0.333] |

## H100g21p1d100V

60 candidate pairs in 46 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.273 | 0.429 | [0.229, 0.600] |
| d1 | 1.000 | format | 1.000 | 0.818 | 0.900 | [0.706, 1.000] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.333 | 0.500 | [0.308, 0.667] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.906 | 0.879 | 0.892 | [0.800, 0.964] |
| d4 | n/a | format | 1.000 | 0.818 | 0.900 | [0.706, 1.000] |
| d4 | n/a | naming | 1.000 | 0.909 | 0.952 | [0.875, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.273 | 0.429 | 0 | 0 |
| d2 | 1.000 | 0.333 | 0.500 | 0 | 0 |
| d4 | 0.906 | 0.879 | 0.892 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 1 | 0 |
| d0 | class_synonym | 1 | 0 |
| d0 | drop_separator | 3 | 0 |
| d0 | split_number | 3 | 0 |
| d0 | swap_separator | 2 | 0 |
| d0 | unit_prefix | 21 | 0 |
| d0 | unpad_sequence | 2 | 0 |
| d1 | case | 1 | 1 |
| d1 | class_synonym | 1 | 0 |
| d1 | drop_separator | 3 | 3 |
| d1 | split_number | 3 | 3 |
| d1 | swap_separator | 2 | 2 |
| d1 | unit_prefix | 21 | 0 |
| d1 | unpad_sequence | 2 | 0 |
| d2 | case | 1 | 1 |
| d2 | class_synonym | 1 | 0 |
| d2 | drop_separator | 3 | 3 |
| d2 | split_number | 3 | 3 |
| d2 | swap_separator | 2 | 2 |
| d2 | unit_prefix | 21 | 0 |
| d2 | unpad_sequence | 2 | 2 |
| d4 | case | 1 | 1 |
| d4 | class_synonym | 1 | 1 |
| d4 | drop_separator | 3 | 3 |
| d4 | split_number | 3 | 3 |
| d4 | swap_separator | 2 | 2 |
| d4 | unit_prefix | 21 | 19 |
| d4 | unpad_sequence | 2 | 0 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 60 | 33 | 0 | 0.007521 | 3.672 | 6.032 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.429 | [0.229, 0.600] |
| d1|format | d0|format | 0.900 | [0.706, 1.000] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.500 | [0.308, 0.667] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.071 | [0.000, 0.187] |
| d2|format | d1|format | 0.100 | [0.000, 0.294] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.892 | [0.800, 0.964] |
| d4|format | d0|format | 0.900 | [0.706, 1.000] |
| d4|naming | d0|naming | 0.952 | [0.875, 1.000] |
| d4|all | d1|all | 0.464 | [0.287, 0.658] |
| d4|format | d1|format | 0.000 | [0.000, 0.000] |
| d4|naming | d1|naming | 0.952 | [0.875, 1.000] |
| d4|all | d2|all | 0.392 | [0.191, 0.606] |
| d4|format | d2|format | -0.100 | [-0.294, 0.000] |
| d4|naming | d2|naming | 0.952 | [0.875, 1.000] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.900 | [0.706, 1.000] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | -0.052 | [-0.239, 0.081] |

## H1000g21p1V

501 candidate pairs in 261 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.326 | 0.492 | [0.376, 0.595] |
| d1 | 1.000 | format | 1.000 | 0.744 | 0.853 | [0.746, 0.935] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.438 | 0.609 | [0.500, 0.700] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.637 | 0.966 | 0.768 | [0.706, 0.826] |
| d4 | n/a | format | 0.973 | 0.923 | 0.947 | [0.889, 0.988] |
| d4 | n/a | naming | 0.980 | 1.000 | 0.990 | [0.968, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.326 | 0.492 | 0 | 0 |
| d2 | 1.000 | 0.438 | 0.609 | 2 | 0 |
| d4 | 0.637 | 0.966 | 0.768 | 1 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 8 | 0 |
| d0 | class_synonym | 7 | 0 |
| d0 | drop_separator | 6 | 0 |
| d0 | split_number | 12 | 0 |
| d0 | swap_separator | 3 | 0 |
| d0 | unit_prefix | 43 | 0 |
| d0 | unpad_sequence | 10 | 0 |
| d1 | case | 8 | 8 |
| d1 | class_synonym | 7 | 0 |
| d1 | drop_separator | 6 | 6 |
| d1 | split_number | 12 | 12 |
| d1 | swap_separator | 3 | 3 |
| d1 | unit_prefix | 43 | 0 |
| d1 | unpad_sequence | 10 | 0 |
| d2 | case | 8 | 8 |
| d2 | class_synonym | 7 | 0 |
| d2 | drop_separator | 6 | 6 |
| d2 | split_number | 12 | 12 |
| d2 | swap_separator | 3 | 3 |
| d2 | unit_prefix | 43 | 0 |
| d2 | unpad_sequence | 10 | 10 |
| d4 | case | 8 | 8 |
| d4 | class_synonym | 7 | 7 |
| d4 | drop_separator | 6 | 6 |
| d4 | split_number | 12 | 12 |
| d4 | swap_separator | 3 | 3 |
| d4 | unit_prefix | 43 | 43 |
| d4 | unpad_sequence | 10 | 7 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 501 | 0 | 0 | 0.058656 | 3.797 | 6.969 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.492 | [0.376, 0.595] |
| d1|format | d0|format | 0.853 | [0.746, 0.935] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.609 | [0.500, 0.700] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.118 | [0.052, 0.193] |
| d2|format | d1|format | 0.147 | [0.065, 0.254] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.768 | [0.706, 0.826] |
| d4|format | d0|format | 0.947 | [0.889, 0.988] |
| d4|naming | d0|naming | 0.990 | [0.968, 1.000] |
| d4|all | d1|all | 0.276 | [0.155, 0.402] |
| d4|format | d1|format | 0.094 | [0.030, 0.182] |
| d4|naming | d1|naming | 0.990 | [0.968, 1.000] |
| d4|all | d2|all | 0.158 | [0.043, 0.279] |
| d4|format | d2|format | -0.053 | [-0.111, -0.012] |
| d4|naming | d2|naming | 0.990 | [0.968, 1.000] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.853 | [0.746, 0.935] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | -0.043 | [-0.104, 0.007] |

## H1000g21p1d100V

830 candidate pairs in 495 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.420 | 0.591 | [0.537, 0.642] |
| d1 | 1.000 | format | 1.000 | 0.819 | 0.900 | [0.862, 0.933] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.513 | 0.678 | [0.629, 0.722] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.844 | 0.961 | 0.899 | [0.873, 0.923] |
| d4 | n/a | format | 0.966 | 0.934 | 0.950 | [0.925, 0.971] |
| d4 | n/a | naming | 0.945 | 0.988 | 0.966 | [0.941, 0.985] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.420 | 0.591 | 0 | 0 |
| d2 | 1.000 | 0.513 | 0.678 | 5 | 0 |
| d4 | 0.844 | 0.961 | 0.899 | 4 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 43 | 0 |
| d0 | class_synonym | 16 | 0 |
| d0 | drop_separator | 33 | 0 |
| d0 | spare_separator | 1 | 0 |
| d0 | split_number | 42 | 0 |
| d0 | swap_separator | 30 | 0 |
| d0 | unit_prefix | 157 | 0 |
| d0 | unpad_sequence | 33 | 0 |
| d1 | case | 43 | 43 |
| d1 | class_synonym | 16 | 0 |
| d1 | drop_separator | 33 | 33 |
| d1 | spare_separator | 1 | 1 |
| d1 | split_number | 42 | 42 |
| d1 | swap_separator | 30 | 30 |
| d1 | unit_prefix | 157 | 0 |
| d1 | unpad_sequence | 33 | 0 |
| d2 | case | 43 | 43 |
| d2 | class_synonym | 16 | 0 |
| d2 | drop_separator | 33 | 33 |
| d2 | spare_separator | 1 | 1 |
| d2 | split_number | 42 | 42 |
| d2 | swap_separator | 30 | 30 |
| d2 | unit_prefix | 157 | 0 |
| d2 | unpad_sequence | 33 | 33 |
| d4 | case | 43 | 43 |
| d4 | class_synonym | 16 | 16 |
| d4 | drop_separator | 33 | 33 |
| d4 | spare_separator | 1 | 1 |
| d4 | split_number | 42 | 42 |
| d4 | swap_separator | 30 | 30 |
| d4 | unit_prefix | 157 | 155 |
| d4 | unpad_sequence | 33 | 21 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 830 | 473 | 0 | 0.090452 | 3.656 | 6.734 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.591 | [0.537, 0.642] |
| d1|format | d0|format | 0.900 | [0.862, 0.933] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.678 | [0.629, 0.722] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.087 | [0.059, 0.118] |
| d2|format | d1|format | 0.100 | [0.067, 0.138] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.899 | [0.873, 0.923] |
| d4|format | d0|format | 0.950 | [0.925, 0.971] |
| d4|naming | d0|naming | 0.966 | [0.941, 0.985] |
| d4|all | d1|all | 0.307 | [0.253, 0.362] |
| d4|format | d1|format | 0.049 | [0.022, 0.081] |
| d4|naming | d1|naming | 0.966 | [0.941, 0.985] |
| d4|all | d2|all | 0.221 | [0.167, 0.276] |
| d4|format | d2|format | -0.050 | [-0.075, -0.029] |
| d4|naming | d2|naming | 0.966 | [0.941, 0.985] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.900 | [0.862, 0.933] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | -0.016 | [-0.048, 0.016] |

