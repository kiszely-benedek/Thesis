#!/bin/sh
# EXP-0009 P1: the whole v2.2 measurement of A2 and B, P0 -> END, in one resumable launch (ADR-0068, design 19).
#
# NOTHING IN THIS FOLDER RUNS BEFORE THE USER SAYS "mehet". The draw (step 0) is run by hand first:
#   python -m plantgraph.qa.exp0009.launcher draw --draw-seed N          (free; writes prereg/seeds.json, plan.json)
# Start (see README.md for the Windows form):
#   nohup sh data/runs/exp0009/run_all.sh > data/runs/exp0009/run_all.log 2>&1 &
#
#   --from <stage>   run <stage> and everything after it (earlier stages must be done and unchanged);
#                    the default resumes at the first stage that is not done
#   --smoke          the whole chain on tiny plants in a temporary folder, with a fake transport: zero paid
#                    calls, no Neo4j, no network (the cheap proof that the launcher itself works)
#   --force <what>   smoke only, to prove a stop works: g1 | g1b | g1b2 | g0l | cap | dirty-tree | wrong-head | b-files
#                    (g1b and g1b2 take the "B not sealed" branch without a stop)
#
# Stages: P0 P1a P1b F10 B10 P1c P1g P1d END  (see stages/ and the README). P0, F10, B10, END are free.
# P1g is the user's small GLM comparison arm (design 20): two sealed plants, scope R only, its own $2.50 cap.
# Each finished stage writes state/<stage>.done with the sha256 of its outputs; a rerun skips it after re-checking.
# Every event is one line:  === <UTC> <stage> <START|DONE|SKIP|NOTE|GATE PASS|GATE FAIL|CAP|STOP> <detail>
# Any stop leaves state/STOPPED with the stage, the reason and the exact resume command. This script never commits,
# never pushes, and writes only under its output folder (data/runs/exp0009, or the smoke's temporary folder).
set -eu
cd "$(git rev-parse --show-toplevel)"

SMOKE=no; FORCE=; FROM=
while [ $# -gt 0 ]; do
  case $1 in
    --smoke) SMOKE=yes ;;
    --from) [ $# -ge 2 ] || { echo "ERROR: --from needs a stage" >&2; exit 2; }; FROM=$2; shift ;;
    --force) [ $# -ge 2 ] || { echo "ERROR: --force needs g1|g1b|g1b2|g0l|cap|dirty-tree|wrong-head|b-files" >&2; exit 2; }; FORCE=$2; shift ;;
    *) echo "ERROR: unknown option $1 (expected --smoke, --from <stage> or --force <what>)" >&2; exit 2 ;;
  esac
  shift
done
if [ -n "$FORCE" ] && [ "$SMOKE" != yes ]; then echo "ERROR: --force is for --smoke only" >&2; exit 2; fi
if [ "$SMOKE" != yes ] && [ ! -d "${E10_NEO4J_HOME:-}" ]; then
  echo "ERROR: expected E10_NEO4J_HOME to name the Neo4j server's home folder, found '${E10_NEO4J_HOME:-}' (start with launch.sh)" >&2
  exit 2
fi
export SMOKE FORCE
if [ "$SMOKE" = yes ] && [ -z "${E10_ROOT:-}" ]; then   # a fresh temporary folder, as a path Python can open too
  E10_ROOT=$(mktemp -d); if command -v cygpath > /dev/null 2>&1; then E10_ROOT=$(cygpath -m "$E10_ROOT"); fi
fi
export E10_ROOT="${E10_ROOT:-}"
if [ -z "$E10_ROOT" ]; then unset E10_ROOT; fi

SCRIPTS=data/runs/exp0009
. "$SCRIPTS/lib.sh"
. "$SCRIPTS/lib_plants.sh"
. "$SCRIPTS/lib_runs.sh"
for stage_file in "$SCRIPTS"/stages/*.sh; do . "$stage_file"; done

STAGES="P0 P1a P1b F10 B10 P1c P1g P1d END"
if [ -n "$FROM" ]; then
  case " $STAGES " in *" $FROM "*) ;; *) echo "ERROR: unknown stage $FROM (stages: $STAGES)" >&2; exit 2 ;; esac
fi

# A smoke has no committed part A or drawn seeds: it writes stand-ins in its temporary folder (and draws a tiny plan).
smoke_prepare() {
  ensure_dirs
  SMOKE_HEAD=1111111111111111111111111111111111111111; export SMOKE_HEAD
  printf '# PREREG part A (smoke stand-in)\n\nPart A code commit: %s\n' "$SMOKE_HEAD" > "$PREREG/PREREG_A.md"
  [ -f "$PREREG/plan.json" ] || $L draw --smoke --prereg "$PREREG" || stop_run infra "the smoke draw failed"
  event NOTE "SMOKE in $ROOT: tiny plants, fake transport, no Neo4j, no network; forced: ${FORCE:-nothing}"
  if [ "$FORCE" = cap ]; then E10_SMOKE_COST_USD=2; export E10_SMOKE_COST_USD; else E10_SMOKE_COST_USD=0.00005; export E10_SMOKE_COST_USD; fi
}

ensure_dirs
rm -f "$STATE/STOPPED"
CUR_STAGE=launcher
if smoke; then smoke_prepare; else event NOTE "real run into $ROOT (resume with: $(resume_command P0))"; fi

run_stage() {  # run_stage <stage>: the stage in a subshell, so a stop or a failure leaves only files behind
  rs_stage=$1; CUR_STAGE=$rs_stage
  event START "$rs_stage"
  rm -f "$STATE/$rs_stage.outputs"
  rs_rc=0
  set +e
  ( set -eu; CUR_STAGE=$rs_stage; "stage_$rs_stage" )
  rs_rc=$?
  set -e
  if [ $rs_rc -ne 0 ]; then
    if [ ! -f "$STATE/STOPPED" ]; then   # not a designed stop: say so, with the resume point
      event STOP "[infrastructure] stage $rs_stage failed unexpectedly (exit $rs_rc), see the lines above"
      $L stopped --dir "$STATE" --stage "$rs_stage" --reason "[infrastructure] unexpected failure (exit $rs_rc)" \
        --resume "$(resume_command "$rs_stage")"
    fi
    exit 10
  fi
  # shellcheck disable=SC2046
  $L state-write --dir "$STATE" --stage "$rs_stage" $(cat "$STATE/$rs_stage.outputs") \
    || stop_run infra "stage $rs_stage did not leave the outputs it listed"
  event DONE "$rs_stage"
}

started=no; if [ -z "$FROM" ]; then started=yes; fi
for stage in $STAGES; do
  CUR_STAGE=$stage
  if [ "$started" = no ] && [ "$stage" = "$FROM" ]; then started=yes; fi
  if [ "$started" = no ]; then   # before --from: it must be done and unchanged
    $L state-check --dir "$STATE" --stage "$stage" || stop_run user "stage $stage comes before --from $FROM but is not done"
    event SKIP "$stage (done)"
    continue
  fi
  if [ -z "$FROM" ]; then   # the default skips what is done and still hashes as recorded; --from reruns
    if $L state-check --dir "$STATE" --stage "$stage" 2> /dev/null; then event SKIP "$stage (done)"; continue; fi
  fi
  run_stage "$stage"
done

CUR_STAGE=launcher
event DONE "all stages: $($L spent --root "$ROOT")"
if smoke; then
  git rev-parse HEAD > "$ROOT/SMOKE_PASSED"   # readiness compares this with HEAD
  event NOTE "SMOKE_PASSED: every stage reached with zero real calls; evidence $ROOT/SMOKE_PASSED"
fi
