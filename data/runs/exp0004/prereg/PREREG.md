# EXP-0004 pre-registration (before the first decider run on a test corpus)

Design `docs/private/40-design/exp0004-v2.md` §5.5, §6, §7, §10; ADR-0063 (accepted 2026-11-04).
Written 2026-11-04, after P1 and P2 on the dev corpus and before any decider has seen a test corpus.
Every file the test runs depend on is hashed in `PREREG.sha256`; `run_p3.sh` refuses to start when one differs.
**Nothing listed here changes after the first test-corpus run.** A defect found then is reported, not fixed.

## 1. System and freeze

- System V2T-A (`cascade_v4_iso`, both GPT-6 Luna tiers, setting A), freeze E8 = `4dfad69` (`../E8.commit`).
- Test runs read only the dev thresholds (`../dev/D100g2d100Vf/taus.json`); nothing is tuned on a test corpus.

## 2. Corpora

| Role | Corpus | Sheets | Seed | Duplication | Families | Candidates (IDBLOCK-01, `b2f4bd0`) |
|---|---|---|---|---|---|---|
| dev (tuning) | `D100g2d100Vf` | 100 | 1 | 1.0 | format | 200 (93 true) |
| test | `H100g2V` | 100 | 5002 | 0.25 | format + naming | 41 (21 true) |
| test | `H100g2d100V` | 100 | 5002 | 1.0 | format + naming | 128 (85 true) |
| test | `H1000g2V` | 1,000 | 5003 | 0.25 | format + naming | 794 (214 true) |
| test | `H1000g2d100V` | 1,000 | 5003 | 1.0 | format + naming | 1,923 (863 true) |

The naming family (class synonyms, unit prefix) is generated for the first time inside the test runs.
A test corpus whose rebuilt candidate count differs from this table stops the run.

## 3. Deciders, fixed

| Id | Rule | Fixed parameter |
|---|---|---|
| D0 | equal tag and class (today's resolver) | none |
| D1 | `SequenceMatcher` ratio of the tags after upper-case and keeping `[A-Z0-9]` | τ₁ = 1.0 |
| D2 | D1's score ≥ τ₂ and A's unit (else its sheet's units) is among the units printed on B's sheet | τ₂ = 0.857142857143 |
| D4 | GPT-6 Luna on the pair card, JSON `{"same_item", "reason"}`, no threshold | prompt sha256 `8a4095d56d8036dad66a5cc8039a60f6ddf2ea3110a75250fb67c593bb994a98`, pin hash `acf24178d47dd4873fc2a36e7f67efbf2dc7ab5de694711f3b934e6ef4f4c21d` |

- τ₁, τ₂: maximise pair F1 on `D100g2d100Vf` only, grid = every observed score, ties to the higher τ.
- D4: pin `data/runs/exp0007/inputs/pin_cypher_luna_low.json` (openai/gpt-6-luna, reasoning effort low, seed 0),
  the V2T-A Cypher-tier pin, unchanged. The card format is the code in `resolution/identity_card.py` and
  `exp0004/d4_prompt.py` (hashed). The prompt names no variant operator and no synonym. A parse failure counts as
  "not accepted" and is reported. The prompt was not changed after P1 (0 parse failures in 20 calls).

## 4. Truth, grouping, scoring

- Truth: two occurrences are the same item when they belong to the same gold identity group (all pairs).
- Accepted links go through the one-link-per-other-sheet rule and the same-sheet split before scoring.
- Pair level P/R/F1 on the candidate set; F1 = 2tp / (2tp + fp + fn) for the point estimate and in every resample
  (a decider that accepts nothing has F1 0.0). Group level with `score_identity_groups`.
- 95 % intervals: cluster bootstrap over blocks, 2,000 resamples, seed 20261104; differences between deciders are
  paired on the same resampled blocks.
- Family attribution: a pair gets the family and operator of the first rewritten occurrence in it (first, then
  second); a pair with no rewritten occurrence has family `none` and counts only in the `all` subset.

## 5. Claims

Resolution claims (corpus `H1000g2d100V` unless stated):

| Id | Claim | Pass if |
|---|---|---|
| I0 (gate) | blocking keeps the gold links | completeness ≥ 0.99 on every test corpus |
| I1 (manipulation check) | the naming family is harder than the tuned one for D1 | F1(D1, format) − F1(D1, naming) > 0, CI lower bound > 0 |
| I2 (context) | context without a model helps | F1(D2) − F1(D1), both families, CI lower bound > 0 |
| I3 (model on unseen variants) | the model generalises where tuned rules do not | F1(D4, naming) − F1(D2, naming), CI lower bound > 0 |
| I4 (scale, descriptive) | — | F1 at H1000 minus H100 per decider, with CI; candidate and cost elasticity `e = ln(c1000/c100)/ln(10)` |

End-to-end claims (`H1000g2V`, the sealed H1000g2 question set rehomed, R5's 440-question headline scope,
paired bootstrap from the EXP-0007 claims code):

| Id | Claim | Pass if |
|---|---|---|
| E1 (primary) | tag variants with the exact resolver cost accuracy at plant scale | acc(V, D0) − acc(R5), CI upper bound < 0 |
| E2 | D2 wins accuracy back | acc(V, D2) − acc(V, D0), CI lower bound > 0 |
| E3 | D4 wins accuracy back | acc(V, D4) − acc(V, D0), CI lower bound > 0 |
| E4 (non-inferiority, D2 and D4 each) | the decider restores the headline | acc(V, Dx) − acc(R5), CI lower bound > −0.03 |

## 6. Arms (all run; none is picked afterwards)

- Resolution (P3): D0, D1, D2, D4 on each of the four test corpora.
- End-to-end (P4): D0, D2, D4 links on `H1000g2V`, three loads, both tiers; baseline R5 `S7-{CYP,AG}-H1000g2`.
  `H100g2V` end-to-end is not run (ADR-0063 question 1, answered as recommended).

## 7. Money caps

- P3, per test corpus: cap = 1.5 × candidates × $0.000171 (R5's p90 small-call cost). Total over the four corpora:
  1.5 × 2,886 × $0.000171 = $0.740. Measured basis on dev: $0.000105 per live call (P1 + P2, 200 live calls).
- P4: cap = the free dry run's miss count × R5's per-question tier cost × 1.5, upper bound $4.44 for three arms.

## 8. What was known before registration (dev only, stated so nothing hides)

`D100g2d100Vf`, format family only, pair level, 95 % CI:

| Decider | P | R | F1 (all) | F1 (format) |
|---|---|---|---|---|
| D0 | n/a | 0.000 | 0.000 | 0.000 |
| D1 | 1.000 | 0.828 | 0.906 [0.855, 0.947] | 0.906 [0.855, 0.947] |
| D2 | 0.979 | 0.989 | 0.984 [0.957, 1.000] | 0.995 [0.982, 1.000] |
| D4 | 0.895 | 0.914 | 0.904 [0.849, 0.951] | 0.939 [0.897, 0.975] |

D4 − D2 on dev: −0.080 [−0.127, −0.039] (all), −0.055 [−0.093, −0.023] (format). D4 misses 8 of 16
`unpad_sequence` pairs and accepts some distinct items (V-/D- prefix pairs, A/B spares, `E-401`/`E-4001`).
This is recorded, not acted on: D4 has no threshold and its prompt may change only for parse failures.
The naming family has not been generated on any corpus a decider has seen.
