---
adr: 0058
title: Grow the v2 schema to a fluid-process allowlist of pyDEXPI classes by one ancestry rule, model drivers as DEXPI does, and recalibrate v2 against the real-sample inventory
status: accepted
date: 2026-10-25
supersedes: ADR-0057 in part — its design note §4 (the 49 curated classes, "drivers not used", "ProcessControlFunction is not used", CentrifugalBlower/AxialFan in U3), the sheet knobs `min/max_equipment_per_sheet`, `p_cv_station`, the "no cascade loops" exclusion, two acceptance bands, the CLASS_NAME instruction on v2 corpora, and the task plan §14 from T1. ADR-0057's V-c versioning, tap convention, utilities answer (Q1: consumer stubs only), F1 and measurement plan R0–R6 carry over unchanged.
design: 40-design/generator-v2-pid-vocabulary.md
---

# ADR-0058 — Generator v2 on a fluid-process pyDEXPI allowlist

## Context

ADR-0057 (accepted 2026-10-25, v2 = headline corpus) grows the schema by 49 hand-picked classes. The user then
asked for "each and every element playing a role in the PyDEXPI standard … to be useful for [industry]". After
seeing the full proposal, the user narrowed this the same day (gist, relayed): *pyDEXPI is a fully industrialised
standard, but we only need it for piping and instrumentation diagrams. Elevators, packaging machines, trucks,
railway and ship filling, burners, chimneys, ventilators, the solids operations — we don't need these; just the
related stuff in the schema.*

Measured today (pyDEXPI 1.2.0, repo venv; design note §2):
- `Equipment` has 75 non-custom leaves + 24 parents + 25 Custom*. `PipingComponent` has 50 leaves + 5 parents +
  6 Custom*. `ProcessControlFunction` is the only subclass of `ProcessInstrumentationFunction`.
- **One ancestry rule** reproduces all 16 non-structural v1 label chains with **0 mismatches**. The rule keeps the
  classes in a class's ancestry that lie below the first schema root, then adds the root's fixed suffix.
- pyDEXPI's graph abstraction removes `MotorAsComponent` (DEXPI's way of putting a motor on a machine) and keeps
  `vessel -agitator-> Agitator` and `ActuatingElectricalFunction -> machine`. A standalone motor is an isolated
  node, because DEXPI has no "drives" relation.
- `qa/schema_text.py` lists labels and relationship types from the load plan. A v1 corpus's schema text is
  therefore unaffected by schema growth. The CLASS_NAME answer instruction (`qa/final_answer.py`), by contrast,
  lists every `NodeClass` and would change.

The researcher's `10-literature/real-pid-samples-2026-10.md` (16 hand-counted real sheets, 11 sources) contradicts
parts of ADR-0057: cascades are common on dense sheets; sheets carry 1–16 equipment items; the on-off valve letter
(X/Y) and the spare numbering (suffix or consecutive) are company-specific; condensate sometimes leaves through a
level-controlled drain pot; motors are drawn as an "M" on the machine, never as separately tagged items.

## Options considered

**Schema scope**
- **S-a. Keep ADR-0057's 49 curated classes.** Small, but a hand-drawn boundary. A real file's `SpiralHeatExchanger`
  or `NeedleValve`-type variants (`AngleGlobeValve`, …) import as `GenericItem`.
- **S-b. All 164 pyDEXPI topology classes** (the proposed version, below). Complete, but the user does not want
  solids, logistics, power and utility-production equipment in a P&ID QA system.
- **S-c (chosen). A declared fluid-process allowlist, with chains and `piping_kind` derived by the ancestry rule.**
  The allowlist has 25 equipment leaves and their 8 pyDEXPI parents, all 55 piping classes, `PropertyBreak`,
  5 instrumentation classes and 4 connectors: **98 topology classes**. Classes outside the allowlist import by the
  ancestor walk (`Silo` → `Vessel`, `Boiler` → `Heater`, `Conveyor` → `GenericItem`).

**Drivers:** *D-a (chosen)* DEXPI motor components on the machine, with visible `HS → AEF → machine` start/stop
and speed signals; *D-b* separately tagged motor nodes; *D-c* an invented `drives` edge. **Vessel–agitator link:**
*(i)* `related_to` fallback; *(ii, chosen)* new relation `has_agitator`; *(iii)* none (isolated agitator).
**Recalibration:** *R-a* keep ADR-0057's values; *R-b (chosen)* change what the samples contradict, as declared
parameters with the counts as basis.

## Decision

1. **Schema = S-c.**
   - Rule in `adapters/pydexpi_vocabulary.py` (the only pyDEXPI import, ADR-0003); the allowlist is declared there.
   - A generated, checked-in literal table `graph/schema_vocabulary.py`, plus a drift test.
   - v1 specs byte-identical; the `V1_*` pins feed every v1 path.
   - Custom* map by ancestry on import.
   - New relation `has_agitator`.
   - `control` gains equipment targets from `ActuatingElectricalFunction` only.
2. **Import.** `--vocabulary v2` (opt-in; default v1, so EX01/EXP-0001 are unchanged) maps a real file onto the
   allowlist with true classes, under corpus ids with a `v2` suffix (`EX01v2`).
3. **Generation.**
   - ADR-0057's fluid patterns U1–U8, plus a crude-desalter pattern U10 and variants inside the existing patterns.
   - **Generated:** 25 equipment leaves, 47 of 50 piping leaves, `CheckValve`, `PropertyBreak`, 5 instrumentation
     classes = **79 generator classes**.
   - **Import-only:** `Hose`, `ClampedFlangeCoupling`, `Penetration`.
   - Electric motors as `AlternatingCurrentMotorAsComponent` inside the DEXPI file.
   - 8 new instrument templates incl. cascade; 15 first letters.
   - Utilities stay parked: consumer-side stubs only, as in ADR-0057 Q1.
4. **Recalibration (R-b).**
   - `p_cv_station` 0.8 → 0.6.
   - Cascade templates; split-range template, off by default.
   - Per-train `on_off_letter` ∈ {X, Y} and `spare_naming` ∈ {suffix, consecutive}.
   - Condensate variants: trap, trap station, drain pot. Pump-pressure variants: per-pump PI, header PT.
     Pump set on its own sheet as a variant.
   - Sheet knobs 1–16 equipment.
   - Bands: every sheet 1–16 equipment and ≥ 90 % ≤ 10; every sheet ≤ 21 off-page stubs; class coverage replaces
     "distinct kinds".
5. **F1 carries over.** On v2 corpora the CLASS_NAME instruction lists the classes present in the corpus; v1
   corpora keep their exact text (Q3).

## Rationale

- **The claim needs a realistic corpus measured by a frozen system.** The fluid allowlist is where P&IDs and
  the samples are. It keeps v1 byte-identical (16/16 chains, pins, plan-derived text). Its boundary is one
  sentence: the equipment of fluid process units plus every piping and instrumentation class.
- **pyDEXPI decides modelling.** Drivers and agitators use the fields pyDEXPI has; nothing a real DEXPI file could
  not carry is invented.
- **Novelty budget.** Vocabulary is boring work: a rule, a table and variants. The per-train conventions (spare
  naming, X/Y letters) feed the contribution as realistic identity cases.
- **Narrowing costs no thesis argument.** Every dropped kind would have been a declared [U] placement (no sample
  shows silos, feeders, crushers, extruders, sieves, weighers, packaging, centrifuges, rail waggons, ships,
  forklifts, cooling towers, turbines or generators, per the coordinator's digest of the samples note).

## Consequences

**Enables:**
- Real fluid-process DEXPI files import with true classes.
- The headline corpus carries every piping and instrumentation kind with a fluid placement.
- Visible motor start/stop and VFD signals, cascades, X/Y on-off letters and consecutive spare numbering.

**Costs (estimates):**
- 16 coder tasks after V2-T0 (4 S, 9 M, 3 L), against ADR-0057's 15.
- Up to 5 more DEXPI objects per motor-driven machine, by construction.
- A longer plan-derived label list, measured in R3.

**Forecloses:** solids, logistics, power-block and utility-production equipment in generated corpora (they still
import, by ancestry); a shaft link between driver and machine; separately tagged electric motors.

**Revisit if:**
- a v1 golden changes;
- the coverage report shows a generator class absent at D1000g2;
- a band fails within three logged rounds;
- pyDEXPI keeps `MotorAsComponent` or gains a `drives` relation;
- the user widens the allowlist (the rule takes any class list).

## Proposed version and why it was narrowed

The proposed version of this ADR (same day) derived **all 164** non-custom topology classes and placed 128 of
them. It did so through 15 new unit patterns (steam, power block, cooling water, flare, air, firewater, polymer
finishing, silos and bagging, raw solids, granulation, evaporation and crystallisation, desalting, loading,
wastewater, off-gas), four area archetypes, utility islands and 23 coder tasks. 35 of its 46 new equipment
placements were declared [U]. The user narrowed it to P&ID-relevant fluid-process content. The rule, the driver
model, the agitator relation and the recalibration survive unchanged; only the class list and the pattern library
shrank.

## Status

**Accepted 2026-10-25 (user, in chat).** Answers to the design note's questions:

| # | Question | Answer |
|---|---|---|
| Q1 | Drivers | **A** — DEXPI motor components + visible start/stop and speed signals |
| Q2 | Utility units | **B** — stay parked; consumer-side stubs only (ADR-0057 Q1 stands) |
| Q3 | CLASS_NAME instruction on v2 | **B** — list the classes present in the corpus; v1 corpora keep their exact text |
| Q4 | Headline corpus | **B** — the fluid-process corpus; no integrated site, no solids/logistics/utility areas |
| Q5 | Weak placements | **B** — drop the seven weakest (of these, only `Penetration` and `AxialCompressor` lay inside the fluid scope; both are dropped) |
| Q6 | Equipment per sheet | **A** — 1–16, ≥ 90 % ≤ 10 |

**Borderline classes** (main-session default, each a one-line toggle in the allowlist; the user may veto):
- Kept: `Agitator`, `StaticMixer`, `RotaryMixer`, `InLineMixer` (piping), `AirEjector`, `Furnace` (without burner,
  chimney or blower nodes), `AirCoolingSystem`.
- Kept and flagged by the architect for a fluid-process reason: `EjectorPump`, `RotaryCompressor`,
  `SpiralHeatExchanger`, `ElectricalSeparator` (crude desalter).
