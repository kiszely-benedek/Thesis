# Plants, Neo4j loads and question sets of the EXP-0008 launcher: sourced after lib.sh.
#
# Layout under $ROOT:  corpora/<id>/ingest.json      built without Neo4j (the agent tier reads this)
#                      neo4jplant/<id>/ingest.json   the plant that was loaded into Neo4j (Cypher tier)
#                      questions/<id>/questions.jsonl, qpool/<id>/  the question set and its pool
# One corpus is in Neo4j at a time: every load wipes the database first (--fresh-database).
# In --smoke the "load" builds the same files with --no-neo4j, so no database is touched.

# Plan lines are `id sheets seed duplication_rate variant`; the plan module is the single source.
plan_to_file() {  # plan_to_file <kind>: sets PLAN_FILE
  PLAN_FILE=$LOGS/plan_$1.txt
  pf_flag=; if smoke; then pf_flag=--smoke; fi
  # shellcheck disable=SC2086
  $L plan "$1" $pf_flag > "$PLAN_FILE" || stop_run infra "cannot list the $1 plants (are the seeds drawn? $PREREG/seeds.json)"
}

for_each_plant() {  # for_each_plant <kind> <function>: the function sees PL_ID PL_SHEETS PL_SEED PL_RATE PL_VARIANT
  plan_to_file "$1"; fe_fn=$2
  exec 3< "$PLAN_FILE"   # fd 3, so the commands inside the function never read the plan from stdin
  while read -r PL_ID PL_SHEETS PL_SEED PL_RATE PL_VARIANT <&3; do
    "$fe_fn"
  done
  exec 3<&-
}

# ---- building and loading --------------------------------------------------------------------------

build_plant() {  # build_plant: the plant PL_* without Neo4j; round trip (G1) and identity (S16) checked
  bp_dir=$ROOT/corpora/$PL_ID
  if [ -f "$bp_dir/ingest.json" ]; then return 0; fi
  event NOTE "build $PL_ID ($PL_SHEETS sheets, seed $PL_SEED, duplication $PL_RATE)"
  try $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$PL_SHEETS" --seed "$PL_SEED" \
    --headline-duplication-rate "$PL_RATE" --corpus-id "$PL_ID" --check --no-neo4j --out "$bp_dir" \
    > "$LOGS/corpus_$PL_ID.json"
  try $P -m plantgraph.qa.exp0007 check-ingest --ingest-json "$bp_dir/ingest.json" --corpus-id "$PL_ID"
}

neo4j_load() {  # neo4j_load <plant_lines|plant>: the plant PL_* alone in the database (smoke: files only)
  nl_dir=$ROOT/neo4jplant/$PL_ID
  nl_args="--headline-v2 --target-sheets $PL_SHEETS --seed $PL_SEED --headline-duplication-rate $PL_RATE"
  if smoke; then
    event NOTE "SMOKE: no Neo4j, $PL_ID written as files only"
    nl_mode="--no-neo4j"
  else
    event NOTE "load $PL_ID into Neo4j ($1), wiping the database first"
    nl_mode="--store-profile $1 --fresh-database"
    if [ -n "${E9_NEO4J_HOME:-}" ]; then nl_mode="$nl_mode --neo4j-home $E9_NEO4J_HOME"; fi
  fi
  rm -rf "$nl_dir"
  # shellcheck disable=SC2086
  try $P -m plantgraph.ingest synthetic $nl_args --corpus-id "$PL_ID" $nl_mode --out "$nl_dir" \
    > "$LOGS/load_$PL_ID.json" 2> "$LOGS/load_$PL_ID.err"
  # A reload rewrites ingest.json (its timings differ), but a run freezes that file's hash (F7) and refuses
  # to resume on a changed one. The Cypher tier therefore reads a copy that is made once and never replaced.
  mkdir -p "$ROOT/cypcorp/$1/$PL_ID"
  if [ ! -f "$ROOT/cypcorp/$1/$PL_ID/ingest.json" ]; then
    try cp "$nl_dir/ingest.json" "$ROOT/cypcorp/$1/$PL_ID/ingest.json"
  fi
}

drop_tmp_database() {  # the first measurement's temporary database goes away before anything is loaded
  if smoke; then event NOTE "SMOKE: e7tune not dropped (no Neo4j)"; return 0; fi
  try $P -m plantgraph.qa.exp0007 drop-neo4j-database --database e7tune
}

# ---- question sets ---------------------------------------------------------------------------------

dev_questions() {  # dev_questions <id>: the dev recipe (pool, then 10 per family), for dev and validation plants
  dq_id=$1; dq_out=$ROOT/questions/$dq_id
  if [ -f "$dq_out/questions.jsonl" ]; then return 0; fi
  dq_bin=97; dq_fam=10
  if smoke; then dq_bin=2; dq_fam=1; fi
  if [ ! -f "$ROOT/qpool/$dq_id/questions.jsonl" ]; then   # M0's memory probe may have drawn the pool already
    try $P -m plantgraph.qa.questions --corpus-id "$dq_id" --ingest-json "$ROOT/corpora/$dq_id/ingest.json" \
      --seed 1 --n-per-bin "$dq_bin" --n-unanswerable "$dq_bin" --out "$ROOT/qpool/$dq_id" > "$LOGS/pool_$dq_id.log"
  fi
  try $P -m plantgraph.qa.questions.per_family --in "$ROOT/qpool/$dq_id/questions.jsonl" --n "$dq_fam" \
    --seed 20261101 --out "$dq_out"
}

sealed_questions() {  # sealed_questions <id>: 10 per family, the sealed recipe of EXP-0007 (design 5.1)
  sq_id=$1; sq_out=$ROOT/questions/$sq_id
  if [ -f "$sq_out/questions.jsonl" ]; then return 0; fi
  sq_bin=500; sq_unans=100; sq_fam=10; sq_word=5
  if smoke; then sq_bin=2; sq_unans=2; sq_fam=1; sq_word=1; fi
  try $P -m plantgraph.qa.questions.sealed_set --corpus-id "$sq_id" \
    --ingest-json "$ROOT/corpora/$sq_id/ingest.json" --seed 31 --n-per-bin "$sq_bin" \
    --n-unanswerable "$sq_unans" --n-per-family "$sq_fam" --n-per-wording "$sq_word" \
    --sample-seed 20261031 --out "$sq_out" --pool-out "$ROOT/qpool/$sq_id" > "$LOGS/questions_$sq_id.log"
}

# ---- free gates of a plant -------------------------------------------------------------------------

line_view_gate() {  # line_view_gate <id>: LINE-01, the line view equals the gold's own walk (P = R = 1)
  try $P -m plantgraph.qa.harness.line_view_fidelity --corpus-id "$1" \
    --ingest-json "$ROOT/corpora/$1/ingest.json"
}

n_sheets_of() { $P -c "import json,sys;print(json.load(open(sys.argv[1]))['counts']['n_sheets'])" "$1"; }

check_loaded_matches() {  # check_loaded_matches <id>: the loaded plant has the built plant's sheet count
  cm_built=$(n_sheets_of "$ROOT/corpora/$1/ingest.json")
  cm_loaded=$(n_sheets_of "$ROOT/neo4jplant/$1/ingest.json")
  [ "$cm_built" = "$cm_loaded" ] || stop_run infra "loaded $1 has $cm_loaded sheets, the built plant $cm_built"
}
