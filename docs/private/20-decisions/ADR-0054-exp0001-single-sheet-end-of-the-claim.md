---
adr: 0054
title: Measure the single-sheet end of the claim on a size ladder (H1, H3, H10, H30) of fresh headline corpora with ContextRAG at high effort against the frozen cascade_v3 and its tiers, plus a descriptive EX01 anchor with ChatP&ID's five scored questions; primary claim = the slope of the accuracy gap over log size; H100 only on a pre-registered trigger
status: accepted (user, 2026-10-11) — U1–U9 as recommended
date: 2026-10-11
supersedes: none. Invokes ADR-0038's clause "a small paid H100 sample only if a later result needs it" with a pre-registered trigger. Deviates from ADR-0013 E3 for EXP-0001 (no LLM judge, point 6). Settles ADR-0044 U3 (EX01 control valves, point 7). Corrects in part ADR-0053 decision 2's wording "ContextRAG at H100 … DID_NOT_FIT" (see Consequences). ADR-0021, ADR-0022, ADR-0050, ADR-0052 and the F1 freeze of ADR-0053 carry over unchanged.
design: 40-design/exp0001-single-sheet.md
---

# ADR-0054 — EXP-0001: the single-sheet end of the claim

## Context

The plant-scale end is measured: cascade_v3 0.937 / 0.917 acc@120 at H100 / H1000 for $0.00065 / $0.00071 per
question (EXP-0002). The single-sheet end is not: no ContextRAG answer exists in the project on any model or
corpus. The claim says ContextRAG's single-page optimum (ChatP&ID 0.91, GPT-5-mini, one file, 19 questions) is an
artifact of single-page evaluation and inverts with scale. Showing that needs ContextRAG's strength where it
should be strong, on the same pipeline, model and question families as EXP-0002.

Constraints:
- **F1 freeze.** The strategy code, prompts, pins, params and policies measured in EXP-0002 must not change;
  otherwise EXP-0001 measures a different system.
- **Model.** GPT-6 Luna on the OpenAI host lists 922,000 max prompt tokens and a price step at 272,000 tokens
  (listing 2026-10-10). The H100 ContextRAG prompt (1,649,451 chars) therefore very likely fits; H1000
  (16,747,117 chars) cannot (it would need ≥ 18.1 chars per token).
- **Budget.** "A few dollars". The tiers cost ≈ $0.0004–0.0007 per question (measured); ContextRAG costs scale
  with prompt size (≈ 16.3k chars per sheet, PROMPT-04).
- **EX01** has only 5 scorable ChatP&ID questions (ADR-0021), and its loop tags sit on actuators, not valves.

Nine points have a real alternative.

## Options considered

**1 — Substrate**
- **A. EX01 only.** The literal reproduction. n = 5, one point on the size axis: cannot show where anything flips.
- **B. Synthetic ladder only.** Continuous with D/H corpora, ≈ 96 questions per size, but no real DEXPI file and
  none of ChatP&ID's questions.
- **C. Both:** the ladder carries the claim; EX01 is a descriptive anchor (no claim on n = 5).

**2 — Ladder sizes**
- **A. 1 / 5 / 10 / 25.** Uneven on a log axis.
- **B. 1 / 3 / 10 / 30 (≈ ×3 steps), one plant per size; H1 = the first seed in 100…399 whose one-unit headline
  corpus has exactly one sheet.** Even on log size; H30 stays under the 272k-token price step.
- **C. Many points (1…100) with replicate plants per size.** Better curve, ≈ 3× the cost and a pooled report
  that does not exist yet.
- For H1, the alternative to the seed scan is accepting the usual two-sheet one-unit corpus, which is no longer
  "one sheet".

**3 — ContextRAG reasoning effort (Luna)**
- **A. Low**, like the Cypher tier: cheapest, but a weak baseline invites "you crippled the baseline".
- **B. High**, like the agent's final answer: ContextRAG's single call is its whole work, so this is its strongest
  reasonable setting.
- **C. High as the arm, low at H1 and H10 as a sensitivity check** (≈ $0.7 more).

**4 — Primary claim**
- **A. Per-size tests only.** Four comparisons, each weak at ≈ 70–96 paired questions; "where it flips" depends
  on which test happens to cross.
- **B. One trend test: the slope of Δ = acc@120(ContextRAG) − acc@120(cascade_v3) over log10(sheets), paired
  bootstrap, on the families present at every size.** Uses all sizes at once and removes the family-mix
  confound (one sheet has no sheet- or unit-crossing families).
- **C. As B on all families.** More questions, but the mix changes with size.

**5 — H100**
- **A. Never** (ADR-0038 as applied). The accuracy flip may then be unobserved.
- **B. Always**, 24 questions ≈ $2.7 (≈ 550k prompt tokens each at $0.20/M).
- **C. Conditional:** only if no accuracy flip is seen by H30, X5 predicts H100 fits, and the user approves.

**6 — EX01 scoring**
- **A. LLM judge with ChatP&ID's rubric** (ADR-0013 E3). QA-T16 was never built; a judge needs its own
  agreement check, which 5 questions cannot supply.
- **B. A checklist of required tags, order and statements, written before any answer from ChatP&ID's references
  and our imported graph; blind manual review (answers shuffled, arms hidden); the user confirms.**
- **C. Reword the questions into typed answers for exact scoring.** Breaks the natural-questions rule.

**7 — EX01 control-valve tags (ADR-0044 U3)**
- **A. Import as is:** `HV4750.01`, `PV4712.02`, `TV4750.03` stay on `ActuatingFunction` nodes; valves keep `C1`.
  This is the structure pyDEXPI gives, so it is the input ChatP&ID's pipeline read.
- **B. Apply ADR-0044 A-i in the importer** (the valve takes the loop tag). Matches our generator's convention, but
  changes the reproduction's input and adds importer code.

**8 — EX01 model**
- **A. Luna only.**
- **B. Luna, plus ContextRAG on GPT-5-mini (ChatP&ID's model) on EX01 only** (≈ $0.08).

**9 — Freeze and pre-registration**
- **A. Informal:** run at HEAD, describe afterwards.
- **B. As ADR-0053 5B:** user commit E; `E.sha256` over inputs, questions, the design note and this ADR; the run
  script refuses on any mismatch or on a `src` change since F1 outside an allow-list (T's paths plus
  `src/plantgraph/qa/exp0001/`); a free cache-only replay of `ST-AG-H100` must be byte-identical.

**Question count** (not numbered as a point; follows from the budget): 4 per family, ≤ 96 per size. 2 per family
halves the cost and doubles the CI width; 10 per family costs ≈ $10 at the ContextRAG arms alone (estimate).

## Decision (recommended; awaiting the user)

1. **C — both substrates.** EX01 is reported, never claimed.
2. **B — H1 (seed scan), H3, H10, H30 at seed 3; 4 questions per family.**
3. **C — ContextRAG at high effort; low at H1 and H10.**
4. **B — primary X1: the slope's 95 % CI upper bound < 0 on the common-family scope.** Secondary: X2
   non-inferiority at H1 (CI lower bound of Δ ≥ −0.05), X3 accuracy flip point, X4 cost and latency flip, X5 the
   wall from the measured chars-per-token ratio, X6 effort sensitivity (design §7, wording fixed there).
5. **C — H100 conditional,** with the same 24 questions' cascade answers joined from the sealed runs.
6. **B — checklist + blind review,** a recorded deviation from ADR-0013 E3 for EXP-0001.
7. **A — EX01 as imported.**
8. **B — add GPT-5-mini ContextRAG on EX01.**
9. **B — commit E, `E.sha256`, allow-list, replay guard.**

## Rationale

- **It measures the claim, not a proxy.** The claim is that the best strategy depends on scale. One pipeline, one
  model, one family set, only the corpus size moving: that is the cleanest form of the test. EX01 ties the
  synthetic H1 to the real file and ChatP&ID's own questions.
- **The steelman is the honest baseline.** ContextRAG at high effort is the version a sceptic would ask for. If it
  still loses with size, the loss is not an artefact of a weak setting; if it wins at H1, the thesis shows the
  published optimum is real before showing it fade.
- **One trend test answers "where it flips" without forking.** Per-size tests are reported, but the verdict rests on
  one pre-registered slope over the families every size can ask.
- **Boring where it can be.** No new generator code (the T-commit `sealed_set` and `per_family` build every
  question set), no change to frozen code, the sealed scripts' structure reused. New code is limited to an EX01
  runner and a report.
- **Spend follows evidence.** The expensive H100 point runs only if the cheap ladder leaves the accuracy question
  open.

## Consequences

- **Cost ≈ $4.5 (estimate)** for stages A and B, caps ≈ $8.9, a gate after the ContextRAG smoke stops at a
  projected $6. Stage C ≈ $2.7 (cap $4). Time: ≈ 1–1.5 coder days, ≈ 2–2.5 h of runs.
- **Easy to audit:** the same mechanism as the sealed run; every ladder number joins to frozen pins.
- **Correction recorded here:** ADR-0053 decision 2 and the sealed report (R2, D7) call ContextRAG at H100
  `DID_NOT_FIT`. On Luna it fits unless the tokenizer packs fewer than 1.79 chars per token, which no plausible
  GraphML ratio does (estimate 2.5–3.5, unmeasured until EXP-0001). The correct wording is "not run at H100
  (ADR-0038); does not fit at H1000". X5 measures the ratio and gives the wall's position (≈ 140–200 sheets at
  2.5–3.5 chars per token — an estimate until measured).
- **Honest limits:** one plant per size; one repeat on the ladder (Luna takes no temperature); effort asymmetry
  between ContextRAG (high) and the Cypher tier (low); the serializer is frozen, so a compact rendering that could
  move the wall is not tested; EX01 is n = 5, scored by our checklist, not ChatP&ID's judge.
- **Forecloses:** fixing ContextRAG or the cascade during EXP-0001. Any such change is a new arm under a new ADR.
- **Revisit if** a frozen file must change (then EXP-0001 is post hoc and says so); Luna's price or window changes
  before the run (re-estimate, then ask); E-T1's dry run shows a tier cannot run on EX01 (the arm is reported "not
  applicable", the frozen code stays); the H1 seed scan finds no one-sheet unit (fall back to the two-sheet seed 100
  and state it).
