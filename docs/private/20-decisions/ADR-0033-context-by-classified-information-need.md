---
adr: 0033
title: Select Hierarchical's context by a classified information need over a closed set of evidence shapes, with interchangeable classifiers and fallback to the generic Hierarchical
status: accepted
date: 2026-10-02
supersedes: none — adds a fifth Hierarchical variant beside ADR-0030's four; the ADR-0030 pair stays the fallback
design: 40-design/question-aware-retrieval.md §4
---

# ADR-0033 — Context by information need

## Context

Hierarchical (ADR-0030) chooses sheets from the anchors a question names: the anchor sheets, the route between two
anchors, hop rings; over budget it drops rings or compresses route sheets. One cut rule serves every question. The
user (2026-10-02): different question types need different subgraphs — "which valves must I close so that T-5-2
receives no flow?" needs every upstream branch back to the first operated valve, across sheets; "what is directly
after X?" needs one hop; "how many pumps in unit 5?" needs a unit.

Measured (ROUTE-01 H100 part, `_results.md`): on 76 `UPSTREAM_ISOLATION` questions the generic Hierarchical's strict
routing hit is 0.421 and its evidence-node recall 0.760, **identical across all four route × budget combinations and
all three budgets**. The loss is the anchor-plus-rings selection, not compression. On FLOW_PATH the flow route already
reaches 1.000.

Constraint: retrieval sees only the question text (`Strategy.retrieve(question_text)`); the gold family, answer type
and `k` are never available. And the user wants unforeseen question types handled, so a fixed list of question types
cannot be the mechanism.

## Options considered

**A. Status quo** — one selection rule for all questions. No work. Leaves the measured isolation loss in place and
gives no handle on other shapes.

**B. One hand-written selector per question family**, chosen by matching the family's template. Precise on the
benchmark, but it is the benchmark encoded in code: every new question type needs a new selector, which is the
scalability problem the user named, and it cannot be evaluated on unseen types honestly.

**C. A closed set of evidence shapes ("need labels") + a classifier from text to label + one fixed primitive program
per label + fallback to the generic Hierarchical.** The labels follow the schema, not the families: one per shape
(item, neighbours, signal chain, path, closure, unit) and per direction, plus "closure up to the first operated
valve" in both directions, plus `GENERIC` — 11 in all. Question types are open; shapes are few, so a new type
either maps onto a shape or falls back. Classifiers are interchangeable behind one protocol: rules (free), a
label-probability chat LLM (paid, small), Jev `choice` (paid, small, ADR-0032), and an oracle label for analysis only.

**D. Let an LLM write the selection each time** — that is the graph-tool agent (ADR-0034), built and measured as a
separate arm rather than folded in here.

## Decision

**C**, built as `NeedAwareHierarchical` with three strategy names (`hierarchical_need_rules`, `_labelprob`, `_jev`).
1. Labels and their neutral descriptions are fixed in `question-aware-retrieval.md` §4.1 and frozen at F1
   (ADR-0035) before any held-out family is opened.
2. The rules classifier is written **only** from the dev question templates.
3. Fallback to the generic Hierarchical (ADR-0030 pair) when the label is `GENERIC`, the score is below `tau`, a
   program's precondition fails, or no anchor is found; anchor sheets always stay whole.
4. `tau` (label-probability classifier only) is chosen on D1000 by the highest mean evidence-node recall over
   dev-family questions; ties → the higher `tau`.
5. Every variant is measured free first (NEED-01: need accuracy, fallback rate, evidence-node recall, context size)
   on all corpora; paid accuracy runs follow EXP-0006 (ADR-0035). Gate N1: on H100 at ROUTE-01's settings,
   `hierarchical_need_rules` must beat 0.760 node recall on `UPSTREAM_ISOLATION` before any paid Part 1 run.

## Rationale

- C4 (the hierarchy survives past the wall) is the design claim; a hierarchy that fetches the wrong shape loses for a
  reason that has nothing to do with scale. ROUTE-01 shows that loss on isolation questions.
- Shapes, not types, are what keep this scalable: the classifier's output space does not grow with the number of
  question types, and the fallback makes an unforeseen type cost at most what the generic Hierarchical costs.
- Interchangeable classifiers turn "rules vs a cheap model vs Jev" into a measured comparison (need accuracy and
  end-to-end accuracy on the same questions), which is what the user asked for and what ADR-0032 already prepares.

## Consequences

- Easy: the free NEED-01 report answers "does the shape help" per family with no model call; the oracle label
  separates classifier misses from program misses.
- Harder: a fifth Hierarchical variant, a primitive layer (`qa/plant_api/`, ADR-0034), and a harness-side gold-label
  table that strategies must never import (import-ban test extended).
- A misclassified question gets a narrower context than the generic Hierarchical would have sent; the confidence
  threshold and the "anchor sheets always whole" invariant bound the damage, and NEED-01's confusion matrix measures
  it.
- **Revisit if** NEED-01 shows, on dev families, that misclassified questions lose more than 0.05 evidence-node
  recall against the generic Hierarchical (then add a mode that augments the generic selection instead of replacing
  it); or gate N1 fails.

**Accepted 2026-10-02 (user, in chat), with the main session's recommendations.** U1: 20 questions per family per corpus, **executed in stages** (10 first, extended to 20 only if the first half is informative); U2: the user topped up to $25 total — runs must be budgeted, staged and stopped early when results are clearly poor; U3: classifier pin glm-5.3-flash (logprobs per the 2026-10-02 snapshot); U4: QAR-T1 → T2–T5 (free) → J-tasks → T6–T9; U5: `cypher_agent` should-tier. The answer model is chosen in ADR-0019 from cheaper candidates, not assumed to be gpt-5-mini.
