---
topic: Liptak (ed.), Instrument Engineers' Handbook, Vol. 1 Process Measurement and Analysis, 4th ed. (CRC, 2003) — parts relevant to generator v2.1
date: 2026-11-22
status: read §1.1 "Flowsheet Symbols and P&I Diagrams" (pp. 4-30, prose; symbol tables only by caption) and the venting part of §7.7 (pp. 920-927); NOT read: §1.10 (it covers computer fault tolerance, not trip voting), the selection/orientation tables of §2.1 (flow), §3.1 (level), §5.1 (pressure) — candidates for a later pass; the rest of the 1868 pages (sensor physics) is out of scope
related: [10-literature/toghraei-2019-vs-generator.md, 10-literature/api-rp-14c-2001-vs-generator.md]
note: PDF page = printed page + 47 near the front; drifts later. Points from §1.1 are cited by section only (the extract has no reliable per-page markers). This is the MEASUREMENT volume; per-equipment control schemes are in Vol. 2 (Process Control and Optimization), which we do not have.
---

# Liptak IEH Vol. 1 (2003) vs generator v2.1

## §1.1 Identification (based on the ISA S5.1 revision draft, now ANSI/ISA-5.01.01)
- **Loop identification** = optional prefix (unit/area) + optional punctuation + measured-variable letters + loop number + optional suffix; numbering may be **parallel** (separate sequence per variable letter), **serial** (one sequence for all), or parallel/serial. GEN: one serial counter per unit with a unit prefix (`FIC-12014`) → CONSISTENT with "serial"; parallel numbering is a candidate **sampled alternative**.
- All components of a loop carry the **same distinctive number**. GEN → CONSISTENT.
- **Primary instrumentation** (measuring, controlling, calculating devices) gets loop and instrument numbers; **secondary instrumentation (level glasses, pressure gauges, thermometers) "shall be assigned only a functional identification"**, or numbers per the owner's guidelines. GEN numbers every local gauge (`PI-12021`) → candidate **sampled alternative** (numbered vs functional-only gauges), same spirit as tagged/untagged manual valves.
- **Cancelled tag numbers are never reused** → real loop sequences have gaps. GEN numbers consecutively → optional realism knob (gaps in sequences).
- A/B spare equipment: "their relevant instruments are often tagged with the tag number suffixed with A/B". GEN: pump PIs are per pump → check suffix style.
- A transmitter (TT) follows a sensor (TE), not a converter (TY) (definitions). A "hand control valve" (HCV) is a hand-actuated valve used for throttling that needs instrument identification.
- §1.1 "P&IDs" practice (end of the section): at the detailed/IFC stage the P&ID shows **all lines including services to machinery, drains and vents**; each line sized, classed, numbered (size, class, rating, insulation, tracing); control valves with true size, flange rating, **block and bypass valves, handwheel, action on air failure**; transmitters single, duplicated or triplicated with taps; level bridles with valving; correct primary-element type; safety valves with inlet/outlet sizes and set pressure; all vents, drains, silencers. Small-bore piping (< 2") is omitted at the estimate stage. **Typical sketches** (motor-operated valves, motors, on-off pneumatic valves) are numbered and referenced next to each device. GEN: action on air failure missing (= the valve-position gap from Toghraei); duplicated/triplicated transmitters missing; otherwise consistent.

## §7.7 Flame arresters, conservation vents, emergency vents (pp. 920-927)
- NFPA requires flame arresters **or** conservation (breather) vents on tanks holding liquids with flash point < 23 °C (73 °F) and boiling point > 38 °C (100 °F) (p. 927); combination flame-arrester/conservation-vent units exist (Fig. 7.7m).
- Flame arresters can clog (foaming, plugging, freezing) → steam tracing and a **secondary pressure-relieving device** are advisable (p. 927). Emergency venting is treated separately (references to API 2000).
- GEN 6.19 tank vent: FlameArrestor → BreatherValve → open end → CONSISTENT for the normal vent; secondary/emergency relief missing (same gap as Toghraei pp. 235-236 and API 14C A.5).

## What this adds to v2.2
1. Sampled identification alternatives: serial vs parallel loop numbering; numbered vs functional-only local gauges; optional gaps in tag sequences.
2. Valve "action on air failure" as part of the valve-position attribute (confirms Toghraei).
3. Redundant transmitters (duplicated/triplicated) on trip functions — pairs with API 14C two-level protection.
4. Tank secondary/emergency relief (confirms Toghraei and API 14C).
