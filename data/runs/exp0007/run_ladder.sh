#!/bin/sh
# R4: the ladder H1g2..H30g2 on the tuned system V2T-A (plan section 6; ADR-0054 applied by ADR-0060;
# ADR-0061 setting A: Cypher `cypher_rag_lines` with a 30 s query timeout, agent `graph_agent_lines`,
# 120 s per question, Cypher store profile `plant_lines`). PAID.
# ContextRAG, the reference arm (EXP-0001's ctx-high: the whole plant in the prompt, Luna at high
# effort), runs only with --with-ctx-small, and only on H1g2, H3g2 and H10g2: H30g2 is too dear, and
# from about 56 sheets a v2 plant no longer fits the window (plan R3). Its caps are in the cap file.
# Do NOT run pytest while this runs. One corpus in Neo4j at a time, in the database E7_NEO4J_DATABASE.
#   sh data/runs/exp0007/run_ladder.sh                  FREE: checks the freeze, shows the caps
#   sh data/runs/exp0007/run_ladder.sh --allow-paid-calls --cap-file data/runs/exp0007/caps_r4.json --cap-sha256 <hash>
#   ... --with-ctx-small     also the ContextRAG reference arm on H1g2, H3g2, H10g2 (2-question smoke first)
# Refuses without the E7 freeze file, or when a V2T system file, an input, a question set or the cap
# file differs from E7. The tree need not be clean (a rerun after a stop has partial results in it).
# A rerun skips finished steps; a run stopped at its cap resumes under the same id only with a higher cap.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh
WITH_CTX=no; REST=
while [ $# -gt 0 ]; do  # --with-ctx-small is ours; the rest is lib.sh's paid options
  case $1 in
    --with-ctx-small) WITH_CTX=yes ;;
    *) REST="$REST $1" ;;
  esac
  shift
done
parse_paid_args $REST
S=$X/ladder; CACHE=$S/cache_e7.sqlite; EXPERIMENT=EXP-0007
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$S/corpora; QROOT=$S/questions
LADDER="H1g2 H3g2 H10g2 H30g2"
CTX_LADDER="H1g2 H3g2 H10g2"
require_v2t_freeze
DEADLINE_S=$(setting_a_deadline)
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
check_listing "$(listing_file)"
init_stage; mkdir -p $S/cascade_report $S/tune_reports $S/report
cat $X/caps_r4.json
echo "ContextRAG small ladder: $WITH_CTX (--with-ctx-small)"
if [ "$ALLOW_PAID" != yes ]; then echo "checked only: nothing was paid. sha256 $(sha256sum $X/caps_r4.json | cut -d' ' -f1)"; exit 0; fi
require_paid
[ "$CAP_FILE" = $X/caps_r4.json ] || die "expected --cap-file $X/caps_r4.json (hashed into E7.sha256), found $CAP_FILE"
use_database

load_ladder() {  # this corpus alone in the database, in the plant_lines profile V2T-A reads
  ll_c=$1; ll_n=$(sheets_of "$ll_c")
  load_corpus "$ll_c" "$ll_n" "$($EX test-seed --sheets "$ll_n")" plant_lines
}

cypher_tier() {
  for lad_c in $LADDER; do
    step load_$lad_c load_ladder $lad_c
    if [ "$lad_c" = H1g2 ]; then
      step cypher_H1g2_smoke v2t_run CYP-A E7-CYP-H1g2-SMOKE H1g2 smoke $DEADLINE_S $S/questions_smoke
    fi
    step cypher_$lad_c v2t_run CYP-A E7-CYP-$lad_c $lad_c full $DEADLINE_S
    step replay_cyp_$lad_c v2t_replay CYP-A E7-CYP-$lad_c $lad_c $DEADLINE_S
  done
}

agent_tier() {  # reads the in-memory graph; the database is not used
  step agent_H1g2_smoke v2t_run AG E7-AG-H1g2-SMOKE H1g2 smoke $DEADLINE_S $S/questions_smoke
  for lad_c in $LADDER; do
    step agent_$lad_c v2t_run AG E7-AG-$lad_c $lad_c full $DEADLINE_S
    step replay_ag_$lad_c v2t_replay AG E7-AG-$lad_c $lad_c $DEADLINE_S
  done
}

ctx_tier() {  # no database: the prompt is the whole plant, read from the ingest record
  step ctx_H1g2_smoke v2t_run CTX E7-CTXH-H1g2-SMOKE H1g2 smoke $CTX_DEADLINE_S $S/questions_smoke
  for ct_c in $CTX_LADDER; do
    step ctx_$ct_c v2t_run CTX E7-CTXH-$ct_c $ct_c full $CTX_DEADLINE_S
    step replay_ctx_$ct_c v2t_replay CTX E7-CTXH-$ct_c $ct_c $CTX_DEADLINE_S
  done
}

# Free. Setting A (limits.SETTING_A): `cascade report` is the per-size table of the two tiers and of
# cascade_v4_iso / cascade_v4; `tune-report` adds, per size, the per-family counts, the oracle and the
# Cypher accept rule, and refuses runs that do not match the setting.
report() {
  POL=src/plantgraph/qa/cascade/policies_v2t
  set --
  for rep_c in $LADDER; do
    set -- "$@" --corpus $rep_c --run $rep_c:cypher-v2t=$S/runs/E7-CYP-$rep_c --run $rep_c:agent-v2t=$S/runs/E7-AG-$rep_c
  done
  $P -m plantgraph.qa.cascade report --no-baselines --setting A --policy $POL/cascade_v4_iso.json \
    --policy $POL/cascade_v4.json --policy $POL/references/always_g_v2t.json \
    --policy $POL/references/always_c_v2t.json --questions-root $QROOT --corpora-root $S/corpora \
    --out $S/cascade_report "$@" > $S/logs/cascade_report.stdout.txt 2>&1 \
    || die "the cascade report failed, see $S/logs/cascade_report.stdout.txt"
  for rep_c in $LADDER; do
    $P -m plantgraph.qa.cascade tune-report --corpus $rep_c --setting A --questions-root $QROOT \
      --corpora-root $S/corpora --run cypher-v2t=$S/runs/E7-CYP-$rep_c --run agent-v2t=$S/runs/E7-AG-$rep_c \
      --out $S/tune_reports/$rep_c > $S/logs/tune_report_$rep_c.txt 2>&1 \
      || die "the tune report for $rep_c failed, see $S/logs/tune_report_$rep_c.txt"
  done
  # the ladder report of EXP-0001's shape: X1-X5 compare ContextRAG with the cascade where both ran
  # the arm policies live in inputs/, not under $S (the report's default looks in $S/inputs)
  $P -m plantgraph.qa.exp0001 report --edition v2 --system v2t --root $S --out $S/report \
    --ctx-high-policy $IN/always_ctx_high.json --ctx-low-policy $IN/always_ctx_low.json \
    --footnote "$CTX_FOOTNOTE" > $S/logs/report.stdout.txt 2>&1 \
    || die "the ladder report failed, see $S/logs/report.stdout.txt"
}

CTX_FOOTNOTE="ContextRAG was run on H1g2, H3g2 and H10g2 only and is not run at H30g2 and above: the \
cost of a full-plant prompt there is out of proportion, and from about 56 sheets a v2 plant no longer \
fits the model's prompt window (EXP-0007 R3). Rows marked absent are runs that were not made."

step make_smoke $EX head-questions --source $QROOT/H1g2/questions.jsonl --out $S/questions_smoke/H1g2/questions.jsonl
cypher_tier
step restore_d1000_a restore_d1000
agent_tier
if [ "$WITH_CTX" = yes ]; then ctx_tier; fi
require_identical_replays
report  # free and quick: rerun every time, so a later --with-ctx-small run is included
echo "=== replay checks (all must read 'identical')"; head -v $S/replays/*/replay_check.txt
echo "=== $(date +%T) done: $S/cascade_report/report.md ; $S/tune_reports/<corpus>/tune_report.md ; $S/report/report.md"
