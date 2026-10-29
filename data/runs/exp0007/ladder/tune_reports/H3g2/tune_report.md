# V2T tuning: H3g2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 82 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 69/82 | 69/82 | 69/82 | 69/82 | 0 | 9 | 7.3 | 30.8 |
| cascade_v4_iso | 73/82 | 73/82 | 73/82 | 73/82 | 0 | 5 | 7.3 | 30.8 |

Cypher tier: 62/82 accepted (49 correct); rejected by rule: answered 2, not_abstained 1, rows 17; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 78/82.

Variant choice: not defined here (the rule is fixed on the tuning set only).

