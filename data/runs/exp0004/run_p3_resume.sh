#!/bin/sh
# EXP-0004 P3, resumed: the same steps as run_p3.sh for the corpora it did not finish (PAID, same caps).
#
# Why a second script: the first run stopped on 2026-11-04 at 21:37, when the session that launched it ended,
# during D1 on H1000g2V (log: p3_first.log). H100g2V and H100g2d100V were complete; no D4 call had been made
# on H1000g2V. run_p3.sh is hashed in the pre-registration, so it is not edited; this script repeats its
# per-corpus steps verbatim and checks the same pre-registration first.
#
#   sh data/runs/exp0004/run_p3_resume.sh
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

require_finished() {  # require_finished <corpus>: the first run completed this corpus
  for file in corpus.json pairs.json score.json d4_summary.json; do
    [ -f "$T/$1/$file" ] || die "$1 is not finished ($file missing); resume cannot skip it"
  done
  echo "$1: finished in the first run, skipped"
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
require_finished H100g2V
require_finished H100g2d100V
one_corpus H1000g2V 1000 5003 0.25 794
one_corpus H1000g2d100V 1000 5003 1.0 1923
$X report $E/dev/D100g2d100Vf $T/H100g2V $T/H100g2d100V $T/H1000g2V $T/H1000g2d100V --out $T/report.md
echo "=== $(date +%T) done: $T/report.md"
