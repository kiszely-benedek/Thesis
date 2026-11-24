# P1d: the scorer audit, then END's reports. PAID (the judge). Sourced by run_all.sh.
#
# The scorer audit has a second model (the judge) read a sample of answered rows and say whether the programmatic
# scorer was right. The MAIN SAMPLE is EXP-0008's selection and frozen `qa.audit judge` over the SCOPE R rows of the
# A2 sealed runs (ADR-0069: A2's scope X rows are wrong by construction and are left out), in the pre-registered
# order. When B is sealed it is sized with 2/3 of the audit cap, so the B stratum (half its rows) fits in the rest.
# The B STRATUM is half the main sample's size: VALVE_SET and POSITION rows of the B sealed runs only, every wrong
# row first, then a seeded random sample of right rows, deduplicated by question and parsed answer; judged with the
# same pin and prompt template (through `exp0009.audit_judge`, which adds the help lines for VALVE_SET and POSITION),
# with excerpts cut by scripts/audit_export_subgraphs.py on the B corpus, and a sheet that prints, per B row, the
# nodes each answered item resolved to.
# The audit ledger is design 19.9's: min($8.13, $35 - runs spent). Both judges get that TOTAL as their cap and share
# one ledger file, so each dollar is counted once; a judge stopped by its cap is a STOP, not a silent success.
# The launcher STOPS after the judge reports (F5): classifying disagreements is the main session's work under the
# audit rule, which then creates state/audit_classified and resumes.

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

audit_select() {  # the main sample: scope R rows only, sized with 2/3 of the cap when the B stratum follows it
  as_cap=$($L audit-cap --root "$ROOT" --for-main-sample "$(cat "$STATE/b_sealed")") \
    || stop_run topup "no money left under the \$35 program cap for the audit"
  # shellcheck disable=SC2046
  try $P -m plantgraph.qa.exp0009.audit_select $(audit_run_flags A) --questions-root "$ROOT/questions" \
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

judge_module() {  # judge_module <A|B>: the frozen judge for the main sample, the EXP-0009 entry point for B's two answer types
  if [ "$1" = B ]; then echo "$P -m plantgraph.qa.exp0009.audit_judge"; else echo "$P -m plantgraph.qa.audit"; fi
}

require_judge_not_capped() {  # require_judge_not_capped <A|B>: the judge exits 0 even when its cap stopped it; read its log
  # the log is appended to over resumes, so only its LAST such line counts
  rj_line=$(grep "stopped by cap" "$LOGS/audit_judge_$1.log" | tail -n 1) \
    || stop_run infra "the audit judge ($1) printed no 'stopped by cap' line: $LOGS/audit_judge_$1.log"
  case $rj_line in
    *"stopped by cap: True"*) event CAP "the audit judge ($1) was stopped by its cap"
      stop_run topup "the audit judge ($1) was stopped by its cap, rows are left unjudged (see $LOGS/audit_judge_$1.log)" ;;
  esac
}

audit_judge() {  # audit_judge <A|B>: both judges get the TOTAL audit cap; they share one ledger file, so spend counts once
  aj_sys=$1; aj_dir=$AUDIT; if [ "$aj_sys" = B ]; then aj_dir=$AUDIT_B; fi
  aj_cap=$($L audit-cap --root "$ROOT") || stop_run topup "no money left under the \$35 program cap for the audit"
  aj_left=$($L audit-cap --root "$ROOT" --left) || stop_run topup "no money left under the \$35 program cap for the audit"
  # shellcheck disable=SC2046
  $L balance --needed "$aj_left" $(balance_args) || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$aj_left"
  aj_sub=; for aj_f in "$aj_dir"/subgraphs/*.json; do aj_sub="$aj_sub --subgraphs $aj_f"; done
  event START "audit judge ($aj_sys), total cap \$$aj_cap, still to spend \$$aj_left"
  aj_rc=0
  # shellcheck disable=SC2046,SC2086
  $(judge_module "$aj_sys") judge $(audit_run_flags "$aj_sys") --questions-root "$ROOT/questions" --plan "$aj_dir/plan.json" \
    $aj_sub --out-dir "$aj_dir" --ledger "$ROOT/audit/ledger.jsonl" --cap-usd "$aj_cap" --stage audit \
    --allow-paid-calls >> "$LOGS/audit_judge_$aj_sys.log" 2>&1 || aj_rc=$?
  [ $aj_rc -eq 0 ] || stop_run infra "the audit judge ($aj_sys) failed (exit $aj_rc), see $LOGS/audit_judge_$aj_sys.log"
  require_judge_not_capped "$aj_sys"
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
    smoke_judge_cap_check
  else
    once select audit_select
    once subgraphs audit_subgraphs
    if [ "$(cat "$STATE/b_sealed")" = yes ]; then once b_select audit_b_select; fi
    once judge audit_judge A
    if [ "$(cat "$STATE/b_sealed")" = yes ]; then once judge_b audit_judge B; fi
    audit_report "$AUDIT"
    if [ "$(cat "$STATE/b_sealed")" = yes ]; then audit_report "$AUDIT_B"; fi
  fi
  require_audit_classified
  outputs "$AUDIT/report.md"
}

require_audit_classified() {  # §19.7: the launcher stops after the judge; the main session classifies, then creates the file
  if smoke; then   # the smoke has no verdicts to classify: it plays the main session, unless told not to
    if forced audit-stop; then rm -f "$STATE/audit_classified"; else : > "$STATE/audit_classified"; fi
  fi
  [ -e "$STATE/audit_classified" ] && return 0
  stop_run main "the judge is done: classify the disagreements under the audit rule ($AUDIT/disagreements.csv, $AUDIT_B/disagreements.csv), then create $STATE/audit_classified and resume"
}

smoke_judge_cap_check() {  # --force judge-cap: a judge log that says its cap stopped it must stop the launcher
  forced judge-cap || return 0
  printf '%s\n' "judged 3, already done 0, not run 0" "failed 0; stopped by cap: True" > "$LOGS/audit_judge_B.log"
  require_judge_not_capped B
}

estimate_note_audit() {
  event NOTE "estimate P1d: main sample + B stratum about \$5.42, audit ledger cap \$8.13 (min of that and \$35 less the runs); $($L spent --root "$ROOT")"
}
