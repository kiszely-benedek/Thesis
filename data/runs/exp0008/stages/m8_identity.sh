# M8: EXP-0004 cross-sheet identity. Sourced by run_all.sh.
#
#   M8a (P3, I0-I4)  on each V corpus of the p3 plan: the registered four-corpus set on plant 1 and the other
#                    four 1,000-sheet V corpora, whose D4 links P4 needs anyway (those are reported descriptively,
#                    not judged). Deciders D0, D1, D2 are free; D4 asks the model about each candidate pair under a
#                    cap of 1.5 x candidates x the first measurement's p90 call price (run_p3.sh), cut to the ledger.
#   M8b (P4, E1-E4)  on the five 1,000-sheet plants and the arms d0, d2, d4: reload the plant with that arm's
#                    identity links, re-home the sealed questions onto it (with a proof), and let V2T-A2 answer
#                    them from a copy of the M6a cache, so only the changed prompts cost money.
# In --smoke the model-backed pieces (D4, and so the d4 arm) are left out: the other deciders run for real.

P90_CALL_USD=0.000171   # R5's p90 small Luna call (EXP-0004 run_p3.sh: S7-CYP-H100g2/calls.jsonl, n = 497)
TAUS=$ROOT/tune/dev/D100g21d100Vf/taus.json

json_field() {  # json_field <file> <python expression on `d`>
  $P - "$1" "$2" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
print(eval(sys.argv[2]))
PYEOF
}

p3_corpus() {  # the deciders on one V corpus (built in M4), then its scores and links
  p3_dir=$ROOT/p3/$PL_ID
  if smoke && [ "$(json_field "$p3_dir/corpus.json" 'd["description"]["blocking"]["n_candidates"]')" = 0 ]; then
    event NOTE "SMOKE: $PL_ID has no candidate pairs (too small), not scored"; return 0
  fi
  # exp0004 never overwrites a measurement, so a resumed stage skips what the first attempt wrote
  for p3_decider in d0 d1 d2; do
    if [ ! -f "$p3_dir/decisions/$p3_decider.json" ]; then
      try $P -m plantgraph.exp0004 decide "$p3_dir" --decider $p3_decider --taus-json "$TAUS" > /dev/null
    fi
  done
  if ! smoke && [ ! -f "$p3_dir/decisions/d4.json" ]; then
    p3_n=$(json_field "$p3_dir/corpus.json" 'd["description"]["blocking"]["n_candidates"]')
    p3_own=$($P -c "import sys;print(round(1.5 * float(sys.argv[1]) * float(sys.argv[2]), 4))" "$p3_n" "$P90_CALL_USD")
    p3_cap=$($L fixed-cap --own "$p3_own" --step M8a --step-dir "$SD" --root "$ROOT") \
      || stop_run topup "no money left for D4 on $PL_ID"
    $L balance --needed "$p3_cap" || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$p3_cap"
    event START "D4 on $PL_ID: $p3_n candidates, cap \$$p3_cap"
    $P -m plantgraph.exp0004 decide "$p3_dir" --decider d4 --allow-paid-calls --max-spend-usd "$p3_cap" \
      --cache-path "$SD/cache_d4.sqlite" > "$p3_dir/d4_summary.json" 2> "$LOGS/d4_$PL_ID.log" \
      || { event CAP "D4 on $PL_ID stopped (cap \$$p3_cap or an error), see $LOGS/d4_$PL_ID.log"; stop_run topup "D4 on $PL_ID did not finish"; }
  fi
  if [ ! -f "$p3_dir/score.json" ]; then try $P -m plantgraph.exp0004 score "$p3_dir" > /dev/null; fi
  for p3_decider in $E2E_ARMS; do
    if [ ! -f "$p3_dir/links/$p3_decider.json" ]; then
      try $P -m plantgraph.exp0004 links "$p3_dir" --decider $p3_decider > /dev/null
    fi
  done
}

p3_report() {
  p3_dirs=; p3_extra=
  for p3_id in H100g21p1V H100g21p1d100V H1000g21p1V H1000g21p1d100V; do p3_dirs="$p3_dirs $ROOT/p3/$p3_id"; done
  for p3_id in H1000g21p2V H1000g21p3V H1000g21p4V H1000g21p5V; do p3_extra="$p3_extra $ROOT/p3/$p3_id"; done
  # shellcheck disable=SC2086
  # test corpora only (the design keeps P3 on the test set): M2 writes no score.json for the dev corpus
  try $P -m plantgraph.exp0004 report $p3_dirs --out "$SD/report.md"
  # shellcheck disable=SC2086
  try $P -m plantgraph.exp0004 report $p3_extra --out "$SD/report_extra.md"
}

stage_M8a() {
  STEP=M8a; SD=$ROOT/p3; EXPERIMENT=EXP-0008-P3
  mkdir -p "$SD"
  E2E_ARMS="d0 d2 d4"; if smoke; then E2E_ARMS="d0 d2"; fi
  require_frozen
  for_each_plant p3 p3_corpus
  if smoke; then   # tiny corpora have too few pairs for the report tool
    event NOTE "SMOKE: P3 report skipped"; echo "smoke: P3 report skipped" > "$SD/SMOKE.txt"; outputs "$SD/SMOKE.txt"
  else
    once report p3_report
    outputs "$SD/report.md" "$SD/report_extra.md"
  fi
}

# ---- M8b -----------------------------------------------------------------------------------------------

e2e_load() {  # the V plant PL_ID with this arm's identity links, in Neo4j (smoke: files only)
  el_links=$ROOT/p3/$PL_ID/links/$E2E_ARM.json
  [ -f "$el_links" ] || stop_run infra "no links file $el_links: run M8a first"
  el_args="--headline-v2 --target-sheets $PL_SHEETS --seed $PL_SEED --headline-duplication-rate $PL_RATE"
  el_args="$el_args --tag-variants --variant-families format naming --identity-links $el_links --corpus-id $PL_ID"
  if smoke; then el_mode="--no-neo4j"; else el_mode="--store-profile plant_lines --fresh-database"; fi
  rm -rf "$SD/load_tmp/$PL_ID"
  # shellcheck disable=SC2086
  try $P -m plantgraph.ingest synthetic $el_args $el_mode --out "$SD/load_tmp/$PL_ID" \
    > "$LOGS/load_${PL_ID}_$E2E_ARM.json" 2> "$LOGS/load_${PL_ID}_$E2E_ARM.err"
  # kept from the first load of this arm: a run freezes the hash of ingest.json and a reload changes its timings
  mkdir -p "$SD/corpora/$PL_ID"
  if [ ! -f "$SD/corpora/$PL_ID/ingest.json" ]; then
    try cp "$SD/load_tmp/$PL_ID/ingest.json" "$SD/corpora/$PL_ID/ingest.json"
  fi
}

e2e_rehome() {  # the sealed questions of the underlying plant, copied onto the V corpus, with a proof
  er_sealed=${PL_ID%V}
  try $P -m plantgraph.exp0004.rehome --source "$ROOT/questions/$er_sealed/questions.jsonl" \
    --variant-corpus-id "$PL_ID" --sealed-corpus-id "$er_sealed" \
    --out "$QROOT/$PL_ID/questions.jsonl" --proof "$ARM_DIR/rehome_proof_$PL_ID.json" \
    --sealed-ingest "$ROOT/corpora/$er_sealed/ingest.json" --variant-ingest "$SD/corpora/$PL_ID/ingest.json"
}

e2e_plant_arm() {  # one V plant under the arm E2E_ARM (d0, d2 or d4)
  if smoke && [ ! -f "$ROOT/p3/$PL_ID/links/$E2E_ARM.json" ]; then
    event NOTE "SMOKE: no links for $PL_ID ($E2E_ARM), plant too small"; return 0
  fi
  ARM_DIR=$ROOT/m8b/e2e/$E2E_ARM
  SD=$ARM_DIR/live; QROOT=$ARM_DIR/questions; CACHE=$SD/cache.sqlite
  CYP_CORPORA=$SD/corpora; AG_CORPORA=$SD/corpora
  mkdir -p "$SD/runs" "$SD/replays" "$SD/corpora" "$QROOT/$PL_ID"
  if [ ! -f "$CACHE" ]; then cp "$ROOT/m6a/cache.sqlite" "$CACHE"; fi   # R5's answers replay free where the prompt is unchanged
  once "load_${PL_ID}_$E2E_ARM" e2e_load
  once "rehome_${PL_ID}_$E2E_ARM" e2e_rehome
  TIER_SUFFIX=$E2E_ARM   # the first P4 measurement's spend per missed question, per arm and tier
  paid_run CYP-A "E2E-CYP-$PL_ID-$E2E_ARM" "$PL_ID" test
  replay_run CYP-A "E2E-CYP-$PL_ID-$E2E_ARM" "$PL_ID" test
  paid_run AG "E2E-AG-$PL_ID-$E2E_ARM" "$PL_ID" test
  TIER_SUFFIX=
  replay_run AG "E2E-AG-$PL_ID-$E2E_ARM" "$PL_ID" test
}

e2e_plant() {  # all arms of one V plant
  for E2E_ARM in $E2E_ARMS; do e2e_plant_arm; done
}

stage_M8b() {
  STEP=M8b; STEP_DIR=$ROOT/m8b; EXPERIMENT=EXP-0008-P4
  E2E_ARMS="d0 d2 d4"; if smoke; then E2E_ARMS="d0 d2"; fi
  mkdir -p "$STEP_DIR"
  require_frozen
  for_each_plant p4 e2e_plant
  find "$STEP_DIR/e2e" -name '*.complete' | sort > "$STEP_DIR/completed_runs.txt"
  outputs "$STEP_DIR/completed_runs.txt"
}
