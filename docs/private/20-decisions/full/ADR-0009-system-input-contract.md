---
adr: 0009
title: Make the per-sheet graph the system's input contract; feed it from a DEXPI Proteus importer as well as the splitter
status: accepted
date: 2026-09-25
accepted: 2026-09-26
supersedes: none
---

# ADR-0009 — The system's input contract

## Context

ADR-0008 (R1) accepts a DEXPI/Proteus file as a "drawing". That settles what counts as input in principle.
It does not settle **what the Q&A system actually accepts**, and today the answer is: nothing that is a
DEXPI file.

Facts as of 2026-09-25:
- **The benchmark path never touches a DEXPI file.** Our seeded builder produces a `DexpiModel`, the
  ADR-0003 adapter turns it into a schema `DiGraph`, and the splitter cuts that into `SheetGraph`s
  (`00-index.md`, "Current phase"; ADR-0007 decision 2). The generated model is persisted as **pyDEXPI JSON**
  (`src/plantgraph/adapters/pydexpi_io.py`, `save_json` / `load_json`).
- **ADR-0007 decision 4: "the method's input stays per-sheet graphs".**
- **pyDEXPI 1.2.0 exports Proteus XML for equipment only** (ADR-0007, Costs;
  `pydexpi_io.save_proteus_equipment_only`).
- **pyDEXPI's Proteus parser reads piping and instrumentation too** (`pydexpi_io.load_proteus_equipment_only`
  docstring). For a full external file (EXP-0001) that docstring already says the adapter must run on the
  loaded model.
- **EXP-0001 needs an external file.** ChatP&ID evaluates on `DEXPIEX01.xml` "from the DEXPI standard"
  (`10-literature/2603.22528.md`, Evaluation). It is **not in the repo** and not in the installed pyDEXPI
  package. Candidate files exist publicly (gitlab.com/dexpi/TrainingTestCases, e.g. `C01V01-SAG.EX01.XML`;
  pyDEXPI's GitHub `data/` has `C01V04-VER.EX01.xml`); **which one ChatP&ID means is unverified.**
- `SheetGraph` (`src/plantgraph/benchmark/sheet_graph.py`) is `sheet_id`, a `networkx.DiGraph`, and
  `connectors: list[OffPageConnector]`.

## Options considered

**I1. Per-sheet schema graphs only** (current state). The system accepts `SheetGraph`s and nothing else.
Zero new work. But under ADR-0008 the system then accepts **no drawing at all**: R1 is true in principle and
never exercised, and EXP-0001 has no way in.

**I2. Per-sheet DEXPI Proteus XML files.** The system accepts only Proteus files; the synthetic corpus is
written out as one Proteus file per sheet. The most faithful reading of R1: every input is a real drawing
format. Cost: a **full Proteus exporter** (piping, instrumentation, off-page connectors), which pyDEXPI 1.2.0
does not have, plus a way to produce per-sheet DEXPI models — either a second splitter at the `DexpiModel`
level or a back-mapping from sheet graphs to DEXPI. Neither exists; neither is on the thesis claim's path.

**I3. Per-sheet pyDEXPI JSON models.** Lossless persistence already exists. But the split would have to happen
at the `DexpiModel` level, not the graph level (the same second splitter as I2), and **pyDEXPI JSON is a
library serialization, not a DEXPI exchange format** — the DEXPI exchange file is Proteus XML (the file
ChatP&ID feeds its "Proteus file direct" baseline, `2603.22528.md`). I3 pays most of I2's cost without
buying the "drawing" reading.

**I4. The sheet graph is the contract; a DEXPI Proteus importer is a second producer.** The system accepts
`SheetGraph`s. Two producers fill that contract:
1. the splitter, over generated plants (exists);
2. a **Proteus importer**: `ProteusSerializer().load` (pyDEXPI) → the ADR-0003 adapter
   (`src/plantgraph/adapters/pydexpi_adapter.py`) → schema `DiGraph` → one `SheetGraph` per file.
It is used for the EXP-0001 file and for any real DEXPI file that turns up. Mostly existing parts; the new
code is the wrapper and its tests.

## Decision

**I4 for the deadline. I2 is the upgrade path**, tied to a future Proteus-exporter ADR.

**Contract rule (new, applies to every producer):** a `SheetGraph` may carry only what is **visible on that
sheet** — tags, connector labels (partner sheet, partner tag, line number), attributes. It must not carry
cross-sheet identity. This matters for ADR-0010: today the splitter's sheets **share node ids across sheets
for the occurrences of one identity group** — `rejoin()` merges reference occurrences into the home node
purely by node-id collision (`src/plantgraph/benchmark/rejoin.py` lines 49–56). A resolver reading those ids
would be reading the answer key. The coder must make sheet-local ids (or a test that renames them) part of
the contract; whether any other field leaks the manifest is **unverified** and is a check for the design note.

## Rationale

- **It makes R1 real at the lowest cost.** The system demonstrably accepts a DEXPI drawing, on the one file the
  baseline needs, through code that is mostly already written and tested.
- **The contract is where the thesis claim lives.** Retrieval strategies, the resolver and the crossover
  experiment all consume sheet graphs. Keeping one contract means EXP-0001 (single sheet, imported) and
  EXP-0002 (thousands of sheets, generated) run the same downstream code — so a difference between them is a
  scale effect, not a pipeline difference.
- **I2 stays additive.** When a full exporter exists, the synthetic corpus can be written as per-sheet Proteus
  files and read back through the same importer; `import(export(sheet)) == sheet` becomes a test. Nothing
  built under I4 is thrown away.
- **Boring option.** Proteus export is not the contribution (ADR-0001's novelty budget).

## Consequences

**Enables** — EXP-0001 can run; the ADR-0008 branch point is one concrete type; any real DEXPI file enters by
the same door.

**Costs — state this in the thesis:** **the synthetic multi-sheet corpus never exists as DEXPI files.** The
system is shown to accept a DEXPI drawing on **one** external file (the EX01 file); the scale results are on
sheet graphs derived from generated `DexpiModel`s. Proposed limitation wording: *"The Proteus importer is
exercised on a single public DEXPI example; the multi-sheet corpora are generated as DEXPI models and enter
the system as per-sheet graphs, not as exported Proteus files."*

**Unverified:**
- that pyDEXPI 1.2.0's Proteus importer reads the chosen EX01 file without error;
- that the ADR-0003 adapter maps every pyDEXPI class in that file (it was built against our generator's
  output; unmapped classes must be reported, not dropped);
- which public file is ChatP&ID's `DEXPIEX01.xml`;
- how a real DEXPI file's off-page connectors would map onto `OffPageConnector` — not needed for EX01 (one
  sheet), needed before any real multi-sheet DEXPI set.

**Needs** — a short design note in `40-design/` for the importer (inputs, outputs, the unmapped-class report,
the contract rule and its test) before the coder starts.

**Revisit if:**
- a Proteus-exporter ADR is accepted (move to I2);
- the professor's written answer to ADR-0008 (a) asks for a file-based input on the whole corpus;
- pyDEXPI cannot load the EX01 file (then EXP-0001 needs another route, and this ADR's cost estimate is wrong).

## Outcome log

- **2026-09-26:** Accepted by the user 2026-09-26 as recommended (I4). **Verified the same day:** pyDEXPI 1.2.0's `ProteusSerializer().load` reads `data/external/C01V04-VER.EX01.xml` (from pyDEXPI's GitHub `data/`, 445,726 bytes, sha256 `a2b172f0…b809c`) in 0.36 s; `load_complete_graph` gives 214 nodes / 376 edges, `abstract_conceptual_graph` 36 nodes / 39 edges. ChatP&ID reports 212 nodes condensed to 53 — **the gap is unexplained** and is a check for EXP-0001. That this is ChatP&ID's `DEXPIEX01.xml` is supported, not proven: the paper cites it as "DEXPIEX01.xml from (Theißen and Wiedau, 2021)", and the tags in its sample questions (P4712, T4750) occur in the file (3 and 4 times).
