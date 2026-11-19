# V2T tuning: H1000g21p1, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 280 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 259/280 | 257/280 | 259/280 | 257/280 | 9 | 5 | 8.3 | 78.3 |
| cascade_v4_iso | 260/280 | 258/280 | 260/280 | 258/280 | 6 | 4 | 8.3 | 48.5 |

Cypher tier: 211/280 accepted (203 correct); rejected by rule: answered 29, complete 2, not_abstained 5, rows 33; correct answers rejected only for being cut at the row cap: 1.

Oracle (either tier correct): 264/280.

Variant choice: not defined here (the rule is fixed on the tuning set only).

