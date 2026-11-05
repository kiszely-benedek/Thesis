# Helpers of run_e2e.sh (EXP-0004 end-to-end arm, design 40-design/exp0004-v2.md section 7): sourced after
# lib.sh, tune_lib.sh and v2t_lib.sh, never run on its own. Same variable discipline as v2t_lib.sh: the
# sourced helpers set the shell globals `tier`, `id`, `orig`, `dir`, `cache`, `name`, so every name here is
# prefixed `e2e_` or `ed_`.
#
# The caller sets: E (this folder), A (the arm's folder), S (the stage folder: dry or live), ARM, CACHE,
# CYP_CORPORA, AG_CORPORA, QROOT, EXPERIMENT, DEADLINE_S.

E2E_CORPUS=H1000g2V          # the variant of R5's claims corpus (PREREG.md section 6)
E2E_SEALED_CORPUS=H1000g2
E2E_SEALED_SHEETS=1000
E2E_SYSTEM=V2T-A

e2e_links_file() {  # e2e_links_file <d0|d2|d4>: the arm's identity links, written by P3
  case $1 in
    d0|d2|d4) echo "$E/test/$E2E_CORPUS/links/$1.json" ;;
    *) die "unknown arm '$1': expected d0, d2 or d4 (PREREG.md section 6)" ;;
  esac
}

# ---- the freeze E8 and the pre-registration ----------------------------------------------------

# E8 is E7 shown unchanged after EXP-0004's data-side code landed (design section 8). E8.commit is after
# every data-side change, so no frozen file may differ from it: the data-side exceptions of e8_identify.sh
# belong to the E7..E8 comparison, which that script already made, not to this one. Like
# require_v2t_freeze, a change counts committed or not; listing_E7.json is judged by its hash in E8.sha256.
require_e8_freeze() {
  [ -f "$E/E8.commit" ] && [ -f "$E/E8.sha256" ] && [ -f "$E/E8.system" ] \
    || die "no E8 freeze file in $E: run e8_identify.sh first"
  [ "$(cat "$E/E8.system")" = "$E2E_SYSTEM" ] || die "E8 froze '$(cat "$E/E8.system")', this script runs $E2E_SYSTEM"
  ed_skip=":(exclude)$IN/listing_E7.json"
  # shellcheck disable=SC2086
  if ! git diff --quiet "$(cat "$E/E8.commit")" -- $V2T_FROZEN_FILES $IN "$ed_skip" \
      || [ -n "$(git status --porcelain -- $V2T_FROZEN_FILES $IN "$ed_skip")" ]; then
    die "a V2T system file (tune_lib.sh V2T_FROZEN_FILES) or an input differs from E8 ($(cat "$E/E8.commit")): the system is not frozen"
  fi
  sha256sum -c --quiet "$E/E8.sha256" || die "a file hashed in E8.sha256 changed since E8"
  echo "frozen system: $E2E_SYSTEM at E8 $(cat "$E/E8.commit")"
}

# Every file the test runs depend on is hashed in PREREG.sha256 and committed before the first test call.
require_prereg_holds() {
  sha256sum -c --quiet "$E/prereg/PREREG.sha256" || die "a pre-registered file changed"
  # shellcheck disable=SC2046
  [ -z "$(git status --porcelain -- "$E/prereg" $(sed 's/^[0-9a-f]* \*//' "$E/prereg/PREREG.sha256"))" ] \
    || die "the pre-registration is not committed"
  echo "pre-registration holds ($(wc -l < "$E/prereg/PREREG.sha256") hashes)"
}

# ---- load, rehome, dry run ---------------------------------------------------------------------

# R5's own load of H1000g2 (run_sealed.sh load_sealed: test seed, plant_lines profile, preset duplication),
# plus the variant flags that built the P3 corpus: seed 5003, families in the order format naming, variant
# rate 1.0 (the default; exp0004/corpus.py), and the arm's identity links.
e2e_load() {  # e2e_load <links file>
  ed_seed=$($EX test-seed --sheets $E2E_SEALED_SHEETS)
  load_corpus "$E2E_CORPUS" $E2E_SEALED_SHEETS "$ed_seed" plant_lines $(sealed_dup_args "$E2E_SEALED_CORPUS") \
    --tag-variants --variant-families format naming --identity-links "$1"
}

e2e_rehome() {  # the question copy and its proof; the proof lives beside the arm's folders
  $P -m plantgraph.exp0004.rehome --source "$X/sealed/questions/$E2E_SEALED_CORPUS/questions.jsonl" \
    --variant-corpus-id "$E2E_CORPUS" --sealed-corpus-id "$E2E_SEALED_CORPUS" \
    --out "$QROOT/$E2E_CORPUS/questions.jsonl" --proof "$A/rehome_proof.json" \
    --sealed-ingest "$X/sealed/corpora/$E2E_SEALED_CORPUS/ingest.json" \
    --variant-ingest "$CYP_CORPORA/$E2E_CORPUS/ingest.json" \
    > "$S/logs/rehome.log" 2>&1 || die "rehome failed, see $S/logs/rehome.log"
}

# Replay-only dry run of one tier. The wrapper runs the harness on the COPY of the sealed cache with a fake
# transport, so a miss is listed instead of stopping the run and no request is ever sent. This script
# itself passes no --allow-paid-calls.
e2e_dry_tier() {  # e2e_dry_tier <CYP-A|AG> <run-id>
  ed_arm=$1; ed_id=$2
  echo "=== $(date +%T) dry run $ed_id (cache copy, nothing is paid)"
  $P -m plantgraph.exp0004.e2e_dry_run --misses-out "$S/$ed_id.misses.json" \
    --run-id "$ed_id" --experiment "$EXPERIMENT" --corpus "$E2E_CORPUS:test" $(v2t_arm_options "$ed_arm") \
    --corpora-root "$(arm_corpora "$ed_arm")" --questions-root "$QROOT" --runs-root "$S/runs" \
    --cache-path "$CACHE" --concurrency 1 --question-deadline-s "$DEADLINE_S" \
    >> "$S/logs/$ed_id.log" 2>&1 || die "$ed_id failed, see $S/logs/$ed_id.log"
  tail -n 1 "$S/logs/$ed_id.log"
}

e2e_dry_ids() { E2E_DRY_CYP=E2E-DRY-CYP-$E2E_CORPUS-$ARM; E2E_DRY_AG=E2E-DRY-AG-$E2E_CORPUS-$ARM; }

e2e_dry_caps() {  # both tiers' miss counts -> the arm's caps file (design section 10)
  $P -m plantgraph.exp0004.e2e_caps make --arm "$ARM" --cyp-misses "$S/$E2E_DRY_CYP.misses.json" \
    --ag-misses "$S/$E2E_DRY_AG.misses.json" --out "$S/caps.json" || die "writing the caps failed"
}

# ---- the live tiers ----------------------------------------------------------------------------

# v2t_run asks cap_of / cost_of per run id. The arm's cap comes from the command line (split between the
# tiers by e2e_split_caps); the cost per question is R5's at H1000g2 (EXP-0007-R5-sealed.md, rows
# always_c_v2t and always_g_v2t): Cypher tier $0.00075, agent tier $0.00189.
cap_of() { case $1 in E2E-CYP-*) echo "$E2E_CAP_CYP" ;; E2E-AG-*) echo "$E2E_CAP_AG" ;; *) die "no cap for $1" ;; esac; }
cost_of() { case $1 in E2E-CYP-*) echo 0.00075 ;; E2E-AG-*) echo 0.00189 ;; *) die "no cost for $1" ;; esac; }

e2e_split_caps() {  # e2e_split_caps <caps file> <max spend usd>: sets E2E_CAP_CYP and E2E_CAP_AG
  ed_caps=$($P -m plantgraph.exp0004.e2e_caps split --caps "$1" --max-spend-usd "$2") \
    || die "the cap $2 is refused (see above): the dry run decides the most that may be spent"
  E2E_CAP_CYP=${ed_caps% *}; E2E_CAP_AG=${ed_caps#* }
  echo "caps: Cypher tier \$$E2E_CAP_CYP, agent tier \$$E2E_CAP_AG (arm total \$$2)"
}

e2e_check_questions() {  # the questions on disk are the copy the proof describes
  ed_want=$($P -c "import json,sys;print(json.load(open(sys.argv[1]))['output_sha256'])" "$A/rehome_proof.json") \
    || die "cannot read $A/rehome_proof.json: run the dry mode first"
  ed_have=$(sha256sum "$QROOT/$E2E_CORPUS/questions.jsonl" | cut -d' ' -f1)
  [ "$ed_want" = "$ed_have" ] || die "the re-homed questions changed since the proof ($ed_have, proof $ed_want)"
}

e2e_live_tier() {  # e2e_live_tier <CYP-A|AG> <run-id>: the run, then its cache-only replay
  step "live_$2" v2t_run "$1" "$2" "$E2E_CORPUS" full "$DEADLINE_S"
  step "replay_$2" v2t_replay "$1" "$2" "$E2E_CORPUS" "$DEADLINE_S"
}
