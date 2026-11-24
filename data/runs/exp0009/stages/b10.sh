# B10: build the sealed plants, pool and draw their question files, $0. Sourced by run_all.sh.
#
# First time any sealed plant exists: it follows the freeze (F10), which is the point of the ordering.
# Per plant, the 100-sheet plants first: build (A corpus, B relabel, positions) and the plant gates (G0c, G0g, G0k,
# line view, G0-B 1-3), then the pool step (R pool and the X candidates, one generation).
# Then, once: the drop set (the five pre-registered R families and G0e's too-few families, at both scales), G0l,
# the samples and the A2 and B files, the sealed bands (ADR-0059, REPORTED ONLY - the freeze is done), and
# D10.sha256 over E10.commit and everything drawn. D10.sha256 is written once and never overwritten.
# G0h (each arm's first-turn prompt of the longest question fits the pin's context wall) is the harness's own
# run-start check; no separate gate is built (see the README).

b10_plant() {
  build_plant
  pool_plant_sealed
}

sealed_bands() {  # ADR-0059 bands on the pooled sealed plants of each scale: reported only
  if smoke; then event NOTE "SMOKE: tiny plants are not judged by the composition bands"; return 0; fi
  plan_to_file sealed
  for sb_scale in 100 1000; do
    sb_seeds=$(awk -v s="$sb_scale" '$2 == s { printf "%s ", $3 }' "$PLAN_FILE")
    # shellcheck disable=SC2086
    pooled_bands report "sealed$sb_scale" "$sb_scale" $sb_seeds
  done
}

write_d10() {
  [ ! -e "$ROOT/D10.sha256" ] || stop_run infra "$ROOT/D10.sha256 exists; a drawn set is never overwritten"
  try $L d10-write --root "$ROOT" --prereg "$PREREG" > "$LOGS/d10.txt"
  event NOTE "D10.sha256 written: $(cat "$LOGS/d10.txt") hashes"
}

stage_B10() {
  [ -f "$PREREG/E10.sha256" ] || stop_run user "no E10 freeze ($PREREG/E10.sha256): run F10 before any sealed plant exists"
  once plants for_each_plant sealed b10_plant
  once files question_files sealed
  once bands sealed_bands
  once d10 write_d10
  outputs "$ROOT/D10.sha256"
}
