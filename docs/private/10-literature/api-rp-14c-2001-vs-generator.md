---
topic: API RP 14C (7th ed., 2001), Recommended Practice for Analysis, Design, Installation, and Testing of Basic Surface Safety Systems for Offshore Production Platforms — compared with generator v2.1
date: 2026-11-22
status: read sections 2, 3, 4.1-4.2.3 and Appendix A for headers (A.3), pressure vessels (A.4), atmospheric vessels (A.5), fired and exhaust heated components (A.6), pumps (A.7), compressors (A.8), shell-tube exchangers (A.10); skipped wellheads, flowlines, injection lines, pipelines (A.1, A.2, A.9: offshore-specific, not in our patterns), Appendix C-G only by headings
related: [10-literature/toghraei-2019-vs-generator.md, 10-literature/pid-structural-rules.md, src/plantgraph/benchmark/v2]
note: cited by section number (the PDF is a scan; printed page headers are partly garbled). Paraphrased. Scope is offshore production platforms, but the component analyses (A.4-A.8, A.10) are generic to hydrocarbon process plants.
---

# API RP 14C (2001) vs generator v2.1

## Why this source matters for the generator
API RP 14C turns safety-device placement into a **per-component checklist**: for each process component type, a Safety Analysis Table (SAT: undesirable event → cause → detectable condition) and a Safety Analysis Checklist (SAC: each recommended device, plus numbered conditions under which it may be omitted). That shape maps directly onto rule tests: *every component of type X has device D, or carries one of the SAC exception codes for D*. Toghraei (2019, p. 412) names API 14C as the source of P&ID check lists.

## Core premises (§3.4, §4.2)
- §3.4b-c: **two levels of protection** per failure, independent of the normal control devices, preferably **functionally different** (example: overpressure → PSH primary, PSV secondary).
- §3.4d-f: analyse each component on its own under worst-case input/output; a facility made of fully protected components is protected.
- §4.2.2d: all devices of the component figure are installed **unless** a SAC condition says their function is not needed or is done by another device.
- §4.2.3: on an abnormal condition, shut off all inputs (process, heat, fuel) **at the primary source** (pump, compressor, well); closing the component inlet is an addition, not a substitute; cascading shut-in only in special cases.

## Device identification (§2.2-2.5, Tables 2-1, 2-2)
- "S" (safety) is the second letter of sensing and self-acting safety devices: PSH, PSL, PSV, PSE (rupture disc), LSH, LSL, TSH, TSL, TSE (fusible element), FSH, FSL, **FSV = check valve**, BSL (burner flame), ASH (gas detector); actuated valves SSV, SDV, BDV (blowdown), ESD.
- A device tag may carry a component code (e.g. "PSV ABJ 1000": atmospheric vessel, tank, unit 1000).
- GEN uses ISA trip letters (LSHH, PSHH, BSL) → acceptable alternative spelling; API's "S" style is a candidate sampled variant (oilfield style).

## Component checklists → generator
| Component (§) | Recommended devices (SAC) | Main omission conditions | GEN v2.1 |
|---|---|---|---|
| Pressure vessel (A.4, SAC A-4.2) | PSH (shut inflow), PSL, PSV (≥1, one set ≤ MAWP), LSH, LSL (per liquid outlet), FSV on each outlet, TSH if heated | input cannot exceed MAWP (pump/compressor); protected by an upstream/downstream device that cannot be isolated; flare final scrubber; atmospheric operation; small manually drained traps need no level devices | PSV on every vessel (S6) ✓; PSHH trip only on U3 separator; LSHH trip on drums/KO; LSL rare; no FSV on outlets → PARTIAL |
| Atmospheric vessel (A.5, SAC A-5.2) | vent + flame arrestor; PSV (P/V relief) or second vent; LSH (unless fill attended / overflow contained); LSL (unless containment); TSH if heated | no pressure source except blanket gas; pressure vessel in atmospheric service | flame arrestor + breather valve ✓; overfill LSHH trip ✓; second vent / emergency vent missing; LSL alarm optional → PARTIAL |
| Fired / exhaust heated (A.6, SAC A-6.2) | TSH medium, TSH stack, FSL on medium flow (tube heaters), FSV on tube outlet, PSH fuel (+PSL fuel, PSL air, motor starter interlock on forced draft), PSV on tubes, flame arrestor on natural-draft air intake, stack arrestor, BSL/TSL flame failure; PSH/PSL located between last fuel regulator and fuel control valve | isolated area, non-combustible service | U3: BSL→XV, fuel PIC, blower → PARTIAL (no TSH stack/medium, no FSL, no PSH/PSL fuel, no tube PSV, no FSV) |
| Pump (A.7, SAC A-7.2) | PSH on discharge, PSL on discharge, PSV on discharge, **FSV (check valve) on all pumps** ("Check valve installed" is the only SAC entry); PSH/PSL upstream of the check and any block; PSV upstream of any block | PSH: discharge ≤ 70 % of line MAWP, manually attended, small chemical-injection pumps, discharge to atmospheric vessel; PSL: attended, containment, small pumps, to atmospheric vessel; PSV: kinetic (centrifugal) pump that cannot exceed MAWP, internal relief | check on every pump ✓ (matches API, see conflict below); PD relief ✓; no PSH/PSL on pump discharges → PARTIAL |
| Compressor (A.8, SAC A-8.2) | PSH + PSL on each suction and discharge; PSV on each suction and discharge; FSV on final discharge; TSH on each cylinder/case discharge; SDV on each inflow and fuel gas line; BDV on final discharge; ASH if enclosed | input sources already protected; kinetic compressor that cannot exceed MAWP (discharge PSV); downstream device upstream of the cooler | U2: discharge PSV ✓, discharge check ✓, KO-drum LSHH→XV ✓, ST/VT; no PSH/PSL, no TSH, no suction PSV, no BDV → PARTIAL |
| Shell-tube exchanger (A.10, SAC A-10.2) | each SECTION analysed separately: PSH, PSL (hydrocarbon section), PSV per section (incl. tube-rupture of the other side); TSH not generally required | input cannot exceed section MAWP; protected by non-isolable upstream/downstream device | thermal relief on CW return, optional shell PSV → PARTIAL |
| Header (A.3, SAC A-3.2) | PSH, PSL, PSV with exceptions; flare/relief/vent headers need no PSL and no PSV if no valving in the outlet | — | headers are pipes in GEN; no header devices → out of scope unless network sheets are added |

## Conflict with Toghraei (important for the v2.2 rule registry)
- **Check valve on reciprocating pumps**: Toghraei (2019, pp. 191-192) says a reciprocating pump needs no external check valve (internal check); API RP 14C SAC A-7.2 g lists a check valve for **all pumps** with no omission condition. → The sources disagree; v2.2 should treat it as a **sampled alternative** (or follow API as the stricter safety source) and record the choice. The earlier note's "DEVIATION 1" is downgraded to "sources disagree".
- **Decision (user, 2026-11-22): follow Toghraei** (2019, the later source) → reciprocating pumps get no external check valve; the registry entry cites both sources and states the conflict and the choice.

## What this adds to v2.2 (candidates for the architect)
1. A **SAC-shaped rule test**: per component type, the required safety devices, each either present or covered by a declared exception code drawn by the generator (exceptions depend on pressures we do not model, ADR-0021 → declared parameter, recorded in the answer key).
2. **Two-level protection** check: every pressure vessel has a primary sensor-trip (PSH/LSH) and a secondary device (PSV) — functionally different.
3. **Shut-in at the primary source**: trips should close the source (pump/compressor stop, upstream SDV), not only the vessel inlet XV.
4. Compressor and fired-heater device sets (largest gaps); FSV on vessel outlets; PSH/PSL on pump discharges.
5. Device-letter style as a sampled variant: ISA (LSHH) vs API (LSH with "S" for safety).
