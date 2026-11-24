# END: the free reports, the ledger summary, the T17 hook and the demo database restore. $0. Sourced by run_all.sh.
#
# Cascade reports per plant and arm (and the GLM arm's report of P1g), the record check over every run, the offline re-score of every run, the
# ledger summary, the T17 analysis entry point if it is present (a missing T17 is noted, not a stop), and LAST the
# demo database restore (wipe, then H1000g21p1 with plant_lines: ADR-0064, demo-v2.md). As in EXP-0008 M10b, a
# failed report is named, the restore still runs, and only then does the stage stop. To restore the demo plant alone:
#   sh data/runs/exp0009/demo_load.sh

END_FAILED=

end_try() {  # end_try <name> <command...>: a failed report is noted and the next one still runs
  et_name=$1; shift
  if "$@" > "$LOGS/end_$et_name.txt" 2>&1; then event NOTE "report $et_name ok"
  else event NOTE "report $et_name FAILED, see $LOGS/end_$et_name.txt"; END_FAILED="$END_FAILED $et_name"; fi
}

end_plant() {  # the reports of one sealed plant, both arms
  rd=$ROOT/p1c/runs
  for ep_run in "$rd/S9-CYP-$PL_ID" "$rd/S9-AG-$PL_ID" "$rd/S9-CYP-${PL_ID}B" "$rd/S9-AG-${PL_ID}B"; do
    [ -d "$ep_run" ] || continue
    end_try "records_$(basename "$ep_run")" $L records-check --run-dir "$ep_run"
  done
  if smoke; then return 0; fi   # canned answers: the cascade reports and the re-score are meaningful on real runs only
  end_try "cascade_$PL_ID" $L cascade-report --corpus-id "$PL_ID" --arm A2 --cyp-run "$rd/S9-CYP-$PL_ID" \
    --ag-run "$rd/S9-AG-$PL_ID" --questions-root "$ROOT/questions" --corpora-root "$ROOT/corpora" --out "$ROOT/reports/${PL_ID}_a2.json"
  end_try "rescore_AG_$PL_ID" $L rescore --run-dir "$rd/S9-AG-$PL_ID" --questions-root "$ROOT/questions" --corpus-id "$PL_ID" \
    --ingest-json "$ROOT/corpora/$PL_ID/ingest.json" --out "$ROOT/reports/rescore_AG_$PL_ID.json"
  if [ "$(cat "$STATE/b_sealed")" = yes ]; then
    end_try "cascade_${PL_ID}B" $L cascade-report --corpus-id "${PL_ID}B" --arm B --cyp-run "$rd/S9-CYP-${PL_ID}B" \
      --ag-run "$rd/S9-AG-${PL_ID}B" --questions-root "$ROOT/questions" --corpora-root "$ROOT/corpora" --out "$ROOT/reports/${PL_ID}_b.json"
    end_try "rescore_AG_${PL_ID}B" $L rescore --b --run-dir "$rd/S9-AG-${PL_ID}B" --questions-root "$ROOT/questions" --corpus-id "${PL_ID}B" \
      --ingest-json "$ROOT/corpora/${PL_ID}B/ingest.json" --out "$ROOT/reports/rescore_AG_${PL_ID}B.json"
  fi
}

end_glm_plant() {  # the reports of one plant of the GLM comparison arm (stage P1g)
  gd=$ROOT/p1g/runs
  for eg_run in "$gd/G9-GLM-CYP-$PL_ID" "$gd/G9-GLM-AG-$PL_ID"; do
    [ -d "$eg_run" ] || continue
    end_try "records_$(basename "$eg_run")" $L records-check --run-dir "$eg_run"
  done
  if smoke; then return 0; fi   # canned answers: the cascade report and the re-score are meaningful on real runs only
  end_try "cascade_glm_$PL_ID" $L cascade-report --corpus-id "$PL_ID" --arm A2 --cyp-run "$gd/G9-GLM-CYP-$PL_ID"     --ag-run "$gd/G9-GLM-AG-$PL_ID" --questions-root "$ROOT/p1g/questions" --corpora-root "$ROOT/corpora"     --out "$ROOT/reports/glm/${PL_ID}_glm.json"
  end_try "rescore_AG_glm_$PL_ID" $L rescore --run-dir "$gd/G9-GLM-AG-$PL_ID" --questions-root "$ROOT/p1g/questions"     --corpus-id "$PL_ID" --ingest-json "$ROOT/corpora/$PL_ID/ingest.json" --out "$ROOT/reports/glm/rescore_AG_$PL_ID.json"
}

end_glm() {  # GLM - Luna on the same questions: descriptive, no claim (design 20)
  if [ ! -d "$ROOT/p1g/runs" ]; then event NOTE "P1g left no runs: no GLM report"; return 0; fi
  mkdir -p "$ROOT/reports/glm"
  for_each_plant glm end_glm_plant
  if ! smoke; then end_try glm_report $L glm-report --root "$ROOT" --prereg "$PREREG"; fi
}

end_t17() {  # the sealed analysis (T17), if it has been built and committed before F10
  if $P -c "import plantgraph.qa.exp0009.analysis" 2> /dev/null; then
    end_try t17 $P -m plantgraph.qa.exp0009.analysis --root "$ROOT"
  else
    event NOTE "T17 (the sealed analysis, plantgraph.qa.exp0009.analysis) is not present: noted, not a stop"
  fi
}

stage_END() {
  mkdir -p "$ROOT/reports"
  require_frozen
  plan_to_file sealed
  end_try ledger $L spent --root "$ROOT"
  event NOTE "ledger: $($L spent --root "$ROOT")"
  for_each_plant sealed end_plant
  end_glm
  end_t17
  demo_database   # LAST: the user's database ends on the demo plant, whatever failed above
  [ -z "$END_FAILED" ] || stop_run infra "these reports failed:$END_FAILED (the demo database was restored)"
  outputs "$LOGS/end_ledger.txt"
}
