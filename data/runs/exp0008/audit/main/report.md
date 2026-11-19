# Scorer audit report

| Group | Rows | Agreement | Judged correct | Judged incorrect | Ambiguous |
|---|---|---|---|---|---|
| right sample | 89 | 84.3 % | 75 | 7 | 7 |
| wrong rows | 144 | 86.1 % | 4 | 124 | 16 |
| ContextRAG wrong rows | 0 | n/a | 0 | 0 | 0 |

Cohen's kappa (decisive rows, pooled, not population-weighted): 0.889

## Disagreements by class and family

| Class | Family | Rows |
|---|---|---|
| ambiguous_question | CONNECTED | 2 |
| ambiguous_question | DOWNSTREAM_IN_UNIT | 1 |
| ambiguous_question | DOWNSTREAM_ISOLATION | 4 |
| ambiguous_question | FLOW_PATH | 1 |
| ambiguous_question | LOOPS_NEAR_ITEM | 10 |
| ambiguous_question | NEIGHBOURS_DOWNSTREAM | 1 |
| ambiguous_question | ROUTE_AVOIDING | 1 |
| ambiguous_question | UNITS_REACHED | 2 |
| ambiguous_question | VALVES_ON_PATH | 1 |
| scorer_right_judge_incorrect | FLOW_PATH | 3 |
| scorer_right_judge_incorrect | ROUTE_AVOIDING | 1 |
| scorer_right_judge_incorrect | UNITS_REACHED | 3 |
| system_right_scorer_wrong | COUNT_IN_UNIT | 1 |
| system_right_scorer_wrong | NEIGHBOURS_DOWNSTREAM | 1 |
| system_right_scorer_wrong | UNANSWERABLE_TAG | 1 |
| system_right_scorer_wrong | UNITS_REACHED | 1 |
