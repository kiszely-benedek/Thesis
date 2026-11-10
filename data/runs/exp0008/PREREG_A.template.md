# EXP-0008 pre-registration, part A (template)

How to use this file: copy it to `data/runs/exp0008/prereg/PREREG_A.md`, replace every `<<FILL: ...>>`
marker, commit it together with `prereg/seeds.json` (written by `draw_seeds`), and only then say "mehet".
`readiness.py` refuses a part A that still holds a marker, that lacks the current judge prompt hash, or
whose "Frozen code commit" is not HEAD (or an ancestor of HEAD with only `prereg/` changed since).
Part B (the numbers the first stages measure) is written by the launcher at stage M3.

Frozen code commit: `<<FILL: the 40-hex commit of the last F-task, i.e. the code the launcher will run>>`

## 1. What is registered, and what is not

- Registered here, before any test plant exists: the claims and thresholds, the plant design and the
  aggregation, the gates G1 and G2, the audit rule, the money rule, the judge's prompt and pin, and the
  drawn test seeds.
- Measured later and registered in part B at stage M3, before the first test plant is built: the G1
  result, the identity thresholds tau1 and tau2, the judge pilot's cost per call and G2 result, the audit
  capacity that follows from it, and the E9 freeze hashes.
- A defect found after M3 is reported, not fixed, except through the audit rule of section 6.

## 2. Claims and thresholds

Every claim keeps the wording and the pass rule of its ADR; the ADR is the source, this list only names it.

| Claim | Source | Pass rule |
|---|---|---|
| Q4 (primary): 1,000 vs 100 sheets, unpaired across scales | ADR-0053 decision 6 | `<<FILL: copy verbatim; design 5.1 states: passes if the interval contains 0 or lies above>>` |
| K1, K2, K3, Q5 | ADR-0053 / ADR-0046 / ADR-0048 | `<<FILL: copy each pass rule verbatim>>` |
| X1, X2 (single-sheet ladder, ContextRAG) | ADR-0054 | `<<FILL>>` |
| I0-I4, E1-E4 (identity, end to end) | ADR-0063 | `<<FILL>>` |
| M1-M7 (machine cost) | ADR-0051 | `<<FILL>>` |
| V2T - F1 (paired, on the same questions) | design 5.2 | `<<FILL: pass rule of the F1-baseline claims>>` |

## 3. Plant design and aggregation (design 5.1 and 5.2)

- Five independently seeded plants at 100 sheets and five at 1,000: 280 questions each (10 per family, 220
  headline). V2T-A2 and the F1 baseline answer the same questions on all ten; P4 reuses the five 1,000-sheet
  plants (tag-variant corpora, questions re-homed with a proof).
- Single-plant arms: the R4 ladder (1, 3, 10, 30 sheets; ContextRAG high on 1, 3, 10), P3 (I0-I4, on plant 1),
  duplication d0/d50 on the first 100-sheet plant, the concurrency-1 control, EX01.
- Pooled estimate: the mean of the per-plant statistics. Interval: two-stage cluster bootstrap (plants, then
  questions), the resample count and seed of the EXP-0007 claims code `<<FILL: count and seed from qa/cascade/stats.py>>`.
  Paired claims are paired within a plant. With 5 clusters the bootstrap understates between-plant variance
  (stated limitation). The number of plants whose own estimate has the pooled sign is reported, not judged.
- Stated risk: a narrower Q4 interval makes Q4 stricter; a real small loss that passed with one plant can fail with five.

## 4. Gates

- **M0:** the ADR-0059 composition bands (a failed band stops the launcher: U4) and the pool memory probe.
- **G1 (after M1):** on both validation plants cascade_v4_iso >= F1's cascade_v3, and no dev family is below
  50 % on both plants at once. If it fails: stop (U2), one tuning round on X100g21s211 under ADR-0061, then a second fresh pair.
- **G2 (after M2b):** the judge pilot (every known first-measurement defect row of the two groups, at least 8 each, plus 20 controls) judges at least 80 % of the
  known defects `correct` or `ambiguous_question` and at least 80 % of the controls `correct`.
- **M3:** a clean tree under `src/` and the EXP-0008 scripts, and HEAD as named above.
- **Free gates of M4:** round trip and identity of each plant, LINE-01, blocking completeness I0 >= 0.99,
  ContextRAG prompt sizes, `T9.sha256` over the drawn sets.

## 5. Money (design 6)

EXP-0008 may spend at most **$40**: the runs at most $30 cumulative, the audit at most $10 including its
pilot ($2.50). A run's cap is the smallest of its dry-run cap (cache misses x cost per question x 1.5; the cost per question is the first measurement's real spend per tier, per identity arm in M8b and per plant size for ContextRAG in M5, `qa/exp0008/caps.py`), what
is left of its step's ceiling and what is left of the $30; the audit's cap is $10 or what the runs leave of
the $40. The OpenRouter balance must cover a cap before the run starts. Step ceilings: M1 $2.00, M2 $0.05,
M5 $4.90, M6a $10.00, M6b $6.27, M6c $1.44, M8a $0.80, M8b $7.28, M9 $0.25.

## 6. The scorer audit (design 5.3)

- Judge: `anthropic/claude-sonnet-5.5`, reasoning effort low, 2,048 output tokens, blind to the scorer's verdict.
  Judge prompt sha256: `<<FILL: python -c "from plantgraph.qa.audit.judge import template_sha256 as t; print(t())">>`.
  Judge pin sha256: `<<FILL: python -c "from plantgraph.qa.audit.judge import judge_pin as p; print(p().pin_hash())">>`.
- Budget order: the pilot; every wrong row of the ten sealed plants (deduplicated by question and parsed
  answer); a random right sample of at least 2 per family per scale; ContextRAG's wrong rows; more right
  samples up to 5 per family per scale. The runner stops at the cap.
- Disagreements are classified by a script against the graph. A scorer or gold defect is fixed only in the
  scorer or the gold, by a rule from the question text or answer type written down before re-scoring, applied
  family-wide on every plant and arm, by code with a test. An ambiguous question accepts every defensible
  answer. No question is removed or reworded. Judge errors change nothing. The post-audit score is the
  reported result; the pre-audit score and every changed row are in one table.

## 7. Seeds

The test seeds were drawn once by `python -m plantgraph.qa.exp0008.draw_seeds --draw-seed <<FILL: N>>`, before
any plant existed, from the test range minus every seed the first measurement used.

<<FILL: the table printed by draw_seeds (role | seed)>>
