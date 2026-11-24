# P1g: the user's GLM comparison arm (design 20, task T13b). PAID. Sourced by run_all.sh.
#
# A small descriptive arm: the frozen V2T-A2 system and policy (cascade_v4_iso) with GLM 5.3 Flash on one pinned
# host (pins in inputs/, effort per tier as A2: Cypher low, agent high) instead of GPT-6 Luna. It runs on the
# FIRST sealed plant of each scale in plan.json order (the rule PREREG A fixes before any plant exists), scope R
# questions only: the A2 question file with its scope X questions taken out, every other line untouched.
# Per plant: load A; G9-GLM-CYP-<id> and its replay; G9-GLM-AG-<id> and its replay. Every run is replayed
# cache-only, as every sealed run is (ADR-0068 decision 4). It runs after P1c, when P1's actual spend is known.
# Money: a hard cap of $2.50 for the stage, with its own estimate NOTE. Before the first call the stage checks that
# the runs ledger and the OpenRouter balance cover what is left of the cap; if not it stops [top-up or restart].
# No gate, no claim, no role in Q4: the report (END) only describes GLM - Luna on the same questions.

p1g_questions() {  # the arm's question files, written once from the A2 files of B10
  try $L glm-questions --root "$ROOT" --prereg "$PREREG" > "$LOGS/glm_questions.log"
}

p1g_preflight() {  # the cap must fit the runs ledger and the balance before anything is paid
  pg_needed=$($L glm-room --root "$ROOT") \
    || stop_run topup "the runs ledger has no room for the GLM arm's \$2.50 cap"
  # shellcheck disable=SC2046
  $L balance --needed "$pg_needed" $(balance_args) \
    || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$pg_needed for the GLM arm"
}

p1g_plant() {  # the plant PL_ID: the Cypher tier needs it loaded, the agent tier reads files
  neo4j_load_a
  paid_run CYP-GLM "G9-GLM-CYP-$PL_ID" "$PL_ID" test
  replay_run CYP-GLM "G9-GLM-CYP-$PL_ID" "$PL_ID" test
  paid_run AG-GLM "G9-GLM-AG-$PL_ID" "$PL_ID" test
  replay_run AG-GLM "G9-GLM-AG-$PL_ID" "$PL_ID" test
}

stage_P1g() {
  SD=$ROOT/p1g; STEP=P1g; CACHE=$SD/cache.sqlite; EXPERIMENT=EXP-0009-GLM; QROOT=$SD/questions
  mkdir -p "$SD/runs" "$SD/replays"
  require_frozen
  once questions p1g_questions
  event NOTE "$($L glm-estimate --root "$ROOT" --prereg "$PREREG")"
  p1g_preflight
  for_each_plant glm p1g_plant
  plan_to_file glm
  pg_outputs=
  while read -r pg_id _pg_scale _pg_seed; do
    pg_outputs="$pg_outputs $SD/runs/G9-GLM-CYP-$pg_id/answers.jsonl $SD/runs/G9-GLM-AG-$pg_id/answers.jsonl"
  done < "$PLAN_FILE"
  # shellcheck disable=SC2086
  outputs $pg_outputs
}
