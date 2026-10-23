#!/bin/sh
# INF-T4: the infrastructure-cost measurement (design infra-cost.md section 7). ZERO paid calls.
#
# Do NOT run pytest while this script runs: the integration tests write to the same Neo4j, and
# --fresh-database below would destroy their fixtures (and the tests would corrupt the sizes).
# Keep the laptop plugged in, in one Windows power mode, with no other heavy process.
#
# Per corpus (D100, D1000, D4000) the script
#   1. ingests REPS times with --fresh-database --neo4j-home (the last repeat stays loaded);
#   2. D100 and D1000 only: replays AGL3 and DEV10 cache-only at concurrency 1 and records in
#      <run>/replay_check.txt whether answers.jsonl equals the source byte for byte. The Cypher
#      tier is measured from CYPL2 (the runs after the canonical row order, ADR-0052): its answer
#      prompts no longer depend on the store layout, so CYPL2 is replayed through the cache like
#      the others (INF-CYPL2-<c>, full local compute). In addition `infra-cypher-replay`
#      re-executes the stored queries: DATABASE TIME ONLY, no model call (INF-CYPL2DB-<c>), shown
#      beside it in the report as a lower bound;
#   3. times the live-cascade startup REPS times (infra-probe) and measures memory once.
# D4000 gets steps 1 and 3 only (no questions exist for it). At the end it re-ingests D1000, so
# Neo4j holds exactly one corpus, the one the demo expects.
#
# Overrides (the smoke test uses them): INFRA_ROOT, REPS, CORPORA, NEO4J_HOME.
set -eu

R=data/runs/cv1
P=.venv/Scripts/python
INFRA=${INFRA_ROOT:-$R/infra}
REPS=${REPS:-3}
CORPORA=${CORPORA:-"D100 D1000 D4000"}
NEO4J_HOME=${NEO4J_HOME:-"$USERPROFILE/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"}
RUNS=$INFRA/runs            # replay runs: a new folder, so no existing run is overwritten
PLANT_CORPORA=$R/neo4jplant # plant-profile ingest.json files (the Cypher tier refuses the others)
OCC_CORPORA=$R/corpora      # occurrence-profile ingest.json files (the agent and need tiers)
PROBE_CORPORA=$INFRA/corpora # ingest.json of each repeat's last ingest, for the probes
POLICY=cascade_v3

die() { echo "ERROR: $*" >&2; exit 1; }

sheets_of() {  # the --target-sheets of a corpus id
  case $1 in D100) echo 100 ;; D1000) echo 1000 ;; D4000) echo 4000 ;; *) die "unknown corpus $1" ;; esac
}

preflight() {
  [ -x "$P" ] || [ -f "$P.exe" ] || die "expected $P, found no project interpreter"
  [ -d "$NEO4J_HOME" ] || die "expected the Neo4j home at $NEO4J_HOME, found none"
  [ -f "$NEO4J_HOME/metrics/neo4j.dbms.page_cache.usage_ratio.csv" ] \
    || die "expected the page-cache metric under $NEO4J_HOME/metrics, found none"
  for c in $CORPORA; do
    [ ! -e "$INFRA/ingest/$c" ] || die "$INFRA/ingest/$c exists; refusing to overwrite a measurement"
    [ ! -e "$INFRA/probe/$c" ] || die "$INFRA/probe/$c exists; refusing to overwrite a measurement"
  done
  for run in CYPL2 CYPL2DB AGL3 DEV10; do
    for c in D100 D1000; do
      [ ! -e "$RUNS/INF-$run-$c" ] || die "$RUNS/INF-$run-$c exists; refusing to overwrite a run"
    done
  done
  mkdir -p "$INFRA" "$RUNS" "$PROBE_CORPORA"
}

ingest_repeats() {  # ingest_repeats <corpus>: REPS fresh-database ingests; the last stays loaded
  c=$1
  k=1
  while [ $k -le "$REPS" ]; do
    echo "=== $(date +%T) ingest $c repeat $k/$REPS"
    out=$INFRA/ingest/$c/rep$k
    mkdir -p "$INFRA/ingest/$c"
    $P -m plantgraph.ingest synthetic --headline --target-sheets "$(sheets_of "$c")" --seed 1 \
      --store-profile plant --corpus-id "$c" --fresh-database --neo4j-home "$NEO4J_HOME" \
      --out "$out" > "$out.stdout.json" 2> "$out.err" || die "ingest $c repeat $k failed, see $out.err"
    k=$((k + 1))
  done
  mkdir -p "$PROBE_CORPORA/$c"
  cp "$INFRA/ingest/$c/rep$REPS/ingest.json" "$PROBE_CORPORA/$c/ingest.json"
}

replay() {  # replay <label> <corpus> <corpora-root> <strategy> <params> <pin> <cache> <deadline|none>
  label=$1; c=$2; corpora_root=$3; strategy=$4; params=$5; pin=$6; cache=$7; deadline=$8
  id=INF-$label-$c
  source_run=$R/runs/$label-$c
  [ -f "$source_run/answers.jsonl" ] || die "expected the source run $source_run, found none"
  deadline_flag=""
  [ "$deadline" = none ] || deadline_flag="--question-deadline-s $deadline"
  echo "=== $(date +%T) replay $id (cache-only: no --allow-paid-calls)"
  # no --allow-paid-calls: the harness reads only the cache and stops at the first miss (exit 2)
  rc=0
  # shellcheck disable=SC2086
  $P -m plantgraph.qa.harness --run-id "$id" --experiment INFRA-COST --corpus "$c:dev" \
    --strategy "$strategy" --strategy-params-json "$params" --pin-json "$pin" \
    --corpora-root "$corpora_root" --questions-root $R/questions --runs-root "$RUNS" \
    --cache-path "$cache" --concurrency 1 $deadline_flag > "$RUNS/$id.log" 2>&1 || rc=$?
  record_replay_check "$id" "$source_run" $rc
}

same_answers() {  # same_answers <replay-id> <source-run-dir>: the same answers, byte for byte
  # Two fields are allowed to differ and are neutralised on BOTH sides before the comparison:
  # the run_id (the replay has a new id; every row starts with {"run_id":"<id>") and the
  # from_cache flag (calls that were live in the source run are cached in any replay). Neither
  # changes what was computed. Everything else, including every retrieved row, must be equal.
  source_id=$(basename "$2")
  normalised=$RUNS/$1/.replay_normalised
  sed -e "s/^{\"run_id\":\"$1\"/{\"run_id\":\"$source_id\"/"       -e 's/"from_cache":false/"from_cache":true/g' "$RUNS/$1/answers.jsonl" > "$normalised"
  same=1
  sed 's/"from_cache":false/"from_cache":true/g' "$2/answers.jsonl" | cmp -s - "$normalised" || same=0
  rm -f "$normalised"
  [ $same -eq 1 ]
}

record_replay_check() {  # record_replay_check <run-id> <source-run-dir> <exit-code>
  id=$1; source_run=$2; rc=$3
  if [ "$rc" -eq 2 ]; then
    status=cache_miss
  elif [ "$rc" -ne 0 ]; then
    die "replay $id failed with exit code $rc, see $RUNS/$id.log"
  elif same_answers "$id" "$source_run"; then
    status=identical
  else
    status=different
  fi
  echo "$status" > "$RUNS/$id/replay_check.txt"
  echo "    $id: $status"
}

replay_all() {  # replay_all <corpus>: Cypher first, so the page cache is warm for the probes
  c=$1
  echo "=== $(date +%T) cypher query-timing replay INF-CYPL2DB-$c (database time only, no model)"
  $P -m plantgraph.qa.cascade infra-cypher-replay --source-run "$R/runs/CYPL2-$c" --corpus "$c" \
    --corpora-root $PLANT_CORPORA --out-run "$RUNS/INF-CYPL2DB-$c" > "$RUNS/INF-CYPL2DB-$c.log" 2>&1 \
    || die "cypher query-timing replay of $c failed, see $RUNS/INF-CYPL2DB-$c.log"
  # the full cache-only replay: the query-writing call and the answer call both come from the cache
  replay CYPL2 "$c" $PLANT_CORPORA cypher_rag_plant $R/params_cypher_plant.json \
    $R/pins_bakeoff/F_cypher.json $R/cache_luna.sqlite 120
  replay AGL3 "$c" $OCC_CORPORA graph_agent_low_steps $R/params_agent_low.json \
    $R/pin_luna_final_high.json $R/cache_luna.sqlite 120
  # DEV10 ran at an older commit and without a deadline; a cache miss is allowed and reported
  replay DEV10 "$c" $OCC_CORPORA hierarchical_need_rules_plant $R/params_need_plant.json \
    $R/pin_default.json $R/cache_default.sqlite none
}

probe() {  # probe <corpus> <extra infra-probe args...>
  c=$1; shift
  $P -m plantgraph.qa.cascade infra-probe --corpus "$c" --corpora-root "$PROBE_CORPORA" \
    --policy $POLICY --run cypher-luna=$R/runs/CYPL2-D100 --run agent-luna=$R/runs/AGL3-D100 "$@" \
    > /dev/null || die "infra-probe on $c failed"
}

probe_repeats() {  # probe_repeats <corpus>: REPS timing probes, then one memory probe
  c=$1
  mkdir -p "$INFRA/probe/$c"
  k=1
  while [ $k -le "$REPS" ]; do
    echo "=== $(date +%T) infra-probe $c repeat $k/$REPS"
    probe "$c" --neo4j-home "$NEO4J_HOME" --out "$INFRA/probe/$c/rep$k.json"
    k=$((k + 1))
  done
  echo "=== $(date +%T) infra-probe $c memory"
  probe "$c" --memory --out "$INFRA/probe/$c/memory.json"
}

restore_d1000() {
  echo "=== $(date +%T) restore: D1000 (plant profile) alone in Neo4j"
  $P -m plantgraph.ingest synthetic --headline --target-sheets 1000 --seed 1 --store-profile plant \
    --corpus-id D1000 --fresh-database --out "$INFRA/restore_D1000" \
    > "$INFRA/restore_D1000.stdout.json" 2> "$INFRA/restore_D1000.err" || die "restoring D1000 failed"
}

preflight
for corpus in $CORPORA; do
  ingest_repeats "$corpus"
  case $corpus in D4000) ;; *) replay_all "$corpus" ;; esac  # D4000 has no questions
  probe_repeats "$corpus"
done
restore_d1000
write_report() {
  echo "=== $(date +%T) infra-report"
  corpus_args=""; compute_args=""
  for c in $CORPORA; do
    corpus_args="$corpus_args --corpus $c"
    case $c in D4000) ;; *) compute_args="$compute_args --compute-corpus $c" ;; esac
  done
  # a missing reference_price.json simply means no money table (never invent a price)
  # shellcheck disable=SC2086
  $P -m plantgraph.qa.cascade infra-report --ingest-root "$INFRA/ingest"     --probe-root "$INFRA/probe" --runs-root "$RUNS" $corpus_args $compute_args     --run "cypher=INF-CYPL2-{c}" --db-replay "cypher_db_only=INF-CYPL2DB-{c}" --run "agent=INF-AGL3-{c}" --run "need=INF-DEV10-{c}"     --old-run "cypher=CYPL2-{c}" --old-run "agent=AGL3-{c}" --old-run "need=DEV10-{c}" --price-json "$INFRA/reference_price.json"     --out "$INFRA/report.md" > "$INFRA/report.stdout.txt" || die "infra-report failed"
  echo "report: $INFRA/report.md"
}

write_report
echo "=== $(date +%T) done"
