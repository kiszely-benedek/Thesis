# V2T tuning: X100g2s212, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 163 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 150/163 | 150/163 | 150/163 | 150/163 | 0 | 7 | 6.5 | 30.0 |
| cascade_v4_iso | 154/163 | 154/163 | 154/163 | 154/163 | 0 | 3 | 6.5 | 27.0 |

Cypher tier: 118/163 accepted (109 correct); rejected by rule: answered 9, complete 1, not_abstained 5, rows 30; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 157/163.

Variant choice: not defined here (the rule is fixed on the tuning set only).

