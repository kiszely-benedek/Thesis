#!/bin/sh
# Stage 3: dev quality check on D100g2 (ADR-0060 status, stage 3). DIAGNOSTIC ONLY: nothing is tuned on it
# under F1. Both frozen tiers answer the dev question set (10 per family); cascade_v3 is joined offline.
# Writes dev_check/report/{dev_report.md,dev_report.json,failures.jsonl}: accuracy per family and the
# list of wrong answers (question, family, expected, got, which tier answered) for a later tuning round.
#
#   sh data/runs/exp0007/dev_check.sh        FREE: builds the question set, computes and prints the caps
#   sh data/runs/exp0007/dev_check.sh --allow-paid-calls --cap-file <file> --cap-sha256 <hash>      PAID
# Caps: cap = ceil_0.05(1.3 x n x c) per tier, c = v1 dev cost per question x the pilot correction.
# Needs: pilot/pilot_result.json (override: PILOT_RESULT), R1/R2, guards.sh --with-neo4j at this commit,
# E7_NEO4J_DATABASE. The pilot's cache is reused, so its ten questions cost nothing again.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/dev_check; CACHE=$X/cache_dev.sqlite; EXPERIMENT=EXP-0007-DEVCHECK
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$X/r1; QROOT=$S/questions
PILOT_RESULT=${PILOT_RESULT:-$X/pilot/pilot_result.json}
init_stage; require_r1_r2
[ -f "$PILOT_RESULT" ] || die "run the pilot first: $PILOT_RESULT is missing (the caps need its correction)"

make_questions() {  # the dev set: 10 per family from the dev pool (R2's draw), same seed as the other recipes
  $P -m plantgraph.qa.questions.per_family --in $X/r2/D100g2/questions.jsonl --n 10 --seed 20261101 \
    --out $QROOT/D100g2 || die "per-family draw failed"
}
step make_questions make_questions
show_caps dev "$PILOT_RESULT" --dev-questions $QROOT/D100g2/questions.jsonl
if [ "$ALLOW_PAID" != yes ]; then echo "prepared only: nothing was paid. To run: add --allow-paid-calls --cap-file ... --cap-sha256 ..."; exit 0; fi

require_paid; require_guards_passed; require_clean_tree
check_listing "$(listing_file)"
use_database
dev_tier_runs Q7 no
$EX dev-report --corpus-id D100g2 --cyp-run $S/runs/Q7-CYP-D100g2 --ag-run $S/runs/Q7-AG-D100g2 \
  --questions-root $QROOT --out $S/report || die "the dev report failed"
echo "=== $(date +%T) dev check done: $S/report/dev_report.md"
