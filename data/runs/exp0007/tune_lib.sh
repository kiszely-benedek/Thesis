# Helpers of tune.sh (V2T tuning, ADR-0061): sourced after lib.sh, never run on its own.
# Like lib.sh's tier_run, but for the V2T tiers and F1's two tiers on the validation plants.
# Variable pitfall (fixed in d788105 for tier_run): never reuse a caller's loop variable here, so the
# helpers keep their own `run_*` names.

# Arms: AG (V2T agent), CYP-A and CYP-B (V2T Cypher at setting A / B), F1-AG and F1-CYP (frozen F1).
arm_options() {
  case $1 in
    AG) echo "--strategy graph_agent_lines --strategy-params-json $IN/params_agent_v2t.json --pin-json $IN/pin_agent_luna_final_high.json" ;;
    CYP-A) echo "--strategy cypher_rag_lines --strategy-params-json $IN/params_cypher_v2t_a.json --pin-json $IN/pin_cypher_luna_low.json" ;;
    CYP-B) echo "--strategy cypher_rag_lines --strategy-params-json $IN/params_cypher_v2t_b.json --pin-json $IN/pin_cypher_luna_low.json" ;;
    F1-AG) tier_options ag ;;
    F1-CYP) tier_options cyp ;;
    *) die "unknown arm $1" ;;
  esac
}

# The per-question deadline each arm is run under. The agent and setting B run to the 900 s hang guard
# (a later answer is cut offline, per setting, by tune-report); setting A and F1 keep their 120 s.
arm_deadline() {
  case $1 in
    AG|CYP-B) echo 900 ;;
    CYP-A|F1-AG|F1-CYP) echo 120 ;;
    *) die "unknown arm $1" ;;
  esac
}

# Cypher arms read the corpus's plant graph from Neo4j (CYP_CORPORA); the others from the ingest record
arm_corpora() { case $1 in CYP-*|F1-CYP) echo "$CYP_CORPORA" ;; *) echo "$AG_CORPORA" ;; esac; }

tune_run() {  # tune_run <arm> <run-id> <corpus> <smoke|full> <questions-root>
  run_arm=$1; run_id=$2; run_corpus=$3; run_stage=$4; run_qroot=$5
  run_cap=$(cap_of "$run_id") || die "no cap for $run_id"; run_cost=$(cost_of "$run_id") || die "no cost for $run_id"
  echo "=== $(date +%T) $run_id ($run_stage, cap \$$run_cap)"; run_rc=0
  # the cap goes into run_config.json (max_spend_usd) before the first call
  $P -m plantgraph.qa.harness --run-id "$run_id" --experiment "$EXPERIMENT" --corpus "$run_corpus:dev" \
    $(arm_options "$run_arm") --corpora-root "$(arm_corpora "$run_arm")" --questions-root "$run_qroot" \
    --runs-root "$S/runs" --cache-path "$CACHE" --allow-paid-calls --cost-per-question-usd "$run_cost" \
    --max-spend-usd "$run_cap" --concurrency 4 --question-deadline-s "$(arm_deadline "$run_arm")" \
    >> "$S/logs/$run_id.log" 2>&1 || run_rc=$?
  finish "$run_id" $run_rc "$run_stage"
}

load_lines() {  # load_lines <corpus> <sheets> <seed> <profile plant_lines|plant>: this plant alone in the temp database
  ld_corpus=$1; ld_sheets=$2; ld_seed=$3; ld_profile=$4
  echo "=== $(date +%T) load $ld_corpus ($ld_profile) into $NEO4J_DATABASE"
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$ld_sheets" --seed "$ld_seed" \
    --store-profile "$ld_profile" --corpus-id "$ld_corpus" --fresh-database --out "$CYP_CORPORA/$ld_corpus" \
    > "$S/logs/load_$ld_corpus.json" 2> "$S/logs/load_$ld_corpus.err" \
    || die "loading $ld_corpus ($ld_profile) failed, see $S/logs/load_$ld_corpus.err"
  check_loaded_matches "$CYP_CORPORA/$ld_corpus/ingest.json" "$AG_CORPORA/$ld_corpus/ingest.json"
}

drop_temp_database() {  # the temporary database goes away when the script ends, however it ends
  if [ -n "${LOADED_DB:-}" ]; then
    $EX drop-neo4j-database --database "$LOADED_DB" || echo "WARNING: could not drop $LOADED_DB: drop it by hand"
    LOADED_DB=
  fi
}

require_tune_guards_passed() {  # tune_guards.sh --with-neo4j passed at this very commit
  gf=$X/tune/guards/PASSED
  [ -f $gf ] || die "run tune_guards.sh --with-neo4j first: $gf is missing"
  [ "$(sed -n 1p $gf)" = "$(git rev-parse HEAD)" ] || die "tune_guards.sh passed at another commit: run it again at $(git rev-parse HEAD)"
  [ "$(sed -n 2p $gf)" = "with_cypher_replay=yes" ] || die "tune_guards.sh was run without --with-neo4j: the Cypher replay is required"
}

draw_questions() {  # draw_questions <corpus> <ingest.json>: the dev recipe: R2-style pool, then 10 per family
  dq_corpus=$1; dq_ingest=$2
  $P -m plantgraph.qa.questions --corpus-id "$dq_corpus" --ingest-json "$dq_ingest" --seed 1 \
    --n-per-bin 97 --n-unanswerable 97 --out "$S/pool/$dq_corpus" > "$S/logs/pool_$dq_corpus.log" \
    || die "question pool for $dq_corpus failed, see $S/logs/pool_$dq_corpus.log"
  $P -m plantgraph.qa.questions.per_family --in "$S/pool/$dq_corpus/questions.jsonl" --n 10 \
    --seed 20261101 --out "$QROOT/$dq_corpus" || die "per-family draw for $dq_corpus failed"
}

build_plant() {  # build_plant <corpus>: the plant (seed and size from the protocol table), checked G1 and S16
  bp_corpus=$1; bp_args=$($EX tune-corpus --corpus-id "$bp_corpus" $FINAL_FLAG) || die "$bp_corpus is not allowed here"
  set -- $bp_args  # "<sheets> <seed>"
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$1" --seed "$2" --corpus-id "$bp_corpus" \
    --check --no-neo4j --out "$AG_CORPORA/$bp_corpus" > "$S/logs/corpus_$bp_corpus.json" \
    2> "$S/logs/corpus_$bp_corpus.err" || die "building $bp_corpus failed, see $S/logs/corpus_$bp_corpus.err"
  $EX check-ingest --ingest-json "$AG_CORPORA/$bp_corpus/ingest.json" --corpus-id "$bp_corpus" \
    || die "$bp_corpus failed its gates"
}

# LINE-01 gates (P = R = 1). API-02 on a fresh plant only reports: its gate is D100g2 in tune_guards.sh,
# and a family below 1.0 here is a finding to read (an agent-tool gap), not a reason to stop the setup.
free_plant_checks() {
  fc_corpus=$1
  $P -m plantgraph.qa.harness.line_view_fidelity --corpus-id "$fc_corpus" \
    --ingest-json "$AG_CORPORA/$fc_corpus/ingest.json" || die "LINE-01 failed on $fc_corpus"
  $P -m plantgraph.qa.harness.api_check_questions --corpus-id "$fc_corpus" \
    --ingest-json "$AG_CORPORA/$fc_corpus/ingest.json" --questions "$QROOT/$fc_corpus/questions.jsonl" \
    --min-share 1.0 || echo "WARNING: API-02 below 1.0 on $fc_corpus (reported, not a gate here): read the table above"
}
