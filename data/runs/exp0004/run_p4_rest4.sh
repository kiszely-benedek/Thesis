#!/bin/sh
# EXP-0004 P4, d4 agent tier after it hit its $0.65 cap (2026-11-06 15:19; $0.620 really spent, 445 of 560 rows).
# The user approved at most $0.25 more of real spend to finish d4 (2026-11-06, "igen, mehet").
# On a resume the spend guard counts the recorded cost of the rows on disk, cache hits included ($0.9255 for the
# 445 d4 agent rows), so the agent tier's nominal cap is 0.9255 + 0.25 = $1.176. The Cypher tier is done (skipped).
# Real spend of P4 stays under 1.824 + 0.25 = $2.07.
# Launch detached:  Invoke-CimMethod Win32_Process Create  "C:\Program Files\Git\bin\bash.exe" -l <this file>
# Log: e2e_paid.log.  Do NOT run pytest or the demo while this runs.
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 1
E=data/runs/exp0004
PLOG=$E/e2e_paid.log

[ -f $E/e2e/d4/live/logs/steps/replay_E2E-CYP-H1000g2V-d4.ok ] || { echo "=== $(date +%T) STOP: the d4 Cypher tier is not done" >> "$PLOG"; exit 1; }
echo "=== $(date +%T) resume paid d4 agent tier (nominal \$1.176 = recorded \$0.9255 + at most \$0.25 new, approved by the user)" >> "$PLOG"
if sh $E/run_e2e.sh paid d4 --allow-paid-calls --max-spend-usd 1.65 --above-dry-cap --tier-caps 0.474,1.176 --resume >> "$PLOG" 2>&1; then
  echo "=== $(date +%T) done paid d4" >> "$PLOG"
  echo "=== $(date +%T) all three paid runs done" >> "$PLOG"
else
  echo "=== $(date +%T) FAILED paid d4 (exit $?)" >> "$PLOG"; exit 1
fi
