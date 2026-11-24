# EXP-0009 P1 launcher

Two systems on the same v2.2 plants: A2 (the frozen V2T-A2, E9) and B (the revised V2T-B). Design:
`docs/private/40-design/generator-v2-2-handbook-rules.md` section 19; ADR-0067, ADR-0068 (proposed).
Everything here follows EXP-0008's launcher (`data/runs/exp0008/`). **Nothing runs before the user says "mehet".**

## Order of work

1. `python -m plantgraph.qa.exp0009.launcher draw --draw-seed N` (free, minutes). Writes `prereg/seeds.json`,
   `plan.json`, `position_prior.json`; never overwrites; prints the PREREG A tables.
2. Fill `PREREG_A.template.md` into `prereg/PREREG_A.md`; commit part A on the user's order.
3. `sh data/runs/exp0009/readiness.sh`.
4. `launch.sh` (or `run_all.sh`), stage by stage. P0, F10, B10, END are free; P1a, P1b, P1c, P1g, P1d are paid.

## Stages (`run_all.sh --from <stage>` resumes; `--smoke` proves the chain with zero real calls)

| Stage | What | Paid |
|---|---|---|
| P0 | G0a/b/c/d/f/g/j/k, line view, G0-B, R14f, prior refit, ledger and records tests | no |
| P1a | B tuning on D100g22; stops after each round `[needs the main session]` | yes |
| P1b | validation pair; G1, G1-B, G1-B2 | yes |
| F10 | E10 freeze, `B_FILES.sha256`, `PREREG_B.md`, `PREREG.sha256` | no |
| B10 | sealed plants, pools, drop set, question files, `D10.sha256` | no |
| P1c | ten sealed plants, both arms, each run replayed cache-only | yes |
| P1g | the user's GLM comparison arm: GLM 5.3 Flash (pinned host fireworks) instead of Luna, on the first sealed plant of each scale, scope R only; own cap $2.50, descriptive only | yes |
| P1d | scorer audit: main sample (scope R rows only) and the B stratum; stops after the judge until `state/audit_classified` exists | yes |
| END | reports, record check, re-score of both tiers, ledger, T17 analysis, demo database restore | no |

P1a: after round 1 change B files, then `E10_TUNE_CHANGE="what changed" sh run_all.sh --from P1a` for the next
round, or `python -m plantgraph.qa.exp0009.launcher finish-tuning --root data/runs/exp0009` to end tuning.

## Neo4j

One corpus at a time: every load wipes first. A stop leaves the last plant loaded. To restore the demo plant by
hand: `sh data/runs/exp0009/demo_load.sh` (wipe, then H1000g21p1 with `plant_lines`, ADR-0064).

## Money

Hard cap $35 for runs and audit together; per-run caps from question counts (no dry run); the estimate is printed
before each paid stage. Money stops (`[top-up or restart]`) are resolved by the main session without asking.

P1g (the GLM comparison arm) has its own hard cap of $2.50, inside the runs ledger. Its estimate NOTE is A2's sealed
rate times GLM's dev cost ratio 1.2-1.9. Before its first call it checks the runs ledger and the OpenRouter balance
against what is left of the cap. A shortfall does not stop the launcher: P1g records `p1g/SHORTFALL`, prints a `[needs the user]` NOTE, ends with the runs it finished, and P1d goes on. It runs after P1c, when P1's
actual spend is known. Its pins (`inputs/pin_*_glm_fireworks_*.json`) are hashed into E10 with the other inputs.

## Records

Every run keeps `calls.jsonl`, `answers.jsonl`, `timings.jsonl`, `environment.jsonl`. After each run the launcher
checks them (`records-check`); `launcher rescore` re-scores a run offline and writes precision, recall and F1.

## Audit (P1d)

- The main sample is drawn from **scope R rows only** (`exp0009.audit_select`, ADR-0069): A2's scope X rows are wrong by
  construction. With B sealed it is sized with 2/3 of the audit cap; both judges get the **total** cap and share one
  ledger file. A judge stopped by its cap is a STOP `[top-up or restart]`.
- The B stratum is judged through `exp0009.audit_judge`, which adds the help lines for VALVE_SET and POSITION to the
  frozen judge in its own process and prints them with their sha256 (record both in PREREG A). The prompt template file
  and the judge pin are unchanged. The main sample uses the frozen `qa.audit judge` (same prompt for scope R types).
- After the judge reports the launcher stops `[needs the main session]`. Classify the disagreements, then
  `touch data/runs/exp0009/state/audit_classified` and resume with `--from P1d`.

## Guards added after the second review (T13c)

- `launch.sh` refuses any `NEO4J_DATABASE` but `neo4j` and exports it: every load replaces that database.
- End of P1b: P1c's spend is projected from the measured costs; if it exceeds the step ceiling or the runs ledger less
  the $2.50 GLM reserve the launcher stops `[needs the user]` before F10 (`state/p1c_projection.json`, also in part B).
- A resume loads a plant only if a Cypher run or replay of it is still to do.
- `require_frozen` also asks git: no uncommitted, untracked or committed change under the frozen paths since E10.
- F10 refuses to run again once a sealed plant exists or `E10.commit` is committed.
- F10 runs T17's tests; END reports a T17 that fails to import as a failed report.
- 1,000-sheet builds and pools run under the memory probe (limit 10 GiB, peak into the log); B10 stops
  `[needs the main session]` if the VAL1000 pool passed 8 GiB (`touch state/memory_acknowledged` to go on).
- A STOP inside a redirected block reaches `run_all.log` (fd 4), not only the step log.

## Known gaps

- G0h (first-turn prompt fits the pin's context wall) is left to the harness's own run-start check.
- The G0f replays (P0, step `g0f_replays`) and the Neo4j loads have been exercised only through stubs and the smoke's
  file-only mode; the first live run is the first real test of them.
