# V2T tuning: H100g21p3, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 280 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 257/280 | 257/280 | 257/280 | 257/280 | 0 | 7 | 7.0 | 43.0 |
| cascade_v4_iso | 259/280 | 259/280 | 259/280 | 259/280 | 0 | 5 | 7.0 | 42.2 |

Cypher tier: 222/280 accepted (212 correct); rejected by rule: answered 23, complete 1, not_abstained 7, rows 27; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 264/280.

Variant choice: not defined here (the rule is fixed on the tuning set only).

