#!/bin/sh
# EXP-0004 P4, the rest after the 2026-11-05 evening stop: the free dry run of d4, then the paid arm
# (approved by the user on 2026-11-05 within a $4.44 total for all three arms).
# d0 and d2 dry runs are done (e2e/d0/dry/caps.json, e2e/d2/dry/caps.json). Refuses if the three caps sum
# above $4.44; runs d0, d2, d4 paid one at a time, each capped at its own dry-run total; stops at the first failure.
# Launch detached (survives the session):
#   Invoke-CimMethod Win32_Process Create with  "C:\Program Files\Git\bin\bash.exe" -l <this file>
# Logs: e2e_dry_d4.log, e2e_paid.log.  Do NOT run pytest or the demo while this runs.
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)" || exit 1
E=data/runs/exp0004
PY=.venv/Scripts/python.exe
BUDGET=4.44
DLOG=$E/e2e_dry_d4.log
PLOG=$E/e2e_paid.log

if [ ! -f $E/e2e/d4/dry/caps.json ]; then
  echo "=== $(date +%T) start dry d4" >> "$DLOG"
  if sh $E/run_e2e.sh dry d4 >> "$DLOG" 2>&1; then
    echo "=== $(date +%T) done dry d4" >> "$DLOG"
  else
    echo "=== $(date +%T) FAILED dry d4 (exit $?)" >> "$DLOG"; exit 1
  fi
fi

caps() { $PY -I -c "import json,sys;print(json.load(open(sys.argv[1]))['total_cap_usd'])" "$E/e2e/$1/dry/caps.json"; }
C0=$(caps d0) && C2=$(caps d2) && C4=$(caps d4) || { echo "=== $(date +%T) STOP: a caps.json is missing" >> "$PLOG"; exit 1; }
SUM=$($PY -I -c "import sys;print(round(sum(map(float,sys.argv[1:])),4))" "$C0" "$C2" "$C4")
echo "=== $(date +%T) caps d0 \$$C0, d2 \$$C2, d4 \$$C4, total \$$SUM (budget \$$BUDGET)" >> "$PLOG"
if ! $PY -I -c "import sys;sys.exit(0 if float(sys.argv[1])<=float(sys.argv[2]) else 1)" "$SUM" "$BUDGET"; then
  echo "=== $(date +%T) STOP: total cap above the approved budget, ask the user" >> "$PLOG"; exit 1
fi

for arm in d0 d2 d4; do
  if [ -f $E/e2e/$arm/live/logs/steps/restore_d1000.ok ]; then echo "=== $(date +%T) paid $arm already done" >> "$PLOG"; continue; fi
  if [ -e $E/e2e/$arm/live ]; then  # a stopped paid run: part of its cap may be spent, so a human decides the resume cap
    echo "=== $(date +%T) STOP: $E/e2e/$arm/live exists but is not finished; resume by hand with the remaining cap" >> "$PLOG"; exit 1
  fi
  cap=$(caps $arm)
  echo "=== $(date +%T) start paid $arm (max \$$cap)" >> "$PLOG"
  if sh $E/run_e2e.sh paid $arm --allow-paid-calls --max-spend-usd "$cap" >> "$PLOG" 2>&1; then
    echo "=== $(date +%T) done paid $arm" >> "$PLOG"
  else
    echo "=== $(date +%T) FAILED paid $arm (exit $?)" >> "$PLOG"; exit 1
  fi
done
echo "=== $(date +%T) all three paid runs done" >> "$PLOG"
