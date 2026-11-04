#!/bin/sh
# INFRA-2: the infrastructure-cost measurement (ADR-0051, design infra-cost.md "v2 addendum") for the tuned
# system V2T-A on the sealed v2 corpora H100g2 and H1000g2. ZERO paid calls: no --allow-paid-calls anywhere.
# Mirrors data/runs/cv1/run_infra.sh; the R5 helpers (lib.sh, v2t_lib.sh) supply the corpus builds and the arms.
#
#   sh data/runs/exp0007/run_infra_v2.sh --check   validates every input; touches no file and no Neo4j
#   E7_NEO4J_DATABASE=neo4j E7_TARGET_IS_PLANT_DB=yes sh data/runs/exp0007/run_infra_v2.sh
#
# Do NOT run pytest while it runs (the integration tests write to the same Neo4j). Keep the laptop plugged in,
# in one Windows power mode, with no other heavy process. The database it loads into is E7_NEO4J_DATABASE,
# exactly as for run_sealed.sh; if that is the user's plant database, the script ends by restoring D1000.
#
# Per corpus the script
#   1. ingests REPS times (R5's seed, size and duplication, store profile plant_lines) with --fresh-database
#      --neo4j-home; the last repeat stays loaded;
#   2. replays S7-CYP-<c> and S7-AG-<c> cache-only at concurrency 1 with the R5 setting A parameters (new run
#      ids INF2-CYP-<c>, INF2-AG-<c>) and writes replay_check.txt (identical / different / cache_miss; a miss at
#      1,000 sheets is expected, see sealed/replays/INF-S7-CYP-H1000g2/timing_note.md: recorded, not a failure);
#      `infra-cypher-replay` re-executes the stored queries (DATABASE TIME ONLY, INF2-CYPDB-<c>);
#   3. times the live-cascade startup REPS times (infra-probe) and measures memory once.
# Then it restores Neo4j as run_sealed.sh leaves it (lib.sh restore_d1000) and writes the report.
#
# The probe uses cascade_v4, not cascade_v4_iso: the probe refuses label-routed policies (a free-text question
# has no need label) and cascade_v4_iso differs from cascade_v4 only by that routing, so the startup is the same.
#
# Overrides: INFRA_ROOT, REPS, CORPORA (default "H100g2 H1000g2"; H4000g2 needs INFRA_H4000G2_SEED, no
# question set exists for it, so it gets steps 1 and 3 only), NEO4J_HOME.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh

CHECK_ONLY=no
for arg in "$@"; do
  case $arg in
    --check) CHECK_ONLY=yes ;;
    *) die "unknown option $arg (the only option is --check)" ;;
  esac
done

INFRA=${INFRA_ROOT:-$X/infra}
REPS=${REPS:-3}
CORPORA=${CORPORA:-"H100g2 H1000g2"}
NEO4J_HOME=${NEO4J_HOME:-"$USERPROFILE/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"}
E7_NEO4J_HOME=$NEO4J_HOME   # lib.sh's load_corpus passes it to the ingest as --neo4j-home
R5=$X/sealed                # the sealed run: source runs, questions, corpora, cache
RUNS=$INFRA/runs            # replay runs: a new folder, so no existing run is overwritten
PROBE_CORPORA=$INFRA/corpora # ingest.json of each corpus's last ingest, for the probes and the Cypher replays
STAGE=$INFRA/stage          # one ingest lands here before it is moved to ingest/<c>/rep<k>
POLICY=src/plantgraph/qa/cascade/policies_v2t/cascade_v4.json
PIN_CORPUS=H100g2           # the tier runs the probes read their pins from (the pins are the same on every corpus)
# what the shared helpers expect (lib.sh, v2t_lib.sh)
S=$INFRA; CACHE=$R5/cache_s7.sqlite; EXPERIMENT=INFRA-COST
CYP_CORPORA=$STAGE; AG_CORPORA=$R5/corpora; QROOT=$R5/questions

infra_sheets() { case $1 in H4000g2) echo 4000 ;; *) sealed_sheets "$1" ;; esac; }

infra_seed() {  # R5's registered test seed; H4000g2 has none registered, so the caller names one
  case $1 in
    H4000g2) [ -n "${INFRA_H4000G2_SEED:-}" ] || die "set INFRA_H4000G2_SEED: no test seed is registered for H4000g2"
             echo "$INFRA_H4000G2_SEED" ;;
    *) $EX test-seed --sheets "$(infra_sheets "$1")" ;;
  esac
}

has_questions() { [ "$1" != H4000g2 ]; }

# ---- preflight ---------------------------------------------------------------------------------

check_inputs() {  # read-only: every file the measurement reads must exist
  [ -x "$P" ] || [ -f "$P.exe" ] || die "expected $P, found no project interpreter"
  [ -d "$NEO4J_HOME" ] || die "expected the Neo4j home at $NEO4J_HOME, found none"
  [ -f "$NEO4J_HOME/metrics/neo4j.dbms.page_cache.usage_ratio.csv" ] \
    || die "expected the page-cache metric under $NEO4J_HOME/metrics, found none"
  [ -f "$POLICY" ] || die "expected the policy $POLICY, found none"
  [ -f "$CACHE" ] || die "expected the R5 cache $CACHE, found none"
  [ "$REPS" -ge 1 ] 2> /dev/null || die "expected REPS to be a positive integer, found '$REPS'"
  for src in S7-CYP-$PIN_CORPUS S7-AG-$PIN_CORPUS; do
    [ -f "$R5/runs/$src/run_config.json" ] || die "expected the source run $R5/runs/$src, found none"
  done
  for c in $CORPORA; do
    infra_sheets "$c" > /dev/null; infra_seed "$c" > /dev/null
    has_questions "$c" || continue
    for src in S7-CYP-$c S7-AG-$c; do
      [ -f "$R5/runs/$src/answers.jsonl" ] || die "expected the source run $R5/runs/$src, found none"
    done
    [ -f "$AG_CORPORA/$c/ingest.json" ] || die "expected $AG_CORPORA/$c/ingest.json, found none"
    [ -f "$QROOT/$c/questions.jsonl" ] || die "expected $QROOT/$c/questions.jsonl, found none"
  done
}

refuse_existing() {  # a measurement is never overwritten
  for c in $CORPORA; do
    for existing in "$INFRA/ingest/$c" "$INFRA/probe/$c" "$RUNS/INF2-CYP-$c" "$RUNS/INF2-CYPDB-$c" "$RUNS/INF2-AG-$c"; do
      [ ! -e "$existing" ] || die "$existing exists; refusing to overwrite a measurement"
    done
  done
  [ ! -e "$STAGE" ] || die "$STAGE exists (a stopped run?); remove it by hand"
}

preflight() {  # checks only; creates nothing
  require_v2t_freeze            # the V2T system files and inputs are the ones E7 froze
  DEADLINE_S=$(setting_a_deadline)
  # E7_NEO4J_DATABASE must be named; the plant database only with E7_TARGET_IS_PLANT_DB=yes. --check may omit it.
  if [ "$CHECK_ONLY" = no ] || [ -n "${E7_NEO4J_DATABASE:-}" ]; then use_database
  else echo "note: E7_NEO4J_DATABASE is not set; the real run needs it"; NEO4J_DATABASE=unset; fi
  check_inputs
  refuse_existing
}

# ---- step 1: ingests ---------------------------------------------------------------------------

load_stage() {  # load_stage <corpus>: one fresh-database ingest into $STAGE/<corpus>
  ls_c=$1; ls_n=$(infra_sheets "$ls_c"); ls_seed=$(infra_seed "$ls_c")
  if has_questions "$ls_c"; then  # R5's own loader: same seed and duplication, checked against the question corpus
    load_corpus "$ls_c" "$ls_n" "$ls_seed" plant_lines $(sealed_dup_args "$ls_c")
    return
  fi
  echo "=== $(date +%T) load $ls_c (plant_lines) into $NEO4J_DATABASE"
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$ls_n" --seed "$ls_seed" \
    --store-profile plant_lines --corpus-id "$ls_c" --fresh-database --neo4j-home "$NEO4J_HOME" \
    --out "$STAGE/$ls_c" > "$S/logs/load_${ls_c}_plant_lines.json" 2> "$S/logs/load_${ls_c}_plant_lines.err" \
    || die "loading $ls_c failed, see $S/logs/load_${ls_c}_plant_lines.err"
}

ingest_repeats() {  # ingest_repeats <corpus>: REPS fresh-database ingests; the last stays loaded
  c=$1; k=1
  mkdir -p "$INFRA/ingest/$c"
  while [ "$k" -le "$REPS" ]; do
    echo "=== $(date +%T) ingest $c repeat $k/$REPS"
    mkdir -p "$STAGE"
    load_stage "$c"
    mv "$STAGE/$c" "$INFRA/ingest/$c/rep$k"
    mv "$S/logs/load_${c}_plant_lines.json" "$INFRA/ingest/$c/rep$k.stdout.json"
    mv "$S/logs/load_${c}_plant_lines.err" "$INFRA/ingest/$c/rep$k.err"
    rmdir "$STAGE"
    k=$((k + 1))
  done
  mkdir -p "$PROBE_CORPORA/$c"
  cp "$INFRA/ingest/$c/rep$REPS/ingest.json" "$PROBE_CORPORA/$c/ingest.json"
}

# ---- step 2: replays ---------------------------------------------------------------------------

same_answers() {  # same_answers <replay-id> <source-run-dir>: the same answers, byte for byte
  # The run_id and the from_cache flag are neutralised on BOTH sides (the replay has a new id, and calls that
  # were live in the source run come from the cache in any replay); neither changes what was computed.
  sa_source_id=$(basename "$2")
  sa_normalised=$RUNS/$1/.replay_normalised
  sed -e "s/^{\"run_id\":\"$1\"/{\"run_id\":\"$sa_source_id\"/" -e 's/"from_cache":false/"from_cache":true/g' \
    "$RUNS/$1/answers.jsonl" > "$sa_normalised"
  sa_same=1
  sed 's/"from_cache":false/"from_cache":true/g' "$2/answers.jsonl" | cmp -s - "$sa_normalised" || sa_same=0
  rm -f "$sa_normalised"
  [ $sa_same -eq 1 ]
}

# lib.sh's `replay` writes only identical / different_or_miss, so the three-way check is written here
record_replay_check() {  # record_replay_check <run-id> <source-run-dir> <exit-code>
  if [ "$3" -eq 2 ]; then rr_status=cache_miss   # the harness stops at the first cache miss (exit 2)
  elif [ "$3" -ne 0 ]; then die "replay $1 failed with exit code $3, see $RUNS/$1.log"
  elif same_answers "$1" "$2"; then rr_status=identical
  else rr_status=different; fi
  echo "$rr_status" > "$RUNS/$1/replay_check.txt"
  echo "    $1: $rr_status"
}

infra_replay() {  # infra_replay <arm CYP-A|AG> <source-run-id> <new-run-id> <corpus> <corpora-root>
  ir_arm=$1; ir_source=$R5/runs/$2; ir_id=$3; ir_corpus=$4; ir_root=$5; ir_rc=0
  echo "=== $(date +%T) replay $ir_id (cache-only: no --allow-paid-calls)"
  # no --allow-paid-calls: the harness reads only the cache. The R5 setting A parameters come from arm_options.
  $P -m plantgraph.qa.harness --run-id "$ir_id" --experiment "$EXPERIMENT" --corpus "$ir_corpus:test" \
    $(v2t_arm_options "$ir_arm") --corpora-root "$ir_root" --questions-root "$QROOT" \
    --runs-root "$RUNS" --cache-path "$CACHE" --concurrency 1 --question-deadline-s "$DEADLINE_S" \
    > "$RUNS/$ir_id.log" 2>&1 || ir_rc=$?
  record_replay_check "$ir_id" "$ir_source" $ir_rc
}

replay_all() {  # replay_all <corpus>: Cypher first, so the page cache is warm for the probes
  c=$1
  echo "=== $(date +%T) cypher query-timing replay INF2-CYPDB-$c (database time only, no model)"
  $P -m plantgraph.qa.cascade infra-cypher-replay --source-run "$R5/runs/S7-CYP-$c" --corpus "$c" \
    --corpora-root "$PROBE_CORPORA" --out-run "$RUNS/INF2-CYPDB-$c" > "$RUNS/INF2-CYPDB-$c.log" 2>&1 \
    || die "cypher query-timing replay of $c failed, see $RUNS/INF2-CYPDB-$c.log"
  infra_replay CYP-A "S7-CYP-$c" "INF2-CYP-$c" "$c" "$PROBE_CORPORA"
  infra_replay AG "S7-AG-$c" "INF2-AG-$c" "$c" "$AG_CORPORA"
}

# ---- step 3: probes ----------------------------------------------------------------------------

probe() {  # probe <corpus> <extra infra-probe args...>
  pr_c=$1; shift
  $P -m plantgraph.qa.cascade infra-probe --corpus "$pr_c" --corpora-root "$PROBE_CORPORA" --policy "$POLICY" \
    --run cypher-v2t="$R5/runs/S7-CYP-$PIN_CORPUS" --run agent-v2t="$R5/runs/S7-AG-$PIN_CORPUS" "$@" \
    > /dev/null || die "infra-probe on $pr_c failed"
}

probe_repeats() {  # probe_repeats <corpus>: REPS timing probes, then one memory probe
  c=$1; k=1
  mkdir -p "$INFRA/probe/$c"
  while [ "$k" -le "$REPS" ]; do
    echo "=== $(date +%T) infra-probe $c repeat $k/$REPS"
    probe "$c" --neo4j-home "$NEO4J_HOME" --out "$INFRA/probe/$c/rep$k.json"
    k=$((k + 1))
  done
  echo "=== $(date +%T) infra-probe $c memory"
  probe "$c" --memory --out "$INFRA/probe/$c/memory.json"
}

# ---- report ------------------------------------------------------------------------------------

write_report() {
  echo "=== $(date +%T) infra-report"
  corpus_args=""; compute_args=""
  for c in $CORPORA; do
    corpus_args="$corpus_args --corpus $c"
    has_questions "$c" && compute_args="$compute_args --compute-corpus $c"
  done
  # a missing reference_price.json simply means no money table (never invent a price)
  # shellcheck disable=SC2086
  $P -m plantgraph.qa.cascade infra-report --ingest-root "$INFRA/ingest" --probe-root "$INFRA/probe" \
    --runs-root "$RUNS" $corpus_args $compute_args \
    --run "cypher=INF2-CYP-{c}" --db-replay "cypher_db_only=INF2-CYPDB-{c}" --run "agent=INF2-AG-{c}" \
    --old-run "cypher=S7-CYP-{c}" --old-run "agent=S7-AG-{c}" --old-runs-root "$R5/runs" \
    --price-json "$INFRA/reference_price.json" --out "$INFRA/report.md" > "$INFRA/report.stdout.txt" \
    || die "infra-report failed, see $INFRA/report.stdout.txt"
  echo "report: $INFRA/report.md"
}

# ---- main --------------------------------------------------------------------------------------

preflight
if [ "$CHECK_ONLY" = yes ]; then
  echo "check ok: corpora [$CORPORA], REPS=$REPS, deadline ${DEADLINE_S}s, output $INFRA; nothing was touched"
  exit 0
fi
mkdir -p "$INFRA/logs" "$RUNS" "$PROBE_CORPORA"
for corpus in $CORPORA; do
  ingest_repeats "$corpus"
  if has_questions "$corpus"; then replay_all "$corpus"; fi
  probe_repeats "$corpus"
done
restore_d1000   # the same restore as run_sealed.sh's restore_d1000_a: the demo expects this one corpus
write_report
echo "=== $(date +%T) done"
