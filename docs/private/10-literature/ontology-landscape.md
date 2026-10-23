---
topic: Ontologies and information models for P&IDs and process plants
date: 2026-09-08
status: draft
author: researcher agent (for the professor's ontology question)
question: >
  "Is there an ontology? Which ontology do they work on? Or is this missing from the
  big ones, like schema.org? Or is a P&ID ontology missing and needed?
  An ontology is definitely needed." (professor, translated from Hungarian)
sources:
  # verified by fetching the HTML/JSON/plain-text source on 2026-09-08
  - https://dexpi.org/specifications/
  - https://dexpi.org/dexpi-2-0-specification-available-with-sparxsystems-enterprise-architect-modeling-tool/
  - https://dexpi.org/announcement-dexpi-2-0-release-events-november-2025/
  - https://dexpi.org/dexpi-august-2026-update/
  - https://gitlab.com/dexpi/Specification  (via GitLab API tree scan)
  - https://github.com/dexpi
  - https://github.com/process-intelligence-research/pyDEXPI  (+ GitHub API + raw pydantic_classes.py)
  - http://data.posccaesar.org/rdl/RDS7151859  (content-negotiated Turtle)
  - http://data.15926.org/rdl/RDS304199
  - https://rds.posccaesar.org/ontology/lis14/
  - https://rds.posccaesar.org/
  - https://posccaesar.org/ontology/plm/ont/equipment/
  - https://rds.posccaesar.org/doc/background/iso15926-2_in_OWL/
  - https://docs.posccaesar.org/libraries-and-standards/arrowhead-handbook/Handbook/
  - https://docs.posccaesar.org/libraries-and-standards/arrowhead-handbook/Use_Cases/
  - https://www.jip36-cfihos.org/cfihos-standards/
  - https://readi-jip.org/digital-reference-data-library-based-on-iso-15926-part-14/
  - https://en.wikipedia.org/wiki/ISO_15926
  - https://en.wikipedia.org/wiki/IEC_Common_Data_Dictionary
  - https://www.avt.rwth-aachen.de/cms/AVT/Forschung/Sonstiges/Software/~ipts/OntoCape/?lidx=1
  - https://reference.opcfoundation.org/specs/OPC-30250/7
  - https://schema.org/ , https://schema.org/docs/schemas.html , https://schema.org/docs/full.html , https://schema.org/Pump (404)
  - https://www.wikidata.org/w/api.php  (wbsearchentities)
  - https://qudt.org/
  - https://www.w3.org/TR/vocab-ssn/
  - https://spec.industrialontologies.org/iof/
  - https://arxiv.org/html/2603.22528v1 , https://arxiv.org/html/2502.18928v1 , https://arxiv.org/html/2502.18493v1
  - https://arxiv.org/html/2411.13929v2 , https://arxiv.org/html/2606.03410v1 , https://arxiv.org/abs/2607.19568
  - https://arxiv.org/abs/2504.21694
  - https://github.com/mgupta70/PIDQA , https://asu.elsevierpure.com/en/publications/pidqaquestion-answering-on-piping-and-instrumentation-diagrams/
  - https://graphwise.ai/event/industrial-semantic-interoperability-summit-2026/
  - https://www.cares.cam.ac.uk/research/the-world-avatar/
not_readable:
  - https://www.mdpi.com/2504-4990/7/2/39  (PIDQA full text - HTTP 403)
  - https://onlinelibrary.wiley.com/doi/full/10.1002/cite.202200223  (Oeing 2023 - HTTP 403)
  - https://arxiv.org/html/2607.19568v1  (HTTP 404; paper is PDF-only, not opened per project rule)
  - IDTA-02012-1-0_Submodel_DEXPI.pdf on industrialdigitaltwin.org  (PDF-only, not opened)
  - https://www.arcweb.com/industry-best-practices/dexpi-standard-engineering-data-interoperability-process-industry  (HTTP 403)
  - https://blog.ansi.org/ansi/ansi-isa-5-1-2024-instrumentation-symbols/  (HTTP 403)
---

# The ontology landscape for P&IDs - what exists, what the papers use, and where the real gap is

**Reading rule for this note.** Every factual line below is marked:
**[V]** = verified today (2026-09-08) by fetching the source named next to it;
**[R]** = reported by a secondary source (search snippet, third-party page) and *not* confirmed from the
primary document; **[X]** = could not be read (paywall / 403 / PDF-only under the project's no-PDF rule).
Nothing in this note is from memory.

**One-line answer to the professor.** Yes, ontologies exist - several, and they are serious:
ISO 15926 / IDO (ISO 23726-3) in OWL 2, the PCA Reference Data Library, OntoCAPE, CFIHOS's RDL.
DEXPI - the P&ID standard everyone in our field actually uses - is a **UML + XML information model with
no published OWL/RDF form**; its class *definitions* are borrowed from the ISO 15926 Part 4 reference data
library, and an OWL version of DEXPI is being built right now by TotalEnergies (announced 2026-03-23) but
is not published. schema.org has nothing: no `Pump`, no `Valve`, no `Pipe`, and it never intended to.
So "a P&ID ontology" is neither missing nor free for the taking - what is missing is anything that
*uses* these vocabularies for **retrieval at multi-sheet scale**.

---

## 1. Which ontologies / information models exist

### 1.1 Summary table

| Vocabulary | Models what | Machine-readable form | Open? | Maintainer | Last activity seen |
|---|---|---|---|---|---|
| **DEXPI** (P&ID 1.4 / DEXPI 2.0) | P&ID plant items, piping topology, instrumentation, graphics, sheet metadata | UML (Sparx EA) + **DEXPI XML / XSD**; **no OWL/RDF** | Yes, Creative Commons **[V]** | DEXPI e.V. | 2.0 published Oct 2025; news 2026-08-25 **[V]** |
| **ISO 15926** | Lifecycle data for process plants; upper data model (Pt 2) + reference data (Pt 4) | Pt 8 = OWL/RDF implementation, Pt 12 = OWL2 lifecycle-integration ontology **[R, Wikipedia]**; Pt 2-in-OWL exists as a 2008 PCA "intermediate effort", unofficial **[V]** | Standard text paid; RDL browsable free | ISO TC 184/SC 4 + POSC Caesar Association (PCA) | Pt 6:2024 **[V, handbook]** |
| **IDO** (ex ISO/TR 15926-14, now **ISO 23726-3**) | Upper ontology for industrial asset and process data | **W3C OWL 2** **[V]** | Ontology browsable; ISO text paid | PCA / DNV / ISO | "IDO v4.2 (FDIS, April 2026)" **[V, handbook]** |
| **PCA RDL** (two generations) | Equipment / piping / instrument classes and properties | legacy `data.posccaesar.org/rdl/RDS...` dereferences to **Turtle** **[V]**; new `plm/rdl/PCA_...` is OWL 2 but returns **HTTP 401** **[V]** | legacy open; current one auth-walled | PCA | equipment module `versionInfo 0.9.1`, `modified 2022-09-26`, status *incomplete* **[V]** |
| **CFIHOS** (IOGP JIP36) | Handover data requirements: tag / equipment class attributes, document metadata | RDL published as **Excel + CSV only**; no RDF/OWL/API listed **[V]** | Free download **[V]** | IOGP JIP-36 | "Version 2.0 (November 2025)" **[V, jip36 page]** |
| **OntoCAPE 2.0** | Chemical process engineering: materials, models, process systems | **62 OWL files** **[V]** | Free after a questionnaire; **GPL** **[V]** | RWTH Aachen AVT | newest publication listed = 2009 -> dormant **[V]** |
| **IEC 61987 / IEC CDD** | Property dictionaries (lists of properties) for process measuring equipment | Online standard database at cdd.iec.ch; data spec from IEC 61360 **[V, Wikipedia]** | Free to browse **[V]** | IEC SC 3D (+ joint WG with ISO TC 184/SC 4) | rolling change requests ~6-monthly **[V, Wikipedia]** |
| **IEC 62424 (CAEX)** | PCE requests in P&IDs + P&ID <-> PCE-CAE tool exchange | XML (CAEX); AutomationML derives from it | Paid standard | IEC | AutomationML->OWL work 2025 (arXiv 2504.21694) **[V]** |
| **ISA-5.1** | Instrument **symbols and identification letters** on drawings | none - it is a drawing convention, not a data model | Paid | ISA / ANSI | ANSI/ISA-5.1-**2022** on the ANSI webstore **[R]**; a 2024 edition is claimed by an ANSI blog page I could not open **[X]** |
| **ISO 10628 / ISO 10209** | Flow-diagram graphical symbols / plant-structure terminology | none (graphical + terminological) | Paid | ISO | cited *by* DEXPI **[V]** |
| **IMF** (ISO/IEC 81346-based) | Reference-designation aspects (`=`, `-`, `+`), `partOf` / `connectedTo` / `fulfills` | **RDF / OWL / SHACL** **[V, handbook]** | Manual v0.3.0 referenced | READI JIP / TechnipFMC / DISC | IMF Manual v0.3.0 cited in fPVN D3.3, 2026 **[V]** |
| **OPC UA for DEXPI** (OPC 30250) | DEXPI classes as an OPC UA address space | OPC UA NodeSet (~179 ObjectTypes) **[V]** | Spec free to read online | OPC Foundation | v1.0 **[V]** |
| **AAS submodel IDTA 02012-1-0** | "Information Model for P&I Diagrams based on DEXPI Standard" | AAS submodel template | Free PDF | IDTA | **[X]** PDF-only, not opened |
| **QUDT** | quantity kinds, units, dimensions - nothing physical | OWL/SHACL, CC BY 4.0 **[V]** | Yes | QUDT.org (501(c)(3)) **[V]** | Release 2.1; page "Last Updated March 1, 2022" **[V]** |
| **SOSA/SSN** | sensors, observations, actuators, procedures | OWL, W3C Recommendation **19 Oct 2017** **[V]** | Yes | W3C | 2017 (+ 2017 erratum) **[V]** |
| **IOF** (Industrial Ontologies Foundry) | manufacturing; BFO-based | OWL, MIT licence **[V]** | Yes | IOF | release **202603**, 999 classes, 158 properties, 7 domains **[V]** - no process-plant / P&ID module found **[V]** |
| **Brick / SAREF** | buildings, HVAC, smart appliances | OWL/RDF | Yes | Brick consortium / ETSI | out of scope for process plants **[R]** |

### 1.2 DEXPI - the one that matters to this thesis

**What it is.** From `dexpi.org/specifications/` **[V]**:

> "The DEXPI Specification 2.0 defines a standardized data model for plant models and process models,
> enabling consistent exchange of engineering information, especially BFDs, PFDs, and P&IDs, across tools
> and organizations. ... It comprises the DEXPI P&ID Specification 1.4 as plant model and an improved
> version of the DEXPI Process Specification as process model."

> "DEXPI 2.0 is the first version making use of DEXPI XML as the format for the specification as well as
> the serialization of instances/diagrams. Starting with this version, DEXPI can be fully used without the
> need for implementation of Proteus XML schema."

Specifications are offered as PDF, HTML and "supporting materials", with the "Source of truth at
[GitLab]" -> `https://gitlab.com/dexpi/Specification`, and "DEXPI specifications are published under a
Creative Commons license" **[V]**. DEXPI 2.0 release events were announced for 25 and 27 November 2025
(news post dated 2025-11-10) **[V]**; a later news post says "Following the publication of DEXPI 2.0 last
October" **[V]**. Version history of the plant model, quoted from PCA's DEXPI use-case page **[V]**:
"DEXPI Plant was modelled with UML, and the first releases used the Proteus P&I D Profile Schema 4.0.1 as
serialization platform. In 2016 DEXPI Plant 1.1, in 2017 DEXPI Plant 1.2 and in 2021 DEXPI Plant 1.3 was
released."

**Is it an ontology?** No. It is a UML information model with an XML serialization. I scanned the whole
GitLab source-of-truth repository through the GitLab API (225 tree entries over 3 pages, `ref=master`,
project last activity 2026-08-05) **[V]**. File extensions present: `.html` 97, `.pdf` 24, `.svg` 23,
`.py` 17, `.rst` 9, `.png` 9, `.ods` 3, `.gif` 3, `.gitkeep` 3, `.yml` 1, `.md` 1, **`.xsd` 1**, `.xml` 1.
**Zero `.ttl`, `.owl`, `.rdf`, `.jsonld`, `.nt`, `.trig` files.** The `github.com/dexpi` organisation holds
only three repos (Specification, last updated 2021-09-24; GraphicBuilder and TestCases, archived 2018) **[V]**.

**What DEXPI borrows from the ontology world.** From the PCA / Arrowhead fPVN handbook **[V]**:

> "DEXPI uses ISO 15926 Part 4 as its reference data library for class and property definitions;
> additional concepts are published in the DEXPI sandbox."

and from the same source's DEXPI use case **[V]**, DEXPI Plant is "based on international standards
wherever possible": plant structure ISO 10209; apparatus/machine and piping taxonomy and symbols
ISO 10628; instrumentation concept IEC 62424 / IEC 61987; boundary and maintainable-item concepts
ISO 14224; reference data library ISO 15926 part 4. It also notes: "DEXPI Plant does not have a very
detailed property concept for the different classes" - only required services, design sizes, design
pressures, design temperatures, required material.

**An OWL DEXPI is being built - by industry, not by us.** dexpi.org news, 2026-03-23 **[V]**, verbatim:

> "In the same spirit of developing open industry 'commons', TotalEnergies is currently building a
> semantic version of the DEXPI models, aligned independently with both ISO 21838-2 (BFO: Basic Formal
> Ontology), and the upcoming ISO 23726-3 (IDO: Industry Data Ontology), still under development.
> These semantic assets will be shared with DEXPI members for review and alignment, ensuring that their
> contents are validated collectively before broader dissemination."

The same post records that the DEXPI 2.0 UML model now ships as a Sparx Enterprise Architect QEA project
plus an HTML export **[V]**. In parallel, the EU **Arrowhead fPVN** project (Chips JU 101111977) has a work
package whose scope is "complex product data standards (CFIHOS, DEXPI Process and P&ID, STEP),
semantization of these standards, harmonization of industrial ontologies under the IDO top-level
ontology" **[V, Graphwise summit page and the handbook]**.

**How far that semantization has actually got.** I read the Arrowhead fPVN Handbook's
"Alignment with DEXPI" section in full **[V]**. It aligns DEXPI's *lifecycle zones* and *property model*
to IDO, implemented "fully ... in Turtle and verified in GraphDB" - for **one pump**. The input is, in the
appendix's own words, a "hand made simplified xml file for the DEXPI pump life cycle story" whose
namespaces are `http://example.com/dexpi/2.0/` and similar **[V]**. The handbook's own gap list says the
"IDO PLM modules for Process and Equipment are incomplete and not actively maintained" **[V]**. The word
**"connector" does not appear anywhere in the handbook**, and P&ID *topology* is mentioned only
descriptively **[V, full-text grep of the rendered page]**. So DEXPI->OWL exists today as a
property/lifecycle alignment demo on a single item, not as a loadable P&ID ontology.

### 1.3 pyDEXPI - how our Pydantic classes relate to DEXPI (and to ISO 15926)

Repository `process-intelligence-research/pyDEXPI`, **AGPL-3.0**, last push **2026-04-17**, 220 stars
**[V, GitHub API]**. README: it "implements the DEXPI data model", "includes a Pydantic data class model of
the DEXPI data model", targets **DEXPI 1.3**, loads the "Proteus .xml export of DEXPI", and exports to
NetworkX (`GraphLoader`; `GraphAbstractor` with `build_complete_graph` / `build_process_graph` /
`build_conceptual_graph`). **No RDF, OWL or SPARQL export is mentioned** **[V]**.

I read the generated model file `pydexpi/dexpi_classes/pydantic_classes.py` (238,181 bytes) directly **[V]**:

- **514 classes**; **462** carry a `uri: ClassVar[str]` of the form
  `https://pyDEXPI.org/schemas/pydexpi_1_3/<className>.py`. So every class already has a *nominal* URI -
  but it is a stand-in identifier, not a resolvable ontology term.
- Occurrences of `rdf`, `owl`, `iri`, `ontolog` in that file: **0**.
- **105 class docstrings cite a reference-data-library definition by IRI** - 87 distinct
  `data.posccaesar.org/rdl/RDS...` and 18 distinct `data.15926.org/rdl/RDS...`. Example, verbatim:

  ```python
  class HeatExchanger(Equipment):
      """An apparatus or machine that has the capability of heat exchanging (from http://data.15926.org/rdl/RDS304199)."""
  ```

- I dereferenced one of them with content negotiation **[V]**:
  `curl -H "Accept: text/turtle" http://data.posccaesar.org/rdl/RDS7151859` -> **HTTP 200, `text/turtle`**,
  and the payload types the class as
  `<http://rds.posccaesar.org/2008/02/OWL/ISO-15926-2_2003#ClassOfInanimatePhysicalObject>`,
  `rdfs:label "PROCESS PLANT"`, `hasDefinition "A plant employed in carrying out chemical processes,
  including the required supporting processes."` - **word for word the pyDEXPI `ProcessPlant` docstring.**
  The same RDS number under `data.15926.org` returned HTML only in my test.

**This is the single most useful finding for ADR-0002:** the bridge from our Pydantic model to a live RDF
vocabulary already exists inside the source we are using, as docstring annotations pointing at
dereferenceable PCA RDL IRIs.

**Multi-sheet primitives that already exist in DEXPI 1.3** **[V, same file]** - important, because the
thesis must not claim these are missing:

- 16 off-page-connector classes, including `PipeOffPageConnector`, `FlowInPipeOffPageConnector`,
  `FlowOutPipeOffPageConnector`, and the signal equivalents.
- `PipeOffPageConnectorReferenceByNumber` - *"A reference to a PipeOffPageConnector by drawing and
  connector number."* with data attributes **`referencedConnectorNumber`** and
  **`referencedDrawingNumber`**; and `PipeOffPageConnectorObjectReference` - *"A reference to a
  PipeOffPageConnector by an association."* with reference attribute `referencedConnector`.
- `TaggedPlantItem` with `tagName`, `tagNamePrefix`, `tagNameSequenceNumber`, `tagNameSuffix`.
- `MetaData` carries **`drawingNumber`, `sheetNumber`, `totalNumberOfSheets`, `replacedDrawing`**, plus
  site / plant / area / section identification codes.

**And the multi-sheet primitive that does not exist** **[V]**: `DexpiModel` is documented as
*"An entire DEXPI model. A DexpiModel is the root of the composition hierarchy"* and holds exactly one
`conceptualModel` and one `diagram`. **One DEXPI file = one drawing.** There is no container class for a
set of drawings, and no construct that asserts "this `TaggedPlantItem` on sheet 3 is the same item as that
one on sheet 8". Cross-drawing continuation is expressible only as an unresolved *string pair*
(`referencedDrawingNumber`, `referencedConnectorNumber`), or as an object reference that cannot cross a
file boundary because there is no shared identifier space.

### 1.4 ISO 15926, IDO / ISO 23726-3, and the PCA RDL

- Parts, from the Wikipedia table (the article states "as of February 2022") **[R]**: Pt 1 overview,
  Pt 2 data model (IS since 2003), Pt 3 geometry/topology reference data, Pt 4 reference data
  (TS, 2007-06-05), Pt 6 under development, Pt 7 template methodology,
  **Pt 8 "OWL/RDF implementation" (published)**, Pt 9 under development, Pt 10 conformance testing,
  Pt 11 under development,
  **Pt 12 "Life cycle integration ontology in Web Ontology Language (OWL2)" (published)**, Pt 13.
- The Arrowhead handbook lists as most relevant **[V]**: ISO 15926-1:2004, ISO 15926-2:2003,
  **ISO/TS 15926-4 Ed. 4** (core reference data), **ISO 15926-6:2024**. And, crucially **[V]**:

  > "ISO 15926 was not originally designed for reasoning, but ISO 15926-4 Ed. 4, when published as OWL,
  > provides a basis for OWL 2 DL inference."

  Note the conditional - the OWL form of Part 4 Ed. 4 is spoken of as a future artefact.
- The only OWL rendering of Part 2 that is actually downloadable is PCA's own, and PCA describes it as an
  **"intermediate effort"** made in **2008**, unofficial, with two files still reachable "as of 2022", and
  a known defect (a dependency on the now-unavailable co-ode OWL List ontology) **[V]**.
- **IDO** = "a W3C OWL 2 ontology", formerly ISO TR 15926-14, now "part of the emerging ISO/NP 23726
  standard, specifically ISO/NP 23726-3 Ontology Based Interoperability"
  **[V, rds.posccaesar.org/ontology/lis14/]**. Handbook baseline: "IDO v4.2 (FDIS, April 2026)",
  namespace prefix `lis:` **[V]**.
- **PCA RDL, two generations, and an access wall** **[V]**:
  - *Legacy*: `data.posccaesar.org/rdl/RDS...` -> open, content-negotiable **Turtle** (tested above).
  - *Current*: `rds.posccaesar.org/ontology/plm/rdl/PCA_...`. The **HTML documentation is public** - the
    `equipment` module page gives `title equipment`, `issued 2021-08-27`, `modified 2022-09-26`,
    `versionInfo 0.9.1`, `preferredNamespacePrefix rdl`, licence **CC BY-SA 4.0**, status **incomplete** -
    and it carries **198 distinct class labels marked "(DEXPI symbol)"** (e.g. "Bag Filter (DEXPI symbol)",
    "Agitator (DEXPI symbol)"), i.e. PCA maintains a DEXPI-symbol alignment inside its RDL.
    But requesting the module IRI or an individual `PCA_...` IRI with `Accept: text/turtle` returns
    **HTTP 401** - the machine-readable form is behind PCA authentication.
  - Handbook: "The PCA RDL provides over 10,000 reference data instances built on ISO 15926-4" **[V]**.
- READI JIP built the "Digital Reference Library (RDL) ... according to the ISO 15926 Part 14 standard",
  published by PCA at rds.posccaesar.org, with the Krafla/Equinor and NOA/AkerBP field projects **[V]**.

### 1.5 CFIHOS (IOGP JIP36)

From `jip36-cfihos.org/cfihos-standards/` **[V]**: latest release **Version 2.0 (November 2025)**;
documents include Scope and Procedures (C-TP-001), Specification (C-SP-001), implementation guides for
principal and contractor (C-GD-001/002), RDL Development Guide (V08), Data Dictionary (C-DM-002); the RDL
is published in **Excel (CORE and EXTENDED) and CSV (CORE)** - *no SQL, RDF/OWL or API form is listed*;
"All documents are available to download and use FREE of charge"; managed by IOGP. Scope is
**equipment / tag attributes and document metadata**; no P&ID topology or piping connectivity.
*(I did not open the Excel/CSV files - project rule.)*

The Arrowhead handbook describes CFIHOS differently on two points **[V]**: it says "Version 2.0
(October 2024) restructured the specification as a formal requirements document (REQIF-compatible ...)" and
that the RDL "contains more than 10,000 property definitions, equipment classes, document types, and
discipline codes". **Flagged discrepancy:** the CFIHOS site says v2.0 = November 2025, the handbook says
October 2024. Do not cite a CFIHOS 2.0 date in the thesis before resolving this.

A **CFIHOS Semantics Working Group** was "established in 2024 within the CFIHOS governance structure
(IOGP JIP-36) with the mandate to develop IDO-compliant semantic representations of CFIHOS data", led by
Onno Paap (Fluor) **[V]**. So CFIHOS-in-OWL is also *in progress, not published*.

### 1.6 OntoCAPE and its descendants

RWTH Aachen AVT page **[V]**: "The current release of OntoCAPE consists of 62 OWL files, each of which
includes one module of the ontology"; the informal specification is six technical reports (Meta Model,
Upper Level, Supporting Concepts, Material, Mathematical Models, Chemical Process System); "OntoCAPE is
distributed under the terms of the GNU General Public License"; free of charge after completing a
questionnaire; the unzip instruction still hard-codes `C:\OntoCAPE\`; the newest publication listed is 2009
and no update date is given -> effectively **dormant**.

OntoCAPE is not dead as *content*: Cambridge CARES' **J-Park Simulator / The World Avatar** knowledge graph
uses OntoCAPE classes alongside OntoKin, OntoCityGML and DBpedia **[R, cares.cam.ac.uk]**. I found no
evidence in the sources I read that this line of work touches P&ID *drawings*, digitization or retrieval
benchmarks - treat it as plant/process-level ontology work, adjacent to us.

### 1.7 The rest, briefly

- **IEC CDD** (`cdd.iec.ch`): "a metadata registry providing product classification and formalized product
  descriptions", hosted by IEC-CO, maintained by IEC SC 3D with a joint working group with ISO TC 184/SC 4;
  data specification from IEC 61360; "freely available"; IEC 61360-4 DB designates it "an International
  Standard in the form of an online database" **[V, Wikipedia]**. A claim that XML-Schema and JSON exchange
  formats exist via IEC 62656-8 appeared only in a search summary **[R]** - unverified.
- **IEC 62424** defines CAEX, "a data transfer language" for exchanging PCE-request data between P&ID tools
  and PCE-CAE tools **[R, standards catalogue pages]**. The interesting academic follow-on is
  **arXiv 2504.21694** (Westermann, Ramonat, Hujer, Gehlhoff, Fay; submitted 30 Apr 2025, revised
  18 Sep 2025), "Automatic Mapping of AutomationML Files to Ontologies for Graph Queries and Validation":
  "transformation of AutomationML into OWL enables new use cases in querying with SPARQL and validation
  with SHACL", providing "an up-to-date ontology of the concepts defined in the AutomationML standard"
  **[V, abs page]**. Its evaluation is "a study on examples from the automation domain" with no counts in
  the abstract; I did not read the full text.
- **ISA-5.1** is a *symbol and identification* standard (what the bubble looks like, what the letters mean),
  not a data model - ANSI/ISA-5.1-2022 on the ANSI webstore **[R]**. An ANSI blog page claims a 2024
  edition **[X, 403]**.
- **OPC UA for DEXPI (OPC 30250 v1.0)** **[V]**: maps DEXPI into an OPC UA address space and states the
  structural cost explicitly - "The DEXPI data model uses multiple inheritance, a paradigm not compatible
  with OPC UA (an ObjectType can inherit from only one parent)", resolved by "An additional table with
  hierarchical relations between the DEXPI classes". Roughly 179 ObjectTypes. This matters as evidence:
  **DEXPI's multiple inheritance is a modelling feature that OWL handles natively and OPC UA does not.**
- **IMF** (Information Modelling Framework, READI JIP / TechnipFMC): grounded in ISO/IEC 81346 reference
  designation, "relies on W3C semantic technologies (RDF, OWL, SHACL) as its implementation layer", with
  three relations - `partOf`, **`connectedTo` ("topological connectivity and medium flow")**, `fulfills`
  **[V, handbook]**. This is the closest existing *topology* relation in an OWL-based industrial framework.
- **IOF**: BFO-based, release 202603 with 999 classes / 158 properties / 7 domains, MIT licence; no
  process-plant or P&ID module found **[V]**.
- **AAS / IDTA 02012-1-0** "Information Model for P&I Diagrams based on DEXPI Standard" exists but is
  distributed as PDF **[X]** - recorded, not read.

---

## 2. What the papers on our reading list actually use

**Answer: none of them uses an ontology.** All the DEXPI-based work uses **pyDEXPI class names as
labeled-property-graph labels**; the vision work uses small hand-made class lists; the largest QA dataset
uses **integers**. Verified per paper below.

> **ID correction for the task brief:** ChatP&ID is **arXiv 2603.22528**, not 2411.13929.
> 2411.13929 is Stuermer et al., "From Engineering Diagrams to Graphs: Digitizing P&IDs with Transformers"
> (the PID2Graph paper). See `00-reading-list.md`.

| Paper | Ontology / formal vocabulary? | What the labels actually are | Eval scale (for the record) |
|---|---|---|---|
| **2603.22528** ChatP&ID | **No.** RDF is discussed and *rejected* | pyDEXPI class hierarchy -> node labels | 1 DEXPI file (`DEXPIEX01.xml`), 19 QA pairs, authors' own reference answers, 2 runs per config **[V]** |
| **2502.18928** Talking like P&IDs | **No.** The words *ontology, OWL, RDF, SPARQL, semantic web, ISO 15926, vocabulary, taxonomy* do not appear **[V]** | "Node labels are inherited from the pyDEXPI class name and its parent class" | 1 flowsheet, 3 questions **[V]** |
| **2502.18493** Rule-based autocorrection | **No.** No OWL/RDF/SHACL; rules are "rule graphs" matched by VF2 subgraph isomorphism **[V]** | DEXPI classes via pyDEXPI | 1 illustrative P&ID; 5 of 33 rules shown; rules from "engineering heuristics, literature ... and existing workflows at Flour(c)" **[V]** |
| **2411.13929** PID2Graph / Relationformer | **No.** Only ISO 10628 appears, and only as the source of the *synthetic symbol templates* **[V]** | 7 symbol classes (General, Pump/Compressor, Tank/Vessel, Instrumentation, Inlet/Outlet, Valve, plus Arrow); 700 templates "collected from a broad range of sources" **[V]** | 60 real annotated P&IDs for training; OPEN100 = 12 real plans **[V, note 2411.13929.md]** |
| **PID2Graph dataset** | **No.** | GraphML labels: `connector, crossing, arrow, instrumentation, valve, general, inlet/outlet, background, tank, pump` **[from our own note pid2graph.md]** | 500 single pages, no cross-page ground truth |
| **2606.03410** Enginuity | **No.** None of *ontology, OWL, RDF, knowledge graph, schema, DEXPI, taxonomy, vocabulary* appears in the paper **[V]** | n/a (VLM benchmark; a JSON output schema only) | 10 manuals / 6,940 pages; Task 1 n=494; Task 2 = 60 QA pairs "authored by a domain expert" **[V]** |
| **2607.19568** MLLM -> process graphs | The abstract mentions no ontology / DEXPI / schema **[V, abs]** | unknown - **HTML version 404, PDF-only, not opened** **[X]** | "two ANSI-standard P&ID case studies" **[V, abstract]**; authors Baikai Zhu, Samuel Duong, Javal Vyas, Mehmet Mercangoez, submitted 21 Jul 2026 **[V]** |

**Verbatim quotes worth keeping.**

- 2502.18928 **[V]**: *"Node labels are inherited from the pyDEXPI class name and its parent class, which
  aligns with DEXPI specification."* Relationships: domain (`has_[componentType]`, `is_located_in`) and
  lexical (`send_to`, `control`, `send_signal_to`, `is_logical_end_of`, `measured_by`).
- 2603.22528 **[V]**: *"each pyDEXPI instance is represented as a graph node, and the class attribute is
  represented as a graph relationship and property ... the pyDEXPI class hierarchy is encoded as node
  labels"*; *"Compositional attributes are modeled as has-type relationships ... Reference attributes, such
  as send_to, control, manipulate ... are translated into relational edges"*.
- 2603.22528 on the RDF / LPG fork - the passage the professor will want to see **[V]**:

  > "There are two graph data formats commonly used for knowledge graph representation: (i) the Resource
  > Description Framework (RDF), which represents information as a triple store consisting of
  > (subject, predicate, object) statements (Pan, 2009). In the context of a P&ID, this could be expressed
  > as (Pump1, hasPressure, 50psi). RDF is a W3C standard and is typically queried using the SPARQL query
  > language. (ii) The Labeled Property Graph (LPG) model represents information using nodes, edges, and
  > associated properties that can be assigned to both nodes and relationships (Barrasa and Webber, 2023).
  > ... LPG-based graphs are typically queried using languages such as Cypher or Gremlin and are commonly
  > implemented in graph databases such as Neo4j."

  and their decision: *"While each of these formats has its own advantages ..., the choice of representation
  for a P&ID should be guided by the specific requirements of the implementation context"* -> *"the LPG
  graph format is particularly well-suited for representing such attribute-rich engineering data"*.
  Their only nod to standardization is *"Standardization initiatives such as DEXPI have also been
  instrumental in this shift by defining a unified data schema for P&IDs."*
  **So the closest prior art considered RDF explicitly and chose LPG on attribute-richness grounds** -
  exactly the trade-off ADR-0002 records, and exactly the thing we can measure instead of assert.

### 2.1 New find during this sweep - PIDQA (not previously on the reading list)

**Gupta, Wei, Czerniawski, Eiris - "PIDQA - Question Answering on Piping and Instrumentation Diagrams",
*Machine Learning and Knowledge Extraction* 7(2), article 39, June 2025, doi 10.3390/make7020039**
**[V, ASU Pure record + the authors' GitHub `mgupta70/PIDQA`]**. MDPI full text returned HTTP 403 **[X]**.

- Pipeline: entity recognition on the P&ID image -> base entity graph -> **Labeled Property Graph "enriched
  with semantic attributes"** -> an LLM translates the question to **Cypher** and executes it. Neo4j.
- Dataset: **"64,000 question-answer pairs" spanning "500 P&ID sheets"** from Dataset-P&ID, four categories
  (simple counting, spatial counting, spatial connections, value-based), **16,000 each**, **128 questions
  per sheet (32 per category)**, each accompanied by "a syntactically correct Cypher query" -> ground truth
  is programmatically generated, not human-written. Licence CC0-1.0.
- **Questions target individual sheets, not multiple sheets** **[V, GitHub README]**.
- Reported result: with GPT-3.5-turbo, dynamic few-shot sampling improved accuracy by **"10.6-43.5%"**
  over schema contextualization alone **[V, abstract]**.
- **Ontology content: none. The node labels are integers** - the README states symbols "are named as
  numbers ranging from 1 to 32" **[V]**.

Why this matters to the thesis: it is by far the **largest P&ID QA evaluation in the literature**
(64,000 questions / 500 sheets vs ChatP&ID's 19 questions / 1 sheet) - and it is still **single-sheet,
synthetic, template-generated and vocabulary-free**. It does not threaten the scale claim; it *sharpens*
it, because "many questions" is not "many documents", and it gives us a reason to report per-sheet and
cross-sheet question counts separately in our own benchmark.
**Action:** needs a proper `/paper-intake` note and a reading-list row; a stub is filed at
`docs/private/10-literature/make7020039-pidqa.md`.

---

## 3. Does schema.org (or any general-purpose vocabulary) cover P&IDs?

**No - and it was never meant to.** Verified today:

- schema.org's own mission statement **[V, schema.org]**: *"Schema.org is a collaborative, community
  activity with a mission to create, maintain, and promote schemas for structured data on the Internet, on
  web pages, in email messages, and beyond."* Founded by Google, Microsoft, Yahoo and Yandex; its purpose
  is enriched search results. Current release **V30.0, 2026-03-19**, with **"823 Types, 1529 Properties,
  19 Datatypes, 96 Enumerations and 535 Enumeration members"** **[V, schema.org/docs/schemas.html]**.
- `https://schema.org/Pump` -> **HTTP 404** **[V]**. A scan of the full type hierarchy
  (`schema.org/docs/full.html`) found **no** type for pump, valve, pipe, pipeline, tank, vessel, heat
  exchanger, instrument, control loop, process equipment or plant **[V]**. The nearest things are
  `Product`, `Place`, `EngineSpecification`, `PropertyValue`, `Observation`.
  -> schema.org models *documents about things, for search engines*, not engineering artefacts. The correct
  answer to the professor is that this is not a shortcoming of schema.org; P&IDs are out of its scope by
  design.
- **Wikidata** does have the *concepts*, at encyclopedia granularity **[V, wbsearchentities API]**:
  `Q134574` pump, `Q208443` valve, `Q627111` centrifugal pump, `Q1890459` piping and instrumentation
  diagram, `Q48995591` control loop; plus a generic property `P2789` "connects with" ("item with which the
  item is physically connected"). What it does not have is engineering *instance* vocabulary - no tag
  identity, no nozzle/port semantics, no design pressure per nozzle, no off-page connector. DBpedia is
  derived from Wikipedia and sits at the same granularity **[R]**.
- **QUDT**: "semantic specifications for units of measure, quantity kind, dimensions and data types",
  CC BY 4.0, Release 2.1; models **no equipment and no topology** **[V]**. It is nevertheless the right
  choice for units - the Arrowhead/IDO framework mandates it: instance data "MUST reference QUDT unit
  individuals (namespace http://qudt.org/vocab/unit/)" **[V]**.
- **SOSA/SSN** (W3C Recommendation, 19 October 2017) **[V]**: Sensor, Observation, Actuator, Platform,
  System, FeatureOfInterest - an observation/actuation pattern. It models **no equipment types, no piping
  topology, and it has no notion of a control loop**. It could describe *measurements taken by* an
  instrument that we identify some other way; it cannot describe the P&ID.
- **Brick / SAREF** are building-domain (HVAC, smart appliances) **[R]**; **IOF** is BFO-based
  manufacturing with no process-plant module **[V]**.

---

## 4. So is there a gap? - precise statements

### 4.1 What exists (do not claim these as contributions)

1. **A P&ID information model exists and is dominant.** DEXPI 2.0 / P&ID 1.4, UML + XML, Creative Commons,
   actively maintained (news 2026-08-25; work on 2.0.1 and a "DEXPI Profile" in progress) **[V]**.
2. **A mature process-plant ontology stack exists** in OWL 2: IDO / ISO 23726-3, ISO 15926 Parts 8 and 12,
   the PCA RDL, IMF, OntoCAPE **[V/R as marked]**.
3. **DEXPI is already semantically anchored** to ISO 15926 Part 4, and 105 pyDEXPI classes carry RDL IRIs
   in their docstrings, at least 87 of which dereference to Turtle today **[V]**.
4. **An OWL version of DEXPI is under construction by TotalEnergies** (BFO- and IDO-aligned), announced
   2026-03-23, plus an EU project (Arrowhead fPVN) whose WP3 exists to semantize DEXPI/CFIHOS/STEP **[V]**.
   -> **Building "the DEXPI ontology" is therefore not a defensible master's contribution.** We would be
   racing an industry consortium and would lose on authority even if we won on time.
5. **DEXPI already has a cross-sheet vocabulary at the schema level**:
   `PipeOffPageConnectorReferenceByNumber(referencedDrawingNumber, referencedConnectorNumber)`,
   `PipeOffPageConnectorObjectReference(referencedConnector)`, the signal equivalents, plus
   `MetaData.drawingNumber / sheetNumber / totalNumberOfSheets` **[V]**.
   -> **Do not write "there is no vocabulary for off-page connectors". There is.**

### 4.2 What does not exist (verified absences - candidate contributions)

1. **No published OWL/RDF/SHACL serialization of the DEXPI P&ID information model.** Verified by scanning
   the source-of-truth GitLab repository: zero RDF files among 225 tree entries **[V]**. The IDO-side
   "semantization" that exists today is a **hand-written example XML about one pump**, in `example.com`
   namespaces, covering **properties and lifecycle zones - not P&ID topology**; the word "connector" does
   not occur anywhere in the Arrowhead handbook **[V]**.
2. **Nobody uses any of these vocabularies for retrieval.** Every paper on the reading list, plus PIDQA,
   uses pyDEXPI class names, small hand-made class lists, or integers as graph labels; RDF appears in this
   literature exactly once, in ChatP&ID, as an option that is explained and then declined **[V]**.
   There is **no P&ID SPARQL/OWL retrieval baseline in the literature at any scale**.
3. **No identity vocabulary across drawings.** `DexpiModel` is one drawing (one `conceptualModel`, one
   `diagram`) **[V]**; there is no container for a drawing set and no construct asserting that a
   `TaggedPlantItem` on one sheet is the same plant item as one on another sheet. Cross-sheet continuation
   is an **unresolved string pair**. The tooling world confirms the state of practice: Autodesk's own
   support documentation says AutoCAD Plant 3D P&ID "does not assign unique identifiers to off-page
   connectors by default" and recommends adding attributes for the connected drawing name **[R, Autodesk
   support pages]**. That is CAD-vendor practice, not a published vocabulary.
4. **No SHACL (or any declarative) constraint set for P&ID consistency.** 2502.18493's 33 rules are
   `NetworkX` + VF2 rule graphs **[V]**. The nearest declarative work is in a different standard family -
   AutomationML -> OWL + SPARQL + SHACL (arXiv 2504.21694) **[V]**.
5. **No machine-readable link from a P&ID graph to CFIHOS handover data**, because the CFIHOS RDL ships as
   Excel/CSV **[V]** and its IDO-compliant form is a working group's mandate from 2024, not a release **[V]**.

### 4.3 The honest formulation of the gap

> An ontology for P&IDs is **not** missing - DEXPI (as an information model) plus ISO 15926 / IDO (as an
> ontology stack) cover the domain, and an official OWL DEXPI is being built by industry. What is missing
> is (a) any **loadable** OWL/SHACL form of DEXPI available to a researcher today, (b) any use of these
> vocabularies for **retrieval**, at any scale, and (c) any vocabulary or benchmark for **identity across
> drawings** - off-page connector resolution and tag identity between sheets. (a) is a two-week engineering
> task and someone else will publish the authoritative version; (c) is where the contribution is, and it
> needs (a) only as a means.

---

## 5. Practical recommendation for ADR-0002's RDF side

**These are recommendations, not findings.** They follow from sections 1-4, but they are my judgement, and
the `architect` design note for the RDF store should re-argue them.

**R1 - Do not invent a vocabulary; do not wait for one either. Mint a thin project namespace and align it
outward.** Target three layers:

| Layer | Use what | Why (evidence) |
|---|---|---|
| Class semantics for equipment / piping / instrument types | **PCA RDL legacy IRIs** `http://data.posccaesar.org/rdl/RDS...` via `rdfs:subClassOf` / `skos:exactMatch` | 105 pyDEXPI docstrings already name these IRIs; at least 87 dereference to Turtle today; DEXPI's own definitions are copied from them verbatim **[V]** |
| Units and quantity kinds | **QUDT** (`http://qudt.org/vocab/unit/`) | QUDT is what DEXPI properties are typed with in the IDO alignment, and the Arrowhead framework mandates it **[V]** |
| Everything DEXPI-specific with no external equivalent (structure, ports, off-page connectors, sheet metadata) | **our own namespace**, e.g. `https://<thesis>/ns/dexpi#`, generated mechanically from the 514 pyDEXPI classes, keeping the class names unchanged | there is no published DEXPI OWL to map onto **[V]**; keeping pyDEXPI names preserves comparability with ChatP&ID and "Talking like P&IDs", whose LPG labels are the same strings **[V]** |

**R2 - Generate, do not hand-write.** The mapping should be produced by a script over
`pydexpi.dexpi_classes.pydantic_classes`: 514 classes -> `owl:Class`; the `attribute_category` markers
already present in `json_schema_extra` (`"composition"`, `"reference"`, `"data"`) -> object properties vs
datatype properties; docstring-embedded `data.posccaesar.org/rdl/RDS...` IRIs -> alignment axioms. This is
the same transformation ChatP&ID performs into LPG labels, so the two stores stay comparable by
construction.

**R3 - The extension we genuinely have to write ourselves is small, and it is the thesis's own subject.**
Four things DEXPI does not give us:

1. a **drawing-set / plant-region container** (DEXPI's root is one drawing) - one class plus a `hasSheet`
   property;
2. **resolved** off-page connector links - DEXPI gives only the *unresolved* form
   (`referencedDrawingNumber` + `referencedConnectorNumber`); we need a `continuesAs` / `sameConduitAs`
   property whose *asserted* instances are our cross-sheet ground truth, and which lets us distinguish
   "the drawing says so" from "our resolver inferred it";
3. **tag identity across sheets** - `owl:sameAs` between `TaggedPlantItem` occurrences, or (safer, because
   `owl:sameAs` is unrestricted and will merge properties we may not want merged) a `sameTaggedItemAs`
   property plus an explicit `IdentityGroup`, which is already what the OPEN100 annotation design calls it;
4. ~~**provenance per assertion** (which sheet, which grid cell, who confirmed it)~~ **— DROPPED by the user, 2026-09-20: "It is not needed." The `verified_by_human` column in the OPEN100 annotation stays; it is a CSV field, not an ontology term. The extension is therefore three items, not four.** - the OPEN100 work already
   needs `verified_by_human`, so this is not new scope.

That extension is roughly ten classes and properties. **It should be presented as a multi-sheet extension
to DEXPI, not as "a P&ID ontology"** - the second framing is both untrue and easy for a reviewer to shoot
down with the TotalEnergies announcement.

**R4 - Two concrete measurements make the RDF side worth its cost** (and neither has been done by any paper
on the reading list **[V]**):
(i) **triple count and query latency** for the same corpus in LPG vs RDF at 1 -> 12 -> ~100 sheets, which is
the reification cost ADR-0002 says must be measured rather than assumed;
(ii) **transitive tag identity** - the `sameTaggedItemAs` closure across sheets is one SPARQL property path
or one OWL axiom, versus a hand-written traversal in Cypher. If inference wins anywhere it wins here, and
that is precisely ADR-0002's stated "revisit if" trigger.

**R5 - Store choice.** Nothing found today settles the n10s-vs-triplestore question, but two facts feed it:
the current PCA RDL is **auth-walled (HTTP 401)**, so we cannot rely on live vocabulary resolution and must
vendor a local copy of the RDL subset we align to **[V]**; and DEXPI's **multiple inheritance** - the thing
OPC UA had to flatten with a side table **[V]** - is native in OWL and awkward in a single-label LPG model.
That is a genuine, citable argument in RDF's favour for the *schema*, independent of retrieval performance.

**R6 - Do not adopt** schema.org (no relevant types **[V]**), SOSA/SSN (no equipment or topology **[V]**),
Brick/SAREF (buildings **[R]**), IOF (no process-plant module **[V]**) or OntoCAPE (GPL, and dormant since
2009 **[V]**) as the primary vocabulary. Cite them as considered and rejected, with these reasons.

---

## What the dissertation can and cannot claim

**Can claim (each backed by a source read on 2026-09-08):**

1. "No published OWL/RDF serialization of the DEXPI P&ID information model was available as of
   2026-09-08" - evidenced by the empty RDF file scan of `gitlab.com/dexpi/Specification` and by DEXPI's
   own 2026-03-23 announcement that a semantic version is *being built*.
2. "No paper in the P&ID digitization / QA literature uses a formal ontology; graph labels come from
   pyDEXPI class names, small hand-made class lists, or integers" - with the quotes in section 2, including
   PIDQA's "numbers ranging from 1 to 32".
3. "The closest prior art (ChatP&ID, arXiv 2603.22528) considered RDF explicitly and chose LPG" - with the
   verbatim passage in section 2.
4. "There is no P&ID retrieval baseline over RDF/SPARQL at any corpus scale" - absence verified by search;
   report it as an absence, not as proof of impossibility.
5. "DEXPI expresses cross-sheet continuation only as an unresolved (drawing number, connector number)
   string pair, and has no construct for asserting that a tagged item on one sheet is the same item as on
   another; one `DexpiModel` is one drawing" - verified from the generated class model.
6. "The published ontology alignment work for DEXPI (Arrowhead fPVN / IDO) covers properties and lifecycle
   zones, demonstrated on a hand-made single-pump example; it does not cover P&ID topology or cross-sheet
   connectivity" - verified from the handbook, including the absence of the word "connector".
7. "schema.org (V30.0, 2026-03-19, 823 types) has no class for a pump, valve, pipe or control loop, by
   design" - verified, with the 404 and the mission statement.
8. "PIDQA (MAKE 7(2):39, 2025) is the largest P&ID QA evaluation to date - 64,000 QA pairs over 500 sheets,
   128 per sheet, programmatically generated - and every question is scoped to a single sheet."

**Cannot claim (and must not drift into):**

1. NO - "There is no P&ID ontology." False: see ISO 15926 / IDO, the PCA RDL with its 198
   "(DEXPI symbol)" classes, and OntoCAPE.
2. NO - "We are building the first DEXPI ontology / the missing P&ID ontology." TotalEnergies announced
   exactly this on 2026-03-23, BFO- and IDO-aligned. Our artefact is a *thesis-scoped mapping plus a
   multi-sheet extension*, and must be described that way.
3. NO - "There is no vocabulary for off-page connectors." DEXPI 1.3 has 16 off-page connector classes,
   including reference by drawing and connector number.
4. NO - "ISO 15926 has no OWL form." Parts 8 and 12 exist (reported by Wikipedia, not verified in the ISO
   text), Part 2 has an unofficial 2008 PCA OWL rendering, and IDO / ISO 23726-3 is OWL 2. What is true is
   narrower: *no free, complete, loadable OWL bundle of ISO 15926-4 Ed. 4 was retrievable today, and the
   current PCA RDL returns HTTP 401 to machine requests.*
5. NO - "CFIHOS is machine-readable RDF." It is Excel and CSV; the IDO-compliant version is a 2024 working
   group mandate.
6. NO - any date for CFIHOS 2.0 until the November 2025 (CFIHOS site) vs October 2024 (Arrowhead handbook)
   discrepancy is resolved.
7. NO - anything about 2607.19568's internal representation: its HTML build 404s and the PDF was not opened.
8. NO - anything from Oeing et al. 2023 (*Chem. Ing. Tech.* 95, 1049-1060, doi 10.1002/cite.202200223):
   Wiley returned 403. A search snippet asserts it says the ISO 15926 RDL "serves as the basis for the
   DEXPI RDL", which is consistent with section 1.2, but it is **unverified** and must be re-fetched before
   use.

**Open follow-ups**

- [ ] Read the DEXPI 2.0 specification **HTML** build (linked from `dexpi.org/specifications/`) and check
      whether the off-page connector classes and the `MetaData` sheet fields survived 1.3 -> 1.4/2.0
      unchanged. Everything in section 1.3 is verified against pyDEXPI's **DEXPI 1.3** model.
- [ ] Watch for the TotalEnergies DEXPI semantic assets; if they appear before submission, our mapping
      should align to them rather than compete with them.
- [ ] Resolve the CFIHOS 2.0 date discrepancy.
- [ ] Obtain the Oeing et al. 2023 and PIDQA full texts through the university library (HTML only).
- [ ] Decide whether to request PCA API credentials for the current RDL, or to vendor the legacy
      `data.posccaesar.org` subset.
