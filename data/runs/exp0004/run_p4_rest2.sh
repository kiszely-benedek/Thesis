#!/bin/sh
# EXP-0004 P4 after the d2 agent tier hit its spend cap (2026-11-06 12:32). Approved by the user on
# 2026-11-06 ("A"): caps above the dry-run caps, still inside the pre-registered $4.44 bound for P4.
#   d2: resume (load and Cypher tier are done). On a resume the spend guard counts the full recorded cost
#       of the rows on disk, cache hits included ($0.8206 for d2, of which $0.4936 was really spent), so the
#       nominal cap must sit above that: arm $1.15 -> agent tier $0.9471, i.e. at most $0.1265 of new spend
#       (the user approved agent $0.65 = $0.156 more than the $0.494 really spent).
#   d4: 2.0x instead of 1.5x the dry-run caps: arm cap $0.775 (Cypher $0.125, agent $0.650)
# d0 is done ($0.573 spent of its $0.8923 cap). Real spend stays under 0.8923 + (0.4936 + 0.035 + 0.1265) + 0.775 = $2.32.
# Launch detached:  Invoke-CimMethod Win32_Process Create  "C:\Program Files\Git\bin\bash.exe" -l <this file>
# Log: e2e_paid.log.  Do NOT run pytest or the demo while this runs.
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 1
E=data/runs/exp0004
PLOG=$E/e2e_paid.log

paid() {  # paid <arm> <arm cap> [--resume]
  echo "=== $(date +%T) start paid $1 (max \$$2, above the dry-run cap, approved by the user) $3" >> "$PLOG"
  # shellcheck disable=SC2086
  if sh $E/run_e2e.sh paid "$1" --allow-paid-calls --max-spend-usd "$2" --above-dry-cap $3 >> "$PLOG" 2>&1; then
    echo "=== $(date +%T) done paid $1" >> "$PLOG"
  else
    echo "=== $(date +%T) FAILED paid $1 (exit $?)" >> "$PLOG"; exit 1
  fi
}

[ -f $E/e2e/d0/live/logs/steps/restore_d1000.ok ] || { echo "=== $(date +%T) STOP: paid d0 is not done" >> "$PLOG"; exit 1; }
[ -f $E/e2e/d2/live/logs/steps/restore_d1000.ok ] || paid d2 1.15 --resume
[ -e $E/e2e/d4/live ] && { echo "=== $(date +%T) STOP: $E/e2e/d4/live already exists; resume by hand" >> "$PLOG"; exit 1; }
paid d4 0.775
echo "=== $(date +%T) all three paid runs done" >> "$PLOG"
