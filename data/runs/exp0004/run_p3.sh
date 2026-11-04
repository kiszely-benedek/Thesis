#!/bin/sh
# EXP-0004 P3: D0, D1, D2 and D4 on the four test corpora (design 40-design/exp0004-v2.md §5, §6, §10).
# PAID: D4 calls GPT-6 Luna, each corpus under its own cap (PREREG.md §7). Run only after the pre-registration
# commit and the user's approval.
#
#   sh data/runs/exp0004/run_p3.sh
#
# Order: the small corpora first, so a broken run costs cents. Nothing here is tuned: D1 and D2 read the dev
# thresholds, D4 has none. Every output lands under data/runs/exp0004/test and is never overwritten.
set -eu
cd "$(git rev-parse --show-toplevel)"

E=data/runs/exp0004
T=$E/test
P=${EXP0004_PYTHON:-.venv/Scripts/python}
X="$P -m plantgraph.exp0004"
TAUS=$E/dev/D100g2d100Vf/taus.json
P90_CALL_USD=0.000171          # R5's p90 small Luna call (S7-CYP-H100g2/calls.jsonl, n = 497)

die() { echo "error: $*" >&2; exit 1; }

check_preregistration() {  # every registered file is unchanged and committed
  sha256sum -c --quiet $E/prereg/PREREG.sha256 || die "a pre-registered file changed"
  # shellcheck disable=SC2046
  [ -z "$(git status --porcelain -- $E/prereg $(sed 's/^[0-9a-f]* \*//' $E/prereg/PREREG.sha256))" ] \
    || die "the pre-registration is not committed"
  echo "pre-registration holds ($(wc -l < $E/prereg/PREREG.sha256) hashes)"
}

json_field() {  # json_field <file> <python expression on `d`>
  $P - "$1" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(eval(sys.argv[2]))
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

run_deciders() {  # run_deciders <corpus> <candidates>
  dir=$T/$1
  for decider in d0 d1 d2; do
    $X decide "$dir" --decider $decider --taus-json "$TAUS" > /dev/null
  done
  cap=$($P -c "print(round(1.5 * $2 * $P90_CALL_USD, 4))")
  echo "$1: D4 on $2 pairs, cap \$$cap"
  $X decide "$dir" --decider d4 --allow-paid-calls --max-spend-usd "$cap" > "$dir/d4_summary.json"
  $X score "$dir" > /dev/null
  for decider in d0 d2 d4; do $X links "$dir" --decider $decider > /dev/null; done
  echo "$1: done, spent \$$(json_field "$dir/d4_summary.json" 'd["llm"]["cost_usd_spent"]')"
}

one_corpus() {  # one_corpus <corpus> <sheets> <seed> <duplication> <expected candidates>
  [ ! -e "$T/$1" ] || die "$T/$1 exists; refusing to overwrite a measurement"
  echo "=== $(date +%T) $1"
  build_and_gate "$@"
  run_deciders "$1" "$5"
}

check_preregistration
mkdir -p "$T"
one_corpus H100g2V 100 5002 0.25 41
one_corpus H100g2d100V 100 5002 1.0 128
one_corpus H1000g2V 1000 5003 0.25 794
one_corpus H1000g2d100V 1000 5003 1.0 1923
$X report $E/dev/D100g2d100Vf $T/H100g2V $T/H100g2d100V $T/H1000g2V $T/H1000g2d100V --out $T/report.md
echo "=== $(date +%T) done: $T/report.md"
