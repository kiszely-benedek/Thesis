---
name: paper-intake
description: Read a paper properly and file it as a structured, queryable literature note. Takes an arXiv ID, DOI or URL. Use whenever a new paper enters the reading list.
---

# Paper intake

Argument: an arXiv ID (`2603.22528`), a DOI, or a URL.

## Steps

1. **Fetch the full text**, not the abstract. For arXiv try `https://arxiv.org/html/<id>v1` first, fall back to `https://arxiv.org/pdf/<id>`.
2. **Check for a duplicate** in `docs/private/10-literature/` before writing. Update the existing note rather than creating a second one.
3. **Write** `docs/private/10-literature/<arxiv-id-or-slug>.md` using the structure below.
4. **Add one line** to the table in `docs/private/10-literature/00-reading-list.md`.
5. If the paper changes the novelty picture, say so plainly in your reply and flag that ADR-0001 may need revisiting.

## Note structure

```markdown
---
id: <arxiv id or DOI>
title: <full title>
authors: <surnames>
year: <year>
status: read | skimmed | queued
relevance: core | baseline | method | dataset | context
tags: [digitization, graphrag, dataset, evaluation, ...]
---

## Claim
One sentence: what the paper says it contributes.

## Method
The pipeline, concretely. Model names, representations, tools.

## Evaluation  ← the most important section
Documents/pages used. Number of questions. Who wrote the ground truth. Number of runs.
Metrics and exact numbers.

## Relation to this dissertation
Does it take territory from us, give us a baseline, or hand us a method?
Does it evaluate at single-sheet scale? (Almost all of them do — record it.)

## Limitations they admit
Quote them. Their stated limitations are our contribution surface.

## Reusable
Anything we can lift directly: metric definitions, rubrics, datasets, code links.
```

Keep it under a page. Precision beats completeness — exact numbers, exact scale, no rounding from memory.
