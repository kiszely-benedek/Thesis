# M2: EXP-0004 P1/P2 on the dev corpus: the two identity thresholds tau1 and tau2, from exact scores. Sourced by run_all.sh.
#
# Free: build the dev corpus D100g21d100Vf (seed 1, full duplication, tag-format variants) and choose
# tau1/tau2 by the registered rule (`exp0004 tune`). Paid, tiny: D4 (the LLM pair decider) on a 20-pair sample
# to confirm its prompt parses (ADR-0063); more than the allowed parse failures stops the launcher, because the
# remedy is a prompt rule, which is design work.

stage_M2() {
  STEP=M2; SD=$ROOT/tune
  dev_dir=$SD/dev/D100g21d100Vf
  dev_sheets=100; if smoke; then dev_sheets=10; fi
  mkdir -p "$SD"
  if [ ! -f "$dev_dir/corpus.json" ]; then
    once build try $P -m plantgraph.exp0004 build --corpus-id D100g21d100Vf --target-sheets "$dev_sheets" \
      --seed 1 --duplication-rate 1.0 --families format --out "$dev_dir"
  fi
  once tune try $P -m plantgraph.exp0004 tune "$dev_dir"
  [ -f "$dev_dir/taus.json" ] || stop_run infra "expected $dev_dir/taus.json after the tuning, found none"
  once d4_pilot d4_pilot "$dev_dir"
  gate_pass "tau1/tau2 chosen: $(cat "$dev_dir/taus.json"); D4 prompt parses"
  outputs "$dev_dir/taus.json" "$dev_dir/pilot/summary.json"
}

d4_pilot() {  # D4 on 20 pairs under a tiny capped budget; the step ceiling (design 6) is $0.05
  d4_dir=$1
  if smoke; then   # no model in the smoke: a summary of the right shape, so the gate below is exercised
    mkdir -p "$d4_dir/pilot"
    printf '{"parse_failures_over_limit": false}\n' > "$d4_dir/pilot/summary.json"
    return 0
  fi
  d4_cap=$($L fixed-cap --own 0.05 --step M2 --step-dir "$SD" --root "$ROOT") \
    || stop_run topup "no money left for the D4 pilot"
  $L balance --needed "$d4_cap" || stop_run topup "the OpenRouter balance cannot be read or does not cover \$$d4_cap"
  $P -m plantgraph.exp0004 pilot "$d4_dir" --n 20 --allow-paid-calls --max-spend-usd "$d4_cap" \
    --cache-path "$SD/cache_d4.sqlite" > "$LOGS/d4_pilot.log" 2>&1 || stop_run infra "D4 pilot failed, see $LOGS/d4_pilot.log"
  if grep -q '"parse_failures_over_limit": *true' "$d4_dir/pilot/summary.json"; then
    gate_fail "M2" "D4 has too many parse failures: apply the prompt rule of ADR-0063"
  fi
}
