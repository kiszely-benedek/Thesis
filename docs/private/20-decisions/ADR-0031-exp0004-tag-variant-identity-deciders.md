---
adr: 0031
title: Measure tag-variant identity resolution (EXP-0004) as blocking plus interchangeable pair deciders, with a held-out variant family against circularity
status: accepted
date: 2026-10-02
supersedes: none — amends kg-construction.md §5.3 "Tag normalisation is Phase 5" (design-note text); the headline resolver stays exact (ADR-0028 item 2)
design: 40-design/hierarchical-and-jev.md §4
---

# ADR-0031 — EXP-0004: identity across sheets when the tag is written differently

## Context

The resolver groups identities by exact `(tag, node_class)` (`kg-construction.md` §5.3). With inexact tags its
identity recall falls to 0.125 / 0.0 / 0.0 (RESOLVE-01, seeds 0–2), precision 1.0 or undefined. Real sets do
write one item differently: OPEN100 shows `RCS-PU-102A` on the symbol and `RC-P102A` in the schedule for one pump
(`open100-annotation.md` line 90), against the rule that designations must match (`pid-structural-rules.md` C11).
Cross-sheet identity is supporting contribution 2 (`00-index.md`).

Two traps:
- **Circularity.** `kg-construction.md` §5.3 already warns that a normaliser tuned to the splitter's own three
  mutations (`splitter.py` `_tag_variant`) scores the resolver against its own noise model.
- **Scale.** All-pairs over equipment occurrences is ≈ 1.0 × 10⁸ pairs at H1000 (arithmetic: 14.44 equipment per
  sheet × 1,001 sheets, SMOKE-07, squared and halved) — no decider can see them all.

## Options considered

**A. A string normaliser inside the resolver, tuned on generated variants.** Free and simple. Circular by
construction, and it cannot use the context an engineer uses (class, unit, neighbours, which sheets touch).

**B. An LLM decides every candidate pair, nothing else.** Uses context, but has no free baseline to beat, so a
good number cannot be attributed to the model.

**C. Blocking, then interchangeable deciders on the same candidate pairs and the same answer key, with a variant
family held out of all tuning.**
- A variant generator with two operator families: **format** (separators, zero padding, case) and **naming**
  (class-code synonyms: `P`↔`PU`, verified on one OPEN100 pump; `E`↔`HX`, from OPEN100's `CVCS-HX-111`, where
  reading HX as heat exchanger is our interpretation, unverified; and the unit number moved to a prefix, as in
  OPEN100's `RC`/`RCS` system codes).
- Blocking by `(node_class, digits of the tag with zeros removed)`, scored for pair completeness and reduction
  ratio.
- Deciders: exact (today), string similarity, string + context rule, label-probability chat LLM, free-text chat
  LLM, Jev `noul` (ADR-0032). Thresholds on dev only, on the **format** family only; the naming family is unseen
  by every decider until test.

**D. Real data only (OPEN100).** No graphml anchor exists for the visually confirmed identities
(`open100-annotation.md` lines 85–103), and there are at most 5 such items; it cannot give a P/R number.

## Decision

**C.** The headline corpora keep exact tags (ADR-0028); EXP-0004 runs on variant copies of the same seeds
(H100-V, H1000-V; dev D100-V), every reference occurrence written as a variant (`variant_rate = 1.0`).
The OPEN100 strings are used as a qualitative check only (design note §4.8), never as a metric.

## Rationale

- Shared candidates and answer key make the deciders comparable; the free deciders set the bar a paid one must
  clear.
- Holding the naming family out of tuning answers the circularity warning with a measurement: a decider that only
  learned our format operators shows it as a drop on the naming family.
- Blocking keeps the paid pair count bounded and is measured, so a recall loss in blocking is not blamed on the
  decider.
- The claim link: cross-sheet identity is what turns sheets into one plant graph; without it `k_identity` crossings
  (ADR-0028) are invisible to every strategy.

## Consequences

- `SplitConfig` gains `tag_variant_profile` (default `"legacy"`, which keeps `_tag_variant` and RESOLVE-01
  reproducible) and `variant_rate`.
- `resolution/` gains a candidate step and a `PairDecider` protocol; LLM-backed deciders live outside
  `resolution/` so the resolver stays offline and import-clean.
- Variants that change the number itself are not recoverable by this blocking key; stated as a limitation, and
  blocking recall is reported.
- **Revisit if** blocking pair completeness on D100-V is below 0.99 (add a second key), or the candidate count at
  H1000-V makes the paid deciders unaffordable (then sample candidates, stratified by family, and say so).

**Accepted 2026-10-02 (user, in chat).** As written, with `variant_rate = 1.0` and the optional 0.5 run.
