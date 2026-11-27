# Scorer audit report

| Group | Rows | Agreement | Judged correct | Judged incorrect | Ambiguous |
|---|---|---|---|---|---|
| right sample | 0 | n/a | 0 | 0 | 0 |
| wrong rows | 84 | 90.5 % | 7 | 76 | 1 |
| ContextRAG wrong rows | 0 | n/a | 0 | 0 | 0 |

Cohen's kappa (decisive rows, pooled, not population-weighted): -0.000

## Disagreements by class and family

| Class | Family | Rows |
|---|---|---|
| ambiguous_question | OPEN_VALVES_TO_ISOLATE | 1 |
| system_right_scorer_wrong | OPEN_VALVES_TO_ISOLATE | 1 |
| system_right_scorer_wrong | POSITION_OF_VALVE | 6 |
