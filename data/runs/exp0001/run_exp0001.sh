#!/bin/sh
# EXP-0001 stages A and B (ADR-0054; design 9.2). PAID: run only after the user's go.
# Do NOT run pytest while this runs. One corpus in Neo4j at a time; ends with D1000 (plant) loaded.
# A rerun skips finished steps (logs/steps/<name>.ok); a run stopped once is resumed under the same run id.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0001/lib.sh
LADDER="H1 H3 H10 H30"
GATE_USD=6.00

ex01_run() {  # stage A2: five arms, three repeats on ChatP&ID's five scored questions
  rc=0
  $P -m plantgraph.qa.exp0001 ex01 --arms ctx-high,ctx-low,ctx-gpt5mini,cyp,ag --repeats 3 --cap 0.40 \
    --allow-paid-calls --inputs-dir $IN --corpora-root $S/corpora --out-dir $S/ex01 \
    >> $S/logs/E1-EX01.log 2>&1 || rc=$?
  case $rc in
    0) echo "    EX01: complete" ;;
    3) die "EX01 reached its spend cap: ask the user before resuming with a higher cap" ;;
    *) die "EX01 failed with exit code $rc, see $S/logs/E1-EX01.log" ;;
  esac
  $P -m plantgraph.qa.exp0001 ex01-review --checklist $IN/ex01_checklist.json --out-dir $S/ex01 \
    || die "writing the blind review sheet failed"
}

load_ex01() {  # stage A1: EX01 alone in Neo4j, plant profile (the Cypher arm refuses any other)
  echo "=== $(date +%T) load EX01"
  $P -m plantgraph.ingest proteus data/external/C01V04-VER.EX01.xml --corpus-id EX01 --store-profile plant \
    --fresh-database --neo4j-home "$H" --out $S/neo4jplant/EX01 \
    > $S/logs/load_EX01.json 2> $S/logs/load_EX01.err || die "loading EX01 failed, see $S/logs/load_EX01.err"
}

ladder_tier_runs() {  # B1: the Cypher tier, one corpus in Neo4j at a time
  for c in $LADDER; do
    step load_$c load_ladder $c
    if [ "$c" = H1 ]; then step cypher_H1_smoke cypher E1-CYP-H1 H1 0.01 smoke; fi
    step cypher_$c cypher E1-CYP-$c $c 0.15 full
    step replay_cyp_$c replay_cypher E1-CYP-$c $c
  done
}

ladder_agent_runs() {  # B3: the agent tier (reads the in-memory graph; D1000 is only the resting state)
  step agent_H1_smoke agent E1-AG-H1 H1 0.02 smoke
  for c in $LADDER; do
    step agent_$c agent E1-AG-$c $c 0.20 full
    step replay_ag_$c replay_agent E1-AG-$c $c
  done
}

gate() {  # after the ctx smoke: project the remaining ContextRAG cost from measured ratio and output cost
  $P - "$S" "$GATE_USD" <<'EOF'
import json, sys
from pathlib import Path

from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.serialize import serialize_occurrence_graph

root, limit = Path(sys.argv[1]), float(sys.argv[2])
listing = json.loads((root / "logs" / "listing_run.json").read_text(encoding="utf-8"))
base_in = float(listing["pricing"]["prompt"])
step = listing["pricing"]["overrides"][0]          # the price above min_prompt_tokens applies to the whole prompt
rows = [json.loads(x) for x in (root / "runs/E1-CTXH-H1/answers.jsonl").read_text(encoding="utf-8").splitlines()]
rows = [r for r in rows if r["prompt_tokens"] and r["cost_usd"] is not None]
if not rows:
    sys.exit("gate: the smoke run has no priced row; cannot project, stop and ask")
# chars per token from the smoke (context only, so r is a little low and the projection a little high)
ratio = sum(r["context_chars"] for r in rows) / sum(r["prompt_tokens"] for r in rows)
output_usd = sum(r["cost_usd"] - r["prompt_tokens"] * base_in for r in rows) / len(rows)
print(f"gate: chars/token {ratio:.2f}, output cost per question ${output_usd:.5f}, from {len(rows)} smoke rows")

def context_chars(corpus: str) -> int:
    art = load_corpus_artifacts(corpus, root / "corpora" / corpus / "ingest.json")
    return len(serialize_occurrence_graph(NetworkxGraphView(corpus, art.localized_sheets, art.resolution)).text)

def n_questions(corpus: str) -> int:
    return len((root / "questions" / corpus / "questions.jsonl").read_text(encoding="utf-8").splitlines())

# (corpus, arm): the high runs of all four sizes, the low runs of H1 and H10 at the same per-question price
plan = [(c, "high") for c in ("H1", "H3", "H10", "H30")] + [(c, "low") for c in ("H1", "H10")]
total = 0.0
for corpus, effort in plan:
    n = n_questions(corpus) - (len(rows) if (corpus, effort) == ("H1", "high") else 0)
    tokens = (context_chars(corpus) + 768) / ratio
    price = float(step["prompt"]) if tokens > int(step["min_prompt_tokens"]) else base_in
    cost = n * (tokens * price + output_usd)
    total += cost
    print(f"  {corpus:4s} {effort:4s} n={n:3d} prompt~{tokens:8.0f} tokens  ${cost:.3f}")
print(f"gate: projected remaining ContextRAG cost ${total:.2f} (limit ${limit:.2f})")
if total > limit:
    sys.exit(f"gate: projection above ${limit:.2f}. Ask the user; if approved: touch {root}/logs/steps/gate.ok")
EOF
}

ladder_ctx_runs() {  # B4 and B5
  step ctxh_H1_smoke ctx E1-CTXH-H1 H1 $IN/pin_agent_luna_final_high.json 0.03 smoke
  step gate gate
  step ctxh_H1 ctx E1-CTXH-H1 H1 $IN/pin_agent_luna_final_high.json 0.60 full
  step ctxh_H3 ctx E1-CTXH-H3 H3 $IN/pin_agent_luna_final_high.json 0.80 full
  step ctxh_H10 ctx E1-CTXH-H10 H10 $IN/pin_agent_luna_final_high.json 1.50 full
  step ctxh_H30 ctx E1-CTXH-H30 H30 $IN/pin_agent_luna_final_high.json 3.00 full
  step ctxl_H1 ctx E1-CTXL-H1 H1 $IN/pin_cypher_luna_low.json 0.20 full
  step ctxl_H10 ctx E1-CTXL-H10 H10 $IN/pin_cypher_luna_low.json 1.00 full
  for c in $LADDER; do step replay_ctxh_$c replay_ctx E1-CTXH-$c $c $IN/pin_agent_luna_final_high.json; done
  for c in H1 H10; do step replay_ctxl_$c replay_ctx E1-CTXL-$c $c $IN/pin_cypher_luna_low.json; done
}

cascade_and_report() {  # B6, both free. The cascade report is a cross-check; the EXP-0001 report is the result.
  set --
  for c in $LADDER; do
    set -- "$@" --corpus $c
    for pair in cypher-luna:E1-CYP agent-luna:E1-AG context-luna-high:E1-CTXH context-luna-low:E1-CTXL; do
      [ -d $S/runs/${pair#*:}-$c ] && set -- "$@" --run $c:${pair%%:*}=$S/runs/${pair#*:}-$c
    done
  done
  POL=src/plantgraph/qa/cascade/policies
  $P -m plantgraph.qa.cascade report --policy $POL/cascade_v3.json --policy $POL/always_g_luna.json \
    --policy $POL/always_c_luna.json --policy $IN/always_ctx_high.json --policy $IN/always_ctx_low.json \
    --questions-root $S/questions --corpora-root $S/corpora --cutoff-s 120 --out $S/cascade_report "$@" \
    > $S/logs/cascade_report.stdout.txt 2>&1 || echo "WARNING: cascade report failed, see $S/logs/cascade_report.stdout.txt"
  $P -m plantgraph.qa.exp0001 report --root $S > $S/logs/report.stdout.txt || die "the EXP-0001 report failed"
}

preflight
step guard replay_guard
step load_EX01 load_ex01
step ex01 ex01_run
ladder_tier_runs
step restore_d1000_b2 restore_d1000
ladder_agent_runs
ladder_ctx_runs
step report cascade_and_report
echo "=== replay checks (all must read 'identical')"; head -v $S/replays/*/replay_check.txt
echo "=== $(date +%T) done: $S/report/report.md ; EX01: score $S/ex01 blind sheet, then ex01-tally"
