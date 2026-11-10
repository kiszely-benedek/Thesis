# EXP-0008 launcher

The final v2 measurement (ADR-0065) is run by one script, `run_all.sh`, stage after stage, M0 to M10b.
**Nothing here runs before the user says "mehet"** (after reading the study map). Until then this folder
holds only scripts, a template and this file.

## Start

Check first: `.venv/Scripts/python -m plantgraph.qa.exp0008.readiness --smoke-passed <smoke root>/SMOKE_PASSED`
(items it cannot check are printed as `[HAND]`).

Launch on the user's machine, detached from the terminal (proven in EXP-0004). In PowerShell:

```powershell
Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine='"C:\Program Files\Git\bin\bash.exe" -l <script>'}
```

where `<script>` is `launch.sh` in this folder, given with its full path and forward slashes (for example
`C:/path/to/repo/data/runs/exp0008/launch.sh`). It changes to the
repository, sets `E9_NEO4J_HOME` (the Neo4j server's home folder; from the environment, else a line
`E9_NEO4J_HOME=...` in the git-ignored `.env`, else the Neo4j Desktop folder that `exp0007/run_infra_v2.sh` already
names), refuses to start if that folder is missing, and runs `run_all.sh "$@"`, appending to `run_all.log`; options
such as `--from M5` pass through. From a Git Bash prompt the same thing is:

```sh
nohup sh data/runs/exp0008/launch.sh > /dev/null 2>&1 &
```

Watch it with `grep '^===' data/runs/exp0008/run_all.log`. One line per event:
`=== <UTC> <stage> <START|DONE|SKIP|NOTE|GATE PASS|GATE FAIL|CAP|STOP> <detail>`.

| Option | Meaning |
|---|---|
| `--from <stage>` | run that stage and everything after it; earlier stages must be done and unchanged |
| (none) | resume at the first stage that is not done; a done stage is re-hashed before it is skipped |
| `--smoke` | the whole chain on tiny plants in a temporary folder, fake transport, no Neo4j, no network |
| `--force g1\|g2\|cap\|band\|dirty-tree\|wrong-head` | smoke only: make one gate or cap fail, to prove the stop and the resume |

Environment: `E9_NEO4J_HOME` (the Neo4j server's home, for M7's store sizes; a real run refuses to start without it), `E9_ROOT` (output folder;
default is this one, the smoke uses a temporary one), `E9_PYTHON`, `NEO4J_URI/USERNAME/PASSWORD`,
`OPENROUTER_API_KEY` (read from the environment or `.env`, never printed).

## When it stops

Every stop writes `state/STOPPED` (stage, reason, the exact resume command) and ends the launch.

| Kind | Examples | What to do |
|---|---|---|
| needs the user | a composition band (U4), G1, G2, a frozen file changed, golden tests failed | design work; if part A changes, commit a new part A first; then run the resume command |
| top-up or restart | a run reached its cap, the $30 ledger or a step ceiling is used up, the balance is too low or unreadable | top up or raise nothing silently; then resume |
| infrastructure | Neo4j down, a command failed | fix the cause, then resume |

The launcher never commits, pushes, or writes into a first-measurement folder.

## Stages

| Stage | What | Gate | Step ceiling |
|---|---|---|---|
| M0 | drop `e7tune`; dev plants D100g21, D1000g21, X100g21s211; LINE-01; composition bands judged on the pooled plants of each scale (`composition --pool`, per-plant values printed only); golden re-ingest tests; API-02; pool memory probe | bands (U4), golden, API-02, memory | free |
| M1 | validation plants VAL100g21, VAL1000g21: V2T-A2 (2 tiers) and F1 (2 tiers), `tune-report`/`dev-report` | **G1** | $2.00 |
| M2 | EXP-0004 dev corpus, tau1/tau2 (`exp0004 tune`), D4 pilot on 20 pairs | D4 parse failures | $0.05 |
| M2b | judge pilot on every known first-measurement defect row (at least 8 per group) plus 20 controls | **G2** | audit ledger ($2.50 pilot) |
| M3 | E9 freeze and PREREG part B | clean tree, HEAD as part A names it | free |
| M4 | ladder, 10 sealed plants, d0/d50, 8 V corpora, question sets, pooled band report on the sealed plants (reported, not a gate), `T9.sha256` | I0 >= 0.99, LINE-01 | free |
| M5 | R4 ladder: V2T-A2 on 1/3/10/30, ContextRAG on 1/3/10, replays | health, replay identity | $4.90 |
| M6a | V2T-A2 on the ten sealed plants, replays | health, replay identity | $10.00 |
| M6b | F1 baseline on the same ten | same | $6.27 |
| M6c | duplication d0/d50, concurrency-1 control | same | $1.44 |
| M7 | INFRA: ingest repeats and probes (plant 1 per scale), database-only Cypher timing and agent replays on ten plants | none | free |
| M8a | P3: deciders D0, D1, D2, D4 on 8 V corpora | cap per corpus | $0.80 |
| M8b | P4: V2T-A2 on the five 1,000-sheet V plants, arms d0, d2, d4 | health, replay identity | $7.28 |
| M9 | EX01, five arms x 3 repeats | cap | $0.25 |
| M10a | scorer audit: select, judge, report | audit ledger ($10 less the pilot) | audit ledger |
| M10b | reports (sealed V2T-A2, F1 baseline, per-plant tune reports, ladder, duplication, E2E, concurrency-1), then the last Neo4j load: `H1000g21p1` with the `plant_lines` profile | none | free |

Every paid run: free dry run on a copy of the cache (counts cache misses) -> cap = misses x cost per question
(the first measurement's real spend per missed question: per tier, per identity arm in M8b, per plant size for ContextRAG in M5; `qa/exp0008/caps.py`)
x 1.5 -> cut to the step ceiling and the $30 runs ledger -> OpenRouter balance must cover the cap -> run ->
`run_config.json` must hold the code and corpus hashes (F7) -> health -> cache-only replay.

## Layout

`lib.sh`, `lib_plants.sh`, `lib_runs.sh` are sourced helpers; `stages/m*.sh` define `stage_<name>`;
`PREREG_A.template.md` is the pre-registration template. Outputs go to `state/`, `logs/`, `prereg/`, `corpora/`,
`neo4jplant/`, `questions/` and one folder per stage (`val/`, `tune/`, `ladder/`, `m6a/`, `m6b/`, `m6c/`, `infra/`,
`p3/`, `m8b/`, `ex01/`, `audit/`, `reports/`). Python helpers (ledger, balance, gates, freeze, part B) are
`python -m plantgraph.qa.exp0008.launcher <command>`; they have tests in `tests/qa/exp0008/`.

## Inputs a person prepares once

- `prereg/PREREG_A.md` and `prereg/seeds.json` (from the template and `draw_seeds`), committed.
- `inputs/pilot/` for M2b: `valves_ids.txt` (the VALVES_ON_PATH ids, at least 8), `runs.txt` (first-measurement run
  directories, one per line), `questions/<corpus>/questions.jsonl`, and `subgraphs.json` cut with
  `scripts/audit_export_subgraphs.py` on a `git archive 4dfad69` copy (`PYTHONPATH=<copy>/src`).

## After a stop in M10b

M10b runs every report, then loads the demo plant, and only then stops if a report failed (it names the failed
reports; the logs are `logs/report_<name>.txt`). Finished reports are skipped on a resume. To load the demo plant
alone (for example after a stop earlier in the stage, or to reset the database):
`sh data/runs/exp0008/demo_load.sh` (set `E9_NEO4J_HOME` as `launch.sh` does). It wipes the database and loads
`H1000g21p1` with the `plant_lines` profile.
