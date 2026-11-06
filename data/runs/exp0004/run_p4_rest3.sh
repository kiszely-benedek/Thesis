#!/bin/sh
# EXP-0004 P4, d4 after its Cypher tier hit its spend cap (2026-11-06 13:34; $0.0638 really spent).
# Within the user's approval of 2026-11-06 ("A": caps above the dry-run caps, inside the $4.44 P4 bound).
# Tier caps set explicitly (--tier-caps), because on a resume the spend guard counts the recorded cost of
# the rows on disk, cache hits included ($0.3537 for the 440 d4 Cypher rows):
#   Cypher tier: nominal $0.474 -> at most $0.12 of new spend;   agent tier (fresh run): $0.65.
# Real spend of P4 stays under 1.110 (d0 + d2) + 0.064 + 0.12 + 0.65 = $1.944.
# Launch detached:  Invoke-CimMethod Win32_Process Create  "C:\Program Files\Git\bin\bash.exe" -l <this file>
# Log: e2e_paid.log.  Do NOT run pytest or the demo while this runs.
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 1
E=data/runs/exp0004
PLOG=$E/e2e_paid.log

for arm in d0 d2; do
  [ -f $E/e2e/$arm/live/logs/steps/restore_d1000.ok ] || { echo "=== $(date +%T) STOP: paid $arm is not done" >> "$PLOG"; exit 1; }
done
echo "=== $(date +%T) resume paid d4 (tier caps Cypher \$0.474, agent \$0.65, approved by the user)" >> "$PLOG"
if sh $E/run_e2e.sh paid d4 --allow-paid-calls --max-spend-usd 1.124 --above-dry-cap --tier-caps 0.474,0.65 --resume >> "$PLOG" 2>&1; then
  echo "=== $(date +%T) done paid d4" >> "$PLOG"
  echo "=== $(date +%T) all three paid runs done" >> "$PLOG"
else
  echo "=== $(date +%T) FAILED paid d4 (exit $?)" >> "$PLOG"; exit 1
fi
