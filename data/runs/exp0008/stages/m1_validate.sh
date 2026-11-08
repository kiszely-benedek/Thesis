# M1: re-validation of V2T-A2 against the frozen F1 on two fresh plants, then gate G1. Sourced by run_all.sh.
#
# Per validation plant (100 and 1,000 sheets): V2T-A2 (Cypher tier at setting A, agent tier) and F1 (its two
# tiers) answer the dev questions once, then `tune-report` (V2T) and `dev-report` (F1) count the correct ones.
# G1 passes if V2T's cascade_v4_iso scores at least F1's cascade_v3 on both plants and no dev family is below
# 50 % on both plants. There is no setting-B run: tuning is off by default, so its choice is not needed.
# If G1 fails the launcher stops (U2): a tuning round is design work, not something to run unattended.

val_setup() {  # build and check one validation plant, draw its dev questions
  build_plant
  line_view_gate "$PL_ID"
  dev_questions "$PL_ID"
}

val_runs() {  # the four runs on one plant; the plant is loaded twice (V2T reads plant_lines, F1 the plain plant)
  neo4j_load plant_lines
  check_loaded_matches "$PL_ID"
  paid_run CYP-A "V8-CYP-A-$PL_ID" "$PL_ID" dev
  paid_run AG "V8-AG-$PL_ID" "$PL_ID" dev
  neo4j_load plant
  paid_run F1-CYP "V8F1-CYP-$PL_ID" "$PL_ID" dev
  paid_run F1-AG "V8F1-AG-$PL_ID" "$PL_ID" dev
}

val_reports() {  # the two reports G1 reads, for one plant (real mode); each CLI is the first measurement's
  try $P -m plantgraph.qa.cascade tune-report --corpus "$PL_ID" --setting A --questions-root "$QROOT" \
    --corpora-root "$AG_CORPORA" --run "cypher-v2t=$SD/runs/V8-CYP-A-$PL_ID" \
    --run "agent-v2t=$SD/runs/V8-AG-$PL_ID" --out "$SD/report/V2T/$PL_ID" > "$LOGS/tune_report_$PL_ID.txt"
  try $P -m plantgraph.qa.exp0007 dev-report --corpus-id "$PL_ID" --cyp-run "$SD/runs/V8F1-CYP-$PL_ID" \
    --ag-run "$SD/runs/V8F1-AG-$PL_ID" --questions-root "$QROOT" --out "$SD/report/F1/$PL_ID"
}

g1_gate() {
  if smoke; then  # canned replies make every accuracy zero, so the smoke feeds the real gate evidence of its own
    g1_fail=; if forced g1; then g1_fail=--fail; fi
    # shellcheck disable=SC2086
    try $L smoke-evidence g1 --out-dir "$SD/smoke_evidence" $g1_fail
    g1_args="--plant VAL100g21|$SD/smoke_evidence/VAL100g21/tune_report.json|$SD/smoke_evidence/VAL100g21/dev_report.json"
    g1_args="$g1_args --plant VAL1000g21|$SD/smoke_evidence/VAL1000g21/tune_report.json|$SD/smoke_evidence/VAL1000g21/dev_report.json"
  else
    g1_args=
    for g1_id in VAL100g21 VAL1000g21; do
      g1_args="$g1_args --plant $g1_id|$SD/report/V2T/$g1_id/tune_report.json|$SD/report/F1/$g1_id/dev_report.json"
    done
  fi
  # shellcheck disable=SC2086
  if g1_text=$($L g1 $g1_args --out "$STATE/g1.json"); then gate_pass "G1 $g1_text"
  else gate_fail "G1" "$g1_text (U2: one tuning round on X100g21s211 under ADR-0061, then a second fresh pair)"; fi
}

stage_M1() {
  STEP=M1; SD=$ROOT/val; CACHE=$SD/cache.sqlite; EXPERIMENT=EXP-0008-VAL
  AG_CORPORA=$ROOT/corpora; QROOT=$ROOT/questions
  mkdir -p "$SD/runs" "$SD/replays" "$SD/report"
  once setup for_each_plant validation val_setup
  once runs for_each_plant validation val_runs
  if ! smoke; then once reports for_each_plant validation val_reports; fi
  g1_gate
  outputs "$STATE/g1.json" "$SD/runs/V8-AG-VAL100g21/answers.jsonl" "$SD/runs/V8-AG-VAL1000g21/answers.jsonl"
}
