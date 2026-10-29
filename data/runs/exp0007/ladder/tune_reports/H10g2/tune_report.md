# V2T tuning: H10g2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 92 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 80/92 | 80/92 | 80/92 | 80/92 | 0 | 8 | 7.5 | 28.2 |
| cascade_v4_iso | 84/92 | 84/92 | 84/92 | 84/92 | 0 | 4 | 7.5 | 31.9 |

Cypher tier: 75/92 accepted (66 correct); rejected by rule: answered 4, not_abstained 2, rows 11; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 88/92.

Variant choice: not defined here (the rule is fixed on the tuning set only).

