# Core of the EXP-0009 launcher: sourced by run_all.sh, never run on its own. POSIX sh.
#
# Same pattern as EXP-0008's lib.sh (paths, the `=== <UTC> <stage> <event> <detail>` log line, the clean
# stop that leaves state/STOPPED with the exact resume command). Arithmetic, hashing and parsing are not
# done in shell: they are commands of `python -m plantgraph.qa.exp0009.launcher` (`$L`), which have tests.
# Environment variables are EXP-0008's under the prefix E10_ (E10_PYTHON, E10_ROOT, E10_NEO4J_HOME ...).

P=${E10_PYTHON:-.venv/Scripts/python}
L="$P -m plantgraph.qa.exp0009.launcher"
SCRIPTS=data/runs/exp0009
# E10_ROOT: where outputs go. The real run uses the scripts' own folder; the smoke uses a temporary one.
ROOT=${E10_ROOT:-$SCRIPTS}
STATE=$ROOT/state
PREREG=$ROOT/prereg
LOGS=$ROOT/logs
INPUTS=$SCRIPTS/inputs   # copies of the E9 pins and parameters, hashed into E10
SMOKE=${SMOKE:-no}
FORCE=${FORCE:-}
CUR_STAGE=-

utc() { date -u +%Y-%m-%dT%H:%M:%SZ; }

event() {  # event <START|DONE|SKIP|STOP|"GATE PASS"|"GATE FAIL"|CAP|NOTE> <detail>
  echo "=== $(utc) $CUR_STAGE $1 $2"
}

smoke() { [ "$SMOKE" = yes ]; }
forced() { [ "$FORCE" = "$1" ]; }   # a smoke-only switch that makes one gate or cap fail on purpose

resume_command() {  # resume_command <stage>: what the user types to continue from there
  rc_prefix=; rc_flag=
  if [ "$ROOT" != "$SCRIPTS" ]; then rc_prefix="E10_ROOT=$ROOT "; fi
  if smoke; then rc_flag=" --smoke"; fi
  echo "${rc_prefix}sh $SCRIPTS/run_all.sh --from $1$rc_flag"
}

stop_run() {  # stop_run <user|main|topup|infra> <reason>: log it, write state/STOPPED, leave the stage
  case $1 in
    user) sr_who="needs the user" ;;
    main) sr_who="needs the main session" ;;
    topup) sr_who="top-up or restart" ;;
    *) sr_who="infrastructure" ;;
  esac
  event STOP "[$sr_who] $2"
  $L stopped --dir "$STATE" --stage "$CUR_STAGE" --reason "[$sr_who] $2" \
    --resume "$(resume_command "$CUR_STAGE")"
  exit 10
}

try() {  # try <command...>: run it; a failure stops the launcher as an infrastructure error
  "$@" || stop_run infra "command failed (exit $?): $*"
}

gate_pass() { event "GATE PASS" "$1"; }

gate_fail() {  # gate_fail <gate> <detail>: a designed stop that needs the user's design work
  event "GATE FAIL" "$1: $2"
  stop_run user "$1 failed: $2"
}

once() {  # once <name> <command...>: skip when its marker exists (a resumed stage redoes only what is left)
  on_name=$1; shift
  on_marker=$ROOT/state/steps/${CUR_STAGE}_$on_name.ok
  if [ -e "$on_marker" ]; then event NOTE "skip step $on_name (done)"; return 0; fi
  "$@" || stop_run infra "step $on_name failed (exit $?)"
  mkdir -p "$ROOT/state/steps"
  : > "$on_marker"
}

# A stage lists its output files with `outputs`; the parent hashes them into state/<stage>.done.
outputs() { mkdir -p "$STATE"; printf '%s\n' "$@" > "$STATE/$CUR_STAGE.outputs"; }

ensure_dirs() { mkdir -p "$STATE/steps" "$LOGS" "$PREREG"; }

estimate_note() {  # estimate_note <P1a|P1b|P1c>: the cost estimate, printed before every paid stage
  event NOTE "$($L estimate --stage "$1" --root "$ROOT")"
}
