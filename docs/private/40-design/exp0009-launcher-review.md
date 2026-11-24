# EXP-0009 launcher: second read-only review (readiness item 2)

**Date:** 2026-11-24. **Reviewer:** architect. **Commit reviewed:** HEAD `501fcdd` (part A names `ba7277a`; `git diff ba7277a 501fcdd` touches only the four `prereg/` files).
**Scope:** `src/plantgraph/qa/exp0009/`, `data/runs/exp0009/{launch.sh, run_all.sh, lib*.sh, stages/*.sh, inputs/, prereg/}`, the
frozen modules these call where a live path depends on them, against generator design §17.19, §19 and §20, and v2t-b §10.9.

**What I ran (all free, read-only):** no stage, no smoke, no Neo4j, no network, no plant built. Only:
- the records check of `records.py` over the 28 real EXP-0008 paid runs (`m6a/runs/S7-*`, `val/runs/V8-*`): 0 problems;
- a count of incomplete call records in the same files: 22,542 calls, 12 without a response (all with an error kind), none missing tokens, cost, latency or provider;
- `ModelPin.pin_hash()` of the four pins in `inputs/`, and of the judge pin;
- `require_drawn_test_seed` on seeds 1, 5669 and 5791 against the default seed plan (pure function, no plant);
- a cross-check of PREREG A's tables against `plan.json` and `seeds.json`.

## Verdict

**There are blockers: seven.** Five would make a paid or sealed stage fail after money or many machine hours are
spent (P1d twice, the GLM report, B10, and the P1d audit budget). One would let the G0f gate pass on no evidence. One
is a one-line guard that keeps a third party's Neo4j data safe. **The money caps themselves are sound:** no path lets a
run, the $35 program total or the GLM arm's $2.50 be exceeded beyond the in-flight overshoot the harness already
bounds, and a resume does not pay twice.

### How the fixes must land (read this first)

F10's allowed-change list (`freeze.py:29-36`) admits `qa/v2tb/`, `tests/v2tb/`, `qa/exp0009/analysis*`,
`tests/qa/exp0009/test_analysis*`, `prereg/` and `docs/` only. **Every fix below lies outside it** (in `stages/`,
`lib*.sh`, `run_all.sh` or `src/plantgraph/qa/exp0009/*.py`), except B7, which is in the unfrozen `launch.sh`.
After P0 has run, such a fix makes F10 refuse ("expected only B files ... to change"). So:

1. **One fix commit before P0** carries every BLOCKER and every FIX-BEFORE-F10 item (a coder task).
2. **Then re-point part A:** replace the single line `Part A code commit: ba7277a…` in `PREREG_A.md` with the fix
   commit, plus one sentence giving the reason ("second launcher review, `exp0009-launcher-review.md`"). Editing
   `prereg/` is itself allowed. There must stay **exactly one** such line: `f10.sh:30`'s `sed` prints every match,
   and two lines would break the HEAD comparison.
3. Re-run the smoke and the full `readiness.sh` (not only `--prereg-only`), then start P0.

The labels below keep the caller's meaning: **BLOCKER** = must be fixed before P0; **FIX-BEFORE-F10** = would
waste money, machine time or the record if left, and must be fixed before F10 (by point 1, in practice in the same
commit); **RECORD** = note only.

## Findings, ranked

| # | Label | Where | One line |
|---|---|---|---|
| B1 | BLOCKER | `stages/p1d.sh:74` | the judge is called with `--stage auditA`/`auditB`; the CLI accepts only `pilot` or `audit`, so P1d always stops |
| B2 | BLOCKER | `qa/audit/judge.py:29-40, 63` | the frozen judge has no help text for VALVE_SET or POSITION; the B stratum (only those types) crashes at its first row |
| B3 | BLOCKER | `stages/end.sh:43`, `qa/cascade/checks.py:155` | the GLM runs are evaluated with `cascade_v4_iso`, whose tier pins are Luna's; the join refuses, so P1g's money yields no comparison report |
| B4 | BLOCKER | `stages/b10.sh:17-25`, `lib_plants.sh:100`, `benchmark/v2/composition.py:334-339` | the sealed band report reads EXP-0008's seed plan and refuses every EXP-0009 sealed seed; B10 stops after 12–15 h, and the report would describe other plants anyway |
| B5 | BLOCKER | `stages/p1d.sh:32-35, 66, 76`, `qa/audit/budget.py:69-73` | the main audit sample is sized to the whole audit cap, the B judge's cap is counted twice, and a judge stopped by its cap exits 0: the B stratum is starved silently |
| B6 | BLOCKER | `stages/p0.sh:46, 59`, `qa/exp0008/replay.py:59-64` | the G0f Cypher replay may pass as "prefix_equal: 0 of 280 rows" |
| B7 | BLOCKER | `launch.sh` (not frozen), `store/neo4j_settings.py:62-69`, `store/neo4j_loader.py:142-150` | every load replaces the database named by `NEO4J_DATABASE`; an exported value would replace someone else's database |
| F1 | FIX-BEFORE-F10 | `qa/exp0009/stages.py:298-364`, `launcher_stages.py:251`, `caps.py:29` | P1c's ceiling is never recomputed from P1b's measured costs, and part B records no sealed caps; an overrun would end P1c at the last 1,000-sheet plants, past a freeze that forbids changing the ceiling |
| F2 | FIX-BEFORE-F10 | `stages/p1c.sh:11-27`, `stages/p1b.sh:38-47` | every resume regenerates and reloads every earlier plant, A and B |
| F3 | FIX-BEFORE-F10 | `lib_runs.sh:111-120`, `stages/end.sh:55` | `require_frozen` checks listed files only, so a module added after F10 (for example T17) runs unhashed |
| F4 | FIX-BEFORE-F10 | `stages/f10.sh:65` | a rerun of F10 deletes and rewrites the E10 files, even after sealed plants exist |
| F5 | FIX-BEFORE-F10 | `stages/p1d.sh:83-101` | P1d does not stop after the judge (§19.7, and its own header says it does); END and T17 run on unclassified verdicts |
| F6 | FIX-BEFORE-F10 | `lib.sh:44`, `run_all.sh:82-88`, every `try … > log` | a stop raised inside a redirected `try` writes its STOP line into the step log, not `run_all.log` |
| F7 | FIX-BEFORE-F10 | `stages/p1g.sh:17-23`, `run_all.sh:53` | a GLM-arm shortfall stops the launcher, and P1d (claims) cannot start until the optional P1g is done |
| F8 | FIX-BEFORE-F10 | `stages/end.sh:55`, `stages/f10.sh:64` | a T17 that fails to import is reported as "not present"; F10 never runs T17's tests |
| F9 | FIX-BEFORE-F10 (design) | `stages/p1d.sh:31-36` | the main audit sample pools A2's scope X rows, which A2 gets wrong by construction; they use up audit money that Q4's scope R needs |
| R1–R14 | RECORD | — | see the last section |

---

## Blockers

### B1. P1d calls the judge with a stage name the CLI refuses

- **Where.** `stages/p1d.sh:74`: `--stage "audit$aj_sys"` gives `auditA` or `auditB`. `qa/audit/cli.py:72`:
  `choices=["pilot", "audit"]`.
- **Failure.** `argparse` exits 2 before any call. `p1d.sh:76` stops `[infrastructure]`. No money is lost, but P1d
  can never judge. After F10 `p1d.sh` is frozen, so it could not be fixed then. The smoke skips the judge
  (§17.19 ruling 3), which is why it was not seen.
- **Fix.** `--stage audit` for both systems. The two systems are already kept apart by their `--out-dir`.

### B2. The frozen judge cannot render a VALVE_SET or POSITION row

- **Where.** `qa/audit/judge.py:29-40`: `_ANSWER_TYPE_HELP` has ten entries and lacks `AnswerType.VALVE_SET` and
  `AnswerType.POSITION`. `judge.py:63` indexes it. The B stratum holds only those two types
  (`launcher_stages.py:313-339`, `audit_b.py`).
- **Failure.** The first B row raises `KeyError` inside `run_plan` (`qa/audit/runner.py`, `_judge_one` →
  `build_prompt`). It is not caught, the judge exits 1, and `p1d.sh:76` stops. The B stratum of §19.7 cannot be
  judged at all. `qa/audit/` is EXP-0008 code and must not be edited.
- **Recommendation (a decision with alternatives; an ADR is owed).**
  - **(a) Recommended:** an EXP-0009 entry point, e.g. `launcher audit-judge-b`. It runs the frozen
    `run_plan` with a judge-prompt builder that uses the frozen template file and the frozen help table **plus**
    two entries. Draft wording:
    - `VALVE_SET (a set of valves to operate, order irrelevant; a valve without a tag is named by its class, line number, side and nearest tag)`
    - `POSITION (one normal operating position code, e.g. NO, NC, CSO)`

    The template file is unchanged, so the pre-registered prompt sha256 `b56c89d5…` and pin sha256 `e4794d07…`
    still hold. Part B must say that the B rows' answer-type line differs.
  - (b) Retype the rows as TAG_SET or FREE_TEXT. Rejected: it misdescribes the answer to the judge.
  - (c) Drop the B stratum. Rejected: SB2 would then rest on an unaudited scorer.

### B3. The GLM arm's runs are refused by the A2 cascade policy

- **Where.** `stages/end.sh:43` runs `cascade-report --arm A2` on `G9-GLM-*`. `cascade_report.policy_of("A2")`
  loads `cascade_v4_iso`, whose tiers pin `pin_sha256` `acf24178…` (Cypher) and `ffc026d3…` (agent). Those are the
  Luna pins (I computed `pin_hash()`: `pin_cypher_luna_low` = `acf24178…`, `pin_agent_luna_final_high` = `ffc026d3…`).
  The GLM pins hash to `a18d2c66…` and `833e66c3…`. `qa/cascade/checks.py:155` refuses a run whose answer pin
  differs from its tier's, and `join.py:86` raises `JoinRefused`.
- **Failure.** In END, `cascade_glm_<id>` fails, then `glm-report` fails (`reports/glm/<id>_glm.json` is missing).
  END stops after the demo restore. P1g's spend (estimated at $1.5–2 in §20, capped at $2.50) gives no report, and
  the code is frozen by then. The T13b
  tests use hand-made `ArmReport`s (`tests/qa/exp0009/test_glm_report.py`), so they could not see this.
- **Fix.** `policy_of("GLM")`: `cascade_v4_iso` with the two tier `pin_sha256` replaced by the GLM pins' hashes,
  built in code as `policy_b()` is. Add `GLM` to `--arm` and use it in `end.sh:43`. Add a test that runs
  `build_arm_report` on fake runs pinned to the GLM pins.

### B4. The sealed band report refuses the EXP-0009 seeds and would measure other plants

- **Where.** `b10.sh:17-25` → `lib_plants.sh:100` runs `benchmark.v2.composition --target-sheets 100|1000 --seeds
  <sealed seeds> --allow-test-seed`. `composition.py:334-339` calls `load_seed_plan()`, whose default is
  `data/runs/exp0008/prereg/seeds.json` (`ingest/seed_plan.py:30`), then `require_drawn_test_seed`, which
  `--allow-test-seed` does not bypass.
- **Verified.** `require_drawn_test_seed(5669, load_seed_plan())` raises "expected test seed 5669 to be in the drawn
  seed plan". So does 5791.
- **Failure.** Exit 1 with no JSON → `pb_crash=yes` → stop `[infrastructure]` at B10's `bands` step, after every
  sealed build and pool (§19.10: about 12–15 h). The files are frozen by then. The P0 dev gate passes only because
  seed 1 is outside the test range, and the smoke skips bands.
- **Second defect, measurement.** Even with the seed check passed, `composition._report_of_seed` sizes the plant by
  `smallest_n_units_v2(target)` for the nominal 100 or 1,000 and uses the preset's own tagging. The sealed plants
  have drawn targets (90–110, 900–1,100), drawn `n_units` and S9 flags. The report would describe plants that do
  not exist.
- **Fix.** A launcher command, e.g. `bands-built --scale 100 --plants H100g22p1 …`. It runs the frozen
  `build_report(plan_plant(config), …)` on each **built** plant's own recorded config (`corpora/<id>/ingest.json`),
  pools per scale as `--pool` does, and writes the same JSON. Use it in B10. The dev gate at P0 may keep the CLI.

### B5. The audit budget starves the B stratum, and a judge stopped by its cap passes silently

- **Where and how.**
  1. `p1d.sh:32-35`: `select` gets `--cap-usd` = the whole audit cap ($8.13). `select_audit` fills that room
     (`qa/audit/select.py:125-135`).
  2. `p1d.sh:66`: each judge gets `--cap-usd` = `audit-cap --left`, which is the cap less the audit spend so far.
     `SpendLedger.allows` (`budget.py:69-73`) then subtracts the same ledger's cumulative spend **again**, so the B
     judge's room is the cap less **twice** the main sample's spend.
  3. `qa/audit/cli.py:171` returns 0 even when `stopped by cap: True`, and `p1d.sh:76` checks only the exit code.
- **Size (derived from records, not a run).** EXP-0008's pilot mean is $0.02577 a call. At the sizing factor of
  1.25 that is $0.0322, so $8.13 is room for 252 rows. The B stratum is ⌈0.5 × main rows⌉ = 126 rows. If the main
  sample spends $6.50 (252 × $0.0258), the B judge starts with a cap of $1.63 while the ledger already holds $6.50.
  It stops at its first row and exits 0. **The B stratum is judged on zero rows, and nothing in `run_all.log` says so.**
- **Fix.**
  - When `b_sealed = yes`, size `select` with two thirds of the audit cap (main : B = 2 : 1 by rows). This is a
    launcher command, so the shell does no float arithmetic.
  - Pass the **total** audit cap to both judges. Use `--left` only for the balance check.
  - After each judge, `grep -q "stopped by cap: True"` its log, and stop `[top-up or restart]` if found.

### B6. The G0f Cypher replay can pass on an empty prefix

- **Where.** `p0.sh:46` sets `allow-prefix yes` for the Cypher replay. `p0.sh:59` → `replay.compare`
  (`qa/exp0008/replay.py:49-64`). When every row written equals the run's, it returns `prefix_equal: n of m` for
  any `n`, including 0.
- **Failure.** A cache miss at the first question (an environment difference, or a changed driver result order)
  stops the replay with exit 2, which is accepted. G0f then logs `GATE PASS G0f replay … prefix_equal: 0 of 280
  rows`. The gate's purpose, that the A2 system replays as E9, is not shown. At 100 sheets EXP-0008 measured
  `prefix_equal: 280 of 280 rows` for this very run (`exp0008/run_all.log`, 2026-11-12T07:16:33Z), so a complete
  replay is the measured norm.
- **Fix.** For G0f only, require `n == m`: parse the verdict, or add a `--require-complete` mode to an EXP-0009 copy
  of `cmd_replay_compare`. Leave P1b, P1c and P1g as they are (ADR-0062 prefixes at 1,000 sheets), but see R6.

### B7. Guard the Neo4j database name

- **What the launcher touches (answer to item 3).** Every load (A: `load.py:53` via `run_synthetic`; B:
  `v2tb load --fresh-database`; G0f and demo: `ingest synthetic --fresh-database`) ends in `recreate_database`
  (`store/neo4j_loader.py:142-150`). That runs `CREATE OR REPLACE DATABASE \`<settings.database>\`` on `system`.
  Reads (`count_positions_in_database`, `check_store`, the Cypher tier) use the same `settings.database`.
  - Nothing in the launcher drops a database, nothing matches a name pattern, and nothing touches a `ds-` database.
    `DROP DATABASE` exists only in `qa/exp0007/neo4j_tmp.py`, which EXP-0009 never calls.
  - **The launcher creates no corpus database of its own.** §19 names none. It replaces only `neo4j`.
- **Today it is safe.** `.env` sets `NEO4J_DATABASE=neo4j` and the variable is unset in this shell.
- **Failure.** `from_env` lets a real environment variable win over `.env` (`neo4j_settings.py:62-69`), and
  `launch.sh` runs under `bash.exe -l`, which reads the login profile. One exported `NEO4J_DATABASE=ds-…` would make
  every load replace that database. P0 already does this (the G0f load), and the loss cannot be undone.
- **Fix (in `launch.sh`, which is not frozen; no re-point needed).** Refuse to start unless `NEO4J_DATABASE` is
  unset or `neo4j`, then `export NEO4J_DATABASE=neo4j`. Optionally, readiness prints the effective database name.

## FIX-BEFORE-F10

### F1. P1c's caps are never recomputed from P1b's measurement

- **Where.**
  - `stages.render_estimate` (`stages.py:350-364`) prints the static §19.9 estimate. §19.9 says that before P1c it
    also gives the caps recomputed from P1b.
  - `cmd_prereg_b` writes `sealed_caps_usd={}` (`launcher_stages.py:251`). §19.8 item 6 asks for the recomputed
    sealed caps.
  - The P1c ceiling is a constant, $21.09 (`caps.py:29`). That is exactly 1.5 × the $14.06 estimate, so at §19.9's
    rates it equals the sum of the runs' own caps, with no slack.
- **Failure.** If measured $/q run above §19.9's figures, every run stays inside its own cap, yet the step ceiling
  runs out at the last plants in order, which are the 1,000-sheet ones. The resumed caps then raise
  `LedgerExhausted` on every retry, and `caps.py` is frozen, so this is a dead end.
- **Fix.** At the end of P1b, project P1c spend = Σ measured key × 275 or 285 (the derived counts, §19.6) × 10
  plants. Write it into part B. Stop `[needs the user]` before F10 if the projection exceeds the ceiling or what the
  runs ledger leaves after a $2.50 GLM reserve.

### F2. Resumes regenerate and reload every earlier plant

- **Where.** `p1c_plant` (`p1c.sh:11-27`) calls `neo4j_load_a`, and `neo4j_load_b`, before `paid_run` checks
  `.complete`. `val_runs` in `p1b.sh:38-47` does the same.
- **Failure.** A stop at plant k makes the resume regenerate and reload plants 1 to k−1, A and B. Each 1,000-sheet
  reload is a fresh generation (8–12 min, §19.10) plus the load, so a late resume costs hours of machine time.
- **Fix.** Load only if a Cypher run or replay of that system on that plant is still pending. It is safe, because
  `check_store` (`qa/neo4j_view.py:104-118`) refuses a database that holds another corpus id.

### F3. The frozen check misses new files

- **Where.** `require_frozen` (`lib_runs.sh:111-120`) runs `sha256sum -c` over the files E10 listed. A file
  **added** under `src/` after F10 is not seen, and `end.sh:55` imports `plantgraph.qa.exp0009.analysis` whenever it
  exists.
- **Fix.** Also require that `git status --porcelain -- $FROZEN_PATHS` is empty and that
  `git diff --name-only $(cat E10.commit) HEAD -- $FROZEN_PATHS` is empty. The user's later commit of part B touches
  `prereg/` only, so it passes.

### F4. F10 can re-freeze after the sealed plants exist

- **Where.** `f10.sh:65` deletes `E10.commit`, `E10.sha256`, `B_FILES.sha256`, `PREREG_B.md` and `PREREG.sha256`
  before writing them again. That defeats the "never overwrites" `open("x")`. `run_all.sh --from F10` reruns F10
  even when it is done.
- **Fix.** Refuse F10 if `D10.sha256` exists, or any `corpora/H*g22p*` folder exists, or `prereg/E10.commit` is
  tracked by git.

### F5. P1d does not stop for the audit classification

- **Where.** §19.7 and `p1d.sh:9-10` say the launcher stops after the judge. `stage_P1d` (`p1d.sh:83-101`) writes
  its outputs, and `run_all.sh` goes on to END. END then runs T17 on verdicts the audit rule has not classified yet.
- **Fix.** After the reports, stop `[needs the main session]` unless `state/audit_classified` exists. The main
  session creates that file after the classification.

### F6. STOP lines vanish from `run_all.log`

- **Where.** `stop_run` writes its event to stdout (`lib.sh:44`). When it runs inside `try … > file`, the line goes
  to that file. This happens at `lib_plants.sh:47, 54, 76`, `p0.sh:13-17, 24, 29, 43, 77` (the last two to
  `/dev/null` or a log), `p1a.sh:56`, `b10.sh:29`, `p1g.sh:14` and `f10.sh:67`. `run_stage` (`run_all.sh:82-88`)
  prints nothing when `STOPPED` exists.
- **Failure.** `run_all.log` simply ends. A monitor waiting for `STOP` waits forever. The `STOPPED` file itself is
  correct.
- **Fix.** In `run_stage`, when `STOPPED` exists, emit `event STOP "<its reason line>"`.
- **Workaround until then.** Monitor `state/STOPPED` and the process, not the log alone.

### F7. The optional GLM arm can block the audit

- **Where.**
  - `p1g_preflight` (`p1g.sh:17-23`) stops `[top-up or restart]` when the **runs ledger** cannot cover $2.50. A
    top-up cannot fix that; only the user's $35 can.
  - A run that hits the exhausted $2.50 ceiling cannot be resumed either.
  - P1d comes after P1g (`run_all.sh:53`), and `--from P1d` needs P1g done.
- **Fix.** A ledger shortfall in P1g becomes a NOTE: P1g ends with the runs it finished, and the label is
  `[needs the user]`. `end_glm` already handles "no runs".

### F8. A broken T17 is reported as absent and never tested

- **Where.** `end.sh:55` uses `import … 2> /dev/null`, so any import error reads as "not present". F10 runs G0j
  (`tests/v2tb`) but not `tests/qa/exp0009/test_analysis*`.
- **Fix.**
  - Test presence with `importlib.util.find_spec`, so an import error counts as a failed report.
  - At F10, run T17's tests if they exist.
  - At F10, NOTE (or stop `[needs the main session]`) when T17 is absent. §19.11 requires it before F10, and P1b
    flows straight into F10 with no pause.

### F9. The main audit sample should be scope R (a design point)

- **Where.** `audit_select` (`p1d.sh:31-36`) pools every row of the A2 sealed runs, including the four X isolation
  families that A2 answers through the TAG_SET adapter. A2 is wrong by construction wherever the gold holds an
  untagged valve (`scope_x.for_a2`).
- **Failure.** `select_audit` takes every wrong row family by family, round-robin (`select.py:62-80`). The X rows
  fill their four queues and the remainder once R's wrong rows run out. They use up audit money on rows whose
  verdict tells nothing about the scorer of Q4's scope R. EXP-0008's rule had only R families, and §19.9's $5.42
  assumed EXP-0008's sample.
- **Recommendation.** Select the main sample over scope R rows only. Make it an EXP-0009 wrapper that filters the
  pool by family before the frozen `select_audit`. The B stratum covers X. An ADR is owed, because this has a real
  alternative: audit A2's X rows on purpose, as a check of the TAG_SET adapter.

## Answers to the seven questions

1. **Caps.** The order is right in every paid path:
   - runs: step ceiling and runs ledger (`run-cap`) → balance → harness;
   - P1g: `glm-room` → balance → per-run `run-cap`;
   - audit: `audit-cap` → balance → judge.

   A run cannot pass its cap except by the in-flight overshoot `spend_cap.py` bounds. The runs ledger caps the runs
   at $26.87, and the audit takes min($8.13, $35 − runs), so the $35 total holds. The GLM arm is capped by its step
   ceiling of $2.50. A resume is seeded with the run's recorded spend (`fill.spend_guard_for_resume`), and the cap
   it is given is spent + allowance, with the allowance net of that spend (`ledger.py:51-58`), so nothing is paid
   twice. Two caveats: R1, and the dead ends of F1 and F7.
2. **Gates.** Silent passes found: B6 (empty prefix), B5 (judge stopped by its cap), F8 (T17 import error).
   - No `|| true` exists.
   - `once` runs its command in an `||` list, so `set -e` is off inside it. I checked every command `once` reaches:
     each failure that matters has an explicit `|| stop_run` or `try`.
   - The G0d crash detector (`lib_plants.sh:102-104`) is sound: it deletes the JSON first.
   - G1 with empty cells would pass (`gates._weak_everywhere` of nothing). That needs empty reports, which the
     records check rules out.
3. **Neo4j.** See B7. Only `neo4j` is replaced (with `CREATE OR REPLACE`), never dropped. No pattern match exists,
   and no `ds-` database is touched.
   - **END** restores H1000g21p1 with `plant_lines`: seed 5214 = `exp0008/prereg/seeds.json` sealed 1000 [0],
     duplication 0.25 and the ingest CLI's default generator v2.1, all as EXP-0008's `demo_load.sh`.
   - The restore is skipped only if END's `require_frozen` stops first (R12).
4. **PREREG A.**
   - Tables, seeds, tagging and `n_units` agree with `plan.json` and `seeds.json` on all 14 plants. H100g22p2 is
     the tagged 100-sheet plant, and the 1,000-sheet allocations are round_half_up(0.8 × n).
   - The prior sha256 `3d48518f…` equals the file's. The judge prompt sha256 `b56c89d5…` equals the file at
     `ba7277a`. The judge pin sha256 `e4794d07…` is the sorted-key JSON hash of `judge_pin()`, as EXP-0008's.
   - "Part A code commit: ba7277a…" is right: it is one line, matches both parsers, and the later commits change
     `prereg/` only.
   - The allowed list fits B tuning, T17, prereg and docs. It does **not** fit any launcher fix (hence "How the
     fixes must land"), any test outside `tests/v2tb/` and `tests/qa/exp0009/test_analysis*`, or a change to
     `pyproject.toml` or `uv.lock`.
   - Minor: §19.3 asks part A for "the per-tier costs". PREREG A gives the rule but not the four cost keys or the
     B ×1.10 (R13).
5. **First live paths.**
   - The A load and `require_loaded_matches` look right; R5 notes their weak check.
   - `v2tb load` and `count_positions_in_database` are consistent: string codes on both sides, the count over
     `settings.database` read-only, and `plant_lines` layers = 1, which the `plant_lines` tests in
     `tests/v2tb/test_v2tb_load_b.py` cover. Its first live run is in P1a, after the A2 baseline (estimated at $0.33
     in §19.9). The loss would be small, and a fix in `qa/v2tb/` is an allowed path.
   - The P1d judge: B1, B2, B5, F9.
   - The G0f replays: B6. Their inputs are byte-identical to `exp0007/inputs`, which EXP-0008 used.
6. **Records.** Every paid run (`paid_run`) runs `records-check`, `check-run-config`, the B code check and
   `exp0007 health` before it is marked complete. END checks P1c and P1g again. The check passes on all 28 real
   EXP-0008 runs. The judge's calls are not an arm's run and get no timings or environment record (R11).
7. **Memory.** No step is *known* to pass 6–8 GB. The unmeasured one is B10's 1,000-sheet sealed pools: the first
   run of the held-out X families at 1,000 sheets, with no probe (R6).

## RECORD

- **R1.** A resumed run's own cap resets: its cap becomes spent + its own N × cost × 1.5 (`ledger.py:51-58`). The
  step ceiling still bounds it.
- **R2.** `b_code.sha256` is written after a B run, not at its start (v2t-b R18). A failed write keeps an older
  file (`lib_runs.sh:80`), which may then describe other B files after a mid-run edit.
- **R3.** `b_code_hashes` covers `qa/v2tb/*.py` and the policy line only (`freeze.py:93-97`). §19.8 item 5 says
  "every file". `v2tb/params_b.json` and `pins_b.json` are not used by the launcher (the B arms take A2's
  `inputs/`), and E10 hashes them anyway. A tuning round that changed only a non-`.py` file would be refused as
  "unchanged".
- **R4.** The B arms share A2's parameter files (`lib_runs.sh:16-17`). B tuning can change only `v2tb` code, not
  `max_steps` and the like. This matches ADR-0067's scope; it is stated here so that nobody tries.
- **R5.** `require_loaded_matches` compares `n_sheets` only (`load.py:84-93`). The harness's `check_store` guards
  the database against the `cypcorp` copy, but nothing compares that copy with the built corpus the questions came
  from. Comparing the whole `counts` block, store keys aside, would be cheap.
- **R6. Memory and replays.**
  - Measured: EXP-0008's D1000g21 pool peaked at 2.69 GB (`exp0008/dev/pool_probe.json`); Neo4j RSS is 1.20–1.32 GB
    (`demo-v2.md`), with a heap of 1 G and a page cache of 512 m (server `neo4j.conf`); VALVES_ON_PATH peaked at
    8.75 GB before ADR-0062's fix.
  - The VAL1000 probe (`p1b.sh:32`) has no `--limit-gib`, and nothing reads its peak.
  - Recommended: probe P0's D1000g22 build and every 1,000-sheet pool with `--limit-gib 10`, and stop B10
    `[needs the main session]` if VAL1000's peak passes 8 GiB.
  - P1c Cypher replays at 1,000 sheets may pass on a short prefix; EXP-0008 had 45 of 280. Report the prefix
    shares in END.
- **R7. Machine time beyond §19.10 (my reading, not measured).**
  - A build rebuilds the corpus about five times: build, positions, `g0c_validation`, `g0g`, line view, `g0b_checks`.
  - P1d's excerpt export and END's re-score rebuild 20 corpora.
  - B4's fix adds 10 plans.
- **R8.** The four `ds-` databases sit on the same server during P1c, an uncontrolled load for K1–K3. Do not touch
  them; record `SHOW DATABASES` with their status in the P1c log.
- **R9.** G0h is not built (accepted, §17.19). The GLM model's context window is not checked; an overflow would show
  as PROVIDER_ERROR rows.
- **R10.** R14f's footprint check (≤ 5 %, §19.7 P0) is not in `gates.r14f_exactness` (`gates.py:146-160`); only
  exactness is.
- **R11.** The P1g own caps at the ×1.9 key sum to about $3.20 against the $2.50 ceiling. That is arithmetic on
  `caps.py`'s constants and the derived 235 questions. The fourth run, AG on H1000g22p1, gets what is left (about
  $1.13 at ×1.9). If GLM costs more than about 2.2 × Luna, that run is cut short.
- **R12.** END's `require_frozen` runs before the demo restore. If it stops, the database stays on the last plant.
  `demo_load.sh` restores it by hand.
- **R13.** PREREG A omits the four cost keys and the B overhead (§19.3 "per-tier costs"). They are in `caps.py`,
  which E10 hashes.
- **R14. Housekeeping.**
  - Untracked `src/plantgraph/qa/exp0009/analysis*.py` (T17 in progress) make the tree dirty under the frozen
    paths. P0 checks only `--prereg-only`, so G0a would test an uncommitted tree. Run the full readiness before P0.
  - `run_all.sh --from P0` skips steps with `state/steps/P0_*.ok`. After a re-point, delete those markers to re-run
    the gates.
  - The G0f replays open EXP-0008's tracked `m6a/cache.sqlite` read-write; check that `git status data/runs/exp0008`
    is clean after P0.
  - `E10_TUNE_CHANGE` reaches the launcher only if it is exported before `launch.sh`. Otherwise the tuning log reads
    "round k".

## Open questions for the main session

1. **B2 and F9 need a ruling and an ADR:** the B-stratum judge entry point, and a scope-R-only main sample. I
   recommend both as written above.
2. **F1:** confirm the stop rule before F10 (projection > ceiling, or > runs ledger left less $2.50), and that the
   user, not the main session, decides on a shortfall.
3. Whether the user agrees to re-point "Part A code commit" once, before P0, for the fix commit.
