# M10: the scorer audit (M10a), then the reports and the demo's database (M10b). Sourced by run_all.sh.
#
# M10a  Select the rows to judge in the registered budget order (every wrong row of the ten sealed plants, a
#       random right sample, ContextRAG's wrong rows, more right samples), sized from the pilot's measured cost;
#       cut the plant excerpt each judge sees; run the judge under the audit ledger (cap $10, or what the $40
#       program cap leaves); write the agreement report and the disagreement sheet. PAID.
#       The launcher stops here. Classifying disagreements and fixing a scorer or gold defect is the main
#       session's work under the pre-registered audit rule (design 5.3); it is not done unattended.
# M10b  The free reports of the first measurement's tools on the new records, then the last Neo4j load:
#       H1000g21p1 with the plant_lines profile, which the demo expects (ADR-0064, amended by ADR-0065).
#       The reports here are the pre-audit scores; the post-audit re-score follows the audit rule.

AUDIT=$ROOT/audit/main

audit_runs() {  # --run flags: both V2T-A2 tiers on all ten sealed plants
  ar_flags=
  for ar_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    ar_flags="$ar_flags --run $ROOT/m6a/runs/S7-CYP-$ar_id --run $ROOT/m6a/runs/S7-AG-$ar_id"
  done
  echo "$ar_flags"
}

audit_select() {
  as_cap=$($L audit-cap --root "$ROOT") || stop_run topup "no money left under the \$40 program cap for the audit"
  # shellcheck disable=SC2046
  try $P -m plantgraph.qa.audit select $(audit_runs) --questions-root "$ROOT/questions" \
    --contextrag-run "$ROOT/ladder/runs/E8-CTXH-H1g21" --contextrag-run "$ROOT/ladder/runs/E8-CTXH-H3g21" \
    --contextrag-run "$ROOT/ladder/runs/E8-CTXH-H10g21" --ledger "$ROOT/audit/ledger.jsonl" \
    --cap-usd "$as_cap" --out "$AUDIT/plan.json"
}

audit_subgraphs() {  # one excerpt file per corpus that has selected rows (the gold side cuts the plant)
  mkdir -p "$AUDIT/subgraphs"
  for asg_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    try $L plan-ids --plan "$AUDIT/plan.json" --corpus "$asg_id" --out "$AUDIT/ids_$asg_id.txt"
    if [ -s "$AUDIT/ids_$asg_id.txt" ]; then
      try $P scripts/audit_export_subgraphs.py --corpus-id "$asg_id" --ingest-json "$ROOT/corpora/$asg_id/ingest.json" \
        --questions "$ROOT/questions/$asg_id/questions.jsonl" --question-ids "$AUDIT/ids_$asg_id.txt" \
        --out "$AUDIT/subgraphs/$asg_id.json"
    fi
  done
}

audit_judge() {
  aj_cap=$($L audit-cap --root "$ROOT") || stop_run topup "no money left under the \$40 program cap for the audit"
  # shellcheck disable=SC2046
  $L balance --needed "$aj_cap" $(balance_args) || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$aj_cap"
  aj_sub=; for aj_f in "$AUDIT"/subgraphs/*.json; do aj_sub="$aj_sub --subgraphs $aj_f"; done
  event START "audit judge, cap \$$aj_cap"
  aj_rc=0
  # shellcheck disable=SC2046,SC2086
  $P -m plantgraph.qa.audit judge $(audit_runs) --questions-root "$ROOT/questions" --plan "$AUDIT/plan.json" \
    $aj_sub --out-dir "$AUDIT" --ledger "$ROOT/audit/ledger.jsonl" --cap-usd "$aj_cap" --stage audit \
    --allow-paid-calls >> "$LOGS/audit_judge.log" 2>&1 || aj_rc=$?
  [ $aj_rc -eq 0 ] || stop_run infra "the audit judge failed (exit $aj_rc), see $LOGS/audit_judge.log"
  if grep -q "stopped by cap: True" "$LOGS/audit_judge.log"; then
    event CAP "the audit reached its cap \$$aj_cap; the report states the share of wrong rows covered"
  fi
}

stage_M10a() {
  mkdir -p "$AUDIT"
  require_frozen
  plan_to_file sealed
  if smoke; then
    event NOTE "SMOKE: selection and the judge need a real model; the report runs on smoke evidence"
    try $L smoke-evidence g2 --out-dir "$AUDIT"
  else
    once select audit_select
    once subgraphs audit_subgraphs
    once judge audit_judge
  fi
  try $P -m plantgraph.qa.audit report --verdicts "$AUDIT/verdicts.jsonl" --out "$AUDIT/report.md" \
    --sheet "$AUDIT/disagreements.csv"
  outputs "$AUDIT/report.md" "$AUDIT/disagreements.csv"
}

assemble_roots() {  # the first measurement's report tools read <root>/{runs,corpora,questions}: copy them together
  for ar_root in r5_1000 duplication; do mkdir -p "$ROOT/reports/$ar_root/runs" "$ROOT/reports/$ar_root/corpora" "$ROOT/reports/$ar_root/questions"; done
  for ar_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    case $ar_id in
      H1000g*) ar_root=r5_1000 ;;
      H100g21p1) ar_root=duplication ;;
      *) continue ;;
    esac
    cp -r "$ROOT/m6a/runs/S7-CYP-$ar_id" "$ROOT/m6a/runs/S7-AG-$ar_id" "$ROOT/reports/$ar_root/runs/"
    cp -r "$ROOT/corpora/$ar_id" "$ROOT/reports/$ar_root/corpora/"
    cp -r "$ROOT/questions/$ar_id" "$ROOT/reports/$ar_root/questions/"
  done
  for ar_id in H100g21p1d0 H100g21p1d50; do
    cp -r "$ROOT/m6c/runs/S7-CYP-$ar_id" "$ROOT/m6c/runs/S7-AG-$ar_id" "$ROOT/reports/duplication/runs/"
    cp -r "$ROOT/corpora/$ar_id" "$ROOT/reports/duplication/corpora/"
    cp -r "$ROOT/questions/$ar_id" "$ROOT/reports/duplication/questions/"
  done
}

reports() {
  if smoke; then
    event NOTE "SMOKE: the report tools (cascade report, exp0001 report, e2e_report) are not run on canned replies"
    return 0
  fi
  POL=src/plantgraph/qa/cascade/policies_v2t
  mkdir -p "$ROOT/reports"
  sealed_args=; scale100=; scale1000=
  for rp_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    sealed_args="$sealed_args --corpus $rp_id --run $rp_id:cypher-v2t=$ROOT/m6a/runs/S7-CYP-$rp_id --run $rp_id:agent-v2t=$ROOT/m6a/runs/S7-AG-$rp_id"
    case $rp_id in H100g*) scale100="$scale100,$rp_id" ;; *) scale1000="$scale1000,$rp_id" ;; esac
  done
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.cascade report --sealed-claims --claims v2t --setting A \
    --policy $POL/cascade_v4_iso.json --policy $POL/cascade_v4.json --policy $POL/references/always_g_v2t.json \
    --policy $POL/references/always_c_v2t.json --questions-root "$ROOT/questions" --corpora-root "$ROOT/corpora" \
    --scale "S100=${scale100#,}" --scale "S1000=${scale1000#,}" --out "$ROOT/reports/sealed" $sealed_args \
    > "$ROOT/reports/sealed.stdout.txt"
  # the ladder report reads <root>/runs, corpora, questions (assembled in M5)
  try $P -m plantgraph.qa.exp0001 report --edition v21 --system v2t --root "$ROOT/ladder" --out "$ROOT/reports/ladder" \
    --ctx-high-policy "$INPUTS/always_ctx_high.json" --ctx-low-policy "$INPUTS/always_ctx_low.json" \
    > "$ROOT/reports/ladder.stdout.txt"
  assemble_roots
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.exp0001 duplication-report --system v2t --root "$ROOT/reports/duplication"     --points "H100g21p1d0=0,H100g21p1=25,H100g21p1d50=50" --out "$ROOT/reports/duplication_out"     > "$ROOT/reports/duplication.stdout.txt"
  e2e_plants=; for rp_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt" | grep 'H1000'); do e2e_plants="$e2e_plants --plant $rp_id:${rp_id}V"; done
  # shellcheck disable=SC2086
  try $P -m plantgraph.exp0004.e2e_report --e2e-root "$ROOT/m8b/e2e" --r5-root "$ROOT/reports/r5_1000" \
    --out "$ROOT/reports/e2e" $e2e_plants --headline-n 220 > "$ROOT/reports/e2e.stdout.txt"
}

demo_database() {  # the last load: plant 1 at 1,000 sheets, plant_lines, alone in the user's database
  plan_to_file demo
  read -r PL_ID PL_SHEETS PL_SEED PL_RATE PL_VARIANT < "$PLAN_FILE"
  neo4j_load plant_lines
  event NOTE "the database ends on $PL_ID (plant_lines)"
}

stage_M10b() {
  mkdir -p "$ROOT/reports"
  require_frozen
  plan_to_file sealed
  once reports reports
  once demo demo_database
  echo "reports: $ROOT/reports; database: H1000g21p1" > "$ROOT/reports/DONE.txt"
  outputs "$ROOT/reports/DONE.txt"
}
