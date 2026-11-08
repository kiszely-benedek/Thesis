# M3: the E9 freeze and pre-registration part B. Sourced by run_all.sh.
#
# After this stage nothing that decides what a test run does may change, and no test plant exists yet (M4
# builds them). The stage
#   1. refuses a dirty working tree under src/ or the EXP-0008 scripts, and a HEAD other than the commit part A
#      names (or a later commit that changed only the pre-registration folder);
#   2. writes E9.commit and E9.sha256 (every tracked frozen file), then PREREG_B.md from the stage outputs, then
#      PREREG.sha256 over part A, part B, the seeds, the E9 files and the judge prompt;
#   3. logs the time, so the hash and the log line precede the first test-plant build.
# It never commits: the user commits part B and the hash files afterwards, on their order.

# what a test run's behaviour depends on; `git status` is checked over exactly these paths
FROZEN_PATHS="src $SCRIPTS/run_all.sh $SCRIPTS/lib.sh $SCRIPTS/lib_plants.sh $SCRIPTS/lib_runs.sh $SCRIPTS/stages $INPUTS"
JUDGE_PROMPT=src/plantgraph/qa/audit/audit_judge.txt

git_facts() {  # git_facts: writes head, porcelain and the files changed since part A's commit into $SD
  if smoke; then   # the smoke's tree is not a frozen one: it reads stub facts, which `--force` can spoil
    printf '%s\n' "${SMOKE_HEAD:-1111111111111111111111111111111111111111}" > "$SD/head"
    : > "$SD/porcelain"; : > "$SD/changed"
    if forced dirty-tree; then printf ' M src/plantgraph/qa/final_answer.py\n' > "$SD/porcelain"; fi
    if forced wrong-head; then
      printf '2222222222222222222222222222222222222222\n' > "$SD/head"
      printf 'src/plantgraph/qa/final_answer.py\n' > "$SD/changed"
    fi
    return 0
  fi
  git rev-parse HEAD > "$SD/head" || stop_run infra "cannot read HEAD"
  # shellcheck disable=SC2086
  git status --porcelain -- $FROZEN_PATHS > "$SD/porcelain" || stop_run infra "git status failed"
  gf_named=$(sed -n 's/^Frozen code commit:[ `]*\([0-9a-f]\{40\}\).*/\1/p' "$PREREG/PREREG_A.md")
  if [ -n "$gf_named" ] && [ "$gf_named" != "$(cat "$SD/head")" ]; then
    git diff --name-only "$gf_named" HEAD > "$SD/changed" || stop_run infra "git diff failed"
  else : > "$SD/changed"; fi
}

frozen_file_list() {  # every tracked frozen file, one per line, in $SD/frozen_files.txt
  # shellcheck disable=SC2086
  git ls-files $FROZEN_PATHS pyproject.toml uv.lock > "$SD/frozen_files.txt" || stop_run infra "git ls-files failed"
}

freeze() {
  once git_facts git_facts
  [ -f "$PREREG/PREREG_A.md" ] || stop_run user "no $PREREG/PREREG_A.md: commit part A (with the drawn seeds) first"
  $L freeze-check --porcelain "$SD/porcelain" --part-a "$PREREG/PREREG_A.md" --changed "$SD/changed" \
    --head "$(cat "$SD/head")" || gate_fail "M3" "the freeze is refused (see the line above): commit, or fix the tree"
  gate_pass "freeze preconditions"
  rm -f "$PREREG/E9.commit" "$PREREG/E9.sha256" "$PREREG/PREREG_B.md" "$PREREG/PREREG.sha256"
  frozen_file_list
  try $L freeze-write --prereg "$PREREG" --files "$SD/frozen_files.txt" --head "$(cat "$SD/head")"
  try $L prereg-b --root "$ROOT" --prereg "$PREREG" --head "$(cat "$SD/head")" \
    --taus "$ROOT/tune/dev/D100g21d100Vf/taus.json" --extra "$JUDGE_PROMPT"
  event NOTE "E9 frozen at $(utc): E9.sha256 $(sha256sum "$PREREG/E9.sha256" | cut -d' ' -f1), PREREG.sha256 $(sha256sum "$PREREG/PREREG.sha256" | cut -d' ' -f1)"
}

stage_M3() {
  SD=$ROOT/freeze; mkdir -p "$SD"
  rm -f "$SD/head" "$SD/porcelain" "$SD/changed" "$STATE/steps/M3_git_facts.ok"   # the facts are read afresh on every run
  freeze
  outputs "$PREREG/E9.commit" "$PREREG/E9.sha256" "$PREREG/PREREG_B.md" "$PREREG/PREREG.sha256"
}
