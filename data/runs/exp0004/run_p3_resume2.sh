#!/bin/sh
# EXP-0004 P3, second resume (PAID, within the registered caps).
#
# Why: run_p3_resume.sh stopped on 2026-11-05 at about 11:28 during D4 on H1000g2V, after 295 of 794 answers,
# when one OpenRouter response came back without `choices` (TypeError in llm/client.py; log: p3_resume.log).
# llm/ is frozen (E8), so it is not patched. D4 is re-run instead: the 295 answers replay from the cache for free
# and the missing ones are asked again, as the client's own retry does for a transient error. At most three
# attempts per corpus; each attempt's cap is the registered cap minus the live spend already in the call log,
# so the total never passes 1.5 x candidates x $0.000171.
#
#   sh data/runs/exp0004/run_p3_resume2.sh
set -eu
cd "$(git rev-parse --show-toplevel)"

E=data/runs/exp0004
T=$E/test
P=${EXP0004_PYTHON:-.venv/Scripts/python}
X="$P -m plantgraph.exp0004"
TAUS=$E/dev/D100g2d100Vf/taus.json
P90_CALL_USD=0.000171          # R5's p90 small Luna call (S7-CYP-H100g2/calls.jsonl, n = 497)
ATTEMPTS=3

die() { echo "error: $*" >&2; exit 1; }

check_preregistration() {  # every registered file is unchanged and committed
  sha256sum -c --quiet $E/prereg/PREREG.sha256 || die "a pre-registered file changed"
  # shellcheck disable=SC2046
  [ -z "$(git status --porcelain -- $E/prereg $(sed 's/^[0-9a-f]* \*//' $E/prereg/PREREG.sha256))" ] \
    || die "the pre-registration is not committed"
  echo "pre-registration holds ($(wc -l < $E/prereg/PREREG.sha256) hashes)"
}

require_finished() {  # require_finished <corpus>: an earlier run completed this corpus
  for file in corpus.json pairs.json score.json d4_summary.json; do
    [ -f "$T/$1/$file" ] || die "$1 is not finished ($file missing); resume cannot skip it"
  done
  echo "$1: finished earlier, skipped"
}

json_field() {  # json_field <file> <python expression on `d`>
  $P - "$1" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(eval(sys.argv[2]))
PY
}

live_spend() {  # live_spend <call log>: USD of the live (not cached) calls already logged, 0 without a log
  [ -f "$1" ] || { echo 0; return; }
  $P - "$1" <<'PY'
import json, sys
total = 0.0
for line in open(sys.argv[1], encoding="utf-8"):
    response = json.loads(line).get("response") or {}
    if not response.get("from_cache"):
        total += response.get("cost_usd") or 0.0
print(round(total, 6))
PY
}

build_and_gate() {  # build_and_gate <corpus> <sheets> <seed> <duplication> <expected candidates>
  dir=$T/$1
  $X build --corpus-id "$1" --target-sheets "$2" --seed "$3" --duplication-rate "$4" \
    --families format naming --out "$dir" > /dev/null
  n=$(json_field "$dir/corpus.json" 'd["description"]["blocking"]["n_candidates"]')
  completeness=$(json_field "$dir/corpus.json" 'd["description"]["blocking"]["pair_completeness"]')
  [ "$n" = "$5" ] || die "$1: expected $5 candidates (IDBLOCK-01), got $n"
  $P -c "import sys; sys.exit(0 if $completeness >= 0.99 else 1)" || die "$1: I0 fails, completeness $completeness"
  echo "$1: $n candidates, completeness $completeness (I0 holds)"
}

free_deciders() {  # free_deciders <corpus>: D0, D1, D2, each only if its decision is not there yet
  for decider in d0 d1 d2; do
    [ -f "$T/$1/decisions/$decider.json" ] && continue
    $X decide "$T/$1" --decider $decider --taus-json "$TAUS" > /dev/null
  done
}

d4_with_retries() {  # d4_with_retries <corpus> <candidates>
  dir=$T/$1; log=$dir/decisions/d4_llm_calls.jsonl
  cap=$($P -c "print(round(1.5 * $2 * $P90_CALL_USD, 4))")
  attempt=1
  while [ $attempt -le $ATTEMPTS ]; do
    left=$($P -c "print(round($cap - $(live_spend "$log"), 6))")
    echo "$1: D4 attempt $attempt on $2 pairs, cap \$$cap, left \$$left"
    if $X decide "$dir" --decider d4 --allow-paid-calls --max-spend-usd "$left" > "$dir/d4_summary.json"; then
      return 0
    fi
    attempt=$((attempt + 1))
  done
  die "$1: D4 failed $ATTEMPTS times"
}

finish_corpus() {  # finish_corpus <corpus> <candidates>
  free_deciders "$1"
  d4_with_retries "$1" "$2"
  $X score "$T/$1" > /dev/null
  for decider in d0 d2 d4; do $X links "$T/$1" --decider $decider > /dev/null; done
  echo "$1: done, live spend \$$(live_spend "$T/$1/decisions/d4_llm_calls.jsonl") (cap \$$($P -c "print(round(1.5 * $2 * $P90_CALL_USD, 4))"))"
}

check_preregistration
require_finished H100g2V
require_finished H100g2d100V
echo "=== $(date +%T) H1000g2V (continued: corpus and D0-D2 from run_p3_resume.sh)"
finish_corpus H1000g2V 794
[ ! -e "$T/H1000g2d100V" ] || die "$T/H1000g2d100V exists; refusing to overwrite a measurement"
echo "=== $(date +%T) H1000g2d100V"
build_and_gate H1000g2d100V 1000 5003 1.0 1923
finish_corpus H1000g2d100V 1923
$X report $E/dev/D100g2d100Vf $T/H100g2V $T/H100g2d100V $T/H1000g2V $T/H1000g2d100V --out $T/report.md
echo "=== $(date +%T) done: $T/report.md"
