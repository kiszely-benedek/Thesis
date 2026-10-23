---
adr: 0044
title: The operated valve of a control loop carries the loop's {var}V-unit-loop tag; the actuator carries none
status: accepted
date: 2026-10-04
supersedes: ADR-0040 (rejected by the user 2026-10-04); amends plant-generator.md §3.3 "Ids and tags"
design: 40-design/control-valve-tagging.md
---

# ADR-0044 — Give the loop's valve tag to the valve, not to the actuator

## Context

LOOP_ACTUATED_VALVE asks "Which valve is actuated by control loop {loop_tag}?". Its reference is the tag of the
valve at the end of controller `-send_signal_to->` actuator `-control->` valve (`qa/questions/families_loop.py:38-67`).
The generator writes `{var}V-{unit}-{loop}` (e.g. `FV-30-6`) onto the DEXPI `ActuatingFunction`. The valve body
keeps its own, unrelated minted tag (`GV-30-4`) (`adapters/pydexpi_builder.py:179-183`, `:219-226`). Every wrong
answer in PAID-02/03 that named a tag named the actuator.

The models are reading the drawing the way the sources do:
- A third letter V names a valve (DOE-HDBK-1016/1-93, Module 2, p. 6). A pressure-loop control valve is a "PV". The
  ISA-5.1 table excerpt gives V = valve and Z = actuator (*Control Loop Foundation*, ISA, Ch. 7, p. 105).
- Example P&IDs print one tag per control valve (`FV 101`), with no actuator tag. The actuator is drawn as part of
  the valve symbol (same chapter, Fig. 7-16, p. 111; p. 107).
- In the DEXPI reference example C01, the printed number `PV4712.02` belongs to the `ActuatingSystem` (valve plus
  actuator). The valve body has no label, and the actuator only has the sub-tag `PV4712.02_YC`
  (`data/external/C01V04-VER.EX01.xml` lines 63, 76, 103, 118, 1849-1891).
- ChatP&ID's own reference answers call these valves `HV4750.01` and `PV4712.02` (arXiv:2603.22528v1, App. Table 1,
  p. 33).

The question wording must stay as it is (ADR-0040 was rejected for rewording it). The primer, which is now on by
default, says V = valve (`qa/prompts/primer_pid_v1.txt:9`), so the data contradicts the primer.

## Options considered

**A-i. Valve gets `{var}V-u-n`, actuator untagged, `ActuatingSystem.actuatingSystemNumber` set to the same tag.**
Matches what drawings print and how DEXPI C01 groups the objects. Topology, sheets and `k` do not change, because
tags consume no RNG. The cost is a `None`-safe path for one more untagged class: validation, the importer,
`evidence_tags` and the API-01 gold side. Evidence-node recall can no longer count the actuator, because it is
measured by tag.

**A-ii. Valve and actuator both carry `{var}V-u-n`.** Matches C01's data, where the AF number equals the AS number.
It breaks tag uniqueness (`graph/validation.py:146-155`), and every tag-keyed join (API-01, routing gold, anchors)
becomes ambiguous.

**A-iii. Valve gets `{var}V-u-n`, actuator gets `{var}Z-u-n`.** The smallest change, with every node still tagged
and unique. The letter is sourced, but no source read shows an actuator printed with its own tag on a P&ID. It
would add a label real drawings do not carry.

**B. Keep the tags, contract actuator and valve into one item in the plant `ItemGraph`.** Only plant arms would
benefit. Occurrence, Cypher and ContextRAG arms keep the ambiguity, and the representation comparison gets a
naming confound.

**C. Primer line saying the actuator carries the loop's V tag.** A rule written to fit the generator, against the
sources. Ruled out by the user's realism rule.

**D. Score the actuator's tag as correct too, or instead.** The answer stops being unique, or the valve's own tag
becomes "wrong" (ADR-0040's option B).

## Decision

**A-i.**
1. `control_valve_tag(variable, unit_no, loop_no)` in `benchmark/generator_models.py` is the single formula.
   `DexpiPlantBuilder.add_control_loop` writes it to the valve's `pipingComponentNumber` and to
   `ActuatingSystem.actuatingSystemNumber`, and leaves `actuatingFunctionNumber` unset. The offline test builder
   mirrors this.
2. `schema.UNTAGGED_CLASSES` = connector classes plus `ActuatingFunction`. Validation does not require a tag for
   them. The importer omits a `None` tag. `evidence_tags` and API-01 skip or placeholder untagged nodes.
3. One sentence in the schema text and both legends states that actuator nodes have no tag. The primer is
   unchanged.
4. The question template, reference function, scoring, canonical programs and need classifier are unchanged.
5. All four corpora and their question sets are regenerated from their seeds. The free checks (API-01/01b, API-02,
   NEED-00, ROUTE-01, PG-01) are re-run. Earlier paid rows stay as history on the old naming.

## Rationale

- The failure is a realism defect in the data, not a reading error by the models. Fixing it at the source keeps the
  natural question and holds every strategy and representation equal, so it cannot move the ranking the thesis
  measures. It only removes a scoring artefact from it.
- A-i is the only option that matches both what is printed (one tag per control valve) and DEXPI's grouping. A-iii
  is cheaper, but it buys that with a label no source shows.
- Topology is untouched, so every scale measurement so far (sheets, `k`, routing coverage) stays valid. Only
  tag-bearing answers move.

## Consequences

- The loop's valve tag is now formed from the loop tag (`FIC-30-6` → `FV-30-6`) by construction. The family becomes
  answerable from ISA convention alone, as it would be on a real plant. How it is reported (per-family table only,
  or also the headline aggregate) is a user decision recorded in the design note (U2).
- LOOKUP_TYPE and LOOKUP_UNIT lose their actuator questions. Their reference `ActuatingFunction` for an `FV-…` tag
  had the same ambiguity.
- UNANSWERABLE_TAG gains absent tags such as `FV-30-7`.
- Evidence-node recall for loop families covers controller and valve. The actuator stays visible through
  `evidence_sheets` and the evidence-edge hops metric.
- PAID-01…04 and PG-P1 are not comparable with later runs on LOOP_ACTUATED_VALVE and LOOKUP_*.
- **Follow-up, not decided here:** the Proteus importer tags C01's control valves `C1`, whereas ChatP&ID's gold uses
  the `ActuatingSystem` number. That is a separate ADR, needed before EXP-0001.
- **Revisit if** a source shows actuators printed with their own tags on P&IDs (then reconsider A-iii), or the
  thesis adds split-range loops (two valves per loop), which would need a sourced rate.

## Acceptance (2026-10-04)

Accepted by the user in chat: option **A-i**. Built as CV-T1 (`767329e`) and CV-T2. U2 settled by the main session under the user's instruction to proceed, before any new-naming result exists: LOOP_ACTUATED_VALVE stays in the per-family tables and is left out of the headline aggregate (the answer follows from the loop tag by ISA convention). U3 (importer rule for EX01's control valves) deferred to its own ADR before EXP-0001.
