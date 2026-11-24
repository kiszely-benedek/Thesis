# P0: the free gates, $0. Sourced by run_all.sh.
#
# Builds D100g22 (with its B files) and D1000g22 and passes every free gate before any money is involved:
# G0a (tests, lint, types, goldens), G0b (rule suite), G0c, G0g, the line view, G0k and G0-B (at each build),
# G0d (composition bands, dev plants), G0f (the system-side diff and two cache-only replays from EXP-0008),
# G0j (the B scorer's self-tests), R14f on D100g22B, the prior refit, the ledger and records tests.
# It REFUSES TO START if PREREG_A.md holds a <<FILL marker or is not committed (readiness).

GOLDEN_TESTS="tests/test_ingest_pipeline.py tests/test_ingest_variants.py tests/test_open100_crops.py"

g0a_gate() {
  if smoke; then event NOTE "SMOKE: G0a (the whole test suite) is not part of the chain"; return 0; fi
  try $P -m pytest -q > "$LOGS/g0a_pytest.txt" 2>&1
  try $P -m ruff check src tests > "$LOGS/g0a_ruff.txt" 2>&1
  try $P -m mypy --strict src > "$LOGS/g0a_mypy.txt" 2>&1
  # shellcheck disable=SC2086
  try $P -m pytest -q $GOLDEN_TESTS > "$LOGS/golden.txt" 2>&1
  gate_pass "G0a: pytest, ruff, mypy --strict, v1 and v2.1 goldens"
}

g0b_gate() {  # the rule-suite tests (every rule and alternative non-vacuous over dev seeds 1-5)
  if smoke; then event NOTE "SMOKE: G0b is pytest, not part of the chain"; return 0; fi
  try $P -m pytest -q tests/v2 > "$LOGS/g0b.txt" 2>&1
  gate_pass "G0b: the rule suite"
}

g0j_gate() {  # the B scorer's self-tests
  if smoke; then event NOTE "SMOKE: G0j is pytest, not part of the chain"; return 0; fi
  try $P -m pytest -q tests/v2tb > "$LOGS/g0j.txt" 2>&1
  gate_pass "G0j: tests/v2tb"
}

g0f_diff() {  # no system-side path changed since the E9 commit; new untracked files count too
  g0f_list=$($L g0f) || stop_run user "G0f failed: system-side files changed since E9: $g0f_list"
  gate_pass "G0f diff: $g0f_list"
}

g0f_replays() {  # S7-CYP-H100g21p1 (with H100g21p1 loaded) and S7-AG-H100g21p1 replay byte-identical, EVERY row (B6)
  if smoke; then event NOTE "SMOKE: the G0f replays need EXP-0008's plants and Neo4j"; return 0; fi
  e8=data/runs/exp0008; g0f=$ROOT/g0f; mkdir -p "$g0f/replays"
  g0f_seed=$($P -c "import json;print(json.load(open('$e8/prereg/seeds.json'))['sealed']['100'][0])") \
    || stop_run infra "cannot read the EXP-0008 seed of H100g21p1"
  try $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets 100 --seed "$g0f_seed" \
    --headline-duplication-rate 0.25 --corpus-id H100g21p1 --store-profile plant_lines --fresh-database \
    ${E10_NEO4J_HOME:+--neo4j-home "$E10_NEO4J_HOME"} --out "$g0f/load" > "$LOGS/g0f_load.json" 2> "$LOGS/g0f_load.err"
  for g0f_arm in CYP:cypher_rag_lines:params_cypher_v2t_a:pin_cypher_luna_low:cypcorp/plant_lines:yes \
                 AG:graph_agent_lines:params_agent_v2t:pin_agent_luna_final_high:corpora:no; do
    IFS=: read -r g_tier g_strategy g_params g_pin g_corpora g_prefix <<EOF
$g0f_arm
EOF
    g_id=S7-$g_tier-H100g21p1; g_rc=0
    rm -rf "$g0f/replays/G0F-$g_id"
    $P -m plantgraph.qa.harness --run-id "G0F-$g_id" --experiment EXP-0009-G0F --corpus H100g21p1:test \
      --strategy "$g_strategy" --strategy-params-json "$INPUTS/$g_params.json" --pin-json "$INPUTS/$g_pin.json" \
      --corpora-root "$e8/$g_corpora" --questions-root "$e8/questions" --runs-root "$g0f/replays" \
      --cache-path "$e8/m6a/cache.sqlite" --concurrency 1 --question-deadline-s 120 \
      > "$LOGS/g0f_$g_id.log" 2>&1 || g_rc=$?
    [ $g_rc -eq 0 ] || [ $g_rc -eq 2 ] || stop_run infra "the G0f replay of $g_id failed (exit $g_rc)"
    g_verdict=$($L replay-compare --replay-dir "$g0f/replays/G0F-$g_id" --run-dir "$e8/m6a/runs/$g_id" --allow-prefix "$g_prefix" --require-complete yes) \
      || stop_run user "G0f failed: the replay of $g_id is not identical to EXP-0008's run"
    gate_pass "G0f replay $g_id: $g_verdict"
  done
}

p0_plant() {  # build the plant PL_ID with its B files and gates
  build_plant
}

p0_bands() {  # G0d on the dev plants: ADR-0059 bands, pooled per scale (a failed band is U4)
  if smoke; then event NOTE "SMOKE: tiny plants are not judged by the composition bands"; return 0; fi
  pooled_bands gate dev100 100 1
  pooled_bands gate dev1000 1000 1
}

p0_prior() {  # the prior refit must equal plan.json's sha256 (the draw already wrote the file)
  if smoke; then event NOTE "SMOKE: the prior refit (ten plants) is skipped"; return 0; fi
  try $P -m plantgraph.qa.exp0009.position_baselines --out-dir "$ROOT/dev/baselines" > /dev/null
  if [ "$(sha256sum "$ROOT/dev/baselines/position_prior.json" | cut -d' ' -f1)" != "$(sha256sum "$PREREG/position_prior.json" | cut -d' ' -f1)" ]; then
    gate_fail "prior" "the refit differs from prereg/position_prior.json"
  fi
  gate_pass "prior refit equals the pre-registered position_prior.json"
}

p0_ledger_records_tests() {  # the ledger test and the records test on fake runs of both arms
  if smoke; then event NOTE "SMOKE: the ledger and records tests are pytest"; return 0; fi
  try $P -m pytest -q tests/qa/exp0009/test_caps_ledger.py tests/qa/exp0009/test_records.py > "$LOGS/p0_tests.txt" 2>&1
  gate_pass "ledger glob test and records tests"
}

stage_P0() {
  mkdir -p "$ROOT/dev"
  if ! smoke; then
    $P -m plantgraph.qa.exp0009.readiness --prereg-only || stop_run user "PREREG_A.md is unfilled or not committed (readiness)"
  fi
  once g0a g0a_gate
  once g0b g0b_gate
  once g0f_diff g0f_diff
  once g0f_replays g0f_replays
  once plants_dev for_each_plant dev p0_plant
  once plants_probe for_each_plant probe p0_plant
  PL_ID=D100g22; once r14f try $L r14f --root "$ROOT" --prereg "$PREREG" --plant D100g22
  once bands p0_bands
  once g0j g0j_gate
  once prior p0_prior
  once tests p0_ledger_records_tests
  outputs "$ROOT/corpora/D100g22/ingest.json" "$ROOT/corpora/D100g22B/corpus_b.json" "$ROOT/corpora/D1000g22/ingest.json"
}
