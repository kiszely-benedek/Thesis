# V2T tuning: H30g2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 96 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 85/96 | 85/96 | 85/96 | 85/96 | 0 | 7 | 7.3 | 39.6 |
| cascade_v4_iso | 89/96 | 89/96 | 89/96 | 89/96 | 0 | 3 | 7.3 | 39.6 |

Cypher tier: 77/96 accepted (67 correct); rejected by rule: answered 5, not_abstained 3, rows 11; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 92/96.

Variant choice: not defined here (the rule is fixed on the tuning set only).

