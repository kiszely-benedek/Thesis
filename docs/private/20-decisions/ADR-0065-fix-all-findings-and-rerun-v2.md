---
adr: 0065
title: Fix every review finding, then re-run the v2 measurement (EXP-0008) on five regenerated plants per scale, under a fresh pre-registration, a $40 cap, an LLM scorer audit and a single launcher started only on the user's word
status: proposed
date: 2026-11-07
supersedes: in effect, the first v2 measurement: EXP-0007 V2T-VAL, R4, R5, INFRA-2 (ADR-0060, ADR-0061, ADR-0062) and EXP-0004 P1–P4 (ADR-0063). Those records stay on file, marked superseded. Amends ADR-0064 (the demo's plant becomes H1000g21p1) and the VALVES_ON_PATH definition of heldout-families.sealed.md H3 (hops at item level). The claims and thresholds of ADR-0053, ADR-0054, ADR-0051 and ADR-0063 carry over unchanged.
---

# ADR-0065 — Fix all findings; re-run the v2 line as EXP-0008

## Context

- A read-only review of the frozen code (2026-11-06/07) found about 45 defects. Checked independently
  (`40-design/review-fixes.md` §3), four move first-measurement numbers:
  1. **VALVES_ON_PATH gold** counted raw nodes, so untagged fittings counted as hops. Gold differs from the
     item-level count on 5/20 (H100g2) and 8/20 (H1000g2) sealed questions. Every agent answer scored wrong there
     equals the item-level count.
  2. **Numbers in set answers** were parse failures: 20 rows in 15 scored runs.
  5. **INFRA-2's database-only Cypher replay** skipped repaired first attempts: 74 timeouts at H1000g2. Estimated,
     the share is about 49 % rather than 29.8 %.
  10. **Generator realism.** Distillate and side draws are unwired, trims sit on the wrong sheet, fuel-gas sensors
     sit on the furnace, and stubs are double-counted in the composition statistics.
- The user (2026-11-07) gave six directions:
  - fix everything and re-run the measurement as a whole, no stitched-in corrections;
  - test on several plants and aggregate;
  - add an independent reasoning-LLM check of the scoring;
  - keep EXP-0008 under $40 (estimate about $30–32);
  - start nothing, not even the free steps, before saying "mehet" after reading the study map;
  - then run everything from one detached launch.
- ADR-0053: once sealed questions are spent, a system change needs a new sealed set.

## Options considered

**How to correct**
- **A. Correct in place**: registered numbers stay, re-scored ones beside them. Rejected by the user.
- **B. Fix all, re-run the v2 line on regenerated plants with fresh seeds, new pre-registration and freeze.**
- **C. Fix all, re-run only R5 on the old plants**: the other experiments would stay on another generator and system,
  and the sealed plants have been read.

**Plants (for B)**
- **B1. One plant for every arm.** Cheapest. The headline then covers "this plant" only.
- **B2. Five plants for every arm** (ladder, duplication and P3 too). About $80 with the audit, over budget.
- **B3. Variant B.**
  - Five plants per scale for the headline claims: V2T-A2, the F1 baseline, and P4 on the five 1,000-sheet plants.
  - One plant for the single-sheet ladder and for the descriptive arms (duplication, concurrency control).
  - P3's registered four-corpus set on plant 1, plus the four other 1,000-sheet V corpora that P4 needs anyway.
- **B4. Three plants per scale.** A cluster bootstrap over 3 plants has only 10 distinct resamples.

**Scoring check (for B)**
- **S1. Deterministic scorer only.** It carried defect 1 through a whole run.
- **S2. An LLM judge as the primary scorer.** Accepts paraphrase, but is non-deterministic and itself unaudited.
- **S3. Deterministic scorer primary, LLM judge as a capped, pre-registered audit.** Fixes may go into the scorer or
  the gold only.

**Starting the runs (for B)**
- **L1. The main session runs the stages one by one.** Many human steps, easy to run something early.
- **L2. One resumable launcher** that enforces every gate and cap and is started only on the user's word.

## Decision

1. **B, B3, S3, L2.**
2. Every finding is fixed in code (tasks F1–F15). A PLAUSIBLE finding stays unfixed only if no failing test can be
   written for it ("not reproduced").
3. The generator becomes `v2.1` (a `v2` config is refused); ids `g21` with a plant index; system V2T-A2 = V2T-A plus
   the fixes, no tuning. VALVES_ON_PATH counts valves on an item-level shortest route, and a pair is asked only if
   the count is unique.
4. Gates:
   - G1: re-validation of V2T-A2 against F1 on two fresh plants, no re-tuning unless it fails;
   - G2: judge pilot on first-measurement rows with known truth.
5. Claims and thresholds are the registered ones. The headline claims are pooled over five plants per scale with a
   two-stage cluster bootstrap. Paired claims are paired within plant; Q4 is unpaired across scales. Single-plant
   arms keep their registered computation.
6. **Budget.**
   - EXP-0008 has a hard cap of $40, enforced by a ledger over all EXP-0008 call records: runs ≤ $30, audit ≤ $10
     including its pilot.
   - Estimate: runs $21.97, audit ≈ $9, total ≈ $31 (design §6, every line sourced).
7. **Audit.**
   - Judge `anthropic/claude-sonnet-5.5`, blind to the scorer's verdict.
   - Budget order: pilot; every wrong row on the ten sealed plants (deduplicated); a minimum right sample of 2 per
     family per scale; ContextRAG wrong rows; more right samples.
   - The sample is sized by rule from the pilot's measured cost.
   - Fixes go only into the scorer or the gold, family-wide, on every arm and plant. The post-audit score is the
     reported result, with the pre-audit score and every changed row in the same report.
8. **Launch.**
   - Nothing of EXP-0008 runs before the user's "mehet". `data/runs/exp0008/run_all.sh` then runs M0 → M10 detached.
   - It stops cleanly, with a resume point, only on a failed gate (U4, G1, G2), a cap or ledger hit, an unreadable
     balance or an infrastructure error.
   - It logs `===` lines and never commits.
9. **Pre-registration and freeze precede every test plant.**
   - Part A (claims, design, gates, audit rule, ledger, judge hashes and the drawn test seeds) is committed before
     the button.
   - Part B (G1 result, τ values, the pilot's cost and the audit sizes) and the E9 freeze hashes are written by the
     launcher at M3, after M2b and before M4 generates the first test plant.
10. v1 stays as recorded, with a note on the six rows the parse defect touches; EX01 is re-run.
11. The first measurement keeps its files and hashes. Each record gets a "superseded by EXP-0008" line naming the
    defects.

## Rationale

- One number per claim from a system with no known defect is what a thesis can defend; the first measurement
  explains why the second exists.
- **Where the plants go.** Five plants are put where the claims about scale live. Q4, the cascade claims, V2T − F1
  and the identity-at-scale claims E1–E4 then cover "plants of this kind". The single-plant arms are either
  descriptive or the single-sheet ladder, whose most expensive arm (ContextRAG) does not scale to many plants within
  the budget.
- **The audit** targets exactly the failure that slipped through once. Its rule keeps it from becoming tuning on the
  test.
- **The launcher** makes the run reproducible and keeps the user's control: one decision ("mehet") after reading the
  study map, no human step that could alter the order, and the freeze inside the chain at the only point where all
  of its inputs exist.

## Consequences

- **Machine time:** about 72 h, about 6–7 calendar days with gates, after the coder tasks.
- **Lost by the cuts:**
  - the ladder (X1/X2) and P3 (I0–I4) stay single-plant, question-sampling results, as in the first measurement;
  - the duplication interval is about √2 wider (220 instead of 440 paired headline questions);
  - the audit's right sample may be small (at least 88 rows), and ContextRAG rows are covered only if the budget
    allows.
- **Q4 gets stricter:** its rule (interval contains 0 or lies above) tightens with a narrower interval, so a small
  real loss that passed with one plant may fail with five. The pre-registration says so.
- **Demo v2:** waits for the final runs in T3, T6 and T7; the demo's Neo4j database ends on H1000g21p1.
- **Revisit if:**
  - G1 or G2 fails;
  - a composition band breaks (U4);
  - the pool memory probe fails;
  - the pilot's per-call cost is so high that the wrong rows do not fit the $10;
  - a defect found after the freeze is serious enough for a third round.
