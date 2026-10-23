#!/bin/sh
# Test corpora and questions at commit T (ADR-0053; design section 5).
set -eu
S=data/runs/sealed; P=.venv/Scripts/python
ALLOWED='^(src/plantgraph/qa/questions/|src/plantgraph/qa/harness/(family_meta|need_gold)\.py$|src/plantgraph/qa/models\.py$)'
die() { echo "ERROR: $*" >&2; exit 1; }
[ ! -e $S/T.commit ] || die "T already exists; never overwrite it"
[ -z "$(git status --porcelain)" ] || die "commit first: the working tree is not clean"
sha256sum -c --quiet $S/F1.sha256 || die "a frozen input changed since F1"
bad=$(git diff --name-only "$(cat $S/F1.commit)" HEAD -- src | grep -v -E "$ALLOWED" || true)
[ -z "$bad" ] || die "frozen paths changed since F1: $bad"
git diff "$(cat $S/F1.commit)" HEAD -- src/plantgraph/qa/models.py > $S/logs/models_py_diff.txt
git rev-parse HEAD > $S/T.commit
for spec in "H100 100 2" "H1000 1000 0"; do
  set -- $spec
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$2" --seed "$3" --corpus-id "$1" \
    --check --no-neo4j --out "$S/corpora/$1" > "$S/logs/corpus_$1.json" || die "corpus $1 failed"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$1" --ingest-json "$S/corpora/$1/ingest.json" \
    --seed 31 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 10 \
    --sample-seed 20261031 --out "$S/questions/$1" --pool-out "$S/qpool/$1" || die "questions $1 failed"
done
$P -m plantgraph.qa.questions.per_family --in $S/questions/H1000/questions.jsonl \
  --splits $S/questions/H1000/splits.json --only-splits dev-old,dev-new,held-out \
  --n 2 --seed 20261031 --out $S/questions_c1/H1000
sha256sum $S/T.commit $S/corpora/*/ingest.json $S/questions/*/* $S/questions_c1/H1000/questions.jsonl > $S/T.sha256
cat $S/questions/*/availability.json | head -80   # per-family n actually drawn
