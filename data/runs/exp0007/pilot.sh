#!/bin/sh
# Stage 2: the pilot on D100g2 (plan section 5; ADR-0060 status, stage 2). Dev plant, dev questions.
# Ten questions (one per family), both frozen tiers; a 2-question smoke per tier first.
# Measures the token and dollar correction t_v2 / t_v1 that scales every later cap.
#
#   sh data/runs/exp0007/pilot.sh                      FREE: builds the questions, writes and prints the cap file
#   sh data/runs/exp0007/pilot.sh --allow-paid-calls --cap-file <file> --cap-sha256 <hash>      PAID, <= $0.10
# Needs: R1 and R2 outputs; guards.sh --with-neo4j passed at this commit; E7_NEO4J_DATABASE (a temporary
# database; the user's `neo4j` is refused). Writes pilot/pilot_result.json (the correction per tier).
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/pilot; CACHE=$X/cache_dev.sqlite; EXPERIMENT=EXP-0007-PILOT
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$X/r1; QROOT=$S/questions
init_stage; require_r1_r2

make_questions() {  # one question per family from the dev pool, filtered to the ten pilot families
  $P -m plantgraph.qa.questions.per_family --in $X/r2/D100g2/questions.jsonl --n 1 --seed 20261101 \
    --out $S/draw/D100g2 || die "per-family draw failed"
  $EX filter-families --source $S/draw/D100g2/questions.jsonl --out $QROOT/D100g2/questions.jsonl --pilot-families
  $EX head-questions --source $QROOT/D100g2/questions.jsonl --out $S/questions_smoke/D100g2/questions.jsonl
}
step make_questions make_questions
show_caps pilot ''
if [ "$ALLOW_PAID" != yes ]; then echo "prepared only: nothing was paid. To run: add --allow-paid-calls --cap-file ... --cap-sha256 ..."; exit 0; fi

require_paid; require_guards_passed; require_clean_tree
check_listing "$(listing_file)"
use_database
dev_tier_runs P7 yes
$EX pilot-report --pilot-runs $S/runs --out $S/pilot_result.json \
  || die "the pilot correction is above the stop limit (or a run is unreadable): ask the user before any later cap"
echo "=== $(date +%T) pilot done: $S/pilot_result.json"
