# EXP-0009 pre-registration, part A (TEMPLATE)

The main session fills every `<<FILL ...>>` marker after the draw, writes the result to `prereg/PREREG_A.md`
and commits it on the user's order, together with `prereg/seeds.json`, `prereg/plan.json` and
`prereg/position_prior.json`. P0 refuses to start while a marker is left or part A is not committed.
Design: `docs/private/40-design/generator-v2-2-handbook-rules.md` section 19.

## Frozen code

- The A2 system is E9 (`5d31cbb94620645ee018771735edae37f49e7ef8`), checked by gate G0f.
- Part A code commit: <<FILL the 40-hex HEAD at the commit of part A>>
- Between that commit and E10 only these may change:
  B files under `src/plantgraph/qa/v2tb/` and `tests/v2tb/` (tuning); the T17 analysis module and its tests;
  `data/runs/exp0009/prereg/`; `docs/`.

## Claims

Q4, Q4-B, SB1 (descriptive), SB2, K1-K3 and Q5, with their pass rules (design 12.1): <<FILL the rules, verbatim>>.
Descriptive list, in addition: the Q4-B sensitivity row without POSITION_OF_VALVE; POSITION accuracy by form and
by code beside the majority and the text prior; the realized `named_by` mix per scale; the X sub-scopes; refused
shares; network-touching shares.

## Plants

<<FILL the tables printed by `launcher draw`: seeds, size targets, n_units, predicted sheet totals, documents,
tagging allocation (S9), the text prior's sha256 and the majority code>>

## Scope R

- Available families: all v2 families except UPSTREAM_ISOLATION and DOWNSTREAM_ISOLATION (S5), DOWNSTREAM_IN_UNIT and
  UPSTREAM_SOURCES (17.17) and FIRST_MEETING_POINT (v2), pre-registered unavailable at both scales.
- Recipe: EXP-0008's sealed recipe (pool seed 31, 500 per bin, 100 unanswerable; sample seed 20261031, 10 per family),
  then the drop set. G0e: any family with fewer than 10 kept questions on any plant of the role is dropped at both
  scales, and an event NOTE lists it.

## Scope X

The five families (OPEN_VALVES_TO_ISOLATE, OPEN_VALVES_TO_ISOLATE_DOWNSTREAM, UPSTREAM_ISOLATION_X,
DOWNSTREAM_ISOLATION_X, POSITION_OF_VALVE), 10 per family: B 50, A2 40 through the TAG_SET adapter (A2 is not asked
POSITION). Texts R9 and the two POSITION forms R11: <<FILL>>. G0l: a family that refuses more than a quarter of its
candidates as non-unique stops the launcher and returns to the architect.

## POSITION baselines

The majority code and the text prior: `prereg/position_prior.json`, sha256 <<FILL from plan.json>>.

## Positions file

The method only (design v2t-b 10.9 R18), not a hash: the file is regenerated from the plant and its sha256 is
recorded in each `corpus_b.json` and in `D10.sha256`.

## Money

Program cap $35.00 hard (runs and audit together): runs ledger $26.87, audit cap min($8.13, $35 less the runs).
Caps without dry runs: questions x the tier's cost per question x 1.5, never below 5 questions' cost, cut to the step
ceiling (P1a $2.22, P1b $2.12, P1c $21.09) and the ledger. Estimate printed before each paid stage.

## B tuning

At most three rounds, on D100g22 only, dev families only. Stop when a round adds less than 1 point, or after round 3.
The E10 candidate is the round with the highest B dev accuracy, a tie going to the earlier round. The log is kept in
the EXP-0009 experiment note, not in ADR-0067.

## Gates

Design 19.5 and 19.7. If G1-B or G1-B2 fails, B is not run sealed (ADR-0067): A2 alone runs sealed, and the B audit
stratum and the B P1c runs are dropped.

## Audit

EXP-0008's rule, plus a B stratum half the main sample's size (VALVE_SET and POSITION rows). Judge prompt sha256
<<FILL>>, judge pin sha256 <<FILL>>.

## Bootstrap

The resample count and seed of the EXP-0008 claims code: <<FILL>>.
