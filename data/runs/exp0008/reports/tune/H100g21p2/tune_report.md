# V2T tuning: H100g21p2, setting A

Cypher timeout 30 s; limit 120 s (question deadline). 280 questions. Primary number: accuracy within 120 s.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 252/280 | 252/280 | 252/280 | 252/280 | 2 | 7 | 7.7 | 40.5 |
| cascade_v4_iso | 253/280 | 253/280 | 253/280 | 253/280 | 2 | 6 | 7.7 | 42.8 |

Cypher tier: 221/280 accepted (207 correct); rejected by rule: answered 18, not_abstained 9, rows 32; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 259/280.

Variant choice: not defined here (the rule is fixed on the tuning set only).

