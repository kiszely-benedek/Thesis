#!/bin/sh
# V2T tuning (ADR-0061, design qa-tuning-v2.md 7): up to three paid rounds on the tuning plant T, then
# the held-back validation plants V once. Setting A = Cypher timeout 30 s + 120 s per question;
# setting B = Cypher timeout 120 s + no deadline (900 s hang guard). Each round runs the agent tier
# once and the Cypher tier twice (A, B) on T, then `tune-report` for both settings.
#
#   sh data/runs/exp0007/tune.sh
#       FREE prepare: builds T (X100g2s211, seed 211), draws its dev questions (10 per family, seed
#       20261101), runs the free plant checks, writes + prints the caps and their sha256. With
#       E7_NEO4J_DATABASE set it also test-loads T as `plant_lines` and drops the database again.
#   sh data/runs/exp0007/tune.sh --round R --allow-paid-calls --cap-file data/runs/exp0007/tune/caps_tune.json --cap-sha256 <hash>
#       PAID round R (1..3): needs a clean tree, tune_guards.sh --with-neo4j passed at HEAD, a new commit
#       since round R-1, and E7_NEO4J_DATABASE (a temporary database, dropped when the script ends).
#   sh data/runs/exp0007/tune.sh --final-v
#       FREE prepare of the final step: builds V (X100g2s212, X1000g2s213), draws their questions, writes
#       + prints the caps. Seeds of V are refused without --final-v; test seeds 5000-5999 never.
#   sh data/runs/exp0007/tune.sh --final-v --allow-paid-calls --cap-file data/runs/exp0007/tune/final/caps_final.json --cap-sha256 <hash>
#       PAID, ONCE: the frozen V2T (both settings) and F1 on V; refuses to run again. The V2T system files
#       (tune_lib.sh V2T_FROZEN_FILES) and inputs/ must equal the last round's commit.
# Never touches the user's `neo4j` database. Question files are never reworded or hand-edited.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
ROUND=; FINAL_V=no; REST=
while [ $# -gt 0 ]; do  # --round and --final-v are ours; the rest is lib.sh's paid options
  case $1 in
    --round) ROUND=${2:-}; shift ;;
    --final-v) FINAL_V=yes ;;
    *) REST="$REST $1" ;;
  esac
  shift
done
parse_paid_args $REST
FINAL_FLAG=; [ "$FINAL_V" = no ] || FINAL_FLAG=--final-v
[ -z "$ROUND" ] || [ "$FINAL_V" = no ] || die "pass --round or --final-v, not both"
if [ "$FINAL_V" = yes ]; then S=$X/tune/final; CACHE=$S/cache_final.sqlite; else S=$X/tune; CACHE=$S/cache_tune.sqlite; fi
EXPERIMENT=EXP-0007-TUNE; CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$S/corpora; QROOT=$S/questions
T=X100g2s211; V1=X100g2s212; V2=X1000g2s213
LOADED_DB=; trap drop_temp_database EXIT
init_stage; mkdir -p $S/rounds

case "$ROUND" in ""|1|2|3) ;; *) die "expected --round 1, 2 or 3, found '$ROUND' (stop rule 1: at most 3 rounds)" ;; esac
$EX check-seeds --data-root data --exclude $X || die "seed hygiene failed"

# ---- free prepare ------------------------------------------------------------------------------

prepare_tuning() {
  step build_T build_plant $T
  step questions_T draw_questions $T $AG_CORPORA/$T/ingest.json
  step smoke_questions_T $EX head-questions --source $QROOT/$T/questions.jsonl --out $S/questions_smoke/$T/questions.jsonl
  step checks_T free_plant_checks $T
  if [ ! -f $S/caps_tune.json ]; then
    $EX make-tune-caps --stage tune --questions $QROOT/$T/questions.jsonl --out $S/caps_tune.json || die "computing the caps failed"
  else cat $S/caps_tune.json; fi
  echo "cap file $S/caps_tune.json  sha256 $(sha256sum $S/caps_tune.json | cut -d' ' -f1)"
  if [ -n "${E7_NEO4J_DATABASE:-}" ]; then
    use_database; LOADED_DB=$NEO4J_DATABASE
    load_lines $T 100 211 plant_lines
    echo "--- the plant_lines load of $T worked; the temporary database $LOADED_DB is dropped now"
  else echo "--- no E7_NEO4J_DATABASE: the plant_lines test load was skipped (a paid round needs it)"; fi
  echo "prepared only: nothing was paid. To run a round: --round 1 --allow-paid-calls --cap-file ... --cap-sha256 ..."
}

prepare_final() {
  [ -f $X/tune/rounds/r1/DONE ] || die "tune at least one round first: $X/tune/rounds/r1/DONE is missing"
  for fv in $V1 $V2; do
    step build_$fv build_plant $fv
    step questions_$fv draw_questions $fv $AG_CORPORA/$fv/ingest.json
    step checks_$fv free_plant_checks $fv
  done
  if [ ! -f $S/caps_final.json ]; then
    $EX make-tune-caps --stage final --questions $QROOT/$V1/questions.jsonl $QROOT/$V2/questions.jsonl \
      --out $S/caps_final.json || die "computing the caps failed"
  else cat $S/caps_final.json; fi
  echo "cap file $S/caps_final.json  sha256 $(sha256sum $S/caps_final.json | cut -d' ' -f1)"
  echo "prepared only: nothing was paid."
}

# ---- one paid round on T -----------------------------------------------------------------------

round_dir() { echo $S/rounds/r$1; }
run_of() { echo "T7R$ROUND-$1-$T"; }  # run id of one arm in this round

require_round_start() {
  [ -f $S/caps_tune.json ] || die "run the free prepare first: $S/caps_tune.json is missing"
  [ ! -f $S/STOP ] || die "the tuning stopped: $(cat $S/STOP)"
  [ ! -f $(round_dir $ROUND)/DONE ] || die "round $ROUND is already done: $(round_dir $ROUND)/DONE"
  if [ "$ROUND" -gt 1 ]; then
    prev=$(round_dir $((ROUND - 1)))
    [ -f $prev/DONE ] || die "round $((ROUND - 1)) is not done: run it first"
    [ "$(cat $prev/commit)" != "$(git rev-parse HEAD)" ] || die "round $ROUND needs a new commit: HEAD is the previous round's"
  fi
}

cypher_runs() {  # both Cypher arms on T, in the temporary database
  step load_T_r$ROUND load_lines $T 100 211 plant_lines
  if [ "$ROUND" = 1 ]; then
    step smoke_cyp tune_run CYP-A "T7S-CYP-A-$T" $T smoke $S/questions_smoke
  fi
  for round_arm in CYP-A CYP-B; do step run_${round_arm}_r$ROUND tune_run $round_arm "$(run_of $round_arm)" $T full $QROOT; done
}

agent_run() {
  if [ "$ROUND" = 1 ]; then step smoke_ag tune_run AG "T7S-AG-$T" $T smoke $S/questions_smoke; fi
  step run_AG_r$ROUND tune_run AG "$(run_of AG)" $T full $QROOT
}

report_round() {  # tune-report for both settings, against the previous round; then the stop-rule verdicts
  out=$(round_dir $ROUND)
  for rep_setting in A B; do
    prev_arg=
    [ "$ROUND" = 1 ] || prev_arg="--previous $(round_dir $((ROUND - 1)))/$rep_setting/tune_report.json"
    $P -m plantgraph.qa.cascade tune-report --corpus $T --setting $rep_setting --questions-root $QROOT \
      --corpora-root $AG_CORPORA --run cypher-v2t=$S/runs/$(run_of CYP-$rep_setting) \
      --run agent-v2t=$S/runs/$(run_of AG) $prev_arg --out $out/$rep_setting > $out/report_$rep_setting.txt \
      || die "tune-report for setting $rep_setting failed, see $out/report_$rep_setting.txt"
  done
  echo "=== round $ROUND: reports in $out/{A,B}/tune_report.md"
  grep -h "^Variant choice\|stop rule 3\|against the previous round" $out/report_A.txt $out/report_B.txt || true
}

verdicts() {  # stop rules 1 and 2; rule 3 (a family that lost 2) is only printed: reverting is the user's call
  out=$(round_dir $ROUND)
  git rev-parse HEAD > $out/commit
  if grep -h "families that lost" $out/report_A.txt $out/report_B.txt | grep -qv "none"; then
    echo "REVERT CANDIDATE (stop rule 3): a family lost 2 or more T questions: revert it unless a reason is traced"
  fi
  if [ "$ROUND" -gt 1 ] && [ "$(cat $out/report_A.txt $out/report_B.txt | grep -c 'fixed too few: stop rule 2')" = 2 ]; then
    echo "stop rule 2: round $ROUND fixed fewer than 3 T questions at both settings" > $S/STOP
  elif [ "$ROUND" = 3 ]; then echo "stop rule 1: three rounds done" > $S/STOP; fi
  if [ -f $S/STOP ]; then echo "VERDICT: STOP TUNING ($(cat $S/STOP)). Next: --final-v."
  else echo "VERDICT: continue: fix classes traced to T questions, commit, then round $((ROUND + 1))."; fi
  touch $out/DONE
}

paid_round() {
  require_paid; require_clean_tree; require_tune_guards_passed; require_round_start
  [ "$CAP_FILE" = $S/caps_tune.json ] || die "expected --cap-file $S/caps_tune.json, found $CAP_FILE"
  check_listing "$(listing_file)"
  use_database; LOADED_DB=$NEO4J_DATABASE
  mkdir -p $(round_dir $ROUND)
  cypher_runs
  agent_run
  report_round
  verdicts
}

# ---- the final step: V2T and F1 on V, once ----------------------------------------------------

require_final_start() {
  [ ! -f $S/DONE ] || die "the validation plants were already run: $S/DONE (V is run once, never again)"
  [ -f $S/caps_final.json ] || die "run the free prepare first: $S/caps_final.json is missing"
  [ "$CAP_FILE" = $S/caps_final.json ] || die "expected --cap-file $S/caps_final.json, found $CAP_FILE"
  last=$(ls -d $X/tune/rounds/r* | sort | tail -1)
  [ -f $last/DONE ] || die "the last round ($last) is not done"
  # frozen: the V2T system-side files are exactly the last round's (a benchmark-side change does not count)
  # an `if`, not `cmd && die`: under `set -e` a false `cmd` as the function's last command would end the
  # script silently with status 1 exactly when the check passes
  if v2t_system_changed_since "$(cat $last/commit)"; then
    die "a V2T system file (tune_lib.sh V2T_FROZEN_FILES) or inputs/ changed since the last round's commit $(cat $last/commit): V2T is not frozen"
  fi
}

final_plant() {  # final_plant <corpus> <sheets> <seed>
  fp=$1
  step load_lines_$fp load_lines $fp $2 $3 plant_lines
  for fin_arm in CYP-A CYP-B; do step run_${fin_arm}_$fp tune_run $fin_arm "V7-$fin_arm-$fp" $fp full $QROOT; done
  step run_AG_$fp tune_run AG "V7-AG-$fp" $fp full $QROOT
  step load_plain_$fp load_lines $fp $2 $3 plant   # F1 reads the plain plant profile, as when it was sealed
  step run_F1CYP_$fp tune_run F1-CYP "V7F1-CYP-$fp" $fp full $QROOT
  step run_F1AG_$fp tune_run F1-AG "V7F1-AG-$fp" $fp full $QROOT
}

report_final() {
  for fin_corpus in $V1 $V2; do
    for fin_setting in A B; do
      $P -m plantgraph.qa.cascade tune-report --corpus $fin_corpus --setting $fin_setting --questions-root $QROOT \
        --corpora-root $AG_CORPORA --run cypher-v2t=$S/runs/V7-CYP-$fin_setting-$fin_corpus \
        --run agent-v2t=$S/runs/V7-AG-$fin_corpus --out $S/report/V2T-$fin_setting/$fin_corpus \
        > $S/report/V2T-$fin_setting-$fin_corpus.txt || die "V2T report ($fin_setting, $fin_corpus) failed"
    done
    $EX dev-report --corpus-id $fin_corpus --cyp-run $S/runs/V7F1-CYP-$fin_corpus --ag-run $S/runs/V7F1-AG-$fin_corpus \
      --questions-root $QROOT --out $S/report/F1/$fin_corpus || die "the F1 report on $fin_corpus failed"
  done
  echo "=== final reports: $S/report/{V2T-A,V2T-B,F1}/<corpus>/"
}

paid_final() {
  require_paid; require_clean_tree; require_tune_guards_passed; require_final_start
  check_listing "$(listing_file)"
  use_database; LOADED_DB=$NEO4J_DATABASE
  git rev-parse HEAD > $S/commit
  final_plant $V1 100 212
  final_plant $V2 1000 213
  report_final
  touch $S/DONE
  echo "=== $(date +%T) V done: the validation plants are spent; this script will not run them again"
}

if [ "$FINAL_V" = yes ]; then
  [ ! -f $S/DONE ] || die "the validation plants were already run: $S/DONE (V is run once)"
  prepare_final
  [ "$ALLOW_PAID" != yes ] || paid_final
elif [ -n "$ROUND" ]; then
  [ "$ALLOW_PAID" = yes ] || die "a round is paid: pass --allow-paid-calls --cap-file --cap-sha256 (without --round the script only prepares)"
  paid_round
else
  prepare_tuning
fi
