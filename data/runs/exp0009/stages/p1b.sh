# P1b: validation on two fresh plants, then G1, G1-B and G1-B2. PAID. Sourced by run_all.sh.
#
# Precondition: a clean tree under the frozen paths, and the B files equal to the chosen tuning round's hashes.
# Plants VAL100g22, then VAL1000g22. Each gets its build and gates, dev-recipe questions, A2 (CYP-A then AG)
# and B (CYP-B then AG-B). The B runs are replayed cache-only (the E10 replays "per B tier of the B validation
# runs"). The VAL1000g22 pool step runs under the memory probe: the first 1,000-sheet v2.2 pool.
# Gates:  G1 (A2) fails -> the launcher stops [needs the user], as EXP-0008's U2.
#         G1-B or G1-B2 fails -> B is NOT run sealed (ADR-0067): recorded in state/b_sealed, the launcher goes on.
# Run ids: V9-CYP-<id>, V9-AG-<id>, V9-CYP-<id>B, V9-AG-<id>B.

# What a sealed run depends on; `git status` is checked over exactly these paths (the demo is not frozen).
FROZEN_PATHS="src :!src/plantgraph/demo scripts/audit_export_subgraphs.py $SCRIPTS/run_all.sh $SCRIPTS/lib.sh"
FROZEN_PATHS="$FROZEN_PATHS $SCRIPTS/lib_plants.sh $SCRIPTS/lib_runs.sh $SCRIPTS/stages $SCRIPTS/inputs"

p1b_precondition() {
  if smoke; then
    if forced dirty-tree; then stop_run user "the tree is dirty under the frozen paths (forced)"; fi
    if forced b-files; then stop_run user "the B files differ from the chosen round's hashes (forced)"; fi
    return 0
  fi
  # shellcheck disable=SC2086
  pb_dirty=$(git status --porcelain -- $FROZEN_PATHS) || stop_run infra "git status failed"
  [ -z "$pb_dirty" ] || stop_run user "the tree is dirty under the frozen paths: $(echo "$pb_dirty" | head -n 1)"
  pb_round=$(cat "$ROOT/tune/chosen_round.txt") || stop_run infra "tuning is not finished (no tune/chosen_round.txt)"
  $L b-files-check --against "$ROOT/tune/round$pb_round/b_code.sha256" \
    || stop_run user "the B files differ from the chosen round $pb_round's hashes: restore them first"
}

val_setup() {  # build and pool one validation plant (the 1,000-sheet pool under the memory probe)
  build_plant
  if [ "$PL_ID" = VAL1000g22 ] && [ ! -f "$ROOT/qpool/$PL_ID/scope_x/report.json" ]; then
    try $L memory-probe --out "$SD/pool_probe.json" --limit-gib "$MEM_LIMIT_GIB" -- \
      $L questions-pool --root "$ROOT" --plant "$PL_ID" --recipe dev
    memory_note "pool $PL_ID (VAL1000 probe)" "$SD/pool_probe.json"
  else
    pool_plant_dev
  fi
}

val_runs() {  # the two arms on one plant; the database holds one corpus at a time, loaded only if a Cypher run of it is still to do (F2)
  if needs_database "V9-CYP-$PL_ID" no; then neo4j_load_a; fi
  paid_run CYP-A "V9-CYP-$PL_ID" "$PL_ID" dev
  paid_run AG "V9-AG-$PL_ID" "$PL_ID" dev
  if needs_database "V9-CYP-${PL_ID}B" yes; then neo4j_load_b; fi
  paid_run CYP-B "V9-CYP-${PL_ID}B" "${PL_ID}B" dev
  replay_run CYP-B "V9-CYP-${PL_ID}B" "${PL_ID}B" dev
  paid_run AG-B "V9-AG-${PL_ID}B" "${PL_ID}B" dev
  replay_run AG-B "V9-AG-${PL_ID}B" "${PL_ID}B" dev
}

val_reports() {  # the cascade reports of both arms on one plant
  mkdir -p "$SD/report"
  if smoke; then
    vr_fail=; if forced g1 || forced g1b || forced g1b2; then vr_fail="--fail $FORCE"; fi
    # shellcheck disable=SC2086
    try $L smoke-cells --plant "$PL_ID" --out-dir "$SD/report" $vr_fail
    return 0
  fi
  try $L cascade-report --corpus-id "$PL_ID" --arm A2 --cyp-run "$SD/runs/V9-CYP-$PL_ID" --ag-run "$SD/runs/V9-AG-$PL_ID" \
    --questions-root "$QROOT" --corpora-root "$ROOT/corpora" --out "$SD/report/${PL_ID}_a2.json"
  try $L cascade-report --corpus-id "${PL_ID}B" --arm B --cyp-run "$SD/runs/V9-CYP-${PL_ID}B" --ag-run "$SD/runs/V9-AG-${PL_ID}B" \
    --questions-root "$QROOT" --corpora-root "$ROOT/corpora" --out "$SD/report/${PL_ID}_b.json"
}

validation_gates() {
  vg_args=
  for vg_id in VAL100g22 VAL1000g22; do
    vg_args="$vg_args --a2 $vg_id=$SD/report/${vg_id}_a2.json --b $vg_id=$SD/report/${vg_id}_b.json"
  done
  vg_rc=0
  # shellcheck disable=SC2086
  vg_text=$($L validation-gates $vg_args --out "$STATE/p1b.json") || vg_rc=$?
  echo "$vg_text"
  if [ $vg_rc -ne 0 ]; then gate_fail "G1" "A2 has a weak family on every validation plant (U2): $(echo "$vg_text" | head -n 1)"; fi
  gate_pass "G1 (A2)"
  case $vg_text in
    *b_sealed=yes*) echo yes > "$STATE/b_sealed"; gate_pass "G1-B and G1-B2: B runs sealed" ;;
    *) echo no > "$STATE/b_sealed"
       event NOTE "BRANCH: G1-B or G1-B2 failed, so B is NOT run sealed (ADR-0067); A2 alone runs sealed" ;;
  esac
}

stage_P1b() {
  SD=$ROOT/val; STEP=P1b; CACHE=$SD/cache.sqlite; EXPERIMENT=EXP-0009-VAL; QROOT=$ROOT/questions
  mkdir -p "$SD/runs" "$SD/replays"
  p1b_precondition
  estimate_note P1b
  once setup for_each_plant validation val_setup
  once files question_files validation
  once runs for_each_plant validation val_runs
  once reports for_each_plant validation val_reports
  validation_gates
  try $L measure-costs --val-dir "$SD" --out "$STATE/measured_costs.json"
  event NOTE "measured dollars per question: $(cat "$STATE/measured_costs.json" | tr -d ' ' | tr '\n' ' ')"
  project_p1c_spend
  outputs "$STATE/p1b.json" "$STATE/b_sealed" "$STATE/measured_costs.json" "$STATE/p1c_projection.json"
}

project_p1c_spend() {  # F1: P1c's spend from P1b's measured costs; if it cannot fit, stop BEFORE F10 freezes the ceiling
  pj_extra=; if smoke && forced p1c-projection; then pj_extra="--ceiling-usd 0.0001"; fi
  # shellcheck disable=SC2086
  pj_text=$($L project-p1c --root "$ROOT" --measured "$STATE/measured_costs.json" \
    --out "$STATE/p1c_projection.json" $pj_extra 2>&1) \
    || stop_run user "P1c would not fit its money (projection from P1b's measured costs, state/p1c_projection.json): $pj_text"
  event NOTE "$pj_text"
}
