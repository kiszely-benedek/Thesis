# EXP-0009 P1 launcher

Two systems on the same v2.2 plants: A2 (the frozen V2T-A2, E9) and B (the revised V2T-B). Design:
`docs/private/40-design/generator-v2-2-handbook-rules.md` section 19; ADR-0067, ADR-0068 (proposed).
Everything here follows EXP-0008's launcher (`data/runs/exp0008/`). **Nothing runs before the user says "mehet".**

## Order of work

1. `python -m plantgraph.qa.exp0009.launcher draw --draw-seed N` (free, minutes). Writes `prereg/seeds.json`,
   `plan.json`, `position_prior.json`; never overwrites; prints the PREREG A tables.
2. Fill `PREREG_A.template.md` into `prereg/PREREG_A.md`; commit part A on the user's order.
3. `sh data/runs/exp0009/readiness.sh`.
4. `launch.sh` (or `run_all.sh`), stage by stage. P0, F10, B10, END are free; P1a, P1b, P1c, P1d are paid.

## Stages (`run_all.sh --from <stage>` resumes; `--smoke` proves the chain with zero real calls)

| Stage | What | Paid |
|---|---|---|
| P0 | G0a/b/c/d/f/g/j/k, line view, G0-B, R14f, prior refit, ledger and records tests | no |
| P1a | B tuning on D100g22; stops after each round `[needs the main session]` | yes |
| P1b | validation pair; G1, G1-B, G1-B2 | yes |
| F10 | E10 freeze, `B_FILES.sha256`, `PREREG_B.md`, `PREREG.sha256` | no |
| B10 | sealed plants, pools, drop set, question files, `D10.sha256` | no |
| P1c | ten sealed plants, both arms, each run replayed cache-only | yes |
| P1d | scorer audit: main sample and the B stratum; stops after the judge | yes |
| END | reports, record check, re-score, ledger, T17 hook, demo database restore | no |

P1a: after round 1 change B files, then `E10_TUNE_CHANGE="what changed" sh run_all.sh --from P1a` for the next
round, or `python -m plantgraph.qa.exp0009.launcher finish-tuning --root data/runs/exp0009` to end tuning.

## Neo4j

One corpus at a time: every load wipes first. A stop leaves the last plant loaded. To restore the demo plant by
hand: `sh data/runs/exp0009/demo_load.sh` (wipe, then H1000g21p1 with `plant_lines`, ADR-0064).

## Money

Hard cap $35 for runs and audit together; per-run caps from question counts (no dry run); the estimate is printed
before each paid stage. Money stops (`[top-up or restart]`) are resolved by the main session without asking.

## Records

Every run keeps `calls.jsonl`, `answers.jsonl`, `timings.jsonl`, `environment.jsonl`. After each run the launcher
checks them (`records-check`); `launcher rescore` re-scores a run offline and writes precision, recall and F1.

## Known gaps

- G0h (first-turn prompt fits the pin's context wall) is left to the harness's own run-start check.
- The G0f replays (P0, step `g0f_replays`) and the Neo4j loads have been exercised only through stubs and the smoke's
  file-only mode; the first live run is the first real test of them.
