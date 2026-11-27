# EXP-0009 scorer audit: classification of the judge disagreements

Date: 2026-11-27, written by the main session under the registered audit rule (review-fixes.md §5.3, "Disagreement handling"). Each disagreement in `main/disagreements.csv` (16 rows) and `b/disagreements.csv` (9 rows) was checked against the plant graph. The check rebuilt the flow graph from the B view of the same plant with `gold_crosscheck_graph.build_flow_graph`: off-page stubs are folded and untagged parts are kept. The check scripts were read-only and ran outside the repository.

## Result

| Class | Rows |
|---|---|
| scorer/gold defect | **0** |
| judge error | **25** |
| ambiguous question | **0** |

No fix to the scorer or the gold follows, and the post-audit score equals the pre-audit score.

## Why the judge erred

Each judge error has one of five causes.

1. **The excerpt was too small.** The excerpt is cut around the evidence tags, so untagged valves a few parts away were missing from what the judge saw. 12 rows:
   - B POSITION_OF_VALVE (6 rows): FE-1006, E-3403, YV-29001, YV-17014, YV-29003, FE-44002. Each named valve exists in the graph, with the class and line number the question gives, and its first tagged item downstream is the anchor. Its position matches the gold (NO, NO, NO, NC, NC, NO).
   - B OPEN_VALVES_TO_ISOLATE F-4701: an untagged GateValve on 6-P-470001-A1A-N, position NO, sits upstream of F-4701 through one PipeTee. The gold is right and the empty answer is wrong.
   - COUNT_IN_UNIT, unit 285, SwingCheckValve (2 rows): the graph holds exactly 1, untagged. The gold of 1 is right.
   - COUNT_IN_UNIT, unit 306, NeedleValve: the graph holds exactly 5. The gold of 5 is right.
   - CONNECTED V-3101|P-3102C and EJ-19101|E-11503: both tags exist in the plant, so the system's `not_present: true` is a false abstention and wrong by the registered rule.
2. **The fitting reading.** The family definitions treat untagged fittings as transparent: tees, blinds, couplings and reducers do not break "directly connected". 4 rows:
   - LOOPS_NEAR_ITEM (3 rows): V-1301, E-303, H-33401. For V-1301, PV-13015 is reached through one untagged PipeTee. This is the same pattern as in EXP-0008.
   - NEIGHBOURS_DOWNSTREAM FV-20008: the only parts between FV-20008 and M-2101 are inline measuring elements (FE-20009, FE-21001). They are neither equipment nor valves and are passed through by definition.
3. **Units and equipment confused.** 2 rows: UNITS_REACHED EJ-4102 and EJ-37601B. The judge counted equipment items, but the question asks for units.
4. **Abstention format.** 3 rows: UNANSWERABLE_TAG FLOW_PATH for P-1802|P-4603, P-2302|TK-104 and P-2602B|P-802. The system replied `{"answer": null, "not_present": false}`. That is not an abstention, and the format rejects it (PARSE_FAILURE). The registered answer on a missing tag is `not_present: true`.
5. **An alternative path.** 1 row: FLOW_PATH GTV-174019|PGV-193002. The scorer accepts any path whose every step is a real ground-truth edge, not only the reference route (scoring.py TAG_PATH rule). The system's route is such a path. The judge could check only the reference route in its excerpt.

## One borderline row: format, not substance

B OPEN_VALVES_TO_ISOLATE P-1701 (agent, B exploratory arm). The system named the right physical valve: the GateValve on 6-P-170004-A1A-N, upstream on the suction side. But it gave `next_to: P-1701`.

The registered descriptor format, which the B prompt states, says that next_to is the first tagged item met walking from the valve. That item is STR-17004, so the scorer's verdict follows the registered format.

The row is classified as a judge error, because the question itself is not ambiguous. It is reported as a format-strictness limitation of the exploratory B arm. A lenient descriptor match (any tagged item on the same side and line) would change this one row. No such rule is applied, because it was not registered.

## Notes for the report

- On the main sample the judge agreed on 91.9 % of the right-scored rows and on 89.8 % of the wrong-scored rows. Cohen's kappa was 0.860 (main/report.md).
- After classification, every disagreement on both strata comes from the judge's side. Most are cases where the excerpt was too small (12 of 25).
- The B stratum's kappa prints as −0.000 because its sample holds no right-scored rows (b/report.md, "right sample 0"). It is not a measure of agreement.
