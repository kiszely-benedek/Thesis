---
adr: 0041
title: Give every model the same small P&ID domain primer, written by a fresh researcher session from cited rules only, on by design, with "off" measured as a pre-registered ablation and the text frozen at F1
status: accepted
date: 2026-10-03
supersedes: none — extends ADR-0035 (one more frozen prompt file, one more pre-registered claim) and ADR-0013 point 6 (the shared final step gains one fixed block)
design: 40-design/plant-graph-first-and-effort-routing.md Part C
---

# ADR-0041 — A P&ID engineer's primer, fair by construction

## Context

The user (2026-10-03) proposes a small, fixed "P&ID engineer" primer for every model, like a skill file: check valves
cannot be closed, operated valves, signal lines, off-page connectors. PAID-04 shows a shared failure this would touch:
UPSTREAM_ISOLATION P-3-1 — GLM and Sonnet both named check valve CHV-3-1; the reference walks through check valves
because only globe and ball valves are operated (`families_isolation.py`, `graph/schema.py` `OPERATED_VALVE_CLASSES`).

Two risks make this non-obvious:
- **Fitting.** A primer written from benchmark failures is a patch to the test. The topic list above already comes
  from dev-family failures on H100 (PAID-01…04).
- **The seal.** The architect role wrote the sealed held-out families (ADR-0035 threat). A primer written by that role
  could encode them.

Source status in the repo: off-page continuation (ISO 10628 5.3.3.2, S1), signal lines distinct from pipes (C7),
control-valve stations with block valves and a bypass (L9), instrument tags (L17), lockout–tagout as a P&ID use (TOG
1.1) are **verified** in `10-literature/pid-structural-rules.md`. "A check valve stops reverse flow" is marked
**not verified** there (`docs/Notes/pid-szerkezeti-szabalyok.md` line 103). So the user's first example still needs a
source.

## Options considered

**A. No primer.** Nothing to build or defend. Leaves domain errors such as the check-valve one to the model.

**B. The architect writes it from the PAID failures.** Fast and targeted; it is a fit to the benchmark, and written by
the role that wrote the seal.

**C. A fresh researcher session writes it from cited sources only; identical text in every plant-reasoning prompt; on
by design; off measured as an ablation; frozen at F1.**

**D. As C, but choose on/off by paid dev runs.** A data-driven choice, but it costs dev runs and turns a design element
into a tuned parameter.

**E. A primer per strategy** (e.g. Cypher hints for CypherRAG). Mixes domain knowledge with interface help; unfair by
construction.

## Decision

**C.**
1. **Content rules.** Only general statements a P&ID engineer applies to any drawing, each traceable to a verbatim
   quote in a cited source. No question template wording, no family name, no tag, no answer-format hint, no count, no
   statement about this benchmark's generator. At most 1,200 characters. A line without a verified source is dropped,
   not softened.
2. **Who writes it.** A fresh `researcher` session that receives only: the source list
   (`pid-structural-rules.md` and anything it newly verifies), the schema vocabulary (node classes and relation names
   from `graph/schema.py`), and the user's topic list, disclosed as dev-influenced. It never receives question
   templates, PAID results, design notes or the sealed file. Output: `src/plantgraph/qa/prompts/primer_pid_v1.txt` and
   `docs/private/10-literature/primer-sources.md` (one row per line: quote, source, location). The architect checks
   only the content rules; the user approves the text.
3. **Placement.** A `<<PRIMER>>` block, same text, same position (before the context or schema), in every prompt that
   reasons about plant content: `final_answer.txt`, `cypher_query.txt`, and the agent system prompts when they are
   built. Not in `unit_router.txt` or the need-classifier prompts (they pick a scope or a shape; their accuracy is
   measured as built). With the primer off, the block and its blank line vanish, so prompts equal today's byte for
   byte (golden test; PAID-01…04 stay replayable).
4. **Configuration.** `RunConfig.primer: str | None` (e.g. `"pid-v1"`); `prompt_hashes` includes the primer file;
   CLI `--primer pid-v1|none`. `qa/prompts/` is already in F1's hash list.
5. **On by design.** The primer is part of the system, not tuned. Every EXP-0006 primary run uses it. EXP-0001 (the
   ChatP&ID reproduction on EX01) runs with it **off**, for fidelity to the published setup, and says so.
6. **Pre-registered claim P1.** At H1000, `hierarchical_need_rules_plant` at the EXP-0006 pin, on the first-stage slice
   (5 questions per family, dev and held-out): with − without > 0, paired 95 % CI excluding 0. Reported per family and
   per split. Wording if not: "a cited P&ID primer does not measurably help". A gain on dev families with none on
   held-out ones is reported as a fitting signal.

## Rationale

- It answers the user's idea and the check-valve failure with domain knowledge rather than a benchmark patch, and the
  provenance protocol makes that auditable: every line has a quote, and the author saw neither the failures in detail
  nor the seal.
- Same text for every arm keeps the strategy comparison clean: the primer moves all arms or none.
- On-by-design plus an off ablation costs one extra small run (estimate in the design note) instead of a dev
  selection loop.

## Consequences

- Cost: about 300 tokens more per prompt (estimate: 1,200 characters at 4 characters per token) — about $0.00005 per
  question on glm-5.3-flash and $0.0006 on Claude Sonnet 5.5 at the 2026-10-02 listing prices (estimates).
- The check-valve rule ships only if the researcher finds a citable source; otherwise the primer simply lacks it, and
  P-3-1-type failures remain a reported limitation.
- ADR-0040 must land first: the tag-letter rule (L17) would otherwise make the ambiguous loop question look worse.
- **Revisit if** the researcher cannot source at least three of the topic rules (then the primer is too thin to test,
  report it as not built); or P1's per-split result shows a dev-only gain (then the thesis says so and the primer is
  kept but not claimed).

**Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet")** Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet") with the main session's recommendations. A fresh researcher writes the primer from cited sources only; on by default; an off run measures it; the check-valve rule only with a citable source.

**Outcome log 2026-10-03:** primer v1 (`40-design/pid-primer-v1.md`, 1,195 characters, every line sourced) **approved by the user in chat**. Disclosed: the author had read this ADR's Context (which names the P-3-1 failure); the check-valve line states the sourced general rule (self-acting; unsuitable for isolation without a screw-down stop), not "cannot be closed". Watch item: line 4 (gate/ball valves start or stop flow) vs the generator's `OPERATED_VALVE_CLASSES`.
