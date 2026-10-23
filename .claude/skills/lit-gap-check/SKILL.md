---
name: lit-gap-check
description: Novelty watch. Searches for new work that could overlap the dissertation's claim and reports whether the contribution is still open. Run every two weeks, or before writing any section that asserts novelty.
---

# Literature gap check

Guards against being scooped. A directly relevant paper (arXiv 2607.19568) appeared in July 2026 without either the user or their professor noticing, so this runs on a schedule.

## The claim being defended

> Multi-page / multi-document / plant-region GraphRAG over engineering diagrams is unaddressed in the academic literature. The published optimum (prompt-stuffing a condensed single-sheet graph) is an artifact of single-page evaluation and inverts at scale.

## Search

Run these, plus any new phrasing that seems warranted:

- `arxiv P&ID multi-sheet OR multi-page knowledge graph`
- `off-page connector cross-drawing linking digitization`
- `GraphRAG scale engineering diagrams <current year>`
- `plant-wide knowledge graph entity resolution tag matching`
- `hierarchical graph retrieval large document corpus industrial`
- citations of arXiv 2603.22528 (ChatP&ID) and 2411.13929

Cross-check anything found against `docs/private/10-literature/` — skip what is already filed.

## Report

For each genuinely new and relevant paper: ID, title, date, **evaluation scale**, and a one-line threat assessment (`no overlap` / `adjacent` / `overlaps — act`).

Then a verdict line: **claim still open** / **claim narrowed** / **claim taken**.

Append the run to `docs/private/10-literature/_novelty-log.md` with the date, even when nothing was found — a record of negative results is evidence for the thesis, and the professor will ask how thoroughly this was checked.

If anything is `overlaps — act`, run `paper-intake` on it and say clearly what part of the contribution is now at risk.
