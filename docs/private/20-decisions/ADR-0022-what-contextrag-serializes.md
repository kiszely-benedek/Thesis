---
adr: 0022
title: ContextRAG serializes the occurrence graph (the sheets as drawn), not the resolver's merged plant
status: accepted
date: 2026-09-26
supersedes: none
---

# ADR-0022 — What ContextRAG serializes

**Question.** `qa-system.md` §19 D8 has ContextRAG (and Hierarchical) serialize the **occurrence graph**: every
sheet's items and off-page connector stubs, `sheet_id` per node, plus `continues_as`. The resolver also builds
`Resolution.plant`, the **merged** graph (paired stubs removed). Which one goes into the prompt?

**Options**
- **S1** Occurrence graph (D8). What an engineer holding the drawing set sees; the same corpus CypherRAG
  (Neo4j), Hierarchical, VectorRAG and PathRAG read (§2.1, D9). The context wall arrives earlier.
- **S2** Merged plant graph. Smaller, but it hands ContextRAG the resolver's output: an input no other
  strategy gets. Hierarchical would have to follow, or "ContextRAG on a routed subset" (§7) stops holding.
- **S3** Both, reported as two ContextRAG variants. Doubles ContextRAG's calls, which are the largest
  prompts in every run, under ADR-0014's budget.

**Recommendation: S1** (D8 as written).
1. ContextRAG and Hierarchical serialize the occurrence view (`qa-system.md` §5); **S1 is the only option
   that keeps every strategy on the same input.**
2. On one sheet the two nearly coincide: EX01 has no pairs, `Resolution.plant` keeps unpaired stubs, so
   they differ only by the `sheet_id` attribute. ChatP&ID's single-sheet setup maps onto both alike.
3. S2 is **sized, not run**: the pilot records its character count next to S1's per corpus (no model call).
4. The thesis states the direction: stubs make the wall arrive earlier, by the measured ratio below.
5. S2 becomes a sensitivity run **only** at a headline point where S2 would fit and S1 does not.

**Why**
- The claim compares retrieval strategies; a different input for one strategy is a confound.
- It is fair to the "sheets" framing: the plant arrives as drawings, and joining them is the system's job.
- At headline defaults S2 adds no content, only fewer characters: the resolver is exact (SMOKE-04, P = R = 1.0).

**Costs.** Measured 2026-09-26 (read-only probe, repo `.venv`, seed 0, budget 16, `flow_greedy`; an
approximation of the §5 serializer, which QA-T3 has not built yet): at 50 units S1 is 377,531 characters
against S2's 278,766; at 1,000 units 7,587,534 against 5,625,832 (17,819 vs 14,687 nodes). S1 is ≈1.35× S2 at
both sizes. Estimate, assuming this ratio holds and size is linear in units: about a quarter fewer units fit
before the wall under S1. QA-T3's real serializer re-measures this.

**Revisit if** the professor contests D8; the pilot's real serializer gives a ratio far from 1.35; or S1 and
S2 would put the wall on different sides of H100 or H1000 (then rule 5 applies).

**Accepted 2026-10-01 (user, in chat).** S1. ContextRAG is the baseline to beat, not the system; the user's priority is selective retrieval (Hierarchical, CypherRAG, PathRAG).
