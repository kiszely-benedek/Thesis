---
adr: 0038
title: ContextRAG is not run as a paid arm at plant scale; it is measured on one sheet and recorded as "did not fit" at scale
status: accepted
date: 2026-10-03
supersedes: ADR-0015 / ADR-0022 in part (ContextRAG's paid cells at H100/H1000)
---

# ADR-0038 — No paid ContextRAG at plant scale

**Question.** ContextRAG puts the whole serialized graph into the prompt. Should it be run as a paid arm on the
headline corpora?

**Context.** Measured prompt sizes (PROMPT-04): EX01 18,461 characters; H100 1,649,451; H1000 16,747,117. The
user and the consultant (relayed 2026-10-03): a pipeline that ends in "put the whole graph into the prompt" cannot
scale to real plants of thousands of sheets; the thesis needs a finer method (the plant-API primitives, ADR-0033/34).

**Options**
- **C1** Paid ContextRAG at H100 and H1000, as planned. At H100 a question costs roughly $0.06–0.08 on
  glm-5.3-flash (estimate from the listing price and ~4 characters per token); at H1000 it cannot fit any listed
  window (≤ 2M tokens, listing snapshot 2026-10-02).
- **C2** ContextRAG only on the single sheet EX01 (EXP-0001, 5 scored questions, cents), where ChatP&ID found it
  best; at H100/H1000 recorded as `DID_NOT_FIT` by the existing fit check, which refuses before any call — zero
  cost. A small paid H100 sample only if a later result needs it.
- **C3** Drop ContextRAG entirely.

**Decision: C2** (user, 2026-10-03: "dobjuk el ezt a megközelítést, csak jegyezzük le, hogy miért").

**Why**
- The claim (scale inverts the single-sheet optimum) needs ContextRAG's single-sheet strength and its failure at
  scale. EX01 gives the first for cents; the fit check gives the second for free and is a measured fact (prompt
  size vs window), not an assumption.
- Spending the budget on an approach that is non-scalable by construction is the dead end the user wants to avoid.

**Costs.** No accuracy number for ContextRAG at H100 (where it may fit a 1M-token window). Stated as a limitation;
revisit if a reviewer or the results need it.

**Revisit if** the strategies built on the primitives turn out clearly worse than expected, or the professor asks
for ContextRAG's H100 accuracy.
