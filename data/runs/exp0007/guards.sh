#!/bin/sh
# Gates S0 of the v2 re-measurement (ADR-0060 point 1; plan section 2): is the system still F1?
# FREE: no paid call. Without --with-neo4j everything except the Cypher replay (S0-d) runs and no
# PASSED file is written; with it, S0-d loads EXP-0001's H1 into the database named by
# E7_NEO4J_DATABASE (never the user's `neo4j` database unless E7_TARGET_IS_PLANT_DB=yes).
#   sh data/runs/exp0007/guards.sh [--with-neo4j]
# Writes data/runs/exp0007/guards/PASSED (commit + whether S0-d ran) when everything passed on a clean tree.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/guards; EXPERIMENT=EXP-0007-GUARD
init_stage; rm -f $S/PASSED

echo "--- S0-a: no system-side path differs from F1 (six named exceptions)"
$EX check-paths --f1-commit-file $SEALED/F1.commit || die "S0-a failed"

echo "--- S0-b: frozen inputs"
sha256sum -c --quiet $SEALED/F1.sha256 || die "S0-b: a file hashed in F1.sha256 changed"
$EX check-inputs --sealed-inputs $SEALED/inputs --inputs $IN \
  --same-as-sealed params_agent_low.json params_cypher_plant.json pin_agent_luna_final_high.json pin_cypher_luna_low.json \
  || die "S0-b failed"
git diff --quiet "$(cat $SEALED/F1.commit)" -- src/plantgraph/qa/cascade/policies || die "S0-b: the cascade policies changed since F1"

echo "--- S0-e: Luna's listing"
check_listing "$(listing_file)"

echo "--- S0-c: cache-only replays of one v1 run per arm (byte-identical or stop)"
# replays read copies, so the committed v1 caches are never opened for writing
cp $SEALED/cache_sealed.sqlite $S/cache_sealed.copy.sqlite
cp $E1/cache_exp0001.sqlite $S/cache_exp0001.copy.sqlite
replay ST-AG-H100 $SEALED/runs/ST-AG-H100 $S/cache_sealed.copy.sqlite 120 --corpus H100:test $(tier_options ag) \
  --corpora-root $SEALED/corpora --questions-root $SEALED/questions
for c in H1 H30; do
  replay E1-AG-$c $E1/runs/E1-AG-$c $S/cache_exp0001.copy.sqlite 120 --corpus $c:test $(tier_options ag) \
    --corpora-root $E1/corpora --questions-root $E1/questions
  replay E1-CTXH-$c $E1/runs/E1-CTXH-$c $S/cache_exp0001.copy.sqlite 300 --corpus $c:test --strategy context_rag \
    --pin-json $IN/pin_agent_luna_final_high.json --corpora-root $E1/corpora --questions-root $E1/questions
done

if [ "$WITH_NEO4J" = yes ]; then
  echo "--- S0-d: Cypher replay of E1-CYP-H1 (EXP-0001's H1 loaded alone)"
  use_database
  $P -m plantgraph.ingest synthetic --headline --target-sheets 1 --seed "$(cat $E1/H1.seed)" \
    --store-profile plant --corpus-id H1 --fresh-database --out $S/neo4jplant/H1 \
    > $S/logs/load_H1.json 2> $S/logs/load_H1.err || die "S0-d: loading H1 failed, see $S/logs/load_H1.err"
  replay E1-CYP-H1 $E1/runs/E1-CYP-H1 $S/cache_exp0001.copy.sqlite 120 --corpus H1:test $(tier_options cyp) \
    --corpora-root $S/neo4jplant --questions-root $E1/questions
else
  echo "--- S0-d skipped (needs Neo4j): rerun with --with-neo4j before the first paid call"
fi

require_identical_replays
rm -f $S/*.copy.sqlite
if [ -n "$(git status --porcelain)" ]; then
  echo "ALL CHECKED GATES PASSED, but the tree is not clean: no PASSED file. Commit, then rerun."
  exit 0
fi
printf '%s\nwith_cypher_replay=%s\n' "$(git rev-parse HEAD)" "$WITH_NEO4J" > $S/PASSED
echo "=== guards passed at $(git rev-parse HEAD) (Cypher replay: $WITH_NEO4J)"
