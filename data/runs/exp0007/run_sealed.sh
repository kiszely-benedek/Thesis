#!/bin/sh
# R5: the sealed test on v2 for the tuned system V2T-A (plan section 7; ADR-0053 applied by ADR-0060;
# ADR-0061 setting A: Cypher `cypher_rag_lines` with a 30 s query timeout on the `plant_lines` store
# profile, agent `graph_agent_lines`, 120 s per question). PAID.
# Corpora: H100g2, H1000g2, and the duplication points H100g2d0 / H100g2d50. ContextRAG is not run.
# Do NOT run pytest while this runs. One corpus in Neo4j at a time, in the database E7_NEO4J_DATABASE.
#   sh data/runs/exp0007/run_sealed.sh                  FREE: checks the freeze, shows the caps
#   sh data/runs/exp0007/run_sealed.sh --allow-paid-calls --cap-file data/runs/exp0007/caps_r5.json --cap-sha256 <hash>
#   ... --with-f1-baseline   OPTIONAL: also runs the frozen F1 tiers on H100g2 and H1000g2 (plain `plant`
#                            store profile, cascade_v3 report). Default off. Its caps are in the same
#                            cap file (runs S7F1-*), so the flag changes nothing that was hashed.
# Refuses without the E7 freeze file and T7.sha256, or when a V2T system file, an input, a question set
# or the cap file differs from E7 / T7. The tree need not be clean (a rerun has partial results in it).
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh
WITH_F1=no; REST=
while [ $# -gt 0 ]; do  # --with-f1-baseline is ours; the rest is lib.sh's paid options
  case $1 in
    --with-f1-baseline) WITH_F1=yes ;;
    *) REST="$REST $1" ;;
  esac
  shift
done
parse_paid_args $REST
S=$X/sealed; CACHE=$S/cache_s7.sqlite; EXPERIMENT=EXP-0007-SEALED
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$S/corpora; QROOT=$S/questions
F1_CORPORA="H100g2 H1000g2"
require_v2t_freeze
[ -f $X/T7.sha256 ] || die "no T7.sha256: run make_test_set.sh first"
sha256sum -c --quiet $X/T7.sha256 || die "a test input changed since it was generated (T7.sha256)"
DEADLINE_S=$(setting_a_deadline)
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"
check_listing "$(listing_file)"
init_stage; mkdir -p $S/report $S/report_duplication $S/report_f1_baseline $S/tune_reports
cat $X/caps_r5.json
echo "F1 baseline: $WITH_F1 (--with-f1-baseline)"
if [ "$ALLOW_PAID" != yes ]; then echo "checked only: nothing was paid. sha256 $(sha256sum $X/caps_r5.json | cut -d' ' -f1)"; exit 0; fi
require_paid
[ "$CAP_FILE" = $X/caps_r5.json ] || die "expected --cap-file $X/caps_r5.json (hashed into T7.sha256), found $CAP_FILE"
use_database

load_sealed() {  # load_sealed <corpus> <plant_lines|plant>: this corpus alone in the database
  ls_c=$1; ls_n=$(sealed_sheets "$ls_c")
  load_corpus "$ls_c" "$ls_n" "$($EX test-seed --sheets "$ls_n")" "$2" $(sealed_dup_args "$ls_c")
}

is_f1_corpus() { case " $F1_CORPORA " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

cypher_tier() {  # per corpus: V2T-A on plant_lines; then, with the baseline flag, F1 on the plain plant
  for sc_c in $SEALED_IDS; do
    step load_$sc_c load_sealed $sc_c plant_lines
    if [ "$sc_c" = H100g2 ]; then
      step cypher_H100g2_smoke v2t_run CYP-A S7-CYP-H100g2-SMOKE H100g2 smoke $DEADLINE_S $S/questions_smoke
    fi
    step cypher_$sc_c v2t_run CYP-A S7-CYP-$sc_c $sc_c full $DEADLINE_S
    step replay_cyp_$sc_c v2t_replay CYP-A S7-CYP-$sc_c $sc_c $DEADLINE_S
    if [ "$WITH_F1" = yes ] && is_f1_corpus $sc_c; then
      step load_plain_$sc_c load_sealed $sc_c plant
      step cypher_f1_$sc_c v2t_run F1-CYP S7F1-CYP-$sc_c $sc_c full 120
      step replay_cyp_f1_$sc_c v2t_replay F1-CYP S7F1-CYP-$sc_c $sc_c 120
    fi
  done
}

agent_tier() {  # H1000g2-C1 is the concurrency-1 control; its own cache stops it reusing the main run's answers
  step agent_H100g2_smoke v2t_run AG S7-AG-H100g2-SMOKE H100g2 smoke $DEADLINE_S $S/questions_smoke
  for sa_c in $SEALED_IDS; do
    step agent_$sa_c v2t_run AG S7-AG-$sa_c $sa_c full $DEADLINE_S
    step replay_ag_$sa_c v2t_replay AG S7-AG-$sa_c $sa_c $DEADLINE_S
  done
  step agent_C1 v2t_run AG S7-AG-H1000g2-C1 H1000g2 full $DEADLINE_S $S/questions_c1 1 $S/cache_s7_c1.sqlite
  step replay_agent_C1 v2t_replay AG S7-AG-H1000g2-C1 H1000g2 $DEADLINE_S $S/questions_c1 $S/cache_s7_c1.sqlite
  if [ "$WITH_F1" = yes ]; then
    for sa_c in $F1_CORPORA; do
      step agent_f1_$sa_c v2t_run F1-AG S7F1-AG-$sa_c $sa_c full 120
      step replay_ag_f1_$sa_c v2t_replay F1-AG S7F1-AG-$sa_c $sa_c 120
    done
  fi
}

# Free. The two headline corpora give the ADR-0053 claims for cascade_v4_iso (the primary), with
# cascade_v4 alongside (also K2's reference: a policy routed by need label has no random-escalation
# arm); setting A (limits.SETTING_A) sets the cutoff. The duplication points are a descriptive table.
# `tune-report` per corpus adds the per-family counts and refuses runs that do not match the setting.
report() {
  POL=src/plantgraph/qa/cascade/policies_v2t
  $P -m plantgraph.qa.cascade report --sealed-claims --claims v2t --setting A \
    --policy $POL/cascade_v4_iso.json --policy $POL/cascade_v4.json \
    --policy $POL/references/always_g_v2t.json --policy $POL/references/always_c_v2t.json \
    --corpus H100g2 --corpus H1000g2 --questions-root $QROOT --corpora-root $S/corpora --out $S/report \
    --run H100g2:cypher-v2t=$S/runs/S7-CYP-H100g2 --run H100g2:agent-v2t=$S/runs/S7-AG-H100g2 \
    --run H1000g2:cypher-v2t=$S/runs/S7-CYP-H1000g2 --run H1000g2:agent-v2t=$S/runs/S7-AG-H1000g2 \
    > $S/logs/report.stdout.txt || die "the sealed report failed, see $S/logs/report.stdout.txt"
  $P -m plantgraph.qa.exp0001 duplication-report --system v2t --root $S --out $S/report_duplication \
    > $S/logs/report_duplication.stdout.txt || die "the duplication report failed"
  for rp_c in $SEALED_IDS; do
    $P -m plantgraph.qa.cascade tune-report --corpus $rp_c --setting A --questions-root $QROOT \
      --corpora-root $S/corpora --run cypher-v2t=$S/runs/S7-CYP-$rp_c --run agent-v2t=$S/runs/S7-AG-$rp_c \
      --out $S/tune_reports/$rp_c > $S/logs/tune_report_$rp_c.txt 2>&1 \
      || die "the tune report for $rp_c failed, see $S/logs/tune_report_$rp_c.txt"
  done
}

report_f1_baseline() {  # F1's own sealed claims (ADR-0053, cascade_v3) on the same two corpora and questions
  POL=src/plantgraph/qa/cascade/policies
  $P -m plantgraph.qa.cascade report --sealed-claims --claims f1 --cutoff-s 120 \
    --policy $POL/cascade_v3.json --policy $POL/always_g_luna.json --policy $POL/always_c_luna.json \
    --policy $POL/cascade_v3_iso.json --corpus H100g2 --corpus H1000g2 --questions-root $QROOT \
    --corpora-root $S/corpora --out $S/report_f1_baseline \
    --run H100g2:cypher-luna=$S/runs/S7F1-CYP-H100g2 --run H100g2:agent-luna=$S/runs/S7F1-AG-H100g2 \
    --run H1000g2:cypher-luna=$S/runs/S7F1-CYP-H1000g2 --run H1000g2:agent-luna=$S/runs/S7F1-AG-H1000g2 \
    > $S/logs/report_f1_baseline.stdout.txt || die "the F1 baseline report failed"
}

step make_smoke $EX head-questions --source $QROOT/H100g2/questions.jsonl --out $S/questions_smoke/H100g2/questions.jsonl
cypher_tier
step restore_d1000_a restore_d1000
agent_tier
require_identical_replays
step report report
if [ "$WITH_F1" = yes ]; then step report_f1_baseline report_f1_baseline; fi
echo "=== replay checks (all must read 'identical')"; head -v $S/replays/*/replay_check.txt
echo "=== $(date +%T) done: $S/report/report.md ; $S/report_duplication/duplication.md ; $S/tune_reports/<corpus>/tune_report.md"
