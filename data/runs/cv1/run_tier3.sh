#!/bin/sh
# Tier-3 candidates (ADR-0046 S1) on the DEV10 runaways of both dev corpora.
R=data/runs/cv1
P=.venv/Scripts/python
for c in D100 D1000; do
  for spec in "mimo pin_mimo.json cache_mimo.sqlite 0.012 0.60" "glmlow pin_low.json cache_low.sqlite 0.003 0.20" "glm64k pin_default_64k.json cache_default.sqlite 0.03 1.40"; do
    set -- $spec
    echo "=== T3-$1-$c"
    $P -m plantgraph.qa.harness --run-id T3-$1-$c --experiment CP-P2-tier3-candidates --corpus $c:dev \
      --strategy hierarchical_need_rules_plant --strategy-params-json $R/params_need_plant.json --pin-json $R/$2 \
      --corpora-root $R/corpora --questions-root $R/q_runaway --runs-root $R/runs --cache-path $R/$3 \
      --allow-paid-calls --cost-per-question-usd $4 --max-spend-usd $5 --concurrency 4 2>&1 | grep -E "mean_total_cost|stopped_by|Error|error" | head -5
  done
done
