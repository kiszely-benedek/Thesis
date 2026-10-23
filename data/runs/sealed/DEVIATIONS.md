# Deviations from the frozen sealed-test note (sealed-test-run.md is hashed into F1 and not edited)

## D1 — candidate pool size `--n-per-bin 500` instead of 200 (2026-10-11, before any test question existed)

- Found by the QAR-T10 coder on a scratch corpus (seed 77, `X1000`, neither dev nor test): with
  `--n-per-bin 200`, families whose candidates all sit in k-bin 0 share the 200 slots, and five families got 10
  questions instead of the pre-registered 20 (`LOOKUP_TYPE`, `LOOKUP_UNIT`, `LOOP_MEASURED_EQUIPMENT`,
  `INSTRUMENTS_OF_ITEM`, `SAME_UNIT`); 530 questions instead of 580. With 500 the same corpus gave exactly 580
  (240 dev-old, 120 dev-new, 120 held-out, 100 wordings).
- ADR-0053 fixes **20 per family** and ~580 per corpus; `--n-per-bin` only sizes the candidate pool the per-family
  sampler draws from. Raising it keeps the pre-registered design; no test question, answer or score existed when
  the change was made. Decided by the main session under ADR-0053's intent; reported to the user the same day.
- `make_test_set.sh` is the §7.2 script with this one flag changed.
