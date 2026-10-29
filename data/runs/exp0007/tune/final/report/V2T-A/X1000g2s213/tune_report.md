# V2T tuning: X1000g2s213, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 163 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 156/163 | 156/163 | 156/163 | 156/163 | 2 | 2 | 7.6 | 39.4 |
| cascade_v4_iso | 156/163 | 156/163 | 156/163 | 156/163 | 0 | 2 | 7.6 | 32.3 |

Cypher tier: 121/163 accepted (119 correct); rejected by rule: answered 14, not_abstained 2, rows 26; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 158/163.

Variant choice: not defined here (the rule is fixed on the tuning set only).

