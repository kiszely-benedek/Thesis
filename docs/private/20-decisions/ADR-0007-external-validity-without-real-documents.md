---
adr: 0007
title: Demonstrate the methodology on generated DEXPI plants; realism is built up in a later phase
status: accepted
date: 2026-09-10
revised: 2026-09-13
accepted: 2026-09-13
supersedes: none
---

# ADR-0007 — Demonstrate the methodology on generated DEXPI plants

**Approved by the user 2026-09-13 with amendments** (Q2 → pyDEXPI, P2 wording, scope items in Decision 4).
Status stays `proposed` until the main session verifies revision 2 of `40-design/plant-generator.md`.

## Context

Four inputs, in order:

1. **No real factory documents will come** (user, relaying the professor, 2026-09-10). Roadmap Phase 5 and
   every realism plan built on those documents are void.
2. **A methodology is enough** (professor, relayed by the user, 2026-09-12). Showing a methodology for large
   document sets is acceptable for the thesis and for publication: hundreds or thousands of interconnected
   sheets, describing one plant or several.
3. **Generate simply, as prior work did** (user decision, 2026-09-12). Use random or another easy method; no
   ISO / PIP / Hanford rules if they complicate things.
4. **Amendments** (user, 2026-09-13):
   - build on pyDEXPI, so the output is a real `DexpiModel`;
   - keep the seeded topology (tree, recycle, inter-unit streams, cross-links, inline valves, control loops);
   - rule-grounded realism is a later phase, not excluded;
   - unit = `PlantSection`;
   - utilities come later;
   - one plant now, several next phase;
   - equipment data tables are in scope;
   - rendering to PDF is a later phase.

Input 3 matches the precedent. pyDEXPI's generator "selects P&ID modules at random", and Hirtreiter et al. join
patterns by "a first-order Markov chain-like sampling process with fixed probabilities"
(`10-literature/pid-structural-rules.md` §6.1, §6.2). PIDQA's 64,000 QA pairs sit on 500 synthetic sheets
(`make7020039-pidqa.md`), and ChatP&ID evaluates one file (`2603.22528.md`). None of them argues realism.

What we hold could not anchor realism anyway (measured 2026-09-10, see History). PID2Graph's 762 sheets are
all undirected and carry no text or tags; 750 of them have no off-page connector and are synthetic. The only
real drawings are OPEN100's 12 sheets, with 23 annotated cross-sheet pairs.

**Q1:** how much realism does the thesis argue? **Q2:** where do plant graphs come from?

## Options considered

### Q1 — evidence posture

**P1. Calibrate on PID2Graph** (the 2026-09-10 decision): a `CorpusProfile` reader, a containment report
(EXP-0006), OPEN100 held out. It answers a question the professor no longer asks, and its calibration source
is itself synthetic (`2411.13929.md` line 25).

**P2. Methodology on generated plants; realism is a stated limitation of this phase.** Generator parameters
are swept, never calibrated. Rule-grounded realism (ISO / PIP / Hanford) is **a later phase, built up
gradually**, not excluded. Its cost is one honest paragraph now.

**P3. OPEN100 as the only evidence.** Twelve sheets are a point, not a curve. OPEN100 keeps a narrower role
under P2 (Decision 3).

### Q2 — plant-graph source

**G1. pyDEXPI `SyntheticPIDGenerator`** with our own patterns (H2 in the design note). Verified costs in
pyDEXPI 1.2.0:
- pattern sampling uses the global `random`;
- every sampled pattern is deep-copied, and `DexpiBaseModel.__deepcopy__` assigns fresh `uuid4` ids (measured
  2026-09-13), so a seed cannot reproduce ids;
- `DexpiPattern` accepts piping connectors only, so control loops fall outside it.

**G2. Our own seeded generator emitting a `networkx.DiGraph`** (revision 1). Everything the methodology needs,
by construction. But the output is not a DEXPI model. Adding an exporter (H3) gives two representations that
must be kept equal.

**G3. networkx random digraphs with random labels.** Types independent of topology; no units. Rejected.

**G4. Compose PID2Graph sheets.** Rejected on measured facts (History).

**G5. Our seeded topology logic builds the `DexpiModel` directly with pyDEXPI classes and toolkits** (H1).
The `DiGraph` is derived through pyDEXPI's loader and conceptual abstraction plus a mapping adapter.

## Decision

1. **Q1: P2 as amended.** The thesis demonstrates a methodology on generated plants. Realism is a stated
   limitation **of this phase**; rule-grounded realism is a later phase.
2. **Q2: G5.** Design, schema and adapter in `40-design/plant-generator.md` revision 2 (§2, §3). The design
   carries a kill criterion: fall back to G2 + exporter for the benchmark path if conversion becomes too slow
   or the adapter cannot be kept exact.
3. **What survives from the 2026-09-10 version:**
   - **OPEN100 hold-out: survives, narrowed.** Nothing is calibrated, so the rule protects the **resolver**.
     OPEN100's 23 pairs are a test set for off-page connector linking (EXP-0004), never used to develop label
     parsing.
   - **Containment report, `CorpusProfile`, EXP-0006: optional**, at most one limitations table.
   - **Crossover regressed on corpus properties: survives** as EXP-0002's analysis.
   - **Flow-direction inference: out of scope.** G5 graphs are directed by construction; the
     `edge_direction_flip_rate` sweep in EXP-0003 is optional.
   - **D spike: closed.**
   - **Abstention:** the frequency claim stays dropped; EXP-0005 uses questions made unanswerable by construction.
   - **pyDEXPI is now on the benchmark path**, behind the ADR-0003 adapter (`src/plantgraph/adapters/pydexpi_*.py`).
     The same adapter serves EXP-0001 on `DEXPIEX01.xml`.
4. **Scope amendments (user, 2026-09-13):**
   - unit = `PlantSection`;
   - utilities are a later generator step;
   - one plant per corpus now, several in the next phase;
   - equipment data attributes are visible, queryable node properties;
   - rendering to one PDF with data tables is a later phase;
   - reading PDFs back is a separate digitization stage;
   - the method's input stays per-sheet graphs (design note §11).

## Rationale

**Why P2.** The claim is internal: the ranking of retrieval strategies changes with corpus scale. Measuring
that needs a dial, not a likeness (ADR-0004: "A benchmark whose difficulty can be swept is worth more here than
a small realistic one"). Deferring realism, rather than excluding it, keeps the door open without putting it on
the critical path.

**Why G5 over G2.**
- **Matches the prior-work pipeline.** It gives the user's requirement, a real `DexpiModel`, and the same
  pipeline as prior work: DEXPI → pyDEXPI → graph (`2502.18928.md`, `2603.22528.md`).
- **One source of truth.** The graph is derived from the model, never maintained beside it.
- **Keeps what G2 gave.** Seed, branching, typed relations and direction all still come by construction.
- **Measured cost (prototype, pyDEXPI 1.2.0, 2026-09-13):**
  - identical JSON bytes for the same seed across processes;
  - seed → `DiGraph` in 15.1 s at 1,000 units (5,470 equipment), once pyDEXPI's quadratic instance collection
    is replaced by a linear subclass whose output was identical at 5 and 50 units.

**Why G5 over G1.** G1's reproducibility problem is structural (uuid ids on every pattern copy), and its
connector model cannot express control loops. G5 uses the same classes and toolkits without the sampler.

## Consequences

**Enables:**
- a `DexpiModel` per generated plant, persisted losslessly as pyDEXPI JSON;
- DEXPI data attributes for equipment tables;
- one conversion path shared by EXP-0001 and the scale sweep;
- a model to render from in a later phase.

**Costs:**
- **pyDEXPI becomes a hard dependency.** Version 1.2.0 needs Python ≥3.12, so `pyproject.toml` must be raised
  from ≥3.10.
- **Proteus XML export is equipment-only** in pyDEXPI 1.2.0; a full exporter is new work if a later phase needs it.
- **We override one private `GraphLoader` method** on a pinned version, guarded by an equality test.
- **Adapter mapping.** pyDEXPI emits no prior-work relation names, so the adapter maps them.
- **No engineering plausibility claim.** The generated plants are not engineering-plausible in this phase, and
  are not claimed to be.

**Forecloses (this phase):**
- any claim that the pipeline works on real industrial documents;
- any realism claim for the benchmark;
- any statement about frequencies in real P&IDs.

**Other ADRs.** On acceptance, append outcome-log entries (accepted ADRs are not edited):
- **ADR-0004:** the inversion decision stands; "pyDEXPI's synthetic P&ID generation" as the source is refined
  to "DEXPI models built with pyDEXPI by our own seeded generator".
- **ADR-0005:** OPEN100's role narrows to the EXP-0004 test set.
- **ADR-0003:** the thin-adapter action item is met by `adapters/pydexpi_*.py`.
- **ADR-0002 and ADR-0006:** unaffected.

**Index (proposed wording; the user edits the index):** append to the claim *"Demonstrated on generated DEXPI
plants of swept size; not evidenced on real factory documents; rule-grounded realism is a later phase."*
Replace roadmap Phase 5 with *"Limitations stated. Later phases: rule-grounded realism, utilities, several
plants, rendering. Optional containment table; EXP-0003 degradation curve."*

**Revisit if:**
- an examiner asks for realism evidence (bring the rule-grounded phase forward, or P1);
- a pyDEXPI upgrade breaks the linear loader or the adapter (kill criterion, design note §2).

## History

- **2026-09-10:** "A + E, D as a one-day spike, C as the residual, B rejected" (423 lines, never accepted; full
  text at commit `39eeae7`). Its facts still stand:
  - PID2Graph census: 762 sheets, all 96 off-page connectors in OPEN100, every graph undirected, no text or tags;
  - `Dataset PID` is synthetic;
  - composition was rejected because a corpus without tags or direction hosts neither the baseline nor
    tag-based resolution.
- **2026-09-12:** revised to P2 + G2 (commit `5585026`).
- **2026-09-13:** approved by the user with amendments; revised to P2 as amended + G5.
- **2026-09-13:** revision 2 verified by the main session and set to `accepted`, per the user's approval of
  2026-09-13. Checks: the frozen sections of `plant-generator.md` are byte-identical to HEAD; a re-run of the
  tiny prototype reproduced the equipment-only Proteus export, pyDEXPI's edge labels and the adapter's mapping
  (8 nodes, 9 edges, all mapped); pyDEXPI 1.2.0 metadata declares `Requires-Python: >=3.12`. The 15.1 s at
  1,000 units figure is the architect's measurement and was not re-run. The open items in `plant-generator.md`
  §10 (Python 3.12, Proteus, DISCHARGE mapping) do not reopen this ADR.
