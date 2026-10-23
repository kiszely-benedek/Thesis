---
component: the sealed test run (EXP-0002-H100 / EXP-0002-H1000) — one-shot evaluation of the frozen cascade_v3 on the held-out corpora, its freeze, run protocol, analysis plan and violation rules (pre-registration)
status: accepted with ADR-0053 (user, 2026-10-11); frozen (hashed into F1.sha256) at F1
related: [ADR-0053 (proposed); ADR-0015, ADR-0035, ADR-0038, ADR-0044 U2, ADR-0045, ADR-0046, ADR-0047, ADR-0048, ADR-0050, ADR-0051, ADR-0052; cascade-v2.md; method-and-effort-cascade.md §7; question-aware-retrieval.md §8–§11; infra-cost.md]
date: 2026-10-11
author: architect (Opus 5.5)
---

# Design — the sealed test run

**After F1 this file is never edited.** Any change would break its hash in `F1.sha256`. What happens during and
after the run goes into `30-experiments/EXP-0002-sealed-test.md` and `_results.md`.

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| R1 | Policy under test | **`cascade_v3`** (primary). Beside it: `always_g_luna` (K1 comparator), `always_c_luna` (new policy file, Q5 comparator), `cascade_v3_iso` (dev-tuned label variant), random escalation and the oracle (references). All of them are offline joins of **two paid runs per corpus**. |
| R2 | Not run | GLM tiers, `always_n`, paid ContextRAG (ADR-0038: `DID_NOT_FIT`, free), `hier_agent` (dropped, ADR-0047). |
| R3 | Corpora | H100 = headline preset, `--target-sheets 100`, seed **2** (ADR-0045); H1000 = `--target-sheets 1000`, seed **0**. Rebuilt at the test-data commit. |
| R4 | Questions | **20 per family** × (18 dev + 6 held-out families), plus **10 per held-out wording**, fixed n. Candidate pool seed **31**, `--n-per-bin 200 --n-unanswerable 100` (as dev); per-family sampling seed **20261031**, dealt round-robin over k-bins (question-aware-retrieval §8.3). About 580 questions per corpus. |
| R5 | Run settings | Concurrency **4**; question deadline **120 s**; cutoff C = 120 s; LB-1 median ≤ 10 s; LB-2 p90 ≤ 60 s; one repeat; fresh cache `cache_sealed.sqlite`; experiment id `EXP-0002`. |
| R6 | Control | `ST-AG-H1000-C1`: agent tier, 48 H1000 questions (2 per family), concurrency 1, fresh cache. Measures latency under no concurrency and run-to-run agreement. Reported, not claimed. |
| R7 | Freeze | F1 = a user commit with a clean tree. `F1.sha256` covers the copied pins and params, the sealed file, this note and ADR-0053. After F1 only the gold-side paths of §6 may change (QAR-T10). The run script checks all of this and refuses to start on a mismatch. |
| R8 | Primary claim | **Q4 for `cascade_v3`**: acc@120(H1000) − acc@120(H100), CI contains 0 or lies above, **and** cost elasticity < 0.5. Secondary: K1, K2, K3, Q4 (other arms), Q5. Q1–Q3 are reported as not run. |
| R9 | Money and time | Estimated **$1.15**, caps **$2.90**. About 1.5 h of paid run time, plus two coder tasks before it (ST-T1, QAR-T10). |

## 1. Where things stand (evidence)

| # | Fact | Source |
|---|---|---|
| E1 | Dev acc@120 /180 (D100 / D1000). Luna: cascade_v3 176 / 175; cascade_v3_iso 178 / 177; always_g_luna 175 / 173; Cypher alone 132 / 129. GLM: cascade_v2 171 / 169; cascade_v2_iso 175 / 176; always_c 137 / 138; always_n 157 / 151 (raw). | `_results.md` CASCADE-V3, CYPL2, DEV10 |
| E2 | The dev report rerun with the CYPL2 Cypher runs (ADR-0052) and AGL3 gives cascade_v3 176 / 175, always_g_luna 175 / 173; both pass LB-1/LB-2. Latency median / p90: cascade_v3 7.2 / 17.0 s (D100), 7.6 / 17.5 s (D1000); always_g_luna 7.3 / 18.9 s, 7.6 / 23.2 s. $/question: cascade_v3 0.00055 / 0.00058; always_g_luna 0.00051 / 0.00063. cascade_v3 against random escalation (D100): +0.169 [+0.126, +0.212]. | architect dry run 2026-10-11, `cascade report` over `CYPL2-*`, `AGL3-*` (scratch output, no new calls) |
| E3 | The report as committed cannot do the test analysis yet, for five reasons: (a) the only paired comparison is against `always_n`, which is not run; (b) label policies need a need-aware run for labels (`cascade_v3_iso`: "Not evaluated"); (c) there is no `always_c_luna` policy file; (d) there is no per-split table, scale section or K/Q verdicts; (e) the dev verdicts S1–V3 show INCOMPLETE on other corpora. | same dry run; `cascade/report.py`, `join.py` |
| E4 | No F1 exists (`data/freeze/` is absent). QAR-T10 is not built (no held-out generators in `qa/questions/`). No run in `data/runs/cv1/runs/` names H100 or H1000. | file listing 2026-10-11 |
| E5 | Measured dev rates per question: Cypher (Luna) $0.000389 / $0.000398, summed latency 6.3 / 6.5 s; agent (Luna, final high) $0.000511 / $0.000627, 10.1 / 11.5 s; highest agent question $0.0074. | `CYPL2-*`, `AGL3-*` `answers.jsonl` (computed 2026-10-11) |
| E6 | The harness refuses a Neo4j store that is not exactly the run's corpus and profile before any call. The join refuses tiers whose source graph, pin, primer or shared prompts differ. `environment.jsonl` records concurrency, clock and machine. | `harness/cypher_setup.py`, `cascade/checks.py`, `CYPL2-D1000/environment.jsonl` |
| E7 | INFRA-1: ContextRAG prompt 1.70M / 16.65M characters at 101 / 1,000 sheets; local compute ≤ 0.5 % of latency. | `_results.md` INFRA-1 |

## 2. The seal — what the planner did

ADR-0035 and question-aware-retrieval §9 settle who may open `heldout-families.sealed.md`: **only the coder of
QAR-T10, after F1**. The user may read it at any time. The architect therefore **did not open it.** Three facts
for the record:

1. sha256 computed 2026-10-11: `905c7984dfc1d346cb696c47590d972d545455fd1149517534ad2309955ff63b`. It equals the
   ADR-0035 value, so the seal is intact.
2. A content search over `docs/private/` printed one line of the file, line 26, by accident. The line is a
   generic sampling sentence ("ADR-0029 (at most one question per family, source anchor and k-bin; target drawn
   with a seeded rng)"). It names no family, template or reference. The architect writes no strategy code, and
   F1 freezes all strategy code, so the line cannot affect any result. It is disclosed here anyway.
3. After F1 the main session may read QAR-T10's diff to review it. That is safe because no strategy-side file
   may change after F1 (§6). The main session reads the sealed file itself only after the four runs are
   complete.

## 3. Deviations from earlier pre-registrations (to be stated in the thesis)

| # | Pre-registered | What happens | Why | When decided |
|---|---|---|---|---|
| D1 | ADR-0048 V2: highest acc@120 among eligible candidates on D100 → `cascade_v3_iso` (178 vs 176); V3 on D1000 gives the same (177 vs 175) | **`cascade_v3` is primary** | The user (2026-10-11): label routing is comparison only. The rules classifier was written from the dev templates, so its held-out behaviour is unmeasured (ADR-0046's own argument). cascade_v3 is within V3's 2-question tolerance on both corpora. | after dev results, before any test data |
| D2 | The candidate set fixed in cascade-v2 §9.2 (GLM) | Luna candidates, through ADR-0050 | Latency (user, 2026-10-10); a bake-off with a rule shown before the run | after dev results, before any test data |
| D3 | ADR-0035 U1: 10, then 20 "if informative" | 20 fixed | Removes optional stopping; costs cents | before any test data |
| D4 | ADR-0035 Q1–Q3 (need-aware Hierarchical, `hier_agent`) | not run, reported as "not run" | Arms dropped by ADR-0047 and ADR-0048 | — |
| D5 | ADR-0035 Q5 arms `graph_agent` − `cypher_rag` | `always_g_luna` − `always_c_luna` | The same question (typed API vs free-form Cypher) on today's arms | before any test data |
| D6 | ADR-0035 F1: `qar-freeze.json` + a pytest | commit + `sha256sum` + allowed diff, enforced by the run script | §6 | before any test data |
| D7 | ADR-0015 must-tier: ContextRAG, CypherRAG and Hierarchical at ~10/100/1,000 sheets | ContextRAG `DID_NOT_FIT` (ADR-0038); Hierarchical only on dev; the ~10-sheet anchor and EXP-0001 not in this run | ADR-0038, ADR-0048 | — |

## 4. Arms and what each answers

| Arm (offline join) | Tier runs used | Answers |
|---|---|---|
| `cascade_v3` | ST-CYP + ST-AG | the system; Q4 (primary); K1–K3 |
| `always_g_luna` | ST-AG | K1 comparator; Q4; Q5 |
| `always_c_luna` (new file) | ST-CYP | Q5 comparator; Q4; "Cypher alone" |
| `cascade_v3_iso` | ST-CYP + ST-AG + rules labels from the question text | dev-tuned variant; what label routing does on held-out families |
| random escalation, oracle | ST-CYP + ST-AG | K2; regret |

The scale reading comes for free from the same runs: tier-1 acceptance share and precision per corpus and per
k-bin, latency growth and cost elasticity. This is what supports the thesis claim. A cheap structured query
settles a share of the questions, that share and its precision move with the plant, and the agent covers the
rest.

## 5. Questions

- **Corpora** (free, rebuilt at the test-data commit T). Occurrence profile with `--check --no-neo4j` for the
  agent tier; plant profile loaded into Neo4j for the Cypher tier. The counts are compared with the 2026-10-04
  records (H100 100 sheets / 4,226 nodes; H1000 1,001 / 42,044). A difference is recorded, not fixed.
- **Families.** dev-old 12 + dev-new 6 + held-out 6 at 20 each; held-out wordings at 10 each (should-tier,
  ADR-0035).
- **Sampling.** The candidate pool is built as for dev, but with the fresh seed 31. Per family: candidates are
  sorted by id, shuffled with `Random(20261031)`, then dealt round-robin over the k-bins present. With fewer than
  n candidates, all are taken.
- **Splits.** `splits.json` next to `questions.jsonl`, mapping question_id → `dev-old | dev-new | held-out |
  held-out-wording`. Question ids are unique across splits, so a wording id carries its template id.
- **Headline set** = dev-old ∪ dev-new ∪ held-out, minus LOOP_ACTUATED_VALVE (ADR-0044 U2). About 460 per corpus.
  All-question figures are reported beside it for comparison with the dev /180 numbers.
- **C1 subset** = 2 per family from the headline splits of H1000, same seed: 48 questions.

## 6. The freeze

**Frozen at F1** (the user's commit after ST-T1, working tree clean):
- Every tracked file under `src/` except the gold-side allowed list below. That covers strategies, agent, plant
  API, prompts (including the final-answer prompt, legend and primer), `qa/cascade/` (policies, join, report and
  the claims constants of ST-T1), harness runner, attempt, usage meter, pool and spend cap, `llm/`, scoring,
  ingest, generator, splitter, resolver and store.
- Untracked inputs, copied to `data/runs/sealed/inputs/` and hashed: the Cypher pin (`pins_bakeoff/F_cypher.json`,
  Luna low; pin hash `acf24178…`), the agent pin (`pin_luna_final_high.json`; `ffc026d3…`),
  `params_cypher_plant.json` (`timeout_s` 30, `row_cap` 200), `params_agent_low.json` (`max_steps` 40). F1 checks
  that the pin hashes equal `cascade_v3.json`'s `pin_sha256`.
- Documents hashed: the sealed file (must stay `905c79…f63b`), this note, ADR-0053 (accepted before F1).
- Parameters, as written in §0 and §5 and enforced by `run_config.json` (deadline, pins, params, prompt hashes,
  question hash) and by the script (concurrency, seeds, n, caps).

**Allowed to change after F1, by QAR-T10 only:** `src/plantgraph/qa/questions/**`,
`src/plantgraph/qa/harness/family_meta.py`, `src/plantgraph/qa/harness/need_gold.py`,
`src/plantgraph/qa/models.py` (**new `QuestionFamily` members only**; the main session reads the diff), and
`tests/**`.

**Recorded where.** `data/runs/sealed/F1.commit`, `F1.sha256`, `T.commit`, `T.sha256` (corpora `ingest.json`,
question files, `splits.json`, the C1 subset), `logs/models_py_diff.txt`, plus every run's `run_config.json` and
`environment.jsonl`.

## 7. Steps (in order; executable today)

| # | Who | Step | Paid |
|---|---|---|---|
| 0 | main | Preflight: `git status` clean; seal hash check; read the OpenRouter balance and the Luna listing (price, context length) into `data/runs/sealed/openrouter-luna-<date>.json`; recompute §8 if the price moved | no |
| 1 | user | Accept ADR-0053 (main session sets `status: accepted`) | — |
| 2 | coder | **ST-T1** (§11). Then the free dev check: the report with `--sealed-claims` on D100/D1000 reproduces E1/E2 | no |
| 3 | user | Commit ST-T1 → **F1** | — |
| 4 | main | `freeze_f1.sh` (§7.1) | no |
| 5 | coder | **QAR-T10** (§11), given the sealed file's path by the main session | no |
| 6 | main → user | Allowed-diff check, review of the `models.py` diff; the user commits → **T** | — |
| 7 | main | `make_test_set.sh` (§7.2): corpora, questions, splits, C1 subset, `T.sha256` | no |
| 8 | main | `run_sealed.sh` (§7.3): load H100 → ST-CYP-H100 (smoke stage, then full) → replay → load H1000 → ST-CYP-H1000 → replay → ST-AG-H100 (smoke, then full) → ST-AG-H1000 → ST-AG-H1000-C1 → agent replays → restore D1000 → report | **yes** |
| 9 | main | `_results.md` rows EXP-0002-H100, EXP-0002-H1000, SEALED-CLAIMS, LAT-CTRL-1; `30-experiments/EXP-0002-sealed-test.md`; `/log-progress`; chat summary in Hungarian | no |

No pytest runs from step 7 until the D1000 restore has finished. The coders' tests run in steps 2 and 5, before
any load.

### 7.1 `data/runs/sealed/freeze_f1.sh` (free)

```sh
#!/bin/sh
# F1 freeze (ADR-0053 point 5). Run once, right after the user's ST-T1 commit.
set -eu
S=data/runs/sealed; C=data/runs/cv1; P=.venv/Scripts/python
die() { echo "ERROR: $*" >&2; exit 1; }
[ ! -e $S/F1.commit ] || die "F1 already exists; never overwrite it"
[ -z "$(git status --porcelain)" ] || die "commit first: the working tree is not clean"
mkdir -p $S/inputs $S/logs
git rev-parse HEAD > $S/F1.commit
cp $C/pins_bakeoff/F_cypher.json $S/inputs/pin_cypher_luna_low.json
cp $C/pin_luna_final_high.json $S/inputs/pin_agent_luna_final_high.json
cp $C/params_cypher_plant.json $C/params_agent_low.json $S/inputs/
$P - <<'EOF'
import json
from pathlib import Path
from plantgraph.llm.models import ModelPin
policy = json.loads(Path("src/plantgraph/qa/cascade/policies/cascade_v3.json").read_text(encoding="utf-8"))
pins = {"cypher-luna": "pin_cypher_luna_low.json", "agent-luna": "pin_agent_luna_final_high.json"}
for tier in policy["tiers"]:
    text = Path("data/runs/sealed/inputs", pins[tier["name"]]).read_text(encoding="utf-8")
    found = ModelPin.model_validate_json(text).pin_hash()
    assert found == tier["pin_sha256"], f"{tier['name']}: pin {found} is not the policy's"
print("pins match cascade_v3")
EOF
sha256sum $S/F1.commit $S/inputs/* docs/private/40-design/heldout-families.sealed.md \
  docs/private/40-design/sealed-test-run.md docs/private/20-decisions/ADR-0053-sealed-test-run-protocol.md \
  > $S/F1.sha256
grep -q 905c7984dfc1d346cb696c47590d972d545455fd1149517534ad2309955ff63b $S/F1.sha256 || die "the seal hash changed"
date -u +%Y-%m-%dT%H:%M:%SZ > $S/F1.time
cat $S/F1.commit $S/F1.time
```

### 7.2 `data/runs/sealed/make_test_set.sh` (free; after the user's QAR-T10 commit)

```sh
#!/bin/sh
# Test corpora and questions at commit T (ADR-0053; design section 5).
set -eu
S=data/runs/sealed; P=.venv/Scripts/python
ALLOWED='^(src/plantgraph/qa/questions/|src/plantgraph/qa/harness/(family_meta|need_gold)\.py$|src/plantgraph/qa/models\.py$)'
die() { echo "ERROR: $*" >&2; exit 1; }
[ ! -e $S/T.commit ] || die "T already exists; never overwrite it"
[ -z "$(git status --porcelain)" ] || die "commit first: the working tree is not clean"
sha256sum -c --quiet $S/F1.sha256 || die "a frozen input changed since F1"
bad=$(git diff --name-only "$(cat $S/F1.commit)" HEAD -- src | grep -v -E "$ALLOWED" || true)
[ -z "$bad" ] || die "frozen paths changed since F1: $bad"
git diff "$(cat $S/F1.commit)" HEAD -- src/plantgraph/qa/models.py > $S/logs/models_py_diff.txt
git rev-parse HEAD > $S/T.commit
for spec in "H100 100 2" "H1000 1000 0"; do
  set -- $spec
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$2" --seed "$3" --corpus-id "$1" \
    --check --no-neo4j --out "$S/corpora/$1" > "$S/logs/corpus_$1.json" || die "corpus $1 failed"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$1" --ingest-json "$S/corpora/$1/ingest.json" \
    --seed 31 --n-per-bin 200 --n-unanswerable 100 --n-per-family 20 --n-per-wording 10 \
    --sample-seed 20261031 --out "$S/questions/$1" --pool-out "$S/qpool/$1" || die "questions $1 failed"
done
$P -m plantgraph.qa.questions.per_family --in $S/questions/H1000/questions.jsonl \
  --splits $S/questions/H1000/splits.json --only-splits dev-old,dev-new,held-out \
  --n 2 --seed 20261031 --out $S/questions_c1/H1000
sha256sum $S/T.commit $S/corpora/*/ingest.json $S/questions/*/* $S/questions_c1/H1000/questions.jsonl > $S/T.sha256
cat $S/questions/*/availability.json | head -80   # per-family n actually drawn
```

### 7.3 `data/runs/sealed/run_sealed.sh` (**paid**; resumable: re-running it resumes each run under the same id)

```sh
#!/bin/sh
# Sealed test run, EXP-0002-H100 / EXP-0002-H1000 (ADR-0053). PAID.
# Do NOT run pytest while this runs. One corpus in Neo4j at a time; ends with D1000 (plant) loaded.
set -eu
S=data/runs/sealed; P=.venv/Scripts/python; IN=$S/inputs
H="$USERPROFILE/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
CACHE=$S/cache_sealed.sqlite
ALLOWED='^(src/plantgraph/qa/questions/|src/plantgraph/qa/harness/(family_meta|need_gold)\.py$|src/plantgraph/qa/models\.py$)'
die() { echo "ERROR: $*" >&2; exit 1; }

preflight() {
  [ -z "$(git status --porcelain)" ] || die "the working tree is not clean"
  [ "$(git rev-parse HEAD)" = "$(cat $S/T.commit)" ] || die "HEAD is not the test-data commit T"
  sha256sum -c --quiet $S/F1.sha256 || die "a frozen input changed since F1"
  sha256sum -c --quiet $S/T.sha256 || die "a test input changed since it was generated"
  bad=$(git diff --name-only "$(cat $S/F1.commit)" HEAD -- src | grep -v -E "$ALLOWED" || true)
  [ -z "$bad" ] || die "frozen paths changed since F1: $bad"
  mkdir -p $S/logs $S/runs $S/replays $S/neo4jplant
}

load() {  # load <corpus> <sheets> <seed>: this corpus alone in Neo4j, plant profile, fresh database
  echo "=== $(date +%T) load $1"
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$2" --seed "$3" --store-profile plant \
    --corpus-id "$1" --fresh-database --neo4j-home "$H" --out "$S/neo4jplant/$1" \
    > "$S/logs/load_$1.json" 2> "$S/logs/load_$1.err" || die "loading $1 failed, see $S/logs/load_$1.err"
}

health() {  # health <run-dir>: outcome counts only, never correctness; stops on a technical fault
  $P - "$1/answers.jsonl" <<'EOF'
import collections, json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
counts = collections.Counter(row["outcome"] for row in rows)
print(f"    {len(rows)} rows: {dict(counts)}")
broken = counts.get("PROVIDER_ERROR", 0) + counts.get("PARSE_FAILURE", 0)
if not rows or broken > 0.1 * len(rows) or counts.get("RETRIEVAL_ERROR", 0) > 0.6 * len(rows):
    sys.exit("technical fault: read the run log; see design section 10 before anything else")
EOF
}

finish() {  # finish <run-id> <exit-code> <stage>: a smoke stage ends at its cap (3); a full stage must not
  case "$2:$3" in
    0:*) echo "    $1: complete" ;;
    3:smoke) echo "    $1: smoke stage done" ;;
    3:full) die "$1 reached its spend cap: ask the user before resuming with a higher cap" ;;
    *) die "$1 failed with exit code $2, see $S/logs/$1.log" ;;
  esac
  health "$S/runs/$1"
}

cypher() {  # cypher <run-id> <corpus> <cap> <stage>
  echo "=== $(date +%T) $1 ($4, cap \$$3)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0002 --corpus "$2:test" \
    --strategy cypher_rag_plant --strategy-params-json $IN/params_cypher_plant.json \
    --pin-json $IN/pin_cypher_luna_low.json --corpora-root $S/neo4jplant --questions-root $S/questions \
    --runs-root $S/runs --cache-path $CACHE --allow-paid-calls --cost-per-question-usd 0.001 \
    --max-spend-usd "$3" --concurrency 4 --question-deadline-s 120 >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$4"
}

agent() {  # agent <run-id> <corpus> <cap> <stage> [<questions-root> <cache> <concurrency>]
  echo "=== $(date +%T) $1 ($4, cap \$$3)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0002 --corpus "$2:test" \
    --strategy graph_agent_low_steps --strategy-params-json $IN/params_agent_low.json \
    --pin-json $IN/pin_agent_luna_final_high.json --corpora-root $S/corpora \
    --questions-root "${5:-$S/questions}" --runs-root $S/runs --cache-path "${6:-$CACHE}" --allow-paid-calls \
    --cost-per-question-usd 0.003 --max-spend-usd "$3" --concurrency "${7:-4}" --question-deadline-s 120 \
    >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$4"
}

replay() {  # replay <run-id> <strategy> <params> <pin> <corpora-root> <corpus>: cache-only, concurrency 1
  id=INF-$1; rc=0
  echo "=== $(date +%T) replay $id (no --allow-paid-calls: cache only)"
  $P -m plantgraph.qa.harness --run-id "$id" --experiment EXP-0002-REPLAY --corpus "$6:test" \
    --strategy "$2" --strategy-params-json "$3" --pin-json "$4" --corpora-root "$5" \
    --questions-root $S/questions --runs-root $S/replays --cache-path $CACHE --concurrency 1 \
    --question-deadline-s 120 > "$S/logs/$id.log" 2>&1 || rc=$?
  sed -e "s/^{\"run_id\":\"$id\"/{\"run_id\":\"$1\"/" -e 's/"from_cache":false/"from_cache":true/g' \
    "$S/replays/$id/answers.jsonl" > "$S/replays/$id/.normalised" 2>/dev/null || true
  if [ $rc -eq 0 ] && sed 's/"from_cache":false/"from_cache":true/g' "$S/runs/$1/answers.jsonl" \
      | cmp -s - "$S/replays/$id/.normalised"; then echo identical > "$S/replays/$id/replay_check.txt"
  else echo "different_or_miss rc=$rc" > "$S/replays/$id/replay_check.txt"; fi
  rm -f "$S/replays/$id/.normalised"; echo "    $id: $(cat $S/replays/$id/replay_check.txt)"
}

preflight
load H100 100 2
cypher ST-CYP-H100 H100 0.02 smoke
cypher ST-CYP-H100 H100 0.50 full
replay ST-CYP-H100 cypher_rag_plant $IN/params_cypher_plant.json $IN/pin_cypher_luna_low.json $S/neo4jplant H100
load H1000 1000 0
cypher ST-CYP-H1000 H1000 0.50 full
replay ST-CYP-H1000 cypher_rag_plant $IN/params_cypher_plant.json $IN/pin_cypher_luna_low.json $S/neo4jplant H1000
agent ST-AG-H100 H100 0.02 smoke
agent ST-AG-H100 H100 0.80 full
agent ST-AG-H1000 H1000 1.00 full
agent ST-AG-H1000-C1 H1000 0.10 full $S/questions_c1 $S/cache_sealed_c1.sqlite 1
replay ST-AG-H100 graph_agent_low_steps $IN/params_agent_low.json $IN/pin_agent_luna_final_high.json $S/corpora H100
replay ST-AG-H1000 graph_agent_low_steps $IN/params_agent_low.json $IN/pin_agent_luna_final_high.json $S/corpora H1000
echo "=== $(date +%T) restore D1000 (plant profile) alone in Neo4j"
$P -m plantgraph.ingest synthetic --headline --target-sheets 1000 --seed 1 --store-profile plant \
  --corpus-id D1000 --fresh-database > $S/logs/restore_D1000.json 2> $S/logs/restore_D1000.err \
  || die "restoring D1000 failed"
POL=src/plantgraph/qa/cascade/policies
$P -m plantgraph.qa.cascade report --sealed-claims \
  --policy $POL/cascade_v3.json --policy $POL/always_g_luna.json --policy $POL/always_c_luna.json \
  --policy $POL/cascade_v3_iso.json --corpus H100 --corpus H1000 \
  --questions-root $S/questions --corpora-root $S/corpora --cutoff-s 120 --out $S/report \
  --run H100:cypher-luna=$S/runs/ST-CYP-H100 --run H100:agent-luna=$S/runs/ST-AG-H100 \
  --run H1000:cypher-luna=$S/runs/ST-CYP-H1000 --run H1000:agent-luna=$S/runs/ST-AG-H1000 \
  > $S/logs/report.stdout.txt || die "report failed"
echo "=== $(date +%T) done: $S/report/report.md"
```

Notes on the script.
- The order is by tier, with each tier's two corpora back to back. Provider-side drift then affects H100 and
  H1000 alike.
- The smoke stage spends at most $0.02 per tier on the first questions of the real run and checks outcome
  counts only. The full stage resumes the same run id; the cap is one of the fields allowed to change.
- The cache-only replays at concurrency 1 serve two purposes: they prove the run is reproducible (byte identity,
  ADR-0051) and they give clean local compute. The C1 control has its own cache, so its calls are live.

## 8. Cost and time (estimates from E5; caps ≈ 2–2.7×, because held-out families may need more agent steps)

| Run | Questions | Estimate | Cap | Wall time (sum of latencies / 4) |
|---|---|---|---|---|
| ST-CYP-H100 | ~580 | $0.23 | $0.50 | ~15 min |
| ST-CYP-H1000 | ~580 | $0.23 | $0.50 | ~16 min |
| ST-AG-H100 | ~580 | $0.30 | $0.80 | ~24 min |
| ST-AG-H1000 | ~580 | $0.36 | $1.00 | ~28 min |
| ST-AG-H1000-C1 | 48 | $0.03 | $0.10 | ~9 min (concurrency 1) |
| **Total** | | **≈ $1.15** | **$2.90** | **≈ 1.5 h** plus loads, question build and replays (~15 min) |

All figures are arithmetic on measured dev rates. Held-out families are unmeasured, which is why the caps are
wide. The figures are re-read against the Luna price on the run day (step 0).

## 9. Analysis plan (pre-registered; implemented by ST-T1 before F1, run unchanged after the test)

All accuracy is **acc@120**. Costs are the total cost per question as first billed. Latency is summed over every
call of every tier tried, plus local compute. Bootstrap: the report's fixed seed and draw count. Claims are
computed on the headline set and repeated on the held-out split. All tables cover both corpora.

| Table | Content |
|---|---|
| T1 headline | per policy: headline n, acc@120 with a 95 % CI, all-question acc@120, $/question, latency median/mean/p90/p95/max, LB-1/LB-2, answered-by shares, tier-1 acceptance share and precision |
| T2 splits | per policy × {dev-old, dev-new, held-out, held-out-wording}: correct/n, acc with CI; generalisation gap (dev − held-out), unpaired bootstrap CI |
| T3 scale | per policy: acc(H1000) − acc(H100) with an unpaired CI; cost elasticity e = ln(c₁₀₀₀/c₁₀₀)/ln(s₁₀₀₀/s₁₀₀), sheets from the corpus record, with a CI; latency median and p90 ratio; tier-1 share and precision per corpus and per k-bin |
| T4 claims | below; PASS/FAIL with the pre-registered wording |
| T5 per family | correct/n per policy and corpus |
| T6 cost | token cost from the runs; infrastructure from INFRA-1 (same sizes) plus test ingest stage times; ContextRAG prompt size against Luna's listed window (ADR-0038) |
| T7 isolation | secondary score "control valves do not isolate" (ADR-0048 U4) |
| T8 diagnostics | agent stop reasons, abandoned calls against late charges, made-up yes, providers that served calls, replay identity, the C1 latency difference (paired median and CI) and answer agreement on 48 |
| T9 dev vs test | the same arms' dev numbers beside the test numbers (reported, not claimed) |

**Claims** (H1000 = the claims corpus; paired 95 % CIs unless stated):

| # | Claim | Supported if | Wording if not |
|---|---|---|---|
| **Q4 (primary)** | `cascade_v3` keeps accuracy and cost from H100 to H1000 | acc diff CI contains 0 or lies above **and** e < 0.5 | "accuracy falls with scale" / "cost grows near-linearly with the plant" |
| Q4′ | the same, for `always_g_luna`, `always_c_luna`, `cascade_v3_iso` | as above | as above |
| K1 | the cascade against always-agent | acc CI contains 0 or lies above, **and** mean cost and mean latency both lower (CIs exclude 0) | "the cascade loses accuracy" / "the cascade saves nothing" |
| K2 | the self-flags route better than chance | cascade − random escalation at the same tier-2 share > 0, CI excludes 0 | "the self-flags route no better than chance" |
| K3 | the latency bound holds at plant scale | LB-1 and LB-2 met at H1000 (point estimates; CIs of median and p90 reported) | "the cascade is not fast enough at plant scale" |
| Q5 | a typed plant API beats free-form Cypher | `always_g_luna` − `always_c_luna` > 0, CI excludes 0 | "free-form Cypher matches the typed API" |
| Q1–Q3 | — | **not run** (ADR-0047, ADR-0048) | — |

With seven claims on shared questions, a CI may exclude 0 by chance. Only Q4 for `cascade_v3` is the primary
claim. Rough power: at accuracy ≈ 0.97 and n ≈ 460, an unpaired difference has a 95 % half-width of about ±0.022
(arithmetic: 1.96·√(2·0.97·0.03/460)), so Q4 can detect a drop of about 2–3 points. Dev forecast, which binds
nothing: K1's cost condition is at risk (E2).

## 10. Protocol violations and the technical-abort rule

**Violations.** Each one makes the affected numbers post hoc: they are reported separately and labelled, and a
new ADR is needed.
1. Any change between F1 and a sealed run's commit outside the allowed list. A `models.py` change that is more
   than new `QuestionFamily` members. Any sealed `run_config.json` with `git_dirty: true`.
2. A sealed run whose pin, params, deadline, concurrency or question file differs from §0/§5 or from the
   manifests.
3. Starting a second run of the same tier and corpus under a new id after any of its answers exist, except under
   the abort rule below. Choosing between two runs.
4. Changing, dropping or replacing questions or families after their answers exist. A family that cannot be
   generated or scored must be dropped from `availability.json` evidence **before** any run starts.
5. Changing the analysis after test answers exist: report code, cutoff, bounds, headline set, primary policy,
   claims. Extra analyses are allowed only when labelled "exploratory".
6. Any LLM call on a sealed question outside the five runs, including demo or debugging use. The demo keeps D1000.
7. Anyone who writes strategy code reading the sealed file before F1.

**Technical abort** (the only allowed restart). Abort applies only to a run that fails the `health` check
(provider or parse errors > 10 % of rows, or retrieval errors > 60 %), crashes, or ran against a wrong store. It
is decided from logs and outcome counts, never from correctness. The run is kept and reported as "aborted",
together with the cause. After the cause is fixed **without touching a frozen path**, the run restarts under the
next id (`…-r2`). A second abort on the same run stops the protocol, and the user decides. A spend-cap stop is not
an abort: the run resumes under the same id once the user approves a higher cap.

## 11. Coder tasks (Sonnet, one at a time, offline tests; ruff, mypy --strict and pytest green)

| # | When | Task | Files | Acceptance |
|---|---|---|---|---|
| **ST-T1** | before F1 | (a) `policies/always_c_luna.json`: one tier `cypher-luna`, pin `acf24178d47dd4873fc2a36e7f67efbf2dc7ab5de694711f3b934e6ef4f4c21d`, accept answered/not_abstained/rows. (b) The report builds an anchor finder from `--corpora-root` and passes it to `join_corpus`, so label policies are evaluated without a need-aware run. (c) `--sealed-claims`: claims constants in a new `report_claims.py` (primary `cascade_v3`, tier-2 comparator `always_g_luna`, Cypher comparator `always_c_luna`, claims corpus = last `--corpus`, scale = first → last, headline exclusion `LOOP_ACTUATED_VALVE`, headline splits dev-old, dev-new, held-out); paired-bootstrap sections for K1 and Q5; per-policy acc CI; `splits.json` read from `<questions_root>/<corpus>/` when present (split tables and the generalisation gap); scale section (T3); claims table (T4) on the headline set and on held-out; dev rules S1–V3 omitted under this flag. (d) `python -m plantgraph.qa.questions.per_family`: `--in`, `--n`, `--seed`, `--out`, optional `--splits` / `--only-splits`; §5 algorithm; deterministic bytes. | `qa/cascade/{cli,report,report_claims,report_render,report_models,join}.py`, `policies/always_c_luna.json`, `qa/questions/per_family.py`, tests | Toy fixtures: e = ln 2 / ln 10 = 0.301 for doubled cost at ×10 sheets; claim verdicts on hand-made numbers, including CI boundary cases; the headline exclusion counts; split tables; the gold-flip metamorphic test stays byte-identical; the import ban holds; the sampler is byte-identical for the same seed and takes all candidates when there are fewer than n. **Local check** (skipped without `data/`): `--sealed-claims` on D100/D1000 with `CYPL2-*`/`AGL3-*` gives cascade_v3 176/175, always_g_luna 175/173, always_c_luna 132/129. cascade_v3_iso is 178/177 with finder labels; if the finder labels differ from DEV10's trace labels on any of the 360 questions, print the count and stop. |
| **QAR-T10** | after F1 | Open `heldout-families.sealed.md`. Build the held-out families and held-out wordings as **question-side code only**. New `QuestionFamily` members in `qa/models.py` (nothing else there). `family_meta` split and `need_gold` for the new families. `python -m plantgraph.qa.questions.sealed_set` (flags as §7.2): builds the pool with the held-out families behind an explicit opt-in, samples with ST-T1's sampler, gives wordings unique ids that carry their template id, writes `questions.jsonl`, `splits.json` and `availability.json` (n drawn per family; families dropped as unscorable, with the reason). | only the allowed paths of §6 | The default `python -m plantgraph.qa.questions` output for D100 at seed 1 is byte-identical before and after. Held-out references are checked by hand on a toy plant. Ids are unique, and `splits.json` covers each question exactly once. Every held-out question uses an existing `AnswerType`. The import ban holds. `git diff --name-only <F1> -- src` lists only allowed paths. |

The ADR-0035 freeze-manifest test is replaced by the script checks (ADR-0053 point 5).

## 12. Open user decisions (recommendation first)

- **U1** Accept ADR-0053: `cascade_v3` primary, with the deviation from V2 stated; `cascade_v3_iso` as the
  dev-tuned comparison. Recommended.
- **U2** 20 per family fixed, wordings 10 (~580 questions per corpus), ≈ $1.15, caps $2.90. Recommended.
  Alternative: 10 per family (≈ $0.6, about √2 wider CIs).
- **U3** Concurrency 4 plus the 48-question concurrency-1 control. Recommended. Alternative: concurrency 1
  throughout (≈ 5–6 h).
- **U4** No GLM replication and no `always_n` on test. Recommended. Alternative: a GLM replication of both tiers
  (≈ $1.5, ≈ 1.5 h more).
- **U5** Two commits by the user: ST-T1 (= F1) and QAR-T10 (= T). The main session prints the commands.

## 13. Open questions

- **O1** The Luna price and listed context window on the run day (step 0). They are needed for T6 and for
  re-reading §8.
- **O2** EXP-0001 (single sheet, ChatP&ID's end of the claim) has no result row. The claim's inversion needs it.
  It is outside this run and needs its own plan (ADR-0044 U3, EX01 control valves).
- **O3** Run-to-run variance of Luna (no temperature) is measured only by the 48-question control. A full second
  repeat would cost about $0.6 per corpus and is not planned.
- **O4** Offline join against live cascade: the offline tier 2 had its own full 120 s, while live it would get
  120 s minus tier 1's time. The summed-latency cutoff scores such cases wrong. Stated as a threat, as in
  cascade-v2.

## 14. Figures and sources

| Figure | Source |
|---|---|
| Dev acc@120 rows, LB results, tier-1 precision | `_results.md` CASCADE-V3, CYPL2, MODEL-SWITCH-R3, DEV10 |
| E2 medians, p90s, $/q, random-escalation difference, K1 dev forecast | architect dry run of `cascade report` 2026-10-11 over `CYPL2-*`, `AGL3-*` (scratch, no calls) |
| Per-question costs and latency sums (E5), highest agent question $0.0074 | `data/runs/cv1/runs/{CYPL2,AGL3}-*/answers.jsonl`, computed 2026-10-11 |
| H100 / H1000 counts on 2026-10-04 | `data/runs/cv1/corpora/{H100,H1000}/ingest.json` |
| ContextRAG prompt sizes, local-compute share | `_results.md` INFRA-1 |
| Seal hash | `sha256sum` 2026-10-11, equal to ADR-0035 |
| Estimates in §8, ±0.022 | arithmetic on the rows above — **estimates** |
