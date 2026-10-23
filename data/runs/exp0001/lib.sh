# Shared helpers of the EXP-0001 scripts (ADR-0054): sourced, never run on its own.
# Callers cd to the repository root first. Functions follow data/runs/sealed/run_sealed.sh.
S=data/runs/exp0001; P=.venv/Scripts/python; IN=$S/inputs; SEALED=data/runs/sealed
H="$USERPROFILE/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-d140-455c-a624-5850769f9dbc"
CACHE=$S/cache_exp0001.sqlite
# The only src paths that may differ from F1 (the sealed run's freeze): T's question-side files + EXP-0001.
ALLOWED='^(src/plantgraph/qa/questions/|src/plantgraph/qa/harness/(family_meta|need_gold)\.py$|src/plantgraph/qa/models\.py$|src/plantgraph/qa/exp0001/)'
die() { echo "ERROR: $*" >&2; exit 1; }

fetch_listing() {  # fetch_listing <out>: Luna's `openai` endpoint, reduced to what price and fit depend on
  $P - "$1" <<'EOF'
import json, sys, urllib.request

URL = "https://openrouter.ai/api/v1/models/openai/gpt-6-luna/endpoints"
with urllib.request.urlopen(URL, timeout=60) as response:
    endpoints = json.load(response)["data"]["endpoints"]
chosen = [e for e in endpoints if e.get("tag") == "openai"]
if len(chosen) != 1:
    sys.exit(f"expected exactly one endpoint tagged 'openai', found {len(chosen)}")
e = chosen[0]
steps = [{k: o[k] for k in ("min_prompt_tokens", "prompt", "completion")} for o in e["pricing"]["overrides"]]
keep = {
    "tag": e["tag"], "context_length": e["context_length"], "max_prompt_tokens": e["max_prompt_tokens"],
    "pricing": {"prompt": e["pricing"]["prompt"], "completion": e["pricing"]["completion"], "overrides": steps},
}
with open(sys.argv[1], "w", encoding="utf-8") as out:
    json.dump(keep, out, indent=1, sort_keys=True)
EOF
}

preflight() {
  [ -z "$(git status --porcelain)" ] || die "the working tree is not clean"
  [ "$(git rev-parse HEAD)" = "$(cat $S/E.commit)" ] || die "HEAD is not the freeze commit E"
  sha256sum -c --quiet $S/E.sha256 || die "an input, question set or document changed since E"
  for f in params_agent_low params_cypher_plant pin_agent_luna_final_high pin_cypher_luna_low; do
    cmp -s $IN/$f.json $SEALED/inputs/$f.json || die "inputs/$f.json is no longer the sealed run's file"
  done
  bad=$(git diff --name-only "$(cat $SEALED/F1.commit)" HEAD -- src | grep -v -E "$ALLOWED" || true)
  [ -z "$bad" ] || die "frozen paths changed since F1: $bad"
  mkdir -p $S/logs/steps $S/runs $S/replays $S/neo4jplant
  fetch_listing $S/logs/listing_run.json || die "could not read OpenRouter's listing for Luna"
  cmp -s $S/logs/listing_run.json $IN/listing_E.json \
    || die "Luna's price or window changed since E (diff $S/logs/listing_run.json $IN/listing_E.json): re-estimate, ask the user"
}

step() {  # step <name> <command...>: run once; a rerun of the script skips the steps that finished
  name=$1; shift
  if [ -e "$S/logs/steps/$name.ok" ]; then echo "--- skip $name (done)"; return 0; fi
  "$@"
  touch "$S/logs/steps/$name.ok"
}

sheets_of() { case $1 in H1) echo 1 ;; H3) echo 3 ;; H10) echo 10 ;; H30) echo 30 ;; *) die "no sheet target for $1" ;; esac; }
seed_of() { if [ "$1" = H1 ]; then cat $S/H1.seed; else echo 3; fi; }

n_sheets() { $P -c "import json,sys;print(json.load(open(sys.argv[1]))['counts']['n_sheets'])" "$1"; }

load_ladder() {  # load_ladder <corpus>: this corpus alone in Neo4j, plant profile, fresh database
  echo "=== $(date +%T) load $1"
  $P -m plantgraph.ingest synthetic --headline --target-sheets "$(sheets_of $1)" --seed "$(seed_of $1)" \
    --store-profile plant --corpus-id "$1" --fresh-database --neo4j-home "$H" --out "$S/neo4jplant/$1" \
    > "$S/logs/load_$1.json" 2> "$S/logs/load_$1.err" || die "loading $1 failed, see $S/logs/load_$1.err"
  # the loaded corpus must be the one the questions were drawn from (same preset, same seed)
  [ "$(n_sheets $S/neo4jplant/$1/ingest.json)" = "$(n_sheets $S/corpora/$1/ingest.json)" ] \
    || die "$1: the loaded corpus has a different sheet count than the question corpus"
}

restore_d1000() {
  echo "=== $(date +%T) restore D1000 (plant profile) alone in Neo4j"
  $P -m plantgraph.ingest synthetic --headline --target-sheets 1000 --seed 1 --store-profile plant \
    --corpus-id D1000 --fresh-database > $S/logs/restore_D1000.json 2> $S/logs/restore_D1000.err \
    || die "restoring D1000 failed, see $S/logs/restore_D1000.err"
}

health() {  # health <run-dir> <stage>: tier runs; outcome counts only, never correctness
  $P - "$1/answers.jsonl" <<'EOF'
import collections, json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
counts = collections.Counter(row["outcome"] for row in rows)
print(f"    {len(rows)} rows: {dict(counts)}")
broken = counts.get("PROVIDER_ERROR", 0) + counts.get("PARSE_FAILURE", 0)
if not rows or broken > 0.1 * len(rows) or counts.get("RETRIEVAL_ERROR", 0) > 0.6 * len(rows):
    sys.exit("technical fault: read the run log; design section 9.4 before anything else")
EOF
}

health_ctx() {  # health_ctx <run-dir> <stage>: PARSE_FAILURE / TIMED_OUT / DID_NOT_FIT are results here
  $P - "$1/answers.jsonl" "$2" <<'EOF'
import collections, json, sys
rows = [json.loads(line) for line in open(sys.argv[1], encoding="utf-8")]
counts = collections.Counter(row["outcome"] for row in rows)
print(f"    {len(rows)} rows: {dict(counts)}")
if not rows or counts.get("PROVIDER_ERROR", 0) > 0.1 * len(rows):
    sys.exit("technical fault: PROVIDER_ERROR above 10 %; design section 9.4")
if sys.argv[2] == "smoke" and counts.get("PARSE_FAILURE", 0) > 0.5 * len(rows):
    sys.exit("PARSE_FAILURE above 50 % in the smoke stage: a pipeline fault, stop and ask the user")
EOF
}

finish() {  # finish <run-id> <exit-code> <stage> <health-function>
  case "$2:$3" in
    0:*) echo "    $1: complete" ;;
    3:smoke) echo "    $1: smoke stage done" ;;
    3:full) die "$1 reached its spend cap: ask the user before resuming with a higher cap" ;;
    *) die "$1 failed with exit code $2, see $S/logs/$1.log" ;;
  esac
  $4 "$S/runs/$1" "$3"
}

cypher() {  # cypher <run-id> <corpus> <cap> <stage>
  echo "=== $(date +%T) $1 ($4, cap \$$3)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0001 --corpus "$2:test" \
    --strategy cypher_rag_plant --strategy-params-json $IN/params_cypher_plant.json \
    --pin-json $IN/pin_cypher_luna_low.json --corpora-root $S/neo4jplant --questions-root $S/questions \
    --runs-root $S/runs --cache-path $CACHE --allow-paid-calls --cost-per-question-usd 0.001 \
    --max-spend-usd "$3" --concurrency 4 --question-deadline-s 120 >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$4" health
}

agent() {  # agent <run-id> <corpus> <cap> <stage>
  echo "=== $(date +%T) $1 ($4, cap \$$3)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0001 --corpus "$2:test" \
    --strategy graph_agent_low_steps --strategy-params-json $IN/params_agent_low.json \
    --pin-json $IN/pin_agent_luna_final_high.json --corpora-root $S/corpora --questions-root $S/questions \
    --runs-root $S/runs --cache-path $CACHE --allow-paid-calls --cost-per-question-usd 0.003 \
    --max-spend-usd "$3" --concurrency 4 --question-deadline-s 120 >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$4" health
}

ctx() {  # ctx <run-id> <corpus> <pin> <cap> <stage> [<questions-root> <corpora-root> <concurrency>]
  echo "=== $(date +%T) $1 ($5, cap \$$4)"; rc=0
  $P -m plantgraph.qa.harness --run-id "$1" --experiment EXP-0001 --corpus "$2:test" --strategy context_rag \
    --pin-json "$3" --corpora-root "${7:-$S/corpora}" --questions-root "${6:-$S/questions}" \
    --runs-root $S/runs --cache-path $CACHE --allow-paid-calls --cost-per-question-usd 0.02 \
    --max-spend-usd "$4" --concurrency "${8:-4}" --question-deadline-s 300 >> "$S/logs/$1.log" 2>&1 || rc=$?
  finish "$1" $rc "$5" health_ctx
}

replay() {  # replay <run-id> <run-dir> <cache> <deadline-s> <harness options...>: cache only, concurrency 1
  orig=$1; id=INF-$1; dir=$2; cache=$3; deadline=$4; shift 4; rc=0
  echo "=== $(date +%T) replay $id (no --allow-paid-calls: cache only)"
  rm -rf "$S/replays/$id"
  $P -m plantgraph.qa.harness --run-id "$id" --experiment EXP-0001-REPLAY --runs-root $S/replays \
    --cache-path "$cache" --concurrency 1 --question-deadline-s "$deadline" "$@" > "$S/logs/$id.log" 2>&1 || rc=$?
  # a replay differs from the run only in its id and in where each answer came from
  sed -e "s/^{\"run_id\":\"$id\"/{\"run_id\":\"$orig\"/" -e 's/"from_cache":false/"from_cache":true/g' \
    "$S/replays/$id/answers.jsonl" > "$S/replays/$id/.normalised" 2>/dev/null || true
  if [ $rc -eq 0 ] && sed 's/"from_cache":false/"from_cache":true/g' "$dir/answers.jsonl" \
      | cmp -s - "$S/replays/$id/.normalised"; then echo identical > "$S/replays/$id/replay_check.txt"
  else echo "different_or_miss rc=$rc" > "$S/replays/$id/replay_check.txt"; fi
  rm -f "$S/replays/$id/.normalised"; echo "    $id: $(cat $S/replays/$id/replay_check.txt)"
}

replay_cypher() {  # replay_cypher <run-id> <corpus>
  replay "$1" "$S/runs/$1" $CACHE 120 --corpus "$2:test" --strategy cypher_rag_plant \
    --strategy-params-json $IN/params_cypher_plant.json --pin-json $IN/pin_cypher_luna_low.json \
    --corpora-root $S/neo4jplant --questions-root $S/questions
}

replay_agent() {  # replay_agent <run-id> <corpus>
  replay "$1" "$S/runs/$1" $CACHE 120 --corpus "$2:test" --strategy graph_agent_low_steps \
    --strategy-params-json $IN/params_agent_low.json --pin-json $IN/pin_agent_luna_final_high.json \
    --corpora-root $S/corpora --questions-root $S/questions
}

replay_ctx() {  # replay_ctx <run-id> <corpus> <pin> [<questions-root> <corpora-root>]
  replay "$1" "$S/runs/$1" $CACHE 300 --corpus "$2:test" --strategy context_rag --pin-json "$3" \
    --corpora-root "${5:-$S/corpora}" --questions-root "${4:-$S/questions}"
}

replay_guard() {  # design 6.4: the F1 agent path still reproduces the sealed ST-AG-H100 byte for byte
  replay ST-AG-H100 $SEALED/runs/ST-AG-H100 $SEALED/cache_sealed.sqlite 120 --corpus H100:test \
    --strategy graph_agent_low_steps --strategy-params-json $IN/params_agent_low.json \
    --pin-json $IN/pin_agent_luna_final_high.json --corpora-root $SEALED/corpora \
    --questions-root $SEALED/questions
  [ "$(cat $S/replays/INF-ST-AG-H100/replay_check.txt)" = identical ] \
    || die "replay guard: ST-AG-H100 is not reproduced from the sealed cache; do not spend anything"
}
