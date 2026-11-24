# P1a: B tuning on D100g22. PAID. Sourced by run_all.sh.
#
# Setup:    D100g22's dev questions (dev recipe), G0l on its X dev families.
# Round 1:  the A2 baseline (load A; CYP-A and AG on the A2 dev file), then B round 1 (load B; CYP-B and AG-B
#           on the B dev file). Run ids U9-A-CYP-D100g22, U9-A-AG-D100g22, U9-<k>-CYP-D100g22B, U9-<k>-AG-D100g22B.
# Each round writes tune/round<k>/b_code.sha256 (every qa/v2tb file and the policy_b dump), the B cascade report
# (per-family dev accuracy over R-dev and X-dev) and B - A2 on R-dev. NO replays in tuning (as EXP-0008 M1).
# After a round the launcher STOPS [needs the main session]: change B files and resume with --from P1a for the
# next round, or end tuning with `launcher finish-tuning`. From round 2 a round that adds less than 1 point ends
# tuning automatically; round 3 always ends it; a fourth is refused; unchanged B files are refused before any call.
# The tuning change text of a round comes from E10_TUNE_CHANGE (default "round <k>").

TUNE=$ROOT/tune
D=D100g22

tune_setup() {
  PL_ID=$D; PL_SCALE=100
  pool_plant_dev
  question_files dev
}

tune_a2_baseline() {  # round 1 only
  PL_ID=$D; PL_SCALE=100
  neo4j_load_a
  paid_run CYP-A "U9-A-CYP-$D" "$D" dev
  paid_run AG "U9-A-AG-$D" "$D" dev
}

tune_reports() {  # tune_reports <k>: the B cascade report of round k, and the A2 one beside it (round 1)
  tr_k=$1; tr_dir=$TUNE/round$tr_k; mkdir -p "$tr_dir"
  if smoke; then   # canned accuracies: the smoke's answers are meaningless
    try $L smoke-cells --plant "$D" --out-dir "$TUNE/smoke_cells"
    cp "$TUNE/smoke_cells/${D}_b.json" "$tr_dir/report_b.json"
    [ -f "$TUNE/a2_report.json" ] || cp "$TUNE/smoke_cells/${D}_a2.json" "$TUNE/a2_report.json"
    return 0
  fi
  if [ ! -f "$TUNE/a2_report.json" ]; then
    try $L cascade-report --corpus-id "$D" --arm A2 --cyp-run "$SD/runs/U9-A-CYP-$D" --ag-run "$SD/runs/U9-A-AG-$D" \
      --questions-root "$QROOT" --corpora-root "$ROOT/corpora" --out "$TUNE/a2_report.json"
  fi
  try $L cascade-report --corpus-id "${D}B" --arm B --cyp-run "$SD/runs/U9-$tr_k-CYP-${D}B" \
    --ag-run "$SD/runs/U9-$tr_k-AG-${D}B" --questions-root "$QROOT" --corpora-root "$ROOT/corpora" \
    --out "$tr_dir/report_b.json"
}

tune_round() {  # tune_round <k>
  tt_k=$1
  PL_ID=$D; PL_SCALE=100
  $L tuning-check --root "$ROOT" --round "$tt_k" || stop_run main "round $tt_k is refused (see the line above): finish tuning or change the B files"
  estimate_note P1a
  if [ "$tt_k" = 1 ]; then tune_a2_baseline; fi
  neo4j_load_b
  paid_run CYP-B "U9-$tt_k-CYP-${D}B" "${D}B" dev
  paid_run AG-B "U9-$tt_k-AG-${D}B" "${D}B" dev
  tune_reports "$tt_k"
  try $L tuning-round --root "$ROOT" --round "$tt_k" --change "${E10_TUNE_CHANGE:-round $tt_k}" \
    --b-report "$TUNE/round$tt_k/report_b.json" --a2-report "$TUNE/a2_report.json" > "$LOGS/tuning_round$tt_k.txt"
  cat "$LOGS/tuning_round$tt_k.txt"
}

stage_P1a() {
  SD=$TUNE; STEP=P1a; CACHE=$SD/cache.sqlite; EXPERIMENT=EXP-0009-TUNE; QROOT=$ROOT/questions
  mkdir -p "$SD/runs"
  require_prereg_part_a_committed_or_smoke
  once setup tune_setup
  if [ ! -f "$TUNE/FINISHED" ]; then
    tp_done=$(ls -d "$TUNE"/round*/round.json 2> /dev/null | wc -l | tr -d ' ')
    tp_next=$((tp_done + 1))
    if [ "$tp_next" -gt 3 ]; then $L finish-tuning --root "$ROOT"; else
      tune_round "$tp_next"
      if grep -q "next_round=no" "$LOGS/tuning_round$tp_next.txt"; then
        $L finish-tuning --root "$ROOT"
      elif ! forced finish-tuning-now && ! smoke; then
        stop_run main "round $tp_next is done, report in $TUNE/round$tp_next: change the B files and resume with --from P1a, or run: $L finish-tuning --root $ROOT"
      else
        $L finish-tuning --root "$ROOT"   # the smoke: one round, then finish-tuning
      fi
    fi
  fi
  outputs "$TUNE/chosen_round.txt"
}

require_prereg_part_a_committed_or_smoke() {
  if smoke; then return 0; fi
  $P -m plantgraph.qa.exp0009.readiness --prereg-only || stop_run user "PREREG_A.md is unfilled or not committed"
}
