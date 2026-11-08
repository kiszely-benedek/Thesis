# Arms, free dry runs, capped paid runs and replays of the EXP-0008 launcher: sourced after lib.sh.
#
# A stage sets, before it calls anything here:
#   STEP     the ledger name of the stage (M1, M5, M6a ...), a key of the step ceilings in caps.py
#   SD       the stage's folder under $ROOT (its runs, cache, replays and dry runs live there)
#   CACHE    the stage's response cache
#   EXPERIMENT   the name written into run_config.json
#   CYP_CORPORA / AG_CORPORA / QROOT   where the Cypher tier, the agent tier and the questions are read
# Money rule: a paid run starts only after a free dry run counted its cache misses (cap = misses x cost
# x 1.5), the cap was cut to what the step ceiling and the $30 runs ledger still allow, and the OpenRouter
# balance covered the cap. In --smoke the harness is the fake-transport one: no request leaves the machine.

IN=$INPUTS
DEADLINE_S=120    # setting A of the cascade (cascade/limits.py): 30 s Cypher timeout, 120 s per question

# ---- arms --------------------------------------------------------------------------------------------

arm_options() {  # arm_options <AG|CYP-A|F1-AG|F1-CYP|CTX>: strategy, parameters and pin of an arm
  case $1 in
    AG) echo "--strategy graph_agent_lines --strategy-params-json $IN/params_agent_v2t.json --pin-json $IN/pin_agent_luna_final_high.json" ;;
    CYP-A)
      if smoke; then arm_options AG   # no Neo4j in the smoke: the Cypher tier is stood in for by the agent
      else echo "--strategy cypher_rag_lines --strategy-params-json $IN/params_cypher_v2t_a.json --pin-json $IN/pin_cypher_luna_low.json"; fi ;;
    F1-AG) echo "--strategy graph_agent_low_steps --strategy-params-json $IN/params_agent_low.json --pin-json $IN/pin_agent_luna_final_high.json" ;;
    F1-CYP)
      if smoke; then arm_options F1-AG
      else echo "--strategy cypher_rag_plant --strategy-params-json $IN/params_cypher_plant.json --pin-json $IN/pin_cypher_luna_low.json"; fi ;;
    CTX) echo "--strategy context_rag --pin-json $IN/pin_agent_luna_final_high.json" ;;
    *) stop_run infra "unknown arm $1" ;;
  esac
}

arm_tier() {  # the cost tier of an arm: cyp, ag or ctx
  case $1 in CYP-A|F1-CYP) echo cyp ;; AG|F1-AG) echo ag ;; CTX) echo ctx ;; *) stop_run infra "unknown arm $1" ;; esac
}

arm_deadline() { if [ "$1" = CTX ]; then echo 300; else echo $DEADLINE_S; fi; }

# The Cypher tier reads the ingest.json kept from the plant's first load with its store profile (cypcorp/),
# unless a stage names its own folder in CYP_CORPORA (the identity arms load each plant once per arm).
arm_corpora() {
  case $1 in
    CYP-A) echo "${CYP_CORPORA:-$ROOT/cypcorp/plant_lines}" ;;
    F1-CYP) echo "${CYP_CORPORA:-$ROOT/cypcorp/plant}" ;;
    *) echo "$AG_CORPORA" ;;
  esac
}

harness_module() { if smoke; then echo plantgraph.qa.exp0008.smoke_harness; else echo plantgraph.qa.harness; fi; }

# ---- the free dry run ----------------------------------------------------------------------------------

dry_run() {  # dry_run <arm> <run-id> <corpus> <role> <deadline> <qroot> <cache>: writes $SD/dry/<run-id>.misses.json
  dr_arm=$1; dr_id=$2
  rm -rf "$SD/dry/runs/$dr_id" "$SD/dry/$dr_id.misses.json" "$SD/dry/cache_copy.sqlite"
  mkdir -p "$SD/dry/runs"
  if [ -f "$7" ]; then cp "$7" "$SD/dry/cache_copy.sqlite"; fi   # a copy: the dry run writes its canned replies into it
  # shellcheck disable=SC2046
  try $P -m plantgraph.exp0004.e2e_dry_run --misses-out "$SD/dry/$dr_id.misses.json" \
    --run-id "$dr_id" --experiment "$EXPERIMENT" --corpus "$3:$4" $(arm_options "$dr_arm") \
    --corpora-root "$(arm_corpora "$dr_arm")" --questions-root "$6" --runs-root "$SD/dry/runs" \
    --cache-path "$SD/dry/cache_copy.sqlite" --concurrency 1 --question-deadline-s "$5" \
    > "$LOGS/dry_$dr_id.log" 2>&1
  event NOTE "dry run $dr_id: $(tail -n 1 "$LOGS/dry_$dr_id.log")"
}

# ---- one capped paid run -----------------------------------------------------------------------------------

balance_args() { if smoke; then echo "--fake-balance ${E9_FAKE_BALANCE:-100}"; fi; }

paid_run() {  # paid_run <arm> <run-id> <corpus> <role> [qroot [concurrency [cache]]]
  pr_arm=$1; pr_id=$2; pr_corpus=$3; pr_role=$4; pr_qroot=${5:-$QROOT}; pr_conc=${6:-4}; pr_cache=${7:-$CACHE}
  pr_tier=$(arm_tier "$pr_arm"); pr_deadline=$(arm_deadline "$pr_arm")
  if [ -f "$SD/runs/$pr_id.complete" ]; then event NOTE "skip $pr_id (complete)"; return 0; fi
  dry_run "$pr_arm" "$pr_id" "$pr_corpus" "$pr_role" "$pr_deadline" "$pr_qroot" "$pr_cache"
  pr_cap=$($L run-cap --misses "$SD/dry/$pr_id.misses.json" --tier "$pr_tier" --step "$STEP" \
    --step-dir "${STEP_DIR:-$SD}" --root "$ROOT" --run-dir "$SD/runs/$pr_id") \
    || stop_run topup "no money left for $pr_id under the step ceiling or the \$30 runs ledger"
  # shellcheck disable=SC2046
  $L balance --needed "$pr_cap" $(balance_args) || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$pr_cap for $pr_id"
  pr_cost=$($L cost-of --tier "$pr_tier") || stop_run infra "no cost per question for tier $pr_tier"
  event START "$pr_id arm $pr_arm on $pr_corpus, cap \$$pr_cap"
  pr_rc=0
  # shellcheck disable=SC2046
  $P -m "$(harness_module)" --run-id "$pr_id" --experiment "$EXPERIMENT" --corpus "$pr_corpus:$pr_role" \
    $(arm_options "$pr_arm") --corpora-root "$(arm_corpora "$pr_arm")" --questions-root "$pr_qroot" \
    --runs-root "$SD/runs" --cache-path "$pr_cache" --allow-paid-calls --cost-per-question-usd "$pr_cost" \
    --max-spend-usd "$pr_cap" --concurrency "$pr_conc" --question-deadline-s "$pr_deadline" \
    >> "$LOGS/$pr_id.log" 2>&1 || pr_rc=$?
  case $pr_rc in
    0) ;;
    3) event CAP "$pr_id reached its cap \$$pr_cap"; stop_run topup "$pr_id reached its spend cap of \$$pr_cap" ;;
    *) stop_run infra "$pr_id: harness exit $pr_rc, see $LOGS/$pr_id.log" ;;
  esac
  # F7: the run froze the hashes of the code and the corpus it ran on
  $L check-run-config --run-dir "$SD/runs/$pr_id" --corpora-root "$(arm_corpora "$pr_arm")" \
    || stop_run infra "$pr_id: its run_config.json lacks the code or corpus hashes"
  run_health "$pr_id" "$pr_arm"
  : > "$SD/runs/$pr_id.complete"
  event DONE "$pr_id"
}

run_health() {  # run_health <run-id> <arm>: too many provider or parse failures means a technical fault
  if smoke; then event NOTE "SMOKE: health check skipped (canned replies)"; return 0; fi
  rh_kind=tier; if [ "$2" = CTX ]; then rh_kind=ctx; fi
  $P -m plantgraph.qa.exp0007 health --run-dir "$SD/runs/$1" --kind "$rh_kind" \
    || stop_run infra "$1: technical fault, read $LOGS/$1.log"
}

# ---- cache-only replay -----------------------------------------------------------------------------------

replay_run() {  # replay_run <arm> <run-id> <corpus> <role> [qroot [cache]]: no --allow-paid-calls, concurrency 1
  rp_arm=$1; rp_id=$2; rp_qroot=${5:-$QROOT}; rp_cache=${6:-$CACHE}; rp_new=INF-$2; rp_rc=0
  rm -rf "$SD/replays/$rp_new"
  # shellcheck disable=SC2046
  $P -m plantgraph.qa.harness --run-id "$rp_new" --experiment "$EXPERIMENT-REPLAY" --corpus "$3:$4" \
    $(arm_options "$rp_arm") --corpora-root "$(arm_corpora "$rp_arm")" --questions-root "$rp_qroot" \
    --runs-root "$SD/replays" --cache-path "$rp_cache" --concurrency 1 \
    --question-deadline-s "$(arm_deadline "$rp_arm")" > "$LOGS/$rp_new.log" 2>&1 || rp_rc=$?
  # exit 2 is a cache miss: the replay stopped early, which is a legitimate prefix at 1,000 sheets (ADR-0062)
  [ $rp_rc -eq 0 ] || [ $rp_rc -eq 2 ] || stop_run infra "replay $rp_new failed (exit $rp_rc), see $LOGS/$rp_new.log"
  rp_prefix_ok=no; case $rp_arm in CYP-A|F1-CYP) rp_prefix_ok=yes ;; esac
  rp_verdict=$($L replay-compare --replay-dir "$SD/replays/$rp_new" --run-dir "$SD/runs/$2" \
    --allow-prefix "$rp_prefix_ok") \
    || stop_run infra "replay $rp_new differs from $2: $rp_verdict"
  event NOTE "replay $rp_new: $rp_verdict"
}

# ---- the frozen state, checked before a stage that makes test runs -----------------------------------

require_frozen() {  # nothing the registered runs depend on changed since M3 froze it, and the drawn sets are as drawn
  sha256sum -c --quiet "$PREREG/E9.sha256" > "$LOGS/frozen_check.txt" 2>&1     || stop_run user "a frozen file changed since the E9 freeze, see $LOGS/frozen_check.txt (a defect found after M3 is reported, not fixed)"
  sha256sum -c --quiet "$PREREG/PREREG.sha256" >> "$LOGS/frozen_check.txt" 2>&1     || stop_run user "the pre-registration changed since the freeze, see $LOGS/frozen_check.txt"
  if [ -f "$ROOT/T9.sha256" ]; then
    sha256sum -c --quiet "$ROOT/T9.sha256" >> "$LOGS/frozen_check.txt" 2>&1       || stop_run user "a drawn plant or question set changed since M4 (T9.sha256), see $LOGS/frozen_check.txt"
  fi
}
