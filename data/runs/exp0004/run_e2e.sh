#!/bin/sh
# EXP-0004 end-to-end arm (design 40-design/exp0004-v2.md section 7, PREREG.md section 6): the frozen system
# V2T-A answers R5's sealed H1000g2 questions on H1000g2V, loaded once per resolver arm d0, d2 or d4.
# Run one arm at a time; one corpus in Neo4j (the database E7_NEO4J_DATABASE; never the demo's `neo4j`).
# Do NOT run pytest while this runs.
#
#   sh data/runs/exp0004/run_e2e.sh dry d0
#       FREE. Checks E8 and the pre-registration, loads the arm's corpus, writes the re-homed questions and
#       their proof, then replays both tiers on a COPY of the sealed cache with a fake transport and lists
#       every cache miss. Writes data/runs/exp0004/e2e/d0/dry/caps.json (cap = misses x R5 cost x 1.5).
#   sh data/runs/exp0004/run_e2e.sh paid d0 --allow-paid-calls --max-spend-usd X [--resume]
#       PAID. Needs the dry run of the same arm; X may not exceed its total cap. Reloads the corpus, runs
#       the Cypher tier and the agent tier from a fresh copy of the sealed cache under X, then replays both
#       from the cache. Refuses to overwrite an existing live/ folder (--resume continues a stopped one).
#
# Nothing under data/runs/exp0007/sealed is ever written: the cache is copied, the questions are copied.
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh
E=${E2E_ROOT:-data/runs/exp0004}   # E2E_ROOT: only the script tests
. "$E/e2e_lib.sh"

usage() { die "usage: run_e2e.sh dry <d0|d2|d4>   |   run_e2e.sh paid <d0|d2|d4> --allow-paid-calls --max-spend-usd X [--resume]"; }

MODE=${1:-}; ARM=${2:-}
[ -n "$MODE" ] && [ -n "$ARM" ] || usage
shift 2
ALLOW_PAID=no; MAX_SPEND=; RESUME=no
while [ $# -gt 0 ]; do
  case $1 in
    --allow-paid-calls) ALLOW_PAID=yes ;;
    --max-spend-usd) [ $# -ge 2 ] || die "--max-spend-usd needs a value"; MAX_SPEND=$2; shift ;;
    --resume) RESUME=yes ;;
    *) die "unknown option $1" ;;
  esac
  shift
done
LINKS=$(e2e_links_file "$ARM")
case $MODE in
  dry)
    [ "$ALLOW_PAID" = no ] && [ -z "$MAX_SPEND" ] && [ "$RESUME" = no ] \
      || die "dry mode takes no option: it is free and never overwrites" ;;
  paid)
    [ "$ALLOW_PAID" = yes ] || die "paid mode: pass --allow-paid-calls (the free check is: run_e2e.sh dry $ARM)"
    [ -n "$MAX_SPEND" ] || die "paid mode: --max-spend-usd X is required (at most the dry run's total cap)" ;;
  *) usage ;;
esac

A=$E/e2e/$ARM
[ -f "$LINKS" ] || die "no links file $LINKS: run P3 (run_p3.sh) first"
require_e8_freeze
require_prereg_holds
DEADLINE_S=$(setting_a_deadline)
SEALED_CACHE=$X/sealed/cache_s7.sqlite
[ -f "$SEALED_CACHE" ] || die "no sealed cache $SEALED_CACHE"
EXPERIMENT=EXP-0004-E2E
QROOT=$A/questions
E7_NEO4J_DATABASE=${E7_NEO4J_DATABASE:-e7tune}; export E7_NEO4J_DATABASE   # a temporary database, never `neo4j`
use_database

if [ "$MODE" = dry ]; then
  { [ ! -e "$A/dry" ] && [ ! -e "$QROOT" ] && [ ! -e "$A/rehome_proof.json" ]; } \
    || die "$A already holds a dry run; refusing to overwrite (move it away deliberately)"
  S=$A/dry; CYP_CORPORA=$S/corpora; AG_CORPORA=$S/corpora; CACHE=$S/cache_copy.sqlite
  mkdir -p "$S/logs/steps" "$CYP_CORPORA"
  cp "$SEALED_CACHE" "$CACHE"           # a copy: the dry run writes its fake replies into it
  e2e_dry_ids
  step load e2e_load "$LINKS"
  step rehome e2e_rehome
  step dry_cypher e2e_dry_tier CYP-A "$E2E_DRY_CYP"
  step dry_agent e2e_dry_tier AG "$E2E_DRY_AG"
  step caps e2e_dry_caps
  step restore_d1000 restore_d1000
  echo "=== $(date +%T) dry run done: $S/caps.json (show these caps to the user before any paid run)"
  exit 0
fi

# paid mode
[ -f "$A/dry/caps.json" ] || die "no $A/dry/caps.json: run the dry mode of $ARM first"
S=$A/live; CYP_CORPORA=$S/corpora; AG_CORPORA=$S/corpora; CACHE=$S/cache_e2e.sqlite
if [ -e "$S" ] && [ "$RESUME" = no ]; then die "$S exists; refusing to overwrite (--resume continues a stopped run)"; fi
e2e_check_questions
e2e_split_caps "$A/dry/caps.json" "$MAX_SPEND"
check_listing "$(listing_file)"
mkdir -p "$S/logs/steps" "$CYP_CORPORA" "$S/runs" "$S/replays"
[ -f "$CACHE" ] || cp "$SEALED_CACHE" "$CACHE"   # a fresh copy of the sealed cache: R5's answers replay free
# the database may hold another arm since the dry run, so the corpus is loaded again
step load e2e_load "$LINKS"
e2e_live_tier CYP-A "E2E-CYP-$E2E_CORPUS-$ARM"
e2e_live_tier AG "E2E-AG-$E2E_CORPUS-$ARM"
step restore_d1000 restore_d1000
echo "=== replay checks"; head -v "$S"/replays/*/replay_check.txt
echo "=== $(date +%T) done: $S/runs (answers), $S/replays (cache-only replays)"
