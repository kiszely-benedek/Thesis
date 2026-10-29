#!/bin/sh
# R5 data: the sealed v2 corpora H100g2, H1000g2 and the duplication points H100g2d0, H100g2d50, their
# questions and caps, for the SAME frozen system as R4 (V2T-A, E7; plan section 7). FREE: no paid call,
# no Neo4j. Run ONCE, after R4 finished. Writes T7.sha256 last and never overwrites it.
# The coder and the architect never open the generated questions; only counts (availability.json) are read.
#   sh data/runs/exp0007/make_test_set.sh
# The question draw is the EXP-0002 recipe on the full candidate enumeration (no sampling); on H1000g2
# it can take about 1.5 hours. Every part is a `step`: a stopped run is simply started again and
# continues after the last finished step (the generated files of an unfinished step are redone).
# The caps use the validation runs' measured costs and R4's measured H30g2 costs (floor).
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh
S=$X/sealed
V7_RUNS=${V7_RUNS:-$X/tune/final/runs}
[ ! -e $X/T7.sha256 ] || die "T7.sha256 exists; never overwrite it"
require_v2t_freeze
[ -s $X/ladder/runs/E7-CYP-H30g2/answers.jsonl ] && [ -s $X/ladder/runs/E7-AG-H30g2/answers.jsonl ] \
  || die "run R4 first: the R5 caps use its measured H30g2 cost"
[ -d "$V7_RUNS" ] || die "no validation runs at $V7_RUNS: the caps are computed from their measured costs"
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
init_stage; mkdir -p $S/logs

build_corpus() {  # build_corpus <id>: the corpus (G1 and identity asserted)
  bc_id=$1; bc_n=$(sealed_sheets "$bc_id"); bc_seed=$($EX test-seed --sheets "$bc_n")
  echo "=== $(date +%T) corpus $bc_id"
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$bc_n" --seed "$bc_seed" $(sealed_dup_args "$bc_id") \
    --check --no-neo4j --out "$S/corpora/$bc_id" > "$S/logs/corpus_$bc_id.json" || die "corpus $bc_id failed"
  $EX check-ingest --ingest-json "$S/corpora/$bc_id/ingest.json" --corpus-id "$bc_id" || die "corpus $bc_id failed its gates"
}

build_questions() {  # build_questions <id>: the EXP-0002 question recipe
  bq_id=$1
  echo "=== $(date +%T) questions $bq_id"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$bq_id" --ingest-json "$S/corpora/$bq_id/ingest.json" \
    --seed 31 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 10 \
    --sample-seed 20261031 --out "$S/questions/$bq_id" --pool-out "$S/qpool/$bq_id" || die "questions $bq_id failed"
}

for mk_c in $SEALED_IDS; do
  step corpus_$mk_c build_corpus $mk_c
  step questions_$mk_c build_questions $mk_c
done
# the concurrency-1 control: two per family from H1000g2
step questions_c1 $P -m plantgraph.qa.questions.per_family --in $S/questions/H1000g2/questions.jsonl \
  --splits $S/questions/H1000g2/splits.json --only-splits dev-old,dev-new,held-out \
  --n 2 --seed 20261031 --out $S/questions_c1/H1000g2

mk_args=; for mk_c in $SEALED_IDS; do mk_args="$mk_args $mk_c=$S/corpora/$mk_c/ingest.json"; done
step prompt_hashes $EX corpus-prompt-hashes $mk_args --out $S/prompt_inputs.json
# ContextRAG prompt size: the free proof that H100g2 / H1000g2 do not fit the window (reference arm deferred)
prompt_size() { $P -m plantgraph.qa.exp0001 prompt-size $mk_args --json $S/prompt_size.json > /dev/null; }
step prompt_size prompt_size
make_caps() {  # not shown to anyone yet, so a file left by a stopped run may be replaced
  rm -f $X/caps_r5.json
  $EX make-v2t-caps --stage r5 --v7-runs "$V7_RUNS" --sealed-questions $S/questions \
    --c1-questions $S/questions_c1 --r4-runs $X/ladder/runs --out $X/caps_r5.json \
    || die "computing the R5 caps failed"
}
step caps make_caps

sha256sum $X/E7.commit $S/corpora/*/ingest.json $S/questions/*/* $S/questions_c1/H1000g2/questions.jsonl \
  $S/prompt_inputs.json $X/caps_r5.json > $X/T7.sha256
cat $S/questions/*/availability.json | head -80   # per-family n actually drawn (counts only)
