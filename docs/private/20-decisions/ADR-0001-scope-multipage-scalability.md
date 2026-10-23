---
adr: 0001
title: Scope the dissertation on multi-page / plant-region scale
status: accepted
date: 2026-08-23
supersedes: none
---

# ADR-0001 — Scope the dissertation on multi-page / plant-region scale

## Context

A novelty check on 2026-08-23 (full-text reads plus web search) mapped the field:

| Territory | Status |
|---|---|
| Single-page P&ID image → graph | **taken** — Stürmer 2411.13929, Prusty 2505.11976, MLLM 2607.19568, DigitizePID, Mani (CVPRW 2020) |
| Single-sheet DEXPI → GraphRAG QA | **taken** — ChatP&ID 2603.22528 |
| Rule-based P&ID graph validation | **taken** — Schulze Balhorn 2502.18493 (33 rules) |
| **Multi-page / multi-document / region scale** | **open** — commercial only (SymphonyAI, Acuvate, Cognite); no published method, benchmark or dataset |

Every academic paper in this field evaluates one sheet at a time. ChatP&ID's headline result — ContextRAG (prompt-stuffing the condensed graph) beats all retrieval at 0.91 — comes from a single page: 212 nodes condensed to 53.

The arithmetic at target scale: 100 pages × ~382 nodes/page (PID2Graph OPEN100 mean) ≈ **38,000 nodes**, still ~10,000 after 4× conceptual condensation, and ×10 documents for a region. Prompt-stuffing is not available. Every conclusion in the state of the art is therefore untested in the regime this work targets.

## Options considered

**A. Improve single-page digitization accuracy.** Well-defined, PID2Graph gives ready ground truth. But four groups are already there and the marginal contribution is small.

**B. Extend rule-based validation.** Useful, but 2502.18493 owns the framing and rules are hand-written — the contribution would be quantity, not insight.

**C. Multi-page / plant-region scale.** Unaddressed academically, with a real industrial pull. Costs: no dataset exists, so a benchmark must be built first; digitization quality becomes a confound.

## Decision

**Option C.** Scope the dissertation on scaling GraphRAG from a single sheet to a multi-document plant region.

## Rationale

It is the only one of the three that is genuinely open, and its openness is documented rather than assumed. It also inherits a ready-made argument: the published optimum is a single-page artifact, which gives the work an obvious and defensible claim to test rather than a vague "we scaled it up".

## Consequences

**Enables** — a clear falsifiable claim (find the crossover where prompt-stuffing loses); a second contribution in the benchmark itself; direct relevance to industry practice.

**Costs** — a benchmark must be constructed before anything can be measured (see ADR-0004); results depend on digitization quality we do not control, so error propagation must be measured as a variable rather than treated as noise.

**Revisit if** — a paper appears with a public multi-sheet P&ID benchmark and a scale study. `/lit-gap-check` runs fortnightly against exactly this risk.

**Explicitly out of scope** — beating the state of the art on single-page symbol detection; inventing new validation rules.
