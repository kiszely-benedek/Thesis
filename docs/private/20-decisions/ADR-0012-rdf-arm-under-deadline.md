---
adr: 0012
title: The RDF comparison arm — keep building it, kill it, or write it up without building
status: accepted
date: 2026-09-25
accepted: 2026-09-26
full: full/ADR-0012-rdf-arm-under-deadline.md
supersedes: ADR-0002 in part, if accepted with K2 or K3
---

# ADR-0012 — The RDF arm

**Accepted 2026-09-26 by the user: K3.**

**Question.** ADR-0002 says build an RDF/SPARQL store *alongside* Neo4j, and kill it if it is not running by the
end of the scale phase. None of it exists. Is it still worth building in the time left?

**Options**
- **K1** Keep, as ADR-0002 says. Costs a design note, four build pieces and a second technology to learn, all
  queued behind the Q&A work on the single coder.
- **K2** Kill it now. Neo4j only; nothing about RDF in the thesis beyond one sentence.
- **K3** Do not build it. Write one thesis section: what an RDF version would test, how each of our graph
  terms maps to RDF, and why it was not built. The source material already exists (`docs/Notes/lpg-vs-rdf.md`,
  ADR-0002).

**Recommendation: K3.**

**Why**
- The claim varies **scale**, not **database**. RDF adds a dimension the thesis does not need.
- The kill criterion protects the deadline only *after* the weeks have been spent.
- The professor said (2026-09-20): *"maybe it's overkill to use ontology for connecting sheets or putting them
  into hierarchy."*

**Costs.** No measured Neo4j-vs-RDF numbers; the section must call any such comparison unmeasured.


**Ask the professor.** Did "overkill" include the RDF comparison? If they want it built → K1.

## Outcome log
- **2026-09-26** User: *"we dont need it, we have the ontology in pyDEXPI which is needed … K3 is my decision."* **K3 accepted:** no RDF implementation; one written thesis section. Wording note for that section: pyDEXPI implements the DEXPI **information model** (a class hierarchy), which the thesis should call that rather than an OWL ontology (`10-literature/ontology-landscape.md`).
