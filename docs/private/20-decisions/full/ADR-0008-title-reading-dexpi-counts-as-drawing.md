---
adr: 0008
title: Read "from technical drawings" as admitting DEXPI/Proteus files; no pixels-to-graph front end
status: accepted
date: 2026-09-25
accepted: 2026-09-25
confirmation: verbal, relayed by the user; written confirmation pending (action item a)
supersedes: none
---

# ADR-0008 — A DEXPI/Proteus file counts as a "drawing"

**The decision is the professor's, relayed by the user on 2026-09-25.** It is recorded as accepted because
it is not ours to weigh. **It is not yet in writing**; getting it in writing is open item (a).

## Context

The registered title (professor, by email, 2026-09-25; `00-index.md`, "Official title"):

> *Tudásgráf-építés műszaki rajzokból és P&ID diagramokból skálázható Q&A rendszerhez*
> (Knowledge-graph construction from technical drawings and P&ID diagrams, for a scalable Q&A system.)

The index flags a **tension**: the title reads as if drawings are the input, but ADR-0001 scopes
digitization out ("beating the state of the art on single-page symbol detection" is explicitly out of scope),
and ADR-0007 decision 4 keeps it out: "reading PDFs back is a separate digitization stage; the method's
input stays per-sheet graphs". We **generate** DEXPI models; we read no drawings.

The index names the question that had to be answered before phases are planned: does "műszaki rajzokból"
require a pixels-to-graph front end, or is a DEXPI/Proteus file — the machine-readable form of a drawing —
an acceptable input? Only the professor could settle it. **Answer (relayed 2026-09-25): a DEXPI/Proteus file
counts as a drawing.**

## Options considered

**R1. DEXPI/Proteus input counts as a drawing.** The pipeline starts at a machine-readable P&ID. This is the
precedent: ChatP&ID's pipeline is DEXPI XML → pyDEXPI → Neo4j (`10-literature/2603.22528.md`, Method). Scope
stays as ADR-0001 and ADR-0007 set it.

**R2. Pixels are required → a new "digitization front end" phase.** What it would contain, and what is known
about each piece:
- **A detector.** Reuse PID2Graph's Relationformer (`10-literature/2411.13929.md`). **Whether trained weights
  are published is unverified.** If not, training on PID2Graph is added work.
- **Text.** PID2Graph's GraphML carries **no text or tags anywhere** (ADR-0004 outcome log, 2026-08-25;
  ADR-0007 History). A detector trained on it yields untagged symbols, so tag- and label-based resolution and
  every tag-bearing question would need an OCR stage on top.
- **Real images to run on.** Only **OPEN100's 12 sheets** are real (ADR-0004 outcome log; ADR-0007 Context:
  750 of PID2Graph's 762 sheets have no off-page connector and are synthetic).
- **Synthetic plants have no images.** They would first need rendering — the rendering phase ADR-0007
  defers — and, if rendering goes through existing DEXPI tooling, a **full Proteus exporter**, because pyDEXPI
  1.2.0 exports equipment only (ADR-0007, Costs).
- **Error that propagates.** PID2Graph reports **75.46 % edge mAP on OPEN100 (real)**
  (`10-literature/2411.13929.md` line 29). That error would enter entity resolution and QA as a confound on
  the scale measurement.
- **Scope collision.** It re-enters the territory ADR-0001 classed as **taken** by four groups.

**R3. Pixels as an optional demo only.** Run a front end on OPEN100's 12 sheets as an appendix, off the
critical path. Cheap in argument, but not in time: detector availability, OCR and schema mapping are the same
work as R2, and without scoring against OPEN100's annotation it measures nothing.

## Decision

**R1.** A DEXPI/Proteus file is an acceptable "drawing" input. No pixels-to-graph front end is built in this
thesis.

### Branch point (so R2 stays re-openable)

The pixels branch would attach at **the ingest stage that produces per-sheet graphs**. Today that stage's
output type is `SheetGraph` (`src/plantgraph/benchmark/sheet_graph.py`): `sheet_id`, a `networkx.DiGraph`
over the schema in `src/plantgraph/graph/schema.py`, and `connectors: list[OffPageConnector]`
(`src/plantgraph/benchmark/models.py`). ADR-0009 makes this type the system's input contract.

A pixels front end would be **one more producer of `SheetGraph`**: image → detector → graph → OCR of tags
and connector labels → schema mapping → `SheetGraph`. Resolution, graph loading, retrieval and QA downstream
of the contract would not change. OPEN100's `ConnectorObservation` (bounding box, `raw_text`, parsed
`target`, `line_number`) is already the image-side half of that producer for connectors.

The cheap proxy for "what if the input came from pixels" already exists in the plan: ADR-0004 decided to
**inject corruption at the rates Stürmer reports** and observe the degradation curve (EXP-0003, optional per
ADR-0007). Under R1 that curve is how the thesis answers the question without building the front end.

## Rationale

- **It is the professor's reading**, and the professor registered the title.
- **It keeps the novelty budget where it belongs.** ADR-0001: multi-page scale is open, single-page
  digitization is taken. R2 would spend the remaining time on the taken part.
- **It matches the published pipeline** we extend (ChatP&ID starts from DEXPI XML).
- **R2's error would confound the claim.** A 75.46 % edge mAP front end mixes digitization error into every
  scale measurement; ADR-0001 already says error propagation must be a controlled variable, which the
  injection proxy provides and a real front end does not.

## Consequences

**Enables** — the phase plan can be made (ADR-0009, ADR-0010); the index "TENSION" row can be closed, with
the wording pending the written answer.

**Costs** — the thesis must say plainly that "drawing" means a machine-readable DEXPI/Proteus P&ID, and that
scanned or raster drawings are out of scope. Under ADR-0009 the synthetic corpus itself never exists as
DEXPI files; that limitation is stated there.

**Forecloses (this thesis)** — any claim about reading raster or scanned drawings.

**Open items:**
- **(a) Get the answer in writing.** An email from the professor confirming that DEXPI/Proteus input satisfies
  "műszaki rajzokból". Until then this ADR rests on a relayed verbal answer.
- **(b) The title names two input kinds**: "műszaki rajzok **és** P&ID diagramok". Confirm whether P&IDs alone
  satisfy "technical drawings", or whether other drawing types (isometrics, general-arrangement drawings)
  are expected. If they are, that is a new scope question and a new ADR, not an edit to this one.

**Revisit if:**
- the written answer differs from the relayed one;
- an examiner asks for image input (the branch point above is where it attaches);
- open item (b) comes back as "other drawing types are expected".

## Outcome log

- **2026-09-26:** open item **(b) closed** — user: *"PID only"*. The thesis covers P&IDs; no other drawing type. Open item (a), the answer in writing, is still open. User also noted that a drawing-reading stage may be tried *"if we will have time"* — a stretch per ADR-0011, not a reopening of R2.
