#!/bin/sh
# Accuracy round 2 (cascade-v2 addendum 2026-10-10): re-run tier 1 and tier 2 on both dev corpora.
R=data/runs/cv1
P=.venv/Scripts/python
for c in D100 D1000; do
  if [ $c = D100 ]; then T=100; else T=1000; fi
  echo "=== load $c into Neo4j (plant profile)"
  $P -m plantgraph.ingest synthetic --headline --target-sheets $T --seed 1 --store-profile plant --corpus-id $c > $R/neo4j_${c}_plant_r2.json 2>$R/neo4j_${c}_r2.err
  $P -c "import json;d=json.load(open('$R/neo4j_${c}_plant_r2.json',encoding='utf-8'));print(d['counts'])"
  echo "=== CYP2-$c-low"
  $P -m plantgraph.qa.harness --run-id CYP2-$c-low --experiment CV2-round2 --corpus $c:dev --strategy cypher_rag_plant --strategy-params-json $R/params_cypher_plant.json --pin-json $R/pin_low.json --corpora-root $R/corpora --questions-root $R/questions --runs-root $R/runs --cache-path $R/cache_low.sqlite --allow-paid-calls --cost-per-question-usd 0.0004 --max-spend-usd 0.15 --concurrency 4 --question-deadline-s 120 > $R/cyp2_$c.log 2>&1
  grep -E "stopped_by|Error" $R/cyp2_$c.log | head -3
  echo "=== CV2-AG2-$c"
  $P -m plantgraph.qa.harness --run-id CV2-AG2-$c --experiment CV2-round2 --corpus $c:dev --strategy graph_agent_low_steps --strategy-params-json $R/params_agent_low.json --pin-json $R/pin_default.json --corpora-root $R/corpora --questions-root $R/questions --runs-root $R/runs --cache-path $R/cache_default.sqlite --allow-paid-calls --cost-per-question-usd 0.0015 --max-spend-usd 0.50 --concurrency 4 --question-deadline-s 120 > $R/cv2ag2_$c.log 2>&1
  grep -E "stopped_by|Error" $R/cv2ag2_$c.log | head -3
done
