# P1d: the scorer audit, then END's reports. PAID (the judge). Sourced by run_all.sh.
#
# The scorer audit has a second model (the judge) read a sample of answered rows and say whether the programmatic
# scorer was right. The MAIN SAMPLE is EXP-0008's `qa.audit select` and `judge` over the A2 sealed runs, in the
# pre-registered order. The B STRATUM is half the main sample's size: VALVE_SET and POSITION rows of the B sealed
# runs only, every wrong row first, then a seeded random sample of right rows, deduplicated by question and parsed
# answer; judged with the same pin and prompt, with excerpts cut by scripts/audit_export_subgraphs.py on the B
# corpus, and a sheet that prints, per B row, the nodes each answered item resolved to.
# The audit ledger is design 19.9's: min($8.13, $35 - runs spent). The launcher STOPS after the judge:
# classifying disagreements is the main session's work under the audit rule.

AUDIT=$ROOT/audit/main
AUDIT_B=$ROOT/audit/b
# the judge sizes its selection with the EXP-0008 pilot's measured cost per call (design 19.9: no new pilot)
audit_call_usd() {
  $P -c "from pathlib import Path; from plantgraph.qa.audit.budget import SpendLedger, sizing_cost_per_call; ledger = SpendLedger(Path('data/runs/exp0008/audit/ledger.jsonl')); print(sizing_cost_per_call(ledger.measured_cost_per_call('pilot')))"
}

audit_run_flags() {  # audit_run_flags <A|B>: --run flags for the sealed runs of one system
  arf_flags=
  for arf_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    if [ "$1" = A ]; then
      arf_flags="$arf_flags --run $ROOT/p1c/runs/S9-CYP-$arf_id --run $ROOT/p1c/runs/S9-AG-$arf_id"
    else
      arf_flags="$arf_flags --run $ROOT/p1c/runs/S9-CYP-${arf_id}B --run $ROOT/p1c/runs/S9-AG-${arf_id}B"
    fi
  done
  echo "$arf_flags"
}

audit_select() {
  as_cap=$($L audit-cap --root "$ROOT") || stop_run topup "no money left under the \$35 program cap for the audit"
  # shellcheck disable=SC2046
  try $P -m plantgraph.qa.audit select $(audit_run_flags A) --questions-root "$ROOT/questions" \
    --ledger "$ROOT/audit/ledger.jsonl" --cap-usd "$as_cap" --call-usd "$(audit_call_usd)" --out "$AUDIT/plan.json"
}

audit_subgraphs() {  # one excerpt file per corpus that has selected rows (A plants; B plants for the stratum)
  mkdir -p "$AUDIT/subgraphs" "$AUDIT_B/subgraphs"
  for asg_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    try $L plan-ids --plan "$AUDIT/plan.json" --corpus "$asg_id" --out "$AUDIT/ids_$asg_id.txt"
    if [ -s "$AUDIT/ids_$asg_id.txt" ]; then
      try $P scripts/audit_export_subgraphs.py --corpus-id "$asg_id" --ingest-json "$ROOT/corpora/$asg_id/ingest.json" \
        --questions "$ROOT/questions/$asg_id/questions.jsonl" --question-ids "$AUDIT/ids_$asg_id.txt" \
        --out "$AUDIT/subgraphs/$asg_id.json"
    fi
  done
}

audit_b_select() {
  # shellcheck disable=SC2046
  try $L audit-b-select $(audit_run_flags B) --main-plan "$AUDIT/plan.json" \
    --questions-root "$ROOT/questions" --corpora-root "$ROOT/corpora" --out "$AUDIT_B/plan.json" --sheet "$AUDIT_B/resolution_sheet.txt"
  for absg_id in $(cut -d' ' -f1 "$LOGS/plan_sealed.txt"); do
    try $L plan-ids --plan "$AUDIT_B/plan.json" --corpus "${absg_id}B" --out "$AUDIT_B/ids_${absg_id}B.txt"
    if [ -s "$AUDIT_B/ids_${absg_id}B.txt" ]; then
      try $P scripts/audit_export_subgraphs.py --corpus-id "${absg_id}B" --ingest-json "$ROOT/corpora/${absg_id}B/ingest.json" \
        --questions "$ROOT/questions/${absg_id}B/questions.jsonl" --question-ids "$AUDIT_B/ids_${absg_id}B.txt" \
        --out "$AUDIT_B/subgraphs/${absg_id}B.json"
    fi
  done
}

audit_judge() {  # audit_judge <A|B>
  aj_sys=$1; aj_dir=$AUDIT; if [ "$aj_sys" = B ]; then aj_dir=$AUDIT_B; fi
  aj_cap=$($L audit-cap --root "$ROOT" --left) || stop_run topup "no money left under the \$35 program cap for the audit"
  # shellcheck disable=SC2046
  $L balance --needed "$aj_cap" $(balance_args) || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$aj_cap"
  aj_sub=; for aj_f in "$aj_dir"/subgraphs/*.json; do aj_sub="$aj_sub --subgraphs $aj_f"; done
  event START "audit judge ($aj_sys), cap \$$aj_cap"
  aj_rc=0
  # shellcheck disable=SC2046,SC2086
  $P -m plantgraph.qa.audit judge $(audit_run_flags "$aj_sys") --questions-root "$ROOT/questions" --plan "$aj_dir/plan.json" \
    $aj_sub --out-dir "$aj_dir" --ledger "$ROOT/audit/ledger.jsonl" --cap-usd "$aj_cap" --stage "audit$aj_sys" \
    --allow-paid-calls >> "$LOGS/audit_judge_$aj_sys.log" 2>&1 || aj_rc=$?
  [ $aj_rc -eq 0 ] || stop_run infra "the audit judge ($aj_sys) failed (exit $aj_rc), see $LOGS/audit_judge_$aj_sys.log"
}

audit_report() {  # audit_report <dir>
  try $P -m plantgraph.qa.audit report --verdicts "$1/verdicts.jsonl" --out "$1/report.md" --sheet "$1/disagreements.csv"
}

stage_P1d() {
  mkdir -p "$AUDIT" "$AUDIT_B"
  require_frozen
  plan_to_file sealed
  estimate_note_audit
  if smoke; then
    event NOTE "SMOKE: selection and the judge need a real model; the audit is not run"
    : > "$AUDIT/report.md"; : > "$AUDIT_B/report.md"
  else
    once select audit_select
    once subgraphs audit_subgraphs
    if [ "$(cat "$STATE/b_sealed")" = yes ]; then once b_select audit_b_select; fi
    once judge audit_judge A
    if [ "$(cat "$STATE/b_sealed")" = yes ]; then once judge_b audit_judge B; fi
    audit_report "$AUDIT"
    if [ "$(cat "$STATE/b_sealed")" = yes ]; then audit_report "$AUDIT_B"; fi
  fi
  outputs "$AUDIT/report.md"
}

estimate_note_audit() {
  event NOTE "estimate P1d: main sample + B stratum about \$5.42, audit ledger cap \$8.13 (min of that and \$35 less the runs); $($L spent --root "$ROOT")"
}
