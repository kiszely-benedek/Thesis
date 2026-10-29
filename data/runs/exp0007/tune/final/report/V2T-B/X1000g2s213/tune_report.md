# V2T tuning: X1000g2s213, setting B

Cypher timeout 120 s; limit 900 s (hang guard). 163 questions. Primary number: uncut accuracy.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 156/163 | 139/163 | 156/163 | 156/163 | 0 | 2 | 7.5 | 129.1 |
| cascade_v4_iso | 156/163 | 145/163 | 156/163 | 156/163 | 0 | 2 | 7.5 | 32.3 |

Cypher tier: 121/163 accepted (119 correct); rejected by rule: answered 14, not_abstained 2, rows 26; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 158/163.

Variant choice: not defined here (the rule is fixed on the tuning set only).

