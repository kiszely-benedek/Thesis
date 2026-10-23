---
adr: 0012
title: The RDF comparison arm under the deadline — keep, kill, or write it up without building it
status: proposed
date: 2026-09-25
supersedes: ADR-0002 in part (the "built alongside" paragraph and the kill criterion), if accepted with K2 or K3
---

# ADR-0012 — The RDF arm under the deadline

**This ADR recommends reversing a leaning the user expressed on 2026-09-20.** The call is the user's.

## Context

- **ADR-0002** (accepted 2026-09-06, revised option C) keeps Neo4j LPG as the primary store. It also
  builds an RDF/SPARQL store alongside, bounded to four things:
  1. a Pydantic-to-triples loader;
  2. a vocabulary mapping;
  3. a SPARQL retrieval strategy behind the shared retrieval interface;
  4. the shared benchmark harness.

  Its **kill criterion** reads: if the RDF loader and the SPARQL strategy are not running on the
  multi-page benchmark by the end of phase 3, the RDF arm is cut. **"The phase-3 crossover measurement is
  never delayed for B."**
- **None of the RDF arm exists.** Its design note has not been written. The index lists it under
  "Later / blocked". Store choice (n10s or a separate triplestore), the IRI scheme and the vocabulary
  mapping are all open. The vocabulary plan (`ontology-landscape.md` §5, cited in ADR-0002) needs three
  things:
  - a namespace generated from **514 pyDEXPI classes**;
  - alignment to the PCA RDL, which is auth-walled (HTTP 401) and must be vendored;
  - alignment to QUDT.
- **The professor, relayed 2026-09-20:** *"maybe it's overkill to use ontology for connecting sheets or
  putting them into hierarchy."* The index reads this as not touching the project. Sheet hierarchy and
  cross-sheet links are already plain LPG terms in `graph/schema.py`:
  - `NodeClass.DRAWING_SET`, `NodeClass.SHEET`;
  - `Relation.HAS_SHEET`, `Relation.IS_DRAWN_ON`, `Relation.CONTINUES_AS`,
    `Relation.SAME_TAGGED_ITEM_AS`;
  - `ConnectorPair` and `IdentityGroup` in `benchmark/models.py`.

  The index leaves one item open: **"Revisit if … the professor's remark turns out to have meant the RDF
  arm too."**
- **The user, 2026-09-20:** *"I think we can keep it."* The index records this as a **provisional keep,
  given before reading** `docs/Notes/sajat-ontologia-leltar.md`, and says that the end-of-phase-3 kill
  criterion, "not a new decision", is what will settle it.
- **New since then (2026-09-25):**
  - the Q&A system is entirely unbuilt;
  - the framing puts the pipeline first (ADR-0011, Context).

  Under those facts the kill criterion protects the **crossover date**, but not the **effort** spent on
  the RDF arm before the criterion fires.

## Options considered

**K1. Keep the status quo: the RDF arm is bounded, with the end-of-phase-3 kill criterion.**

- **Case.** It honours the professor's original reading-list steer (RDF, SPARQL, ontologies, schema.org)
  and the user's leaning. It also keeps a comparison that ADR-0002 notes no paper in the reading list has
  done.
- **Cost.** A design note plus four build items plus a second stack to learn, which means Hungarian
  teaching notes per concept (ADR-0002, Costs). All of it lands before the end of phase 3, and in series
  with the Q&A work, because coders run one at a time (ADR-0006).
- **Cost to the experiment.** The store becomes a **second axis** crossed with retrieval strategy and
  scale. The thesis claim varies only scale.
- **Variant K1b: an earlier checkpoint** (for example, the end of phase 2). This limits the sunk cost but
  still spends the design-note time. It is noted here and not pursued separately.

**K2. Invoke the kill now, driven by the deadline. LPG only.**

- **Case.** Zero further cost. All effort goes to the unbuilt half.
- **Cost.** The professor's original steer gets one sentence in the thesis. ADR-0002's "fallback if LPG
  hits a wall" disappears. No evidence yet shows that LPG hits a wall, but none shows that it does not,
  because Neo4j has not been loaded at scale.

**K3. No implementation, and a written comparison section in the thesis.**

- **Sources.** The section is built from existing material:
  - `docs/Notes/lpg-vs-rdf.md` (2026-09-06);
  - `10-literature/ontology-landscape.md` §5;
  - the evidence already in ADR-0002.
- **ADR-0002 evidence reused:**
  - GQL (ISO/IEC 39075:2024) removes "standardized vs proprietary" as a differentiator;
  - inference and SHACL are the real differentiator;
  - reification multiplies triple count on attribute-heavy data;
  - n10s is a Neo4j Labs project.
- **Content.** The section says what an RDF arm would test and why it was not built. It maps each LPG
  schema term to its would-be RDF counterpart, for example `CONTINUES_AS` → `continuesAs` and
  `SAME_TAGGED_ITEM_AS` → `sameTaggedItemAs` / `owl:sameAs`.
- **Cost.** Writing time for one section. It needs no code and no new stack. No estimate in days is given,
  because none has been measured.
- **Buys.** The professor's question gets a considered written answer, and the design is ready for future
  work.

## Decision

**Recommended: K3.** If accepted, it supersedes ADR-0002 in part:

- **LPG-primary stands.**
- The "RDF/SPARQL store built alongside" paragraph and the kill criterion are replaced by one written
  thesis section.

## Rationale

- **The claim varies scale, not store.** An RDF arm adds a dimension the claim does not need. Under a
  deadline with the Q&A half unbuilt, every coder-week spent on it is a week off the critical path
  (ADR-0011).
- **The kill criterion was designed for a different risk.** It stops the RDF arm from delaying the
  crossover. It does not stop weeks being spent before the criterion fires, and under this deadline that
  sunk cost is the risk.
- **The professor's 2026-09-20 remark points the same way.** It may or may not cover the RDF arm, and
  that is why it is an open question below rather than a premise.
- **K3 over K2.** K3 keeps the professor's steer answered at the cost of writing, not building. ADR-0002's
  own revisit trigger, where entity resolution needs real inference, stays live as a future-work pointer.
- **Against the recommendation.** The user said "keep it" on 2026-09-20, and the index calls that keep
  provisional. Choosing K1 is legitimate if the professor wants the comparison built.

## Consequences

**Enables:**

- no second stack;
- no vocabulary mapping or PCA RDL vendoring;
- no RDF-side teaching notes;
- the RDF design note is dropped from the backlog;
- one thesis section that answers "why not RDF" with sourced reasons.

**Forecloses (this phase):**

- any measured LPG-vs-RDF claim, including RDF's triple-count footprint, which ADR-0002 said must be
  measured and not assumed. The section must therefore state the footprint as **unmeasured**.

**Other ADRs.** If this ADR is accepted, append an outcome-log entry to ADR-0002 pointing here. The body of
an accepted ADR is not edited.

**Open question for the professor.** Did *"overkill"* cover the RDF comparison arm, or only an ontology
for sheet linking and hierarchy? If the professor wants the comparison built, choose K1 and this ADR is
withdrawn.

**Revisit if:**

- the professor asks for the RDF comparison;
- cross-sheet entity resolution needs real inference, such as transitive tag identity or subclass
  reasoning (ADR-0002's own trigger);
- phases 2 to 4 finish with time to spare before a confirmed deadline.
