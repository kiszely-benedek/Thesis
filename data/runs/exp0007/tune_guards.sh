#!/bin/sh
# Guards run at every V2T tuning-round commit (ADR-0061, design qa-tuning-v2.md §5.3, §6, QT-8).
# FREE: no paid call, no model. Three groups:
#   1. F1 stays byte-identical: F1's frozen inputs still hash as sealed, and cache-only replays of one
#      v1 run per arm (the pieces of guards.sh S0-b / S0-c) reproduce their stored answers.
#   2. The line view equals the gold's independent walk (LINE-01), on every corpus listed.
#   3. API-02: the canonical programs against the question references on the dev questions.
#
#   sh data/runs/exp0007/tune_guards.sh [--with-neo4j]
# On a clean tree it also writes tune/guards/PASSED (commit + whether 1c ran); tune.sh requires it.
# Environment:
#   LINE_CORPORA     "corpus-id:ingest.json ..." for LINE-01 (default: D100g2 of the dev check)
#   API02_CORPUS     "corpus-id:ingest.json:questions.jsonl" (default: D100g2 dev set)
#   API02_MIN_SHARE  smallest accepted share per family (default 1.0: since QT-2a the plant API has the
#                    "line" relation group and all 18 dev families are expressible. Before it,
#                    DOWNSTREAM_IN_UNIT, FLOW_PATH and NEIGHBOURS_DOWNSTREAM scored 0.1-0.2 because of fittings)
#   E7_NEO4J_DATABASE  needed only with --with-neo4j (S0-d, the Cypher replay): a temporary database
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/tune/guards; EXPERIMENT=EXP-0007-TUNE-GUARD
init_stage; mkdir -p $S/logs; rm -f $S/PASSED
[ "$ALLOW_PAID" = no ] || die "this script is free: --allow-paid-calls is not accepted"

D=$X/dev_check/neo4jplant/D100g2
LINE_CORPORA=${LINE_CORPORA:-D100g2:$D/ingest.json}
API02_CORPUS=${API02_CORPUS:-D100g2:$D/ingest.json:$X/dev_check/questions/D100g2/questions.jsonl}
API02_MIN_SHARE=${API02_MIN_SHARE:-1.0}

echo "--- 1a: F1's frozen inputs"
sha256sum -c --quiet $SEALED/F1.sha256 || die "a file hashed in F1.sha256 changed"
$EX check-inputs --sealed-inputs $SEALED/inputs --inputs $IN \
  --same-as-sealed params_agent_low.json params_cypher_plant.json pin_agent_luna_final_high.json pin_cypher_luna_low.json \
  || die "1a failed: an F1 input differs from the sealed copy"

echo "--- 1b: cache-only replays of one v1 run per arm (byte-identical or stop)"
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
  echo "--- 1c: Cypher replay of E1-CYP-H1 (EXP-0001's H1 loaded alone, into a temporary database)"
  use_database
  $P -m plantgraph.ingest synthetic --headline --target-sheets 1 --seed "$(cat $E1/H1.seed)" \
    --store-profile plant --corpus-id H1 --fresh-database --out $S/neo4jplant/H1 \
    > $S/logs/load_H1.json 2> $S/logs/load_H1.err || die "1c: loading H1 failed, see $S/logs/load_H1.err"
  replay E1-CYP-H1 $E1/runs/E1-CYP-H1 $S/cache_exp0001.copy.sqlite 120 --corpus H1:test $(tier_options cyp) \
    --corpora-root $S/neo4jplant --questions-root $E1/questions
else
  echo "--- 1c skipped (needs Neo4j): rerun with --with-neo4j before a round commit"
fi
require_identical_replays
rm -f $S/*.copy.sqlite

echo "--- 2: LINE-01, the line view equals the gold's walk"
for spec in $LINE_CORPORA; do
  $P -m plantgraph.qa.harness.line_view_fidelity --corpus-id "${spec%%:*}" --ingest-json "${spec#*:}" \
    || die "2 failed: LINE-01 on ${spec%%:*}"
done

echo "--- 3: API-02 on the dev questions (min share $API02_MIN_SHARE)"
rest=${API02_CORPUS#*:}
$P -m plantgraph.qa.harness.api_check_questions --corpus-id "${API02_CORPUS%%:*}" \
  --ingest-json "${rest%%:*}" --questions "${rest#*:}" --min-share "$API02_MIN_SHARE" \
  || die "3 failed: API-02"
echo "=== tune guards passed at $(git rev-parse --short HEAD) (Cypher replay: $WITH_NEO4J)"
if [ -n "$(git status --porcelain)" ]; then
  echo "ALL CHECKED GATES PASSED, but the tree is not clean: no PASSED file. Commit, then rerun."
  exit 0
fi
printf '%s
with_cypher_replay=%s
' "$(git rev-parse HEAD)" "$WITH_NEO4J" > $S/PASSED
