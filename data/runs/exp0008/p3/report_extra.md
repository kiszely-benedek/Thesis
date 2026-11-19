## H1000g21p2V

452 candidate pairs in 257 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.360 | 0.530 | [0.414, 0.637] |
| d1 | 1.000 | format | 1.000 | 0.738 | 0.849 | [0.755, 0.929] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.488 | 0.656 | [0.550, 0.746] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.654 | 0.965 | 0.779 | [0.716, 0.839] |
| d4 | n/a | format | 0.951 | 0.929 | 0.940 | [0.889, 0.987] |
| d4 | n/a | naming | 0.936 | 1.000 | 0.967 | [0.932, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.360 | 0.530 | 0 | 0 |
| d2 | 1.000 | 0.488 | 0.656 | 2 | 0 |
| d4 | 0.654 | 0.965 | 0.779 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 9 | 0 |
| d0 | class_synonym | 2 | 0 |
| d0 | drop_separator | 4 | 0 |
| d0 | split_number | 6 | 0 |
| d0 | swap_separator | 12 | 0 |
| d0 | unit_prefix | 42 | 0 |
| d0 | unpad_sequence | 11 | 0 |
| d1 | case | 9 | 9 |
| d1 | class_synonym | 2 | 0 |
| d1 | drop_separator | 4 | 4 |
| d1 | split_number | 6 | 6 |
| d1 | swap_separator | 12 | 12 |
| d1 | unit_prefix | 42 | 0 |
| d1 | unpad_sequence | 11 | 0 |
| d2 | case | 9 | 9 |
| d2 | class_synonym | 2 | 0 |
| d2 | drop_separator | 4 | 4 |
| d2 | split_number | 6 | 6 |
| d2 | swap_separator | 12 | 12 |
| d2 | unit_prefix | 42 | 0 |
| d2 | unpad_sequence | 11 | 11 |
| d4 | case | 9 | 9 |
| d4 | class_synonym | 2 | 2 |
| d4 | drop_separator | 4 | 4 |
| d4 | split_number | 6 | 6 |
| d4 | swap_separator | 12 | 12 |
| d4 | unit_prefix | 42 | 42 |
| d4 | unpad_sequence | 11 | 8 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 452 | 0 | 0 | 0.054214 | 3.641 | 7.079 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.530 | [0.414, 0.637] |
| d1|format | d0|format | 0.849 | [0.755, 0.929] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.656 | [0.550, 0.746] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.126 | [0.061, 0.199] |
| d2|format | d1|format | 0.151 | [0.071, 0.245] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.779 | [0.716, 0.839] |
| d4|format | d0|format | 0.940 | [0.889, 0.987] |
| d4|naming | d0|naming | 0.967 | [0.932, 1.000] |
| d4|all | d1|all | 0.249 | [0.127, 0.377] |
| d4|format | d1|format | 0.090 | [0.014, 0.186] |
| d4|naming | d1|naming | 0.967 | [0.932, 1.000] |
| d4|all | d2|all | 0.123 | [0.017, 0.244] |
| d4|format | d2|format | -0.060 | [-0.111, -0.013] |
| d4|naming | d2|naming | 0.967 | [0.932, 1.000] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.849 | [0.755, 0.929] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | -0.027 | [-0.090, 0.033] |

## H1000g21p3V

491 candidate pairs in 258 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.413 | 0.585 | [0.477, 0.677] |
| d1 | 1.000 | format | 1.000 | 0.776 | 0.874 | [0.787, 0.940] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.533 | 0.695 | [0.607, 0.777] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.629 | 0.978 | 0.766 | [0.704, 0.825] |
| d4 | n/a | format | 0.922 | 0.959 | 0.940 | [0.892, 0.980] |
| d4 | n/a | naming | 0.935 | 1.000 | 0.966 | [0.923, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.413 | 0.585 | 0 | 0 |
| d2 | 1.000 | 0.533 | 0.695 | 2 | 0 |
| d4 | 0.629 | 0.978 | 0.766 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 11 | 0 |
| d0 | class_synonym | 4 | 0 |
| d0 | drop_separator | 6 | 0 |
| d0 | spare_separator | 1 | 0 |
| d0 | split_number | 11 | 0 |
| d0 | swap_separator | 9 | 0 |
| d0 | unit_prefix | 39 | 0 |
| d0 | unpad_sequence | 11 | 0 |
| d1 | case | 11 | 11 |
| d1 | class_synonym | 4 | 0 |
| d1 | drop_separator | 6 | 6 |
| d1 | spare_separator | 1 | 1 |
| d1 | split_number | 11 | 11 |
| d1 | swap_separator | 9 | 9 |
| d1 | unit_prefix | 39 | 0 |
| d1 | unpad_sequence | 11 | 0 |
| d2 | case | 11 | 11 |
| d2 | class_synonym | 4 | 0 |
| d2 | drop_separator | 6 | 6 |
| d2 | spare_separator | 1 | 1 |
| d2 | split_number | 11 | 11 |
| d2 | swap_separator | 9 | 9 |
| d2 | unit_prefix | 39 | 0 |
| d2 | unpad_sequence | 11 | 11 |
| d4 | case | 11 | 11 |
| d4 | class_synonym | 4 | 4 |
| d4 | drop_separator | 6 | 6 |
| d4 | spare_separator | 1 | 1 |
| d4 | split_number | 11 | 11 |
| d4 | swap_separator | 9 | 9 |
| d4 | unit_prefix | 39 | 39 |
| d4 | unpad_sequence | 11 | 9 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 491 | 0 | 0 | 0.055248 | 3.718 | 7.078 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.585 | [0.477, 0.677] |
| d1|format | d0|format | 0.874 | [0.787, 0.940] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.695 | [0.607, 0.777] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.110 | [0.053, 0.181] |
| d2|format | d1|format | 0.126 | [0.060, 0.213] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.766 | [0.704, 0.825] |
| d4|format | d0|format | 0.940 | [0.892, 0.980] |
| d4|naming | d0|naming | 0.966 | [0.923, 1.000] |
| d4|all | d1|all | 0.181 | [0.066, 0.308] |
| d4|format | d1|format | 0.066 | [-0.009, 0.156] |
| d4|naming | d1|naming | 0.966 | [0.923, 1.000] |
| d4|all | d2|all | 0.071 | [-0.032, 0.180] |
| d4|format | d2|format | -0.060 | [-0.108, -0.020] |
| d4|naming | d2|naming | 0.966 | [0.923, 1.000] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.874 | [0.787, 0.940] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | -0.026 | [-0.085, 0.031] |

## H1000g21p4V

483 candidate pairs in 250 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.413 | 0.585 | [0.478, 0.683] |
| d1 | 1.000 | format | 1.000 | 0.844 | 0.916 | [0.846, 0.968] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.489 | 0.657 | [0.561, 0.742] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.599 | 0.989 | 0.746 | [0.681, 0.804] |
| d4 | n/a | format | 0.918 | 1.000 | 0.957 | [0.917, 0.990] |
| d4 | n/a | naming | 0.902 | 0.979 | 0.939 | [0.891, 0.979] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.413 | 0.585 | 0 | 0 |
| d2 | 1.000 | 0.489 | 0.657 | 1 | 0 |
| d4 | 0.599 | 0.989 | 0.746 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 13 | 0 |
| d0 | class_synonym | 4 | 0 |
| d0 | drop_separator | 6 | 0 |
| d0 | split_number | 12 | 0 |
| d0 | swap_separator | 7 | 0 |
| d0 | unit_prefix | 43 | 0 |
| d0 | unpad_sequence | 7 | 0 |
| d1 | case | 13 | 13 |
| d1 | class_synonym | 4 | 0 |
| d1 | drop_separator | 6 | 6 |
| d1 | split_number | 12 | 12 |
| d1 | swap_separator | 7 | 7 |
| d1 | unit_prefix | 43 | 0 |
| d1 | unpad_sequence | 7 | 0 |
| d2 | case | 13 | 13 |
| d2 | class_synonym | 4 | 0 |
| d2 | drop_separator | 6 | 6 |
| d2 | split_number | 12 | 12 |
| d2 | swap_separator | 7 | 7 |
| d2 | unit_prefix | 43 | 0 |
| d2 | unpad_sequence | 7 | 7 |
| d4 | case | 13 | 13 |
| d4 | class_synonym | 4 | 4 |
| d4 | drop_separator | 6 | 6 |
| d4 | split_number | 12 | 12 |
| d4 | swap_separator | 7 | 7 |
| d4 | unit_prefix | 43 | 42 |
| d4 | unpad_sequence | 7 | 7 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 483 | 0 | 0 | 0.057173 | 3.672 | 6.703 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.585 | [0.478, 0.683] |
| d1|format | d0|format | 0.916 | [0.846, 0.968] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.657 | [0.561, 0.742] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.072 | [0.028, 0.128] |
| d2|format | d1|format | 0.084 | [0.032, 0.154] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.746 | [0.681, 0.804] |
| d4|format | d0|format | 0.957 | [0.917, 0.990] |
| d4|naming | d0|naming | 0.939 | [0.891, 0.979] |
| d4|all | d1|all | 0.161 | [0.045, 0.281] |
| d4|format | d1|format | 0.042 | [-0.028, 0.126] |
| d4|naming | d1|naming | 0.939 | [0.891, 0.979] |
| d4|all | d2|all | 0.089 | [-0.020, 0.196] |
| d4|format | d2|format | -0.043 | [-0.083, -0.010] |
| d4|naming | d2|naming | 0.939 | [0.891, 0.979] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.916 | [0.846, 0.968] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | 0.019 | [-0.038, 0.077] |

## H1000g21p5V

526 candidate pairs in 279 blocks; 95 % intervals from 2000 block resamples (seed 20261104).

### Pair level (candidate set, after grouping)

| decider | tau | subset | P | R | F1 | F1 95 % CI |
|---|---|---|---|---|---|---|
| d0 | n/a | all | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | format | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d0 | n/a | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d1 | 1.000 | all | 1.000 | 0.391 | 0.562 | [0.446, 0.662] |
| d1 | 1.000 | format | 1.000 | 0.818 | 0.900 | [0.824, 0.960] |
| d1 | 1.000 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d2 | 0.857 | all | 1.000 | 0.478 | 0.647 | [0.541, 0.739] |
| d2 | 0.857 | format | 1.000 | 1.000 | 1.000 | [1.000, 1.000] |
| d2 | 0.857 | naming | n/a | 0.000 | 0.000 | [0.000, 0.000] |
| d4 | n/a | all | 0.643 | 0.978 | 0.776 | [0.709, 0.836] |
| d4 | n/a | format | 0.956 | 0.977 | 0.966 | [0.929, 1.000] |
| d4 | n/a | naming | 0.959 | 0.979 | 0.969 | [0.931, 1.000] |

### Group level (`score_identity_groups`)

| decider | P | R | F1 | dropped one-to-one | identity conflicts |
|---|---|---|---|---|---|
| d0 | n/a | 0.000 | n/a | 0 | 0 |
| d1 | 1.000 | 0.391 | 0.562 | 0 | 0 |
| d2 | 1.000 | 0.478 | 0.647 | 2 | 0 |
| d4 | 0.643 | 0.978 | 0.776 | 0 | 0 |

### Recovered gold pairs per operator (descriptive)

| decider | operator | gold | recovered |
|---|---|---|---|
| d0 | case | 8 | 0 |
| d0 | class_synonym | 6 | 0 |
| d0 | drop_separator | 9 | 0 |
| d0 | split_number | 7 | 0 |
| d0 | swap_separator | 12 | 0 |
| d0 | unit_prefix | 42 | 0 |
| d0 | unpad_sequence | 8 | 0 |
| d1 | case | 8 | 8 |
| d1 | class_synonym | 6 | 0 |
| d1 | drop_separator | 9 | 9 |
| d1 | split_number | 7 | 7 |
| d1 | swap_separator | 12 | 12 |
| d1 | unit_prefix | 42 | 0 |
| d1 | unpad_sequence | 8 | 0 |
| d2 | case | 8 | 8 |
| d2 | class_synonym | 6 | 0 |
| d2 | drop_separator | 9 | 9 |
| d2 | split_number | 7 | 7 |
| d2 | swap_separator | 12 | 12 |
| d2 | unit_prefix | 42 | 0 |
| d2 | unpad_sequence | 8 | 8 |
| d4 | case | 8 | 8 |
| d4 | class_synonym | 6 | 6 |
| d4 | drop_separator | 9 | 9 |
| d4 | split_number | 7 | 7 |
| d4 | swap_separator | 12 | 12 |
| d4 | unit_prefix | 42 | 41 |
| d4 | unpad_sequence | 8 | 7 |

### Model calls

| decider | calls | cache hits | parse failures | cost USD (all calls) | latency p50 s | p95 s |
|---|---|---|---|---|---|---|
| d4 | 526 | 0 | 0 | 0.059288 | 3.656 | 6.812 |

### Paired differences in F1 (plus minus minus)

| plus | minus | difference | 95 % CI |
|---|---|---|---|
| d1|all | d0|all | 0.562 | [0.446, 0.662] |
| d1|format | d0|format | 0.900 | [0.824, 0.960] |
| d1|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d0|all | 0.647 | [0.541, 0.739] |
| d2|format | d0|format | 1.000 | [1.000, 1.000] |
| d2|naming | d0|naming | 0.000 | [0.000, 0.000] |
| d2|all | d1|all | 0.085 | [0.034, 0.145] |
| d2|format | d1|format | 0.100 | [0.040, 0.176] |
| d2|naming | d1|naming | 0.000 | [0.000, 0.000] |
| d4|all | d0|all | 0.776 | [0.709, 0.836] |
| d4|format | d0|format | 0.966 | [0.929, 1.000] |
| d4|naming | d0|naming | 0.969 | [0.931, 1.000] |
| d4|all | d1|all | 0.213 | [0.089, 0.335] |
| d4|format | d1|format | 0.066 | [0.008, 0.139] |
| d4|naming | d1|naming | 0.969 | [0.931, 1.000] |
| d4|all | d2|all | 0.129 | [0.014, 0.248] |
| d4|format | d2|format | -0.034 | [-0.071, 0.000] |
| d4|naming | d2|naming | 0.969 | [0.931, 1.000] |
| d0|format | d0|naming | 0.000 | [0.000, 0.000] |
| d1|format | d1|naming | 0.900 | [0.824, 0.960] |
| d2|format | d2|naming | 1.000 | [1.000, 1.000] |
| d4|format | d4|naming | -0.003 | [-0.052, 0.049] |

