# Real / realistic P&ID data sweep, 2026-10-22

Question: what real or realistic P&ID material is publicly downloadable, to test our DEXPI/Proteus importer and
pipeline beyond generated plants? Sweep covered: DEXPI (GitLab/GitHub/dexpi.org), pyDEXPI, ProteusXML, OPEN100,
digitization datasets (PID2Graph, Digitize-PID, others), post-2024 benchmarks, NRC/DOE public documents, GitHub
and Zenodo search.

Marking: **VERIFIED** = I opened the source (downloaded the file / read the API listing / read the page) and the
number is from that. **UNVERIFIED** = from a search snippet or a secondary page only. Element counts below come
from my own ElementTree count over the downloaded XML (counts of the tag, not of semantic objects). Scratch
downloads are in the session scratchpad, not in the repo.

## 0. Bottom line

1. **No public real multi-sheet DEXPI/Proteus plant exists.** Every public Proteus/DEXPI file I found is a single
   drawing. The largest by element count is C01V01-SAG.EX01 (COMOS export, 1.79 MB, 26,435 XML elements,
   VERIFIED); the largest by bytes is a 2.6 MB COMOS file in a RWTH repo (section 1.7). No academic or open-data
   release of a multi-document DEXPI plant was found (searched: DEXPI GitLab group, pyDEXPI, ProteusXML, GitHub
   topic searches, Zenodo, arXiv). "Not found" here is a result.
2. **The only real two-sheet set with off-page connectors is DEXPI C08 (Covestro, "Two connected P&IDs")**, but it
   ships as PDF + SmartPlant Foundation Excel lists, **no Proteus XML** (VERIFIED on master and two other branches).
3. **For importer robustness on real vendor dialects there is a good, licensed set**: DEXPI "Public Example PIDs",
   CC BY 4.0, 35 Proteus files in the 1.3 folder and 185 XML variants in 1.2 (vendor exports from SmartPlant
   P&ID, COMOS, AVEVA P&ID). It does not give scale.
4. **Correction to our own record:** ADR-0007's OPEN100 spike concluded the drawings are not reachable from
   open-100.com as static HTML. They are: each of the 10 system pages embeds its P&ID as a Wix-hosted PNG that
   curl fetches with a browser User-Agent (VERIFIED, section 3.1). The public count is 12 P&ID PNGs, equal to
   PID2Graph OPEN100's 12. No extra OPEN100 sheets exist, so nothing new for scale.

## 1. DEXPI / Proteus XML

### 1.1 DEXPI "Public Example PIDs" (TrainingTestCases) - best importer test material

| Fact | Value | Status |
|---|---|---|
| URL | https://gitlab.com/dexpi/TrainingTestCases (project name "Public Example PIDs") | VERIFIED |
| Licence | Creative Commons Attribution 4.0 International (LICENSE blob read; GitLab project metadata shows `license: None`, the file is what counts) | VERIFIED |
| Created / last activity | 2018-09-19 / API `last_activity_at` 2025-07-11; master last commit 2024-10-17 | VERIFIED |
| Tree | 754 entries on master: folders `dexpi 1.2`, `dexpi 1.3`; 220 `.xml` files in total | VERIFIED (API tree, 8 pages) |
| `dexpi 1.3/example pids` | 35 Proteus XML files, 863,547 bytes in total. C01 (DEXPI reference P&ID, 445,726 B), C02 (BASF process column, 157,666 B), C03 (Equinor piping, 68,507 B), E01-E14 (equipment), I01-I15 (instrumentation), P01-P04 (piping). C04-C06 and C08 exist as folders but have no 1.3 XML | VERIFIED (downloaded all 35) |
| Content of the 35 | together 61 `PipingNetworkSegment`, 70 `Equipment`, 39 `ProcessInstrumentationFunction` elements. C01 is schema 4.1.1, OriginatingSystem "P&ID Toolbox" (pnb plants & bytes), 5,216 XML elements | VERIFIED |
| `dexpi 1.2/example pids` | 185 XML: the same cases exported by several vendors, file suffix = exporter (AUD, AVV, HEX, ING, SAG, VER, DXI). Header check on the 19 C-series files: OriginatingSystem is `SPPID` (SmartPlant P&ID, schema 3.3.3 and 4.0.1), `Comos`, `AVEVAPID`, or none (VER = reference solution). Sizes 3 KB to 1.79 MB | VERIFIED for the 19 files downloaded; the other 166 only listed |
| Sheets | every file is one drawing (at most one `<Drawing>`) | VERIFIED |
| Connectivity | yes: piping network systems/segments, nozzles, instrumentation functions, actuating systems (E-series files are equipment only, no piping) | VERIFIED |
| Off-page connectors | present in 1.3 as `PipeOffPageConnector` elements: C01 (FlowIn + FlowOut; the element count of 4 includes two shape elements), C02 (FlowOut + a ReferenceByNumber), C03 (FlowOut), P02 (FlowIn + ReferenceByNumber). In 1.2 vendor files they appear as `PipeConnectorSymbol` (1-4 per file). **They do not point to another file**: in P02 the connector number and the referenced connector number are both "123" (same file); the partner would be in a drawing that is not shipped. The Proteus cross-sheet key is a connector number (`PipeConnectorNumberAssignmentClass` / `ReferencedConnectorNumberAssignmentClass`), not a drawing number. C01's connectors carry no attributes | VERIFIED (read the XML of P02, C01, C02, C03) |
| Usable for importer at larger scale? | **No for scale** (one sheet per file). **Yes for dialect coverage**: three real vendor dialects of the same drawing, schema 3.3.3 / 4.0.1 / 4.1.1, PipeConnectorSymbol vs PipeOffPageConnector variants, ReferenceByNumber | - |

The same 35 1.3 files are mirrored (byte sizes identical, GitHub trees read) in `separk-1/codesign data/pids`,
`richardblaha/osiris-dexpi samples/` and `vishal7pandey/chatpid data/dexpi_real`. Do not cite the mirrors; cite
the GitLab source.

### 1.2 C08 "Two connected P&IDs (Covestro)" - only real multi-sheet pair, no XML

| Fact | Value | Status |
|---|---|---|
| Path | `dexpi 1.3/example pids/C08 Two connected P&IDs (Covestro)/C08V01` (1.2: `C08 example Covestro - two connected PIDs`) | VERIFIED |
| Files | `UER-1234567.pdf`, `UER-2345678.pdf` (+ `_bw` variants), and eight lists: `COV Drawing List.xlsm`, `Equipment List`, `Instrument List`, `Line List.xls`, `PCS Connections List`, `PCS List`, `Plant Items`, `Valve List`. **No `.xml` anywhere** (checked master, `cleaning_for_dexpi_1.3`, `rmr.autodesk-master-patch-69346`) | VERIFIED |
| PDFs | one page each, vector with extractable text (`pdftotext` returns text). I rendered UER-1234567: title "Reaktion Str.1 Teil 2 (Musterfliessbild)", project COVPIL1, A1 landscape, created 2020-04-17 | VERIFIED |
| Off-page connectors | **yes, labelled with the partner drawing**: arrows such as "Kuehlwasser, 20 C / LA01-BA009 283 / UER-2345678", "Zur Abluftreinigung / LA01-BA112 274 / UER-2345678", "Tanklager LA01-BA111 287 / UER-2345678", each with a line number (e.g. LA01-LR024.10000-25-10H1200 NV 221), a connector number and the partner drawing number. Seen on sheet 1; the reverse direction on sheet 2 not read | VERIFIED for sheet 1, UNVERIFIED for the reverse direction |
| Excel lists | exported from SmartPlant Foundation; the drawing list names both UER drawings ("Training P&ID"). Row counts of the other lists not read | VERIFIED (drawing list strings read) |
| Licence | repo-level CC BY 4.0 | VERIFIED |
| Connectivity as data | not a machine-readable graph: PDF geometry + lists | - |
| Usable for importer? | **No importer test** (no XML). **Yes for a resolver/cross-sheet test**: a real, industry-authored two-sheet pair with partner-drawing + line-number + connector-number keys, the exact structure of our off-page problem. Ground truth would be hand-built and tiny (2 sheets) | - |

### 1.3 pyDEXPI package and repo

| Fact | Value | Status |
|---|---|---|
| URL | https://github.com/process-intelligence-research/pyDEXPI | VERIFIED |
| Licence | AGPL-3.0 (GitHub API) | VERIFIED |
| Data in repo | `data/C01V04-VER.EX01.xml` (445,726 B) and `data/dexpi_sample_patterns/*.pkl` (already noted). README says the sample is the DEXPI reference P&ID, copyright DEXPI e.V. **Nothing else**: no TEP, no multi-sheet (full 170-entry tree listed) | VERIFIED |
| README caveat | "Drawing information are currently not parsed" by the Proteus loader | VERIFIED |

### 1.4 DEXPI Specification repo (GitLab) and ProteusXML schema repo

- https://gitlab.com/dexpi/Specification: tags V1.3.0, V1.4.0, V2.0.0 (2025-10-10), V2.0.1 (2026-09-30) (VERIFIED, API). The master tree (228 entries) holds one XML example, `src/documentation/_static/reference_pid.xml` (the reference P&ID again), plus the XSD and the Python metamodel. No other example. The claim that "DEXPI XML" in 2.0 replaces the Proteus schema is from a UReason blog (UNVERIFIED); the V2.0.0 tag date is VERIFIED.
- https://github.com/ProteusXML/proteusxml: 11 files, XSDs 4.0.1, 4.1, 4.1.1 rc1, 4.2 and docs, **no example instance files**, no licence in metadata (VERIFIED). Useful only to XSD-validate our inputs.
- GitHub org `DEXPI` lists Specification, GraphicBuilder, TestCases; the last two are archived; Specification "is not maintained anymore" and points to GitLab (VERIFIED from the page text).
- GitLab group `dexpi` projects: dexpi-viewer, dexpi-verificator, public-opc-ua, public-verificator, Specification, GraphicBuilder, TrainingTestCases (VERIFIED, API). dexpi-verificator holds only README.md and ideas.md.

### 1.5 "DEXPI TEP case" - it exists, but it is a PFD in DEXPI 2.0 Process, not a Proteus P&ID

| Fact | Value | Status |
|---|---|---|
| What | Tennessee Eastman Process as a DEXPI **Process** (PFD/BFD) model in DEXPI 2.0 XML. The DEXPI Process 1.0 manual (dexpi.org, 39 pages, Dec 2023) lists `TennesseEastman.xml` as "the Tennessee Eastman example process" among its example files | VERIFIED (read the manual text) |
| Where a copy is public | `vegarringdal/dexpi-viewer`: `refrences/examples/dexpi-2.0/TennesseeEastman-vpd-enriched.xml`, 1,231,552 B, exporter "Model Broker for Diagrams" (Semantum), 2025-12-05. Also `skhella/bpmn2dexpi` `examples/Tennessee_Eastman_Process.bpmn` (212,553 B, MIT) | VERIFIED (downloaded the XML) |
| Size | 42 `Process.Stream`, 84 `MaterialPort`, 2 `Pumping`, 11 `Composition`; 876 objects total | VERIFIED |
| Licence of the XML | not stated. Hosting repo dexpi-viewer is AGPL-3.0; bpmn2dexpi is MIT and says "DEXPI Specification is licensed under CC BY 4.0" | UNVERIFIED |
| Connectivity / off-page | stream connectivity yes (PFD level); no piping, no instrumentation hardware, no off-page connectors | VERIFIED |
| Usable? | **No for the Proteus P&ID importer.** It would need a DEXPI 2.0 Process reader (not planned). ChatP&ID's "TEP" mentions, if any, are not this file | - |

### 1.6 DEXPI 2.0 Plant (P&ID) examples

| Fact | Value | Status |
|---|---|---|
| `reference_pid.xml` | DEXPI 2.0 XML serialisation of the C01 reference P&ID, 1,480,481 B (Specification repo; copy in dexpi-viewer/refrences) | size VERIFIED from the tree; file not opened |
| DISC DEXPI 2026 Pack | https://github.com/ToniaPedersen/DISCDEXPI_2026Pack (no licence in GitHub metadata; pushed 2026-10-21). `Blueprint/DISC_EXAMPLE-14/`: `-01.xml` ... `-13.xml` + `_NOA2`, `_NOA3`, each about 1.07-1.12 MB, DEXPI 2.0 XML, plus PDFs `C01_NOA1_01..13.pdf`. README: "Folder containing all Blueprint use case versions" - i.e. versions of one drawing, not 13 sheets. I opened version 13: 1,717 objects, 33 PipingNetworkSegment, 18 PipingNetworkSystem, 13 ProcessInstrumentationFunction, 1 FlowIn + 1 FlowOut PipeOffPageConnector, 2 PipeOffPageConnectorReferenceByNumber | v13 counts VERIFIED; "same topology across versions" UNVERIFIED |
| Usable? | Only if we add a DEXPI 2.0 XML reader. Single sheet. Licence unstated, so treat as not redistributable | - |

### 1.7 Third-party DEXPI-like files found on GitHub

- `rwth-iat/evidence-aware-engineering-workbench` (MIT repo): `Documents/R&I-Fliessbild/=A10.A10.A10.FB.001 (A58A1PQ0CA).xml`, COMOS 10.5, Proteus 4.0.1, 2,606,355 B, 13 Equipment, 15 PipingNetworkSystem, 33 PipingNetworkSegment, 42 ProcessInstrumentationFunction, one drawing, with `2025-09-03_P&ID_Pumpwerk.pdf` (140,348 B). A real-looking single pump-station plant, the largest real Proteus file by bytes found (VERIFIED: downloaded and counted). Licence of the file itself UNVERIFIED (repo MIT; README calls `Documents/` a "public companion document bundle"). No off-page connectors. The bundle also holds vendor datasheets (out of scope for the thesis).
- `zacheryzhu-cyber/ConceptualGraphIdea` (no licence): `FB.001 1.XML` (COMOS 10.6, Proteus 4.1.1, dated 2026-10-15, 26 Equipment, 5 PipeOffPageConnector, 36 PIF) and `sth.xml` (COMOS 10.4.4, Proteus 4.0.1, 2.96 MB). One drawing each, provenance unknown. VERIFIED (downloaded, counted). **Do not use**: no licence, unknown origin.
- `vishal7pandey/chatpid` (no licence) and `shaaz1000/pid-graph-agent` (AGPL-3.0): ChatP&ID re-implementations on the same DEXPI 1.3 files; nothing new in data.
- `equinor/Dexpi2Imf` (GPL-3.0), `uchokoro/dexpi-render`, `openpid-com/openpidl`, `mouadhassal/pidcheck`: tools; listings show no new Proteus data (pidcheck advertises "real DEXPI test cases", which are the DEXPI examples).

## 2. Annotated image datasets with graph / connectivity

| Name | URL | Format / size | Licence | Connectivity | Off-page | Usable for our importer? | Status |
|---|---|---|---|---|---|---|---|
| PID2Graph (Stuermer et al., arXiv 2411.13929) | https://zenodo.org/records/14803338 | one 9,303,633,645 B zip; graphml + png/jpg. Our earlier count: 500 `Dataset PID` (synthetic, Paliwal) + 250 `Synthetic` + 12 `OPEN100` = 762 sheets | CC BY-SA 4.0 (Zenodo API) | yes, **undirected**, text-free labels | OPEN100 only (12/12 sheets) | No (image to graph, not DEXPI). Already used for EXP-0004 | licence and file size VERIFIED now; 762 count from `pid2graph.md` |
| PID2Graph paper's "60 real-world P&IDs from various plants" | same paper (v3 text) | used for training | - | - | - | **Not in the Zenodo release** (762 sheets there; the paper states the 60 were manually annotated and gives no release statement) | text VERIFIED, absence inferred |
| Dataset-P&ID / Digitize-PID (Paliwal et al., arXiv 2109.03794) | Google Drive folder printed in the paper (`1gMm_YKBZtXB3qUKUpI-LF1HE_MgzwfeR`); HF mirrors `hamzas/digitize-pid-symbols`, `SherifAhmed/digitize-pid-yolo` (symbols only) | 500 **synthetic** sheets, 32 symbol classes, 4:1 train/test; ground truth = symbol boxes + text + line coordinates. The 12 real sheets used for evaluation are a **private, anonymized set, not released** | not stated in the paper text; our PID2Graph note lists CC BY-SA 4.0 | line segments + symbols, not a graph | no | No | paper text VERIFIED; Drive not opened |
| Gupta et al. "PID_dataset" | https://zenodo.org/records/8028570 | 6,685,294,325 B zip; I listed the zip directory by HTTP range request: `0__raw_data/sheets` **92 jpg**, `labels` 93 txt, `1__processed_data` 765 crops, `3__Stage-2` 3,166 + 547 jpg. Description: "P&IDs from industry and webscraping" | CC BY 4.0 (Zenodo API) | **symbol boxes only** (txt labels; no label file opened) | no | No (digitization front end, out of scope) | listing VERIFIED; label content UNVERIFIED |
| PIDQA (Gupta et al., MAKE 7(2):39) | GitHub `mgupta70/PIDQA` | 500 synthetic Dataset-P&ID sheets, 64,000 QA, Neo4j LPG, integer labels | CC0-1.0 | yes (LPG) | no | No (single sheet, synthetic) | from our note |
| SynthPID (arXiv 2604.16513, CVPRW 2026) | `LatentSpaceIITB/SynthPID` named in search results; GitHub API returned 404 | 665 synthetic P&IDs seeded from OPEN100 topology | paper CC BY 4.0; dataset licence not stated | graph annotations not confirmed | not mentioned | No | abstract level only |
| TopoPID-VQA (arXiv 2609.05880) | none ("No code or data link in the paper", our note) | 500 synthetic sheets, 3,000 questions | - | - | no | No | from our note |
| Roboflow Universe P&ID sets | universe.roboflow.com (several projects) | symbol boxes (one ~3,800 images, 11 classes) | some CC BY 4.0 | none | no | No | UNVERIFIED (snippet) |
| Enginuity (arXiv 2601.13299) | - | **an automotive exploded-parts-diagram proposal**, not P&ID; its Kaggle link is a handwritten-circuit dataset | CC BY 4.0 (paper) | proposed | - | **Exclude.** Not the same as the Enginuity VLM benchmark (2606.03410) in our reading list | VERIFIED (read the PDF text) |

No other open real-P&ID corpus with line/graph labels was found. Digitize-PID and PID2Graph both state the same
scarcity; the 12-sheet OPEN100 set is still the only public real graph benchmark.

## 3. Multi-sheet sets with off-page connectors

### 3.1 OPEN100 (Energy Impact Center) - the only public multi-sheet open design

| Fact | Value | Status |
|---|---|---|
| URL | https://www.open-100.com (Engineering menu lists 10 systems: mainsteam, aircooledcondenser, condensate, feedwater, extractionsteam, reactorcoolant, auxiliarycoolingwater, spentfuelcooling, chemicalandvolumecontrol, residualheatremoval) | VERIFIED |
| Format | **PNG only**, embedded in each system page (Wix `static.wixstatic.com/media/b7c2c6_*~mv2.png`). No PDF, ZIP, DWG or DXF link on any of the 10 pages (regex over the HTML). The only download link seen anywhere is a STEP CAD zip of the reactor vessel on /vessel | VERIFIED |
| Sheet count | 12 P&ID PNGs: ACC 1, ACW 2, CVCS 1, condensate 1, extraction steam 1, feedwater 1, main steam 1, reactor coolant 2, RHR 1, spent fuel cooling 1; 1,994x1,330 to 3,198x2,128 px. Excluded: a 1,600x900 decorative PNG (ACW page, viewed) and a 3D-render JPG (main steam page, viewed). I viewed one P&ID (condensate, "PID 160", drawn by MAJ, 09/01/2020, rev A, "SHEET 1 OF 1"); the other 11 were counted by URL pattern and pixel size only. 12 equals PID2Graph OPEN100's 12 | image count VERIFIED; "all 11 unviewed are P&IDs" UNVERIFIED |
| Off-page connectors | yes: boxed arrows naming the partner drawing, e.g. "ACC PID 150-1 / CONDENSATE RETURN", "FWS PID 170-2 (E-1) / FEEDWATER SYSTEM", "WTS PID 200-4", "MSS PID 240-1", with line numbers like `SIZE-COND-162109-SPEC-HC-X`. Partners include sheets not on the site (e.g. feedwater "170-2"), so the public set has dangling references (consistent with `pid2graph.md`) | VERIFIED on the condensate sheet |
| Licence | **none stated** on the pages read (home, engineering, vessel, FAQ). The sheet carries the notice "INFORMATION ONLY - NOT FOR CONSTRUCTION. THIS PRELIMINARY DESIGN HAS BEEN PREPARED AND DISTRIBUTED BY ENERGY IMPACT CENTER FOR THE PURPOSE OF RESEARCH AND DESIGN DEVELOPMENT. USE OF THIS INFORMATION FOR ANY OTHER PURPOSE IS AT THE SOLE RISK OF THE USER." PID2Graph redistributes the 12 sheets under CC BY-SA 4.0 | VERIFIED |
| Connectivity as data | none (images); graph truth only via PID2Graph (undirected, text-free) or our ADR-0005 annotation | - |
| Usable? | already our EXP-0004 set; **nothing new**. ADR-0007's spike wording should be corrected: the images are reachable, just not as a package | - |

### 3.2 Transatomic Power legacy repository (TAP-520 balance-of-plant blueprints)

Search results say Transatomic open-sourced its IP and a GitHub repo holds a `blueprints` folder with
balance-of-plant drawings (a Gitee mirror lists MIT). **UNVERIFIED**: the INL GAIN page returned 403, the guessed
GitHub URL 404, GitHub API search found nothing. I could not confirm that any P&IDs exist, their format, or the
licence. Cheap follow-up for the user: open the INL GAIN "Molten Salt Reactor" page in a browser.

### 3.3 NRC ADAMS public documents (US government, real plants)

Search results point to ADAMS PDFs with real P&ID sheets (a Bechtel drawing package indexed under ML0829...,
BECH-M101 "P.&I.D. Instrument Symbols" first; each sheet a separate one-page document) and to Westinghouse/AP1000
training chapters with system diagrams (e.g. ML023030495). **UNVERIFIED in all details**: nrc.gov returns
HTTP 403 "Access Denied" to my fetches, also with a browser User-Agent, so I could not open a drawing, count
sheets or read a notice. Needs a browser check by the user: which plant, how many sheets, proprietary/copyright
markings (licensee drawings usually carry them), vector or scan. If usable these would be real, multi-sheet, with
off-page references, but PDF only.

### 3.4 Others searched, nothing usable found

- Hanford HNF-64103 (already noted): a standard, not a drawing set.
- Vendor sample P&IDs (Edraw, Creately, DesignsCAD): templates or paid sets, not pursued.
- AVEVA documentation describes DEXPI export of "multiple drawings via the batch option" but links no sample.

## 4. DEXPI-to-graph tools and benchmarks since 2024

| Item | What it is | Data for us? | Status |
|---|---|---|---|
| ChatP&ID (arXiv 2603.22528) | GraphRAG on DEXPI | 1 sheet (C01), 19 questions | existing note |
| `shaaz1000/pid-graph-agent` | agent over DEXPI | 15 questions on C01 + 37 on 8 other DEXPI 1.3 files | existing novelty log |
| `TUDoAD/DEXPI2graphML` (LGPL-3.0, last push 2023-08-14) | DEXPI to GraphML | tree request on `master` failed; no data seen | UNVERIFIED |
| Oeing et al., CIT 2023 (CC BY 4.0) | GNN on DEXPI topology | no dataset link found in snippets | UNVERIFIED |
| bpmn2dexpi (MIT; Khella et al., Digital Chemical Engineering 2026) | BPMN to DEXPI 2.0 Process | TEP PFD only | VERIFIED repo |
| dexpi-viewer (AGPL-3.0), `ToniaPedersen/DEXPIViewer` (MIT) | DEXPI 2.0 viewers/validators | bundle DISC examples and TEP | VERIFIED repo |
| `Qingchuan-ZHU/ugs-dexpi-ir-reproducibility` (MIT) | LLM-generated DEXPI XML experiments | 3 generated files, not real | VERIFIED tree |

No DEXPI-to-graph benchmark released since 2024 with more than one sheet was found.

## 5. Ranked shortlist: what to try first, and what each lets us claim

| # | Try | Effort | What it lets us claim | What it cannot |
|---|---|---|---|---|
| 1 | **DEXPI 1.3 example set (35 files) + the 1.2 C01-C05 vendor exports** (GitLab, CC BY 4.0). Run the importer over all; report parse success, unknown-class fallbacks (ADR-0016), connector handling | hours | "The importer reads real vendor-exported Proteus (SmartPlant P&ID, COMOS, AVEVA, P&ID Toolbox), schema 3.3.3 to 4.1.1, not only pyDEXPI-built models"; a list of dialect differences (PipeConnectorSymbol vs PipeOffPageConnector, ReferenceByNumber) | any scale claim; every file is one sheet |
| 2 | **C08 Covestro two-sheet pair** (PDF + Excel). Hand-transcribe the off-page arrows (partner drawing + line number + connector number) into a cross-sheet truth, optionally hand-build a two-sheet DEXPI | about a day | "The resolver key works on a real industry-authored vector-PDF sheet pair": a second real validation point next to OPEN100's 12 sheets, and a real instance of the Proteus convention (connector number, not a file link) | statistics (2 sheets); no XML importer test |
| 3 | **OPEN100 12 sheets**: already held. Add to the thesis text: images are on the public site, no explicit licence, "not for construction" notice, dangling partner references | minutes | provenance and licence statement; real external-validity set stays 12 sheets | anything beyond 12 |
| 4 | **rwth-iat Pumpwerk COMOS file** (2.6 MB, 13 Equipment, 42 PIF, MIT repo) | an hour | "importer handles a 2.6 MB real COMOS 4.0.1 export" (largest real file by bytes); confirm the file licence with the authors before citing | multi-sheet; off-page |
| 5 | NRC ADAMS drawings, Transatomic repo (both UNVERIFIED, need a browser) | user task | possible real multi-sheet PDFs with off-page references, if licence/marking allows | DEXPI; digitization input only |
| - | TEP (DEXPI 2.0 Process PFD), DISC_EXAMPLE-14 (DEXPI 2.0 XML) | skip | only if we add a DEXPI 2.0 XML reader (a different format from Proteus) | - |
| - | Dataset-P&ID, PID_dataset, Roboflow, SynthPID | skip | the digitization front end is out of scope (ADR-0008) | - |

## 6. What this means for the thesis claim

- The scale gap is confirmed from the data side: **no public real multi-sheet DEXPI plant, no benchmark with cross-sheet truth, largest real Proteus file 2.6 MB / one sheet.** The 12 OPEN100 sheets remain the only real multi-sheet material, and they are images with dangling partner references. This supports the framing that generated plants at 100 to 4,000 sheets are the only way to test scale, and it should be stated as a limitation, not hidden.
- External validity can be strengthened cheaply (items 1-2): dialect coverage on 35 + 19 real Proteus files and a real two-sheet cross-reference pair. Claim "tested on the public DEXPI example corpus and one real sheet pair", not "tested on real plants".
- Honest unknowns: NRC ADAMS content, the Transatomic repo, the licence of the Pumpwerk file, and whether the 11 unviewed OPEN100 images are all P&IDs (very likely, since the count matches PID2Graph's 12).
