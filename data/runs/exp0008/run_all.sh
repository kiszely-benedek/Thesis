#!/bin/sh
# EXP-0008: the whole final v2 measurement, M0 -> M10b, in one resumable launch (ADR-0065, design review-fixes §5.4).
#
# NOTHING IN THIS FOLDER RUNS BEFORE THE USER SAYS "mehet". Start (see README.md for the Windows form):
#   nohup sh data/runs/exp0008/run_all.sh > data/runs/exp0008/run_all.log 2>&1 &
#
#   --from <stage>   run <stage> and everything after it (earlier stages must be done and unchanged);
#                    the default resumes at the first stage that is not done
#   --smoke          the whole chain on tiny plants in a temporary folder, with a fake transport: zero paid
#                    calls, no Neo4j, no network (the cheap proof that the launcher itself works)
#   --force <what>   smoke only, to prove a stop works: g1 | g2 | cap | band | dirty-tree | wrong-head
#
# Stages: M0 M1 M2 M2b M3 M4 M5 M6a M6b M6c M7 M8a M8b M9 M10a M10b  (see stages/ and the README).
# Each finished stage writes state/<stage>.done with the sha256 of its outputs; a rerun skips it after
# re-checking them. Every event is one line:  === <UTC> <stage> <START|DONE|SKIP|NOTE|GATE PASS|GATE FAIL|CAP|STOP> <detail>
# Any stop leaves state/STOPPED with the stage, the reason and the exact resume command. This script never
# commits, never pushes, and writes only under its output folder (data/runs/exp0008, or the smoke's temp folder).
set -eu
cd "$(git rev-parse --show-toplevel)"

SMOKE=no; FORCE=; FROM=
while [ $# -gt 0 ]; do
  case $1 in
    --smoke) SMOKE=yes ;;
    --from) [ $# -ge 2 ] || { echo "ERROR: --from needs a stage" >&2; exit 2; }; FROM=$2; shift ;;
    --force) [ $# -ge 2 ] || { echo "ERROR: --force needs g1|g2|cap|band|dirty-tree|wrong-head" >&2; exit 2; }; FORCE=$2; shift ;;
    *) echo "ERROR: unknown option $1 (expected --smoke, --from <stage> or --force <what>)" >&2; exit 2 ;;
  esac
  shift
done
if [ -n "$FORCE" ] && [ "$SMOKE" != yes ]; then echo "ERROR: --force is for --smoke only" >&2; exit 2; fi
export SMOKE FORCE
if [ "$SMOKE" = yes ] && [ -z "${E9_ROOT:-}" ]; then   # a fresh temporary folder, as a path Python can open too
  E9_ROOT=$(mktemp -d); if command -v cygpath > /dev/null 2>&1; then E9_ROOT=$(cygpath -m "$E9_ROOT"); fi
fi
export E9_ROOT="${E9_ROOT:-}"
if [ -z "$E9_ROOT" ]; then unset E9_ROOT; fi

SCRIPTS=data/runs/exp0008
. "$SCRIPTS/lib.sh"
. "$SCRIPTS/lib_plants.sh"
. "$SCRIPTS/lib_runs.sh"
for stage_file in "$SCRIPTS"/stages/*.sh; do . "$stage_file"; done

STAGES="M0 M1 M2 M2b M3 M4 M5 M6a M6b M6c M7 M8a M8b M9 M10a M10b"
if [ -n "$FROM" ]; then
  case " $STAGES " in *" $FROM "*) ;; *) echo "ERROR: unknown stage $FROM (stages: $STAGES)" >&2; exit 2 ;; esac
fi

# A smoke has no committed part A, drawn seeds or pilot inputs: it writes stand-ins in its temporary folder.
smoke_prepare() {
  ensure_dirs
  SMOKE_HEAD=1111111111111111111111111111111111111111; export SMOKE_HEAD
  printf '# PREREG part A (smoke stand-in)\n\nFrozen code commit: %s\n' "$SMOKE_HEAD" > "$PREREG/PREREG_A.md"
  printf '{"smoke": true}\n' > "$PREREG/seeds.json"
  event NOTE "SMOKE in $ROOT: tiny plants, fake transport, no Neo4j, no network; forced: ${FORCE:-nothing}"
  if [ "$FORCE" = cap ]; then E9_SMOKE_COST_USD=2; export E9_SMOKE_COST_USD; else E9_SMOKE_COST_USD=0.00005; export E9_SMOKE_COST_USD; fi
}

# Stage M0 of a real run creates these; a stage that follows an earlier launch finds them in place.
ensure_dirs
rm -f "$STATE/STOPPED"
CUR_STAGE=launcher
if smoke; then smoke_prepare; else event NOTE "real run into $ROOT (resume with: $(resume_command M0))"; fi

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
  git rev-parse HEAD > "$ROOT/SMOKE_PASSED"   # readiness item 4 compares this with HEAD
  event NOTE "SMOKE PASSED: every stage reached with zero real calls; evidence $ROOT/SMOKE_PASSED"
fi
