#!/bin/sh
# R4: the ladder H1g2..H30g2, both frozen tiers (plan section 6; ADR-0054 applied by ADR-0060). PAID.
# ContextRAG, the reference arm, is NOT run here (deferred by the user, ADR-0060 status).
# Do NOT run pytest while this runs. One corpus in Neo4j at a time, in the database E7_NEO4J_DATABASE.
#   sh data/runs/exp0007/run_ladder.sh                  FREE: checks the freeze, shows the caps
#   sh data/runs/exp0007/run_ladder.sh --allow-paid-calls --cap-file data/runs/exp0007/caps_r4.json --cap-sha256 <hash>
# Refuses to run without the E7 freeze file, at another commit than E7, or after any input changed.
# A rerun skips finished steps; a run stopped at its cap resumes under the same id only with a higher cap.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/ladder; CACHE=$S/cache_e7.sqlite; EXPERIMENT=EXP-0007
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$S/corpora; QROOT=$S/questions
LADDER="H1g2 H3g2 H10g2 H30g2"
require_clean_tree; require_freeze
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
check_listing "$(listing_file)"
init_stage
cat $X/caps_r4.json
if [ "$ALLOW_PAID" != yes ]; then echo "checked only: nothing was paid. sha256 $(sha256sum $X/caps_r4.json | cut -d' ' -f1)"; exit 0; fi
require_paid
[ "$CAP_FILE" = $X/caps_r4.json ] || die "expected --cap-file $X/caps_r4.json (hashed into E7.sha256), found $CAP_FILE"
use_database

load_ladder() {  # this corpus alone in the database, then checked against the question corpus
  id=$1; load_plant "$id" "$(sheets_of "$id")" "$($EX test-seed --sheets "$(sheets_of "$id")")" $S/neo4jplant
  check_loaded_matches "$S/neo4jplant/$id/ingest.json" "$S/corpora/$id/ingest.json"
}

cypher_tier() {
  for c in $LADDER; do
    step load_$c load_ladder $c
    if [ "$c" = H1g2 ]; then step cypher_H1g2_smoke tier_run cyp E7-CYP-H1g2-SMOKE H1g2 test smoke $S/questions_smoke; fi
    step cypher_$c tier_run cyp E7-CYP-$c $c test full
    step replay_cyp_$c replay_tier cyp E7-CYP-$c $c test
  done
}

agent_tier() {  # reads the in-memory graph; the database is not used
  step agent_H1g2_smoke tier_run ag E7-AG-H1g2-SMOKE H1g2 test smoke $S/questions_smoke
  for c in $LADDER; do
    step agent_$c tier_run ag E7-AG-$c $c test full
    step replay_ag_$c replay_tier ag E7-AG-$c $c test
  done
}

report() {  # both free: the cascade report is a cross-check, the EXP-0001-style report is the result
  set --
  for c in $LADDER; do
    set -- "$@" --corpus $c --run $c:cypher-luna=$S/runs/E7-CYP-$c --run $c:agent-luna=$S/runs/E7-AG-$c
  done
  POL=src/plantgraph/qa/cascade/policies
  $P -m plantgraph.qa.cascade report --policy $POL/cascade_v3.json --policy $POL/always_g_luna.json \
    --policy $POL/always_c_luna.json --questions-root $QROOT --corpora-root $S/corpora --cutoff-s 120 \
    --out $S/cascade_report "$@" > $S/logs/cascade_report.stdout.txt 2>&1 \
    || echo "WARNING: cascade report failed, see $S/logs/cascade_report.stdout.txt"
  $P -m plantgraph.qa.exp0001 report --edition v2 --root $S --ctx-high-policy $IN/always_ctx_high.json \
    --ctx-low-policy $IN/always_ctx_low.json --out $S/report > $S/logs/report.stdout.txt || die "the report failed"
}

step make_smoke $EX head-questions --source $QROOT/H1g2/questions.jsonl --out $S/questions_smoke/H1g2/questions.jsonl
cypher_tier
step restore_d1000_a restore_d1000
agent_tier
require_identical_replays
step report report
echo "=== replay checks (all must read 'identical')"; head -v $S/replays/*/replay_check.txt
echo "=== $(date +%T) done: $S/report/report.md"
