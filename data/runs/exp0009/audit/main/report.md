# Scorer audit report

| Group | Rows | Agreement | Judged correct | Judged incorrect | Ambiguous |
|---|---|---|---|---|---|
| right sample | 74 | 91.9 % | 68 | 5 | 1 |
| wrong rows | 88 | 89.8 % | 6 | 79 | 3 |
| ContextRAG wrong rows | 0 | n/a | 0 | 0 | 0 |

Cohen's kappa (decisive rows, pooled, not population-weighted): 0.860

## Disagreements by class and family

| Class | Family | Rows |
|---|---|---|
| ambiguous_question | CONNECTED | 2 |
| ambiguous_question | FLOW_PATH | 1 |
| ambiguous_question | NEIGHBOURS_DOWNSTREAM | 1 |
| scorer_right_judge_incorrect | LOOPS_NEAR_ITEM | 3 |
| scorer_right_judge_incorrect | UNITS_REACHED | 2 |
| system_right_scorer_wrong | COUNT_IN_UNIT | 3 |
| system_right_scorer_wrong | UNANSWERABLE_TAG | 3 |
