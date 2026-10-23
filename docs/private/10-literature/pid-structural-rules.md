---
topic: Codified structural rules of real P&IDs, and which of them a synthetic generator can encode
date: 2026-09-12
status: draft
author: researcher agent
question: >
  What are the codified structural rules of real P&IDs, and which of them can be encoded as constraints
  in a synthetic P&ID generator (pyDEXPI patterns + the existing splitter)?
related: [40-design/splitter.md, ADR-0007, 10-literature/2502.18493.md, 10-literature/ontology-landscape.md,
          Notes/pid-szerkezeti-szabalyok.md, Notes/pid-lapkozi-csatlakozok.md, Notes/open100-rendszerkodok.md]
sources_read:   # fetched and read on 2026-09-12
  - ISO 10628-1:2014 official preview pages (iTeh), clauses 1-5.4.3: https://cdn.standards.iteh.ai/samples/51840/688f149554ee4443b3396c01f82da2ba/ISO-10628-1-2014.pdf
  - HNF-64103 Rev. 0 (Oct 2020), full text, 26 pp: https://hmis.hanford.gov/files.cfm/HNF-64103_-_Rev_00.pdf
  - KLM Technology Group, P&ID Project Engineering Standard Rev 01 (Feb 2011), free introduction pp. 1-23 of 146: https://www.klmtechgroup.com/PDF/ess/PROJECT_STANDARDS_AND_SPECIFICATIONS_piping_and_instrument_diagram_REV01.pdf
  - Toghraei (2019), Everand publisher preview (preface, ch. 1, ch. 2, ch. 3 sections 3.1-3.4): https://www.everand.com/book/401239042/Piping-and-Instrumentation-Diagram-Development
  - Wiley product page, 2nd edition: https://www.wiley.com/en-us/shop/general-introductory-chemical-engineering/piping-and-instrumentation-diagram-development-2nd-edition-p-9781394368587
  - AIChE ChEnected, "P&ID Part 3 - Symbology Primer" (2010): https://www.aiche.org/chenected/2010/09/interpreting-piping-and-instrumentation-diagrams-symbology
  - Wikipedia "Piping and instrumentation diagram" (raw wikitext): https://en.wikipedia.org/wiki/Piping_and_instrumentation_diagram
  - Wikipedia (de) "Kraftwerk-Kennzeichensystem" (raw wikitext): https://de.wikipedia.org/wiki/Kraftwerk-Kennzeichensystem
  - Wikipedia "IEC 81346" (raw wikitext): https://en.wikipedia.org/wiki/IEC_81346
  - pyDEXPI GitHub master: README, pydexpi/syndata/{pattern,dexpi_pattern,graph_pattern,generator_function}.py, data/dexpi_sample_patterns/ (10 JSON + 23 pickles): https://github.com/process-intelligence-research/pyDEXPI
  - pyDEXPI ESCAPE35 paper, LAPSE:2025.0371 (full text grepped): https://psecommunity.org/LAPSE:2025.0371
  - DEXPI TrainingTestCases (GitLab API; C01V04-VER.EX01.xml parsed; C08V01 two PDFs text-extracted): https://gitlab.com/dexpi/TrainingTestCases
  - Hirtreiter, Schulze Balhorn, Schweidtmann preprint (26 Oct 2022), section 3: https://www.pi-research.org/project/pid_pfd/Preprint.pdf ; abs page https://arxiv.org/abs/2211.05583
  - SynthPID, arXiv 2604.16513v1 (abstract, sections 1, 3.1-3.2, data/protocol, 5, 6): https://arxiv.org/html/2604.16513
  - zeroinstrument.com blog (secondary, no citations): https://zeroinstrument.com/documentation-requirements-and-drafting-guidelines-for-pid-piping-and-instrumentation-diagram/
  - pip.org discipline page: https://pip.org/disciplines/pid-and-process/
  - Semantic Scholar API metadata for DOI 10.1016/j.dche.2022.100038 and 10.1007/s11705-026-2685-z
not_readable:
  - PIP PIC001 official preview, store.accuristech.com/pip/products/preview/2574016 (HTTP 403); document-center.com PIP-PIC001 (403)
  - Wiley Online Library book and chapter pages for Toghraei (403)
  - AIChE ChEnected "Codes, Tags and Labels" Part 4 (403 today; read in an earlier session per Notes/pid-lapkozi-csatlakozok.md)
  - Autodesk support article on Plant 3D off-page connectors (403)
  - Hexagon Smart P&ID help "Consistency Checking" (404; JS-rendered)
  - ScienceDirect, Oeing et al. 2022 (403; open access CC BY per Semantic Scholar)
  - Springer, Ma et al. 2026 review (auth redirect; Semantic Scholar lists it CLOSED)
  - iso.org/standard/51840.html (403)
  - github.com/LatentSpaceIITB/SynthPID (GitHub API "Not Found", 2026-09-12)
deliberately_not_used:
  - Full-text copies of PIP PIC001 on Scribd, pdfcoffee, academia.edu, Google Drive, yumpu; of Toghraei on archive.org, pdfcoffee, slideshare; of IPS-E-PR-230 on Scribd, academia.edu, pdfcoffee; of Towler & Sinnott on academia.edu, pdfcoffee, dokumen.pub. These are unauthorised uploads of copyrighted texts. A thesis cannot cite them, so rules are not built on them.
---

# Codified structural rules of real P&IDs, and what a generator can encode

## Reading rules for this note

**Tags** (as specified by the task):
- **[verified]**: I read the text that states it, today, in the source named.
- **[recalled]**: I know it but did not read it in a source this session.
- **[not-read]**: the source exists but was not reachable.

`[verified, prior note]` means it was verified in an earlier session and recorded in the named project note, and was not re-read today.

**Source grade** (authority differs, so every rule row names it):
- **STD**: primary standard text, official preview pages only.
- **ORG**: a publicly released organisational standard or procedure.
- **BOOK**: a publisher preview.
- **ART**: a data or code artefact inspected directly.
- **SEC**: a secondary source (Wikipedia, blog, trade article).
- **OBS**: observation of real drawings recorded in project notes (not a codified rule).

**Encodability verdicts** use the four words from the brief. They are mapped onto the places where rules can enter pyDEXPI generation. All four hooks were verified in the pyDEXPI master source; the first three match the coordinator's reading of installed 1.2.0.

| Verdict | Hook | What it is (verified in source) |
|---|---|---|
| `pattern` | **H1 pattern** | A `DexpiPattern` wraps one `DexpiModel` and exposes `BasicPipingInConnector` / `BasicPipingOutConnector` interfaces. |
| `constraint` | **H2 counterpart** | `Connector.assess_valid_counterpart`. The shipped DEXPI version is a pure type check: in-connector accepts only out-connector and vice versa. |
| `constraint` | **H3 generator** | A custom `GeneratorFunction.get_next_step` / `initialize_pattern`. The shipped `RandomGeneratorFunction` works "fully at random". |
| `constraint` | **H4 capping** | `CappingFunction` caps the connectors still open at the end; its distributions must have exactly one connector label. |
| `constraint` | **post-check** | A rule graph matched after generation (the LHS/RHS + VF2 formalism of arXiv 2502.18493). This lives outside pyDEXPI. |
| `splitter` | **splitter** | A partitioning or connector-labelling parameter in `plantgraph.benchmark`. |
| `not-encodable` | none | The reason is always given. |

**Standards are paraphrased.** Short quotes only, never reproduced wholesale.

---

## 0. Answer in one paragraph

Codified P&ID rules exist and are specific at **level 1**: pump trim, control-valve stations, PSV trim, vessel drains and vents, instrument tags. They are specific at **level 3** only for **connector labelling and utilities**. Nothing I could legitimately read codifies **how a plant is partitioned into sheets** or **how many items a sheet holds**. No source gives a number. **Level 4** is codified by identification systems (KKS, IEC/ISO 81346) and by DEXPI's metadata slots, not by drawing rules.

The most useful single source turned out to be a publicly released US DOE contractor procedure, **HNF-64103**. It states it "is in agreement with Process Industry Practices (PIP) national standard" "except as noted". It is the best legitimate proxy for PIP PIC001, whose only full-text copies online are unauthorised uploads.

Two findings bear directly on the build:
1. The pyDEXPI repository **does** ship sample patterns, but they encode **none** of the verified level-1 rules. There are no instruments, no check valves, no block/bypass stations; valves are the generic `OperatedValve`. With the sample set, the random generator can only produce a **chain or a single ring**.
2. Codified utility rules **contradict** how `utility_aware` cuts. Real sets move utility **headers** to utility P&IDs and leave **consumer equipment** on the unit sheet with a service-labelled stub. The strategy moves **high-degree equipment** to hub sheets.

---

## 1. Sources actually used

| Key | Source | Grade | Access | Authority caveat |
|---|---|---|---|---|
| **ISO10628** | ISO 10628-1:2014 *Diagrams for the chemical and petrochemical industry, Part 1: Specification of diagrams*, clauses 1-5.4.3 | STD | official iTeh preview PDF | Preview ends at 5.4.3. Annex figures not seen. |
| **HNF** | HNF-64103 Rev. 0, *Preparation of Process Flow Diagrams and Piping and Instrumentation Diagrams*, B. A. Christensen, Mission Support Alliance, for US DOE. Published Oct 2020, stamped "Approved for Public Release; Further Dissemination Unlimited". | ORG | full text | One site's procedure. States agreement with PIP "except as noted" (section 3.2), but does not name PIC001 specifically. |
| **KLM** | KLM Technology Group, *Piping and Instrumentation Diagrams (P&ID) (Project Standards and Specifications)*, Rev 01, Feb 2011 | ORG | pp. 1-23 of 146, which KLM states it provides "for free on the internet" | Training-company standard for oil, gas and petrochemical projects. Its scope sentence matches search-result descriptions of IPS-E-PR-230; that derivation is **[not-read]**. |
| **TOG** | M. Toghraei, *Piping and Instrumentation Diagram Development*, Wiley/AIChE 2019 | BOOK | Everand preview: preface, ch. 1-2, ch. 3 sections 3.1-3.4 | The author calls it "book of rules of thumb for P&ID development". Chapters 4-19, where the rules are, are **[not-read]**. A 2nd edition (ISBN 9781394368587) adds a PFD chapter and expands ch. 20 **[verified, Wiley page]**. |
| **CHE3** | AIChE ChEnected, "P&ID Part 3: Symbology Primer" (2010) | SEC | full HTML | One practitioner's blog series. The author flags his own preferences. |
| **W-PID** | Wikipedia, "Piping and instrumentation diagram", section "Identification and reference designation" | SEC | raw wikitext | Secondary to ANSI/ISA-5.1 and ISO 14617-6. |
| **W-KKS** | Wikipedia (de), "Kraftwerk-Kennzeichensystem" | SEC | raw wikitext | Secondary to VGB-B 105 / VGB-S-811-01-2018. |
| **W-81346** | Wikipedia, "IEC 81346" | SEC | raw wikitext | Lists parts only. Aspects come from the ontology note. |
| **PYD** | pyDEXPI GitHub `master`: README, `syndata` sources, `data/dexpi_sample_patterns/` | ART | direct | **`import pydexpi` failed in this project's `uv` environment today** (ModuleNotFoundError). Code quotes are from `master`, not the installed 1.2.0. They agree with the coordinator's 1.2.0 reading of `RandomGeneratorFunction`. |
| **DXT** | DEXPI e.V., `gitlab.com/dexpi/TrainingTestCases`, licence **CC BY 4.0** | ART | GitLab API | Example/test files. C01 is a data-model demonstrator. |
| **HIRT** | Hirtreiter, Schulze Balhorn, Schweidtmann, "Towards automatic generation of P&IDs with AI", preprint 26 Oct 2022 | ART/paper | full preprint, section 3 | Abstract numbers match arXiv 2211.05583. The abs page gives v2 of 8 Jun 2026 and AIChE J. 70(1) e18259 **[verified, abs page via fetch summary]**. |
| **SYN** | Prasad & Mahapatra, "SynthPID: P&ID digitization from Topology-Preserving Synthetic Data", arXiv 2604.16513v1, 15 Apr 2026, CC BY 4.0 | paper | HTML | Sections 3.3-3.5 and the results tables were not read line by line. |
| **ZERO** | zeroinstrument.com, "Documentation Requirements and Drafting Guidelines for P&ID" | SEC | HTML | Uncited blog. Used only where it agrees with ORG/STD. |
| prior notes | `ontology-landscape.md` (DEXPI classes, IMF aspects), `2502.18493.md`, `Notes/pid-lapkozi-csatlakozok.md`, `Notes/open100-rendszerkodok.md` | mixed | project | Verified in earlier sessions. |

### 1a. What kinds of rules exist, and why drawings follow them

**Three kinds of rules [verified, TOG preface].** "In the world of P&IDs there would be at least three sets of rules, guidelines or standards." Toghraei illustrates them with a valve:
1. **Development rules**: whether a valve is needed at that location, and which type and actuator.
2. **Demonstration rules**: which symbol shows it.
3. **Drafting rules**: which his book explicitly does not cover.

The generator mostly needs (1). The splitter needs the sheet-level part of (3). (2) belongs to the renderer, which is out of the current phase (`splitter.md` open question 4).

**Why drawings follow them [verified].**
- **Many users read the same drawing.** HNF 3.2: "Standardized P&IDs allow personnel to quickly get a detailed look at the system and understand its operation." "P&IDs provide the single most important source of information for the project, the client, and the design disciplines in the early stages of engineering design and provide documentation for configuration control." "P&IDs are, by their nature, a document that requires multi-discipline input."
- **They must be clear and stay cheap to revise.** HNF 3.2.1 objectives: "Clearly convey design information in an orderly manner consistent with FH requirements and industry practices" and "Minimize rework that may be required by subsequent revisions to the drawing."
- **Other documents are built from them.** TOG 1.1: the P&ID "might be considered the bible of a chemical process plant". It is used by Process, I&C, piping, mechanical, HVAC and civil groups. It "allows for the generation of other documents, including piping isometric drawings, the piping model, equipment and instrument lists, ... line designation table (LDT) or line list, material take-offs, loop diagrams, tie-in lists". "In HAZOP meetings, the discussion is mainly on P&IDs." "One main use of P&IDs is for maintenance personnel to initiate lockout–tag out actions."
- **The drawing evolves.** TOG 2.2: milestones "Issued for Review (IFR), Issued for Approval (IFA), Issued for Design (IFD), and IFC", then an as-built revision. This is why sources ask for space for future revisions (S8) and discourage deleting sheets (S15).

---

## 2. Level 1: local patterns (inside one equipment arrangement)

| ID | Rule | Source | Tag | Verdict / hook |
|---|---|---|---|---|
| **L1** | **Pump discharge: check valve, then block valve.** "Use a line size block and check valve in the discharge line (check valve will be located between block and pump)." KLM agrees: "discharge valve and check valve"; wafer-type check valves "should be avoided unless otherwise specified". | HNF 3.2.5.3; KLM p. 19 "Pumps" | [verified] | `pattern` (H1). The check-valve subtype is a pattern attribute. |
| **L2** | **Pump suction: block valve and strainer.** HNF: temporary suction screens at centrifugal pumps, "located at the first flanged joint between the pump and the suction block valve"; permanent basket strainers "for all rotary pumps". KLM: "Pump suction valve and strainer". | HNF 3.2.5.3; KLM p. 19 | [verified] | `pattern` (H1). Temporary vs permanent strainer splits by pump class, so use separate pattern distributions. |
| **L3** | **Discharge pressure gauge sits between the pump nozzle and the check valve.** | HNF 3.2.5.3; KLM p. 19 | [verified] | `pattern` (H1). Needs an instrument object in the pattern; no sample pattern has one (section 6.1). |
| **L4** | **Pump vents and drains.** HNF: "Provide a casing vent and valve." KLM: "Pump drains and vents piping and destination." | HNF 3.2.5.3; KLM p. 19 | [verified] | `pattern` (H1) |
| **L5** | **Positive-displacement pumps carry external relief.** "For positive displacement pumps, show external relief protection." DEXPI's own reference P&ID instantiates it: ReciprocatingPump → PipeTee → SpringLoadedGlobeSafetyValve → Tank (parsed from C01V04-VER.EX01.xml). | HNF 3.2.3.7; DXT C01 | [verified] | `pattern` (H1); `constraint` (post-check: PD pump with no relief path) |
| **L6** | **Minimum-flow bypass.** KLM lists "minimum flow bypass line requirement for pumps" among details to show. **No source read states when a min-flow line is required.** | KLM p. 19 | [verified] listing; condition not codified | `pattern` variant; the inclusion probability is an unsourced parameter |
| **L7** | **Warm-up bypass.** KLM: "a DN20 (¾ inch) bypass/drain from the check valve to the pump discharge line" for "the cases specified in item 8.1.4" (not in the free pages). HNF: with warm-up bypasses, the line-size suction valve "will be rated for pump discharge conditions". | KLM p. 19; HNF 3.2.5.3 | [verified] text; triggering condition [not-read] | `pattern` variant (condition unknown) |
| **L8** | **Installed spares are drawn on the P&ID.** ISO: the P&ID shall contain "installed back-up/reserve equipment". KLM: the spare is identified by the word "Spare"; "Automatic start-up of standby unit (if required)". PFDs differ: "Usually, only one of multiple identical train units and spared equipment should be shown" (HNF, **PFD section**). | ISO10628 4.4.2 a); KLM p. 19ff; HNF 3.1.2.2 | [verified] | `constraint` (H3: instantiate A/B parallel copies of a pattern). The tag-suffix convention is a generator parameter. |
| **L9** | **Control-valve station.** "In general, control valve stations have block valves and a by-pass." Show valve size and fail action (fail close/open/last position) and bypass valve size. KLM: "Block and bypass valve sizes at control valve stations"; air failure action FC/FO/FL. | HNF 3.2.4.2; KLM p. 22 "Instrumentation" items 3-4 | [verified] | `pattern` (H1). "In general" means not universal, so a station-vs-bare-valve probability is a parameter. |
| **L10** | **PSV trim.** Block valves locked or car-sealed open, identified as full-port; "Provide a drain valve or a plugged drain between the block and PSV"; show size, orifice, set pressure. | HNF 3.2.4.3 | [verified] | `pattern` (H1) |
| **L11** | **PSV location on vessels.** "Safety Relief valves generally located on the top outlet line downstream of the vessel blinding location or directly connected to the vessel". | KLM "Minimum information", vessels, important notes | [verified] | `pattern` (H1) |
| **L12** | **Thermal relief.** For liquid-filled lines blockable at both ends, provide one "if the pressure can build up to 1.5 times the design pressure". "All coolers using water will have a thermal relief valve on the cooling water return line between the cooler and the block valve." | HNF 3.2.4.4 | [verified] | Cooler part: `pattern` (H1). The 1.5x part is `not-encodable` in a topology-only generator: it needs design-pressure data the graph does not carry. |
| **L13** | **Vessel and column drains and vents. Sources conflict.** KLM: "A valved drain for all columns and vessels shall be indicated" (location rule given); "valved vent with blind flange" on top; utility connections shown; one local PI on top; one local TI on the top outlet line. HNF: "High point vents and drains are shown only when they connect to a closed system or are required for process and safety reasons." | KLM vessels notes; HNF 3.2.5.2 | [verified] | `pattern` (H1) with a **convention parameter**: show all vents/drains (KLM) vs closed-system only (HNF) |
| **L14** | **Valves directly on a nozzle are drawn with no pipe between.** | HNF 3.2.3.4 | [verified] | `pattern` (H1): valve adjacent to nozzle, no segment |
| **L15** | **Heat exchangers.** KLM: shell and channel piping with a valved vent and drain connection unless venting/draining via piping; bypass provision when maintenance is done with the unit operating. HNF: steam-heated reboilers get pressure indication on steam and condensate. | KLM exchangers; HNF 3.2.3.6 | [verified] | `pattern` (H1) |
| **L16** | **Compressors.** KLM: suction and discharge valves, suction strainer and discharge check valve, safety/relief valves, pulsation dampeners where required. HNF: "show auxiliary systems such as lube oil and seal oil systems on a separate auxiliary P&ID". | KLM p. 19; HNF 3.2.3.8 | [verified] | `pattern` (H1); the auxiliary part is `splitter` (S14) |
| **L17** | **Instrument identification.** Tag = function letters "based on ISA S5.1" + a loop number whose "numbering system is company specific"; "the abbreviation + loop number must be unique for each device" (CHE3). Up to 5 letters (measured variable, modifier, readout, output, function modifier); "FIC045 ... The same loop may have FT045" (W-PID). HNF: "Provide unique identification to all instruments". KLM: "The instrument tag number for each instrument"; isolation (primary connection) valves shown. ISO: PCE requests per IEC 62424 with letter codes. | CHE3; W-PID; HNF 3.2.4.1; KLM p. 22; ISO10628 4.4.2 f) | [verified]; ISA-5.1 and IEC 62424 texts [not-read] | `pattern` (loop template, H1); `constraint` (post-check: tag uniqueness) |
| **L18** | **Loop composition.** No source read states "sensor, transmitter, controller, final element" as a rule. DEXPI's reference P&ID encodes loops structurally: `InstrumentationLoopFunction` 4, `ProcessInstrumentationFunction` 4, `ProcessSignalGeneratingFunction` 3, `SignalConveyingFunction` 3, `ActuatingFunction` 3, `ActuatingSystem` 3, `ControlledActuator` 3, `OperatedValveReference` 3 (counts from C01 XML). | DXT C01; W-PID example | canonical chain as a rule: [recalled]; DEXPI structure: [verified] | `pattern` (H1): take the loop template from DEXPI C01 / the I-series examples (section 7) |
| **L19** | **Complex shutdown logic lives off the P&ID.** KLM: shown as a "black box" referring to a logic diagram "on a separate sheet". HNF: "show a logic table ... or show it on a separate P&ID, or logic diagram". | KLM p. 22 item 17; HNF 3.2.4.1 | [verified] | `not-encodable` in the plant graph (off-graph document); at most a reference node (`splitter`) |
| **L20** | **Specification break means a new line number.** "Clearly indicate where a line specification change occurs. This will be cause for a new line number." The same holds at safety-class limits; AG/UG breaks are marked. | HNF 3.2.5.1 | [verified] | `constraint` (H3 emits line numbers; post-check verifies a number change at every class change) |

---

## 3. Level 2: connection rules (between arrangements)

| ID | Rule | Source | Tag | Verdict / hook |
|---|---|---|---|---|
| **C1** | **Direction is intrinsic.** "Flow routes and flow directions shall be indicated by lines and arrows." Main flow direction: "from left to right and from top to bottom". | ISO10628 4.1, 5.3.3.1 | [verified] | Already encoded (H2, in to out only). Left-to-right placement is `not-encodable` in a graph (rendering). |
| **C2** | **The shipped connection rule is type-only.** `BasicPipingInConnector.assess_valid_counterpart` returns `isinstance(counterpart, BasicPipingOutConnector)`, and symmetrically. `GraphConnector` requires the same class and an opposite `is_inlet`. There is **no fluid, service or pressure-class compatibility.** | PYD `dexpi_pattern.py`, `graph_pattern.py` | [verified] | Every further connection rule needs a `Connector` subclass (H2) that carries service or class in `kwinfos` |
| **C3** | **Every line has a line number.** "Each process line and each utility line is identified by a line number." ISO minimum content includes "the pipeline number, piping class, or designations". | HNF 3.2.5.2; ISO10628 4.4.2 d) | [verified] | `constraint` (H3 attribute + post-check) |
| **C4** | **Utilities connect as stubs, not as through-lines.** HNF: utility lines "originate and terminate adjacent to the equipment"; only the length needed "for valving, instrumentation, and line numbering is shown"; origin and terminus "by descriptive title only"; "Main utility headers are not shown on the unit P&ID; they are shown on the utility P&ID for that process area." KLM: utility lines end "at a box indicating the relevant utility service abbreviation (e.g., CWS, CWR, IA, etc.)", plus a "Utilities Identification Table" with reference drawings. ISO: a utility flow diagram shows process equipment "by boxes with inscriptions and with utility connections"; auxiliary system lines are dashed with the energy-carrier type "and, if possible, the drawing number". | HNF 3.2.5.2; KLM p. 12 item 7; ISO10628 4.3.1, 5.3.5 | [verified] | `constraint`: H2 (a utility connector type distinct from process connectors), H4 (cap consumer utility connectors with service-labelled stubs), H3 (generate utility headers as their own patterns). `splitter`: utility sheets (see section 8). |
| **C5** | **Connections to other units are labelled differently.** KLM: lines to/from other Units end "at the bottom of the drawing" in a box with line service, "Source or destination Unit name and number", and the connecting drawing number with coordinates. HNF: outside the unit boundary, "use a general name and associated equipment number". | KLM p. 11-12 item 6; HNF 3.2.5.1 | [verified] | `constraint` (H3: plant-level unit graph). `splitter`: the label grammar depends on whether the cut is same-unit or cross-unit. |
| **C6** | **Auxiliary systems are referenced, not drawn inline.** ISO: "Auxiliary systems can be represented by rectangular frames with references to separate flow diagrams." KLM repeats this. HNF: compressor utility piping goes on a compressor auxiliary P&ID unless minor. | ISO10628 4.4.1; KLM p. 6; HNF 3.2.5.2 | [verified] | `constraint` (H3: sub-model) + `splitter` (auxiliary sheet) |
| **C7** | **Signals are not pipes.** ISO gives control and data-transmission lines their own width class. KLM: "Instrument, control system and software linkage signals from sheet to sheet shall be terminated ... at a box indicating the continuation instrument number, location, and drawing number". PIP PIC001 reportedly uses the off-page connector "in accordance with Appendix A-3" for signal continuation (**search snippet only, [not-read]**). pyDEXPI has `GraphBasicSignalConnector` for graph patterns, but `DexpiPattern` accepts only `(BasicPipingInConnector, BasicPipingOutConnector)`. | ISO10628 5.3.1 c); KLM p. 12 item 8; PYD | [verified] except PIP | `constraint` (H2: a DEXPI signal connector would have to be written) + `splitter` (signal connector type) |
| **C8** | **Vendor packages carry a boundary.** Packaged equipment is enclosed "by a dashed line or cloud ... with arrows showing specific junctures of piping between the Contractor and the Supplier". | HNF 3.2.5.2, 3.2.3.10 | [verified] | `pattern` attribute. Low priority for retrieval. |
| **C9** | **Forbidden connections: none found codified.** No source read gives a list of what must never be connected. HNF gives one rating rule (L7). Toghraei's preface says ch. 17 covers "precautions should be taken when tying together different process elements"; content [not-read]. 2502.18493 shows rule examples (missing check valve after a pump, redundant isolation valves, pressure instrument on the wrong side, crossing without a junction) but only 5 of 33 rules. | TOG preface; `2502.18493.md` | [verified] absence in sources read; [verified, prior note] for 2502.18493 | **Gap.** The post-check formalism exists; the rule content is not public. |
| **C10** | **Stream identity across sheets (PFD).** "Identical numbers and descriptions should be maintained on any stream shown on more than one sheet." | HNF 3.1.2.3 (PFD) | [verified] | `splitter`: connector labels carry the line or stream number (OPEN100 does, see S5) |
| **C11** | **Designations must be consistent across documents.** "Designations must match the equipment list, equipment datasheets, and P&IDs"; titles "identical to those on the equipment list". | HNF 3.1.2.2, 3.2.3.3 | [verified] | `constraint` (post-check). Consequence for the benchmark: messy cross-sheet tags (`RC-P102A` vs `RCS-PU-102A`, OPEN100) are **rule violations** that happen in practice, not a convention. |

---

## 4. Level 3: sheet-level rules (the level that feeds the splitter)

| ID | Rule | Source | Tag | Verdict |
|---|---|---|---|---|
| **S1** | **Continuations are mutual and aligned.** In- and outgoing flows, including those continuing on other diagrams, are marked with arrows. "If a diagram consists of several sheets, it is recommended that lines ... continue at the same level when the individual sheets are placed next to one another horizontally". "When a connection line continues to another diagram the end should be mutually referenced. The reference should consist of a designation". KLM repeats the same-level recommendation. | ISO10628 5.3.3.2; KLM p. 9 item 6 | [verified] | `splitter`. Consistent with the existing `ConnectorPair` invariant. |
| **S2** | **Connector label fields, US DOE practice.** "Clearly identify all lines entering and leaving the diagram, starting in order as follows: Conveyed Fluid; Source / Destination; Drawing Number sheet and Zone". Source/destination is the equipment number within the same unit or system, and "a general name and associated equipment number" outside it. The PFD version adds equipment name. | HNF 3.2.5.1, 3.1.2.5 | [verified] | `splitter` (label grammar: fluid, source/destination, drawing, sheet, zone) |
| **S3** | **Connector label fields, KLM practice.** Identification box: "The line service", "The origin or destination equipment item number", "Continuation drawing number with the relevant coordinates". | KLM p. 11 item 5 | [verified] | `splitter` |
| **S4** | **DEXPI label slots are defined but empty in the reference file.** `PipeOffPageConnectorReferenceByNumber(referencedDrawingNumber, referencedConnectorNumber)` and an object reference exist (**[verified, prior note]** `ontology-landscape.md`). In DEXPI's own reference P&ID (C01V04-VER.EX01.xml), the `FlowInPipeOffPageConnector` and `FlowOutPipeOffPageConnector` elements carry **no reference child at all**: only connection points, nodes and scale (parsed today). | DXT C01 | [verified] | `splitter` (output mapping). Even the reference example does not fill the cross-drawing slot. |
| **S5** | **Two real label conventions are now in hand (observations, not rules).** *OPEN100* (nuclear): incoming `PID 120-1 (C-1)` + sending system code; outgoing system name + `RCS-PID-100-2`; grid only on incoming; line number beside the pipe (**[verified, prior note]** `Notes/pid-lapkozi-csatlakozok.md`). *Covestro C08* (chemical, SmartPlant, 2020, CC BY 4.0): label = German service text (e.g. "Kühlwasser-Rücklauf", "Zur Abluftreinigung") + partner-unit-prefixed code + a three-digit number + partner drawing number, e.g. `LA01-WA112 276` / `UER-2345678`. Drawing UER-1234567 carries **15** such labels (numbers 274-288) naming UER-2345678. UER-2345678 carries **2** naming UER-1234567 (numbers 280, 281). So 13 of the 15 references have no counterpart label on the partner drawing in this two-drawing example. Pairing geometry was **not** checked visually; this is text extraction only. | OBS; DXT C08V01 PDFs | [verified] as extracted text | `splitter` (label-grammar variants from two drawing cultures). Calibrate on neither (ADR-0007); use them as containment points. |
| **S6** | **Connector side follows drawing order.** Process lines to/from other drawings in the Unit "shall be terminated at the left-hand or right-hand side"; "Lines from/to higher number drawings shall enter and leave the drawing on the right-hand end and vice versa." Lines to other Units go to the bottom. | KLM p. 11 items 4, 6 | [verified] | `splitter` (connector side derived from sheet order). **Implies drawing numbers ascend with flow.** |
| **S7** | **Flow continues from sheet to sheet.** "The process should read from left to right across the page; that is, feed stock should enter on the left and product should exit on the right. There should be continuity of the process stream flow from sheet to sheet." Before drafting: "Locate line continuations for adjacent drawings." | HNF 3.2.2, 3.2.3.1 | [verified] | `splitter`: supports ordering sheets along flow (`flow_greedy`) |
| **S8** | **Density: qualitative only, no number.** P&ID: "The final drawing should have an appearance of uniform density ... an inordinate amount of information is not incorporated into a confined area." PFD: "Do not crowd the diagram. Limit the number of equipment items on a drawing so that adequate space remains for future revisions." KLM: drafting legible "when the drawing is reduced to an A3 size sheet". **No source gives an item count per sheet.** | HNF 3.2.2, 3.1.2.2; KLM p. 7 | [verified] | `splitter`: the sheet budget stays a swept parameter with **no sourced value** |
| **S9** | **Sheet size varies by source.** ISO: A1 "should preferably be used"; long sizes and sizes above A1 "are to be avoided". KLM: A0; A1 "may be used for simple P&IDs and UDFDs as per Company's approval". TOG: a company standard size "could be D size (in American system) or A1 in ISO system"; paper size "is different for each company". DEXPI C01 MetaData: `SheetFormat` "DIN A3". Covestro: `A1.PID`. | ISO10628 5.1.1; KLM p. 7; TOG 1.3; DXT | [verified] | `not-encodable` in the graph (rendering). Relevant only as a density proxy. |
| **S10** | **Grid and index.** HNF requires the zone in the label (S2). KLM "Equipment Location Index": each drawing divided into 50 mm intervals, "numbers from 1 to 23 in length and alphabets from "A" to "P" in width"; an "Item Index" in the upper right of each diagram; and **"In a separate sheet apart from P&IDs, an "Item Index" shall be prepared to summarize all equipment of the Unit/Plant with reference P&IDs and equipment location."** OPEN100 grid A-H / 1-12 (**[verified, prior note]**). Covestro border: letters A-L, numbers 1-16 (text extraction). | KLM p. 11; HNF 3.2.5.1; OBS; DXT | [verified] | `splitter`: grid presence and dimensions are convention parameters. The Item Index is the **codified cross-sheet equipment lookup**, and the splitter could emit it as an artefact. |
| **S11** | **Legend (lead) sheets.** "Each symbol on a P&ID shall be traceable to a legend. P&ID drawings must have a legend on the drawing or they must reference a legend drawing". Symbol meanings are "defined on separate drawings called "Lead Sheets" (or Legend Sheets)". TOG: the reference drawing block lists drawings to study first; "Typical reference drawings are legend sheets and auxiliary P&IDs", and legend drawings "are the most important reference drawings". | HNF 3.2.3.2; CHE3; TOG 3.3 | [verified] | `splitter` (optional legend-sheet node referenced by every sheet). `not-encodable` in the plant graph itself. |
| **S12** | **Title block and sheet metadata.** ISO 7200 title block "shall be used". TOG: title block carries drawing type, "sheet name, number, and revision"; name by content; "never ever include the equipment number in the P&ID name". DEXPI MetaData: `DrawingNumber`, `SheetNumber`, `TotalNumberOfSheets`, `ReplacedDrawing` (C01 values "123/A93", "2a", 4). | ISO10628 5.1.2; TOG 3.1; DXT C01 | [verified] | `splitter` (manifest sheet metadata; sheet names from content, not tags) |
| **S13** | **Utility sheets are a sheet type.** Headers go on "the utility P&ID for that process area" (HNF). KLM: the UDFD "is a special type of a P&ID which represents the utility systems". ISO: the UFD is "a special type of process flow diagram". TOG: "utility distribution P&IDs, are shown as schematics but in plan view"; ch. 17 separates utility generation from "distribution of utilities and the collection of used utilities". | HNF 3.2.5.2; KLM p. 6; ISO10628 4.3.1; TOG 1.2, preface | [verified] | `splitter` (see the contradiction in section 8) |
| **S14** | **Auxiliary P&IDs** (lube and seal oil, compressor utilities) are separate drawings. | HNF 3.2.3.8, 3.2.5.2; ISO10628 4.4.1 | [verified] | `splitter` (reference sheets distinct from utilities) |
| **S15** | **Sheets persist; numbering gets gaps.** "It is strongly recommended that a P&ID is never removed for minor reasons like moving the content to other P&ID sheets"; removed sheets are marked void or obsolete. KKS: once set, counts "dürfen ... nicht mehr geändert werden". | TOG 3.1; W-KKS | [verified] | `not-encodable` (lifecycle). It explains numbering gaps and absent sheets, so "numbering gaps" is a `splitter` parameter. |
| **S16** | **Partition principle: no rule found.** No source read says whether a P&ID set is split per unit, per system or per equipment count. Evidence only: PFD frames "grouped into logical subsystems; for example, reaction and product recovery" (HNF, **PFD**); DEXPI MetaData attaches a drawing to area, section, system, train and unit (P5); Covestro drawing title "Reaktion Str.1 Teil 2 (Musterfließbild)", i.e. reaction train 1, part 2; OPEN100 is split per system (prior note). | HNF 3.1.2.2; DXT; OBS | evidence [verified]; rule not found | `splitter`: the rule-grounded form is a label-based `by_unit` / `by_system` strategy on generator-emitted hierarchy codes (P5) |
| **S17** | **Complex logic on a separate sheet** (see L19). | KLM; HNF | [verified] | `splitter` / off-graph |

---

## 5. Level 4: plant-level rules

| ID | Rule | Source | Tag | Verdict |
|---|---|---|---|---|
| **P1** | Designation of objects in diagrams "could be performed using reference designation according to IEC 81346 series". | ISO10628 4.1 | [verified] | `constraint` (H3 tag grammar) |
| **P2** | **IEC/ISO 81346.** Parts: 81346-1 basic rules (2022), -2 classification (2019), -10 RDS-PS power supply (2022), -12 RDS-CW construction works (2018), -14 **RDS-MS "Manufacturing and Processing Systems"** at FDIS stage. Aspects `=` function, `-` product, `+` location, as used by IMF (**[verified, prior note]** `ontology-landscape.md`). The standard text itself [not-read]. | W-81346; prior note | [verified] (secondary) | `constraint` (H3 tag grammar variant) |
| **P3** | **KKS.** 15-17 characters; 3 designation types (process-related, point of installation, location); levels 0 total plant (`A` or `N`), 1 function `(N)AAANN`, 2 equipment unit `AANNN(A)`, 3 equipment `AANN`. Example `1 2LAC03 CT002 QT12` = unit 1, third feedwater pump set in the 2nd water-steam cycle, 2nd temperature measurement, 12th thermowell. Counting: "Die Zählrichtung entspricht in der Regel der Fließrichtung der Stoffströme". The process-related designation requires a P&ID basis ("auf Basis eines RI-Fließbildes erforderlich"). Successor RDS-PP (2007), based on IEC/EN 81346 and ISO 16952; document codes per EN 61355. Primary VGB-S-811-01 [not-read]. | W-KKS | [verified] (secondary) | `constraint` (H3 tag grammar; counting along flow). `splitter` (tag format variants for identity tests). |
| **P4** | **OPEN100 does not use KKS syntax.** It uses 2-4 letter system codes (RCS, CND, FWS …) and drawing numbers `PID 100` … (**[verified, prior note]** `Notes/open100-rendszerkodok.md`). The one real multi-sheet set in the project follows neither KKS nor 81346 syntax. | OBS | [verified, prior note] | Relevant to the brief's KKS premise |
| **P5** | **DEXPI's plant-hierarchy slots.** The C01 MetaData carries identification codes and names for Enterprise, Site, IndustrialComplex, ProcessPlant, PlantArea (with an ISA-95 name), PlantSection (value "Utilities"), PlantSystem, PlantTrain, ProcessCell, Unit (with an ISA-95 name). ISA-95 itself [not-read]. | DXT C01 | [verified] | `constraint` (H3: every generated drawing gets hierarchy codes) + `splitter` (`by_unit` partition; cross-unit label content, C5) |
| **P6** | **KLM's "Unit"**: "one or all process, offsite and/or utility Units and facilities as applicable to form a complete operable oil, gas and/or petrochemical plant". The Item Index is per Unit/Plant (S10). | KLM p. 5 | [verified] | `constraint` (H3) |
| **P7** | **Covestro plant codes.** Title blocks `COVPIL1-V999-TA99` (UER-1234567) and `COVPIL1-V999-LA01` (UER-2345678). Cross-unit line numbers carry the partner unit prefix (`LA01-LR045.10000-25-10H1200 NV 221`). Title-block fields: Industrial Complex, Site, PlantBuilding, Process Area, Subprocess, Technical Equipment, AKZ. Instrument tags like `PI P0020`, `LIC L0012`. | DXT C08V01 | [verified] (text extraction) | `constraint` (H3 tag grammar variant) |
| **P8** | **Tags tie to units or equipment by company convention.** HNF Fig. A-2 legend (OCR, partly garbled): instruments in area "123W" carry "123W as middle part of tag number". CHE3: loop numbering is company-specific; the author bases loop numbers "off the associated major equipment. That's just me". | HNF Fig. A-2; CHE3 | [verified]; HNF figure text only partly legible | Generator parameter. **No universal rule.** |

---

## 6. What research and tooling already exist for generation and checking

### 6.1 pyDEXPI synthetic generation (verified in source and data)

**Mechanism** (verbatim from `master`):
- README: generation "is based on the aggregation of P&ID module templates (or patterns)". The provided `RandomGeneratorFunction` "selects P&ID modules at random". The demo loads `./data/dexpi_sample_patterns`.
- `GeneratorFunction` docstring: "A recycle can be produced by returning two connectors of the current pattern and no next pattern."
- `RandomGeneratorFunction`: "selects next patterns and connectors fully at random". `p_connect_internal: float = 0.0` is the default recycle probability.
- `CappingFunction`: "Default implementation is to cap all connectors with a default capping step." A capping distribution must have exactly one connector label.
- `DexpiPattern` incorporation calls `mt.import_model_contents_into_model(...)`, so the aggregate is **one `DexpiModel`**. That is one drawing in DEXPI terms (`ontology-landscape.md`).
- The ESCAPE35 pyDEXPI paper (LAPSE:2025.0371, CC BY-SA 4.0, 6 pp): its full text contains **no passage** on synthetic generation, patterns or their provenance (grep today). **Who made the sample patterns, and from what knowledge, is documented nowhere I could find.**

**Sample-pattern inventory.** `data/dexpi_sample_patterns/` holds 10 distributions and 23 pickles. It was read with a stub unpickler that never imports a real class, so no pickle code ran.

| Distribution | Connectors (JSON) | Patterns (probability) | Contents (DEXPI classes, counted) |
|---|---|---|---|
| feed | `Main_out` | feed_pattern (1.0) | Vessel 1, OperatedValve 1 |
| product | `Main_in` | product_pattern (1.0) | Vessel 1, OperatedValve 1 |
| pump | `Main_out`, `Main_in` | 1, 2, 3 (1/3 each) | p1: Pump, Mixer, PipeTee, OperatedValve 1 each; topologically a valved line from a discharge tee back to a mixer on the suction side (intent not documented). p2: Pump + 1 OperatedValve on the outlet. **p3: bare Pump.** |
| compressor | both | 1, 2 (0.5 each) | c1: bare Compressor. c2: Compressor, HeatExchanger, Mixer, PipeTee, 2 OperatedValve. |
| hxer | both | 1-4 (0.25 each) | h1: bare Heater. h2, h4: HeatExchanger + 1 OperatedValve. h3: HeatExchanger, Mixer, PipeTee, OperatedValve. |
| mixer | both | 1, 2 (0.5 each) | Mixer + 2 or 1 OperatedValve |
| reactor | both | 1, 2, 3, 4, 6 (0.2 each) | Vessel + 1-3 OperatedValve; 3/4/6 add Mixer + PipeTee |
| reactor_feed | both | 1, 2 (0.5 each) | r1: OperatedValve only. r2: Mixer + OperatedValve. |
| storage | both | 1, 2 (0.5 each) | Vessel + 1 OperatedValve |
| column | both | column_pattern_1 (1.0) | ProcessColumn 1, HeatExchanger 3, Tank 1, OperatedValve 7, PipeTee 2 |

**Across all 23 patterns: zero instrumentation objects, zero check valves, zero typed valves** (only the generic `OperatedValve`), and no block/bypass station. **None of L1-L18 is encoded.**

**Derived consequence (reasoned from the verified JSON and code, not executed).** Every non-terminal pattern has exactly one `Main_in` and one `Main_out`; `feed` has only an out-connector and `product` only an in-connector. Adding a pattern therefore consumes one open connector and adds at most one. An internal connection consumes two. The number of open connectors never increases, so **inter-pattern topology is a single path, optionally closed into one ring, capped by feed/product**. Branching exists only inside a pattern. With the sample set:
- `utility_aware` has no utilities to find.
- `modularity` on a path degenerates to contiguous chunks, which is close to `flow_greedy`.

**Branching needs patterns with more outlets than inlets, or a custom H3.** Verify with one run before relying on this.

### 6.2 Pattern-based P&ID/PFD generation in the Schweidtmann group (HIRT)

*Claim:* data-driven control-structure prediction, pre-trained on generated P&IDs.

*Method (verified, section 3.1):* "we create P&ID patterns of sub-processes, such as thermal separation or reaction", added together via "a first-order Markov chain-like sampling process with fixed probabilities". Control structures are added "based on several basic design heuristics (inspired by [1, 37])" (references not resolved). Details: "up to three feed streams"; "one of six stored reactor patterns with an optional material recycle stream"; patterns "have several outlet streams" (hence branching); branches terminate at conditioning or above 65 nodes; duplicates and graphs over 100 nodes deleted. The design heuristics themselves are **not listed** in the section read.

*Evaluation setup (verified, Table 1):*
- Generated data: 100 / 1,000 / 10,000 / 100,000 training, 1,000 validation, 1,000 test. Nodes 52 ± 20, vocabulary 113.
- Real data: 312 "P&ID-like images from publicly available sources", split 250 / 31 / 31, manually corrected. Nodes 37 ± 28, vocabulary 390.
- Ground truth: by construction for generated data; hand-corrected digitization for real data.
- Number of runs: not stated in the section read.
- Reported: "top-5 accuracy of 74.8% on 10,000 generated P&IDs and 89.2% on 100,000 generated P&IDs".

*Claims vs demonstrated:* the heuristics are asserted, not enumerated. The generated corpus is measurably narrower than real data (vocabulary 113 vs 390; node standard deviation 20 vs 28). *Relevance:* the closest published precedent for pattern + Markov generation. It shows a generator needs multi-outlet patterns to branch. Code and pattern availability were **not checked**.

### 6.3 SynthPID (arXiv 2604.16513v1, Prasad & Mahapatra, IIT Bombay, 15 Apr 2026)

*Claim:* synthetic P&IDs seeded from real topology train a digitizer that reaches 63.8 ± 3.1% edge mAP on OPEN100 "without seeing a single real P&ID during training".

*Method:* it perturbs node positions "while its adjacency is preserved", swaps symbol templates within a class, re-routes with Manhattan routing, and filters with Weisfeiler-Lehman and perceptual hashing. "Running this process against all 12 seeds over roughly 12,000 total attempts, we accept 665 images." **It codifies no structural rule at any level.** Topology is copied from seeds, not generated from rules.

*Evaluation setup (verified):* evaluation on PID2Graph OPEN100, 12 images (57-210 components and 28-118 edges after connector collapsing). 5-fold cross-validation × 3 seeds = 15 runs per configuration. E1 oracle trains on "up to 10 real annotated P&IDs per fold". Ground truth = PID2Graph annotations. Results: E2 63.8%, E1 69.4%, modular baseline 45.9%, E3 72.6%; the template-based reference is ~33% (Stürmer appendix A5, 2,000 images). Gains flatten beyond ~400 images ("only a 5-pp gain between 400 and 665").

*Claims vs demonstrated:*
- The training set is "generated from those same 12 images as seeds". In the sections read, the paper does not say that the seeds of a test fold are excluded from E2's training data. As written, **the evaluation images are also the topology seeds**, so "without seeing a single real P&ID" holds for pixels, not for topology.
- "Real P&IDs have a heavy-tailed degree distribution ... high-degree junctions at vessel inlets, valve groups on main headers, instrument clusters around critical equipment" is asserted; it is demonstrated only as degree histograms over the same 12 sheets.
- Its own limitation: "OPEN100 covers a single reactor configuration".
- The code release is claimed, but `github.com/LatentSpaceIITB/SynthPID` returned Not Found via the GitHub API today. A search result lists the paper at CVPR 2026 Workshops (AI4RWC) **[not-read]**.

*Relevance:* adjacent, single-sheet digitization. **It is off-limits as a generator for this project:** it is seeded on OPEN100, which ADR-0007 holds out for validation. It is useful as independent evidence that topology realism, not visual realism, is what synthetic P&ID data lacks.

### 6.4 Not read

- **Oeing et al. 2022**, *Digital Chemical Engineering* 4:100038 (RNN next-equipment prediction and GNN consistency checks on DEXPI data; open access, CC BY): **[not-read]**, 403.
- **Ma et al. 2026**, "Artificial intelligence for piping and instrumentation diagrams: a review and perspective" (published 2026-06-25, closed access): **[not-read]**.
- **Hexagon Smart P&ID** consistency checking and rule manager: public documentation not reachable, **[not-read]**. No published rule list found.
- **AVEVA**: not searched to exhaustion. Nothing found.
- For the rule-graph formalism and its 33 rules (5 shown), see `2502.18493.md`.

---

## 7. Pattern libraries found, and licences

| Library | What it holds | Licence | Usable for rule-grounded patterns? |
|---|---|---|---|
| **pyDEXPI `data/dexpi_sample_patterns/`** (GitHub `master`; not in the pip package, per the coordinator) | 10 distributions, 23 pickled patterns (table in 6.1) | **AGPL-3.0** (repo licence; no separate licence file under `data/` in the tree listing) | **Format yes, content no.** No verified rule is encoded. Pickles can execute code when loaded normally **[recalled]** (general Python behaviour, not re-read today), so pin a commit before loading. Provenance undocumented. |
| **DEXPI TrainingTestCases** (`gitlab.com/dexpi/TrainingTestCases`, "Lots of example PIDs, many with DEXPI reference solutions and vendor uploads", last activity 2025-07-11) | DEXPI 1.2 and 1.3 folders: E-series equipment (E01-E14), **I-series instrumentation (I01-I15: measurement, control, flow ratio, alarms)**, P-series piping (P01-P04, including "Pipe From OPC to Nozzle"), C-series complete examples (C01 DEXPI reference P&ID, C02 BASF column, C03 Equinor piping, C05 pump/tank/control loop, **C08 Covestro "Two connected P&IDs"**). At least 123 XML files in the first 500 tree entries scanned. | **CC BY 4.0** | **Best available source for loop and equipment templates** (I-series, C01 loop structure, L18). Needs conversion to `DexpiPattern` with pyDEXPI's Proteus loader (not tried). C01's centrifugal pump has **no** valves on suction or discharge (parsed), so it is **not** an exemplar of L1-L3. C08 has **no DEXPI XML**, only 2 PDFs and Excel lists, but it is the only public, licence-clear two-drawing example with real connector labels (S5). |
| **PID2Graph** (known) | 762 sheet graphs, no semantics | CC BY-SA 4.0 | No (ADR-0007) |
| **SynthPID** | 665 perturbed OPEN100 topologies (claimed) | code repo not found | No: seeded on the hold-out set |
| **HIRT / Vogel et al. generator** | SFILES-level sub-process patterns with control heuristics | not checked | Unknown. Check repository availability. |
| **Codified trim libraries (PIP, company standards)** | **None found in machine-readable form.** | none | Gap |

---

## 8. What this means for the existing splitter strategies

**Rules that support the current design:**
- **Sheet order follows flow.** HNF 3.2.2 ("continuity ... from sheet to sheet"), KLM item 4 (higher-numbered drawings on the right), ISO 5.3.3.2 (sheets align side by side), KKS counting along flow direction. `flow_greedy`'s ordering is rule-grounded.
- **Trim rides with its equipment.** L1-L16 place valves, strainers, gauges and PSVs as local arrangements of one equipment item (HNF 3.2.3.4: valves directly on nozzles). `_cluster_owners` assigning non-equipment nodes to the nearest equipment matches this.
- **Every cut has a mutual reference** (ISO 5.3.3.2), which is the `ConnectorPair` invariant.
- **Direction is required** (C1), consistent with ADR-0007's precondition.

**Rules that contradict or undercut how the strategies cut:**

1. **`utility_aware` moves the wrong thing. This is a contradiction.** `_detect_hubs` flags *equipment* clusters whose degree exceeds mean + one standard deviation and puts them on hub sheets. The codified practice (C4, S13) is the reverse: the **headers** go on the utility P&ID for the process area, and **consumer equipment stays on its unit sheet** with a short utility stub labelled by service ("descriptive title only"; "box indicating the relevant utility service abbreviation"). A utility crossing is also **not a pairwise connector**. It is a one-to-many service reference ("Utilities Identification Table" with reference drawings). The current model (`partner_sheet_id`, `partner_tag`) cannot express that. With the pyDEXPI sample patterns there are no utilities at all, so the strategy's hubs would be high-degree **process** equipment.

2. **Connector labels lack codified fields.** `OffPageConnector` = `tag, sheet_id, direction, partner_sheet_id, partner_tag, attached_node_id`. All codified sources require more:
   - conveyed fluid or line service (HNF, KLM);
   - source/destination equipment number, or unit name and number for cross-unit lines (HNF, KLM);
   - drawing and sheet, plus zone or coordinates (HNF, KLM).
   Real sets add the line number (OPEN100) or a connector number (Covestro, DEXPI `referencedConnectorNumber`). `splitter.md` §3 already makes label grammar a parameter; these fields are what the grammar must be able to emit.

3. **No same-unit vs cross-unit distinction, and no signal vs piping distinction.** KLM (items 4-6, 8) and HNF (3.2.5.1) label and place these three crossing types differently. DEXPI has separate signal off-page connector classes (prior note). A cut instrument signal currently becomes the same generic connector as a cut pipe.

4. **The sheet budget has no source.** `splitter.md` §3 says "roughly 5-15 major equipment items per sheet". **No source read gives any number** (S8), and no fetchable source gave one. The line should be marked unsourced. The budget is legitimately a swept variable, not a calibrated constant.

5. **`modularity` as "by process unit" is a proxy, not the rule.** Sources attach drawings to *declared* units, trains and systems (P5, P6, S16; Covestro "Reaktion Str.1 Teil 2"; OPEN100 per system). A unit is a design label, not a graph community. The rule-grounded strategy partitions on generator-emitted unit or system codes; Louvain is a fallback when those codes do not exist.

6. **The `IdentityGroup` duplication has no codified basis.** No source read says to draw one equipment item on several sheets. The codified cross-sheet equipment mechanisms are the **equipment number inside the connector label** (HNF 3.2.5.1, KLM item 5b) and the **Item Index** sheet (KLM, S10). OPEN100 shows real duplicates (prior notes), so the mechanism is observation-grounded. The sentence "which is how real drawings do it" in `splitter.md` open question 3 is supported by OPEN100, not by a rule. HNF C11 also means messy tag variants are rule **violations**.

7. **The pyDEXPI sample set makes three strategies nearly indistinguishable** (6.1 derived consequence). On a chain, `flow_greedy` ≈ `modularity` and `utility_aware` finds nothing. Only `random` differs. The strategy comparison planned in `splitter.md` §3 needs a generator that produces branching, utilities and units first.

---

## 9. Gaps: what no source read codifies

1. **How many items fit on a P&ID sheet.** Qualitative only (S8).
2. **How a plant is partitioned into sheets** (per unit, system, train or count). Evidence only (S16).
3. **When optional trim is required**: minimum-flow lines (L6), warm-up bypasses (L7, the condition is in KLM 8.1.4, [not-read]), control-valve bypass exceptions ("in general", L9).
4. **Forbidden connections** (C9).
5. **Drawing-number schemes**: every source treats them as company-specific. KLM item 4 only implies ascending along flow.
6. **Drawing the same equipment on several sheets** (section 8, item 6).
7. **A machine-readable, licence-clear library of rule-conformant trim patterns** (section 7).
8. **PIP PIC001 itself.** No legitimate full text reachable. HNF is a proxy, not a substitute.

---

## 10. Where sources disagree (make these parameters, not constants)

| Topic | Positions |
|---|---|
| Vents and drains | all vessels get valved drain and vent (KLM) vs shown only for closed system or process/safety reasons (HNF) |
| Sheet size | A1 preferred (ISO) · A0, A1 for simple ones (KLM) · D or A1 by company (TOG) · DIN A3 (DEXPI C01) · A1 (Covestro) |
| Label content | fluid + source/destination + drawing/sheet + zone (HNF) · service + equipment + drawing + coordinates (KLM) · drawing + connector number (DEXPI) · drawing-sheet + grid + system code, line number beside (OPEN100) · service text + unit-prefixed code + number + drawing (Covestro) |
| Grid | 1-23 × A-P at 50 mm (KLM) · A-H × 1-12 (OPEN100) · A-L × 1-16 (Covestro) · zone required, format unstated (HNF) |
| Tag structure | KKS levels · IEC 81346 aspects · system-code-led (OPEN100) · unit-prefixed (Covestro) · ISA letters + company loop numbers (CHE3) |
| Spares on the drawing | P&ID shows installed spares (ISO) · PFD shows one of identical trains (HNF, PFD only) |

---

## 11. Follow-ups

- [ ] Run pyDEXPI generation once with the sample patterns and confirm the chain-or-ring topology (6.1). One run, no code change.
- [ ] Load one DEXPI I-series example and one C-series example with pyDEXPI's Proteus loader and check whether they convert to `DexpiPattern`s. This decides whether CC BY 4.0 templates can replace the AGPL sample set for loops.
- [ ] Obtain PIP PIC001 through the university library, not online copies, and re-tag S2/S3/C7 against it.
- [ ] Check whether the Vogel/HIRT SFILES generator and patterns are public (6.2).
- [ ] `/paper-intake 2604.16513` (SynthPID) and a novelty-log entry. It is adjacent, not threatening, but it uses OPEN100.
- [ ] Mark "roughly 5-15 major equipment items per sheet" in `splitter.md` §3 as unsourced (architect's call; this note does not edit design docs).
