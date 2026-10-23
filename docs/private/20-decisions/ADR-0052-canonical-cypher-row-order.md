---
adr: 0052
title: Put the Cypher tier's result rows in a canonical order before the answer prompt, and re-run the Cypher tier
status: accepted (user, 2026-10-11)
date: 2026-10-11
supersedes: none; changes `format_context` in `qa/strategies/cypher_rag.py` (ChatP&ID Algorithm 4 as implemented)
evidence: INF-T4b verification (2026-10-11), `_results.md` CASCADE-V3; findings log L23
---

# ADR-0052 — Canonical row order in the Cypher tier

## Context

Replaying the stored Cypher-tier runs `CYPL-{D100,D1000}` after a database reload missed the LLM cache. INF-T4b
re-ran every recorded query on fresh loads and rebuilt the answer prompt:

- D100, 149 answered questions: 135 / 138 identical prompts on two reloads, 14 / 11 differing; D1000 (one
  reload): 125 identical, 17 differing.
- Every differing prompt has the recorded length; the content is the same and only the order differs.
- All queries with `ORDER BY` were identical (D100 56/56, D1000 43/43).
- Two causes: the list returned by `labels(n)` comes back in another order (D100 10, D1000 9), and rows of a query
  without `ORDER BY` come back in another order (proven by permutation for 3–4; 1–4 more too long to permute).
  The row order changed between the two D100 reloads as well.

So the Cypher tier's answer depends on store layout, not only on the plant: the same plant and the same query can
give the model the same facts in another order. Results are not reproducible across a reload, and the cache cannot
replay them.

## Decision

`format_context` writes the rows in a canonical order:

1. **Label lists are sets.** A list value whose elements are all node-label names of the store's schema is sorted.
   The label names come from the source the tier already holds (the schema it shows the model), not from a
   guess on the values.
2. **Rows of an unordered query are a set.** When the query has no `ORDER BY` (case-insensitive, anywhere in the
   text), the rows are sorted by their JSON line (already written with sorted keys). A query with `ORDER BY` keeps the
   database's order, because there the order is the answer (nearest first, path order).
3. **Other lists keep their order.** A list built from a path (`[n IN nodes(p) | n.tag]`) or a `collect` is not
   sorted: its order may carry meaning, and the verification found no differing case of that kind.

Then the Cypher tier is re-run on both dev corpora (`CYPL2-{D100,D1000}`, same Luna pin, concurrency 1 so the
INF-T1 clock gives clean local compute), and the paraphrase set (`CYPL2-PARA-D100`); the cascade report is re-run
with them. The old `CYPL-*` runs stay as the record of the unfixed tier.

## Alternatives

- **Leave it, state it as a limitation.** Keeps the measured system unchanged, but leaves a reproducibility hole in
  the arm the thesis recommends.
- **Sort every list.** Simpler, but destroys path order, which some answers need.
- **Ask the model to always write `ORDER BY`.** A prompt change with no guarantee; the model may still omit it.
- **Load into a fresh database every time.** Might make the layout repeatable, but was not shown to (row order
  changed between reloads) and would not hold on a store that is updated in place.

## Consequences

- A truncated result (`row_cap` reached) without `ORDER BY` is still a store-dependent subset; sorting fixes only the
  order of what came back. The rows-cut case is reported as such in the context already.
- The answer prompt of the Cypher tier changes for roughly a tenth of the questions, so the re-run is a new arm,
  not a replay; its cost is about the old one ($0.00039–0.00040 per question, about $0.07 per corpus).
- Thesis: the finding (store-layout-dependent answers in text-to-Cypher) is reported together with the fix.
