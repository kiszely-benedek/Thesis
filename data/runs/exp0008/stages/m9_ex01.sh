# M9: EX01, the real-plant example (ChatP&ID's five scored questions), re-run with the fixed adapter. Sourced by
# run_all.sh. PAID, small: the registered five arms, three repeats, under a cap cut to the step ceiling and the ledger.
#
# EX01 is the one real P&ID in the study (a Proteus XML export). The adapter now gives instrument bubbles their
# function letters (F10), so the first measurement's EX01 answers are re-asked. Its tag-reading arms use the
# first measurement's frozen inputs (data/runs/exp0001/inputs), read only.
# In --smoke there is neither the EX01 export's Neo4j load nor a fakeable client in this command, so the stage
# prints the command it would run and records a note.

EX01_XML=data/external/C01V04-VER.EX01.xml
EX01_INPUTS=data/runs/exp0001/inputs

ex01_import() {  # EX01 as imported, plant profile; once without Neo4j for the corpus, once loaded for the Cypher arm
  try $P -m plantgraph.ingest proteus "$EX01_XML" --corpus-id EX01 --no-neo4j --store-profile plant \
    --out "$SD/corpora/EX01" > "$LOGS/corpus_EX01.json"
  try $P -m plantgraph.ingest proteus "$EX01_XML" --corpus-id EX01 --store-profile plant --fresh-database \
    --out "$SD/neo4jplant/EX01" > "$LOGS/load_EX01.json" 2> "$LOGS/load_EX01.err"
}

ex01_run() {
  ex_cap=$($L fixed-cap --own 0.25 --step M9 --step-dir "$SD" --root "$ROOT") \
    || stop_run topup "no money left for EX01"
  $L balance --needed "$ex_cap" || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$ex_cap"
  event START "EX01 five arms x 3 repeats, cap \$$ex_cap"
  ex_rc=0
  $P -m plantgraph.qa.exp0001 ex01 --arms ctx-high,ctx-low,ctx-gpt5mini,cyp,ag --repeats 3 --cap "$ex_cap" \
    --allow-paid-calls --inputs-dir "$EX01_INPUTS" --corpora-root "$SD/corpora" --out-dir "$SD/out" \
    >> "$LOGS/E8-EX01.log" 2>&1 || ex_rc=$?
  case $ex_rc in
    0) ;;
    3) event CAP "EX01 reached its cap \$$ex_cap"; stop_run topup "EX01 reached its spend cap of \$$ex_cap" ;;
    *) stop_run infra "EX01 failed with exit $ex_rc, see $LOGS/E8-EX01.log" ;;
  esac
  try $P -m plantgraph.qa.exp0001 ex01-review --checklist "$EX01_INPUTS/ex01_checklist.json" --out-dir "$SD/out"
}

stage_M9() {
  STEP=M9; SD=$ROOT/ex01; mkdir -p "$SD/out"
  require_frozen
  if smoke; then
    event NOTE "SMOKE: EX01 not run; it would import $EX01_XML and run: exp0001 ex01 --arms ctx-high,ctx-low,ctx-gpt5mini,cyp,ag --repeats 3 --cap <ledger-cut>"
    echo "smoke: EX01 skipped" > "$SD/out/SMOKE.txt"
    outputs "$SD/out/SMOKE.txt"
    return 0
  fi
  once import ex01_import
  once run ex01_run
  outputs "$SD/out/answers.jsonl"
}
