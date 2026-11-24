# Arms, capped paid runs and replays of the EXP-0009 launcher: sourced after lib.sh.
#
# A stage sets, before it calls anything here:
#   STEP   P1a | P1b | P1c | P1g, a key of the step ceilings in qa/exp0009/caps.py
#   SD     the stage's folder under $ROOT (its runs, cache, replays live there)
#   CACHE  the stage's response cache          EXPERIMENT  the name written into run_config.json
#   QROOT  where the question files are        PL_SCALE    100 or 1000, the plant's nominal scale
# Money rule (ADR-0068 decision 1): NO dry run. A run's cap is its question count x the tier's cost per
# question x 1.5, cut to the step ceiling and the runs ledger left; the balance must cover it. A resume
# adds what the run already spent. In --smoke the harness is the fake-transport one: no request leaves.

DEADLINE_S=120    # setting A of the cascade: 30 s Cypher timeout, 120 s per question

arm_spec() {  # arm_spec <CYP-A|AG|CYP-B|AG-B|CYP-GLM|AG-GLM>: sets AR_* for the arm (strategy, parameters, pin, cost tier, system)
  case $1 in
    CYP-A|CYP-B) AR_PARAMS=$INPUTS/params_cypher_v2t_a.json; AR_PIN=$INPUTS/pin_cypher_luna_low.json; AR_TIER=cyp; AR_CORPORA=$ROOT/cypcorp/plant_lines ;;
    AG|AG-B) AR_PARAMS=$INPUTS/params_agent_v2t.json; AR_PIN=$INPUTS/pin_agent_luna_final_high.json; AR_TIER=ag; AR_CORPORA=$ROOT/corpora ;;
    CYP-GLM) AR_PARAMS=$INPUTS/params_cypher_v2t_a.json; AR_PIN=$INPUTS/pin_cypher_glm_fireworks_low.json; AR_TIER=cyp; AR_CORPORA=$ROOT/cypcorp/plant_lines ;;
    AG-GLM) AR_PARAMS=$INPUTS/params_agent_v2t.json; AR_PIN=$INPUTS/pin_agent_glm_fireworks_high.json; AR_TIER=ag; AR_CORPORA=$ROOT/corpora ;;
    *) stop_run infra "unknown arm $1" ;;
  esac
  case $1 in CYP-A|CYP-GLM) AR_STRATEGY=cypher_rag_lines ;; AG|AG-GLM) AR_STRATEGY=graph_agent_lines ;;
    CYP-B) AR_STRATEGY=cypher_rag_lines_b ;; AG-B) AR_STRATEGY=graph_agent_lines_b ;; esac
  case $1 in *-B) AR_SYSTEM=B ;; *) AR_SYSTEM=A2 ;; esac   # the GLM arm is the A2 system with other pins
  AR_COST_ARM=$AR_SYSTEM; case $1 in *-GLM) AR_COST_ARM=GLM ;; esac   # which cost keys the caps use
  if smoke && [ "$AR_TIER" = cyp ]; then   # no Neo4j in the smoke: the agent stands in for the Cypher tier
    AR_STRATEGY=graph_agent_lines; if [ "$AR_SYSTEM" = B ]; then AR_STRATEGY=graph_agent_lines_b; fi
    AR_PARAMS=$INPUTS/params_agent_v2t.json; AR_PIN=$INPUTS/pin_agent_luna_final_high.json; AR_CORPORA=$ROOT/corpora
    if [ "$AR_COST_ARM" = GLM ]; then AR_PIN=$INPUTS/pin_agent_glm_fireworks_high.json; fi
  fi
  AR_NAME=$1
}

harness_cmd() {  # the command that runs the arm's harness (A2: the frozen one; B: `v2tb run`)
  if smoke; then
    if [ "$AR_SYSTEM" = B ]; then echo "$P -m plantgraph.qa.exp0009.smoke_harness b"; else echo "$P -m plantgraph.qa.exp0009.smoke_harness a2"; fi
  elif [ "$AR_SYSTEM" = B ]; then echo "$P -m plantgraph.qa.v2tb run"
  else echo "$P -m plantgraph.qa.harness"; fi
}

measured_args() { if [ -f "$STATE/measured_costs.json" ]; then echo "--measured $STATE/measured_costs.json"; fi; }
balance_args() { if smoke; then echo "--fake-balance ${E10_FAKE_BALANCE:-100}"; fi; }

paid_run() {  # paid_run <arm> <run-id> <corpus> <role>: one capped run, then its record checks
  pr_arm=$1; pr_id=$2; pr_corpus=$3; pr_role=$4
  arm_spec "$pr_arm"
  if [ -f "$SD/runs/$pr_id.complete" ]; then event NOTE "skip $pr_id (complete)"; return 0; fi
  # shellcheck disable=SC2046
  pr_cap=$($L run-cap --questions "$QROOT/$pr_corpus/questions.jsonl" --tier "$AR_TIER" --scale "$PL_SCALE" \
    --arm "$AR_COST_ARM" --step "$STEP" --root "$ROOT" --step-dir "$SD" --run-dir "$SD/runs/$pr_id" $(measured_args)) \
    || stop_run topup "no money left for $pr_id under the step ceiling or the \$26.87 runs ledger"
  # shellcheck disable=SC2046
  $L balance --needed "$pr_cap" $(balance_args) || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$pr_cap for $pr_id"
  # shellcheck disable=SC2046
  pr_cost=$($L cost-of --tier "$AR_TIER" --scale "$PL_SCALE" --arm "$AR_COST_ARM" $(measured_args)) || stop_run infra "no cost per question for $pr_id"
  event START "$pr_id arm $pr_arm on $pr_corpus, cap \$$pr_cap"
  pr_rc=0
  # shellcheck disable=SC2046
  $(harness_cmd) --run-id "$pr_id" --experiment "$EXPERIMENT" --corpus "$pr_corpus:$pr_role" \
    --strategy "$AR_STRATEGY" --strategy-params-json "$AR_PARAMS" --pin-json "$AR_PIN" \
    --corpora-root "$AR_CORPORA" --questions-root "$QROOT" --runs-root "$SD/runs" --cache-path "$CACHE" \
    --allow-paid-calls --cost-per-question-usd "$pr_cost" --max-spend-usd "$pr_cap" --concurrency 4 \
    --question-deadline-s "$DEADLINE_S" >> "$LOGS/$pr_id.log" 2>&1 || pr_rc=$?
  case $pr_rc in
    0) ;;
    3) event CAP "$pr_id reached its cap \$$pr_cap"; stop_run topup "$pr_id reached its spend cap of \$$pr_cap" ;;
    *) stop_run infra "$pr_id: harness exit $pr_rc, see $LOGS/$pr_id.log" ;;
  esac
  run_checks "$pr_id"
  : > "$SD/runs/$pr_id.complete"
  event DONE "$pr_id"
}

run_checks() {  # the records check (§19.11), the F7 hashes, the B code hashes and the health check of a finished run
  rc_dir=$SD/runs/$1
  $L records-check --run-dir "$rc_dir" || stop_run infra "$1: the measurement record is incomplete (calls, tokens, cost, latency, provider)"
  $L check-run-config --run-dir "$rc_dir" --corpora-root "$AR_CORPORA" \
    || stop_run infra "$1: its run_config.json lacks the code or corpus hashes"
  if [ "$AR_SYSTEM" = B ]; then
    $L b-code-write --run-dir "$rc_dir" 2> /dev/null || [ -f "$rc_dir/b_code.sha256" ] || stop_run infra "$1: cannot write b_code.sha256"
    if [ -f "$PREREG/B_FILES.sha256" ]; then
      $L b-code-check --run-dir "$rc_dir" --against "$PREREG/B_FILES.sha256" \
        || stop_run user "$1: its B files differ from the frozen B_FILES.sha256"
    fi
  fi
  if smoke; then return 0; fi
  $P -m plantgraph.qa.exp0007 health --run-dir "$rc_dir" --kind tier || stop_run infra "$1: technical fault, read $LOGS/$1.log"
}

replay_run() {  # replay_run <arm> <run-id> <corpus> <role>: cache-only replay, concurrency 1, compared with its run
  rp_arm=$1; rp_id=$2; rp_corpus=$3; rp_role=$4; rp_new=INF-$2; rp_rc=0
  arm_spec "$rp_arm"
  rp_marker=$SD/replays/$rp_new.replayed
  if [ -e "$rp_marker" ]; then event NOTE "skip replay $rp_new (done)"; return 0; fi
  rm -rf "$SD/replays/$rp_new"
  # shellcheck disable=SC2046
  $(harness_cmd) --run-id "$rp_new" --experiment "$EXPERIMENT-REPLAY" --corpus "$rp_corpus:$rp_role" \
    --strategy "$AR_STRATEGY" --strategy-params-json "$AR_PARAMS" --pin-json "$AR_PIN" \
    --corpora-root "$AR_CORPORA" --questions-root "$QROOT" --runs-root "$SD/replays" --cache-path "$CACHE" \
    --concurrency 1 --question-deadline-s "$DEADLINE_S" > "$LOGS/$rp_new.log" 2>&1 || rp_rc=$?
  # exit 2 is a cache miss: a Cypher replay may stop early near the 30 s limit (ADR-0062), a legitimate prefix
  [ $rp_rc -eq 0 ] || [ $rp_rc -eq 2 ] || stop_run infra "replay $rp_new failed (exit $rp_rc), see $LOGS/$rp_new.log"
  rp_prefix=no; case $rp_arm in CYP-*) rp_prefix=yes ;; esac
  rp_verdict=$($L replay-compare --replay-dir "$SD/replays/$rp_new" --run-dir "$SD/runs/$rp_id" --allow-prefix "$rp_prefix") \
    || stop_run infra "replay $rp_new differs from $rp_id"
  event NOTE "replay $rp_new: $rp_verdict"
  echo "$rp_id $rp_verdict" >> "$SD/replay_verdicts.txt"
  : > "$rp_marker"
}

require_frozen() {  # nothing the sealed runs depend on changed since F10 froze it, and the drawn sets are as drawn
  sha256sum -c --quiet "$PREREG/E10.sha256" > "$LOGS/frozen_check.txt" 2>&1 \
    || stop_run user "a frozen file changed since the E10 freeze, see $LOGS/frozen_check.txt"
  sha256sum -c --quiet "$PREREG/PREREG.sha256" >> "$LOGS/frozen_check.txt" 2>&1 \
    || stop_run user "the pre-registration changed since the freeze, see $LOGS/frozen_check.txt"
  if [ -f "$ROOT/D10.sha256" ]; then
    sha256sum -c --quiet "$ROOT/D10.sha256" >> "$LOGS/frozen_check.txt" 2>&1 \
      || stop_run user "a drawn plant or question set changed since B10 (D10.sha256), see $LOGS/frozen_check.txt"
  fi
}
