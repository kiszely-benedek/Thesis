# V2T tuning: H1g2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 74 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 68/74 | 68/74 | 68/74 | 68/74 | 0 | 4 | 5.7 | 22.3 |
| cascade_v4_iso | 71/74 | 71/74 | 71/74 | 71/74 | 0 | 1 | 5.7 | 22.5 |

Cypher tier: 59/74 accepted (53 correct); rejected by rule: rows 15; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 72/74.

Variant choice: not defined here (the rule is fixed on the tuning set only).

