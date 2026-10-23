---
adr: 0030
title: Build Hierarchical with two routing modes and two over-budget modes, and pick the default by a pre-registered free measurement on dev corpora
status: accepted
date: 2026-10-02
supersedes: none — amends qa-system.md §7 "Hierarchical" steps 3–4 and its parameter row (design-note text, not an ADR)
design: 40-design/hierarchical-and-jev.md §3
---

# ADR-0030 — How Hierarchical routes between anchors, and what it drops when the route is too long

## Context

`qa-system.md` §7 routes Hierarchical by the shortest path in the **undirected sheet-adjacency graph** built from
the resolver's `continues_as` pairs, and, over budget, **drops the outermost hop ring**. The user (2026-10-02)
wants both choices built as parameters and compared, not chosen up front. The worry: two anchors on sheets far
apart (≈30 sheets between them) must get the whole connecting chain, never a radius around each anchor.

An architect probe (2026-10-02, `hierarchical-and-jev.md` §2) on the H100 headline corpus (seed 0, FLOW_PATH
candidates at question seed 1, anchors assumed found, ring 0) found three things the design did not foresee:

1. **The `continues_as`-only sheet graph is disconnected.** At duplication 0.25 (ADR-0028), a duplicated item
   replaces a cut, so some sheets are joined only by an identity link: 15 components at H100 and 117 at H1000
   (1 at both with identity links added; 23 and 207 sheet pairs joined only by identity). The §7 route then
   finds **no path** for 13 % (H100) / 9.6 % (H1000) of k = 1 questions, and 87.5 % / 52.3 % at k = 9–16.
2. **`k` counts crossings, not distinct sheets.** A flow path can go back and forth between sheets. The shortest
   *sheet* path skips sheets that path visits: even with identity links, the undirected route covered a valid
   answer path for 0.000 (H100, n = 24) / 0.591 (H1000, n = 44) of k = 9–16 questions, and 0 of 3 at k = 17–32
   (H1000).
3. **The flow-directed route covered a valid answer path for every sampled question in every bin at both sizes**
   (relaxed hit 1.000, 3,000 sampled per corpus), with a median of 10 sheets at k = 9–16 and 18 at k = 17–32.

Probe limits: FLOW_PATH only, anchors assumed found, no model call (design note §2).

## Options considered

**A. Keep §7 as written** (undirected `continues_as` route, ring drop). No new code. Shown broken on the
headline corpora (point 1), so it is not a real candidate as written. Its corrected form, with identity links in
the sheet graph, is option B's route (a).

**B. Two routing modes and two over-budget modes as parameters; a pre-registered free metric on dev corpora
picks the default; the full 2×2 is reported on every corpus as a free ablation.**
- `route = "sheet_graph"` (a): the undirected sheet graph, **with identity links added**.
- `route = "flow_path"` (b): a weighted shortest **directed** item path over the occurrence graph (`send_to`
  forward, `continues_as` forward, `same_tagged_item_as` both ways; a cut crossing costs 1, as one plant edge),
  first anchor → other anchor, then the reverse; if neither exists, fall back to (a) and record it.
- `budget = "drop_rings"` (a): drop the hop rings outermost first, then unit-only sheets; never route or anchor
  sheets.
- `budget = "through_line"` (b): as (a), then serialize each intermediate route sheet as its through-line only
  (entry stub → items on the route → exit stub); anchor sheets stay whole.
Cost: one more strategy module (`qa/routing.py`) and two harness metrics. All selection metrics are computed
without any LLM call.

**C. Pick (b)/(b) now on the probe evidence.** Cheapest to build. But the probe is one corpus, one seed, and
anchors assumed perfect; and the user asked for a measured choice.

**D. Run the 2×2 with real model calls on dev and choose by accuracy.** Measures the end goal directly, but costs
4 × Hierarchical's calls on dev, and accuracy at dev size mixes routing with model noise. Kept as a **paid
should-item ablation at H1000**, never as the selector.

## Decision

**B.**
1. Both modes are parameters of one `Hierarchical` strategy; the run config records them
   (`RunConfig.strategies["hierarchical"]`).
2. **Selection rule, fixed before the measurement:** on the dev corpus **D1000** (seed 1, headline preset, new),
   - route: the mode with the higher **strict routing recall** over answerable questions, pooled over powered
     bins; a difference under 0.01 → `sheet_graph` (the simpler one);
   - budget: at the `max_context_chars` derived from the pilot's wall, the mode with the higher **evidence-node
     recall after budget**; a difference under 0.01 → `drop_rings`.
3. The chosen pair is "Hierarchical" in the headline table and claim C4. The other three combinations are
   reported beside it on every corpus with the free metrics (routing recall strict and relaxed, evidence-node
   recall, context characters, over-budget rate), labelled ablation.
4. `max_sheets` is removed from §7's parameter list: the character budget is the binding limit, and a second cap
   would be a second dial tuned on dev.

## Rationale

- C4 (the hierarchy survives past the wall) is the design claim. A route that misses the evidence makes
  Hierarchical lose for a reason that has nothing to do with scale; routing recall separates the two.
- ADR-0029 opened the far bins on purpose (H1000 has candidates up to k = 17–32, AVAIL-01). That is where the two
  routes differ (probe), so the choice cannot be made on D100, whose reach stops at k = 5–8 (AVAIL-01, H100). Hence
  a D1000 dev corpus: it is free to build (the H1000 question build took 75.5 s, AVAIL-01).
- Free metrics make the comparison deterministic and re-runnable by the professor without API access.

## Consequences

- Easy: the user's two-variant comparison is a table of free numbers on four corpora, plus one paid ablation.
- `qa-system.md` §17 gains two Hierarchical metrics (relaxed routing hit, evidence-node recall); §7's step 3 and
  step 4 text is replaced by the design note §3.
- The flow route's single-anchor behaviour is unchanged (hop ring), so `UPSTREAM_ISOLATION` reach still depends
  on `sheet_hops`. Measured per family; if its routing recall is the weak spot, that is a new decision.
- **Revisit if** D1000 and H1000 disagree on the winner (report both, keep the dev choice); or the paid ablation
  shows the free selector picked a mode that loses on accuracy with a CI excluding 0.

**Accepted 2026-10-02 (user, in chat).** As written. The user: "try every combination" — the full 2×2 (route × budget) is built and compared; model calls are allowed (paid steps still logged one by one).

**Outcome log 2026-10-02 (ROUTE-01):** route = **`flow_path`** by the rule (D1000 strict recall over powered bins 0.732 / 0.802 / 0.813 vs `sheet_graph` 0.696 / 0.770 / 0.789 at 100k / 200k / 400k). D1000 and H1000 agree, so no revisit. Budget mode pending the pilot's wall.
