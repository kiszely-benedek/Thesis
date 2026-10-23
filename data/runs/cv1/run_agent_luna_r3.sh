#!/bin/sh
# Round 3 (A6b + A7) under ADR-0050's setting: Luna steps low, final high; both dev corpora and the 252 paraphrases.
R=data/runs/cv1
P=.venv/Scripts/python
run() {  # run <run-id> <corpus> <questions-root> <cap>
  echo "=== $1"
  $P -m plantgraph.qa.harness --run-id $1 --experiment MODEL-SWITCH-R3 --corpus $2:dev --strategy graph_agent_low_steps --strategy-params-json $R/params_agent_low.json --pin-json $R/pin_luna_final_high.json --corpora-root $R/corpora --questions-root $3 --runs-root $R/runs --cache-path $R/cache_luna.sqlite --allow-paid-calls --cost-per-question-usd 0.003 --max-spend-usd $4 --concurrency 4 --question-deadline-s 120 > $R/$1.log 2>&1
  grep -E "stopped_by|Error" $R/$1.log | head -3
}
run AGL3-D100 D100 $R/questions 0.60
run AGL3-D1000 D1000 $R/questions 0.70
run AGL3-PARA-D100 D100 $R/para 0.80
