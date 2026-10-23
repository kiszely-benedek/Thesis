#!/bin/sh
# EXP-0001 stage C: ContextRAG-high on the sealed H100 corpus, 24 questions (ADR-0054 point 5; design 9.3).
# PAID (about $2.7, cap $4.00). Only on the pre-registered trigger: X3 found no accuracy flip up to H30,
# X5 predicts H100 fits, and the user approved the spend. Start with:  STAGE_C_APPROVED=yes sh <this file>
# No Neo4j is used. Do NOT run pytest while this runs.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0001/lib.sh
[ "${STAGE_C_APPROVED:-}" = yes ] || die "stage C needs the user's approval: set STAGE_C_APPROVED=yes"
[ -e $S/report/report.md ] || die "run stages A and B first: the trigger is read from $S/report/report.md"

h100() {
  ctx E1-CTXH-H100 H100 $IN/pin_agent_luna_final_high.json 4.00 full $S/questions_c $SEALED/corpora 2
}

stage_c_report() {  # cascade_v3 on the same 24 questions is joined from the sealed H100 rows
  $P -m plantgraph.qa.exp0001 report --root $S --out $S/report_with_h100 \
    --h100-tiers $SEALED/runs/ST-CYP-H100,$SEALED/runs/ST-AG-H100 > $S/logs/report_h100.stdout.txt \
    || die "the EXP-0001 report with H100 failed"
}

preflight
step guard replay_guard
step ctxh_H100 h100
step replay_ctxh_H100 replay_ctx E1-CTXH-H100 H100 $IN/pin_agent_luna_final_high.json $S/questions_c $SEALED/corpora
step report_h100 stage_c_report
echo "=== replay checks"; head -v $S/replays/INF-E1-CTXH-H100/replay_check.txt
echo "=== $(date +%T) done: $S/report_with_h100/report.md"
