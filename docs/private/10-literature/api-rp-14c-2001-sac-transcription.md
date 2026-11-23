---
topic: API RP 14C (7th ed., 2001), Appendix A Safety Analysis Checklists (SAC) for the six component kinds the generator has, page-checked, mapped onto generator v2.2
date: 2026-11-23
task: T10a of docs/private/40-design/generator-v2-2-handbook-rules.md (§13, §4.7, §6.4)
status: all six SAC tables transcribed item by item and checked against the PDF text layer and a rendered page image; generator coverage measured on v2.2 seeds 1-5
related: [10-literature/api-rp-14c-2001-vs-generator.md, 40-design/generator-v2-2-handbook-rules.md, src/plantgraph/benchmark/v2]
note: Paraphrased. Only device letters and short condition phrases follow the standard's wording. The PDF stays on the user's Desktop and is not copied into the repo.
---

# API RP 14C (2001): SAC transcription for the generator (T10a)

## 1. Source and method

- **Source.** API RP 14C, 7th edition (2001), the PDF on the user's Desktop (100 pages, text layer from
  Adobe Paper Capture).
- **Reading.** `pdftotext -layout`, one page at a time. The six SAC pages were also rendered as images
  (`pdftoppm`) and read visually, because OCR garbles some item letters. In the text layer, "a." can come
  out as "n." or "u.", "e." as "c.", "f." as "r.", and the letters "i." (A-6.2) and "l." (A-6.2) are
  dropped. In the text layer the A-6.2 title reads "Table A-5.2"; the image and the table list on PDF p.8
  (printed vi) both say A-6.2. Every letter below comes from the image.
- **Page offset.** Printed page = PDF page − 8 on every page I read: PDF 24, 34–41, 46, 48, 52, 53, 55,
  59 and 61. The table list on PDF p.8 gives the same printed pages for all six SACs.
- **Exception codes.** API numbers the conditions under each device. Condition 1 is always "device
  installed"; conditions 2 to n are the omission conditions. API says that a device left out is justified
  on the SAFE chart by "the appropriate SAC item number" (§4.3.3, printed p.16, PDF 24). API
  prints no code string, so this note writes codes as `<table> <item letter>.<number>` (e.g. `A-4.2 a.2`).
  That format is ours.
- **Deleted entries** are kept so the numbering stays API's: condition A-4.2 g.2, condition A-5.2 e.2,
  the whole item A-6.2 c, and condition A-10.2 c.5.

### Generator baseline used in the "today" columns

- **Code.** Working tree at `6d8c079`, plus the uncommitted T8 files (`pressure_levels.py`,
  `checks_pressure.py`, `checks_overpressure.py`). `GeneratorConfigV22` was used, with every knob at its
  default.
- **Plants.** Seeds 1–5, each the smallest plant of about 30 sheets (`smallest_n_units_v2(30, …)`):
  17, 16, 19, 18 and 20 units, for **156 sheets** in total (32 + 31 + 31 + 31 + 31). The plants were
  generated locally from scratch-pad scripts, with no Neo4j and no paid calls.
- **How devices were read.** From the oracle graph (`build_rule_view`):
  - a switch is a sensor `measured_by` the equipment, or a bubble that such a sensor feeds, whose letters
    have `S` after the first letter;
  - relief comes from the existing wired checks (S6 / TOG219-VESSEL-PSV, `checks_overpressure.reaches_relief`);
  - a check valve on the pump discharge comes from the `discharge_check` role (`trims.pump_discharge`).
- **Counts.** All counts are totals over the five plants.

| Component kind (API) | Generator classes and roles on seeds 1–5 | Count |
|---|---|---|
| Pressure vessel (A.4), hydrocarbon | `ProcessColumn` column 17; `PressureVessel` reflux_drum 17; flash_drum 28 (`PressureVessel` 18 + `GravitationalSeparator` 10); U3 separator 8 (`GravitationalSeparator`); `ScrubbingSeparator` suction_ko_drum 2; `PressureVessel` reactor 8; `PressureVessel` blend_vessel 1 | **81** |
| (scope question) | `PressureVessel` condensate_drain_pot 12 (steam service); `LiquidFilter` 16, `GasFilter` 2 | 30 |
| Atmospheric vessel (A.5) | `Tank` tank 58 (U4), additive_tank 4 (U8) | **62** |
| Fired component (A.6) | `Furnace` fired_heater (U3) | **8** |
| Pump (A.7) | `CentrifugalPump` 171 (bottoms 38, liquid 72, reflux 35, transfer 26); `ReciprocatingPump` dosing 8; `RotaryPump` transfer 11 | **190** |
| Compressor (A.8) | U2 compressor: `CentrifugalCompressor` 1 + `RotaryCompressor` 1; (scope question) vacuum `RotaryCompressor` liquid_ring_pump 4 | **2** (+4) |
| Shell-tube exchanger (A.10) | `TubularHeatExchanger` 58 (reboiler 17, condenser 11, preheater 9, feed/effluent 8, exchanger 7, intercondenser 4, aftercooler 2); `PlateHeatExchanger` 4; `AirCoolingSystem` 14 (A.10.1, p.51: only the hydrocarbon section) | **76** |
| Not covered by the six SACs | `ElectricHeater` 3, air ejectors, mixers, agitators | — |

## 2. A-4.2 Pressure vessels: printed p.29, PDF p.37

Scope (A.4.1, p.26, PDF 34): vessels that handle hydrocarbons under pressure. Vessel pressure devices
sense the gas section (A.4.3.1, p.28). Check valves go in outlet piping (A.4.3.3, p.30, PDF 38).

| Item | Device | Required | Exceptions (code: condition, paraphrased) | Generator today (81 vessels) | Derivable exceptions | Verdict |
|---|---|---|---|---|---|---|
| a | PSH | every vessel | a.2: inlet from a pump or compressor that cannot exceed the vessel's MAWP · a.3: the input is not a wellhead flow line, production header or pipeline, and every input source has a PSH that also protects the vessel · a.4: the gas outlet runs through adequately sized piping, with no block or regulating valve, to downstream equipment whose PSH also protects this vessel · a.5: final scrubber of a flare, relief or vent system, designed for maximum built-up back pressure · a.6: operates at atmospheric pressure with an adequate vent system | **8/81**: only the U3 separator (`PT → PSHH → XV` on its inlet, `reaction_parts.cooler_to_separator`) | a.4 **from structure**: a valve-free gas route to a vessel that has a PSH (column overhead → condenser → reflux drum, once the drum has one). a.2 **not derivable**: needs a design-pressure (MAWP) rank, and the ordinal model holds operating levels only. a.6 **must not** be read from the level: on seeds 1–5 every enclosure, the reactor and the columns included, sits at `ATM` in the T8 model (the model's floor, not atmospheric service) | **cheap add** on the 73 vessels without a PSH: a `PSHH` switch with an alarm bubble; the 17 columns are covered through a.4 |
| b | PSL | every vessel | b.2: minimum operating pressure is atmospheric in service · b.3: every input source has a PSL, with no pressure control device or restriction between it and the vessel · b.4: a scrubber or small trap that is not a process component, protected by a downstream PSL or by design function · b.5: valve-free gas outlet piping to downstream equipment whose PSL also protects this vessel | **0/81** | b.5 from structure (as a.4). b.2 must not be read from the ordinal level (as a.6) | **defer** (see §8): no derivable exception for most vessels, +0.94 instruments/sheet, offshore-specific practice |
| c | PSV | every vessel; text A.4.2.2.1 c (p.27, PDF 35): "always", at least one set no higher than MAWP | c.2: every input has a PSV set ≤ MAWP **and** the vessel has its own PSV for fire and thermal expansion · c.3: every input has a PSV set ≤ MAWP and at least one cannot be isolated from the vessel · c.4: downstream PSVs can carry the vessel's relief load and cannot be isolated from it · c.5: flare final scrubber, rated for built-up back pressure, with no internal or external obstruction · c.6: as c.5, with a rupture disc or safety head (PSE) bypassing the obstructions | **81/81** reach a safety valve (S6, TOG219-VESSEL-PSV, wired); the reactor also has a rupture disc | none needed. c.3/c.4 could come from structure if a vessel ever lost its own PSV | **satisfied** |
| d | LSH | every vessel | d.2: equipment downstream of the gas outlet is not a flare or vent and can take the maximum liquid carry-over · d.3: the vessel's function does not need separated phases · d.4: a small trap drained by hand | **47/81**: flash drums 28/28 (`LSHH` trip, `separation.py`), KO drums 2/2 (`LSHH` trip), reflux drums 11/17 (optional `LSHH`/`LSH`), separators 6/8 (optional `LSH`); column 0/17, reactor 0/8, blend vessel 0/1 | d.3 by a **declared role table**: reactor (no separated-phase service) and blend vessel. d.2 is a judgement (not derivable) | **cheap add** on the column sump, and on reflux drums and separators where the optional switch was not drawn (about 25 vessels); reactor and blend vessel take d.3 |
| e | LSL | one per liquid outlet | e.2: level not automatically maintained **and** no immersed heating element at risk of overheating · e.3: equipment downstream of the liquid outlet(s) can take the maximum gas blow-by, and no immersed heater (restrictions may limit the gas rate) | **14/81** (`LSLL` or `LSL`: flash drums 10/28, separators 4/8) | e.2 **from structure**: no level control loop on the vessel and no heater inside. That covers the 8 reactors; no vessel has an immersed heater. e.3 is a judgement | **cheap add** on the 59 vessels that have a level loop and no low switch (`LSLL` with an alarm); the reactors take e.2 |
| f | FSV (check valve) | each outlet | f.2: the hydrocarbon volume that could flow back is insignificant · f.3: a control device in the line effectively limits backflow | per-outlet presence was **not measured** (UNMEASURED: the survey could not separate process outlets from trims) | f.3 **from structure**: a control valve (LV, PV, FV) on the outlet route, or the check valve of a pump the route passes. This follows the design's own route definition in §6.3, which lets a route pass pumps. f.2 is a judgement | **derive f.3; defer the rest**: outlets with no control device (column overhead to condenser, reboiler circuit, reactor effluent) stay DEFERRED one by one; a check valve on a column overhead would look wrong to an engineer |
| g | TSH | only vessels with a heat source | g.2: deleted (2nd ed.) · g.3: the heat source cannot cause excess temperature | 0; heated vessels: the 17 columns with a steam reboiler. No other vessel has a heat source | g.3 by **declaration**: an LPS-heated reboiler is limited by the steam temperature (the utility level is declared in §6.2). Not-heated vessels: the item does not apply (its header) | **derive g.3** for steam-reboiled columns; n/a for the rest |

## 3. A-5.2 Atmospheric vessels: printed p.31, PDF p.39

- **Scope** (A.5.1, p.30, PDF 38): processing and temporary storage of liquid hydrocarbons. Vessels
  "ancillary" to the production process, such as diesel or chemical storage, are not covered.
- **Supporting text** (A.5.2.2.1, p.31): the vent system should include a flame arrestor. A
  pressure-vacuum relief device or a second vent covers a fouled primary vent.
- **Location** (A.5.3.1, p.32, PDF 40): vent and PSV on top.
- **What counts as a vent** (table note): a pipe or fitting open to atmosphere. A vent line may hold a
  pressure and/or vacuum relief device.

| Item | Device | Required | Exceptions | Generator today (62 tanks) | Derivable exceptions | Verdict |
|---|---|---|---|---|---|---|
| a | Vent | every vessel | none (only a.1) | **62/62** (`trims_vessel.tank_vent`): 27 flame arrestor + breather valve (flammable U4 service), 35 `VentilationDevice` | — | **satisfied** |
| b | Pressure-vacuum relief device (PSV) | every vessel | b.2: a second vent that can pass the maximum gas volume · b.3: a pressure vessel, not subject to collapse, in atmospheric service with an adequate vent · b.4: no pressure source piped in (blanket gas and/or manual drains excepted), with an adequate vent | **27/62** have a `BreatherValve` in the vent line, which is a pressure-vacuum relief device in the vent (Figure A-5 note 3 and the table note); 35 have none | b.2 once TOG236 adds the emergency vent (design §6.4). b.4 from structure only with a declared reading of "pressure source" (an upstream pressure vessel or compressor reachable without passing a tank) | **satisfied after T10**: b.1 by the breather, b.2 by the TOG236 emergency vent on the rest |
| c | LSH | every vessel | c.2: fill operations are continuously attended · c.3: overflow goes to, or is held by, other process components | **58/62**: every farm tank has `LT → LSHH → XV` on the fill (`storage_parts.py`); the 4 additive tanks have none | none (c.2 and c.3 are operating facts the generator does not hold) | **cheap add** on the 4 additive tanks |
| d | LSL | every vessel | d.2: an adequate containment system · d.3: level not automatically maintained and no immersed heater · d.4: the final vessel of a containment system that collects hydrocarbon liquids | 50/62 have a low switch (optional `LSL`/`LSLL`) | d.3 **from structure** for all 62: no tank has a level control loop. This is the same fact TOG295 records as `storage_tank_batch` | **satisfied by d.3** |
| e | TSH | only vessels with a heat source | e.2: deleted (2nd ed.) · e.3: heat source cannot cause excess temperature | no tank is heated | header: n/a | **n/a** |

**Scope tension (open).** The U4 deck draws "non_flammable" tank service (31 farm tanks). Design §6.1
declares every process service HYDROCARBON. If those tanks are not hydrocarbon, A.5 does not cover them.
If they are, the plain `VentilationDevice` without a flame arrestor contradicts the A.5.2.2.1 text.
Either way it is a question for the architect, not for this transcription.

## 4. A-6.2 Fired and exhaust-heated components: printed p.38, PDF p.46

Scope and text:
- **Scope** (A.6.1, p.32, PDF 40): direct and indirect fired vessels, tube-type heaters with natural or
  forced draft burners, and exhaust-heated components. The SAC covers the firing side and the heating
  section; the process side is analysed under its own component kind.
- **Fuel-line PSH/PSL location** (A.6.3.3, p.33, PDF 41): between the last pressure regulator and the
  fuel control valve.
- **TSH (medium) location** (A.6.3.1, p.33): in the discharge line, close to the heater and upstream of
  every isolating device.

**Generator fact.** The U3 furnace is a tube-type process heater. It is drawn without a blower, stack or
air intake (`reaction.py` docstring: the allowlist leaves them out). Its fuel line is: block, PT tee,
`PV` (PIC), `TV` (TIC on the heater-outlet line), [second switching valve with its own `BSL`], double
block and bleed (first valve on `BE → BSL`).

| Item | Device | Required | Exceptions | Today (8 furnaces) | Derivable | Verdict |
|---|---|---|---|---|---|---|
| a | TSH, medium or process fluid | every component | a.2: a steam generator protected by a PSH and, if fired, by an LSL · a.3: an indirect water-bath heater in atmospheric service protected by an LSL | 0/8: the heater-outlet `TT` feeds the TIC, a control loop and not a safety device (§3.4 asks for independence) | none (neither exception fits a process heater) | **cheap add**: a `TSHH` switch with an alarm on the heater-outlet line, ahead of the skillet blind |
| b | TSH, stack | every component | b.2: isolated, and handles no combustible medium or process fluid other than fuel · b.3: exhaust-heated without supplementary firing, and the medium is not combustible | 0/8; no stack is modelled | none | **defer**: no stack class or nozzle in the model |
| c | (deleted, 2nd ed.) | — | — | — | — | — |
| d | PSL, air supply | every component | d.2: natural draft burner · d.3: forced draft with another kind of low-air sensor · d.4: exhaust-heated without supplementary firing | 0/8 | d.2 by **declaring the U3 furnace natural draft** (no blower is drawn; the declaration goes in the hidden state, not a coin) | **derive d.2** |
| e | PSH, fuel supply | every component | e.2: exhaust-heated without supplementary firing | 0/8: the fuel-line `PT` belongs to the PIC | none | **cheap add**: a `PSHH` switch with an alarm on a tee between `PV` and `TV` (A.6.3.3) |
| f | PSL, fuel supply | every component | f.2: natural draft burner · f.3: exhaust-heated without supplementary firing | 0/8 | f.2 by the natural-draft declaration | **derive f.2** |
| g | BSL (flame failure) | every component | g.2: exhaust-heated without supplementary firing | **8/8** (`BE → BSL → XV`; 11 BSL trips, counting the second switching valves) | — | **satisfied** |
| h | FSL, heated medium | every component | h.2: not a closed heat-transfer system in which a combustible medium flows through tubes in the firing chamber | 0/8 | h.2 **from structure**: the furnace heats the process feed, and the plant has no circulating hot-oil loop | **derive h.2** |
| i | Motor interlock (forced draft fan motor) | every component | i.2: natural draft burner · i.3: exhaust-heated without supplementary firing | 0/8 | i.2 by the natural-draft declaration | **derive i.2** |
| j | Flame arrestor, air intake | every component | j.2: forced draft burner · j.3: located in an isolated area and handling no combustible medium or process fluid other than fuel · j.4: exhaust-heated without supplementary firing | 0/8; no air intake is modelled | none (natural draft rules out j.2; the furnace heats hydrocarbon, which rules out j.3) | **defer**: no air-intake line; drawing one needs a new furnace port |
| k | Stack arrestor | every component | k.2: forced draft burner **and** either the heated fluid is non-flammable or the burner draft pressure at the transfer-section exit exceeds the fluid head · k.3: isolated so process fluids cannot meet stack emissions · k.4: exhaust-heated without supplementary firing | 0/8; no stack | none | **defer**: no stack |
| l | PSV, medium circulating tube | every component | l.2: not a tube-type heater · l.3: a PSV on another component protects the tubes and cannot be isolated from the tube section | 0/8: no relief device on the furnace's own lines; the reactor downstream has a PSV and a rupture disc | l.3 **from structure**, only where the furnace → reactor line holds no isolating device: the skillet blind (`p_skillet` 0.5) counts as one, and the reactor PSV's blocks count as car-sealed open (TOG224) | **derive l.3 where it holds; otherwise add** one PSV on the heater-outlet tee (one valve and a flare end per furnace) |
| m | FSV, medium circulating tube (check valve) | each outlet | m.2: backflow volume of combustible medium is insignificant, or the medium is not combustible · m.3: not a tube-type heater | 0/8 | none (m.2 is a judgement for a hydrocarbon feed) | **cheap add** (one check valve on the heater outlet, A.6.2.2.2 p.33); the expert review should confirm it looks right, otherwise defer |

**Natural or forced draft.** Declaring forced draft instead would make d, f and i required. Each of them
needs a blower or fan class the allowlist does not have, so they would all be deferred. Natural draft
leaves j and k deferred instead, and with fewer added instruments. This note recommends natural draft.

## 5. A-7.2 Pumps: printed p.44, PDF p.52

Scope and definitions:
- **Pipeline pumps** (A.7.1, p.40, PDF 48): pumps that send produced hydrocarbons from the process to a
  pipeline leaving the platform.
- **Device locations** (A.7.3.1–2, p.40): PSH and PSL on the discharge, upstream of the FSV and of any
  block valve; PSV on the discharge, upstream of any block valve.
- **The generator.** It has **no pipeline pump**: every pump is in process service, so items a, c and e
  do not apply. Whether a pump that sends product over a battery limit should be declared a pipeline pump
  is left open (§9).

| Item | Device | Required | Exceptions | Today (190 pumps) | Derivable | Verdict |
|---|---|---|---|---|---|---|
| a | PSH, pipeline pumps | pipeline pumps | none | — | — | **n/a** (no pipeline pump) |
| b | PSH, other pumps | every other pump | b.2: maximum discharge pressure ≤ 70 % of the discharge piping's MAWP · b.3: manually operated and continuously attended · b.4: small low-volume pumps (e.g. chemical injection) · b.5: discharges to an atmospheric vessel · b.6: glycol-powered glycol pump | **0/190** (only a local `PI` gauge) | b.4 by **role**: the 8 `dosing_pump`. b.5 **from structure**: the forward route (min-flow recycles excluded) ends only in a `Tank`, which is true for 28 pumps (bottoms 7, liquid 21). b.2 needs numbers and is **not derivable** | **defer** for the other 154 pumps (cost and realism, §8) |
| c | PSL, pipeline pumps | pipeline pumps | c.2: pump does not handle hydrocarbons | — | — | **n/a** |
| d | PSL, other pumps | every other pump | d.2: manually operated and continuously attended · d.3: adequate containment · d.4: small low-volume pumps · d.5: discharges to an atmospheric vessel | **0/190** | d.4 and d.5 as for b | **defer** for 154 pumps |
| e | PSV, pipeline pumps | pipeline pumps | e.2: kinetic pump (e.g. centrifugal) that cannot develop a head above the discharge piping's MAWP | — | — | **n/a** |
| f | PSV, other pumps | every other pump | f.2: maximum discharge pressure below the discharge piping's MAWP · f.3: the pump has internal pressure relief · f.4, f.5: glycol-powered glycol pump cases | **19/19** PD pumps (`pd_relief_valve`, discharge → suction); 0/171 centrifugal | f.2 by **declaration** for centrifugal pumps: "the discharge pipe class is rated for the pump's shut-off head". This is a convention the T8/ADR-0065 spec ordering can carry, because the discharge class is already one step heavier (TOG82); it is not a computed fact | **satisfied** for PD pumps; centrifugal pumps take f.2 if the architect accepts the declaration, otherwise DEFERRED |
| g | FSV (check valve), all pumps | every pump | **none** (only g.1) | **182/190** (`discharge_check`); 0/8 reciprocating, which v2.2 omits on purpose (TOG192) | none: API allows no exception | **conflict, recorded** as `conflict:TOG192-RECIP-NO-CHECK` (design §6.4) |

## 6. A-8.2 Compressors: printed p.47, PDF p.55

What the supporting text adds:
- **Locations** (A.8.3.1, p.45, PDF 53): suction PSH/PSL as close to the compressor as practical;
  discharge PSH/PSL upstream of the FSV and of any block valve; PSVs placed so they cannot be isolated
  from the compressor.
- **Final-discharge check valve** (A.8.3.2, p.45): on each compressor unit's final discharge line.
- **TSH** (A.8.3.4, p.45): in each cylinder or case discharge, close to it.
- **Not in the SAC.** The SDV on every inflow and fuel-gas line, the blowdown valve on the final
  discharge (A.8.3.5, p.45) and the gas detectors (ASH) for enclosed buildings (A.8.2.2.3, A.8.3.3) are
  **not items of SAC Table A-8.2**. They come from the text and Figure A-8 only.

| Item | Device | Required | Exceptions | Today (2 U2 compressors) | Derivable | Verdict |
|---|---|---|---|---|---|---|
| a | PSH, suction | every compressor | a.2: every input source has a PSH that also protects the compressor | 0/2: the KO drum has `PT → PIC` (control) and an `LSHH` trip, and no PSH | a.2 would hold once the KO drum has a PSHH (§2 a) **and** nothing isolates the drum from the suction. The trip `XV` and the butterfly block always stand between them, so a.2 is **not derivable** | **cheap add**: a `PSHH` switch with an alarm on the compressor suction |
| b | PSH, discharge | every compressor | b.2: a downstream PSH, upstream of any cooler, that cannot be isolated from the compressor | 0/2 | none (the aftercooler follows directly) | **cheap add** on the discharge tee, before the check valve |
| c | PSL, suction | every compressor | c.2: every input source has a PSL that also protects the compressor | 0/2 | none | **cheap add** |
| d | PSL, discharge | every compressor | d.2: a downstream PSL that cannot be isolated from the compressor | 0/2 | none | **cheap add** |
| e | PSV, suction | every compressor | e.2: every input source has a PSV that also protects the compressor | 0/2: the KO-drum PSV sits behind the trip `XV` and the suction block | not derivable (isolable) | **cheap add**: one PSV on a suction tee to the flare (one valve and a flare end per compressor; the flare end joins T7's network) |
| f | PSV, discharge | every compressor | f.2: a downstream PSV, upstream of any cooler, not isolable from the compressor · f.3: kinetic compressor that cannot exceed the MAWP of the compressor or the discharge piping | **2/2** (`compressor_discharge_psv`, wired API14C-A8-PSV) | — | **satisfied** |
| g | FSV, final discharge | every compressor | none | **2/2** (`compressor_discharge_check`, wired API14C-A8-FSV) | — | **satisfied**. The check sits right behind the compressor, before the aftercooler; reading that as the unit's "final discharge" is our interpretation for a one-stage unit |
| h | TSH | every cylinder or case | none | 0/2 (`TT → TIAH` bearing temperature is optional, on the machine, and not a TSH) | none | **cheap add**: a `TSHH` switch with an alarm on the discharge tee |

**Scope question.** Are the 4 liquid-ring vacuum pumps (`RotaryCompressor`, role `liquid_ring_pump`)
A.8 compressors? A.8.1 (p.45) speaks of moving hydrocarbon gases, and they do draw column overhead
vapour. If they count, the same six additions apply to them; each already has a discharge check and
reaches a safety valve.

## 7. A-10.2 Shell-tube heat exchangers: printed p.53, PDF p.61

**Analysed per section** (A.10.2.2.1 a, p.51, PDF 59). The heat-receiving and heat-input sections are
analysed separately. A section is also protected against overpressure from a tube leak in the other
section.

Further text, outside the SAC:
- **PSL only on hydrocarbon sections** (A.10.2.2.1 b, p.51). The text asks for a PSL only on a section
  that contains hydrocarbons, a restriction the SAC item does not state.
- **TSH not generally required** (A.10.2.2.2, p.51).
- **Air coolers** (A.10.1, p.51): only the hydrocarbon section is analysed.
- **Location** (A.10.3.1, p.51): the devices may sit on inlet or outlet piping if the pressure drop is
  negligible and they cannot be isolated.

**Generator fact.** An exchanger is one node, so a check has to split its nozzle runs into process and
utility sides. `checks_exchangers.nozzle_runs` already does this.

| Item | Device | Required | Exceptions | Today (76 exchangers; per section) | Derivable | Verdict |
|---|---|---|---|---|---|---|
| a | PSH | each section | a.2: inputs to the section cannot exceed the section's MAWP · a.3: every input source has a PSH that also protects the section · a.4: a PSH on a downstream component that block or regulating valves cannot isolate from the section | **0** on any section | a.3/a.4 **from structure** once vessels carry a PSH (§2 a): e.g. a condenser between a column and a reflux drum with no valve. a.2 for **utility sections** by declaration ("a utility section is designed for its header pressure", the declared utility levels of §6.2). a.2 for process sections: not derivable (no MAWP) | **derive** a.3/a.4 and utility a.2; **defer** the process sections that remain |
| b | PSL | each section (text: hydrocarbon sections) | b.2: minimum operating pressure is atmospheric in service · b.3: a PSL on another component protects the section and cannot be isolated from it in service | **0** | the utility sections (WATER, STEAM fluid class) are outside the **text** condition, which is not an SAC code; record it as a scope exclusion with the page (p.51). b.3 from structure, as a.4 | **defer** process sections (as for vessel PSL) |
| c | PSV | each section | c.2: every input has a PSV set ≤ the section's MAWP **and** the section has its own PSV for fire and thermal relief · c.3: every input has a PSV set ≤ the section's MAWP that cannot be isolated from the section · c.4: downstream PSVs can carry the section's relief load and cannot be isolated · c.5: deleted (4th ed.) · c.6: the inputs cannot exceed the section's MAWP **and** the section cannot be overpressured by the other section · c.7: every input has a PSV set ≤ the section's MAWP **and** the section cannot be overpressured by the other section | **cooling-water sections**: thermal relief on every CW return (`p_thermal_relief` = 1.0). **Steam sections**: none. **Process sections**: only the optional U5 shell PSV (`P_OPTIONAL_ITEM` 0.5); none on reboilers, preheaters or feed/effluent exchangers | c.3/c.4 **from structure**: with TOG207's no-isolation policy on process sides, a process section usually connects, valve-free, to a vessel that has a PSV (reboiler ↔ column, condenser → reflux drum). c.6 for steam sections only with a declared tube-rupture argument; not derivable from the ordinal levels alone | **T10's TOG207-HX-PSD-BOTH-SIDES**: derive c.3/c.4, keep CW thermal relief as c.1, and add a PSD where neither holds (design §6.4) |

## 8. Summary: cheap additions against deferrals

### Counts

| Component | SAC items | Not applicable to the generator | Satisfied today (as drawn, or by an exception derivable now) | Satisfiable by a derivable exception with a declaration or after T10 | Cheap additions proposed | Deferred |
|---|---|---|---|---|---|---|
| A-4.2 pressure vessel | 7 | — | 1 (c PSV) | f (f.3 part), g (g.3 by declaration) | a PSH, d LSH, e LSL | b PSL; f on outlets with no control device |
| A-5.2 atmospheric vessel | 5 | e TSH (no heated tank) | 2 (a vent, d LSL via d.3) | b PSV (b.1 breather / b.2 TOG236 vent) | c LSH (additive tanks) | — |
| A-6.2 fired | 12 live (+1 deleted) | — | 2 (g BSL; h FSL via h.2) | d, f, i (natural-draft declaration); l (l.3 where structure allows) | a TSH medium, e PSH fuel, m FSV; l PSV where l.3 fails | b stack TSH, j air-intake arrestor, k stack arrestor |
| A-7.2 pump | 7 | a, c, e (no pipeline pump) | f for PD pumps (19/19); g for 182/190 | f for centrifugal pumps (f.2 by declaration); b and d for 36 pumps (b.4/d.4 dosing, b.5/d.5 to a tank) | — | b PSH and d PSL on 154 pumps; g on reciprocating pumps is a recorded conflict |
| A-8.2 compressor | 8 | — | 2 (f PSV discharge, g FSV) | — | a, b, c, d, h (switches), e (suction PSV) | — (SDV, BDV and ASH are not SAC items) |
| A-10.2 exchanger | 3 (per section) | — | c on cooling-water sections | a.3/a.4, utility a.2, c.3/c.4 (in T10 / TOG207) | PSD on the sections left without one (TOG207) | a and b on the process sections left over |

Item totals: 7 + 5 + 12 + 7 + 8 + 3 = **42 live items**, plus 1 deleted item (A-6.2 c).

### Instrument-band cost of the cheap package

- **Device form.** Each added sensor is a switch plus an alarm bubble (`xSHH → xAHH` or `xSLL → xALL`),
  so +2 instruments and no valve. The generator already draws this form (`column_parts.drum_instruments`
  `LSHH → LAHH`), and it passes S7/S8.
- **Arithmetic over the 156 dev sheets** (instruments per sheet):

| Addition | Count | Added instruments | Per sheet |
|---|---|---|---|
| Vessel PSHH (73 vessels without a PSH, minus the 17 columns covered by a.4) | 56 | 112 | +0.72 |
| Vessel LSH | about 25 | 50 | +0.32 |
| Vessel LSLL | 59 | 118 | +0.76 |
| Compressor PSH, PSL, TSH (5 devices) | 2 | 20 | +0.13 |
| Furnace TSHH and PSHH | 8 | 32 | +0.21 |
| Additive-tank LSH | 4 | 8 | +0.05 |
| **Total** | | | **about +2.2** |

  The 4 liquid-ring pumps would add another +0.26 if they count as compressors.
- **Measured today.** The current v2.2 plants (no networks yet) measure **28.9–34.19** instruments per
  sheet (seeds 1–5) against the 20–38 band, so the package fits, with seed 2 the closest (about 36.4).
- **What the band rules out.**
  - Vessel PSL (+0.94) and pump PSH/PSL (154 pumps × 2 devices × 2 = 616 instruments, **+3.95 per
    sheet**) would push seed 2 over 38. With no derivable exception for most items, they are the
    deferrals.
- **Valves are the tighter limit.**
  - Seed 2 already has **27.23 valves per sheet** against the 15–28 band. The valve additions are the
    compressor suction PSV (2), the furnace outlet check (8) and the furnace tube PSV where l.3 fails
    (at most 8): at most 18 valves, +0.12 per sheet on average.
  - These should be checked against seed 2 before T10 commits to them.
  - A trip form (sensor, switch, actuator and an `XV`) for any of the switches above would add a valve
    each and is not recommended.
- **Caveat.** These per-sheet figures are arithmetic from the device counts, not a run of the changed
  generator. T7 (networks) will change the per-sheet denominators before T10 lands.

### Reasons for each deferral

- **Pump PSH/PSL** (A-7.2 b, d, on 154 pumps):
  - the only general exception (b.2, 70 % of MAWP) needs pressure values the ordinal model does not have;
  - +3.95 instruments/sheet breaks the band;
  - a pressure switch on every process pump is offshore-production practice that an onshore expert
    reviewer would likely flag.
- **Vessel PSL** (A-4.2 b) and **exchanger PSH/PSL on process sections** (A-10.2 a, b):
  - no derivable exception;
  - band cost;
  - b.2 ("atmospheric in service") must not be read off the ordinal `ATM` level.
- **Vessel FSV on outlets with no control device** (A-4.2 f): f.2 is a judgement, and a check valve on a
  column overhead or a reboiler circuit is not how engineers draw it.
- **Furnace stack TSH, air-intake flame arrestor, stack arrestor** (A-6.2 b, j, k): no stack or air
  intake exists in the model, and adding one needs a new furnace port and class (§4.9 #11, "fired heater
  detail", already binned "if flagged").

## 9. Findings that change the design or earlier notes

1. **A-8.2 has no SDV, BDV or ASH item.**
   - `api-rp-14c-2001-vs-generator.md` lists "SDV on each inflow and fuel gas line; BDV on final
     discharge; ASH if enclosed" under "Recommended devices (SAC)". They come from A.8.2.2.3 and A.8.3.3
     (ASH) and A.8.3.5 (SDV, blowdown valve), p.45, and from Figure A-8; the SAC table itself has items
     a–h only.
   - §4.9 #12 of the design names "BDV" among the SAC devices. It is a text recommendation, not a SAC
     item.
2. **The API PSV item for pressure vessels has no "source cannot exceed" exception.**
   - A-4.2 c offers only c.2–c.6, all about other PSVs or flare scrubbers, and A.4.2.2.1 c (p.27) says a
     vessel should *always* have a PSV. The "input cannot exceed MAWP" exception exists for the **PSH**
     (a.2).
   - The wired T8 rule API14C-A4-OVERPRESSURE cites A.4.2.2.1 a p.26 (the PSH paragraph), asks for a
     relief device, and grants `source_cannot_exceed`. On seeds 1–5 that code fires only on the 12 steam
     condensate drain pots, which are outside A.4's hydrocarbon scope anyway (A.4.1, p.26).
   - Suggested re-cite: the PSD requirement to A.4.2.2.1 c p.27 / SAC A-4.2 c. The pots' code becomes a
     scope exclusion (non-hydrocarbon, fluid class STEAM) rather than a SAC omission.
   - Exchanger sections do have a near equivalent (A-10.2 c.6), but it also needs "no overpressure from
     the other section".
3. **TOG219-VESSEL-PSV and API14C-A4-OVERPRESSURE cite A.4.2.2.1 at p.26.** Item a (PSH) starts on p.26
   and runs onto p.27; items b, c (PSV) and d are on **p.27** (PDF 35). The PSV citation should read
   "A.4.2.2.1 c p.27".
4. **Every enclosure sits at `ATM` in the uncommitted T8 model** (seeds 1–5: columns, reactors, drums,
   separators and tanks alike). The operating-level ordinal therefore cannot support any SAC code that
   says "operates at atmospheric pressure" (A-4.2 a.6, b.2; A-10.2 b.2), nor any MAWP comparison. Those
   need either a declared convention (recorded as such) or a DEFERRED row.
5. **Text versus SAC differences T10 should not paper over:**
   - A.4.2.2.2 (p.28) says level devices are not needed on vessels not designed for liquid-gas separation
     or on small hand-drained traps. The SAC gives the trap exception for LSH only (d.4), not for LSL
     (e has no trap code).
   - A.10.2.2.1 b limits PSL to hydrocarbon sections; the SAC item does not.
6. **Pages the earlier note left unverified are now verified.** The earlier note cited sections only
   ("printed page headers are partly garbled"). The headers are readable in the text layer, and printed
   = PDF − 8 holds throughout.
7. **The TOG192 conflict is confirmed.** SAC A-7.2 g (p.44) has only g.1 and no omission condition.

## 10. Open questions for the architect (T10)

1. Declare the U3 furnace **natural draft** in the hidden state, so that A-6.2 d.2, f.2 and i.2 can be
   derived?
2. Accept the declarations **"centrifugal pump discharge piping is rated for shut-off"** (A-7.2 f.2) and
   **"a utility section is designed for its header pressure"** (A-10.2 a.2)? Without them those items
   become DEFERRED rows.
3. Accept the **alarm-only switch** as the drawn form of an SAC sensor? The function (shut-in at the
   source) is deferred anyway (§4.9 #13).
4. Scope:
   - Are the condensate drain pots outside A.4 (steam service)?
   - Are filters A.4 pressure vessels? API p.28 names fuel-gas filters among pressure vessels.
   - Are the liquid-ring vacuum pumps A.8 compressors?
   - Should a pump that sends product over a battery limit be declared a pipeline pump?
5. Resolve U4 "non_flammable" tank service against the plant-wide HYDROCARBON declaration (§3).

## 11. Pages checked (printed / PDF)

- **SAC tables** (text layer and rendered image):
  - A-4.2: p.29 / PDF 37
  - A-5.2: p.31 / PDF 39
  - A-6.2: p.38 / PDF 46
  - A-7.2: p.44 / PDF 52
  - A-8.2: p.47 / PDF 55
  - A-10.2: p.53 / PDF 61
- **Supporting text** (text layer):
  - §4.3.1–§4.3.3: p.15–16 / PDF 23–24
  - A.3.2 header SAC: p.26 / PDF 34, read for context only
  - A.4.1–A.4.2.2.1: p.26–27 / PDF 34–35
  - A.4.2.2.2–A.4.3.1: p.28 / PDF 36
  - A.4.3.2–A.5.1: p.30 / PDF 38
  - A.5.2: p.31 / PDF 39
  - A.5.2.2.2–A.6.2.2.1: p.32 / PDF 40
  - A.6.2.2.1–A.6.4: p.33 / PDF 41
  - A.7.1–A.7.3.3: p.40 / PDF 48
  - A.8.1–A.8.3.5: p.45 / PDF 53
  - A.10.1–A.10.3.1: p.51 / PDF 59
- **Table list:** p.vi / PDF 8.
- **Not read for this note:** Appendix B composite SAC (p.56–, PDF 64–). Only its first page was looked
  at, to see the item format. It repeats the Appendix A tables.
- **UNVERIFIED:** nothing in the transcription. Item letters the OCR dropped or garbled were read from
  the page images. Per-outlet FSV presence on vessels (§2 f) was **not measured** on the generated plants.
