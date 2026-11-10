# M5: the R4 ladder, one ladder of 1, 3, 10 and 30 sheets (X1, X2). Sourced by run_all.sh. PAID.
#
# V2T-A2 at setting A (Cypher tier on the plant_lines store, agent tier) on every size, and ContextRAG high
# (the whole plant in one prompt) on 1, 3 and 10 sheets, which is the dearest arm per question. Run ids start
# with E8 because the ladder report (`exp0001 report --edition v21`) looks for `E8-CYP-<id>`, `E8-AG-<id>` and
# `E8-CTXH-<id>`. The report reads <root>/corpora, <root>/questions and <root>/runs, so the stage copies its
# plants and questions beside its runs. Each run has a dry-run cap, a ledger check and a replay.

LADDER="H1g21 H3g21 H10g21 H30g21"
CTX_LADDER="H1g21 H3g21 H10g21"

ladder_copy_inputs() {  # the report root holds what it reads
  for lc_id in $LADDER; do
    mkdir -p "$SD/corpora" "$SD/questions"
    cp -r "$ROOT/corpora/$lc_id" "$SD/corpora/" && cp -r "$ROOT/questions/$lc_id" "$SD/questions/" \
      || stop_run infra "cannot copy $lc_id into $SD"
  done
}

ladder_cypher() {  # one plant in Neo4j at a time
  for lc_id in $LADDER; do
    PL_ID=$lc_id
    plan_line=$(grep "^$lc_id " "$LOGS/plan_ladder.txt")
    set -- $plan_line; PL_SHEETS=$2; PL_SEED=$3; PL_RATE=$4; PL_VARIANT=$5
    once "load_$lc_id" neo4j_load plant_lines
    check_loaded_matches "$lc_id"
    paid_run CYP-A "E8-CYP-$lc_id" "$lc_id" test "$SD/questions"
    replay_run CYP-A "E8-CYP-$lc_id" "$lc_id" test "$SD/questions"
  done
}

ladder_agent() {
  for lc_id in $LADDER; do
    paid_run AG "E8-AG-$lc_id" "$lc_id" test "$SD/questions"
    replay_run AG "E8-AG-$lc_id" "$lc_id" test "$SD/questions"
  done
}

ladder_context() {
  for lc_id in $CTX_LADDER; do
    TIER_SUFFIX=$lc_id   # ContextRAG's cost per question grows with the plant: a size-specific cap
    paid_run CTX "E8-CTXH-$lc_id" "$lc_id" test "$SD/questions"
    TIER_SUFFIX=
    replay_run CTX "E8-CTXH-$lc_id" "$lc_id" test "$SD/questions"
  done
}

stage_M5() {
  STEP=M5; SD=$ROOT/ladder; CACHE=$SD/cache.sqlite; EXPERIMENT=EXP-0008-R4
  AG_CORPORA=$SD/corpora; QROOT=$SD/questions
  mkdir -p "$SD/runs" "$SD/replays"
  require_frozen
  once copy ladder_copy_inputs
  plan_to_file ladder
  ladder_cypher
  ladder_agent
  ladder_context
  outputs "$SD/runs/E8-AG-H30g21/answers.jsonl" "$SD/runs/E8-CYP-H30g21/answers.jsonl" "$SD/runs/E8-CTXH-H10g21/answers.jsonl"
}
