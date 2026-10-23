#!/bin/sh
# Sealed test run, EXP-0002-H100 / EXP-0002-H1000 (ADR-0053). PAID.
# Do NOT run pytest while this runs. One corpus in Neo4j at a time; ends with D1000 (plant) loaded.
set -eu
S=data/runs/sealed; P=.venv/Scripts/python; IN=$S/inputs
H="$USERPROFILE/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
CACHE=$S/cache_sealed.sqlite
ALLOWED='^(src/plantgraph/qa/questions/|src/plantgraph/qa/harness/(family_meta|need_gold)\.py$|src/plantgraph/qa/models\.py$)'
die() { echo "ERROR: $*" >&2; exit 1; }

preflight() {
  [ -z "$(git status --porcelain)" ] || die "the working tree is not clean"
  [ "$(git rev-parse HEAD)" = "$(cat $S/T.commit)" ] || die "HEAD is not the test-data commit T"
  sha256sum -c --quiet $S/F1.sha256 || die "a frozen input changed since F1"
  sha256sum -c --quiet $S/T.sha256 || die "a test input changed since it was generated"
  bad=$(git diff --name-only "$(cat $S/F1.commit)" HEAD -- src | grep -v -E "$ALLOWED" || true)
  [ -z "$bad" ] || die "frozen paths changed since F1: $bad"
  mkdir -p $S/logs $S/runs $S/replays $S/neo4jplant
}

load() {  # load <corpus> <sheets> <seed>: this corpus alone in Neo4j, plant profile, fresh database
  echo "=== $(date +%T) load $1"
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$2" --seed "$3" --store-profile plant \
    --corpus-id "$1" --fresh-database --neo4j-home "$H" --out "$S/neo4jplant/$1" \
    > "$S/logs/load_$1.json" 2> "$S/logs/load_$1.err" || die "loading $1 failed, see $S/logs/load_$1.err"
}

health() {  # health <run-dir>: outcome counts only, never correctness; stops on a technical fault
  $P - "$1/answers.jsonl" <<'EOF'
import collections, json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
counts = collections.Counter(row["outcome"] for row in rows)
print(f"    {len(rows)} rows: {dict(counts)}")
broken = counts.get("PROVIDER_ERROR", 0) + counts.get("PARSE_FAILURE", 0)
if not rows or broken > 0.1 * len(rows) or counts.get("RETRIEVAL_ERROR", 0) > 0.6 * len(rows):
    sys.exit("technical fault: read the run log; see design section 10 before anything else")
EOF
}

finish() {  # finish <run-id> <exit-code> <stage>: a smoke stage ends at its cap (3); a full stage must not
  case "$2:$3" in
    0:*) echo "    $1: complete" ;;
    3:smoke) echo "    $1: smoke stage done" ;;
    3:full) die "$1 reached its spend cap: ask the user before resuming with a higher cap" ;;
    *) die "$1 failed with exit code $2, see $S/logs/$1.log" ;;
  esac
  health "$S/runs/$1"
}

cypher() {  # cypher <run-id> <corpus> <cap> <stage>
  echo "=== $(date +%T) $1 ($4, cap \$$3)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0002 --corpus "$2:test" \
    --strategy cypher_rag_plant --strategy-params-json $IN/params_cypher_plant.json \
    --pin-json $IN/pin_cypher_luna_low.json --corpora-root $S/neo4jplant --questions-root $S/questions \
    --runs-root $S/runs --cache-path $CACHE --allow-paid-calls --cost-per-question-usd 0.001 \
    --max-spend-usd "$3" --concurrency 4 --question-deadline-s 120 >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$4"
}

agent() {  # agent <run-id> <corpus> <cap> <stage> [<questions-root> <cache> <concurrency>]
  echo "=== $(date +%T) $1 ($4, cap \$$3)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0002 --corpus "$2:test" \
    --strategy graph_agent_low_steps --strategy-params-json $IN/params_agent_low.json \
    --pin-json $IN/pin_agent_luna_final_high.json --corpora-root $S/corpora \
    --questions-root "${5:-$S/questions}" --runs-root $S/runs --cache-path "${6:-$CACHE}" --allow-paid-calls \
    --cost-per-question-usd 0.003 --max-spend-usd "$3" --concurrency "${7:-4}" --question-deadline-s 120 \
    >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$4"
}

replay() {  # replay <run-id> <strategy> <params> <pin> <corpora-root> <corpus>: cache-only, concurrency 1
  id=INF-$1; rc=0
  echo "=== $(date +%T) replay $id (no --allow-paid-calls: cache only)"
  $P -m plantgraph.qa.harness --run-id "$id" --experiment EXP-0002-REPLAY --corpus "$6:test" \
    --strategy "$2" --strategy-params-json "$3" --pin-json "$4" --corpora-root "$5" \
    --questions-root $S/questions --runs-root $S/replays --cache-path $CACHE --concurrency 1 \
    --question-deadline-s 120 > "$S/logs/$id.log" 2>&1 || rc=$?
  sed -e "s/^{\"run_id\":\"$id\"/{\"run_id\":\"$1\"/" -e 's/"from_cache":false/"from_cache":true/g' \
    "$S/replays/$id/answers.jsonl" > "$S/replays/$id/.normalised" 2>/dev/null || true
  if [ $rc -eq 0 ] && sed 's/"from_cache":false/"from_cache":true/g' "$S/runs/$1/answers.jsonl" \
      | cmp -s - "$S/replays/$id/.normalised"; then echo identical > "$S/replays/$id/replay_check.txt"
  else echo "different_or_miss rc=$rc" > "$S/replays/$id/replay_check.txt"; fi
  rm -f "$S/replays/$id/.normalised"; echo "    $id: $(cat $S/replays/$id/replay_check.txt)"
}

preflight
load H100 100 2
cypher ST-CYP-H100 H100 0.02 smoke
cypher ST-CYP-H100 H100 0.50 full
replay ST-CYP-H100 cypher_rag_plant $IN/params_cypher_plant.json $IN/pin_cypher_luna_low.json $S/neo4jplant H100
load H1000 1000 0
cypher ST-CYP-H1000 H1000 0.50 full
replay ST-CYP-H1000 cypher_rag_plant $IN/params_cypher_plant.json $IN/pin_cypher_luna_low.json $S/neo4jplant H1000
agent ST-AG-H100 H100 0.02 smoke
agent ST-AG-H100 H100 0.80 full
agent ST-AG-H1000 H1000 1.00 full
agent ST-AG-H1000-C1 H1000 0.10 full $S/questions_c1 $S/cache_sealed_c1.sqlite 1
replay ST-AG-H100 graph_agent_low_steps $IN/params_agent_low.json $IN/pin_agent_luna_final_high.json $S/corpora H100
replay ST-AG-H1000 graph_agent_low_steps $IN/params_agent_low.json $IN/pin_agent_luna_final_high.json $S/corpora H1000
echo "=== $(date +%T) restore D1000 (plant profile) alone in Neo4j"
$P -m plantgraph.ingest synthetic --headline --target-sheets 1000 --seed 1 --store-profile plant \
  --corpus-id D1000 --fresh-database > $S/logs/restore_D1000.json 2> $S/logs/restore_D1000.err \
  || die "restoring D1000 failed"
POL=src/plantgraph/qa/cascade/policies
$P -m plantgraph.qa.cascade report --sealed-claims \
  --policy $POL/cascade_v3.json --policy $POL/always_g_luna.json --policy $POL/always_c_luna.json \
  --policy $POL/cascade_v3_iso.json --corpus H100 --corpus H1000 \
  --questions-root $S/questions --corpora-root $S/corpora --cutoff-s 120 --out $S/report \
  --run H100:cypher-luna=$S/runs/ST-CYP-H100 --run H100:agent-luna=$S/runs/ST-AG-H100 \
  --run H1000:cypher-luna=$S/runs/ST-CYP-H1000 --run H1000:agent-luna=$S/runs/ST-AG-H1000 \
  > $S/logs/report.stdout.txt || die "report failed"
echo "=== $(date +%T) done: $S/report/report.md"
