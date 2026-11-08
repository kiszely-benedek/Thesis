# M4: generate the test plants and draw their question sets, then the free gates. Sourced by run_all.sh.
#
# First time any test plant exists: it follows the freeze (M3), which is the point of the ordering.
#   plants     ladder (1/3/10/30 sheets), 5 sealed plants at 100 and at 1,000 sheets, the duplication points d0/d50
#              of the first 100-sheet plant, and the eight EXP-0004 tag-variant (V) corpora
#   questions  sealed recipe (10 per family) for sealed and duplication plants; ladder recipe (4 per family of
#              the dev and held-out splits, 70-92 questions) for the ladder; 2 per family from the first
#              1,000-sheet plant for the concurrency-1 control
#   gates      round trip and identity (G1, S16) when built, LINE-01 on every plant, blocking completeness I0
#              >= 0.99 on every V corpus, ContextRAG prompt sizes, and T9.sha256 over everything drawn
# Free: no model call, no Neo4j.

I0_MIN_COMPLETENESS=0.99
# the splits a question set draws from; a tiny smoke plant has no held-out family to draw
SPLITS=dev-old,dev-new,held-out
SMOKE_SPLITS=dev-old,dev-new

ladder_questions() {  # the ladder recipe of EXP-0007 make_set.sh: full pool, then 4 per family
  lq_id=$1; lq_out=$ROOT/questions/$lq_id
  if [ -f "$lq_out/questions.jsonl" ]; then return 0; fi
  lq_bin=500; lq_unans=100; lq_fam=20; lq_pick=4; lq_splits=$SPLITS
  if smoke; then lq_bin=2; lq_unans=2; lq_fam=1; lq_pick=1; lq_splits=$SMOKE_SPLITS; fi
  try $P -m plantgraph.qa.questions.sealed_set --corpus-id "$lq_id" \
    --ingest-json "$ROOT/corpora/$lq_id/ingest.json" --seed 41 --n-per-bin "$lq_bin" --n-unanswerable "$lq_unans" \
    --n-per-family "$lq_fam" --n-per-wording 1 --sample-seed 20261101 --out "$ROOT/qfull/$lq_id" \
    --pool-out "$ROOT/qpool/$lq_id" > "$LOGS/questions_$lq_id.log"
  try $P -m plantgraph.qa.questions.per_family --in "$ROOT/qfull/$lq_id/questions.jsonl" \
    --splits "$ROOT/qfull/$lq_id/splits.json" --only-splits "$lq_splits" --n "$lq_pick" \
    --seed 20261101 --out "$lq_out"
}

plant_and_questions() {  # kind-specific question recipe is chosen by the caller through $QUESTIONS_FN
  build_plant
  line_view_gate "$PL_ID"
  "$QUESTIONS_FN" "$PL_ID"
}

variant_corpus() {  # an EXP-0004 V corpus, built by `exp0004 build`; its blocking completeness (I0) is a gate
  vc_dir=$ROOT/p3/$PL_ID
  if [ ! -f "$vc_dir/corpus.json" ]; then
    vc_sheets=$PL_SHEETS
    event NOTE "build V corpus $PL_ID"
    try $P -m plantgraph.exp0004 build --corpus-id "$PL_ID" --target-sheets "$vc_sheets" --seed "$PL_SEED" \
      --duplication-rate "$PL_RATE" --families format naming --out "$vc_dir" > /dev/null
  fi
  vc_c=$($P -c "import json,sys;print(json.load(open(sys.argv[1]))['description']['blocking']['pair_completeness'])" "$vc_dir/corpus.json") \
    || stop_run infra "cannot read the blocking completeness of $PL_ID"
  if [ "$vc_c" = None ] && smoke; then   # a tiny smoke plant can have no true duplicate pair to find
    event NOTE "SMOKE: $PL_ID has no true pairs, so no completeness"; return 0
  fi
  $P -c "import sys; sys.exit(0 if float(sys.argv[1]) >= float(sys.argv[2]) else 1)" "$vc_c" "$I0_MIN_COMPLETENESS" \
    || gate_fail "I0" "$PL_ID: blocking completeness $vc_c is below $I0_MIN_COMPLETENESS"
  event "GATE PASS" "I0 on $PL_ID: completeness $vc_c"
}

control_questions() {  # two per family from the first 1,000-sheet plant, for the concurrency-1 control
  cq_in=$ROOT/questions/H1000g21p1; cq_out=$ROOT/questions_c1/H1000g21p1
  if [ -f "$cq_out/questions.jsonl" ]; then return 0; fi
  cq_splits=$SPLITS; if smoke; then cq_splits=$SMOKE_SPLITS; fi
  try $P -m plantgraph.qa.questions.per_family --in "$cq_in/questions.jsonl" --splits "$cq_in/splits.json" \
    --only-splits "$cq_splits" --n 2 --seed 20261031 --out "$cq_out"
}

prompt_sizes() {  # ContextRAG's prompt size on the ladder (free) and the corpus-dependent prompt inputs
  ps_args=
  for ps_id in H1g21 H3g21 H10g21 H30g21; do ps_args="$ps_args $ps_id=$ROOT/corpora/$ps_id/ingest.json"; done
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.exp0001 prompt-size $ps_args --json "$ROOT/prompt_size.json" > /dev/null
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.exp0007 corpus-prompt-hashes $ps_args --out "$ROOT/prompt_inputs.json"
}

write_t9() {  # T9.sha256: the plants and question sets as drawn; written once, never overwritten
  [ ! -e "$ROOT/T9.sha256" ] || stop_run infra "$ROOT/T9.sha256 exists; a drawn set is never overwritten"
  sha256sum "$PREREG/E9.commit" "$ROOT"/corpora/*/ingest.json "$ROOT"/questions/*/questions.jsonl \
    "$ROOT"/questions_c1/*/questions.jsonl "$ROOT/prompt_size.json" > "$ROOT/T9.sha256" \
    || stop_run infra "cannot hash the drawn sets"
  event NOTE "T9.sha256 written: $(wc -l < "$ROOT/T9.sha256") hashes"
}

stage_M4() {
  [ -f "$PREREG/E9.sha256" ] || stop_run user "no E9 freeze ($PREREG/E9.sha256): run M3 before any test plant exists"
  mkdir -p "$ROOT/qfull" "$ROOT/qpool" "$ROOT/p3"
  QUESTIONS_FN=ladder_questions
  once ladder for_each_plant ladder plant_and_questions
  QUESTIONS_FN=sealed_questions
  once sealed for_each_plant sealed plant_and_questions
  once descriptive for_each_plant descriptive plant_and_questions
  once variants for_each_plant p3 variant_corpus
  once control control_questions
  once prompt_sizes prompt_sizes
  once t9 write_t9
  outputs "$ROOT/T9.sha256"
}
