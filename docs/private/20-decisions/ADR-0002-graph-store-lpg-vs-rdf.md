---
adr: 0002
title: Graph store — Neo4j LPG as primary, an RDF/SPARQL store built alongside for comparison
status: accepted
date: 2026-08-23
supersedes: none
---

# ADR-0002 — Graph store: Neo4j LPG vs RDF/SPARQL

## Context

The professor's reading list pointed explicitly at **RDF, SPARQL, ontologies and schema.org**. The papers on that same list do not use any of them: ChatP&ID and "Talking like P&IDs" both use a **Neo4j labeled property graph** with Cypher. This is a real fork, not an oversight, and it should be decided deliberately rather than by default.

## Options considered

**A. Neo4j LPG + Cypher.** Matches the prior art exactly, so baselines are directly comparable. Properties sit on nodes and edges natively, which suits P&ID attributes (tag, diameter, design pressure). Mature tooling, an MCP server, good Python drivers. No native reasoning: consistency checking must be hand-coded.

**B. RDF triplestore + SPARQL + OWL/SHACL.** Buys formal semantics and **reasoning** — validate a drawing set against a DEXPI/ISO 10628 ontology and get violations as inference, not as bespoke code. Aligns with the professor's steer and with the semantic-web literature. Costs: attribute-heavy graphs get verbose through reification, the prior art is not directly comparable, and it is a second technology stack to learn inside three months.

**C. Both — LPG for retrieval, RDF for validation.** ~~Maximum coverage, double the maintenance, and a real risk of two half-built systems.~~

*Revised 2026-08-25.* This was rejected on the assumption that "both" means two databases. It may not. **neosemantics (n10s)** is a Neo4j plugin that imports/exports RDF losslessly, imports OWL/RDFS/SKOS ontologies, and runs SHACL validation and inferencing — inside Neo4j. So option C could be one database with an RDF view, not two systems.

Counterweight: n10s is **Neo4j Labs**, not the core product, and self-hosted only (not on Aura). Labs projects are community-supported, which is a real dependency risk for work that must still run at submission. Do not treat this as free.

## Decision

**Accepted 2026-09-06, user's call: revised option C.** Neo4j LPG (option A) is the **primary
store** — the retrieval pipeline, the baselines and the crossover experiments run on it. An
**RDF/SPARQL store (option B) is built alongside**, thin and from the same corpus, so that the plant-
scale corpus can be loaded into both and the two can be compared, and so that B is a working
fallback if the LPG path hits a wall that the semantic-web path does not.

"Alongside" is bounded. The RDF path gets: a loader from the shared Pydantic model to triples, a
vocabulary mapping (DEXPI classes to an ontology, IRIs for tags), a SPARQL retrieval strategy behind
the same retrieval interface as the LPG strategies, and the same benchmark harness. It does **not**
get its own digitization, its own benchmark generator or its own chatbot. Whether B lives inside
Neo4j via n10s or in a separate triplestore is a design-note question, not decided here.

The earlier text of this section (proposed A, B as a side-study in phase 4 "if time allows") is
superseded by the paragraph above.

## Rationale

The thesis claim is about **retrieval at scale**, and comparability with ChatP&ID is the fastest route
to a credible baseline — that is why A stays primary. The professor's steer toward RDF is not a
whim, though, and the reason is directly relevant to the claim: RDF identifies every node by a
**global IRI**, so merging the graphs of ten documents into one plant region is a set union of
triples with no identifier clash, and cross-document identity becomes a declarative statement
(`owl:sameAs`) rather than a merge procedure. Whether that translates into better *retrieval* at
scale is exactly the kind of question this dissertation exists to measure rather than assume, so
having both stores loaded from one corpus turns the professor's hypothesis into an experiment
instead of a disagreement. See `docs/Notes/lpg-vs-rdf.md` for the full argument on both sides.

The risk named on 2026-08-23 — "two half-built systems" — is real and is accepted knowingly. The
mitigation is the bound above: B is a loader plus one retrieval strategy, nothing more, and it is
dropped without a second thought if it slips the timeline (see kill criterion).

## Consequences

**Enables** — a direct LPG-vs-RDF comparison on the same corpus, which no paper in the reading list has done; a fallback if Neo4j-side retrieval degrades at plant scale; and an honest measurement of RDF's triple-count footprint on attribute-heavy P&ID data instead of a guess.

**Costs** — a second store to learn and keep running (one Hungarian teaching note per concept as we go, per the user's standing request); a vocabulary-mapping task that A alone would not need; and the consistency checks on the A side must still be written by hand (2502.18493's 33 rules become the model) while the B side can express some of them as SHACL shapes.

**Kill criterion for B** — if the RDF loader and SPARQL strategy are not running on the synthetic multi-page benchmark by the end of phase 3, B is cut and this ADR is superseded with A alone. The phase-3 crossover measurement is never delayed for B.

**Revisit if** — cross-sheet entity resolution turns out to need real inference (transitive tag identity, subclass reasoning over equipment types), which is exactly what OWL is for and exactly where hand-coded Cypher would get ugly.

**Follow-up** — the teaching note this ADR pointed at (`docs/Notes/rdf-vs-lpg.md`, claimed written 2026-08-25) never existed in the repository; the drift was noticed 2026-09-05. Written for real on 2026-09-06 as `docs/Notes/lpg-vs-rdf.md` (Hungarian). Next: an `architect` design note for the RDF side — store choice (n10s vs separate triplestore), IRI scheme, DEXPI vocabulary mapping. **Vocabulary input, 2026-09-08:** `10-literature/ontology-landscape.md` §5 — generate the namespace from the 514 pyDEXPI classes (names unchanged, so LPG↔RDF labels stay comparable), align outward to the legacy PCA RDL IRIs already cited in 105 pyDEXPI docstrings and to QUDT for units, and add only a ~10-term multi-sheet extension (drawing-set container, `continuesAs`, `sameTaggedItemAs` + `IdentityGroup`, per-assertion provenance). The current PCA RDL is auth-walled (HTTP 401), so the aligned subset must be vendored locally.

## Evidence added 2026-08-25 (from the teaching note)

- **"RDF is standardized, Cypher is proprietary" is obsolete.** **GQL — ISO/IEC 39075:2024**, published 17 April 2024, is the first new ISO query language standard since SQL (1987) and is built directly on Cypher. Both sides are standardized; standardization is not the differentiator. Expect the professor to raise this, and have the answer ready.
- **The genuine differentiator is inference and declarative validation** (OWL/RDFS + SHACL), not the query language. Several of 2502.18493's 33 hand-written rules are five-line SHACL shapes. But their rules are *graph rewriting* (LHS→RHS), which is not SHACL's strength — RDF would replace some of that engine elegantly, not all of it.
- **Reification interacts with the thesis claim.** P&ID data is attribute-heavy; reifying it multiplies triple count. Since this dissertation is about what breaks at scale, any RDF evaluation must **measure** its footprint rather than assume it.
- **Standards status verified 2026-08-25:** RDF 1.2 Concepts is a W3C *Candidate* Recommendation (7 Apr 2026), not yet full REC. SPARQL 1.1 deployed, 1.2 in progress. SHACL mature, 1.2 partly in Working Draft. GQL published.

## Outcome log
- **2026-09-26** Superseded **in part** by ADR-0012 (K3, accepted): the RDF/SPARQL store is not built; LPG (Neo4j) primary stands; the comparison becomes one written thesis section.
