# V2T tuning: H1000g2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 560 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 505/560 | 502/560 | 505/560 | 502/560 | 11 | 13 | 6.8 | 51.0 |
| cascade_v4_iso | 505/560 | 502/560 | 505/560 | 502/560 | 8 | 13 | 6.8 | 42.0 |

Cypher tier: 428/560 accepted (409 correct); rejected by rule: answered 59, complete 5, not_abstained 12, rows 56; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 518/560.

Variant choice: not defined here (the rule is fixed on the tuning set only).

