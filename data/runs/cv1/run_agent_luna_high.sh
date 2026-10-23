#!/bin/sh
# ADR-0050 follow-up: Luna agent with steps low (graph_agent_low_steps overrides) and the FINAL answer at high
# effort, like GLM's final at its default. Same cache as AGL-*: unchanged step calls replay.
R=data/runs/cv1
P=.venv/Scripts/python
for c in D100 D1000; do
  echo "=== AGLH-$c"
  $P -m plantgraph.qa.harness --run-id AGLH-$c --experiment MODEL-SWITCH --corpus $c:dev --strategy graph_agent_low_steps --strategy-params-json $R/params_agent_low.json --pin-json $R/pin_luna_final_high.json --corpora-root $R/corpora --questions-root $R/questions --runs-root $R/runs --cache-path $R/cache_luna.sqlite --allow-paid-calls --cost-per-question-usd 0.003 --max-spend-usd 0.60 --concurrency 4 --question-deadline-s 120 > $R/AGLH-$c.log 2>&1
  grep -E "stopped_by|Error" $R/AGLH-$c.log | head -3
done
