#!/bin/sh
# Paraphrase robustness (PARA-R1): Cypher tier on the 252 paraphrased D100 questions, GLM and Luna;
# then leave D1000 loaded, as before.
R=data/runs/cv1
P=.venv/Scripts/python
echo "=== wipe Neo4j, then load D100 (plant profile)"
$P $R/wipe_all_neo4j.py
$P -m plantgraph.ingest synthetic --headline --target-sheets 100 --seed 1 --store-profile plant --corpus-id D100 > $R/neo4j_D100_plant_para.json 2>$R/neo4j_D100_para.err
for arm in "CYP2-PARA-D100 pin_low.json cache_low.sqlite 0.0004 0.20" "CYPL-PARA-D100 pins_bakeoff/F_cypher.json cache_luna.sqlite 0.001 0.40"; do
  set -- $arm
  echo "=== $1"
  $P -m plantgraph.qa.harness --run-id $1 --experiment PARA-R1 --corpus D100:dev --strategy cypher_rag_plant --strategy-params-json $R/params_cypher_plant.json --pin-json $R/$2 --corpora-root $R/neo4jplant --questions-root $R/para --runs-root $R/runs --cache-path $R/$3 --allow-paid-calls --cost-per-question-usd $4 --max-spend-usd $5 --concurrency 4 --question-deadline-s 120 > $R/$1.log 2>&1
  grep -E "stopped_by|Error" $R/$1.log | head -3
done
echo "=== wipe Neo4j, then load D1000 back"
$P $R/wipe_all_neo4j.py
$P -m plantgraph.ingest synthetic --headline --target-sheets 1000 --seed 1 --store-profile plant --corpus-id D1000 > $R/neo4j_D1000_plant_r2.json 2>$R/neo4j_D1000_r2.err
echo done
