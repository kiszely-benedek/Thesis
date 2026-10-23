#!/bin/sh
# Model switch (user 2026-10-11): Cypher tier on both dev corpora, GLM with the round-2 prompt
# and GPT-6 Luna low on the same prompt, so the Cypher tier is compared before Luna is adopted.
R=data/runs/cv1
P=.venv/Scripts/python
for c in D100 D1000; do
  if [ $c = D100 ]; then T=100; else T=1000; fi
  echo "=== wipe Neo4j, then load $c (plant profile)"
  $P data/runs/cv1/wipe_all_neo4j.py
  $P -m plantgraph.ingest synthetic --headline --target-sheets $T --seed 1 --store-profile plant --corpus-id $c > $R/neo4j_${c}_plant_r2.json 2>$R/neo4j_${c}_r2.err
  $P -c "import json;d=json.load(open('$R/neo4j_${c}_plant_r2.json',encoding='utf-8'));print(d['counts'])"
  echo "=== CYP2-$c-low (GLM)"
  $P -m plantgraph.qa.harness --run-id CYP2-$c-low --experiment CV2-round2 --corpus $c:dev --strategy cypher_rag_plant --strategy-params-json $R/params_cypher_plant.json --pin-json $R/pin_low.json --corpora-root $R/neo4jplant --questions-root $R/questions --runs-root $R/runs --cache-path $R/cache_low.sqlite --allow-paid-calls --cost-per-question-usd 0.0004 --max-spend-usd 0.15 --concurrency 4 --question-deadline-s 120 > $R/cyp2_$c.log 2>&1
  grep -E "stopped_by|Error" $R/cyp2_$c.log | head -3
  echo "=== CYPL-$c (Luna low)"
  $P -m plantgraph.qa.harness --run-id CYPL-$c --experiment MODEL-SWITCH --corpus $c:dev --strategy cypher_rag_plant --strategy-params-json $R/params_cypher_plant.json --pin-json $R/pins_bakeoff/F_cypher.json --corpora-root $R/neo4jplant --questions-root $R/questions --runs-root $R/runs --cache-path $R/cache_luna.sqlite --allow-paid-calls --cost-per-question-usd 0.001 --max-spend-usd 0.30 --concurrency 4 --question-deadline-s 120 > $R/cypl_$c.log 2>&1
  grep -E "stopped_by|Error" $R/cypl_$c.log | head -3
done
