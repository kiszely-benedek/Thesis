# V2T tuning: X100g2s211, setting B

Cypher timeout 120 s; limit 900 s (hang guard). 163 questions. Primary number: uncut accuracy.

| policy | uncut | acc@120 | acc@300 | in limit | beyond | oracle gap | p50 s | p90 s |
|---|---|---|---|---|---|---|---|---|
| cascade_v4 | 137/163 | 135/163 | 137/163 | 137/163 | 0 | 6 | 6.8 | 33.6 |
| cascade_v4_iso | 140/163 | 138/163 | 140/163 | 140/163 | 0 | 3 | 6.8 | 32.3 |

Cypher tier: 120/163 accepted (108 correct); rejected by rule: answered 12, not_abstained 1, rows 30; correct answers rejected only for being cut at the row cap: 0.

Oracle (either tier correct): 143/163.

Variant choice: **cascade_v4_iso** (cascade_v4_iso replaces cascade_v4 iff its primary accuracy on T is >= cascade_v4's; counts uncut: v4 137, v4_iso 140 of 163).

