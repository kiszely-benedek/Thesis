# Novelty log

Dated record of every `/lit-gap-check` run, including runs that found nothing. Negative results are evidence — the professor will ask how thoroughly this was checked, and "we looked on these dates with these queries" is the answer.

---

## 2026-08-23 — initial sweep

**Claim tested:** multi-page / multi-document / plant-region GraphRAG over engineering diagrams is unaddressed academically.

**Queries run:** multi-page P&ID off-page connector cross-sheet knowledge graph · plant-wide P&ID knowledge graph entity resolution tag matching · GraphRAG scalability multi-document engineering diagrams 2026 · scanned legacy P&ID digitization large corpus RAG · P&ID multi-sheet graph merging benchmark · hierarchical knowledge graph retrieval industrial documents

**New papers found (not on the professor's list):**

| ID | Date | Eval scale | Threat |
|---|---|---|---|
| 2607.19568 — P&ID Drawings to Process Graphs (MLLM) | Jul 2026 | 2 P&IDs | adjacent |
| 2505.11976 — Discrete Line Segment Integration | May 2025 | single drawing | no overlap |
| 2502.18493 — Rule-based autocorrection of P&IDs | Feb 2025 / rev Jun 2026 | 1 illustrative P&ID | no overlap — becomes our validation baseline |

**Also noted, not yet read:** Oeing et al. (GNNs for plant topology, CIT 2023) · Microsoft GraphRAG, LightRAG, HippoRAG-2, KET-RAG · arXiv 2507.03226 (practical GraphRAG at scale).

**Commercial prior art (no published method):** SymphonyAI P&ID Ingestion, Acuvate DiagramIQ, Cognite. Industry reports ~70–80% automatic entity resolution against existing asset hierarchies, with the remainder surfaced for engineer review. Useful as a target number; not citable as method.

**Verdict: claim still open.**

**Note:** 2607.19568 was published ~1 month before the project started and appeared on neither the professor's list nor our radar. This is why the check is scheduled fortnightly.

---

## 2026-09-08 — ontology sweep (professor's ontology question)

**Claims tested:** (a) no published OWL/RDF form of the DEXPI P&ID information model; (b) no P&ID work uses
a formal ontology/vocabulary for retrieval; (c) no cross-drawing identity vocabulary. Full write-up in
`ontology-landscape.md`.

**Queries run:** DEXPI information model RDF OWL ontology P&ID · ISO 15926 part 14 OWL 2 reference data
library POSC Caesar · CFIHOS IOGP JIP36 RDL machine readable ISO 15926 · OntoCAPE RWTH OWL download ·
"P&ID" ontology OWL 2024 2025 knowledge graph semantic · reference ontology KG construction from P&ID ·
SPARQL RDF RAG P&ID process plant LLM triplestore 2025 2026 · "off-page connector" multi-sheet tag identity
across drawings ontology · IEC 61987 CDD / IEC 62424 CAEX · Brick SAREF IOF scope · Arrowhead fPVN
semantization DEXPI CFIHOS STEP IDO · Oeing machine-readable plant topology.
**Direct source checks:** dexpi.org (specs + news), gitlab.com/dexpi/Specification via API (file-extension
scan), github.com/dexpi, pyDEXPI raw `pydantic_classes.py`, PCA RDL IRI dereferencing (content
negotiation), Arrowhead fPVN Handbook + Use Cases full text, jip36-cfihos.org, schema.org (incl. `/Pump`
404), Wikidata API, QUDT, W3C SSN, IOF spec site.

**New papers / artefacts found (not on the reading list):**

| ID | Date | Eval scale | Threat |
|---|---|---|---|
| **make7020039 — PIDQA** (MAKE 7(2):39) | Jun 2025 | **500 single sheets, 64,000 template QA pairs**, single-sheet only, labels are integers 1–32 | **relevant** — biggest P&ID QA eval to date; raises the evaluation bar, does not touch cross-sheet. Note filed. |
| 2504.21694 — AutomationML → OWL, SPARQL + SHACL | Apr 2025 / rev Sep 2025 | "examples from the automation domain" | adjacent (different standard family); the closest declarative-validation precedent |
| DEXPI 2.0 (Oct 2025) + TotalEnergies "semantic version of the DEXPI models" (announced 2026-03-23, BFO + IDO aligned, **not published**) | 2025–2026 | n/a | **kills "we build the DEXPI ontology" as a contribution** |
| Arrowhead fPVN / IDO handbook DEXPI alignment | 2026 | **one pump**, hand-made example XML, `example.com` namespaces, properties + lifecycle only, no topology, no connectors | no overlap — confirms the retrieval/topology gap |

**Verdict:** the scale claim is untouched. The ontology claim must be narrowed: "a P&ID ontology is
missing" is **false**; "no loadable OWL DEXPI, nobody uses these vocabularies for retrieval, and no
cross-drawing identity vocabulary" is **true and verified**. See the can/cannot-claim list in
`ontology-landscape.md`.

---

## 2026-09-26 — fortnightly check (overdue since 2026-09-22)

**Claim tested:** multi-page / plant-scale GraphRAG over P&IDs is unaddressed academically; the single-sheet
optimum inverts at scale.

**Queries run:** arxiv P&ID multi-sheet OR multi-page knowledge graph 2026 · off-page connector cross-drawing
linking P&ID digitization · GraphRAG scale engineering diagrams 2026 P&ID question answering · plant-wide
knowledge graph entity resolution tag matching P&ID drawings · hierarchical graph retrieval large document
corpus industrial knowledge graph LLM 2026 · "ChatP&ID" OR "2603.22528" citing · multi-page P&ID dataset
cross-sheet question answering benchmark 2026 arxiv

**New papers found:**

| ID | Date | Eval scale | Threat |
|---|---|---|---|
| 2609.05880 — Grounded and Faithful P&ID Reasoning (Gadekar, Srinivas, Runkana; TCS Research) | 5 Sep 2026 | Digitize-PID, 500 synthetic sheets (100 test); TopoPID-VQA 3,000 topology questions, 10 per sheet; **every instance is one sheet** | **adjacent** — pixels → evidence graph → tool-constrained VLM; no cross-sheet, no retrieval-vs-scale comparison. Cites ChatP&ID, not PID2Graph. Raises the single-sheet QA bar again (3,000 questions) |
| 2603.29199 — AEC-Bench (Mankodiya et al.) | 31 Mar 2026 | 196 tasks, 9 types; real public-sector construction documents (arch., structural, civil, MEP); sheet counts not stated | **adjacent — narrows wording.** Has "intra-drawing" tasks "across multiple sheets within the same drawing set". No P&IDs, no KG, no scale study. **We can no longer say cross-sheet reasoning over *engineering drawings* is unstudied — say *P&IDs / process plants*.** |
| 2608.24918 — Semantic Graph Unification for Industrial Digital Threads | Aug 2026 | 11 manufacturing systems | no overlap — ontology-driven integration of IT systems, not drawings |

**Also noted:** ChatP&ID is now published in the **AIChE Journal** (Alimin & Schweidtmann 2026,
doi 10.1002/aic.70540) — cite the journal version. Enginuity (2601.13299) and MegaRAG (2512.20626) resurfaced;
Enginuity is already referenced in `2603.22528.md`, MegaRAG is generic multimodal page-wise KG-RAG (no overlap).
ChemRxiv 10.26434/chemrxiv.10001546 is materials-science literature (no overlap).

**Observation:** the user's public GitHub repository (`kiszely-benedek/Thesis`) is indexed and surfaces for
these queries with our claim in its description — useful as a dated public record of the idea.

**Verdict: claim still open — wording narrowed to P&IDs / process plants** (AEC-Bench covers cross-sheet tasks
in building drawings). No `overlaps — act`; no `/paper-intake` required. 2609.05880 and 2603.29199 belong in
related work.

## 2026-10-02 — focused check: Jev (TypeSafe System One) + standing claim

**Claims tested:** (1) multi-sheet / plant-scale P&ID GraphRAG and cross-sheet entity resolution are unaddressed;
(2) new: is using Jev for cross-sheet tag-variant identity resolution, or for per-question routing between
retrieval strategies / LLMs over P&IDs, already done?

**Queries run:** Jev TypeSafe entity resolution OR record linkage OR deduplication · "System One" model typed
decisions Jev paper OR benchmark OR evaluation · Jev "System One" P&ID OR DEXPI OR "engineering drawings" ·
arxiv 2026 LLM router RAG strategy selection per query GraphRAG adaptive retrieval routing · arxiv P&ID multi-sheet
knowledge graph question answering off-page connector October 2026 · LLM tag matching equipment identifiers
engineering drawings entity resolution plant asset 2026 · ChatP&ID cited by GraphRAG P&ID 2026 scale plant ·
ChatP&ID AIChE Journal "industry-scale" (to check a search-summary claim — not supported by any source; discarded).

**Found:**

| ID / source | Date | Eval scale | Threat |
|---|---|---|---|
| arXiv 2609.37647 — Evaluating and Benchmarking the System One Model Jev (Deußer, Sparrenberg, Sifa) | 29 Sep 2026 | jev-1.13.0 zero-shot, 37 datasets, 346,009 requests (classification, routing, NLI, …); beats Qwen3.8-27B on 27/37 (abstract, read) | **adjacent** — general benchmark; no entity resolution over drawings, no P&IDs |
| arXiv 2609.32160 — Typed Decision Models: An Early Evidence Audit and Evaluation Checklist (Tang, Zheng) | late Sep 2026 | audit of 28 papers posted 19–24 Sep 2026 | **adjacent — important framing:** typed readout shows no independent accuracy advantage over label-probability readouts; gains are latency and cost. Gives a 14-item checklist our Jev arm should follow |
| arXiv 2610.00346, 2609.33401, 2609.28940 — System One models for decision gates, agent security, pentest harnesses | Sep–Oct 2026 | titles/snippets only, not read | no overlap |
| TDS tutorial "GraphRAG with TypeSafe Jev" (P. Sarkar) | 27 Sep 2026 | no dataset, no measurement (read) | **adjacent** — proposes Jev for KG entity resolution / predicate merging / subgraph pruning in generic GraphRAG; no evaluation, no engineering domain |
| Southbridge blog "Jev entity resolution" | 2026 | campaign-finance records; snippet claims −99.56 % model cost, 7.35× throughput (not read) | **adjacent** — Jev for entity matching exists in practice, not on drawings |
| arXiv 2604.16401 — GraphRAG-Router (Fan et al.) | 31 Mar 2026 | 6 Wikipedia QA benchmarks; joint routing over GraphRAG methods and LLMs; −30 % large-LLM calls (read) | **adjacent** — per-query routing over GraphRAGs+LLMs is published (RL-trained); not engineering, not scale-dependent |
| arXiv 2609.02894 (R²Adapter), 2604.03455 / 2602.00296 (RAGRouter-Bench) | 2026 | snippets only | adjacent — adaptive RAG routing, general text |

**No Jev × P&ID / DEXPI / engineering-drawing result** was found. No new multi-sheet P&ID GraphRAG paper since 2026-09-26.

**Verdict: claim still open.** For the Jev arm: **"using Jev" is not novel by itself** (≥ 28 evaluation papers in its
first ten days; Jev for entity matching and GraphRAG-style routing are both described). The defensible novelty is
the **domain and the measurement**: cross-sheet equipment-tag identity on P&IDs with a generated answer key, and
routing over retrieval strategies whose optimum changes with plant scale. Follow 2609.32160's checklist; compare
Jev against a label-probability LLM readout, not only against free-text LLMs. No `overlaps — act`.

---

## 2026-10-10 — fortnightly check + focused: graph-tool agent over generic primitives (ADR-0034)

**Claims tested:** (a) multi-sheet / plant-scale P&ID GraphRAG is unaddressed academically; (b) the retrieval-strategy
optimum depends on corpus scale (serialization → text-to-Cypher → agent); (c) new: is an LLM agent that answers P&ID /
process-plant questions by composing a small fixed set of generic graph primitives (find, neighbours, traverse, path,
filter, aggregate) already published — on one sheet or across sheets? Also: cross-sheet / off-page connector
resolution in DEXPI or P&ID graphs.

**Queries run (web):** arxiv P&ID multi-sheet OR multi-page knowledge graph 2026 · off-page connector cross-drawing
linking P&ID digitization · GraphRAG scale engineering diagrams 2026 · plant-wide knowledge graph entity resolution tag
matching P&ID · hierarchical graph retrieval large document corpus industrial LLM 2026 · LLM agent tool calling P&ID
knowledge graph traversal tools neighbors path · process plant knowledge graph LLM agent graph exploration tools
industrial asset QA 2026 · DEXPI LLM agent 2026 · P&ID copilot LLM agent graph tools isolation upstream downstream ·
off-page connector resolution multi-sheet P&ID graph merging DEXPI · KGQA serialize vs text-to-Cypher vs agent as
graph size grows · cascade/escalation retrieval cost latency GraphRAG text2cypher agent · LLM agent graph database
tool calling MCP Neo4j benchmark 2026 · graph size crossover full graph in context vs retrieval · TableRAG / long
context vs RAG structured size · "When to use Graphs in RAG" / "RAG vs GraphRAG" corpus size · GraphOTTER / GraphAgent
/ agentic GraphRAG · chemrxiv/sciencedirect 2026 P&ID multi-sheet cross-sheet KG QA.

**Direct source checks:** Semantic Scholar citation API for 2603.22528, 2411.13929, 2607.19568, 2502.18928,
2609.05880 · arXiv API newest-first listings for "piping and instrumentation", "P&ID", "P&IDs", DEXPI,
"engineering diagrams" AND graph (newest P&ID-related entry: 2609.12656, 11 Sep 2026) · arXiv HTML full text of
2603.22528 (agent loop, §6.2, quotes verified against the raw HTML), 2609.05880 (tool table 16), 2402.14672,
2404.07103, 2402.11163, 2506.05690v3 (App. G.5), 2511.08609 · GitHub API + README of shaaz1000/pid-graph-agent ·
neo4j-contrib/mcp-neo4j README · AWS Industries blog (Everllence) · Neo4j NODES 2026 session page.

**P&ID / process-plant hits (not filed as notes in this folder):**

| ID / source | Date | Eval scale | Threat |
|---|---|---|---|
| **arXiv 2609.05880**: Grounded and Faithful P&ID Reasoning (TCS Research). *In the 2026-09-26 log as adjacent; re-read for (c)* | 5 Sep 2026 | 100 synthetic test sheets × 30 = 3,000 questions (TopoPID-VQA), gold from oracle graph, one greedy decode; Qwen3-VL-4B/8B, Gemma-4-E4B; image-only 40.1/41.3/36.7 % → grounded 76.0/75.1/74.3 % | **overlaps (c), act.** Its harness is a VLM that calls **seven fact-returning graph primitives** (`node_info`, `neighbors`, `find_nodes`, `bfs` with `exclude_ids`/`max_hops`, `shortest_path`, `edge_exists`, `set_op`) in a loop with a **six-turn budget**; at least one tool call is required (Table 16, full text read). That is ADR-0034's pattern on single sheets. Every item is one sheet; no off-page connectors. No note filed yet → **paper-intake needed** |
| GitHub `shaaz1000/pid-graph-agent` (take-home assignment, not peer-reviewed, 0 stars) | created 2026-10-01, last push 2026-10-07 | 15 author-written questions on DEXPI C01 (12/15 fully correct, mean 0.894) + 37 on 8 other DEXPI 1.3 example files (30/37, mean 0.811) + 150-run follow-up; one run each; required-fact scorer, no LLM judge (README read in full) | **adjacent, very close to (c).** LangGraph agent, **seven generic tools** (`find_entities`, `list_entities`, `get_entity`, `get_connections`, `traverse`, `find_path`, `get_properties`), later three composite ones (isolation boundary, instrumentation chain, line trace); budgets 8 planning turns / 16 tool calls; deterministic grounding validator. **One DEXPI file per question**; a traversal ending at an off-page connector is reported as "the absence is about this drawing". Software, not a paper |
| AWS Industries blog: "How Everllence Scaled P&ID Intelligence…" (Kochański et al.) | 27 May 2026 | **no evaluation**; graph sizes only ("an eight-page engine P&ID can contain 2,000 nodes with 7,500 relationships"; "1,909 nodes and 7,525 relationships from a single site in 1 hour"); plants "up to 100 pages" | **commercial prior art for (a) and (c).** Neo4j KG with "cross-page connectivity restoration [that] links systems that span multiple diagram sheets" (method not described); LangGraph ReAct agent with "predefined graph query tools for common patterns", a guarded free-form Cypher tool and LightRAG. Joins the SymphonyAI / Acuvate / Cognite list |
| Neo4j NODES 2026 talk: "What Connects to This Pump?" (H. Kokubo, JGC) | scheduled 12 Nov 2026 | none (abstract page only) | **commercial, adjacent.** Claude Agent SDK + read-only Neo4j MCP server; the agent writes its own Cypher; the demo spans "several linked drawings". Text-to-Cypher, not primitives; no method or eval |
| arXiv 2605.26874: KGs as the Missing Data Layer for LLM-Based Industrial Asset Operations (Mandarapu, Kunkunuru) | 26 May 2026 | AssetOpsBench 139 scenarios + 40 graph-native; GPT-4 65 % → 82–83 % with LLM Cypher; native primitives (no LLM) 99 % on graph-answerable (abstract read) | **adjacent.** Routes each question to LLM-Cypher, deterministic graph primitives or generated knowledge; maintenance assets, not P&IDs; no cross-sheet |
| ACS Chem. Health Saf. 10.1021/acs.chas.6c00094: Neuro-symbolic P&ID auditing (Shinde, Chachad, Bhosale) | 15 Sep 2026 | **none**: "examined conceptually" on three scenarios (abstract read) | no overlap |
| arXiv 2604.16513: SynthPID (Prasad, Mahapatra) | 15 Apr 2026 | 665 synthetic P&IDs; 63.8 ± 3.1 % edge mAP on PID2Graph OPEN100 (abstract read) | no overlap (single-sheet digitization) |
| arXiv 2608.11220: LLMs in Process Diagram Engineering, PFD → P&ID (Zakarin et al.) | 21 Jul 2026 | not stated in abstract | no overlap (generation via a restricted SDK) |
| arXiv 2609.12656: DEXPI serialization in LLM greenfield design (Zhu, Tong, Ren) | 11 Sep 2026 | 3 cases, 1 generation each | no overlap |
| arXiv 2511.08609: Transformer digitization of SNAM gas plants (Bailo et al.) | 5 Nov 2025 | ~1,500 documents provided; eval sheet count not stated; 91 % design-data text, 93 % components, ~80 % hierarchy (full text skimmed) | no overlap (no cross-sheet linking, no QA) |
| arXiv 2409.00082: multi-agent ReAct VQA over PFD/P&ID images (Sakhinana, Sannidhi, Runkana) | Aug 2024 | not stated in abstract | adjacent (image-based, no graph tools) |
| Front. Chem. Sci. Eng. 10.1007/s11705-026-2685-z: "AI for P&IDs: a review and perspective" (Ma et al.) | 25 Jun 2026 | review; **abstract and full text not accessible** (Springer paywall; S2 abstract elided) | **unknown; get it via the library.** If it names multi-sheet as an open problem, that is a citable statement of the gap |

**General prior art read for (c), tool-based KG exploration** (abstracts read; tool lists from full text where
marked): StructGPT 2305.09645 (iterative reading-then-reasoning over interfaces) · Think-on-Graph 2307.07697 (LLM beam
search over a KG) · ToG-2 2407.10805 · AgentBench 2308.03688 (KG environment) · **Middleware / KBQA-Agent 2402.14672**
(full text: seven KB tools `get_relations`, `get_neighbors`, `get_attributes`, `argmax`, `argmin`, `intersection`,
`count` over **variables** that name earlier results, e.g. `#0`; 500 questions). This is the closest general precedent
to our primitives-plus-handles design · **KG-Agent 2402.11163** (full text: extraction / logic / semantic toolbox incl.
`get_relation`, `get_entity_by_constraint`, `count`, `intersect`, `union`, `end`; LLaMA2-7B fine-tuned on 10K samples)
· **Graph-CoT 2404.07103** (full text: `RetrieveNode`, `NodeFeature`, `NeighborCheck`, `NodeDegree` + Finish; GRBench
1,740 questions over 10 graphs of ~47K to ~84M nodes; no analysis by graph size) · Interactive-KBQA 2402.15131 (three
generic KB APIs) · Tree-of-Traversals 2407.21358 · QueryAgent 2403.11886 · KBQA-o1 2501.18922 · RoG 2310.01061
(plan-then-retrieve relation paths; no tools) · KnowGPT 2312.06185 (prompt construction; no tools) · GraphOTTER
2412.01230 (table → graph, pre-defined actions) · GraphDancer 2602.02518 · GraphReAct 2605.07357 · **GraphScout
2603.01410** (argues "a limited set of predefined tools … substantially constrains graph exploration": the
counter-position to ADR-0034) · GABench 2608.01684 (84 graph tools, 10,400 tasks) · BYOKG-RAG 2507.04127
(multi-strategy incl. OpenCypher) · RLM-on-KG 2604.17056 (fixed tool set, heuristics first) · Neo4j `mcp-neo4j-cypher`
(tools `get_neo4j_schema`, `read_neo4j_cypher`, `write_neo4j_cypher`: MCP graph access is free-form Cypher, i.e. our
`cypher_agent` arm).

**Prior art read for (b) and the cascade:**
- **arXiv 2506.05690v3, GraphRAG-Bench "When to use Graphs in RAG" (Xiang et al.), App. G.5 (full text read):** Novel
  corpus at ~56k / ~603k / ~1,132k tokens. Standard RAG beats HippoRAG2 at Small on every task (Complex Reasoning
  58.64 vs 53.38) but falls to 41.33 / 43.20 at Medium / Large while HippoRAG2 holds 56.67 / 54.29. **A published
  scale-dependent crossover between retrieval strategies, on text corpora, not engineering graphs.**
- arXiv 2407.16833, Self-Route (Li et al.): long context beats RAG "when resourced sufficiently", RAG is far cheaper;
  routes per query (abstract).
- arXiv 2509.18487 (Finkelshtein et al.): code generation beats prompting "on long-text or high-degree graphs where
  prompting quickly exceeds the token budget" (abstract).
- arXiv 2601.21162, A2RAG: progressive escalation of retrieval effort, about 50 % token / latency cut (abstract).
- arXiv 2609.12746, LAST-CQ: agentic text-to-Cypher; "What works is detecting failure and routing it to a retry";
  2,471 queries (abstract). arXiv 2412.18702 CypherBench (abstract). arXiv 2502.11371 RAG vs GraphRAG (abstract).
- **ChatP&ID 2603.22528 itself (full text; quotes checked against the raw HTML):** §3.1 "The agent iteratively assesses
  whether the retrieved knowledge is sufficient to answer the user query" … "until the information is sufficient or
  the predefined maximum number of tool calls is reached"; §4.1 "Each tool can be called only once per test to
  evaluate its performance without iteration"; §6.2 "its primary limitation emerges when flowsheets span multiple
  pages; because the entire graph must be passed to the LLM for each inference, costs scale linearly with graph size"
  (about ContextRAG; their mitigation is a "topology mode"). **The authors name our setting as their limitation and do
  not measure it.** Our note `2603.22528.md` says "single call": true of the evaluation, not of the architecture.

**Cross-sheet / off-page connector resolution:** no academic method or benchmark found. Only vendor documentation
(Autodesk Plant 3D, Bentley OpenPlant, AVEVA: manual connector linking in authoring tools), the AWS/Everllence claim
above (no method), the IDTA 02012-1-0 DEXPI submodel noting that bundling multiple DEXPI files is a gap in the
specification (search snippet only, not read in full), and the user's own public repository.

**Verdict:**
- **(a) multi-sheet / plant-scale P&ID GraphRAG: claim still open** academically. The commercial list grows
  (AWS/Everllence, May 2026, with "cross-page connectivity restoration"; JGC talk, Nov 2026). Keep the wording "no
  published method or evaluation", never "nobody has built it".
- **(b) strategy vs scale: claim narrowed in framing.** A scale-dependent crossover between retrieval strategies is
  published for text RAG (2506.05690 App. G.5; Self-Route 2407.16833). It is still unmeasured for structured
  engineering graphs and for serialization vs text-to-Cypher vs agent; ChatP&ID predicts it in §6.2 without measuring
  it. Cite both as the general precedent and claim the first measurement on P&ID plant graphs.
- **(c) generic-primitive graph-tool agent: the pattern is taken, including on P&IDs at single-sheet level.**
  General: Middleware/KBQA-Agent 2402.14672, KG-Agent, Graph-CoT, StructGPT, Interactive-KBQA. P&ID: 2609.05880 (seven
  primitives, six-turn budget, 3,000 single-sheet questions); pid-graph-agent (software, one DEXPI file at a time).
  What remains ours: the primitives running over a **cross-sheet item graph** in which off-page connectors and
  identity links are resolved beneath the API; the controlled typed-primitive vs free-form-Cypher agent comparison
  with iteration held equal; held-out question families; the offline cascade with a cost/latency frontier; the scale
  sweep.
- **`overlaps — act`: arXiv 2609.05880.** Run `/paper-intake 2609.05880`; ADR-0034's related-work framing must cite
  it. Library request: Ma et al. 2026 review (10.1007/s11705-026-2685-z).

**Follow-up 2026-10-10 — `/paper-intake 2609.05880` done** → `2609.05880.md` (full text incl. App. A.1–A.18). Confirms
(c): single synthetic sheets only, no off-page connectors; behaviour at the six-turn cap is unstated; tool-result ids
are for citation, not input handles; no serialization or Cypher baseline, so (b) is untouched. Author correction:
arXiv lists the second author as "Sakhinana, Sagar Srinivas" — cite as Gadekar, Sakhinana, Runkana. ChatP&ID note
`2603.22528.md` now carries the dated agent-loop vs single-call-evaluation correction and the §6.2 quote.
