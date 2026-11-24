# EXP-0009 pre-registration, part A

Filled by the main session on 2026-11-24 after the draw (`launcher draw --draw-seed 20261124`). The draw seed 20261124
is the date of the draw, chosen before the draw. Committed with `prereg/seeds.json`, `prereg/plan.json` and
`prereg/position_prior.json`; the user granted commit and push authority for this session.
Design: `docs/private/40-design/generator-v2-2-handbook-rules.md` section 19.

## Frozen code

- The A2 system is E9 (`5d31cbb94620645ee018771735edae37f49e7ef8`), checked by gate G0f.
- The code at the draw; the part A commit adds only `prereg/` files:

Part A code commit: ba7277a76a32262bc4eee884dc47fbb1460909bf

- Between that commit and E10 only these may change:
  B files under `src/plantgraph/qa/v2tb/` and `tests/v2tb/` (tuning); the T17 analysis module and its tests;
  `data/runs/exp0009/prereg/`; `docs/`.

## Claims

Q4, Q4-B, SB1 (descriptive), SB2, K1-K3 and Q5, with their pass rules (design 12.1, verbatim):

| Claim | Arm and scope | Pass |
|---|---|---|
| Q4 (primary) | V2T-A2, scope R, cascade_v4_iso, S1000 − S100, two-stage cluster bootstrap | the interval contains 0 or lies above (ADR-0053, ADR-0065) |
| Q4-B | V2T-B, scope R ∪ X | the same rule |
| SB1 no harm | V2T-B − V2T-A2, scope R, paired on the same questions | descriptive: the difference and its interval, no margin (user, 2026-11-23) |
| SB2 content value | V2T-B − V2T-A2, scope X isolation families, paired | the interval lies above 0 |
| K1, K2, K3, Q5 | V2T-A2, scope R | as EXP-0008 |
| Descriptive | data effect: V2T-A2 on v2.2 − V2T-A2 on v2.1 (EXP-0008) per scale, on the families both share (unpaired, the same bootstrap); X sub-scopes (untagged gold, discriminating share); POSITION_OF_VALVE accuracy; refused shares; network-touching shares; `rules.json` summaries | — |
| In P2 | X1/X2 (ladder) and E1–E4 (identity), on V2T-A2, as registered | — |

Descriptive list, in addition: the Q4-B sensitivity row without POSITION_OF_VALVE; POSITION accuracy by form and
by code beside the majority and the text prior; the realized `named_by` mix per scale; the X sub-scopes; refused
shares; network-touching shares.

## Plants

| role | seed |
|---|---|
| validation, 100 sheets | 5860 |
| validation, 1000 sheets | 5184 |
| ladder, 3/10/30 sheets | 5708 |
| ladder, 1-sheet candidates in order | 5993, 5006, 5048, 5704, 5832, 5725, 5145, 5915, 5635, 5487, 5513, 5982, 5172, 5795, 5459, 5445, 5812, 5874, 5597, 5262, 5080, 5835, 5759, 5004, 5612, 5590, 5924, 5062, 5983, 5149 |
| sealed 100 sheets, plant p1 | 5669 |
| sealed 100 sheets, plant p2 | 5474 |
| sealed 100 sheets, plant p3 | 5308 |
| sealed 100 sheets, plant p4 | 5917 |
| sealed 100 sheets, plant p5 | 5030 |
| sealed 1000 sheets, plant p1 | 5791 |
| sealed 1000 sheets, plant p2 | 5827 |
| sealed 1000 sheets, plant p3 | 5738 |
| sealed 1000 sheets, plant p4 | 5568 |
| sealed 1000 sheets, plant p5 | 5945 |

| plant | role | seed | target | n_units | predicted sheets | documents | documents untagged |
|---|---|---|---|---|---|---|---|
| D100g22 | dev | 1 | 100 | 47 | 100 | 1 | 1 |
| D1000g22 | probe | 1 | 1000 | 500 | 1000 | 10 | 9 |
| VAL100g22 | validation | 5860 | 104 | 52 | 104 | 1 | 1 |
| VAL1000g22 | validation | 5184 | 1049 | 531 | 1050 | 10 | 8 |
| H100g22p1 | sealed | 5669 | 108 | 55 | 110 | 2 | 2 |
| H100g22p2 | sealed | 5474 | 90 | 42 | 90 | 1 | 0 |
| H100g22p3 | sealed | 5308 | 110 | 53 | 109 | 2 | 2 |
| H100g22p4 | sealed | 5917 | 110 | 55 | 109 | 1 | 1 |
| H100g22p5 | sealed | 5030 | 104 | 53 | 100 | 1 | 1 |
| H1000g22p1 | sealed | 5791 | 920 | 468 | 921 | 9 | 7 |
| H1000g22p2 | sealed | 5827 | 1086 | 558 | 1086 | 11 | 9 |
| H1000g22p3 | sealed | 5738 | 1024 | 533 | 1025 | 10 | 8 |
| H1000g22p4 | sealed | 5568 | 1072 | 531 | 1072 | 10 | 8 |
| H1000g22p5 | sealed | 5945 | 1012 | 506 | 1011 | 11 | 9 |

Tagging allocation (S9): at 100 sheets, 4 of the 5 sealed plants are wholly untagged (H100g22p2 is the tagged one); at
1,000 sheets each plant leaves round(0.8 × documents) untagged, rounding half up. Text prior sha256
`3d48518f16a43262bc23cc74fb7e9d2e56c68d6059d248c71e5195191cbd529a`; majority code NO for both forms.

## Scope R

- Available families: all v2 families except UPSTREAM_ISOLATION and DOWNSTREAM_ISOLATION (S5), DOWNSTREAM_IN_UNIT and
  UPSTREAM_SOURCES (17.17) and FIRST_MEETING_POINT (v2), pre-registered unavailable at both scales.
- Recipe: EXP-0008's sealed recipe (pool seed 31, 500 per bin, 100 unanswerable; sample seed 20261031, 10 per family),
  then the drop set. G0e: any family with fewer than 10 kept questions on any plant of the role is dropped at both
  scales, and an event NOTE lists it.

## Scope X

The five families (OPEN_VALVES_TO_ISOLATE, OPEN_VALVES_TO_ISOLATE_DOWNSTREAM, UPSTREAM_ISOLATION_X,
DOWNSTREAM_ISOLATION_X, POSITION_OF_VALVE), 10 per family: B 50, A2 40 through the TAG_SET adapter (A2 is not asked
POSITION). Texts R9 and the two POSITION forms R11: dev OPEN_VALVES_TO_ISOLATE "To isolate {tag} from all upstream equipment, which normally open valves must be
closed?"; held-out OPEN_VALVES_TO_ISOLATE_DOWNSTREAM "To cut {tag} off from all downstream equipment, which normally
open valves must be closed?"; POSITION tag form "What is the normal operating position of valve {tag}?"; POSITION
descriptor form "What is the normal operating position of the {class words} on line {line number}, on the {side} side
of {next_to}?" (`qa/questions/templates_x.py`). G0l: a family that refuses more than a quarter of its
candidates as non-unique stops the launcher and returns to the architect.

## POSITION baselines

The majority code and the text prior: `prereg/position_prior.json`, sha256 `3d48518f16a43262bc23cc74fb7e9d2e56c68d6059d248c71e5195191cbd529a`.

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

## GLM comparison arm (the user's, design 20)

A small descriptive arm, with no gate, no claim and no role in Q4: the frozen V2T-A2 system and policy
`cascade_v4_iso` with GLM 5.3 Flash (`z-ai/glm-5.3-flash`) on one pinned host (fireworks) instead of GPT-6 Luna.
Effort and token caps per tier are A2's (Cypher low, agent high); the pins are `inputs/pin_cypher_glm_fireworks_low.json`
and `inputs/pin_agent_glm_fireworks_high.json`, hashed into E10.
- **Plant choice (fixed here, before any plant exists):** the first sealed plant of each scale in `plan.json` order,
  that is `H100g22p1` and `H1000g22p1`.
- **Questions:** scope R only, read from each plant's A2 question file with the X questions filtered out; the rest of
  the file is byte for byte A2's.
- **Money:** its own hard cap of $2.50, inside the runs ledger; the estimate is A2's sealed rate per question times 1.2-1.9.
- **Report:** paired GLM - Luna accuracy per plant on the same questions with a bootstrap interval (the cascade code's
  5,000 resamples, seed 1), with cost per question, latency and outcome mix beside Luna's.

## Audit

EXP-0008's rule, plus a B stratum half the main sample's size (VALVE_SET and POSITION rows). Judge prompt sha256
`b56c89d5fba7111f4270d47ef4d8cd53796eee5c499fc3cc5e1ce3d9d2312eaa`, judge pin sha256
`e4794d07b865bf29c276f58309ccf35f205f3a71fabf9257260863cf2a0ea6aa` (both equal EXP-0008's).

## Bootstrap

The resample count and seed of the EXP-0008 claims code: 5,000 resamples, seed 1 (`N_RESAMPLES`, `BOOTSTRAP_SEED` in `qa/cascade/stats.py`).
