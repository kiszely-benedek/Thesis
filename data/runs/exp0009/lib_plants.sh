# Plants, Neo4j loads and question sets of the EXP-0009 launcher: sourced after lib.sh.
#
# Layout under $ROOT:  prereg/plan.json                  the draw: every plant, size, seed and tagging
#                      corpora/<id>/ingest.json          A corpus, built without Neo4j (the agent tier reads it)
#                      corpora/<id>B/                    its B twin: relabelled ingest.json + operating_positions.json
#                      neo4jplant/<id>/ingest.json       the plant as loaded into Neo4j
#                      cypcorp/plant_lines/<id>[B]/      what the Cypher tier reads (kept once, never replaced)
#                      qpool/<id>/  questions/<id>[B]/   pools and question files
# ONE corpus is in Neo4j at a time: every load wipes the database first. In --smoke a "load" writes the
# same files and touches no database. The Python behind each function is a command of $L.

plan_to_file() {  # plan_to_file <dev|probe|validation|sealed|all>: sets PLAN_FILE (lines: id scale seed)
  PLAN_FILE=$LOGS/plan_$1.txt
  $L plan-list "$1" --prereg "$PREREG" > "$PLAN_FILE" \
    || stop_run infra "cannot list the $1 plants (has the draw run? $PREREG/plan.json)"
}

for_each_plant() {  # for_each_plant <kind> <function>: the function sees PL_ID PL_SCALE PL_SEED
  plan_to_file "$1"; fe_fn=$2
  exec 3< "$PLAN_FILE"
  while read -r PL_ID PL_SCALE PL_SEED <&3; do
    "$fe_fn"
  done
  exec 3<&-
}

smoke_flag() { if smoke; then echo --smoke; fi; }

# ---- memory probe (R6) -------------------------------------------------------------------------------
# A 1,000-sheet build or pool is the first run of its kind on this machine; VALVES_ON_PATH once peaked at 8.75 GB.
# Those steps run under `memory-probe` (peak resident memory of the command and its children): the peak goes into
# the run log, and a step that passes the limit fails. Smaller plants run plain.
MEM_LIMIT_GIB=10

probed() {  # probed <json> <command...>: run the command, under the memory probe for a 1,000-sheet plant (PL_SCALE)
  pd_json=$1; shift
  if smoke || [ "$PL_SCALE" != 1000 ]; then "$@"; return; fi
  $L memory-probe --out "$pd_json" --limit-gib "$MEM_LIMIT_GIB" -- "$@"
}

memory_note() {  # memory_note <what> <probe json>: the probe's peak memory into the run log (nothing if it did not run)
  if [ -f "$2" ]; then event NOTE "memory: $1 peaked at $($L peak-gib --file "$2") GiB (limit $MEM_LIMIT_GIB)"; fi
}

# ---- building (free) ------------------------------------------------------------------------------

build_plant() {  # the plant PL_ID: A corpus, B relabel, positions, and every build-time gate
  bp_dir=$ROOT/corpora/$PL_ID
  if [ -f "$bp_dir/gates.json" ]; then return 0; fi
  rm -rf "$bp_dir" "$ROOT/corpora/${PL_ID}B"   # a build that died half way left a folder behind
  event NOTE "build $PL_ID (scale $PL_SCALE, seed $PL_SEED)"
  # shellcheck disable=SC2046
  probed "$LOGS/mem_build_$PL_ID.json" $L build --root "$ROOT" --prereg "$PREREG" --plant "$PL_ID" $(smoke_flag) \
    > "$LOGS/build_$PL_ID.txt" 2>&1 \
    || { cat "$LOGS/build_$PL_ID.txt"; stop_run user "the build or a build gate of $PL_ID failed (G0c, G0g, G0k, line view, G0-B, or the 10 GiB memory probe), see $LOGS/build_$PL_ID.txt"; }
  memory_note "build $PL_ID" "$LOGS/mem_build_$PL_ID.json"
  gate_pass "build gates of $PL_ID: $(tr '\n' ' ' < "$LOGS/build_$PL_ID.txt" | cut -c1-200)"
}

# ---- Neo4j loads (paid stages only) -----------------------------------------------------------------

neo4j_load_a() {  # the plant PL_ID, A corpus, alone in the database with plant_lines
  if ! smoke; then event NOTE "load $PL_ID into Neo4j (plant_lines), wiping the database first"; fi
  # shellcheck disable=SC2046
  try $L load-a --root "$ROOT" --prereg "$PREREG" --plant "$PL_ID" $(smoke_flag) > "$LOGS/load_$PL_ID.log" 2>&1
}

neo4j_load_b() {  # the plant PL_ID, B corpus: the relabelled copy and its positions, then the frozen B loader
  try $L prepare-b-load --root "$ROOT" --prereg "$PREREG" --plant "$PL_ID" > /dev/null
  if smoke; then event NOTE "SMOKE: no Neo4j, ${PL_ID}B prepared as files only"; return 0; fi
  event NOTE "load ${PL_ID}B into Neo4j (plant_lines), wiping the database first"
  try $P -m plantgraph.qa.v2tb load --corpus-id "${PL_ID}B" --corpora-root "$ROOT/cypcorp/plant_lines" \
    --fresh-database > "$LOGS/load_${PL_ID}B.log" 2>&1 \
    || stop_run infra "the B load of $PL_ID failed, its database-side G0-B (check 4) included: $LOGS/load_${PL_ID}B.log"
}

demo_database() {  # the last load: H1000g21p1 with plant_lines, the plant the demo expects (ADR-0064)
  if smoke; then event NOTE "SMOKE: the demo database is not restored (no Neo4j)"; return 0; fi
  event NOTE "restore the demo database: H1000g21p1 with plant_lines"
  dd_seed=$($P -c "import json;print(json.load(open('data/runs/exp0008/prereg/seeds.json'))['sealed']['1000'][0])") \
    || stop_run infra "cannot read the EXP-0008 seed of H1000g21p1"
  try $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets 1000 --seed "$dd_seed" \
    --headline-duplication-rate 0.25 --corpus-id H1000g21p1 --store-profile plant_lines --fresh-database \
    ${E10_NEO4J_HOME:+--neo4j-home "$E10_NEO4J_HOME"} --out "$ROOT/neo4jplant/demo_H1000g21p1" \
    > "$LOGS/demo_load.json" 2> "$LOGS/demo_load.err"
}

# ---- question pools and files ------------------------------------------------------------------------

pool_plant() {  # pool_plant <recipe>: one pool step for PL_ID (R pool and the X candidates, one generation)
  pp_recipe=$1
  if [ -f "$ROOT/qpool/$PL_ID/scope_x/report.json" ]; then return 0; fi
  event NOTE "pool $PL_ID ($pp_recipe recipe)"
  probed "$LOGS/mem_pool_$PL_ID.json" $L questions-pool --root "$ROOT" --plant "$PL_ID" --recipe "$pp_recipe" \
    > "$LOGS/pool_$PL_ID.log" 2>&1 \
    || stop_run infra "the question pool of $PL_ID failed (or passed the 10 GiB memory probe), see $LOGS/pool_$PL_ID.log"
  memory_note "pool $PL_ID" "$LOGS/mem_pool_$PL_ID.json"
}

pool_plant_dev() { pool_plant dev; }
pool_plant_sealed() { pool_plant sealed; }

question_files() {  # question_files <dev|validation|sealed>: the drop set, G0l, the samples and the files
  qf_role=$1
  if [ -f "$ROOT/questions/drop_$qf_role.json" ]; then return 0; fi
  $L questions-files --root "$ROOT" --prereg "$PREREG" --role "$qf_role" > "$LOGS/questions_$qf_role.log" \
    || { cat "$LOGS/questions_$qf_role.log"; gate_fail "G0l" "or the question files of the $qf_role plants, see $LOGS/questions_$qf_role.log"; }
  if smoke && forced g0l; then gate_fail "G0l" "forced: a quarter-rule failure on an X family (the smoke's plants are too small to show one)"; fi
  event NOTE "question files ($qf_role): $(tail -n 3 "$LOGS/questions_$qf_role.log" | tr '\n' ' ')"
}

# ---- composition bands (G0d) -------------------------------------------------------------------------

pooled_bands() {  # pooled_bands <gate|report> <name> <sheets> <seed|plant-id>...: ADR-0059 bands on the mean over the plants
  pb_mode=$1; pb_name=$2; pb_sheets=$3; shift 3
  pb_json=$ROOT/bands/composition_$pb_name.json; pb_txt=$LOGS/composition_$pb_name.txt
  mkdir -p "$ROOT/bands"; rm -f "$pb_json"
  pb_rc=0
  if [ "$pb_mode" = report ]; then
    # the sealed plants as BUILT: each plant is planned from its own recorded seed, drawn size and tagging (B4);
    # the frozen CLI re-sizes plants to the nominal scale and refuses every seed outside EXP-0008's seed plan
    $P -m plantgraph.qa.exp0009.bands_built --root "$ROOT" --plants "$@" --json "$pb_json" > "$pb_txt" 2>&1 || pb_rc=$?
  else   # the dev plants (seed 1): the frozen command line, plants named by their seeds
    $P -m plantgraph.benchmark.v2.composition --generator v2.2 --target-sheets "$pb_sheets" --seeds "$@" --pool --corpus \
      --json "$pb_json" > "$pb_txt" 2>&1 || pb_rc=$?
  fi
  pb_crash=no
  if [ $pb_rc -ne 0 ] && { [ ! -s "$pb_json" ] || grep -q Traceback "$pb_txt"; }; then pb_crash=yes; fi
  [ "$pb_crash" = no ] || stop_run infra "the composition report of $pb_name crashed (exit $pb_rc), see $pb_txt"
  if [ $pb_rc -eq 0 ]; then gate_pass "composition bands hold on the $pb_name plants"; return 0; fi
  if [ "$pb_mode" = report ]; then event NOTE "bands NOT met on the pooled $pb_name plants (reported, see $pb_txt)"; return 0; fi
  gate_fail "U4" "the pooled $pb_name plants break a composition band (ADR-0059); see $pb_txt"
}
