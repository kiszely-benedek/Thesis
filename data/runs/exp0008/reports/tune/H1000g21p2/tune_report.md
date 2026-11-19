# V2T tuning: H1000g21p2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 280 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 258/280 | 254/280 | 258/280 | 254/280 | 18 | 5 | 8.5 | 74.2 |
| cascade_v4_iso | 258/280 | 256/280 | 258/280 | 256/280 | 13 | 5 | 8.5 | 64.3 |

Cypher tier: 211/280 accepted (205 correct); rejected by rule: answered 29, complete 2, not_abstained 9, rows 29; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 263/280.

Variant choice: not defined here (the rule is fixed on the tuning set only).

