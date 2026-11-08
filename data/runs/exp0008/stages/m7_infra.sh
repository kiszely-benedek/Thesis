# M7: INFRA, the machine-cost measurement (ADR-0051 v2). Sourced by run_all.sh. ZERO paid calls.
#
# On the first plant of each scale (100 and 1,000 sheets): ingest three times into a fresh Neo4j database to
# measure load time and store size (needs E9_NEO4J_HOME, the Neo4j server's home), then time the live-cascade
# start-up three times and measure memory once (`infra-probe`).
# On all ten sealed plants: re-execute every stored Cypher query against the loaded plant to time the database
# alone (`infra-cypher-replay`, every recorded attempt, F6), and replay the agent tier from the M6a cache at
# concurrency 1. Then `infra-report`. A model is never called: there is no --allow-paid-calls anywhere here.
# In --smoke there is no database, so the ingest repeats, the database replay and the probes are skipped;
# the agent replays and the stage's bookkeeping still run.

INFRA_REPS=3
INFRA_POLICY=src/plantgraph/qa/cascade/policies_v2t/cascade_v4.json

infra_footprint() {  # three ingests of this plant (the last stays loaded), then the probes; plants 1 only
  if smoke; then event NOTE "SMOKE: no ingest repeats or probes for $PL_ID (no Neo4j)"; return 0; fi
  [ -n "${E9_NEO4J_HOME:-}" ] || stop_run infra "set E9_NEO4J_HOME to the Neo4j server's home for the store-size measurement"
  k=1
  mkdir -p "$SD/ingest/$PL_ID" "$SD/probe/$PL_ID"
  while [ "$k" -le "$INFRA_REPS" ]; do
    neo4j_load plant_lines
    rm -rf "$SD/ingest/$PL_ID/rep$k"; mv "$ROOT/neo4jplant/$PL_ID" "$SD/ingest/$PL_ID/rep$k"
    k=$((k + 1))
  done
  mkdir -p "$ROOT/neo4jplant/$PL_ID"; cp "$SD/ingest/$PL_ID/rep$INFRA_REPS/ingest.json" "$ROOT/neo4jplant/$PL_ID/ingest.json"
  k=1
  while [ "$k" -le "$INFRA_REPS" ]; do
    infra_probe --neo4j-home "$E9_NEO4J_HOME" --out "$SD/probe/$PL_ID/rep$k.json"
    k=$((k + 1))
  done
  infra_probe --memory --out "$SD/probe/$PL_ID/memory.json"
}

infra_probe() {
  try $P -m plantgraph.qa.cascade infra-probe --corpus "$PL_ID" --corpora-root "$ROOT/neo4jplant" \
    --policy "$INFRA_POLICY" --run "cypher-v2t=$ROOT/m6a/runs/S7-CYP-$PL_ID" \
    --run "agent-v2t=$ROOT/m6a/runs/S7-AG-$PL_ID" "$@" > /dev/null
}

infra_plant() {  # all ten plants: database-only Cypher timing, then the agent replay
  case $PL_ID in
    H100g21p1|H1000g21p1) once "footprint_$PL_ID" infra_footprint ;;
  esac
  if smoke; then
    event NOTE "SMOKE: no database-only replay for $PL_ID"
  else
    once "load_$PL_ID" neo4j_load plant_lines
    once "cypher_db_$PL_ID" try $P -m plantgraph.qa.cascade infra-cypher-replay \
      --source-run "$ROOT/m6a/runs/S7-CYP-$PL_ID" --corpus "$PL_ID" --corpora-root "$ROOT/neo4jplant" \
      --out-run "$SD/runs/INF2-CYPDB-$PL_ID"
  fi
  once "agent_$PL_ID" infra_agent_replay
}

infra_agent_replay() {  # the agent tier from the M6a cache, concurrency 1, written under this stage's own runs
  ia_dir=$SD/runs; ia_rc=0
  rm -rf "$ia_dir/INF2-AG-$PL_ID"
  # shellcheck disable=SC2046
  $P -m plantgraph.qa.harness --run-id "INF2-AG-$PL_ID" --experiment EXP-0008-INFRA --corpus "$PL_ID:test" \
    $(arm_options AG) --corpora-root "$ROOT/corpora" --questions-root "$ROOT/questions" --runs-root "$ia_dir" \
    --cache-path "$ROOT/m6a/cache.sqlite" --concurrency 1 --question-deadline-s "$DEADLINE_S" \
    > "$LOGS/INF2-AG-$PL_ID.log" 2>&1 || ia_rc=$?
  # exit 2 is a cache miss: recorded in the log and the summary, not a failure (as in the first measurement)
  [ $ia_rc -eq 0 ] || [ $ia_rc -eq 2 ] || return 1
  echo "$PL_ID agent replay exit $ia_rc" >> "$SD/summary.txt"
}

infra_report() {
  if smoke; then event NOTE "SMOKE: infra-report skipped (no probes)"; return 0; fi
  ir_corpora="--corpus H100g21p1 --corpus H1000g21p1"; ir_compute=
  for ir_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do ir_compute="$ir_compute --compute-corpus $ir_id"; done
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.cascade infra-report --ingest-root "$SD/ingest" --probe-root "$SD/probe" \
    --runs-root "$SD/runs" $ir_corpora $ir_compute --run "agent=INF2-AG-{c}" --db-replay "cypher_db_only=INF2-CYPDB-{c}" \
    --old-run "cypher=S7-CYP-{c}" --old-run "agent=S7-AG-{c}" --old-runs-root "$ROOT/m6a/runs" \
    --price-json "$SD/reference_price.json" --out "$SD/report.md" > "$SD/report.stdout.txt"
}

stage_M7() {
  STEP=M7; SD=$ROOT/infra; EXPERIMENT=EXP-0008-INFRA
  mkdir -p "$SD/runs"; : >> "$SD/summary.txt"
  require_frozen
  for_each_plant sealed infra_plant
  once report infra_report
  outputs "$SD/summary.txt"
}
