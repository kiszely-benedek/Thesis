#!/bin/sh
# R4 data: the v2 ladder corpora H1g2 H3g2 H10g2 H30g2, their questions and caps, at the FROZEN system
# (plan section 6; ADR-0060 decision 3B). FREE: no paid call, no Neo4j. Run ONCE, right after the user's
# commit of the system to measure. That commit is the freeze E7: this script writes E7.commit,
# E7.system and E7.sha256, and refuses to run again.
#   PILOT_RESULT=<file> sh data/runs/exp0007/make_set.sh --system-label <name>
# --system-label names what is frozen (F1 if untouched; otherwise the tuned system's own label).
# The pilot result must come from that same system (override the default with PILOT_RESULT).
# Test seeds come from TEST_SEEDS_V2 only (asserted); no test corpus exists before this script.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
parse_paid_args "$@"
S=$X/ladder
PILOT_RESULT=${PILOT_RESULT:-$X/pilot/pilot_result.json}
[ ! -e $X/E7.sha256 ] || die "E7.sha256 exists; never overwrite it"
[ -n "$SYSTEM_LABEL" ] || die "pass --system-label <name>: which system is frozen at this commit (F1, or a tuned one)"
[ -f "$PILOT_RESULT" ] || die "no pilot result at $PILOT_RESULT: run the pilot on this system first"
require_clean_tree
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
# an earlier run that stopped before E7.sha256 left only generated files: clear exactly those
rm -rf $S/corpora $S/qfull $S/qpool $S/questions $S/prompt_size.json $S/prompt_inputs.json $X/caps_r4.json
mkdir -p $S/logs $IN
git rev-parse HEAD > $X/E7.commit
echo "$SYSTEM_LABEL" > $X/E7.system
$EX check-listing --expected $IN/listing_E7.json --write-if-absent

build() {  # build <id>: corpus (G1 and identity asserted), the full question pool, then 4 per family
  id=$1; n=$(sheets_of "$id"); seed=$($EX test-seed --sheets "$n")
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$n" --seed "$seed" --check --no-neo4j \
    --out "$S/corpora/$id" > "$S/logs/corpus_$id.json" || die "corpus $id failed"
  $EX check-ingest --ingest-json "$S/corpora/$id/ingest.json" --corpus-id "$id" || die "corpus $id failed its gates"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$id" --ingest-json "$S/corpora/$id/ingest.json" \
    --seed 41 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 1 \
    --sample-seed 20261101 --out "$S/qfull/$id" --pool-out "$S/qpool/$id" || die "questions $id failed"
  $P -m plantgraph.qa.questions.per_family --in "$S/qfull/$id/questions.jsonl" \
    --splits "$S/qfull/$id/splits.json" --only-splits dev-old,dev-new,held-out --n 4 --seed 20261101 \
    --out "$S/questions/$id" || die "subsample $id failed"
}
for id in H1g2 H3g2 H10g2 H30g2; do build $id; done

# the two corpus-dependent prompt inputs, and the exact ContextRAG prompt size (reference arm, deferred)
args=; for id in H1g2 H3g2 H10g2 H30g2; do args="$args $id=$S/corpora/$id/ingest.json"; done
$EX corpus-prompt-hashes $args --out $S/prompt_inputs.json
$P -m plantgraph.qa.exp0001 prompt-size $args --json $S/prompt_size.json > /dev/null
$EX make-caps --stage r4 --pilot-result "$PILOT_RESULT" --ladder-questions $S/questions --out $X/caps_r4.json \
  || die "computing the R4 caps failed"

sha256sum $X/E7.commit $X/E7.system $IN/* $S/corpora/*/ingest.json $S/questions/*/questions.jsonl \
  $S/prompt_inputs.json $X/caps_r4.json "$PILOT_RESULT" \
  docs/private/30-experiments/EXP-0007-v2-remeasurement-plan.md docs/private/20-decisions/ADR-0060-*.md > $X/E7.sha256
echo "E7 = $(cat $X/E7.commit) (system: $SYSTEM_LABEL)"
cat $S/qfull/*/availability.json | head -60   # per-family n actually available (counts only)
