# M6: the sealed R5 measurement on ten plants. Sourced by run_all.sh. PAID, in three sub-stages.
#
#   M6a  V2T-A2 on the ten sealed plants (5 at 100, 5 at 1,000 sheets): the Cypher tier on the plant_lines store,
#        then the agent tier, each followed by its cache-only replay.   Run ids S7-CYP-<id>, S7-AG-<id>.
#   M6b  the frozen F1 baseline on the same ten plants and questions (plain `plant` store). S7F1-CYP/AG-<id>.
#   M6c  the descriptive arms: duplication points d0 and d50 of the first 100-sheet plant, and the concurrency-1
#        control (the agent tier on 2 questions per family of the first 1,000-sheet plant, run one at a time
#        with its own cache so it cannot reuse the main run's answers).
# (The run ids keep the first measurement's `S7` prefix because the duplication report reads that name.)
# Nothing else runs while a timed arm runs: the latency claims K1 and K3 depend on it.

sealed_load() {  # the plant PL_* in Neo4j with profile $1, checked against the built plant
  neo4j_load "$1"
  check_loaded_matches "$PL_ID"
}

m6a_plant() {
  once "load_$PL_ID" sealed_load plant_lines
  paid_run CYP-A "S7-CYP-$PL_ID" "$PL_ID" test
  replay_run CYP-A "S7-CYP-$PL_ID" "$PL_ID" test
  paid_run AG "S7-AG-$PL_ID" "$PL_ID" test
  replay_run AG "S7-AG-$PL_ID" "$PL_ID" test
}

m6b_plant() {
  once "load_plain_$PL_ID" sealed_load plant
  paid_run F1-CYP "S7F1-CYP-$PL_ID" "$PL_ID" test
  replay_run F1-CYP "S7F1-CYP-$PL_ID" "$PL_ID" test
  paid_run F1-AG "S7F1-AG-$PL_ID" "$PL_ID" test
  replay_run F1-AG "S7F1-AG-$PL_ID" "$PL_ID" test
}

m6c_plant() {  # d0 and d50 of the first 100-sheet plant, same arms as M6a
  m6a_plant
}

m6c_control() {  # concurrency 1, its own cache and question root (design 5.1: 46 questions)
  paid_run AG "S7-AG-H1000g21p1-C1" H1000g21p1 test "$ROOT/questions_c1" 1 "$SD/cache_c1.sqlite"
  replay_run AG "S7-AG-H1000g21p1-C1" H1000g21p1 test "$ROOT/questions_c1" "$SD/cache_c1.sqlite"
}

sealed_stage_setup() {  # sealed_stage_setup <step> <folder>
  STEP=$1; SD=$ROOT/$2; CACHE=$SD/cache.sqlite
  AG_CORPORA=$ROOT/corpora; QROOT=$ROOT/questions
  mkdir -p "$SD/runs" "$SD/replays"
  require_frozen
}

stage_M6a() {
  sealed_stage_setup M6a m6a; EXPERIMENT=EXP-0008-R5
  for_each_plant sealed m6a_plant
  outputs "$SD/runs/S7-AG-H1000g21p5/answers.jsonl" "$SD/runs/S7-CYP-H100g21p5/answers.jsonl"
}

stage_M6b() {
  sealed_stage_setup M6b m6b; EXPERIMENT=EXP-0008-R5-F1
  for_each_plant sealed m6b_plant
  outputs "$SD/runs/S7F1-AG-H1000g21p5/answers.jsonl" "$SD/runs/S7F1-CYP-H100g21p5/answers.jsonl"
}

stage_M6c() {
  sealed_stage_setup M6c m6c; EXPERIMENT=EXP-0008-R5-DESC
  for_each_plant descriptive m6c_plant
  # the control needs H1000g21p1's agent graph only; no database is involved
  m6c_control
  outputs "$SD/runs/S7-AG-H100g21p1d50/answers.jsonl" "$SD/runs/S7-AG-H1000g21p1-C1/answers.jsonl"
}
