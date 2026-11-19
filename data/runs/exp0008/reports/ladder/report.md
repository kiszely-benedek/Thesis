# EXP-0008 report (v2.1 plants)

Cutoff 120 s (acc@120); paired bootstrap 10000 resamples, seed 20261101, 95 % percentile CI.

## Claims

| Id | Claim | Value | Verdict |
|---|---|---|---|
| X1 | The single-sheet advantage of ContextRAG shrinks with corpus size | slope -0.048 per log10(sheets), 95% CI [-0.190, +0.096] over H1g21, H3g21, H10g21 (common families) | FAIL |
| X2 | ChatP&ID's end holds: on one sheet ContextRAG is not worse than the cascade | H1g21 common: delta -0.206 [-0.309, -0.118], n=68; all families: delta -0.206 [-0.309, -0.118], n=68; margin -0.05 | FAIL |
| X3 | Accuracy flip point | s_acc = H1g21, the smallest measured size | REPORTED |
| X4 | Cost and latency flip | s_cost = H1g21; s_lat = H3g21; $/q ratio ctx-high/cascade_v4_iso: H1g21 3.22, H3g21 8.91, H10g21 23.22; median-latency ratio: H1g21 0.68, H3g21 1.73, H10g21 2.50 | REPORTED |
| X5 | The context wall | r = 2.56 chars/token over 244 calls; c = 35,429 chars/sheet; W = 67 sheets (window 922,000 prompt tokens) | REPORTED |
| X6 | Effort sensitivity | not run on v2 (ADR-0060), see EXP-0001 | NOT_RUN |

## Corpus sizes

| Corpus | Sheets | Occurrence nodes | ctx prompt chars | Median prompt tokens | Chars/token |
|---|---|---|---|---|---|
| H1g21 | 1 | 89 | 38,353 | 14,788 | 2.59 |
| H3g21 | 3 | 267 | 110,507 | 43,102 | 2.56 |
| H10g21 | 11 | 968 | 393,076 | 154,874 | 2.54 |
| H30g21 | 32 | 3275 | - | - | - |

## Arms per size

| Corpus | Arm | Scope | n | acc@cutoff [95% CI] | Uncut | $/q mean (median) | Latency median / p90 s | Outcomes |
|---|---|---|---|---|---|---|---|---|
| H1g21 | ctx-high | common | 68 | 0.779 [0.667, 0.862] | 0.779 | 0.00225 (0.00201) | 4.6 / 24.4 | ANSWERED 68 |
| H1g21 | ctx-high | all | 68 | 0.779 [0.667, 0.862] | 0.779 | 0.00225 (0.00201) | 4.6 / 24.4 | ANSWERED 68 |
| H1g21 | cyp | common | 68 | 0.824 [0.716, 0.896] | 0.824 | 0.00052 (0.00047) | 5.3 / 10.3 | ANSWERED 68 |
| H1g21 | cyp | all | 68 | 0.824 [0.716, 0.896] | 0.824 | 0.00052 (0.00047) | 5.3 / 10.3 | ANSWERED 68 |
| H1g21 | ag | common | 68 | 0.985 [0.921, 0.997] | 0.985 | 0.00047 (0.00030) | 8.5 / 22.2 | ANSWERED 68 |
| H1g21 | ag | all | 68 | 0.985 [0.921, 0.997] | 0.985 | 0.00047 (0.00030) | 8.5 / 22.2 | ANSWERED 68 |
| H1g21 | cascade_v4_iso | common | 68 | 0.985 [0.921, 0.997] | 0.985 | 0.00070 (0.00049) | 6.8 / 25.8 | ANSWERED 68 |
| H1g21 | cascade_v4_iso | all | 68 | 0.985 [0.921, 0.997] | 0.985 | 0.00070 (0.00049) | 6.8 / 25.8 | ANSWERED 68 |
| H3g21 | ctx-high | common | 76 | 0.566 [0.454, 0.671] | 0.566 | 0.00614 (0.00582) | 10.6 / 38.5 | ANSWERED 76 |
| H3g21 | ctx-high | all | 78 | 0.577 [0.466, 0.680] | 0.577 | 0.00613 (0.00582) | 10.6 / 38.5 | ANSWERED 78 |
| H3g21 | cyp | common | 76 | 0.789 [0.685, 0.866] | 0.789 | 0.00056 (0.00049) | 5.2 / 13.2 | ANSWERED 76 |
| H3g21 | cyp | all | 78 | 0.795 [0.692, 0.870] | 0.795 | 0.00055 (0.00049) | 5.2 / 13.2 | ANSWERED 78 |
| H3g21 | ag | common | 76 | 0.934 [0.855, 0.972] | 0.934 | 0.00060 (0.00040) | 11.7 / 22.4 | ANSWERED 76 |
| H3g21 | ag | all | 78 | 0.923 [0.842, 0.964] | 0.923 | 0.00064 (0.00041) | 12.0 / 22.9 | ANSWERED 78 |
| H3g21 | cascade_v4_iso | common | 76 | 0.921 [0.838, 0.963] | 0.921 | 0.00069 (0.00053) | 6.2 / 22.6 | ANSWERED 76 |
| H3g21 | cascade_v4_iso | all | 78 | 0.923 [0.842, 0.964] | 0.923 | 0.00069 (0.00053) | 6.2 / 22.6 | ANSWERED 78 |
| H10g21 | ctx-high | common | 76 | 0.592 [0.480, 0.696] | 0.592 | 0.02067 (0.02026) | 20.6 / 68.1 | ANSWERED 76 |
| H10g21 | ctx-high | all | 86 | 0.640 [0.534, 0.733] | 0.640 | 0.02055 (0.02013) | 16.7 / 67.8 | ANSWERED 86 |
| H10g21 | cyp | common | 76 | 0.763 [0.656, 0.845] | 0.763 | 0.00061 (0.00052) | 5.7 / 12.8 | ANSWERED 71, PARSE_FAILURE 5 |
| H10g21 | cyp | all | 86 | 0.779 [0.681, 0.854] | 0.779 | 0.00060 (0.00053) | 5.9 / 12.8 | ANSWERED 81, PARSE_FAILURE 5 |
| H10g21 | ag | common | 76 | 0.882 [0.790, 0.936] | 0.882 | 0.00098 (0.00039) | 10.1 / 31.1 | ANSWERED 76 |
| H10g21 | ag | all | 86 | 0.895 [0.813, 0.944] | 0.895 | 0.00108 (0.00044) | 10.4 / 31.1 | ANSWERED 86 |
| H10g21 | cascade_v4_iso | common | 76 | 0.855 [0.759, 0.917] | 0.855 | 0.00090 (0.00056) | 6.6 / 33.4 | ANSWERED 76 |
| H10g21 | cascade_v4_iso | all | 86 | 0.872 [0.785, 0.927] | 0.872 | 0.00088 (0.00056) | 6.7 / 25.9 | ANSWERED 86 |
| H30g21 | cyp | common | 76 | 0.868 [0.774, 0.927] | 0.868 | 0.00067 (0.00052) | 6.2 / 21.7 | ANSWERED 74, PARSE_FAILURE 2 |
| H30g21 | cyp | all | 88 | 0.852 [0.763, 0.912] | 0.852 | 0.00066 (0.00052) | 6.4 / 16.4 | ANSWERED 85, PARSE_FAILURE 3 |
| H30g21 | ag | common | 76 | 0.895 [0.806, 0.946] | 0.895 | 0.00150 (0.00042) | 9.8 / 32.7 | ANSWERED 76 |
| H30g21 | ag | all | 88 | 0.898 [0.817, 0.945] | 0.898 | 0.00155 (0.00048) | 10.2 / 31.5 | ANSWERED 88 |
| H30g21 | cascade_v4_iso | common | 76 | 0.908 [0.822, 0.955] | 0.908 | 0.00134 (0.00057) | 6.7 / 45.1 | ANSWERED 76 |
| H30g21 | cascade_v4_iso | all | 88 | 0.920 [0.845, 0.961] | 0.920 | 0.00133 (0.00058) | 6.8 / 44.0 | ANSWERED 88 |

## Paired differences

| Corpus | Scope | Difference | Metric | n | Delta | 95% CI |
|---|---|---|---|---|---|---|
| H1g21 | common | ctx-high - cascade_v4_iso | acc@120 | 68 | -0.20588 | [-0.30882, -0.11765] |
| H1g21 | all | ctx-high - cascade_v4_iso | acc@120 | 68 | -0.20588 | [-0.30882, -0.11765] |
| H3g21 | common | ctx-high - cascade_v4_iso | acc@120 | 76 | -0.35526 | [-0.47368, -0.23684] |
| H3g21 | all | ctx-high - cascade_v4_iso | acc@120 | 78 | -0.34615 | [-0.46154, -0.23077] |
| H10g21 | common | ctx-high - cascade_v4_iso | acc@120 | 76 | -0.26316 | [-0.38158, -0.15789] |
| H10g21 | all | ctx-high - cascade_v4_iso | acc@120 | 86 | -0.23256 | [-0.33721, -0.12791] |

## Trend over log10(sheets)

| Scope | Sizes | Slope | 95% CI | Resamples | Seed |
|---|---|---|---|---|---|
| common | H1g21, H3g21, H10g21 | -0.0484 | [-0.1896, +0.0957] | 10000 | 20261101 |

## Scopes

- **common** (19 families): CONNECTED, COUNT_IN_UNIT, DOWNSTREAM_IN_UNIT, DOWNSTREAM_ISOLATION, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, UNANSWERABLE_TAG, UNITS_REACHED, UPSTREAM_ISOLATION, UPSTREAM_SOURCES, VALVES_ON_PATH
- **all** (23 families): CONNECTED, COUNT_IN_UNIT, CROSS_UNIT, DOWNSTREAM_IN_UNIT, DOWNSTREAM_ISOLATION, FEEDING_UNITS, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_ACTUATED_VALVE, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, SHEETS_OF_TAG, UNANSWERABLE_TAG, UNITS_REACHED, UPSTREAM_ISOLATION, UPSTREAM_SOURCES, VALVES_ON_PATH

## Arms or sizes not scored

- ctx-low at H1g21: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-low at H3g21: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-low at H10g21: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-high at H30g21: no run for tier 'context-luna-high' (arm 'ctx-high')
- ctx-low at H30g21: no run for tier 'context-luna-low' (arm 'ctx-low')
