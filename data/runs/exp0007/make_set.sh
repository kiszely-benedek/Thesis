#!/bin/sh
# R4 data: the v2 ladder corpora H1g2 H3g2 H10g2 H30g2, their questions and caps, for the tuned
# system V2T-A (plan section 6; ADR-0060 decision 3B, ADR-0061). FREE: no paid call, no Neo4j.
# Run ONCE, right after the user's commit of the system to measure. That commit is the freeze E7:
# this script writes E7.commit, E7.system and E7.sha256 (which hashes every tracked V2T system file
# and the inputs), and refuses to run again.
#   sh data/runs/exp0007/make_set.sh --system-label V2T-A
# Needs: the validation step done (tune/final/DONE), tune_guards.sh --with-neo4j passed at this very
# commit (the F1 replays and the line-view gate), a clean tree. The caps are computed from the
# validation runs' measured costs (V7_RUNS, default tune/final/runs).
# Test seeds come from TEST_SEEDS_V2 only (asserted); no test corpus exists before this script.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh
parse_paid_args "$@"
S=$X/ladder
V7_RUNS=${V7_RUNS:-$X/tune/final/runs}
[ ! -e $X/E7.sha256 ] || die "E7.sha256 exists; never overwrite it"
[ "$SYSTEM_LABEL" = "$V2T_LABEL" ] || die "pass --system-label $V2T_LABEL: R4 and R5 measure that system (found '$SYSTEM_LABEL')"
[ -f $X/tune/final/DONE ] || die "the validation step is not done: $X/tune/final/DONE is missing"
[ -d "$V7_RUNS" ] || die "no validation runs at $V7_RUNS: the caps are computed from their measured costs"
require_clean_tree
require_tune_guards_passed
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
# an earlier run that stopped before E7.sha256 left only generated files: clear exactly those
rm -rf $S/corpora $S/qfull $S/qpool $S/questions $S/prompt_size.json $S/prompt_inputs.json $X/caps_r4.json
mkdir -p $S/logs $IN
git rev-parse HEAD > $X/E7.commit
echo "$SYSTEM_LABEL" > $X/E7.system
$EX check-listing --expected $IN/listing_E7.json --write-if-absent

build() {  # build <id>: corpus (G1 and identity asserted), the full question pool, then 4 per family
  bd_id=$1; bd_n=$(sheets_of "$bd_id"); bd_seed=$($EX test-seed --sheets "$bd_n")
  $P -m plantgraph.ingest synthetic --headline-v2 --target-sheets "$bd_n" --seed "$bd_seed" --check --no-neo4j \
    --out "$S/corpora/$bd_id" > "$S/logs/corpus_$bd_id.json" || die "corpus $bd_id failed"
  $EX check-ingest --ingest-json "$S/corpora/$bd_id/ingest.json" --corpus-id "$bd_id" || die "corpus $bd_id failed its gates"
  $P -m plantgraph.qa.questions.sealed_set --corpus-id "$bd_id" --ingest-json "$S/corpora/$bd_id/ingest.json" \
    --seed 41 --n-per-bin 500 --n-unanswerable 100 --n-per-family 20 --n-per-wording 1 \
    --sample-seed 20261101 --out "$S/qfull/$bd_id" --pool-out "$S/qpool/$bd_id" || die "questions $bd_id failed"
  $P -m plantgraph.qa.questions.per_family --in "$S/qfull/$bd_id/questions.jsonl" \
    --splits "$S/qfull/$bd_id/splits.json" --only-splits dev-old,dev-new,held-out --n 4 --seed 20261101 \
    --out "$S/questions/$bd_id" || die "subsample $bd_id failed"
}
for set_c in H1g2 H3g2 H10g2 H30g2; do build $set_c; done

# the two corpus-dependent prompt inputs, and the exact ContextRAG prompt size (it prices the optional
# ContextRAG arm on H1g2, H3g2 and H10g2)
set_args=; for set_c in H1g2 H3g2 H10g2 H30g2; do set_args="$set_args $set_c=$S/corpora/$set_c/ingest.json"; done
$EX corpus-prompt-hashes $set_args --out $S/prompt_inputs.json
$P -m plantgraph.qa.exp0001 prompt-size $set_args --json $S/prompt_size.json > /dev/null
$EX make-v2t-caps --stage r4 --v7-runs "$V7_RUNS" --ladder-questions $S/questions \
  --prompt-size $S/prompt_size.json --out $X/caps_r4.json \
  || die "computing the R4 caps failed"

# the plan note and ADR-0060 are not hashed: they are records, edited as the runs go on
{
  sha256sum $X/E7.commit $X/E7.system $IN/* $S/corpora/*/ingest.json $S/questions/*/questions.jsonl \
    $S/prompt_inputs.json $X/caps_r4.json
  v2t_system_hashes
} > $X/E7.sha256
echo "E7 = $(cat $X/E7.commit) (system: $SYSTEM_LABEL; $(v2t_system_hashes | wc -l) system files hashed)"
cat $S/qfull/*/availability.json | head -60   # per-family n actually available (counts only)
