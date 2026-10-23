#!/bin/sh
# Model switch (ADR-0050): agent tier under GPT-6 Luna low on both dev corpora and the 252 paraphrases,
# after the A6 no-substitute wording. No Neo4j needed (graph agent reads the networkx view).
R=data/runs/cv1
P=.venv/Scripts/python
run() {  # run <run-id> <corpus> <questions-root> <cap>
  echo "=== $1"
  $P -m plantgraph.qa.harness --run-id $1 --experiment MODEL-SWITCH --corpus $2:dev --strategy graph_agent_low_steps --strategy-params-json $R/params_agent_low.json --pin-json $R/pins_bakeoff/F_answer.json --corpora-root $R/corpora --questions-root $3 --runs-root $R/runs --cache-path $R/cache_luna.sqlite --allow-paid-calls --cost-per-question-usd 0.0015 --max-spend-usd $4 --concurrency 4 --question-deadline-s 120 > $R/$1.log 2>&1
  grep -E "stopped_by|Error" $R/$1.log | head -3
}
run AGL-D100 D100 $R/questions 0.40
run AGL-D1000 D1000 $R/questions 0.50
run AGL-PARA-D100 D100 $R/para 0.60
