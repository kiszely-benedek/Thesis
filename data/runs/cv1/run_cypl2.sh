#!/bin/sh
# ADR-0052: Cypher tier on GPT-6 Luna re-run after the canonical row order fix.
# Dev corpora at concurrency 1 (clean perf_counter local compute for the infra tables), the
# paraphrase set at concurrency 4; ends with D1000 loaded, as the demo needs.
R=data/runs/cv1
P=.venv/Scripts/python
H="$USERPROFILE/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
cypher() {  # cypher <run-id> <corpus> <questions-root> <concurrency> <cap>
  echo "=== $1"
  $P -m plantgraph.qa.harness --run-id $1 --experiment ADR-0052 --corpus $2:dev --strategy cypher_rag_plant --strategy-params-json $R/params_cypher_plant.json --pin-json $R/pins_bakeoff/F_cypher.json --corpora-root $R/neo4jplant --questions-root $3 --runs-root $R/runs --cache-path $R/cache_luna.sqlite --allow-paid-calls --cost-per-question-usd 0.001 --max-spend-usd $5 --concurrency $4 --question-deadline-s 120 > $R/$1.log 2>&1
  grep -E "stopped_by|Error" $R/$1.log | head -3
}
load() {  # load <corpus> <sheets>
  echo "=== fresh database, load $1 (plant profile)"
  $P -m plantgraph.ingest synthetic --headline --target-sheets $2 --seed 1 --store-profile plant --corpus-id $1 --fresh-database --neo4j-home "$H" > $R/neo4j_$1_plant_cypl2.json 2>$R/neo4j_$1_cypl2.err || { echo "load $1 failed"; exit 1; }
}
load D100 100
cypher CYPL2-D100 D100 $R/questions 1 0.30
cypher CYPL2-PARA-D100 D100 $R/para 4 0.40
load D1000 1000
cypher CYPL2-D1000 D1000 $R/questions 1 0.30
echo done
