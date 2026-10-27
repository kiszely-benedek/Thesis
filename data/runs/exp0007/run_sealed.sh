#!/bin/sh
# R5: the sealed test on v2, both frozen tiers (plan section 7; ADR-0053 applied by ADR-0060). PAID.
# Corpora: H100g2, H1000g2, and the duplication points H100g2d0 / H100g2d50. ContextRAG is not run.
# Do NOT run pytest while this runs. One corpus in Neo4j at a time, in the database E7_NEO4J_DATABASE.
#   sh data/runs/exp0007/run_sealed.sh                  FREE: checks the freeze, shows the caps
#   sh data/runs/exp0007/run_sealed.sh --allow-paid-calls --cap-file data/runs/exp0007/caps_r5.json --cap-sha256 <hash>
# Refuses without the E7 freeze file and T7.sha256, at another commit than E7, or after any input changed.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/sealed; CACHE=$S/cache_s7.sqlite; EXPERIMENT=EXP-0007-SEALED
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$S/corpora; QROOT=$S/questions
require_clean_tree; require_freeze
[ -f $X/T7.sha256 ] || die "no T7.sha256: run make_test_set.sh first"
sha256sum -c --quiet $X/T7.sha256 || die "a test input changed since it was generated (T7.sha256)"
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
check_listing "$(listing_file)"
init_stage
cat $X/caps_r5.json
if [ "$ALLOW_PAID" != yes ]; then echo "checked only: nothing was paid. sha256 $(sha256sum $X/caps_r5.json | cut -d' ' -f1)"; exit 0; fi
require_paid
[ "$CAP_FILE" = $X/caps_r5.json ] || die "expected --cap-file $X/caps_r5.json (hashed into T7.sha256), found $CAP_FILE"
use_database

load_sealed() {  # this corpus alone in the database, then checked against the question corpus
  id=$1
  load_plant "$id" "$(sealed_sheets "$id")" "$($EX test-seed --sheets "$(sealed_sheets "$id")")" $S/neo4jplant $(sealed_dup_args "$id")
  check_loaded_matches "$S/neo4jplant/$id/ingest.json" "$S/corpora/$id/ingest.json"
}

cypher_tier() {
  for c in $SEALED_IDS; do
    step load_$c load_sealed $c
    if [ "$c" = H100g2 ]; then step cypher_H100g2_smoke tier_run cyp S7-CYP-H100g2-SMOKE H100g2 test smoke $S/questions_smoke; fi
    step cypher_$c tier_run cyp S7-CYP-$c $c test full
    step replay_cyp_$c replay_tier cyp S7-CYP-$c $c test
  done
}

agent_tier() {  # H1000g2-C1 is the concurrency-1 control; its own cache stops it reusing the main run's answers
  step agent_H100g2_smoke tier_run ag S7-AG-H100g2-SMOKE H100g2 test smoke $S/questions_smoke
  for c in $SEALED_IDS; do
    step agent_$c tier_run ag S7-AG-$c $c test full
    step replay_ag_$c replay_tier ag S7-AG-$c $c test
  done
  step agent_C1 tier_run ag S7-AG-H1000g2-C1 H1000g2 test full $S/questions_c1 1 $S/cache_s7_c1.sqlite
  step replay_agent_C1 replay S7-AG-H1000g2-C1 $S/runs/S7-AG-H1000g2-C1 $S/cache_s7_c1.sqlite 120 \
    --corpus H1000g2:test $(tier_options ag) --corpora-root $AG_CORPORA --questions-root $S/questions_c1
}

report() {  # free. The two headline corpora give the claims; the duplication points a descriptive table.
  POL=src/plantgraph/qa/cascade/policies
  $P -m plantgraph.qa.cascade report --sealed-claims --policy $POL/cascade_v3.json \
    --policy $POL/always_g_luna.json --policy $POL/always_c_luna.json --policy $POL/cascade_v3_iso.json \
    --corpus H100g2 --corpus H1000g2 --questions-root $QROOT --corpora-root $S/corpora --cutoff-s 120 --out $S/report \
    --run H100g2:cypher-luna=$S/runs/S7-CYP-H100g2 --run H100g2:agent-luna=$S/runs/S7-AG-H100g2 \
    --run H1000g2:cypher-luna=$S/runs/S7-CYP-H1000g2 --run H1000g2:agent-luna=$S/runs/S7-AG-H1000g2 \
    > $S/logs/report.stdout.txt || die "the sealed report failed"
  $P -m plantgraph.qa.exp0001 duplication-report --root $S --out $S/report_duplication \
    > $S/logs/report_duplication.stdout.txt || die "the duplication report failed"
}

step make_smoke $EX head-questions --source $QROOT/H100g2/questions.jsonl --out $S/questions_smoke/H100g2/questions.jsonl
cypher_tier
step restore_d1000_a restore_d1000
agent_tier
require_identical_replays
step report report
echo "=== replay checks (all must read 'identical')"; head -v $S/replays/*/replay_check.txt
echo "=== $(date +%T) done: $S/report/report.md ; $S/report_duplication/duplication.md"
