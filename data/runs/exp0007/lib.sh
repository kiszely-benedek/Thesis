# Shared helpers of the EXP-0007 scripts (ADR-0060): sourced, never run on its own.
# Callers cd to the repository root first. Adapted from data/runs/exp0001/lib.sh and sealed/run_sealed.sh.
#
# Each stage script sets, before calling the helpers:  S (its data directory), CACHE (its response
# cache), EXPERIMENT (the name recorded in run_config.json), and the roots it reads
# (CYP_CORPORA, AG_CORPORA, QROOT). Paid helpers need ALLOW_PAID=yes and a verified cap file.
P=.venv/Scripts/python; EX="$P -m plantgraph.qa.exp0007"
X=${E7_ROOT:-data/runs/exp0007}; IN=$X/inputs   # E7_ROOT: only to try the scripts on a scratch copy
E1=data/runs/exp0001; SEALED=data/runs/sealed; CV1=data/runs/cv1
die() { echo "ERROR: $*" >&2; exit 1; }

# ---- options, caps, targets -------------------------------------------------------------------

parse_paid_args() {  # sets ALLOW_PAID, CAP_FILE, CAP_SHA, SYSTEM_LABEL, WITH_NEO4J from the script's options
  ALLOW_PAID=no; CAP_FILE=; CAP_SHA=; SYSTEM_LABEL=; WITH_NEO4J=no
  while [ $# -gt 0 ]; do
    case $1 in
      --allow-paid-calls) ALLOW_PAID=yes ;;
      --cap-file) CAP_FILE=$2; shift ;;
      --cap-sha256) CAP_SHA=$2; shift ;;
      --system-label) SYSTEM_LABEL=$2; shift ;;
      --with-neo4j) WITH_NEO4J=yes ;;
      *) die "unknown option $1" ;;
    esac
    shift
  done
}

require_paid() {  # a paid script starts only with the flag, the written cap file and the sha256 the user saw
  [ "$ALLOW_PAID" = yes ] || die "paid stage: pass --allow-paid-calls (without it the script only prepares and prints the caps)"
  [ -n "$CAP_FILE" ] && [ -f "$CAP_FILE" ] || die "paid stage: --cap-file must name a cap file that exists (found '$CAP_FILE')"
  [ -n "$CAP_SHA" ] || die "paid stage: --cap-sha256 is required: the hash printed when the cap file was written"
  [ "$(sha256sum "$CAP_FILE" | cut -d' ' -f1)" = "$CAP_SHA" ] || die "the cap file changed since it was shown: $CAP_FILE does not hash to $CAP_SHA"
}

cap_of() { $EX cap-of --cap-file "$CAP_FILE" --cap-sha256 "$CAP_SHA" --run-id "$1" --field cap; }
cost_of() { $EX cap-of --cap-file "$CAP_FILE" --cap-sha256 "$CAP_SHA" --run-id "$1" --field cost; }

use_database() {  # the Neo4j database to load into: named explicitly; the user's plant database only when told so
  plant=
  [ "${E7_TARGET_IS_PLANT_DB:-}" != yes ] || plant=--is-plant-db
  DB=$($EX check-neo4j-target --database "${E7_NEO4J_DATABASE:-}" $plant) || die "set E7_NEO4J_DATABASE to a temporary database"
  export NEO4J_DATABASE=$DB
  echo "Neo4j database: $DB"
}

# the server's home directory is only needed for the store-size measurement of a load
neo4j_home_args() { [ -z "${E7_NEO4J_HOME:-}" ] || echo "--neo4j-home $E7_NEO4J_HOME"; }

require_clean_tree() { [ -z "$(git status --porcelain)" ] || die "the working tree is not clean: commit first"; }

# ---- steps and health --------------------------------------------------------------------------

step() {  # step <name> <command...>: run once; a rerun of the script skips the steps that finished
  name=$1; shift
  if [ -e "$S/logs/steps/$name.ok" ]; then echo "--- skip $name (done)"; return 0; fi
  "$@"
  touch "$S/logs/steps/$name.ok"
}

init_stage() { mkdir -p "$S/logs/steps" "$S/runs" "$S/replays"; }

health() { $EX health --run-dir "$S/runs/$1" || die "$1: technical fault; read $S/logs/$1.log before anything else"; }

finish() {  # finish <run-id> <exit-code> <stage>: a smoke ends at its cap (3); a full stage must not
  case "$2:$3" in
    0:*) echo "    $1: complete" ;;
    3:smoke) echo "    $1: smoke stage done" ;;
    3:full) die "$1 reached its spend cap: ask the user before resuming with a higher cap" ;;
    *) die "$1 failed with exit code $2, see $S/logs/$1.log" ;;
  esac
  health "$1"
}

# ---- the two tiers -----------------------------------------------------------------------------

tier_options() {  # tier_options cyp|ag: the frozen strategy, params and pin of a tier
  case $1 in
    cyp) echo "--strategy cypher_rag_plant --strategy-params-json $IN/params_cypher_plant.json --pin-json $IN/pin_cypher_luna_low.json" ;;
    ag) echo "--strategy graph_agent_low_steps --strategy-params-json $IN/params_agent_low.json --pin-json $IN/pin_agent_luna_final_high.json" ;;
    *) die "unknown tier $1" ;;
  esac
}

tier_corpora() { if [ "$1" = cyp ]; then echo "$CYP_CORPORA"; else echo "$AG_CORPORA"; fi; }

tier_run() {  # tier_run <cyp|ag> <run-id> <corpus> <role dev|test> <stage smoke|full> [<questions-root> [<concurrency> [<cache>]]]
  tier=$1; id=$2; corpus=$3; role=$4; stage=$5; qroot=${6:-$QROOT}; conc=${7:-4}; cache=${8:-$CACHE}
  cap=$(cap_of "$id") || die "no cap for $id"; cost=$(cost_of "$id") || die "no cost for $id"
  echo "=== $(date +%T) $id ($stage, cap \$$cap)"; rc=0
  # the cap goes into run_config.json (max_spend_usd) before the first call
  $P -m plantgraph.qa.harness --run-id "$id" --experiment "$EXPERIMENT" --corpus "$corpus:$role" \
    $(tier_options "$tier") --corpora-root "$(tier_corpora "$tier")" --questions-root "$qroot" \
    --runs-root "$S/runs" --cache-path "$cache" --allow-paid-calls --cost-per-question-usd "$cost" \
    --max-spend-usd "$cap" --concurrency "$conc" --question-deadline-s 120 >> "$S/logs/$id.log" 2>&1 || rc=$?
  finish "$id" $rc "$stage"
}

# ---- replays: cache only, never a paid call ----------------------------------------------------

replay() {  # replay <run-id> <run-dir> <cache> <deadline-s> <harness options...>: concurrency 1, no --allow-paid-calls
  orig=$1; id=INF-$1; dir=$2; cache=$3; deadline=$4; shift 4; rc=0
  echo "=== $(date +%T) replay $id (no --allow-paid-calls: cache only)"
  rm -rf "$S/replays/$id"
  $P -m plantgraph.qa.harness --run-id "$id" --experiment "$EXPERIMENT-REPLAY" --runs-root "$S/replays" \
    --cache-path "$cache" --concurrency 1 --question-deadline-s "$deadline" "$@" > "$S/logs/$id.log" 2>&1 || rc=$?
  # a replay differs from the run only in its id and in where each answer came from
  sed -e "s/^{\"run_id\":\"$id\"/{\"run_id\":\"$orig\"/" -e 's/"from_cache":false/"from_cache":true/g' \
    "$S/replays/$id/answers.jsonl" > "$S/replays/$id/.normalised" 2>/dev/null || true
  if [ $rc -eq 0 ] && sed 's/"from_cache":false/"from_cache":true/g' "$dir/answers.jsonl" \
      | cmp -s - "$S/replays/$id/.normalised"; then echo identical > "$S/replays/$id/replay_check.txt"
  else echo "different_or_miss rc=$rc" > "$S/replays/$id/replay_check.txt"; fi
  rm -f "$S/replays/$id/.normalised"; echo "    $id: $(cat "$S/replays/$id/replay_check.txt")"
}

replay_tier() {  # replay_tier <cyp|ag> <run-id> <corpus> <role>: replay of a run of this stage
  replay "$2" "$S/runs/$2" "$CACHE" 120 --corpus "$3:$4" $(tier_options "$1") \
    --corpora-root "$(tier_corpora "$1")" --questions-root "$QROOT"
}

require_identical_replays() {  # every replay_check.txt of the stage reads 'identical'
  bad=$(grep -L '^identical$' "$S"/replays/*/replay_check.txt 2>/dev/null || true)
  [ -z "$bad" ] || die "replays that are not byte-identical: $bad"
}

# ---- Neo4j load of one corpus (plant profile, fresh database) ---------------------------------

# the v2 ladder: corpus id -> target sheets
sheets_of() { case $1 in H1g2) echo 1 ;; H3g2) echo 3 ;; H10g2) echo 10 ;; H30g2) echo 30 ;; *) die "no sheet target for $1" ;; esac; }

# R5 corpora: H100g2 (preset duplication 0.25), H1000g2, and H100g2 again at duplication 0 and 0.5
sealed_sheets() { case $1 in H100g2|H100g2d0|H100g2d50) echo 100 ;; H1000g2) echo 1000 ;; *) die "no sheet target for $1" ;; esac; }
sealed_dup_args() { case $1 in H100g2d0) echo "--headline-duplication-rate 0" ;; H100g2d50) echo "--headline-duplication-rate 0.5" ;; *) echo "" ;; esac; }
SEALED_IDS="H100g2 H1000g2 H100g2d0 H100g2d50"

n_sheets() { $P -c "import json,sys;print(json.load(open(sys.argv[1]))['counts']['n_sheets'])" "$1"; }

load_plant() {  # load_plant <corpus> <sheets> <seed> <out-dir> [more ingest options]: this corpus alone in the database
  corpus=$1; sheets=$2; seed=$3; out=$4; shift 4
  echo "=== $(date +%T) load $corpus into $NEO4J_DATABASE"
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$sheets" --seed "$seed" "$@"     --store-profile plant --corpus-id "$corpus" --fresh-database $(neo4j_home_args) --out "$out/$corpus"     > "$S/logs/load_$corpus.json" 2> "$S/logs/load_$corpus.err" || die "loading $corpus failed, see $S/logs/load_$corpus.err"
}

check_loaded_matches() {  # check_loaded_matches <loaded ingest.json> <question corpus ingest.json>
  [ "$(n_sheets "$1")" = "$(n_sheets "$2")" ] || die "the loaded corpus has a different sheet count than the question corpus ($1 vs $2)"
}

restore_d1000() {  # only when the plant database itself was the target
  if [ "${E7_TARGET_IS_PLANT_DB:-}" = yes ]; then
    echo "=== $(date +%T) restore D1000 (plant profile) alone in Neo4j"
    $P -m plantgraph.ingest synthetic --headline --target-sheets 1000 --seed 1 --store-profile plant \
      --corpus-id D1000 --fresh-database > "$S/logs/restore_D1000.json" 2> "$S/logs/restore_D1000.err" \
      || die "restoring D1000 failed, see $S/logs/restore_D1000.err"
  else echo "--- no D1000 restore: the target was the temporary database $NEO4J_DATABASE"; fi
}

# ---- freeze files ------------------------------------------------------------------------------

require_guards_passed() {  # the S0 gates (with the Cypher replay) passed at this very commit
  [ -f $X/guards/PASSED ] || die "run guards.sh --with-neo4j first: $X/guards/PASSED is missing"
  [ "$(sed -n 1p $X/guards/PASSED)" = "$(git rev-parse HEAD)" ] || die "guards.sh passed at another commit: run it again at $(git rev-parse HEAD)"
  [ "$(sed -n 2p $X/guards/PASSED)" = "with_cypher_replay=yes" ] || die "guards.sh was run without --with-neo4j: the Cypher replay (S0-d) is required"
}

require_freeze() {  # R4 / R5: the system's identity is the explicit freeze file E7, written once by make_set.sh
  [ -f $X/E7.commit ] && [ -f $X/E7.sha256 ] || die "no E7 freeze file: run make_set.sh on the frozen system first"
  [ "$(git rev-parse HEAD)" = "$(cat $X/E7.commit)" ] || die "HEAD is not the frozen system's commit $(cat $X/E7.commit) (system: $(cat $X/E7.system))"
  sha256sum -c --quiet $X/E7.sha256 || die "an input, question set or cap file changed since E7"
  echo "frozen system: $(cat $X/E7.system) at $(cat $X/E7.commit)"
}

# the registered listing: E7's once it exists, else EXP-0001's (equal on 2026-10-27)
listing_file() { if [ -f $IN/listing_E7.json ]; then echo $IN/listing_E7.json; else echo $E1/inputs/listing_E.json; fi; }
check_listing() { $EX check-listing --expected "$1" || die "Luna's price or window changed since the freeze: re-estimate, ask the user"; }

# ---- stages 2 and 3: both tiers on the dev plant D100g2 ----------------------------------------

upper() { echo "$1" | tr a-z A-Z; }

require_r1_r2() {
  [ -f $X/r1/D100g2/ingest.json ] || die "run R1 first: $X/r1/D100g2/ingest.json is missing (plan section 3)"
  [ -f $X/r2/D100g2/questions.jsonl ] || die "run R2 first: $X/r2/D100g2/questions.jsonl is missing (plan section 3)"
}

load_dev_plant() {  # D100g2 alone in the database, checked against the plant R1 built
  load_plant D100g2 100 1 "$S/neo4jplant"
  check_loaded_matches "$S/neo4jplant/D100g2/ingest.json" $X/r1/D100g2/ingest.json
}

dev_tier_runs() {  # dev_tier_runs <run prefix P7|Q7> <with smoke yes|no>: Cypher tier, then agent tier, on D100g2
  step load_D100g2 load_dev_plant
  # own names: tier_run sets the shell-global `tier` and `id`, which would rename the full run after its smoke
  for dev_tier in cyp ag; do
    dev_id=$1-$(upper $dev_tier)-D100g2
    if [ "$2" = yes ]; then step smoke_$dev_tier tier_run $dev_tier "$dev_id-SMOKE" D100g2 dev smoke "$S/questions_smoke"; fi
    step full_$dev_tier tier_run $dev_tier "$dev_id" D100g2 dev full
  done
}

show_caps() {  # show_caps <stage> <pilot-result or ''> [more make-caps options]: write the cap file once, show it and its hash
  stage=$1; result=$2; shift 2; file=$S/caps_$stage.json
  if [ -f "$file" ]; then cat "$file"
  elif [ -n "$result" ]; then $EX make-caps --stage "$stage" --pilot-result "$result" --out "$file" "$@" || die "computing the caps failed"
  else $EX make-caps --stage "$stage" --out "$file" "$@" || die "computing the caps failed"; fi
  echo "cap file $file  sha256 $(sha256sum "$file" | cut -d' ' -f1)"
}
