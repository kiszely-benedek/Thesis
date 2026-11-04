# V2T tuning: H100g2d50, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 560 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 507/560 | 507/560 | 507/560 | 507/560 | 1 | 19 | 6.3 | 33.6 |
| cascade_v4_iso | 512/560 | 512/560 | 512/560 | 512/560 | 1 | 14 | 6.3 | 31.3 |

Cypher tier: 447/560 accepted (416 correct); rejected by rule: answered 31, not_abstained 20, rows 62; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 526/560.

Variant choice: not defined here (the rule is fixed on the tuning set only).

