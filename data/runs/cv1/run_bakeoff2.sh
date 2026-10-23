#!/bin/sh
# Model bake-off stage 2 (agent tier): the 72 remaining q5 questions; finalists C and F plus baseline A, one window.
R=data/runs/cv1
P=.venv/Scripts/python
for c in A C F; do
  echo "=== BO2-$c"
  $P -m plantgraph.qa.harness --run-id BO2-$c-D100 --experiment BAKEOFF-2 --corpus D100:dev --strategy graph_agent_low_steps --strategy-params-json $R/params_agent_low.json --pin-json $R/pins_bakeoff/${c}_answer.json --corpora-root $R/corpora --questions-root $R/q72 --runs-root $R/runs --cache-path $R/cache_bakeoff.sqlite --allow-paid-calls --cost-per-question-usd 0.003 --max-spend-usd 0.80 --concurrency 4 --question-deadline-s 120 > $R/bo2_$c.log 2>&1
  grep -E "stopped_by|Error" $R/bo2_$c.log | head -3
done
