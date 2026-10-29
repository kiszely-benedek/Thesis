# Round 3 re-scored under the line-view LOOPS_NEAR_ITEM gold (for the record)

Rule change (ADR-0061, "After tuning"): "valves directly connected to X" now looks through untagged
fittings, as NEIGHBOURS_DOWNSTREAM does. The round's own reports are unchanged. Produced by
`rescore_loops_near_item.py` (offline, no model call): it rewrites the 10 drawn LOOPS_NEAR_ITEM
references on `X100g2s211`, re-scores the stored `T7R3-*` answers with the normal set scoring, and re-runs
`tune-report` on the re-scored copies.

References that changed: 2 of the 10 drawn questions (both gain one loop tag).

| question | old reference | new reference |
|---|---|---|
| LOOPS_NEAR_ITEM:V-5201 | LSHH-52010 | LSHH-52010, PIC-52015 |
| LOOPS_NEAR_ITEM:V-6101 | LSHH-61010 | LSHH-61010, PIC-61016 |

Verdict changes of the stored round-3 answers (LOOPS_NEAR_ITEM, 10 questions per tier):

| tier | correct before | correct after | verdicts that changed |
|---|---|---|---|
| agent (T7R3-AG) | 8 | 10 | 2 wrong to right (V-5201, V-6101) |
| Cypher, setting A (T7R3-CYP-A) | 0 | 0 | 0 |
| Cypher, setting B (T7R3-CYP-B) | 0 | 0 | 0 |

Cascade on all 163 questions of T:

| setting | policy | correct before | correct after |
|---|---|---|---|
| A (120 s) | cascade_v4_iso | 159 | 159 |
| B (uncut) | cascade_v4_iso | 158 | 158 |
| A | cascade_v4 | 154 | 154 |
| B | cascade_v4 | 153 | 153 |
| A and B | oracle (either tier right) | 159 | 161 |

The cascade totals do not move although the agent tier gains 2: on those two questions the cascade's
final answer was evidently the Cypher tier's (the cascade did not use the agent's answer), so the
agent's now-correct answer does not reach the total. Only the oracle gains 2. (Inferred from the counts;
the per-question routing was not inspected.)
