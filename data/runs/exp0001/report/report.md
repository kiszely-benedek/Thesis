# EXP-0001 report

Cutoff 120 s (acc@120); paired bootstrap 10000 resamples, seed 20261101, 95 % percentile CI.

## Claims

| Id | Claim | Value | Verdict |
|---|---|---|---|
| X1 | The single-sheet advantage of ContextRAG shrinks with corpus size | slope -0.110 per log10(sheets), 95% CI [-0.197, -0.022] over H1, H3, H10, H30 (common families) | PASS |
| X2 | ChatP&ID's end holds: on one sheet ContextRAG is not worse than the cascade | H1 common: delta -0.118 [-0.206, -0.029], n=68; all families: delta -0.118 [-0.206, -0.029], n=68; margin -0.05 | FAIL |
| X3 | Accuracy flip point | s_acc = H1, the smallest measured size | REPORTED |
| X4 | Cost and latency flip | s_cost = H1; s_lat = H30; $/q ratio ctx-high/cascade_v3: H1 1.76, H3 6.02, H10 16.59, H30 41.54; median-latency ratio: H1 0.45, H3 0.57, H10 0.87, H30 1.13 | REPORTED |
| X5 | The context wall | r = 2.54 chars/token over 348 calls; c = 16,435 chars/sheet; W = 143 sheets (window 922,000 prompt tokens); H100 (1,649,451 chars = 649,255 tokens): fits; H1000 (16,747,117 chars = 6,591,984 tokens): does not fit | REPORTED |
| X6 | Effort sensitivity | H1: delta acc -0.029 [-0.118, +0.044], delta $/q -0.00005 [-0.00008, -0.00003] (low minus high, n=68); H10: delta acc -0.154 [-0.242, -0.066], delta $/q -0.00045 [-0.00060, -0.00031] (low minus high, n=91) | REPORTED |

## Corpus sizes

| Corpus | Sheets | Occurrence nodes | ctx prompt chars | Median prompt tokens | Chars/token |
|---|---|---|---|---|---|
| H1 | 1 | 35 | 16,606 | 6,222 | 2.67 |
| H3 | 4 | 151 | 63,277 | 24,719 | 2.56 |
| H10 | 10 | 448 | 182,609 | 71,999 | 2.54 |
| H30 | 30 | 1223 | 493,397 | 194,218 | 2.54 |

## Arms per size

| Corpus | Arm | Scope | n | acc@cutoff [95% CI] | Uncut | $/q mean (median) | Latency median / p90 s | Outcomes |
|---|---|---|---|---|---|---|---|---|
| H1 | ctx-high | common | 68 | 0.824 [0.716, 0.896] | 0.824 | 0.00090 (0.00084) | 3.6 / 8.0 | ANSWERED 68 |
| H1 | ctx-high | all | 68 | 0.824 [0.716, 0.896] | 0.824 | 0.00090 (0.00084) | 3.6 / 8.0 | ANSWERED 68 |
| H1 | ctx-low | common | 68 | 0.794 [0.684, 0.873] | 0.794 | 0.00084 (0.00083) | 2.7 / 4.4 | ANSWERED 68 |
| H1 | ctx-low | all | 68 | 0.794 [0.684, 0.873] | 0.794 | 0.00084 (0.00083) | 2.7 / 4.4 | ANSWERED 68 |
| H1 | cyp | common | 68 | 0.794 [0.684, 0.873] | 0.794 | 0.00041 (0.00041) | 6.6 / 9.9 | ANSWERED 61, RETRIEVAL_ERROR 7 |
| H1 | cyp | all | 68 | 0.794 [0.684, 0.873] | 0.794 | 0.00041 (0.00041) | 6.6 / 9.9 | ANSWERED 61, RETRIEVAL_ERROR 7 |
| H1 | ag | common | 68 | 0.882 [0.785, 0.939] | 0.882 | 0.00033 (0.00023) | 7.3 / 17.9 | ANSWERED 68 |
| H1 | ag | all | 68 | 0.882 [0.785, 0.939] | 0.882 | 0.00033 (0.00023) | 7.3 / 17.9 | ANSWERED 68 |
| H1 | cascade_v3 | common | 68 | 0.941 [0.858, 0.977] | 0.941 | 0.00051 (0.00044) | 8.1 / 15.8 | ANSWERED 68 |
| H1 | cascade_v3 | all | 68 | 0.941 [0.858, 0.977] | 0.941 | 0.00051 (0.00044) | 8.1 / 15.8 | ANSWERED 68 |
| H3 | ctx-high | common | 76 | 0.789 [0.685, 0.866] | 0.789 | 0.00342 (0.00324) | 4.9 / 15.6 | ANSWERED 76 |
| H3 | ctx-high | all | 83 | 0.783 [0.683, 0.858] | 0.783 | 0.00341 (0.00324) | 4.9 / 15.5 | ANSWERED 83 |
| H3 | cyp | common | 76 | 0.697 [0.587, 0.789] | 0.697 | 0.00043 (0.00043) | 6.7 / 11.4 | ANSWERED 59, RETRIEVAL_ERROR 17 |
| H3 | cyp | all | 83 | 0.723 [0.618, 0.808] | 0.723 | 0.00042 (0.00042) | 6.6 / 11.4 | ANSWERED 66, RETRIEVAL_ERROR 17 |
| H3 | ag | common | 76 | 0.987 [0.929, 0.998] | 0.987 | 0.00044 (0.00024) | 7.6 / 16.8 | ANSWERED 76 |
| H3 | ag | all | 83 | 0.988 [0.935, 0.998] | 0.988 | 0.00046 (0.00024) | 7.5 / 18.1 | ANSWERED 83 |
| H3 | cascade_v3 | common | 76 | 0.974 [0.909, 0.993] | 0.974 | 0.00059 (0.00048) | 8.8 / 19.3 | ANSWERED 76 |
| H3 | cascade_v3 | all | 83 | 0.976 [0.916, 0.993] | 0.976 | 0.00057 (0.00048) | 8.6 / 19.2 | ANSWERED 83 |
| H10 | ctx-high | common | 76 | 0.750 [0.642, 0.834] | 0.750 | 0.00961 (0.00920) | 5.9 / 30.6 | ANSWERED 76 |
| H10 | ctx-high | all | 91 | 0.714 [0.614, 0.797] | 0.714 | 0.00962 (0.00930) | 7.0 / 29.4 | ANSWERED 90, PARSE_FAILURE 1 |
| H10 | ctx-low | common | 76 | 0.592 [0.480, 0.696] | 0.592 | 0.00917 (0.00913) | 4.3 / 10.1 | ANSWERED 76 |
| H10 | ctx-low | all | 91 | 0.560 [0.458, 0.658] | 0.560 | 0.00917 (0.00913) | 4.7 / 9.5 | ANSWERED 91 |
| H10 | cyp | common | 76 | 0.724 [0.614, 0.812] | 0.724 | 0.00043 (0.00041) | 6.9 / 12.4 | ANSWERED 62, RETRIEVAL_ERROR 14 |
| H10 | cyp | all | 91 | 0.769 [0.673, 0.844] | 0.769 | 0.00043 (0.00041) | 7.0 / 10.6 | ANSWERED 77, RETRIEVAL_ERROR 14 |
| H10 | ag | common | 76 | 0.934 [0.855, 0.972] | 0.934 | 0.00052 (0.00029) | 8.1 / 21.8 | ANSWERED 76 |
| H10 | ag | all | 91 | 0.945 [0.878, 0.976] | 0.945 | 0.00058 (0.00029) | 8.5 / 21.8 | ANSWERED 91 |
| H10 | cascade_v3 | common | 76 | 0.947 [0.872, 0.979] | 0.947 | 0.00061 (0.00049) | 8.2 / 23.2 | ANSWERED 76 |
| H10 | cascade_v3 | all | 91 | 0.956 [0.892, 0.983] | 0.956 | 0.00058 (0.00047) | 8.0 / 17.6 | ANSWERED 91 |
| H30 | ctx-high | common | 76 | 0.658 [0.546, 0.755] | 0.658 | 0.02494 (0.02460) | 9.0 / 34.4 | ANSWERED 76 |
| H30 | ctx-high | all | 92 | 0.652 [0.551, 0.742] | 0.652 | 0.02497 (0.02462) | 9.6 / 34.4 | ANSWERED 91, PARSE_FAILURE 1 |
| H30 | cyp | common | 76 | 0.658 [0.546, 0.755] | 0.658 | 0.00042 (0.00038) | 6.9 / 11.2 | ANSWERED 58, RETRIEVAL_ERROR 18 |
| H30 | cyp | all | 92 | 0.685 [0.584, 0.771] | 0.685 | 0.00042 (0.00040) | 7.0 / 11.2 | ANSWERED 73, RETRIEVAL_ERROR 19 |
| H30 | ag | common | 76 | 0.934 [0.855, 0.972] | 0.934 | 0.00043 (0.00028) | 8.4 / 19.2 | ANSWERED 76 |
| H30 | ag | all | 92 | 0.946 [0.879, 0.977] | 0.946 | 0.00050 (0.00031) | 8.8 / 21.6 | ANSWERED 92 |
| H30 | cascade_v3 | common | 76 | 0.947 [0.872, 0.979] | 0.947 | 0.00062 (0.00050) | 8.9 / 23.1 | ANSWERED 76 |
| H30 | cascade_v3 | all | 92 | 0.935 [0.865, 0.970] | 0.935 | 0.00060 (0.00048) | 8.5 / 20.7 | ANSWERED 92 |

## Paired differences

| Corpus | Scope | Difference | Metric | n | Delta | 95% CI |
|---|---|---|---|---|---|---|
| H1 | common | ctx-high - cascade_v3 | acc@120 | 68 | -0.11765 | [-0.20588, -0.02941] |
| H1 | all | ctx-high - cascade_v3 | acc@120 | 68 | -0.11765 | [-0.20588, -0.02941] |
| H1 | all | ctx-low - ctx-high | acc@120 | 68 | -0.02941 | [-0.11765, +0.04412] |
| H1 | all | ctx-low - ctx-high | cost_usd | 68 | -0.00005 | [-0.00008, -0.00003] |
| H3 | common | ctx-high - cascade_v3 | acc@120 | 76 | -0.18421 | [-0.27632, -0.09211] |
| H3 | all | ctx-high - cascade_v3 | acc@120 | 83 | -0.19277 | [-0.28916, -0.10843] |
| H10 | common | ctx-high - cascade_v3 | acc@120 | 76 | -0.19737 | [-0.28947, -0.10526] |
| H10 | all | ctx-high - cascade_v3 | acc@120 | 91 | -0.24176 | [-0.34066, -0.15385] |
| H10 | all | ctx-low - ctx-high | acc@120 | 91 | -0.15385 | [-0.24176, -0.06593] |
| H10 | all | ctx-low - ctx-high | cost_usd | 91 | -0.00045 | [-0.00060, -0.00031] |
| H30 | common | ctx-high - cascade_v3 | acc@120 | 76 | -0.28947 | [-0.39474, -0.18421] |
| H30 | all | ctx-high - cascade_v3 | acc@120 | 92 | -0.28261 | [-0.38043, -0.18478] |

## Trend over log10(sheets)

| Scope | Sizes | Slope | 95% CI | Resamples | Seed |
|---|---|---|---|---|---|
| common | H1, H3, H10, H30 | -0.1096 | [-0.1974, -0.0220] | 10000 | 20261101 |

## Scopes

- **common** (19 families): CONNECTED, COUNT_IN_UNIT, DOWNSTREAM_IN_UNIT, DOWNSTREAM_ISOLATION, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, UNANSWERABLE_TAG, UNITS_REACHED, UPSTREAM_ISOLATION, UPSTREAM_SOURCES, VALVES_ON_PATH
- **all** (24 families): CONNECTED, COUNT_IN_UNIT, CROSS_UNIT, DOWNSTREAM_IN_UNIT, DOWNSTREAM_ISOLATION, FEEDING_UNITS, FIRST_MEETING_POINT, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_ACTUATED_VALVE, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, SHEETS_OF_TAG, UNANSWERABLE_TAG, UNITS_REACHED, UPSTREAM_ISOLATION, UPSTREAM_SOURCES, VALVES_ON_PATH

## Arms or sizes not scored

- ctx-low at H3: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-low at H30: no run for tier 'context-luna-low' (arm 'ctx-low')
