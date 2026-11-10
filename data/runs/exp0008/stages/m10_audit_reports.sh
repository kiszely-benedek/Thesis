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
#       A report that fails is noted and the next one still runs; the demo load always runs; only then does
#       the stage stop, naming the failed reports. To load the demo plant alone: sh data/runs/exp0008/demo_load.sh

AUDIT=$ROOT/audit/main

audit_runs() {  # --run flags: both V2T-A2 tiers on all ten sealed plants
  ar_flags=
  for ar_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    ar_flags="$ar_flags --run $ROOT/m6a/runs/S7-CYP-$ar_id --run $ROOT/m6a/runs/S7-AG-$ar_id"
  done
  echo "$ar_flags"
}

audit_ctx_runs() {  # --run flags for ContextRAG's ladder runs, which the judge needs to read their rows
  acr_flags=
  for acr_id in $CTX_LADDER; do acr_flags="$acr_flags --run $ROOT/ladder/runs/E8-CTXH-$acr_id"; done
  echo "$acr_flags"
}

audit_select() {
  as_cap=$($L audit-cap --root "$ROOT") || stop_run topup "no money left under the \$40 program cap for the audit"
  # shellcheck disable=SC2046
  try $P -m plantgraph.qa.audit select $(audit_runs) --questions-root "$ROOT/questions" \
    --contextrag-run "$ROOT/ladder/runs/E8-CTXH-H1g21" --contextrag-run "$ROOT/ladder/runs/E8-CTXH-H3g21" \
    --contextrag-run "$ROOT/ladder/runs/E8-CTXH-H10g21" --ledger "$ROOT/audit/ledger.jsonl" \
    --cap-usd "$as_cap" --out "$AUDIT/plan.json"
}

audit_subgraphs() {  # one excerpt file per corpus that has selected rows: the sealed plants and ContextRAG's ladder plants
  mkdir -p "$AUDIT/subgraphs"
  for asg_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt") $CTX_LADDER; do
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
  $P -m plantgraph.qa.audit judge $(audit_runs) $(audit_ctx_runs) --questions-root "$ROOT/questions" --plan "$AUDIT/plan.json" \
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

copy_dirs() {  # copy_dirs <dest> <source>...: a failed copy is a failed report, not a silent gap
  cd_dest=$1; shift
  mkdir -p "$cd_dest" || return 1
  for cd_src in "$@"; do cp -r "$cd_src" "$cd_dest/" || return 1; done
}

assemble_roots() {  # the first measurement's report tools read <root>/{runs,corpora,questions}: copy them together
  for ar_root in r5_1000 duplication; do
    for ar_part in runs corpora questions; do mkdir -p "$ROOT/reports/$ar_root/$ar_part" || return 1; done
  done
  for ar_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    case $ar_id in
      H1000g*) ar_root=r5_1000 ;;
      H100g21p1) ar_root=duplication ;;
      *) continue ;;
    esac
    copy_dirs "$ROOT/reports/$ar_root/runs" "$ROOT/m6a/runs/S7-CYP-$ar_id" "$ROOT/m6a/runs/S7-AG-$ar_id" || return 1
    copy_dirs "$ROOT/reports/$ar_root/corpora" "$ROOT/corpora/$ar_id" || return 1
    copy_dirs "$ROOT/reports/$ar_root/questions" "$ROOT/questions/$ar_id" || return 1
  done
  for ar_id in H100g21p1d0 H100g21p1d50; do
    copy_dirs "$ROOT/reports/duplication/runs" "$ROOT/m6c/runs/S7-CYP-$ar_id" "$ROOT/m6c/runs/S7-AG-$ar_id" || return 1
    copy_dirs "$ROOT/reports/duplication/corpora" "$ROOT/corpora/$ar_id" || return 1
    copy_dirs "$ROOT/reports/duplication/questions" "$ROOT/questions/$ar_id" || return 1
  done
}

# ---- the reports: each is a function that returns 1 on failure and never stops the launcher itself ----------

scale_args() {  # scale_args: sets SEALED_CORPORA (--corpus flags) and SCALE_ARGS (--scale flags) from the sealed plan
  SEALED_CORPORA=; sa_100=; sa_1000=
  for sa_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    SEALED_CORPORA="$SEALED_CORPORA --corpus $sa_id"
    case $sa_id in H100g*) sa_100="$sa_100,$sa_id" ;; *) sa_1000="$sa_1000,$sa_id" ;; esac
  done
  SCALE_ARGS="--scale S100=${sa_100#,} --scale S1000=${sa_1000#,}"
}

report_sealed() {  # V2T-A2's sealed claims (Q4, K1, K2, K3, Q5)
  POL=src/plantgraph/qa/cascade/policies_v2t
  scale_args; rs_runs=
  for rs_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    rs_runs="$rs_runs --run $rs_id:cypher-v2t=$ROOT/m6a/runs/S7-CYP-$rs_id --run $rs_id:agent-v2t=$ROOT/m6a/runs/S7-AG-$rs_id"
  done
  # shellcheck disable=SC2086
  $P -m plantgraph.qa.cascade report --sealed-claims --claims v2t --setting A \
    --policy $POL/cascade_v4_iso.json --policy $POL/cascade_v4.json --policy $POL/references/always_g_v2t.json \
    --policy $POL/references/always_c_v2t.json --questions-root "$ROOT/questions" --corpora-root "$ROOT/corpora" \
    $SCALE_ARGS --out "$ROOT/reports/sealed" $SEALED_CORPORA $rs_runs > "$ROOT/reports/sealed.stdout.txt" || return 1
}

report_f1_baseline() {  # F1's own sealed claims (cascade_v3) on the same ten plants, as exp0007 run_sealed.sh did
  POL=src/plantgraph/qa/cascade/policies
  scale_args; rf_runs=
  for rf_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    rf_runs="$rf_runs --run $rf_id:cypher-luna=$ROOT/m6b/runs/S7F1-CYP-$rf_id --run $rf_id:agent-luna=$ROOT/m6b/runs/S7F1-AG-$rf_id"
  done
  # shellcheck disable=SC2086
  $P -m plantgraph.qa.cascade report --sealed-claims --claims f1 --cutoff-s 120 \
    --policy $POL/cascade_v3.json --policy $POL/always_g_luna.json --policy $POL/always_c_luna.json \
    --policy $POL/cascade_v3_iso.json --questions-root "$ROOT/questions" --corpora-root "$ROOT/corpora" \
    $SCALE_ARGS --out "$ROOT/reports/f1_baseline" $SEALED_CORPORA $rf_runs > "$ROOT/reports/f1_baseline.stdout.txt" || return 1
}

report_tune() {  # per-plant counts by question family and the setting check, for every sealed plant
  for rt_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    $P -m plantgraph.qa.cascade tune-report --corpus "$rt_id" --setting A --questions-root "$ROOT/questions" \
      --corpora-root "$ROOT/corpora" --run "cypher-v2t=$ROOT/m6a/runs/S7-CYP-$rt_id" \
      --run "agent-v2t=$ROOT/m6a/runs/S7-AG-$rt_id" --out "$ROOT/reports/tune/$rt_id" \
      > "$ROOT/reports/tune_$rt_id.stdout.txt" 2>&1 || return 1
  done
}

report_ladder() {  # the ladder report reads <root>/runs, corpora, questions (assembled in M5)
  $P -m plantgraph.qa.exp0001 report --edition v21 --system v2t --root "$ROOT/ladder" --out "$ROOT/reports/ladder" \
    --ctx-high-policy "$INPUTS/always_ctx_high.json" --ctx-low-policy "$INPUTS/always_ctx_low.json" \
    > "$ROOT/reports/ladder.stdout.txt" || return 1
}

report_duplication() {
  assemble_roots || return 1
  $P -m plantgraph.qa.exp0001 duplication-report --system v2t --root "$ROOT/reports/duplication" \
    --points "H100g21p1d0=0,H100g21p1=25,H100g21p1d50=50" --out "$ROOT/reports/duplication_out" \
    > "$ROOT/reports/duplication.stdout.txt" || return 1
}

report_e2e() {
  assemble_roots || return 1
  re_plants=
  for re_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt" | grep 'H1000'); do re_plants="$re_plants --plant $re_id:${re_id}V"; done
  # shellcheck disable=SC2086
  $P -m plantgraph.exp0004.e2e_report --e2e-root "$ROOT/m8b/e2e" --r5-root "$ROOT/reports/r5_1000" \
    --out "$ROOT/reports/e2e" $re_plants --headline-n 220 > "$ROOT/reports/e2e.stdout.txt" || return 1
}

report_c1() {  # the concurrency-1 control against the main run of the same plant
  $P -m plantgraph.qa.exp0008.c1_report --main-answers "$ROOT/m6a/runs/S7-AG-H1000g21p1/answers.jsonl" \
    --control-answers "$ROOT/m6c/runs/S7-AG-H1000g21p1-C1/answers.jsonl" --out "$ROOT/reports/c1.md" || return 1
}

report_step() {  # report_step <name>: run report_<name> once; a failure is noted and the next report still runs
  rs_name=$1
  rs_marker=$STATE/steps/M10b_report_$rs_name.ok
  if [ -e "$rs_marker" ]; then event NOTE "skip report $rs_name (done)"; return 0; fi
  if "report_$rs_name" > "$LOGS/report_$rs_name.txt" 2>&1; then
    : > "$rs_marker"
    event NOTE "report $rs_name done"
  else
    echo "$rs_name" >> "$ROOT/reports/FAILED.txt"
    event NOTE "report $rs_name FAILED, see $LOGS/report_$rs_name.txt"
  fi
}

all_reports() {
  if smoke; then   # canned replies: only the report that needs no real scores is exercised
    event NOTE "SMOKE: the cascade, ladder, duplication and E2E report tools are not run on canned replies"
    report_step c1
    return 0
  fi
  for ar_name in sealed f1_baseline tune ladder duplication e2e c1; do report_step "$ar_name"; done
}

stage_M10b() {
  mkdir -p "$ROOT/reports"
  require_frozen
  plan_to_file sealed
  rm -f "$ROOT/reports/FAILED.txt"
  all_reports
  once demo demo_database   # always runs, even after a failed report: the database must end on the demo plant
  if [ -s "$ROOT/reports/FAILED.txt" ]; then
    stop_run infra "reports failed: $(tr '\n' ' ' < "$ROOT/reports/FAILED.txt")(logs $LOGS/report_<name>.txt); the demo plant is loaded; fix, then resume (finished reports are skipped)"
  fi
  echo "reports: $ROOT/reports; database: H1000g21p1" > "$ROOT/reports/DONE.txt"
  outputs "$ROOT/reports/DONE.txt"
}
