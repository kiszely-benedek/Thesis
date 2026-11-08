# M0: regenerate the dev plants and pass the free gates before any money is involved. Sourced by run_all.sh.
#
# Gates, in order: each dev plant round-trips (G1) and keeps its identity (S16); the line view equals the
# gold's own walk (LINE-01); the ADR-0059 composition bands hold (a failed band is U4: the launcher stops and
# the user decides between changing the generator and reporting the band as missed); the golden re-ingest
# tests of v1 and EX01 pass; the plant API can express every dev question (API-02); and a 1,000-sheet
# question pool fits in this machine's memory (five of them are scheduled).
# Free: no model call. Neo4j is touched only to drop the first measurement's temporary database `e7tune`.

# the tests that re-ingest the v1 plants and the EX01 import and compare them with their golden files
GOLDEN_TESTS="tests/test_ingest_pipeline.py tests/test_ingest_variants.py tests/test_open100_crops.py"

dev_plant() {
  build_plant
  line_view_gate "$PL_ID"
}

band_check() {  # the composition report of one dev plant; exit code 1 means a pass/fail band failed
  bc_rc=0
  $P -m plantgraph.benchmark.v2.composition --target-sheets "$PL_SHEETS" --seeds "$PL_SEED" --corpus \
    --json "$ROOT/dev/composition_$PL_ID.json" > "$LOGS/composition_$PL_ID.txt" 2>&1 || bc_rc=$?
  if forced band; then bc_rc=1; fi
  case $bc_rc in
    0) gate_pass "composition bands hold on $PL_ID" ;;
    1)
      # the bands describe plants of 100+ sheets, so a tiny smoke plant is not judged by them unless forced
      if smoke && ! forced band; then event NOTE "SMOKE: $PL_ID is too small for the bands, not judged"
      else gate_fail "U4" "$PL_ID breaks a composition band (ADR-0059); see $LOGS/composition_$PL_ID.txt"; fi ;;
    *) stop_run infra "the composition report of $PL_ID failed (exit $bc_rc), see $LOGS/composition_$PL_ID.txt" ;;
  esac
}

golden_gate() {
  if smoke; then event NOTE "SMOKE: golden re-ingest tests skipped (they are pytest, not part of the chain)"; return 0; fi
  # shellcheck disable=SC2086
  $P -m pytest -q $GOLDEN_TESTS > "$LOGS/golden.txt" 2>&1 || stop_run user "the golden re-ingest tests failed, see $LOGS/golden.txt"
  gate_pass "v1 and EX01 golden re-ingest"
}

api_gate() {  # API-02: every dev question has a canonical program in the plant API (D100g21)
  dev_questions D100g21
  if $P -m plantgraph.qa.harness.api_check_questions --corpus-id D100g21 \
      --ingest-json "$ROOT/corpora/D100g21/ingest.json" --questions "$ROOT/questions/D100g21/questions.jsonl" \
      --min-share 1.0 > "$LOGS/api02.txt" 2>&1; then gate_pass "API-02 on D100g21"
  elif smoke; then event NOTE "SMOKE: API-02 not judged on a tiny plant"
  else gate_fail "API-02" "a family is below 1.0, see $LOGS/api02.txt"; fi
}

pool_probe() {  # the 1,000-sheet dev question pool, with its peak memory
  pp_bin=97; if smoke; then pp_bin=2; fi
  mkdir -p "$ROOT/qpool"
  $L memory-probe --out "$ROOT/dev/pool_probe.json" -- $P -m plantgraph.qa.questions --corpus-id D1000g21 \
    --ingest-json "$ROOT/corpora/D1000g21/ingest.json" --seed 1 --n-per-bin "$pp_bin" \
    --n-unanswerable "$pp_bin" --out "$ROOT/qpool/D1000g21" > "$LOGS/pool_probe.txt" 2>&1 \
    || stop_run user "the 1,000-sheet question pool does not fit this machine, see $LOGS/pool_probe.txt"
  gate_pass "pool memory probe: $(cat "$LOGS/pool_probe.txt" | tail -n 1)"
}

stage_M0() {
  mkdir -p "$ROOT/dev"
  once drop_tmp drop_tmp_database
  once plants for_each_plant dev dev_plant
  once bands for_each_plant dev band_check
  once golden golden_gate
  once api02 api_gate
  once pool_probe pool_probe
  outputs "$ROOT/corpora/D100g21/ingest.json" "$ROOT/corpora/D1000g21/ingest.json" \
    "$ROOT/corpora/X100g21s211/ingest.json" "$ROOT/dev/composition_D100g21.json" "$ROOT/dev/pool_probe.json"
}
