# Helpers of the R4 / R5 scripts, which measure the tuned system V2T-A (ADR-0061, setting A):
# sourced after lib.sh and tune_lib.sh, never run on its own. A stage script sets S, CACHE,
# EXPERIMENT, CYP_CORPORA, AG_CORPORA and QROOT first, as for lib.sh.
# Variable pitfall: lib.sh's tier_run and replay set the shell globals `tier`, `id`, `orig`, `dir`,
# `cache`; every helper and every loop here uses its own prefixed names.

V2T_LABEL=V2T-A

# ---- the freeze E7 ---------------------------------------------------------------------------

# What E7 hashes besides the data it writes: every tracked file of the V2T system (tune_lib.sh
# V2T_FROZEN_FILES). The run scripts check these hashes and the paths' git state.
v2t_system_hashes() { git ls-files $V2T_FROZEN_FILES | xargs sha256sum; }

# Succeeds (status 0) when a V2T system file or an input differs from <commit>, committed or not.
# listing_E7.json is the one input that appears after E7 (make_set.sh writes it), so it is left out.
v2t_frozen_changed_since() {
  fz_skip=":(exclude)$IN/listing_E7.json"
  if ! git diff --quiet "$1" -- $V2T_FROZEN_FILES $IN "$fz_skip"; then return 0; fi
  if [ -n "$(git status --porcelain -- $V2T_FROZEN_FILES $IN "$fz_skip")" ]; then return 0; fi
  return 1
}

# R4 / R5 start only on the system E7 froze. The commit itself may move on (the user commits the
# generated data after make_set.sh), so the test is on the system's files, not on HEAD.
require_v2t_freeze() {
  [ -f $X/E7.commit ] && [ -f $X/E7.sha256 ] && [ -f $X/E7.system ] \
    || die "no E7 freeze file: run make_set.sh --system-label $V2T_LABEL on the frozen system first"
  [ "$(cat $X/E7.system)" = "$V2T_LABEL" ] || die "E7 froze '$(cat $X/E7.system)', these scripts run $V2T_LABEL"
  if v2t_frozen_changed_since "$(cat $X/E7.commit)"; then
    die "a V2T system file (tune_lib.sh V2T_FROZEN_FILES) or an input differs from E7 ($(cat $X/E7.commit)): the system is not frozen"
  fi
  sha256sum -c --quiet $X/E7.sha256 || die "a file hashed in E7.sha256 changed since E7 (system file, input, question set or cap file)"
  echo "frozen system: $V2T_LABEL at E7 $(cat $X/E7.commit)"
}

# Setting A (cascade/limits.py): 30 s Cypher timeout, 120 s per question. Prints the deadline and
# refuses when the Cypher params file does not carry the setting's timeout.
setting_a_deadline() {
  $EX setting-deadline --setting A --cypher-params $IN/params_cypher_v2t_a.json \
    || die "the Cypher params of V2T-A do not match limits.SETTING_A"
}

# The ContextRAG reference arm (CTX, EXP-0001's ctx-high: whole plant in one prompt, Luna at high
# effort) is run on the small ladder only; it has no params file and its deadline is 300 s.
CTX_DEADLINE_S=300
v2t_arm_options() {
  case $1 in
    CTX) echo "--strategy context_rag --pin-json $IN/pin_agent_luna_final_high.json" ;;
    *) arm_options "$1" ;;
  esac
}

# ---- one run, one replay ---------------------------------------------------------------------

# Arms (tune_lib.sh arm_options): CYP-A and AG are V2T-A; F1-CYP and F1-AG are the frozen F1 tiers.
v2t_run() {  # v2t_run <arm> <run-id> <corpus> <smoke|full> <deadline-s> [<questions-root> [<concurrency> [<cache>]]]
  vr_arm=$1; vr_id=$2; vr_corpus=$3; vr_stage=$4; vr_deadline=$5
  vr_qroot=${6:-$QROOT}; vr_conc=${7:-4}; vr_cache=${8:-$CACHE}
  # ContextRAG is judged by its own health rule (health.py): a long prompt may time out
  HEALTH_KIND=; [ "$vr_arm" != CTX ] || HEALTH_KIND=ctx
  vr_cap=$(cap_of "$vr_id") || die "no cap for $vr_id"; vr_cost=$(cost_of "$vr_id") || die "no cost for $vr_id"
  echo "=== $(date +%T) $vr_id ($vr_stage, cap \$$vr_cap)"; vr_rc=0
  # the cap goes into run_config.json (max_spend_usd) before the first call
  $P -m plantgraph.qa.harness --run-id "$vr_id" --experiment "$EXPERIMENT" --corpus "$vr_corpus:test" \
    $(v2t_arm_options "$vr_arm") --corpora-root "$(arm_corpora "$vr_arm")" --questions-root "$vr_qroot" \
    --runs-root "$S/runs" --cache-path "$vr_cache" --allow-paid-calls --cost-per-question-usd "$vr_cost" \
    --max-spend-usd "$vr_cap" --concurrency "$vr_conc" --question-deadline-s "$vr_deadline" \
    >> "$S/logs/$vr_id.log" 2>&1 || vr_rc=$?
  finish "$vr_id" $vr_rc "$vr_stage"
}

v2t_replay() {  # v2t_replay <arm> <run-id> <corpus> <deadline-s> [<questions-root> [<cache>]]: cache only, concurrency 1
  rp_arm=$1; rp_id=$2; rp_corpus=$3; rp_deadline=$4; rp_qroot=${5:-$QROOT}; rp_cache=${6:-$CACHE}
  replay "$rp_id" "$S/runs/$rp_id" "$rp_cache" "$rp_deadline" --corpus "$rp_corpus:test" \
    $(v2t_arm_options "$rp_arm") --corpora-root "$(arm_corpora "$rp_arm")" --questions-root "$rp_qroot"
}

# ---- Neo4j load of one corpus ----------------------------------------------------------------

# Cypher arms read Neo4j: V2T-A the `plant_lines` profile, F1 the plain `plant` profile. One corpus
# alone in the database (fresh database), then checked against the corpus the questions were drawn on.
load_corpus() {  # load_corpus <corpus> <sheets> <seed> <plant_lines|plant> [more ingest options]
  lc_corpus=$1; lc_sheets=$2; lc_seed=$3; lc_profile=$4; shift 4
  echo "=== $(date +%T) load $lc_corpus ($lc_profile) into $NEO4J_DATABASE"
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$lc_sheets" --seed "$lc_seed" "$@" \
    --store-profile "$lc_profile" --corpus-id "$lc_corpus" --fresh-database $(neo4j_home_args) \
    --out "$CYP_CORPORA/$lc_corpus" > "$S/logs/load_${lc_corpus}_$lc_profile.json" \
    2> "$S/logs/load_${lc_corpus}_$lc_profile.err" \
    || die "loading $lc_corpus ($lc_profile) failed, see $S/logs/load_${lc_corpus}_$lc_profile.err"
  check_loaded_matches "$CYP_CORPORA/$lc_corpus/ingest.json" "$AG_CORPORA/$lc_corpus/ingest.json"
}
