#!/bin/sh
# EXP-0001 ladder corpora, questions and EX01 import at commit E (ADR-0054; design 9.1). Free: no paid call, no Neo4j.
# Run ONCE, right after the user's commit E (clean tree). It writes E.commit and E.sha256 (the freeze).
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0001/lib.sh
[ ! -e $S/E.sha256 ] || die "E.sha256 exists; never overwrite it"
[ -z "$(git status --porcelain)" ] || die "commit first: the working tree is not clean"
# an earlier run that stopped before E.sha256 left only generated files: clear exactly those
rm -rf $S/scan $S/corpora $S/qfull $S/qpool $S/questions $S/questions_c $S/H1.seed
mkdir -p $S/scan $S/logs
git rev-parse HEAD > $S/E.commit
[ -e $IN/listing_E.json ] || fetch_listing $IN/listing_E.json || die "could not read OpenRouter's listing for Luna"

# H1: the first seed whose one-unit headline corpus is exactly one sheet (selection on sheet count only)
for seed in $(seq 100 399); do
  $P -m plantgraph.ingest synthetic --headline --target-sheets 1 --seed $seed --corpus-id H1 --check \
    --no-neo4j --out $S/scan/H1-$seed > $S/scan/H1-$seed.log 2>&1 || die "scan seed $seed failed"
  if [ "$(n_sheets $S/scan/H1-$seed/ingest.json)" = 1 ]; then echo $seed > $S/H1.seed; break; fi
done
[ -e $S/H1.seed ] || die "no one-sheet unit in seeds 100-399: stop and ask (fallback: two-sheet H1, seed 100)"

build() {  # build <id> <target-sheets> <seed>: corpus, full question pool, then 4 per family
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$2" --seed "$3" --corpus-id "$1" --check \
    --no-neo4j --out "$S/corpora/$1" > "$S/logs/corpus_$1.json" || die "corpus $1 failed"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$1" --ingest-json "$S/corpora/$1/ingest.json" \
    --seed 41 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 1 \
    --sample-seed 20261101 --out "$S/qfull/$1" --pool-out "$S/qpool/$1" || die "questions $1 failed"
  $P -m plantgraph.qa.questions.per_family --in "$S/qfull/$1/questions.jsonl" \
    --splits "$S/qfull/$1/splits.json" --only-splits dev-old,dev-new,held-out --n 4 --seed 20261101 \
    --out "$S/questions/$1" || die "subsample $1 failed"
}
build H1 1 "$(cat $S/H1.seed)"; build H3 3 3; build H10 10 3; build H30 30 3

# stage C's 24 questions (one per family) come from the sealed H100 pool; no corpus is built
$P -m plantgraph.qa.questions.per_family --in $SEALED/questions/H100/questions.jsonl \
  --splits $SEALED/questions/H100/splits.json --only-splits dev-old,dev-new,held-out --n 1 \
  --seed 20261101 --out $S/questions_c/H100 || die "stage C questions failed"

# EX01 as imported; the plant profile is needed because cypher_rag_plant refuses the default 'both'
$P -m plantgraph.ingest proteus data/external/C01V04-VER.EX01.xml --corpus-id EX01 --no-neo4j \
  --store-profile plant --out $S/corpora/EX01 > $S/logs/corpus_EX01.json || die "EX01 import failed"

sha256sum $S/E.commit $S/H1.seed $IN/* $S/corpora/*/ingest.json $S/questions/*/questions.jsonl \
  $S/questions_c/H100/questions.jsonl data/external/chatpid_ex01_qa.jsonl \
  docs/private/40-design/exp0001-single-sheet.md docs/private/20-decisions/ADR-0054-*.md > $S/E.sha256
echo "E = $(cat $S/E.commit); H1 seed $(cat $S/H1.seed)"
cat $S/qfull/*/availability.json | head -60   # per-family n actually available
