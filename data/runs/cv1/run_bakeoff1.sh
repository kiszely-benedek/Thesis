#!/bin/sh
# Model bake-off stage 1 (agent tier): 18 q (one per family), seven pinned configs, one time window, fresh cache.
R=data/runs/cv1
P=.venv/Scripts/python
for spec in "A 0.20" "B 0.20" "C 0.20" "D 0.20" "E 0.35" "F 0.20" "G 0.30"; do
  set -- $spec
  echo "=== BO1-$1"
  $P -m plantgraph.qa.harness --run-id BO1-$1-D100 --experiment BAKEOFF-1 --corpus D100:dev --strategy graph_agent_low_steps --strategy-params-json $R/params_agent_low.json --pin-json $R/pins_bakeoff/$1_answer.json --corpora-root $R/corpora --questions-root $R/q18 --runs-root $R/runs --cache-path $R/cache_bakeoff.sqlite --allow-paid-calls --cost-per-question-usd 0.005 --max-spend-usd $2 --concurrency 4 --question-deadline-s 120 > $R/bo1_$1.log 2>&1
  grep -E "stopped_by|Error" $R/bo1_$1.log | head -3
done
