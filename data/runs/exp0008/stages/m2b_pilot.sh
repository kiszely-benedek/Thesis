# M2b: the judge pilot and gate G2. Sourced by run_all.sh.
#
# The scorer audit (M10a) asks a second, independent LLM judge whether the deterministic scorer's verdicts are
# right. Before the audit is relied on, the judge is piloted on 45 first-measurement rows whose truth is known:
# 13 VALVES_ON_PATH rows the scorer got wrong, 12 numeric-list parse failures, 20 controls (right under both
# definitions). G2 passes if at least 80 % of the known defects are judged correct or ambiguous_question and at
# least 80 % of the controls correct. The pilot also measures the cost per judge call, which sizes the audit.
#
# The pilot reads first-measurement records, which the v2.1 code cannot rebuild, so its inputs are prepared
# once by hand and listed in data/runs/exp0008/inputs/pilot/ (see the README):
#   valves_ids.txt   the 13 question ids         runs.txt       one first-measurement run directory per line
#   questions/       <corpus>/questions.jsonl     subgraphs.json  plant excerpts cut with
#                                                scripts/audit_export_subgraphs.py on a `git archive 4dfad69` copy
# Money: the judge's own ledger (audit/ledger.jsonl) caps the pilot at $1.50 and the audit at $10 in all.

PILOT_IN=$SCRIPTS/inputs/pilot

pilot_set() {
  pilot_runs=
  while read -r pilot_run; do pilot_runs="$pilot_runs --run $pilot_run"; done < "$PILOT_IN/runs.txt"
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.audit pilot-set $pilot_runs --questions-root "$PILOT_IN/questions" \
    --valves-ids "$PILOT_IN/valves_ids.txt" --out "$ROOT/audit/pilot/plan.json"
}

pilot_judge() {
  pj_cap=$($L audit-cap --root "$ROOT") || stop_run topup "no money left under the \$40 program cap for the audit"
  $L balance --needed "$pj_cap" $(balance_args) || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$pj_cap"
  pilot_runs=
  while read -r pilot_run; do pilot_runs="$pilot_runs --run $pilot_run"; done < "$PILOT_IN/runs.txt"
  # shellcheck disable=SC2086
  try $P -m plantgraph.qa.audit judge $pilot_runs --questions-root "$PILOT_IN/questions" \
    --plan "$ROOT/audit/pilot/plan.json" --subgraphs "$PILOT_IN/subgraphs.json" --out-dir "$ROOT/audit/pilot" \
    --ledger "$ROOT/audit/ledger.jsonl" --cap-usd "$pj_cap" --stage pilot --allow-paid-calls
}

g2_gate() {
  g2_file=$ROOT/audit/pilot/verdicts.jsonl
  if smoke; then
    g2_fail=; if forced g2; then g2_fail=--fail; fi
    mkdir -p "$ROOT/audit"; rm -f "$ROOT/audit/ledger.jsonl"
    # shellcheck disable=SC2086
    try $L smoke-evidence g2 --out-dir "$ROOT/audit/pilot" $g2_fail
  fi
  if g2_text=$($L g2 --verdicts "$g2_file" --out "$STATE/g2.json"); then gate_pass "G2 $g2_text"
  else gate_fail "G2" "$g2_text (revise the judge prompt, commit a new part A, re-pilot on the old rows only)"; fi
}

stage_M2b() {
  mkdir -p "$ROOT/audit/pilot"
  if ! smoke; then
    once pilot_set pilot_set
    once pilot_judge pilot_judge
  fi
  g2_gate
  outputs "$STATE/g2.json" "$ROOT/audit/pilot/verdicts.jsonl" "$ROOT/audit/ledger.jsonl"
}
