#!/bin/sh
# R5 data: the sealed v2 corpora H100g2, H1000g2 and the duplication points H100g2d0, H100g2d50, their
# questions and caps, at the SAME frozen system as R4 (E7; plan section 7). FREE: no paid call, no Neo4j.
# Run ONCE, after R4 finished (its measured H30g2 cost sets the caps). Writes T7.sha256; never overwrites.
# The coder and the architect never open the generated questions; only counts (availability.json) are read.
#   PILOT_RESULT=<file> sh data/runs/exp0007/make_test_set.sh
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
S=$X/sealed
PILOT_RESULT=${PILOT_RESULT:-$X/pilot/pilot_result.json}
[ ! -e $X/T7.sha256 ] || die "T7.sha256 exists; never overwrite it"
require_clean_tree; require_freeze
[ -d $X/ladder/runs/E7-CYP-H30g2 ] && [ -d $X/ladder/runs/E7-AG-H30g2 ] || die "run R4 first: the R5 caps use its measured H30g2 cost"
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
rm -rf $S/corpora $S/qfull $S/qpool $S/questions $S/questions_c1 $S/prompt_size.json $S/prompt_inputs.json $X/caps_r5.json
mkdir -p $S/logs

build() {  # build <id>: corpus (G1 and identity asserted), then the EXP-0002 question recipe
  id=$1; n=$(sealed_sheets "$id"); seed=$($EX test-seed --sheets "$n")
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$n" --seed "$seed" $(sealed_dup_args "$id") \
    --check --no-neo4j --out "$S/corpora/$id" > "$S/logs/corpus_$id.json" || die "corpus $id failed"
  $EX check-ingest --ingest-json "$S/corpora/$id/ingest.json" --corpus-id "$id" || die "corpus $id failed its gates"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$id" --ingest-json "$S/corpora/$id/ingest.json" \
    --seed 31 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 10 \
    --sample-seed 20261031 --out "$S/questions/$id" --pool-out "$S/qpool/$id" || die "questions $id failed"
}
for id in $SEALED_IDS; do build $id; done
# the concurrency-1 control: two per family from H1000g2
$P -m plantgraph.qa.questions.per_family --in $S/questions/H1000g2/questions.jsonl \
  --splits $S/questions/H1000g2/splits.json --only-splits dev-old,dev-new,held-out \
  --n 2 --seed 20261031 --out $S/questions_c1/H1000g2 || die "C1 subsample failed"

args=; for id in $SEALED_IDS; do args="$args $id=$S/corpora/$id/ingest.json"; done
$EX corpus-prompt-hashes $args --out $S/prompt_inputs.json
# ContextRAG prompt size: the free proof that H100g2 / H1000g2 do not fit the window (reference arm deferred)
$P -m plantgraph.qa.exp0001 prompt-size $args --json $S/prompt_size.json > /dev/null
$EX make-caps --stage r5 --pilot-result "$PILOT_RESULT" --runs-root data/runs --sealed-questions $S/questions \
  --c1-questions $S/questions_c1 --r4-runs $X/ladder/runs --out $X/caps_r5.json || die "computing the R5 caps failed"

sha256sum $X/E7.commit $S/corpora/*/ingest.json $S/questions/*/* $S/questions_c1/H1000g2/questions.jsonl \
  $S/prompt_inputs.json $X/caps_r5.json > $X/T7.sha256
cat $S/questions/*/availability.json | head -80   # per-family n actually drawn (counts only)
