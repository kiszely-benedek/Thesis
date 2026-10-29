# Dissertation index

The map. Loaded at the start of every session by `/catchup`. Keep it short and keep it true.

## Official title (professor, by email, 2026-09-25)

> **Tudásgráf-építés műszaki rajzokból és P&ID diagramokból skálázható Q&A rendszerhez**
>
> *Knowledge-graph construction from technical drawings and P&ID diagrams, for a scalable Q&A system.*

**This is the registered topic. Read it against the claim below — they are not identical, and the
difference is the single most important open question in the project.**

| The title says | Status in the project today |
|---|---|
| "knowledge-graph construction" | Built — `graph/schema.py`, the generator, the splitter. **Framing confirmed 2026-09-20: the pipeline leads.** |
| "**from** technical drawings **and P&ID diagrams**" | **Resolved 2026-09-25 (ADR-0008, accepted):** the professor (relayed by the user) says a **DEXPI/Proteus file counts as a drawing** — no pixels → graph front end. **Verbal only; written confirmation pending.** Still open: does "technical drawings **and** P&IDs" expect a second drawing type? |
| "scalable" | Measured 2026-09-20: 4,015 sheets, 43,043 nodes, 49.42 s, 786 MiB (`30-experiments/2026-09-20-scale-smoke.md`). |
| "Q&A system" | **Built and measured (2026-10-11):** cascade_v3 (Cypher tier → graph-tool agent, GPT-6 Luna), frozen at F1 `07d4029`; sealed test EXP-0002 acc@120 0.937 (H100) / 0.917 (H1000). Live English demo app (`plantgraph.demo.app`, last commit `e2b22ad`). |

**~~The question that must be resolved before phases are planned~~ — answered 2026-09-25, see ADR-0008.** Kept for the record: does "műszaki rajzokból" require a
pixels-to-graph front end, or is a DEXPI/Proteus file — which *is* the machine-readable form of a drawing
— an acceptable input? The honest answer is that **only the professor can settle it**, and it changes the
phase plan substantially:
- **If DEXPI files count:** the current scope stands, and PDF reading stays the conditional backlog item.
- **If pixels count:** a digitization front end enters scope, which ADR-0001 explicitly excluded as a
  crowded problem (PID2Graph already does it at 75.46 % edge mAP), and the plan needs a new phase.

Note also that the title does **not** mention the retrieval-inversion claim. That is consistent with the
2026-09-20 framing decision (pipeline leads, crossover as supporting evidence), and with the professor's
2026-09-12 statement that a *methodology* is acceptable for the thesis and for publication.

## Thesis claim

> The optimal retrieval strategy for GraphRAG over engineering diagrams is a **function of corpus scale**. The published optimum — serializing a condensed single-sheet graph into the prompt (ChatP&ID, 0.91 accuracy) — is an artifact of single-page evaluation and inverts at plant scale. This work finds the crossover points and builds the hierarchy that survives past them.

**Supporting contributions**
1. A public **multi-sheet P&ID benchmark** with cross-page ground truth, built by splitting large plant graphs across pages with off-page connectors.
2. **Cross-sheet entity resolution** measured properly — off-page connector linking and tag-based equipment identity across drawings.

## Current phase

**2026-10-23: all measurements done; demo finished (ADR-0055/0056, `ce9bb60` … `e2b22ad`). From 10-22 the user is in learning mode. 10-23: README rewritten; the user publishes the tooling and `docs/` in one commit (reverses the 09-19 local-only rule). 2048 tests pass on `e2b22ad`.**

**2026-10-29: generator v2 done (ADR-0057/0058/0059, T0–T16 `0ba680a`…`917b4c3`); re-measurement EXP-0007 (ADR-0060) found F1 weaker on v2 (D100g2 cascade_v3 0.896); the separately labelled tuned system V2T (ADR-0061) was tuned on X100g2s211 (3 rounds) and validated once on held-back X100g2s212 / X1000g2s213: cascade_v4_iso 154 / 156 of 163 vs F1 145 / 144 (`c51c83e`, `30-experiments/EXP-0007-V2T-validation.md`). Next: E7 freeze of V2T-A, then R4 (ladder, tiers + ContextRAG H1g2–H10g2) and R5 (sealed, + F1 baseline). Progress: `50-progress/2026-W44.md`.**

**2026-10-16: demo polish ADR-0055: DP-T1…T4 committed, DP-T5 uncommitted, DP-T6…T10 next.**

**2026-10-11: sealed test run done (EXP-0002, ADR-0053): frozen cascade_v3 (GPT-6 Luna, ADR-0050/0052) on held-out H100/H1000 — headline acc@120 0.937 / 0.917, $0.00065 / $0.00071 per question, primary claim Q4 PASS, K1 FAIL on headline; infra cost measured (INFRA-1, ADR-0051). EXP-0001 done (ladder 1–30 sheets: ContextRAG 0.824 → 0.658 vs cascade 0.941 → 0.947, X1 PASS, X2 FAIL — no single-sheet crossing; EX01 0–1/5). Next: the clickable results UI.**

**2026-10-06: phases 1–3 built (incl. the self-flag cascade and the graph-tool agent); phase 4 dev runs done on D100/D1000; cascade v2 with the agent as tier 2 is next, then the sealed test run.** *(2026-09-26: phase 1 closed except the freeze.)* What follows is the phase 1 record.

**Phase 1 in progress.** **Updated 2026-09-20:** the git history was rewritten to strip AI-tooling traces, so the old hashes (`85d23f2`, `5585026`) no longer exist. Everything below is now **committed**: the splitter is `96aeea1`, and `42cc83d` carries the graph schema and validators, pipe/signal connectors with visible labels, the `by_unit` strategy, and **the plant generator end to end** — `plan_plant` (seeded topology) → `DexpiPlantBuilder` (real pyDEXPI `DexpiModel`) → adapter → schema `DiGraph` that the splitter cuts, with an oracle-equality test tying the pyDEXPI pipeline to a test-only graph builder; plus a comment pass (233 tests at that point). Python ≥ 3.12, `pydexpi==1.2.0`. **ADR-0007 accepted 2026-09-13.** Step 6 (integration) turned out to be **already covered** by `tests/test_generator_integration.py` (invariant 7 line 30, sheet-schema validity line 45, invariant 8 line 57); its only missing assertion was the §4.8 one, which fell with the datasheet decision. **Step 7 (scale smoke) ran on 2026-09-20 at two sizes:** 1,000 units → 1,378 sheets in 14.07 s / 278.1 MiB, and **2,900 units → 4,015 sheets in 49.42 s seed → `DiGraph` (53.96 s including the split) and 785.7 MiB** — against a 600 s kill criterion, so **H1 stands** with a 12× margin at the larger size (`30-experiments/2026-09-20-scale-smoke.md`). Growth is **slightly superlinear, not quadratic** (size ×2.93, time ×3.51, memory ×2.83). **"Hundreds or thousands of sheets" is now measured, not estimated.** **238 tests today; ruff, format and mypy --strict clean.** Not built: utilities (step 8). Equipment data (step 3b) is **struck, not pending** — see the open questions.

## Roadmap

**Accepted 2026-09-26 (ADR-0010, ADR-0011).** Calendar and detail: `40-design/thesis-phase-plan.md` revision 2.

| Phase | Goal | Weeks | Status |
|---|---|---|---|
| 0 | Repo, docs, agents | — | closed |
| 1 | Synthetic multi-sheet benchmark | — | done except the freeze; utilities cut |
| 2 | **KG construction**: Proteus importer, resolver, Neo4j loader, `ingest` CLI | W40 | design note in progress |
| 3 | **Q&A system** + single-sheet baseline (EXP-0001 on EX01, 19 questions) | W41 | design note in progress |
| 4 | **Headline: plant-scale Q&A** at ~100 / ~1,000 (/ ~4,000) sheets + crossover sweep (ADR-0015, accepted) | W42–W43 | |
| 5 | Resolver evaluation (EXP-0004: OPEN100 23 pairs + label dials) | W43 | |
| 6 | Later phases (realism, utilities, several plants, rendering, drawing reading) | — | future work (ADR-0011) |
| 7 | Write-up — BSc, Hungarian (since 2026-10-05) | W39–W44 | |

## Layout

| Path | Holds |
|---|---|
| `docs/private/ALLAPOT.md` | **the user's one-glance status page (Hungarian)** — phases, tasks with commits, checkpoints vs calendar, what awaits the user; updated by `/log-progress` every session |
| `docs/private/10-literature/` | one note per paper + reading list + novelty log |
| `docs/private/20-decisions/` | ADRs — numbered, dated, immutable once accepted |
| `docs/private/30-experiments/` | one note per run + the running results table |
| `docs/private/40-design/` | component designs, graph schema, pipeline specs |
| `docs/private/50-progress/` | weekly log, appended by `/log-progress` |
| `docs/Notes/` | teaching notes on topics being learned (`/explain`) |
| `docs/Academic_papers/` | paper PDFs |
| `docs/Technology_research/` | technology deep dives |

## Fixed decisions

- Data model: **Pydantic** · DEXPI conversion: **pyDEXPI** (AGPL-3.0, ADR-0003 accepted 2026-09-10) · Graph store: **Neo4j LPG only** (ADR-0002 accepted 2026-09-06; its RDF arm dropped by ADR-0012 K3, 2026-09-26)
- **Title reading (ADR-0008, accepted 2026-09-25):** a DEXPI/Proteus file counts as "a drawing"; no digitization front end. Professor's answer, relayed verbally by the user; written confirmation pending.
- **Thesis:** BSc szakdolgozat, BME VIK mérnökinformatikus, TMIT; Hungarian (since 2026-10-05, was English). Equipment datasheets: **out of scope — not part of this thesis**. **P&IDs only** (ADR-0008 item b).
- **Accepted 2026-09-26:** ADR-0009 (input contract I4), ADR-0010 (ordering O3), ADR-0011 (scope cuts as recommended), ADR-0013 (evaluation E3), ADR-0014 (LLM policy M3, via **OpenRouter**). **Also accepted 2026-09-26:** ADR-0012 (K3 — no RDF store; ADR-0002 superseded in part), ADR-0015 (headline: one sweep, H100/H1000 table, public release), ADR-0016 (unknown DEXPI classes → generic node, never dropped), ADR-0017 (splitter walks depth-first; headline corpora at 16 equipment/sheet), **ADR-0018 → A1** (no equipment attributes in generated plants). ~~ADR-0020~~ superseded by **ADR-0021 (same day): no equipment/datasheet data anywhere**, not even from real files (out of scope — not part of this thesis); ChatP&ID's datasheet questions are listed as out of scope in EXP-0001. Identifiers (part names like 66KL21) are kept.
- Models (ADR-0006 accepted 2026-09-06): planning on **Opus**, **Fable 5.1** only on explicit request; implementation on **Sonnet**; coders run **sequentially**, the parallel skill was dropped
- **Plant graphs (ADR-0007, accepted 2026-09-13):** DEXPI models built with pyDEXPI classes and toolkits by our own seeded builder, converted by the pyDEXPI loader, the conceptual abstraction and our adapter into the schema `DiGraph` (`40-design/plant-generator.md` revision 2). Methodology contribution; realism a later phase; OPEN100's 23 pairs held out for EXP-0004; unit = `PlantSection`.
- Test dataset: **PID2Graph** (Zenodo 14803338, 9.3 GB) — validates digitization, **not** scale. See ADR-0001. Local path on this machine: `C:/Users/Otthon/Desktop/PID2Graph` (the old `b.kiszely` path was another machine's).
- **PID2Graph contents, verified 2026-09-10 by counting every file** — three subsets, not two: `Dataset PID` (500 sheets, graphml+png), `PID2Graph Synthetic` (250 sheets, graphml+jpg), `PID2Graph OPEN100` (12 sheets). `Patched/` holds the same drawings pre-tiled for detector training. **Only OPEN100 carries off-page connectors: 12 of 12 sheets have `inlet/outlet` nodes; 0 of the other 750 sheets have a single one.** The extra 750 sheets therefore add topology and scale but **no cross-sheet ground truth whatsoever**. Node-label vocabulary is generic and text-free throughout (connector, crossing, valve, general, instrumentation, background, arrow, tank, pump) — no tags, no line numbers. Nodes/sheet: `Dataset PID` 366–695 (mean 456), `Synthetic` 97–170 (mean 131), OPEN100 181–675 (mean 386). ~~**Unverified:** whether `Dataset PID` is Paliwal et al.'s synthetic Dataset-P&ID.~~ **Verified 2026-09-10 from our own paper note** `10-literature/2411.13929.md` line 25, which lists the PID2Graph test sets as "PID2Graph Synthetic, PID2Graph OPEN100 (12 real reactor plans), **Dataset-P&ID (500 synthetic, Paliwal et al.)**". So `Dataset PID` **is synthetic**, and the consequence must be stated plainly wherever external validity is discussed: **OPEN100's 12 sheets are the only real drawings in the entire project — 750 synthetic, 12 real.** Corroboration: that note records OPEN100 at mean 382±125 nodes/plan against the 386 measured here. On-disk sizes: `Complete/` 3.1 GB + 191 MB + 11 MB, `Patched/` 6.1 GB + 3.0 GB + 407 MB.
- **Every graphml in PID2Graph is undirected — 762 of 762 sheets, verified 2026-09-10 by grepping every file for `edgedefault`.** Flow direction is fundamental to a P&ID and is **not in the data**. This is a problem no earlier note accounted for: the splitter takes an `nx.DiGraph` and its default `flow_greedy` strategy walks downstream from feed nodes, which is meaningless without direction. Possible recovery routes, **all unverified**: arrow geometry (OPEN100 has 451 `arrow` nodes with bboxes), equipment semantics (a pump implies suction/discharge), or assigning direction arbitrarily as a stated modelling assumption. pyDEXPI-generated plant graphs would be directed by construction, which may reverse the cost ranking in ADR-0007.

## Open questions

- ~~LPG vs RDF/SPARQL — ADR-0002 is `proposed`, not decided~~ **Decided 2026-09-06:** LPG primary, RDF alongside (bounded, kill criterion end of phase 3). Needs an `architect` design note for the RDF side.
- ~~Parallel coder subagents — ADR-0006~~ **Decided 2026-09-06:** dropped; sequential coders, model policy recorded.
- ~~ADR-0003 (AGPL) — two questions await the professor~~ **Decided 2026-09-10:** the professor answered "we will be AGPL compliant, do not worry". ADR-0003 is `accepted`; the provisional licence application stands, pyDEXPI may be imported. **All six ADRs are now closed.**
- ~~Is there a P&ID ontology, and should we build one? (professor, 2026-09-08)~~ **Answered 2026-09-08** by the researcher's sweep (`10-literature/ontology-landscape.md`): ontologies exist (ISO 15926 / IDO / PCA RDL), DEXPI is an information model not an ontology, an OWL DEXPI is being built by TotalEnergies, no paper uses any of them for retrieval, and DEXPI has no cross-drawing identity construct. The contribution is a ~10-term multi-sheet extension plus a generated mapping, never "a P&ID ontology". Teaching note: `docs/Notes/ontologia-pid.md`.
- **PIDQA** (MAKE 7(2):39, 2025) found 2026-09-08: 64,000 QA pairs over 500 single sheets, node labels are integers 1–32. Largest P&ID QA eval to date; raises our evaluation bar, does not touch cross-sheet. Needs a proper `/paper-intake` when the full text is reachable as HTML.
- **The professor will not be sending documents at all (user, 2026-09-10).** Phase 5 as written is void, and with it the external-validity plan. Everything must be built from PID2Graph. Consequences proposed in **ADR-0007** (`proposed`). **2026-09-12, professor (relayed by the user):** a *methodology* for large document sets — hundreds or thousands of interconnected sheets, one plant or several — is acceptable for the thesis and for publication. Real factory documents are therefore not required; external validity becomes a stated limitation, not a blocker. **OPEN100 spike (ADR-0007 decision 4), 2026-09-12:** the full drawing package is **not** reachable from open-100.com as static HTML (7 pages checked, no P&ID, PDF, drawing number or licence text); remaining routes need the user (real browser, or contacting the Energy Impact Center). Details in ADR-0007 open question 4.
- **P&ID structural rules swept 2026-09-12** (`10-literature/pid-structural-rules.md`, teaching note `docs/Notes/pid-szerkezeti-szabalyok.md`). **Codified and usable:** local equipment arrangements and connector labelling. **Not codified anywhere readable:** how a plant is split into sheets, and how many items a sheet holds — no source gives a number, so the sheet budget stays a swept parameter (the unsourced "5–15 items per sheet" in `splitter.md` §3 is struck). Quotes checked against the source PDF by the main session, verbatim: HNF-64103 (Hanford, 2020, public; agrees with PIP "except as noted") §3.2.2 flow "from sheet to sheet", §3.2.4.2 "In general, control valve stations have block valves and a by-pass", §3.2.5.1 lines leaving a diagram labelled "Conveyed Fluid / Source / Destination / Drawing Number sheet and Zone", pump discharge check valve "between block and pump", §3.2.5.2 "Main utility headers are not shown on the unit P&ID". PIP PIC001 itself: no legitimate full text reachable.
- **Four findings against the splitter as built** (verified against the code 2026-09-12): (1) `utility_aware`'s `_detect_hubs` moves high-degree *equipment* to hub sheets, but the rules move *utility headers* and keep consumers in place, and a utility crossing is one-to-many, which `ConnectorPair` cannot express; (2) `OffPageConnector` lacks the codified label fields (fluid/service, source/destination, zone) and cannot distinguish same-unit vs cross-unit or pipe vs signal cuts; (3) `modularity` is only a proxy for "by unit" — units are declared labels, not graph communities; (4) `IdentityGroup` duplication is grounded in OPEN100 observation, not in any rule. **Not yet actioned** — needs an `architect` revision together with ADR-0007.
- **pyDEXPI sample patterns** (GitHub `master`, `data/dexpi_sample_patterns/`, AGPL-3.0; not in the pip package): 10 distributions (verified), 23 patterns (researcher, read with a non-executing unpickler), zero instruments, zero check valves, provenance undocumented. **Reasoned, not run:** every middle pattern has one inlet and one outlet, so the random generator can only build a chain or one ring — no branching, no utilities — which would make `flow_greedy`, `modularity` and `utility_aware` cut almost identically. A rule-grounded pattern library has to be written by us.
- **Decided 2026-09-12 (user): generate plants simply, the way prior work did** — random or another easy method; do not build the generator on ISO/PIP rules if it complicates things. The rules sweep stays on file as background. Formalised in ADR-0007 and `40-design/plant-generator.md`. **Refined 2026-09-13 (user):** generation is built on pyDEXPI (output a real `DexpiModel`), and rule-grounded realism is a later phase, not excluded — see Next action.
- **Ontology (professor's question, revisited 2026-09-12):** still needed, but on the **query side** — a minimal graph schema (node classes aligned with DEXPI/pyDEXPI, relation types, plant → unit → sheet containment, off-page connectors, cross-sheet identity), per `ontology-landscape.md` §5. Not construction rules, and not "a P&ID ontology". Defined in the plant-generator design note.
- **OPEN100 PNGs from the site (2026-09-12):** the two images the user saved from the reactor coolant page are pixel-identical to PID2Graph OPEN100 sheets 5 and 6. No new sheets.
- **Framing (user, 2026-09-20): this is an engineering master's thesis, and the pipeline leads.** The user's words: *"im an engineering student, so its a thesis."* The deliverable is **a methodology and a working system for plant-scale multi-sheet P&ID retrieval** — ingest many sheets, resolve their cross-references into one plant graph, retrieve over it — with the scale-dependence claim as **the evidence justifying the design**, not as the headline discovery. **Nothing is superseded:** ADR-0001 scopes the work on plant scale and treats the claim as a *benefit* of that scope, not an obligation; and the professor already accepted a methodology contribution for "hundreds or thousands of interconnected sheets" on 2026-09-12. **Practical consequence:** phase 4 (cross-sheet entity resolution) and the retrieval hierarchy are the centrepiece; EXP-0002's crossover is supporting evidence. **What does not change:** the experiments still have to happen — without them the design choices are asserted rather than justified.
- **Equipment datasheets dropped (user, 2026-09-20).** *"we dont need to do anything with datasheets, thats important, just the scaling interconnecting."* Step 3b (§4.8) was started and reverted uncommitted the same day; requirement **N8 falls with it**, and the DISCHARGE question (answered `differentialPressure` an hour earlier) is moot. `plant-generator.md` §4.8, §9 step 3b, §10 Q5 and the N8 row carry struck banners. **No code ever shipped for it.** The project's scope is now explicitly: **scale and interconnection.**
- **Ontology, professor's remark relayed 2026-09-20:** *"maybe it's overkill to use ontology for connecting sheets or putting them into hierarchy."* **No position changed, because there was nothing to change:** the sheet hierarchy and the cross-sheet links are already plain graph terms in `graph/schema.py` — `NodeClass.DRAWING_SET`, `NodeClass.SHEET`, `Relation.HAS_SHEET`, `Relation.IS_DRAWN_ON`, `Relation.CONTINUES_AS`, `Relation.SAME_TAGGED_ITEM_AS` — plus `ConnectorPair` / `IdentityGroup` in `benchmark/models.py`. **We do not use an ontology to connect sheets and never did.** The ontology strand is only the RDF comparison arm's vocabulary (ADR-0002), which keeps its own kill criterion at the end of phase 3. Teaching note written for the user: `docs/Notes/sajat-ontologia-leltar.md` (what we build, term by term, and what each is anchored to). **User decision, 2026-09-20: keep the ontology strand as it stands** (*"I think we can keep it"*), given before reading the note, so it is a provisional keep rather than a considered one. **ADR-0002 is unchanged and needs no ADR.** The RDF arm keeps its existing bounded scope and its end-of-phase-3 kill criterion — that criterion, not a new decision, is what will settle it. **Revisit if** the note changes the user's mind, or if the professor's remark turns out to have meant the RDF arm too.
- **Full Proteus exporter — user leaning, 2026-09-20:** *"We will need this I think."* pyDEXPI 1.2.0 exports **equipment only**, so a renderer or any external DEXPI tool would need piping and instrumentation modules too. **Not a decision and no work started**; it belongs to the rendering phase (ADR-0007). It has a real alternative (write it ourselves vs contribute upstream to pyDEXPI under AGPL-3.0), so it becomes an **ADR** when the rendering design starts. Recorded in `plant-generator.md` §10 Q2.
- **Backlog, conditional on time (user, 2026-09-20):** reading **real PDFs** into the scalability pipeline, "after a discovery". Explicitly *after* the scaling result, not before. Needs a `researcher` sweep first — what PDF → graph extraction yields at plant scale, and whether PID2Graph's detectors are reusable — before any design note. **No work started.**
- Is "insufficient information" actually common in real P&IDs? Unverified assumption, and **no longer resolvable** by waiting for real documents. Either it is answered from OPEN100's 12 sheets or it is dropped as an assumption.
- ~~Are OPEN100's 12 sheets one coherent plant?~~ **Answered 2026-08-25 by file inspection: YES.** One nuclear plant (OPEN 100), 4 systems spanning 2 sheets each, with real off-page connectors naming partner sheet + grid cell. **But the GraphML annotations contain no text or tags** — the cross-sheet truth is in the images only, and is recoverable with ~96 connector labels of annotation work. *(An earlier entry claimed the opposite; it was unverified and wrong.)*
- ~~Should we annotate OPEN100 for a real validation set?~~ **Decided 2026-08-25: yes** — ADR-0005 accepted, design in `40-design/open100-annotation.md`.
- Grid-cell interpolation (open100-annotation.md open question 2) is still not implemented — a handful of pairs were confirmed by target+line only, not by an independently-computed grid position.
- The `"pump"` label in PID2Graph's GraphML does not reliably mean pump equipment — on sheet 5, all six `pump`-labeled nodes are flow-element instrument bubbles. The RCS-PU-102A/102B tag identity is confirmed **visually** but has no resolvable graphml node on either sheet, so it is documented, not encoded as an `IdentityGroup`.

## Next action

**Updated 2026-10-23.** User-facing status: `ALLAPOT.md`. Latest log: `50-progress/2026-W43.md`.
**The chat is the user's single source of truth** (CLAUDE.md). **The thesis is written in Hungarian** (2026-10-05).

1. The user commits the README and the tooling/`docs/` publication (commands in the 10-23 chat).
2. Teaching lessons in Hungarian (big picture → benchmark → KG → Q&A → experiments → ADRs → code map).
3. Optional: realism backlog (`10-literature/real-pid-composition-2026-10.md`), H4000 Q&A run.
4. Data in `data/` (plants, questions, runs, caches, reports, demo config) — committed since 2026-10-23, see `data/README.md`. Neo4j holds one plant at a time.
