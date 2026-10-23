---
adr: 0004
title: Build the multi-page benchmark by inversion, not by annotation
status: accepted
date: 2026-08-23
supersedes: none
---

# ADR-0004 — Build the multi-page benchmark by inversion

## Context

ADR-0001 scopes the work on multi-page scale. Nothing exists to measure it on.

**PID2Graph does not solve this.** It is 500 *independent single-page* diagrams with per-page GraphML ground truth. It carries `connector` nodes and `border-node` labels, but border-nodes exist for stitching **patches within one page** during training — there is no cross-page or off-page-connector ground truth anywhere in the dataset. PID2Graph validates a digitization front-end; it cannot validate scale.

Real scanned factory documents are expected from the professor in roughly one to two weeks, but work cannot be blocked on them, and even when they arrive they will have **no ground truth** — which is precisely why a synthetic benchmark is still needed alongside them.

## Options considered

**A. Hand-annotate cross-page links on real multi-sheet drawings.** Highest realism, unusable timeline. Annotating off-page connectors across a few hundred sheets is months of expert work, and we do not have the drawings yet.

**B. Inversion — generate, then cut.** Build (or take) a large plant graph, **split it across N pages**, inserting an off-page connector pair at every cut edge, then render each page. The cross-page ground truth is known **by construction**, because we performed the cut. Page count, cut density and cross-reference depth become controllable variables. Information can be deliberately deleted to create known-unanswerable questions.

**C. Concatenate unrelated PID2Graph pages.** Trivial to build, but the pages have no genuine cross-references, so retrieval never has to resolve anything. It measures index size, not the actual problem.

## Decision

**Option B.** Construct the multi-page benchmark by inversion, using pyDEXPI's synthetic P&ID generation as the source of plant graphs.

Use PID2Graph in parallel for its actual purpose: measuring how **digitization error propagates** into retrieval accuracy (inject corruption at the rates Stürmer reports — edge mAP ~75% on real plans — and observe the degradation curve).

## Rationale

Inversion is the only option that yields exact cross-page ground truth on this timeline, and it makes scale a **dial** rather than a fixed property of a corpus — which is what a claim about crossover points requires. A benchmark whose difficulty can be swept is worth more here than a small realistic one.

It is also a publishable artifact in its own right: no public multi-sheet P&ID benchmark exists.

## Consequences

**Enables** — controlled sweeps over page count, cut density and missing information; exact scoring of cross-sheet entity resolution; the second contribution named in `00-index.md`.

**Costs** — synthetic data invites the "not realistic" objection. Mitigate by (a) validating against the professor's real documents in Phase 5 even without ground truth, (b) checking whether PID2Graph's OPEN100 subset (12 real reactor sheets from open-100.com) forms a coherent plant with genuine cross-references — if so it becomes a small real validation set.

**Open** — the cutting strategy must mimic how engineers actually partition drawings (by process unit, not arbitrarily), or the benchmark tests a distribution nobody has. Needs a design note before implementation.

---

## Outcome log

*Appended after acceptance. The decision above is unchanged; this records how its mitigations turned out.*

**2026-08-25 — mitigation (b) SUCCEEDED. An earlier version of this entry said the opposite; it was wrong and unverified.**

Direct inspection of the downloaded files shows all 12 OPEN100 sheets are **PROJECT: OPEN 100** — one nuclear plant (Energy Impact Center), same author, same date, revision A. Four systems span two sheets each (PID 100, 120, 170, 210).

The sheets carry **real off-page connectors that name their partner sheet and grid cell** (`PID 120-1 (D-1) RHRS`), plus line numbers (`SIZE-RCS-100007-SPEC-HC-X`). Several references resolve inside the 12 (PID 100-2, 110-1, 120-1, 150-1, 170-1, 180-1); three dangle outside it (PID 190, 240, 290).

**But the GraphML annotations capture none of it** — nodes carry only `label` + bounding box, edges only `solid`, and there is no text or tag anywhere. The 96 `inlet/outlet` nodes are the connector symbols with their labels stripped.

**Consequences for this decision — the decision itself stands:**

1. **Option B is still correct as the primary path.** 12 sheets cannot sweep scale from 10 to 1000; only a generator can. The claim needs a curve, not a point.
2. **But a real validation set is now achievable**, which this ADR assumed it was not. Recovering ~96 connector labels by OCR + manual check is days of work and yields a real multi-sheet P&ID set with cross-sheet ground truth — which does not exist publicly today.
3. **The realism problem is largely solved.** The generator's cutting strategy can now be *calibrated against real drawings*: measured cut density, connector counts per sheet (2–12 observed), sheet sizes (181–675 nodes), and the partition-by-system convention visible in the title blocks. Previously this could only be argued from convention.
4. **Free abstention cases.** The dangling PID 190/240/290 references are naturally occurring incomplete information, better evidence than deleting data ourselves.

Follow-up: a separate ADR should decide whether to invest the annotation effort. Recommendation is yes — it converts the weakest point of the thesis (synthetic-only evidence) into a two-source design.

**2026-09-13 — source of plant graphs refined (ADR-0007, accepted). The inversion decision stands.** The plant
graphs this ADR cuts are no longer taken from pyDEXPI's `SyntheticPIDGenerator`. They are DEXPI models built
with pyDEXPI classes and toolkits by our own seeded builder (`40-design/plant-generator.md` revision 2, H1).
The sampler cannot reproduce ids from a seed — every sampled pattern is deep-copied and gets fresh uuids
(measured by the architect's prototype) — and its connectors cannot express control loops.
