---
adr: 0057
title: Build generator v2 from process patterns with standard trims and ISA-5.1 instruments, beside a frozen v1, and measure it with the frozen system
status: accepted
date: 2026-10-25
supersedes: none. Opens the "rule-grounded realism, later phase" that ADR-0007 deferred; amends nothing accepted. Extends ADR-0044's tag rule to four control-valve bodies. Promotes 49 pyDEXPI classes into the schema under ADR-0016 rule 4 (named questions: §10 of the design note). ADR-0021, ADR-0025, ADR-0028, ADR-0053 (F1) carry over unchanged.
design: 40-design/generator-v2-realism.md
---

# ADR-0057 — Generator v2: realistic P&IDs from process patterns

## Context

The user (2026-10-24) asked for synthetic P&IDs that "resemble real ones almost entirely": many instrument kinds,
connections with meaning, current practice — "real life is more complicated than 3 valve types and 6 equipment
types" — and chose the deepest option offered: vocabulary, standard trims, sheet density **and process patterns**.

The evidence (`10-literature/real-pid-composition-2026-10.md` §7) puts the gap in numbers. The generator uses 6
of pyDEXPI's 99 non-custom equipment classes, 3 of 55 piping classes and 4 ISA first letters, in one loop shape,
on a random tree. Against the 12 real OPEN100 sheets (one nuclear plant), a generated headline sheet carries
1.4× fewer valves (15.0 vs 21.4), 3.8× fewer instrument nodes (7.8 vs 29.2), about 4× more equipment, and about
half the symbols (42.6 nodes vs 82.3 symbols). Real instruments are leaf attachments (69 % degree 1); ours all sit
in control loops. The codified local rules L1–L16 (HNF-64103, KLM) are not encoded at all.

Three constraints make this non-obvious:
- **Every measured result must stay reproducible**: EXP-0001 ladder, EXP-0002 sealed test, dev runs, the demo's
  plants, 2,048 tests. The v1 code reads shared schema constants and the EX01 importer maps classes through the same
  schema, so simply growing the schema would change v1 plants and EX01 (design note §2).
- **No per-class frequency is published** for real P&IDs (composition note §10). Weights cannot be calibrated.
- **pyDEXPI decides what survives**: measured today, a sensor located on a piping segment loses its edge in
  pyDEXPI's abstraction; one located on a piping component keeps it (design note §3).

## Options considered

**A. Vocabulary only.** Swap in ~25 equipment, ~30 piping classes and an ISA tag grammar on today's random tree.
Cheap (composition note ranks it S). It changes labels, not structure: valves still land at random on random
streams, instruments still hang only on loops, sheets stay 4× too equipment-dense. It answers "more types", not
"connections with meaning".

**B. Vocabulary + standard trims.** Add the codified arrangements (pump suction/discharge, CV station, PSV, drains,
vents) around each randomly placed item. Local structure becomes recognisable; but the plant-level topology is
still a random tree with random recycles, so upstream/downstream questions and `k` (the claim's x-axis) run over
connections no engineer would draw.

**C. Full process patterns (chosen).** Unit-operation templates (column system, compressor stage,
heater–reactor–separator, tank farm, exchanger train, flash drum, filter package, blending) with their trims,
instruments, loops and A/B spares, wired through typed ports by a seeded flowsheet grammar; sheets drawn per
pattern drawing group. Highest realism per sheet and per plant; effort estimate 15 coder tasks (4 S, 9 M, 2 L,
unmeasured pace). Control schemes inside patterns are textbook practice not codified by any source read — they are
declared, not sourced.

**D. Import patterns from the SFILES / flowsheet literature.** Hirtreiter et al. generate flowsheets from
sub-process patterns joined by Markov sampling — the closest precedent. But their patterns are flowsheet-level
(no trims, no valves, no line numbers), the code and pattern availability and licence were never checked
(`pid-structural-rules.md` §6.2, §7: "unknown"), and their generated data is itself measurably narrower than real
data (vocabulary 113 vs 390). We adopt their *mechanism* (patterns + seeded sampling), not their patterns.

**E. pyDEXPI's sample patterns.** Ready-made `DexpiPattern`s, but: AGPL repository data; zero instruments, zero
check valves, only generic `OperatedValve`; single-in/single-out, so inter-pattern topology is a chain or one ring
(`pid-structural-rules.md` §6.1); and pyDEXPI's sampler uses global `random` and gives every copy a fresh `uuid4`
id, which breaks seeded reproducibility (ADR-0007, measured 2026-09-13). They would have to be rewritten into C
anyway.

**Versioning, a sub-decision with its own alternatives.**
- *V-a: change the generator in place behind new defaults.* Breaks every frozen result.
- *V-b: a `version` field on the existing `GeneratorConfig`.* Adds a key to every v1 `ingest.json` and record, so
  byte-identity is lost even when the value is "v1".
- *V-c (chosen): v1 frozen behind pinned constants; v2 as separate types (`GeneratorConfigV2` with a
  `generator_version: Literal["v2"]` discriminator), its own preset and corpus ids (`D100g2`, `H100g2`, …), one
  dispatch function that returns v1 for every existing `ingest.json`.*

**Line-mounted instruments, a sub-decision.** *(i)* sensor on the pipe segment — measured to lose the edge;
*(ii)* sensor on the nearest inline valve — survives but means "the valve is measured"; *(iii, chosen)* DEXPI C01's
own tap: a `PipeTee` on the line, a branch to the root component, sensor located there. Local gauges are one PSGF
node (a deviation from C01's PIF + PSGF pair, chosen so one drawn bubble is one node with one tag).

## Decision

1. **C, with V-c and tap convention (iii)**, as specified in `40-design/generator-v2-realism.md`.
2. **v1 is pinned first** (task V2-T0): `V1_*` constants, golden digests of v1 DEXPI JSON, `ingest.json` config
   blocks, schema text and the EX01 import, recorded before any schema growth.
3. **No new visible property.** An item's kind is read from `node_class` and the ISA letters of its tag, by one
   published grammar; the store, resolver and Cypher schema text keep their shape.
4. **Targets** are OPEN100's per-sheet values (one nuclear plant) used as declared acceptance bands, or declared
   design parameters; the composition report and the structural invariants are the evaluation of the generator.
5. **Measurement** of v2 uses the frozen system (F1, ADR-0053): free gates and composition first, then the
   EXP-0001-style ladder and the EXP-0002-style sealed test on fresh v2 seeds, each estimated, capped and staged.
   v1 results are kept, never replaced.

## Rationale

- **The claim needs external validity, not a new system.** The inversion was shown on random-tree plants; an
  examiner can call it an artefact of toy topology. C makes the corpus look like plant drawings (codified trims,
  OPEN100-level density, ISA tags, patterns per unit operation) while V-c and point 5 keep the retrieval system
  fixed, so a v2 result is a replication on realistic data. A and B leave the plant-level topology random, which is
  exactly where `k` and the path questions live.
- **Novelty budget.** The contribution is retrieval at scale and cross-sheet identity, not P&ID synthesis. C is
  built from boring parts: codified rules, DEXPI's own reference structures, a published sampling mechanism. The
  interesting part it adds to the contribution is A/B spares, the realistic hard case for identity.
- **Reproducibility is a hard constraint**, and only V-c meets it byte for byte.
- **pyDEXPI decides modelling** (point (iii)): the chosen tap is the reference example's own and survives the
  abstraction, measured.

## Consequences

**Enables:** a 25-equipment / 31-piping / ~20-template ISA vocabulary on real `DexpiModel`s; meaningful topology
(pumps with suction vessels, CV stations, PSVs, recycles through compressors); sheets of 3–10 equipment centred on a
major item; line numbers in `SIZE-SVC-NNNNNN-SPEC-INS` form; XV on-off valves with solenoids, PTs on lines and
vessels, control valves in loops, Coriolis meters — the device kinds the separate joint project needs, readable from
the drawing.

**Costs:** ~15 coder tasks (estimate); a larger store (≈ 2–3× nodes per sheet, estimated from the targets, to be
measured); question families need three v1-safe fixes (loop filter, absent-tag grammar, valve-vs-piping sets);
EXP-0004 becomes harder (A/B spares share digits in ADR-0031's blocking key); paid re-measurement.

**Forecloses / does not claim:** per-class frequencies of real P&IDs; realism beyond one real plant plus codified
rules; utility headers and utility sheets (still parked; only consumer-side stubs); equipment data (ADR-0021).

**Revisit if:** a v1 golden changes; the v2 scale smoke breaks plant-generator.md's kill criterion or K-NEO; the
composition bands cannot be met within three logged tuning rounds; a second real multi-sheet set becomes available
(re-derive the bands); pyDEXPI gains a thermowell class or changes its abstraction.

## Status

**Accepted 2026-10-25 (user, in chat)**, with the design note's open questions (§16) answered as follows.

| # | Question | Answer |
|---|---|---|
| Q1 | Utilities | Recommendation: consumer-side stubs (block valve, service code, open end at the sheet edge); headers and utility sheets stay parked |
| Q2 | Prompts on v2 runs | Recommendation A: the frozen system (F1); a v2 legend only as a separately labelled system, and only if failures trace to it |
| Q3 | Role of v2 | **Changed by the user: B.** v2 becomes the headline result ("mainly v2"); v1 stays reported as the first, sealed measurement and the development history. No v1 number is replaced or deleted |
| Q4 | Duplication rate on v2 | Recommendation A: 0.25 (ADR-0028). Because v2 is now the headline, ADR-0028's user amendment applies to it: the H100g2 sensitivity runs at rates 0 and 0.5 are **required** |
| Q5 | Paid runs | Recommendation A: both R4 and R5, each estimated after R3, capped and staged |

**Consequence of Q3 = B.** R4, R5 and the H100g2 sensitivity points carry the thesis's headline numbers; R0–R3 and
the composition report are their preconditions. The user also asked (2026-10-25) for real P&ID samples to be
collected so that declared parameters can be checked against more than OPEN100
(`10-literature/real-pid-samples-2026-10.md`, when filed).
