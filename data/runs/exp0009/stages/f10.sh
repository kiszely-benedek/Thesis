# F10: the E10 freeze and pre-registration part B, $0. Sourced by run_all.sh.
#
# After this stage nothing that decides what a sealed run does may change, and no sealed plant exists yet (B10
# builds them). The stage
#   1. refuses a dirty tree under the frozen paths, and a HEAD other than the commit part A names (or a later
#      commit that changed only B files, the T17 analysis, prereg/ and docs/ - design 19.3);
#   2. refuses B files that differ from the chosen tuning round's hashes or from the P1b B runs' b_code.sha256;
#   3. repeats the G0f diff and G0j;
#   4. writes E10.commit and E10.sha256 (every tracked frozen file: all of src again), B_FILES.sha256 (every
#      qa/v2tb file plus the policy line), PREREG_B.md and PREREG.sha256 (part A, part B, seeds, plan, prior,
#      the E10 and B hash files, the judge prompt).
# It never commits: the user commits part B and the hash files on their order.

JUDGE_PROMPT=src/plantgraph/qa/audit/audit_judge.txt

git_facts() {  # writes head, porcelain and the files changed since part A's commit into $SD
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
  git status --porcelain -- $FROZEN_PATHS pyproject.toml uv.lock > "$SD/porcelain" || stop_run infra "git status failed"
  f_named=$(sed -n 's/^Part A code commit:[ `]*\([0-9a-f]\{40\}\).*/\1/p' "$PREREG/PREREG_A.md")
  if [ -n "$f_named" ] && [ "$f_named" != "$(cat "$SD/head")" ]; then
    # shellcheck disable=SC2086
    git diff --name-only "$f_named" HEAD -- $FROZEN_PATHS pyproject.toml uv.lock tests docs data/runs/exp0009/prereg > "$SD/changed" \
      || stop_run infra "git diff failed"
  else : > "$SD/changed"; fi
}

frozen_file_list() {  # every tracked frozen file, one per line
  # shellcheck disable=SC2086
  git ls-files $FROZEN_PATHS pyproject.toml uv.lock > "$SD/frozen_files.txt" || stop_run infra "git ls-files failed"
}

chosen_b_code() {  # the chosen round's b_code.sha256, or (forced) a spoiled copy
  cb_round=$(cat "$ROOT/tune/chosen_round.txt") || stop_run infra "tuning is not finished"
  CHOSEN_B=$ROOT/tune/round$cb_round/b_code.sha256
  if smoke && forced b-files; then
    cp "$CHOSEN_B" "$SD/chosen_b_code.spoiled"; echo "0000000000000000000000000000000000000000000000000000000000000000 *src/plantgraph/qa/v2tb/none.py" >> "$SD/chosen_b_code.spoiled"
    CHOSEN_B=$SD/chosen_b_code.spoiled
  fi
}

freeze() {
  once git_facts git_facts
  [ -f "$PREREG/PREREG_A.md" ] || stop_run user "no $PREREG/PREREG_A.md: commit part A first"
  chosen_b_code
  $L freeze-check --porcelain "$SD/porcelain" --part-a "$PREREG/PREREG_A.md" --changed "$SD/changed" \
    --chosen-b-code "$CHOSEN_B" --head "$(cat "$SD/head")" || gate_fail "F10" "the freeze is refused (see the line above): commit, or restore the B files"
  gate_pass "freeze preconditions"
  for f_run in "$ROOT"/val/runs/V9-*B; do   # the P1b B runs ran on the chosen round's B files
    [ -d "$f_run" ] || continue
    $L b-code-check --run-dir "$f_run" --against "$CHOSEN_B" || gate_fail "F10" "$(basename "$f_run") ran on other B files than the chosen round's"
  done
  g0f_diff
  g0j_gate
  rm -f "$PREREG/E10.commit" "$PREREG/E10.sha256" "$PREREG/B_FILES.sha256" "$PREREG/PREREG_B.md" "$PREREG/PREREG.sha256"
  frozen_file_list
  try $L freeze-write --prereg "$PREREG" --files "$SD/frozen_files.txt" --head "$(cat "$SD/head")" > /dev/null
  try $L prereg-b --root "$ROOT" --prereg "$PREREG" --head "$(cat "$SD/head")" --extra "$JUDGE_PROMPT"
  event NOTE "E10 frozen at $(utc): E10.sha256 $(sha256sum "$PREREG/E10.sha256" | cut -d' ' -f1), PREREG.sha256 $(sha256sum "$PREREG/PREREG.sha256" | cut -d' ' -f1)"
}

stage_F10() {
  SD=$ROOT/freeze; mkdir -p "$SD"
  rm -f "$SD/head" "$SD/porcelain" "$SD/changed" "$STATE/steps/F10_git_facts.ok"   # the facts are read afresh every run
  freeze
  outputs "$PREREG/E10.commit" "$PREREG/E10.sha256" "$PREREG/B_FILES.sha256" "$PREREG/PREREG_B.md" "$PREREG/PREREG.sha256"
}
