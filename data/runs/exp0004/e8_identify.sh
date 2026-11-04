#!/bin/sh
# E8 identification (design 40-design/exp0004-v2.md §8, ADR-0063; ADR-0060 option 1B applied again). ZERO paid calls.
#
# Shows that V2T-A is unchanged now that EXP-0004's data-side code has landed in frozen directories:
#   point 2  no diff since E7 on any frozen file outside the data-side list below;
#   point 3  cache-only replays at concurrency 1 of S7-CYP-H100g2, S7-AG-H100g2, S7-AG-H1000g2 are byte-identical to
#            R5, and S7-CYP-H1000g2 is identical up to a timing stop (ADR-0062's gate, recorded, not a failure);
#   point 4  default-path golden: re-ingesting H100g2 and H1000g2 with no new flag gives the sealed ingest.json
#            (counts, resolution report, load plan, config), stage seconds excepted;
#   point 5  writes E8.commit and E8.sha256 (E7's list re-hashed) when points 2-4 hold.
# The sealed records are only read: the replays write under data/runs/exp0004/e8, from a copy of the R5 cache.
#
#   E7_NEO4J_DATABASE=e7tune sh data/runs/exp0004/e8_identify.sh
set -eu
cd "$(git rev-parse --show-toplevel)"
. data/runs/exp0007/lib.sh
. data/runs/exp0007/tune_lib.sh
. data/runs/exp0007/v2t_lib.sh

E=data/runs/exp0004
R5=$X/sealed
S=$E/e8                                   # every file this script writes lives here
CACHE=$S/cache_s7_copy.sqlite             # a copy: the sealed cache is never opened
EXPERIMENT=EXP-0004-E8
CYP_CORPORA=$S/neo4jplant; AG_CORPORA=$R5/corpora; QROOT=$R5/questions
CORPORA="H100g2 H1000g2"

# Design §8 point 1: the only frozen paths EXP-0004 may change (data side). ingest/ is data-building (ADR-0060).
DATA_SIDE="src/plantgraph/benchmark/tag_variants.py src/plantgraph/resolution/identity_
  src/plantgraph/resolution/resolver.py src/plantgraph/ingest/ src/plantgraph/qa/corpus.py
  data/runs/exp0007/inputs/listing_E7.json"

is_data_side() {  # is_data_side <path>: the path starts with one of the DATA_SIDE prefixes
  for prefix in $DATA_SIDE; do case $1 in "$prefix"*) return 0 ;; esac; done
  return 1
}

check_system_side_unchanged() {  # point 2
  e7=$(cat $X/E7.commit); bad=""
  # shellcheck disable=SC2086
  for path in $(git diff --name-only "$e7" HEAD -- $V2T_FROZEN_FILES $IN); do
    is_data_side "$path" || bad="$bad $path"
  done
  [ -z "$bad" ] || die "system-side files changed since E7 $e7:$bad"
  [ -z "$(git status --porcelain -- $V2T_FROZEN_FILES $IN)" ] || die "uncommitted changes in frozen paths"
  echo "point 2: no system-side diff since E7 $e7"
}

same_ingest() {  # same_ingest <new ingest.json> <sealed ingest.json>: equal once timings and the machine are left out
  $P - "$1" "$2" <<'PY'
import json, sys
# What differs between two loads of the same code by construction (checked on INFRA-2 against R5, 2026-11-04):
# stage and load timings, the environment record (time, machine, commit) and the store footprint (written only
# with --neo4j-home, which R5 did not pass).
def load(path):
    record = json.load(open(path, encoding="utf-8"))
    for volatile in ("stage_seconds", "environment", "store_footprint"):
        record.pop(volatile, None)
    report = record.get("load_report") or {}
    record["load_report"] = {k: v for k, v in report.items() if not k.endswith("_s")}
    return record
new, sealed = load(sys.argv[1]), load(sys.argv[2])
diff = sorted(k for k in set(new) | set(sealed) if new.get(k) != sealed.get(k))
print("identical" if not diff else "different: " + ", ".join(diff))
sys.exit(1 if diff else 0)
PY
}

load_and_compare() {  # point 4 for one corpus; the load stays in the database for the Cypher replay
  c=$1
  load_corpus "$c" "$(sealed_sheets "$c")" "$($EX test-seed --sheets "$(sealed_sheets "$c")")" plant_lines \
    $(sealed_dup_args "$c")
  same_ingest "$CYP_CORPORA/$c/ingest.json" "$R5/neo4jplant/$c/ingest.json" > "$S/golden_$c.txt" \
    || die "point 4 failed on $c: $(cat "$S/golden_$c.txt")"
  echo "point 4 $c: $(cat "$S/golden_$c.txt")"
}

replays() {  # point 3 for one corpus, R5's own source runs, setting A
  c=$1
  replay "S7-CYP-$c" "$R5/runs/S7-CYP-$c" "$CACHE" "$DEADLINE_S" --corpus "$c:test" $(v2t_arm_options CYP-A) \
    --corpora-root "$CYP_CORPORA" --questions-root "$QROOT"
  replay "S7-AG-$c" "$R5/runs/S7-AG-$c" "$CACHE" "$DEADLINE_S" --corpus "$c:test" $(v2t_arm_options AG) \
    --corpora-root "$AG_CORPORA" --questions-root "$QROOT"
}

rows_equal_so_far() {  # rows_equal_so_far <replay dir> <source run dir>: every replayed row equals the run's row
  $P - "$1/answers.jsonl" "$2/answers.jsonl" <<'PY'
import json, sys
def rows(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        row = json.loads(line)
        for volatile in ("run_id", "latency_s", "trace"):
            row.pop(volatile, None)
        out[row["question_id"]] = row
    return out
replayed, source = rows(sys.argv[1]), rows(sys.argv[2])
bad = [q for q, row in replayed.items() if source.get(q) != row]
print(f"{len(replayed)} rows replayed, {len(bad)} differ from the run")
sys.exit(1 if bad else 0)
PY
}

check_replays() {  # point 3's gate
  for id in INF-S7-CYP-H100g2 INF-S7-AG-H100g2 INF-S7-AG-H1000g2; do
    [ "$(cat "$S/replays/$id/replay_check.txt")" = identical ] || die "point 3 failed: $id is not identical"
  done
  id=INF-S7-CYP-H1000g2
  if [ "$(cat "$S/replays/$id/replay_check.txt")" != identical ]; then
    rows_equal_so_far "$S/replays/$id" "$R5/runs/S7-CYP-H1000g2" > "$S/replays/$id/rows_check.txt" \
      || die "point 3 failed: $id has a row that differs from R5 ($(cat "$S/replays/$id/rows_check.txt"))"
    echo "point 3: $id stopped early (timing, ADR-0062): $(cat "$S/replays/$id/rows_check.txt")"
  fi
  echo "point 3: replays hold"
}

write_freeze() {  # point 5
  git rev-parse HEAD > $E/E8.commit
  echo "V2T-A" > $E/E8.system
  # E7's list re-hashed at E8 (the four data-side files now hash differently, by design)
  sed 's/^[0-9a-f]* \*//' $X/E7.sha256 | grep -v '^data/runs/exp0007/E7\.' | xargs sha256sum -b > $E/E8.sha256
  sha256sum -b $E/E8.commit $E/E8.system >> $E/E8.sha256
  echo "point 5: $E/E8.commit $(cat $E/E8.commit), $(wc -l < $E/E8.sha256) hashes"
}

[ ! -e "$S" ] || die "$S exists; refusing to overwrite an identification"
check_system_side_unchanged
DEADLINE_S=$(setting_a_deadline)
use_database
mkdir -p "$S/logs" "$S/replays" "$CYP_CORPORA"
cp "$R5/cache_s7.sqlite" "$CACHE"
for corpus in $CORPORA; do
  load_and_compare "$corpus"
  replays "$corpus"
done
echo "=== replay checks"; head -v "$S"/replays/*/replay_check.txt
check_replays
write_freeze
echo "=== $(date +%T) done"
