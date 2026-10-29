# EXP-0007 report (v2 plants)

Cutoff 120 s (acc@120); paired bootstrap 10000 resamples, seed 20261101, 95 % percentile CI.

## Claims

| Id | Claim | Value | Verdict |
|---|---|---|---|
| X1 | The single-sheet advantage of ContextRAG shrinks with corpus size | slope -0.071 per log10(sheets), 95% CI [-0.218, +0.074] over H1g2, H3g2, H10g2 (common families) | FAIL |
| X2 | ChatP&ID's end holds: on one sheet ContextRAG is not worse than the cascade | H1g2 common: delta -0.271 [-0.386, -0.157], n=70; all families: delta -0.271 [-0.386, -0.157], n=70; margin -0.05 | FAIL |
| X3 | Accuracy flip point | s_acc = H1g2, the smallest measured size | REPORTED |
| X4 | Cost and latency flip | s_cost = H1g2; s_lat = H1g2; $/q ratio ctx-high/cascade_v4_iso: H1g2 3.79, H3g2 7.13, H10g2 21.57; median-latency ratio: H1g2 1.39, H3g2 1.46, H10g2 2.10 | REPORTED |
| X5 | The context wall | r = 2.56 chars/token over 248 calls; c = 37,935 chars/sheet; W = 62 sheets (window 922,000 prompt tokens) | REPORTED |
| X6 | Effort sensitivity | not run on v2 (ADR-0060), see EXP-0001 | NOT_RUN |

## Corpus sizes

| Corpus | Sheets | Occurrence nodes | ctx prompt chars | Median prompt tokens | Chars/token |
|---|---|---|---|---|---|
| H1g2 | 1 | 104 | 44,234 | 17,228 | 2.57 |
| H3g2 | 3 | 260 | 107,685 | 42,116 | 2.56 |
| H10g2 | 11 | 1035 | 419,443 | 164,780 | 2.55 |
| H30g2 | 30 | 2853 | - | - | - |

## Arms per size

| Corpus | Arm | Scope | n | acc@cutoff [95% CI] | Uncut | $/q mean (median) | Latency median / p90 s | Outcomes |
|---|---|---|---|---|---|---|---|---|
| H1g2 | ctx-high | common | 70 | 0.686 [0.570, 0.782] | 0.686 | 0.00274 (0.00238) | 7.6 / 34.9 | ANSWERED 70 |
| H1g2 | ctx-high | all | 70 | 0.686 [0.570, 0.782] | 0.686 | 0.00274 (0.00238) | 7.6 / 34.9 | ANSWERED 70 |
| H1g2 | cyp | common | 70 | 0.857 [0.757, 0.921] | 0.857 | 0.00056 (0.00047) | 5.1 / 11.4 | ANSWERED 70 |
| H1g2 | cyp | all | 70 | 0.857 [0.757, 0.921] | 0.857 | 0.00056 (0.00047) | 5.1 / 11.4 | ANSWERED 70 |
| H1g2 | ag | common | 70 | 0.957 [0.881, 0.985] | 0.957 | 0.00055 (0.00034) | 8.2 / 17.9 | ANSWERED 70 |
| H1g2 | ag | all | 70 | 0.957 [0.881, 0.985] | 0.957 | 0.00055 (0.00034) | 8.2 / 17.9 | ANSWERED 70 |
| H1g2 | cascade_v4_iso | common | 70 | 0.957 [0.881, 0.985] | 0.957 | 0.00072 (0.00050) | 5.5 / 22.5 | ANSWERED 70 |
| H1g2 | cascade_v4_iso | all | 70 | 0.957 [0.881, 0.985] | 0.957 | 0.00072 (0.00050) | 5.5 / 22.5 | ANSWERED 70 |
| H3g2 | ctx-high | common | 76 | 0.645 [0.533, 0.743] | 0.645 | 0.00601 (0.00571) | 11.6 / 48.1 | ANSWERED 76 |
| H3g2 | ctx-high | all | 78 | 0.654 [0.543, 0.750] | 0.654 | 0.00600 (0.00567) | 11.0 / 48.1 | ANSWERED 78 |
| H3g2 | cyp | common | 76 | 0.711 [0.600, 0.800] | 0.711 | 0.00059 (0.00053) | 6.5 / 11.8 | ANSWERED 74, RETRIEVAL_ERROR 2 |
| H3g2 | cyp | all | 78 | 0.705 [0.596, 0.795] | 0.705 | 0.00059 (0.00052) | 6.5 / 11.8 | ANSWERED 76, RETRIEVAL_ERROR 2 |
| H3g2 | ag | common | 76 | 0.934 [0.855, 0.972] | 0.934 | 0.00074 (0.00037) | 10.0 / 28.4 | ANSWERED 76 |
| H3g2 | ag | all | 78 | 0.936 [0.859, 0.972] | 0.936 | 0.00077 (0.00039) | 10.5 / 28.4 | ANSWERED 78 |
| H3g2 | cascade_v4_iso | common | 76 | 0.882 [0.790, 0.936] | 0.882 | 0.00083 (0.00061) | 7.5 / 33.7 | ANSWERED 76 |
| H3g2 | cascade_v4_iso | all | 78 | 0.885 [0.795, 0.938] | 0.885 | 0.00084 (0.00061) | 7.5 / 33.7 | ANSWERED 78 |
| H10g2 | ctx-high | common | 76 | 0.553 [0.441, 0.659] | 0.553 | 0.02185 (0.02133) | 18.4 / 60.0 | ANSWERED 75, PARSE_FAILURE 1 |
| H10g2 | ctx-high | all | 88 | 0.614 [0.509, 0.709] | 0.614 | 0.02172 (0.02105) | 16.1 / 59.2 | ANSWERED 87, PARSE_FAILURE 1 |
| H10g2 | cyp | common | 76 | 0.763 [0.656, 0.845] | 0.763 | 0.00063 (0.00052) | 6.3 / 14.0 | ANSWERED 72, PARSE_FAILURE 3, RETRIEVAL_ERROR 1 |
| H10g2 | cyp | all | 88 | 0.795 [0.700, 0.867] | 0.795 | 0.00062 (0.00053) | 6.3 / 13.6 | ANSWERED 84, PARSE_FAILURE 3, RETRIEVAL_ERROR 1 |
| H10g2 | ag | common | 76 | 0.947 [0.872, 0.979] | 0.947 | 0.00121 (0.00040) | 10.1 / 27.4 | ANSWERED 76 |
| H10g2 | ag | all | 88 | 0.943 [0.874, 0.975] | 0.943 | 0.00133 (0.00050) | 10.1 / 26.1 | ANSWERED 88 |
| H10g2 | cascade_v4_iso | common | 76 | 0.895 [0.806, 0.946] | 0.895 | 0.00108 (0.00061) | 7.8 / 38.0 | ANSWERED 76 |
| H10g2 | cascade_v4_iso | all | 88 | 0.909 [0.831, 0.953] | 0.909 | 0.00101 (0.00059) | 7.6 / 35.2 | ANSWERED 88 |
| H30g2 | cyp | common | 76 | 0.750 [0.642, 0.834] | 0.750 | 0.00068 (0.00054) | 5.8 / 18.6 | ANSWERED 72, RETRIEVAL_ERROR 4 |
| H30g2 | cyp | all | 92 | 0.761 [0.664, 0.836] | 0.761 | 0.00067 (0.00057) | 6.2 / 18.6 | ANSWERED 87, RETRIEVAL_ERROR 5 |
| H30g2 | ag | common | 76 | 0.934 [0.855, 0.972] | 0.934 | 0.00125 (0.00043) | 10.9 / 27.4 | ANSWERED 76 |
| H30g2 | ag | all | 92 | 0.935 [0.865, 0.970] | 0.935 | 0.00137 (0.00051) | 11.4 / 27.1 | ANSWERED 91, PARSE_FAILURE 1 |
| H30g2 | cascade_v4_iso | common | 76 | 0.908 [0.822, 0.955] | 0.908 | 0.00107 (0.00062) | 7.2 / 39.6 | ANSWERED 76 |
| H30g2 | cascade_v4_iso | all | 92 | 0.924 [0.851, 0.963] | 0.924 | 0.00104 (0.00061) | 7.3 / 39.6 | ANSWERED 92 |

## Paired differences

| Corpus | Scope | Difference | Metric | n | Delta | 95% CI |
|---|---|---|---|---|---|---|
| H1g2 | common | ctx-high - cascade_v4_iso | acc@120 | 70 | -0.27143 | [-0.38571, -0.15714] |
| H1g2 | all | ctx-high - cascade_v4_iso | acc@120 | 70 | -0.27143 | [-0.38571, -0.15714] |
| H3g2 | common | ctx-high - cascade_v4_iso | acc@120 | 76 | -0.23684 | [-0.35526, -0.11842] |
| H3g2 | all | ctx-high - cascade_v4_iso | acc@120 | 78 | -0.23077 | [-0.34615, -0.11538] |
| H10g2 | common | ctx-high - cascade_v4_iso | acc@120 | 76 | -0.34211 | [-0.44737, -0.23684] |
| H10g2 | all | ctx-high - cascade_v4_iso | acc@120 | 88 | -0.29545 | [-0.39773, -0.20455] |

## Trend over log10(sheets)

| Scope | Sizes | Slope | 95% CI | Resamples | Seed |
|---|---|---|---|---|---|
| common | H1g2, H3g2, H10g2 | -0.0714 | [-0.2182, +0.0739] | 10000 | 20261101 |

## Scopes

- **common** (19 families): CONNECTED, COUNT_IN_UNIT, DOWNSTREAM_IN_UNIT, DOWNSTREAM_ISOLATION, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, UNANSWERABLE_TAG, UNITS_REACHED, UPSTREAM_ISOLATION, UPSTREAM_SOURCES, VALVES_ON_PATH
- **all** (24 families): CONNECTED, COUNT_IN_UNIT, CROSS_UNIT, DOWNSTREAM_IN_UNIT, DOWNSTREAM_ISOLATION, FEEDING_UNITS, FIRST_MEETING_POINT, FLOW_PATH, INSTRUMENTS_OF_ITEM, LOOKUP_TYPE, LOOKUP_UNIT, LOOPS_NEAR_ITEM, LOOP_ACTUATED_VALVE, LOOP_MEASURED_EQUIPMENT, NEIGHBOURS_DOWNSTREAM, NO_PATH, ROUTE_AVOIDING, SAME_UNIT, SHEETS_OF_TAG, UNANSWERABLE_TAG, UNITS_REACHED, UPSTREAM_ISOLATION, UPSTREAM_SOURCES, VALVES_ON_PATH

## Arms or sizes not scored

- ctx-low at H1g2: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-low at H3g2: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-low at H10g2: no run for tier 'context-luna-low' (arm 'ctx-low')
- ctx-high at H30g2: no run for tier 'context-luna-high' (arm 'ctx-high')
- ctx-low at H30g2: no run for tier 'context-luna-low' (arm 'ctx-low')

ContextRAG was run on H1g2, H3g2 and H10g2 only and is not run at H30g2 and above: the \ cost of a full-plant prompt there is out of proportion, and from about 56 sheets a v2 plant no longer \ fits the model's prompt window (EXP-0007 R3). Rows marked absent are runs that were not made. 
