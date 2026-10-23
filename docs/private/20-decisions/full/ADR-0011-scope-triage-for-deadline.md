---
adr: 0011
title: Triage the open scope items against the deadline
status: accepted
date: 2026-09-25
accepted: 2026-09-26
supersedes: none
---

# ADR-0011 — Scope triage for the deadline

## Context

- **Deadline: exact date not yet known** (user, 2026-09-25). Plan against the near end until the date is known.
- **Measured pace.** The progress log starts in week 34 (17–23 August). Phase 1's generator, splitter
  and schema reached their scale smoke on 2026-09-20 (SMOKE-01 to SMOKE-03, `30-experiments/_results.md`).
  So phases 0 and 1 took **about five calendar weeks** (17 August to 20 September, 34 days). This is an
  estimate of elapsed time from two dates. It says nothing about effort per week.
- **The larger half is unbuilt.** The index's title table records the Q&A system as **"Not built at all.
  No retrieval, no question answering exists yet"** (`00-index.md`). `_results.md` records **"no thesis
  experiment yet — EXP-0001–0005 all still blocked"**. Phases 2 to 4 and the write-up (phase 6) have not
  started.
- **Framing** (user, 2026-09-20): this is an engineering thesis, the pipeline leads, and the crossover is
  supporting evidence. **Title reading** (professor, relayed 2026-09-25): a DEXPI/Proteus file counts as a
  drawing, and no digitization front end is required.
- **Novelty budget** (architect brief): retrieval at scale and cross-sheet entity resolution. Every item
  below that is not on that line competes for time with the unbuilt Q&A half.

Nine items are open. Item 5 is split in two, so the table has ten rows. Each row has the same three
options:

- **Keep** — do the item as currently planned.
- **Minimal** — the smallest version that keeps its thesis-relevant part.
- **Cut** — move the item to the future-work section of the write-up. It gets one paragraph and no code.

## Decision table (the user ticks one box per row)

| # | Item | Keep | Minimal | Cut | Recommended |
|---|---|:-:|:-:|:-:|---|
| 1 | Phase 1 step 8, utilities | [ ] | [ ] | [ ] | **Cut** |
| 2 | EXP-0003, digitization edge-error sweep | [ ] | [ ] | [ ] | **Minimal**: label noise inside EXP-0004; EXP-0003 itself is cut |
| 3 | EXP-0005, abstention | [ ] | [ ] | [ ] | **Minimal**: an unanswerable template family inside the ADR-0013 question set |
| 4 | Several plants per corpus | [ ] | [ ] | [ ] | **Cut** |
| 5a | Rendering to PDF | [ ] | [ ] | [ ] | **Cut** |
| 5b | Full Proteus exporter | [ ] | [ ] | [ ] | **Cut** if ADR-0009 is accepted as I4; **Minimal** if I2 |
| 6 | "Read real PDFs" backlog | [ ] | [ ] | [ ] | **Cut** |
| 7 | OPEN100 grid-cell interpolation | [ ] | [ ] | [ ] | **Minimal**: human verification flags instead of interpolation |
| 8 | `rejoin.py` dict fix and `--rejoin` flag | [ ] | [ ] | [ ] | **Cut** (defer) |
| 9 | `/paper-intake` for PIDQA | [ ] | [ ] | [ ] | **Keep** |

**Before acceptance.** Every row is ticked before this ADR is set to `accepted`, because accepted ADRs are
not edited. A row that is still unticked means the item keeps its current status. It does not mean the
item is cut.

## Options and recommendation per item

### 1. Utilities (phase 1, step 8)

- **Context.** ADR-0007 already defers utilities to "a later generator step". The index lists two
  obstacles:
  - Splitter finding (1): a utility crossing is **one-to-many**, and **`ConnectorPair` cannot express it**.
  - HNF-64103 §3.2.5.2: "Main utility headers are not shown on the unit P&ID".
- **Keep.** A design addendum, a schema change (a one-to-many connector), and generator and splitter
  changes. That is three components, and the design does not exist yet.
- **Minimal.** None that is honest. Modelling utilities as one-to-one pairs contradicts the codified rule
  above.
- **Cut.** The benchmark states "process lines only, no utility systems" as a limitation.
- **Recommend Cut.** Nothing in the scale claim needs utilities. SMOKE-02 already reaches 4,015 sheets
  without them.
- **Consequence.** `utility_aware` stays what finding (1) says it is: a degree-based hub heuristic. EXP-0002
  either describes it that way or drops it from the list of split strategies.

### 2. EXP-0003: digitization edge-error sweep

- **Context.** EXP-0003 asks "How does retrieval accuracy degrade as digitization edge error rises
  0% → 25%?" (`_results.md`). It is blocked on a corruption injector. Under the DEXPI reading of the title
  there is **no digitization stage in the pipeline**, so the sweep would model an error source that the
  system does not have. ADR-0007 already made the direction-flip sweep optional.
- **Keep.** Build the injector and run the sweep as specified.
- **Minimal.** A **label-noise variant inside EXP-0004**:
  - Perturb the text the resolver reads (off-page connector labels and equipment tags) at a few noise
    levels.
  - Measure resolver precision and recall at each level.
  - This tests the robustness of the thesis's centrepiece component, not of a digitizer that is absent.
  - Noise levels are set in the EXP-0004 design note, not here.
- **Cut.** A future-work paragraph, linked to item 6.
- **Recommend Minimal.** EXP-0003 leaves the main line. The label-noise sub-sweep runs only after
  EXP-0004 has its clean-label result.

### 3. EXP-0005: abstention

- **Context.** ChatP&ID has **"No abstention/unanswerable category"** (`10-literature/2603.22528.md`, Gaps).
  ADR-0007 keeps EXP-0005 on "questions made unanswerable by construction" and drops the frequency claim.
- **Keep.** A separate experiment on a benchmark variant with deleted information (`_results.md`, Planned).
- **Minimal.** Add one or two unanswerable template families to the ADR-0013 question set. An example is a
  question about a tag or attribute that is absent from the ground-truth plant, where the reference
  answer is "not present". Abstention rate is then **one more column** in the per-strategy, per-scale
  results. No separate benchmark is needed.
- **Cut.** A future-work paragraph.
- **Recommend Minimal.** It fills a gap in the closest prior art almost for free once E2 or E3 from
  ADR-0013 exists. If ADR-0013 is not accepted, this row falls back to Cut.

### 4. Several plants per corpus

- **Context.** ADR-0007 decision 4 says "one plant per corpus now, several in the next phase". The
  professor said on 2026-09-12 that "one plant or several" is acceptable.
- **Keep.** The generator emits several plants, with separate namespaces and handling for tag collisions.
- **Minimal.** Concatenate independent plants as disconnected components with prefixed tags. That tests
  only plant disambiguation, and entity resolution becomes trivial.
- **Cut.** State "one plant region per corpus" as the scope.
- **Recommend Cut.** The scale dial already reaches thousands of sheets from one plant (SMOKE-02). Several
  plants add a different question, plant disambiguation, which is not the claim.

### 5a. Rendering to PDF

- **Context.** ADR-0007 lists rendering as a later phase. The professor said on 2026-09-25 that a DEXPI
  file counts as a drawing.
- **Keep / Minimal / Cut.** Build a renderer, render a sample for figures only, or cut.
- **Recommend Cut.** Nothing in the pipeline consumes pixels. Thesis figures can be drawn from the graph.

### 5b. Full Proteus exporter

- **Context.**
  - pyDEXPI 1.2.0's Proteus export is **equipment-only** (ADR-0007, Costs).
  - User leaning, 2026-09-20: *"We will need this I think."*
  - The index notes that the real alternative is to write the exporter ourselves or to contribute it
    upstream under AGPL-3.0.
  - EXP-0001 needs only Proteus **import**, and pyDEXPI already provides it: ADR-0007 notes that the
    same adapter serves EXP-0001 on `DEXPIEX01.xml`.
- **Keep.** A full exporter for piping, instrumentation and equipment.
- **Minimal.** Export only the classes the generator emits: equipment, piping, off-page connectors, and
  the instrumentation that control loops need.
- **Cut.** Persist generated plants as pyDEXPI JSON, as ADR-0007 already does.
- **Recommend: this depends on ADR-0009 (input contract).** ADR-0009 recommends **I4**: the `SheetGraph`
  is the contract, fed by the splitter and by a Proteus **importer**; per-sheet Proteus XML (I2) is only the
  upgrade path. *(Cross-reference pinned by the main session, 2026-09-25.)*
  - If ADR-0009 is accepted as I4, **Cut**.
  - If the user chooses I2 instead, so that "from drawings" holds literally for the synthetic corpus too,
    **Minimal**, because the full exporter is more than the benchmark needs.
- **Reverses a user leaning** in the Cut branch.

### 6. "Read real PDFs" backlog

- **Context.** The user made this conditional on 2026-09-20: "after a discovery", explicitly after the
  scaling result. A `researcher` sweep must come first. The professor said on 2026-09-25 that no
  digitization front end is required. PID2Graph already covers pixels-to-graph at **75.46 % edge mAP**
  (`00-index.md`).
- **Keep.** Researcher sweep, then design, then build.
- **Minimal.** The researcher sweep only, to feed a future-work paragraph. It costs agent time plus the
  user's reading time.
- **Cut.** A future-work paragraph that cites PID2Graph from existing notes.
- **Recommend Cut.** The professor's answer removes the reason this item existed.

### 7. OPEN100 grid-cell interpolation

- **Context.** This is open question 2 in `40-design/open100-annotation.md`. A handful of pairs were
  confirmed by target and line only, not by an independently computed grid position (`00-index.md`).
  OPEN100's **23 pairs** are the EXP-0004 test set (ADR-0007, decision 3). The manifest reads: 23 pairs,
  42 dangling, 8 unresolved, 96/96.
- **Keep.** Implement interpolation and recompute the pairs.
- **Minimal.** The user sets the `verified_by_human` flags on the CSV (already a Next-action item) by
  checking visually the pairs that lack grid confirmation. EXP-0004 then reports how many pairs rest on
  which kind of evidence.
- **Cut.** Report the pairs as they are and state the limitation.
- **Recommend Minimal.** A test set of 23 pairs is small enough that each pair's evidence matters. A
  visual check is bounded at 23 pairs, while interpolation is new code.

### 8. `rejoin.py` dict fix and `--rejoin` flag

- **Context.** SMOKE-03 measured `rejoin` at **3.176 s at 2,900 units**. The O(pairs × sheets) scan is
  real (**×6.30 for ×2.9 size**) but takes **6 % of the pipeline** (`_results.md`).
- **Keep.** Apply the fix and add the flag.
- **Minimal.** The fix without the flag.
- **Cut.** Leave the code as it is. The scale-smoke note already records the cost.
- **Recommend Cut (defer).** It is measured not to be a hotspot, and it has no thesis value.
- **Revisit if** the thin cross-sheet resolver in the KG-construction phase reuses `rejoin.py`. The fix
  would then ride along with that work.

### 9. `/paper-intake` for PIDQA

- **Context.** The note is a **stub**: MDPI returned HTTP 403, and the note was written from the abstract
  and the GitHub README (`10-literature/make7020039-pidqa.md`). ADR-0013's E2 is **PIDQA's method**, and
  the related-work chapter must describe that method accurately.
- **Keep.** Run a full `/paper-intake` once the user has fetched the HTML through the university library.
- **Minimal.** Answer only the stub's two TODOs that ADR-0013 depends on: how the schema is put into the
  prompt, and how the templates are built.
- **Cut.** Cite PIDQA from the stub.
- **Recommend Keep.** It is one skill run, and it underpins the evaluation method. The repo rule is to use
  the skill rather than hand-roll a partial reading. The only blocker is access, which needs the user.

## Decision

Proposed: **the Recommended column**, decided row by row by the user.

## Rationale

The time left is limited. Phases 0 and 1 took about five weeks.
Everything that makes the title's second half real (retrieval, question answering, the crossover, entity
resolution, the write-up) is unbuilt. Every recommendation above keeps an item only if it does one of
three things:

- it feeds the two novelty lines (items 2 and 7 feed EXP-0004);
- it is nearly free once the evaluation harness exists (item 3);
- it protects the correctness of a published method (item 9).

Everything else becomes future work. Where the professor's 2026-09-25 answer removed an item's reason
(items 2, 5a and 6), the item leaves the main line.

## Consequences

**Critical path after triage:**

1. The single-sheet baseline, EXP-0001.
2. The thin cross-sheet resolver, placed by the phase-ordering ADR written in parallel.
3. The scale sweep, EXP-0002.
4. EXP-0004, with the optional label-noise sub-sweep.
5. The write-up.

**Future-work chapter** gains paragraphs for utilities, several plants, rendering, reading PDFs, the
digitization error sweep, and (depending on 5b) the Proteus exporter. These are one paragraph each, and
together they make up ADR-0007's "later phases".

**Reinstatement order if time frees up:**

1. Item 2's label noise, if it has not already run.
2. Item 4.
3. Item 1.
4. Item 5b.
5. Item 5a.
6. Item 6.

This order is by distance from the claim.

**Revisit if:**

- the deadline turns out to be late and phases 2 to 4 are done with weeks to spare;
- the professor asks for pixels or realism evidence, which would reopen items 5a and 6;
- the input-contract ADR settles item 5b.

## Outcome log

- **2026-09-26:** Accepted by the user 2026-09-26 **as recommended, every row**. Two clarifications from the user the same day: the "read real drawings" item is *"if we will have time"* — a stretch after the core, never before it; and equipment datasheets are **out of scope — not part of this thesis**. The deadline was since corrected to an earlier date, which makes the cuts more necessary, not less.
