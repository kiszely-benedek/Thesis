#!/bin/sh
# E8 point 3, second attempt for S7-CYP-H100g2 (ZERO paid calls).
#
# The first E8 pass (e8_identify.sh) stopped this replay at row 157 of 560 on a cache miss; all 157 rows equal R5.
# The same stop, at the same question, happened in INFRA-2 at e91abb5, before any EXP-0004 code: a query near the
# 30 s Cypher limit on a freshly loaded database. R5's own replay ran right after the run, on a warm database.
# This script reloads H100g2 exactly as R5 did and replays twice: pass 1 warms the page cache, pass 2 is the check.
#
#   E7_NEO4J_DATABASE=e7tune sh data/runs/exp0004/e8_warm_cypher_h100.sh
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh

R5=$X/sealed
S=data/runs/exp0004/e8/warm_h100
CACHE=data/runs/exp0004/e8/cache_s7_copy.sqlite
EXPERIMENT=EXP-0004-E8
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$R5/corpora; QROOT=$R5/questions
c=H100g2

[ ! -e "$S" ] || die "$S exists; refusing to overwrite"
[ -f "$CACHE" ] || die "expected the cache copy $CACHE from e8_identify.sh"
DEADLINE_S=$(setting_a_deadline)
use_database
mkdir -p "$S/logs" "$S/replays" "$CYP_CORPORA"
load_corpus "$c" 100 "$($EX test-seed --sheets 100)" plant_lines
for pass in 1 2; do
  replay "S7-CYP-$c" "$R5/runs/S7-CYP-$c" "$CACHE" "$DEADLINE_S" --corpus "$c:test" $(v2t_arm_options CYP-A) \
    --corpora-root "$CYP_CORPORA" --questions-root "$QROOT"
  mv "$S/replays/INF-S7-CYP-$c" "$S/replays/pass$pass"
  mv "$S/logs/INF-S7-CYP-$c.log" "$S/logs/pass$pass.log"
  echo "pass $pass: $(cat "$S/replays/pass$pass/replay_check.txt")"
done
echo "=== $(date +%T) done"
