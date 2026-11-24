# P1c: the sealed runs on ten plants, both arms. PAID. Sourced by run_all.sh.
#
# Per plant, in plan order (100-sheet p1-p5, then 1,000-sheet p1-p5), A2 then B:
#   1. load A; S9-CYP-<id> and its replay
#   2. load B; S9-CYP-<id>B and its replay                      (skipped if B is not run sealed, state/b_sealed = no)
#   3. S9-AG-<id> and its replay; S9-AG-<id>B and its replay    (the agent runs need no database)
# EVERY sealed run is replayed cache-only (ADR-0068 decision 4, as EXP-0008 M6a). Concurrency 4. Nothing else
# may run on the machine meanwhile (K1, K3). The caps use P1b's measured dollars per question
# (state/measured_costs.json), recomputed before the first B run.

p1c_plant() {
  if [ "$(cat "$STATE/b_sealed")" = yes ]; then pc_b=yes; else pc_b=no; fi
  neo4j_load_a
  paid_run CYP-A "S9-CYP-$PL_ID" "$PL_ID" test
  replay_run CYP-A "S9-CYP-$PL_ID" "$PL_ID" test
  if [ $pc_b = yes ]; then
    neo4j_load_b
    paid_run CYP-B "S9-CYP-${PL_ID}B" "${PL_ID}B" test
    replay_run CYP-B "S9-CYP-${PL_ID}B" "${PL_ID}B" test
  fi
  paid_run AG "S9-AG-$PL_ID" "$PL_ID" test
  replay_run AG "S9-AG-$PL_ID" "$PL_ID" test
  if [ $pc_b = yes ]; then
    paid_run AG-B "S9-AG-${PL_ID}B" "${PL_ID}B" test
    replay_run AG-B "S9-AG-${PL_ID}B" "${PL_ID}B" test
  fi
}

stage_P1c() {
  SD=$ROOT/p1c; STEP=P1c; CACHE=$SD/cache.sqlite; EXPERIMENT=EXP-0009-SEALED; QROOT=$ROOT/questions
  mkdir -p "$SD/runs" "$SD/replays"
  require_frozen
  [ -f "$STATE/b_sealed" ] || stop_run infra "no state/b_sealed: P1b did not finish"
  if forced cap; then E10_SMOKE_COST_USD=2; export E10_SMOKE_COST_USD; fi
  event NOTE "B sealed: $(cat "$STATE/b_sealed"); measured costs: $(tr -d ' \n' < "$STATE/measured_costs.json")"
  estimate_note P1c
  # a plant's scale decides its cost keys; for_each_plant sets PL_SCALE
  for_each_plant sealed p1c_plant
  outputs "$SD/runs/S9-AG-H1000g22p5/answers.jsonl" "$SD/runs/S9-CYP-H100g22p5/answers.jsonl"
}
