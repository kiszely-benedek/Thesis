---
component: benchmark/generator v2 — amendment: fluid-process pyDEXPI allowlist, DEXPI drivers, recalibration from real samples
status: accepted with ADR-0058 (2026-10-25); narrowed by the user from the proposed full-vocabulary version
related: [ADR-0058, ADR-0057, ADR-0003, ADR-0016, ADR-0021, ADR-0044, ADR-0053,
          40-design/generator-v2-realism.md, 10-literature/real-pid-samples-2026-10.md,
          10-literature/real-pid-composition-2026-10.md, 10-literature/pid-structural-rules.md]
date: 2026-10-25
---

# Design — generator v2 on a fluid-process pyDEXPI allowlist

This note **amends** `generator-v2-realism.md` (the "base note"). Sections it does not mention stay as they are.
"base §6.7" means section 6.7 there.

## 0. Recommendation (as accepted)

1. **Schema.**
   - A declared fluid-process allowlist: 25 equipment leaves, their 8 parents, all 55 piping classes,
     `PropertyBreak`, 5 instrumentation classes and 4 connectors = **98 topology classes** (v1: 16).
   - Label chains and `piping_kind` are derived by one ancestry rule, which reproduces all 16 v1 chains (measured,
     §2).
   - The rule runs in the adapter layer (ADR-0003) and writes a checked-in table, pinned by a drift test.
2. **Generation.**
   - ADR-0057's fluid patterns U1–U8, plus the crude-desalter pattern U10 and variants.
   - 79 generator classes: 25 equipment, 47 piping, `CheckValve`, `PropertyBreak`, 5 instrumentation.
   - Utilities stay parked (consumer stubs only).
   - Electric motors as DEXPI components, with visible `HS → AEF → machine` signals.
3. **v1 does not move.** `V1_*` pins (V2-T0, committed). Plan-derived schema text. CLASS_NAME pinned for v1
   corpora; on v2 corpora it lists the corpus's classes.
4. **Recalibrated against the real samples** where they contradict ADR-0057 (§7.1).
5. **Milestones.** M1 = first measurable liquid-handling corpus (V2-T12). Headline corpus = end of the fluid
   patterns (V2-T16). Effort estimate: 16 tasks (4 S, 9 M, 3 L).

## 1. What changes against ADR-0057

| Item | ADR-0057 / base note | This amendment |
|---|---|---|
| Schema classes | v1 + 49 curated | 98-class allowlist, chains and kinds derived (§3) |
| Equipment generated | 21 default-on (+ 4 utility, weight 0) | 25 (§6.1): 19 of ADR-0057's default-on ones (blower and fan dropped), + AirEjector, EjectorPump, RotaryCompressor, SpiralHeatExchanger, ElectricalSeparator, RotaryMixer; the 4 utility classes leave the schema |
| Piping generated | 30 leaves + `CheckValve` | 47 leaves + `CheckValve` (§6.2) |
| Drivers | "not used" | motor components on every electric machine; `HS`/VFD → `ActuatingElectricalFunction` → machine (§5.1) |
| `ProcessControlFunction` | "not used" | class of every controller; indicators, alarms, switches stay `ProcessInstrumentationFunction` |
| Agitator | "own node, fed by nothing" (isolated) | `has_agitator` edge from the vessel's `agitator` field |
| U3 fired heater | Furnace + CentrifugalBlower / AxialFan | Furnace only; no burner, blower or chimney nodes |
| Patterns | U1–U8, U9 utilities (weight 0) | U1–U8 with new variants, + U10 crude desalter; U9 stays parked |
| ISA | 11 first letters, ~20 templates | 15 first letters, + 8 templates incl. cascade (§5.3) |
| Real-file import | v1 vocabulary | + opt-in `--vocabulary v2` (§4) |
| Parameters, bands | declared | recalibrated where the samples contradict (§7.1) |
| Tasks | 15 (4 S, 9 M, 2 L) | 16 (4 S, 9 M, 3 L) (§9) |

## 2. Evidence (measured today, pyDEXPI 1.2.0, repo venv; scripts in the session scratchpad, not in the repo)

| Check | Result |
|---|---|
| Classes in `pydexpi.dexpi_classes.pydantic_classes` | 514 |
| `Equipment` descendants | 124 = 75 non-custom leaves + 24 parents + 25 Custom* |
| `PipingComponent` descendants | 61 = 50 leaves + 5 parents + 6 Custom* |
| Instrumentation function classes | PSGF, PIF (+ subclass `ProcessControlFunction`), AF, `ActuatingElectricalFunction` |
| Abstract marking | none on any vocabulary class |
| Ancestry rule (§3.1) against the 16 non-structural v1 `CLASS_SPECS` | **0 mismatches** |
| Rule over all non-custom classes (proposed version) | 164 topology classes; the allowlist is 98 of them |
| `piping_kind` over the 55 piping classes | operated 12, fitting 23, primary_element 10, safety 6, check 3, junction 1 |
| Equipment fields that hold equipment | only `agitator` (`Agitator \| None`), on the `Vessel` and `HeatExchanger` families |
| Driver fields | `Equipment.motors: list[MotorAsComponent]` (AC, DC, CombustionEngine `…AsComponent`, each with `subTagName`); `Equipment.gearBoxes` |
| Removed by `GraphAbstractor.build_conceptual_graph` | 26 equipment-internal classes, incl. `MotorAsComponent` (and subclasses), `GearBox`, `Impeller`, `AgitatorRotor`, `Chamber`, `TubeBundle` |
| Micro model through `load_complete_graph` + `abstract_conceptual_graph` | kept: `tank → agitator` (`reference/agitator`); `AEF → pump` (`reference/actuatingElectricalLocation`, through the machine nozzle); `PIF → AEF` (`composition/actuatingElectricalFunctions`); `PropertyBreak` inline; `Compensator`, `Funnel`, `Hose` inline. Gone: the pump's motor component and gearbox. A standalone `AlternatingCurrentMotor`: no edge |
| `ActuatingElectricalLocation` subclasses | `Nozzle`, `PipingNetworkSegment` |
| Custom* | `typeName`, `typeURI`; ancestry `CustomPump : CustomObject : Pump` |
| Tag fields | safety devices `positionNumber`; other piping `pipingComponentNumber`; AEF `actuatingElectricalFunctionNumber` |
| EX01 | no AEF, no motors |
| `qa/schema_text.py` | labels and types from the load plan; property list fixed (`VISIBLE_NODE_PROPERTIES`) |
| `qa/final_answer.py` CLASS_NAME | lists `sorted(NodeClass)`; the saved V2-T1 partial patch pins it to `V1_NODE_CLASSES` |
| Neo4j | indexes only on `CorpusNode`; more labels add no index |
| Families | `families_loop.py:119` picks controllers by `node_class == ProcessInstrumentationFunction`; flow walks go through `common.send_to_successors` / `relation_successors` |

Real-sheet evidence: `10-literature/real-pid-samples-2026-10.md` (IDs H1…WM; [HC] hand count, [R] read).

**[Vw]** = viewed by me today: Valdosta I-1..I-3 (legends, belt-press sheet; motors as "M" on machines; VFD speed
set points); Wenatchee 000Y-01..04 (motor-operated valves, a flocculation tank with mixer `MX-560-01`); the Wikimedia
NaCl crystallizer sheet.

**[L]** = the symbol is in the Valdosta legend I-2: it is used on that project's P&IDs, with no frequency.

## 3. Schema

### 3.1 The rule, applied to an allowlist

```
ROOTS = {Equipment: ("TaggedPlantItem",), PipingComponent: (), PropertyBreak: (),
         ProcessSignalGeneratingFunction: (), ProcessInstrumentationFunction: (), ActuatingFunction: (),
         ActuatingElectricalFunction: (), PipeOffPageConnector: (), SignalOffPageConnector: ()}
ALLOWLIST   = EQUIPMENT_LEAVES (25, §6.1) ∪ their pyDEXPI parents (8) ∪ every non-custom PipingComponent class (55)
              ∪ {PropertyBreak} ∪ {PSGF, PIF, ProcessControlFunction, AF, ActuatingElectricalFunction}
              ∪ the 4 off-page connector leaves
root(C)     = first class in C's MRO that is in ROOTS
labels(C)   = [A for A in C.__mro__ if A is a pyDEXPI class and issubclass(A, root(C))] + ROOTS[root(C)]
category(C) = EQUIPMENT | PIPING (PipingComponent, PropertyBreak) | INSTRUMENTATION | CONNECTOR, by root
```

- Mixins (`ChamberOwner`, `NozzleOwner`, `CustomAttributeOwner`, `SignalConveyingFunctionSource`) are not
  subclasses of a root, so they never enter a chain. That is why `CentrifugalPump:Pump:Equipment:TaggedPlantItem`
  comes out exactly as in v1.
- **The 8 equipment parents** are `Pump`, `Compressor`, `Vessel`, `HeatExchanger`, `Heater`, `Separator`, `Filter`
  and `Mixer`. They are in the schema so that a real file's generic item, or a dropped sibling, imports as its
  family. Examples: `Silo` → `Vessel`, `Boiler` → `Heater`, `CentrifugalBlower` → `GenericItem` (no `Blower` in the
  allowlist).
- **Toggling a class.** The allowlist is a declared tuple. Adding or removing a class is one line, plus
  regenerating the table.

**Files.**
- `src/plantgraph/adapters/pydexpi_vocabulary.py`: `ALLOWLIST`, `derive_vocabulary() -> list[VocabularyRow]`.
  This is the only pyDEXPI import for this.
- `src/plantgraph/graph/schema_vocabulary.py`: generated literal rows `(name, labels, category, piping_kind,
  tag_prefix, leaf)`, with a header naming the generator and the pyDEXPI version.
- `scripts/derive_schema_vocabulary.py`: writes it.
- `tests/test_schema_vocabulary.py`: table == `derive_vocabulary()`; pyDEXPI pinned to 1.2.0.
- `graph/schema_classes.py`: the `NodeClass` enum (103 members = 98 + 4 structure + `GenericItem`; from the saved
  partial patch).
- `graph/schema.py`: builds `CLASS_SPECS` from the table and keeps `V1_*`. No pyDEXPI or `benchmark` import in
  `graph/` (base invariant).

### 3.2 `piping_kind` from ancestry

The first ancestor that matches wins: `CheckValve` → check; `SafetyValveOrFitting` → safety;
`InlinePrimaryElement` → primary_element; `OperatedValve` → operated; `PipeFitting` → fitting.

**Overrides:**
- `PipeTee` → junction.
- `PropertyBreak` → `break` (a new kind; it is not a `PipingComponent`).

Constants:
- `VALVE_CLASSES` = operated ∪ check ∪ safety;
- `FITTING_CLASSES`, `JUNCTION_CLASSES`, `PRIMARY_ELEMENT_CLASSES`, `BREAK_CLASSES`;
- `CONTROL_VALVE_BODY_CLASSES` = {Globe, Ball, Butterfly, Angle, AngleGlobe, AngleBall}, a declared list
  (ADR-0044, + 2 angle bodies).
- v1 values unchanged (partial-patch tests).

### 3.3 Tag prefixes (declared; the samples show five equipment-tag grammars in 16 sheets, samples note §1.6)

**Equipment.** ADR-0057's codes are kept, plus:

| Class | Code | Class | Code |
|---|---|---|---|
| EjectorPump, AirEjector | `EJ` | RotaryCompressor | K |
| SpiralHeatExchanger | E | ElectricalSeparator | `DS` |
| RotaryMixer | M | — | — |

**Piping.**
- StraightwayValve `SWV`; angle bodies take their straight body's code.
- TurbineFlowMeter and VolumeFlowMeasuringElement `FE`.
- InLineMixer `MX`.
- PipeFlangeSpade / PipeFlangeSpacer `SB` (tagged skillet blinds, F2 [HC]).
- Silencer `SL`.
- `UNTAGGED_CLASSES` += Flange, FlangedConnection, PipeCoupling, ClampedFlangeCoupling, Compensator, Hose, Funnel,
  Penetration, VentilationDevice, PropertyBreak, ActuatingElectricalFunction (untagged like the AF, ADR-0044).

### 3.4 Relations and endpoints

| Change | Why | v1-safe because |
|---|---|---|
| New `Relation.HAS_AGITATOR` (vessel or exchanger → `Agitator`), mapped from `reference/agitator` | the only equipment-to-equipment field in pyDEXPI; the name explains itself in the plan-derived type list | v1 plans have no such edge |
| `control` targets += `EQUIPMENT_CLASSES`, sources += AEF; validation pair rule: equipment targets only from AEF | `HS`/VFD → AEF → machine | sets only grow |
| `send_signal_to` targets += AEF | PIF/PCF → AEF | grows only |
| `send_to`, `measured_by` over `EQUIPMENT ∪ PIPING` (partial patch) | fittings, primary elements, breaks inline and sensed | grows only |
| Adapter rules, gated by `vocabulary`: `reference/agitator` → `has_agitator`; `reference/actuatingElectricalLocation` → `control`; `composition/actuatingElectricalFunctions` stays dropped (the `SignalLineFunction` edge carries the signal, as for AF) | measured §2 | default vocabulary = v1; EX01 has no AEF |

`VISIBLE_NODE_PROPERTIES` and `VISIBLE_EDGE_PROPERTIES` do not change.

## 4. Importing a real DEXPI file (recommended and kept: cheap, S)

- `topology_node_class(label, vocabulary: frozenset[str] = V1_IMPORTABLE_CLASSES)` keeps today's behaviour.
  `V2_IMPORTABLE_CLASSES` = the 98 allowlist classes + `GenericItem`.
- `--vocabulary {v1,v2}` on the Proteus import and the ingest CLI, default `v1`. The import record carries the
  field only when `v2`, so v1 records stay byte-identical. Corpus ids: `EX01v2` (EXP-0001's `EX01` untouched; EX01
  golden).
- **Why keep it.** Under `v2`, EX01 keeps `ReciprocatingPump`, `SwingCheckValve`, `PipeTee`, `BlindFlange`,
  `PipeReducer`, `PlateHeatExchanger` and `TubularHeatExchanger` as themselves. That is the industrial-use case,
  measurable with the existing EX01 QA file. Non-allowlist classes still land on their family or `GenericItem`,
  so nothing is lost.
- **Custom*:** ancestor walk to the nearest allowlist class (`CustomPump` → `Pump`). `CustomEquipment`,
  `CustomPipingComponent` → `GenericItem` (ADR-0016, with `dexpi_labels`). `typeName` stays in the DEXPI file.

## 5. Generation

### 5.1 Drivers, agitators, electrical actuation (Q1 = A)

| Construct | DEXPI model | Graph result (measured §2) | Placement |
|---|---|---|---|
| Electric motor | `machine.motors = [AlternatingCurrentMotorAsComponent(subTagName="PM-1203A")]`; [`gearBoxes`] on agitators and rotary mixers | none (removed by pyDEXPI); kept in the DEXPI file | every pump (except EjectorPump), compressor (except AirEjector), agitator, rotary mixer. Real sheets draw an untagged "M" on the machine (Valdosta I-3, Wenatchee 000Y-01 [Vw]; samples digest) |
| Start / stop | PIF `HS` → `SignalLineFunction` → AEF at a dedicated machine nozzle | `HS -send_signal_to-> AEF -control-> machine` | `p_motor_hs` per machine (declared 0.5); HS per machine on H3 (HS ×10), F3 HOA/S-S [HC] |
| VFD speed | PCF `xIC` → AEF | `FT/PT -…-> xIC -send_signal_to-> AEF -control-> pump` | dosing pumps (U8), compressors (U2); Valdosta "speed setpoint" [Vw] |
| Running status | PSGF `YI` on the machine | `machine -measured_by-> YI` | with the HS (H3 YI ×2 [HC]) |
| Agitator | `vessel.agitator = Agitator` + motor component | `vessel -has_agitator-> agitator` | U8 agitated vessel; U3 agitated-reactor variant (D2 agitated reactor [HC]) |

Driver and machine share the tag number (`P-1203A` / `PM-1203A`, DEXPI `subTagName`); no relation is needed.

### 5.2 Patterns: new variants and U10

| Pattern | Additions |
|---|---|
| U1 column | **vacuum variant**: overhead condenser → two-stage `AirEjector` A/B with motive-steam stubs and inter-condenser (H2 [HC]) [or liquid-ring `RotaryCompressor`]; ejector discharge → `Silencer` → open end; **cascades** TC → steam FC, drum LIC → FC (§5.3); reboiler **condensate variants** (§5.4) |
| U2 compressor stage | **screw variant** `RotaryCompressor`; motor current `IT → II` on the machine (HW1 IT/II [HC]); VFD on the compressor (§5.1) |
| U3 heater–reactor–separator | Furnace **without blower**: fuel-gas stub with double block and bleed (F1 [HC]); BE → BSL flame trip on a furnace nozzle (base); **agitated reactor** variant (`PressureVessel` + `Agitator`); skillet blinds at reactor and furnace inlets (§5.4); `UC` multivariable on the reactor (D1 UC [HC]) |
| U4 tank farm | angle bottom-drain valves; `TurbineFlowMeter` / `VolumeFlowMeasuringElement` metering variants; atmospheric `VentilationDevice` on non-flammable tanks; point-level `LSH`/`LSL` |
| U5 exchanger train | **`SpiralHeatExchanger`** variant (viscous / fouling service) [U] |
| U6 flash drum | split-range template available (off by default) |
| U7 filter package | unchanged |
| U8 blending | **eductor** variant (`EjectorPump` with motive liquid) [L]; **`RotaryMixer`** variant [U]; `InLineMixer` on additive injection [U]; `StraightwayValve` (diaphragm-type) on corrosive dosing lines [L for the symbol, U for the mapping]; agitated vessel with `has_agitator`; VFD dosing |
| **U10 crude desalter (`DES`)** | wash-water `InLineMixer` → mixing `GlobeValve` (ΔP, PDIC) → `ElectricalSeparator` → brine pump set; interface LIC; brine AT → AI. Placed in the grammar between the first and second U5 of a train with `p_desalter` (declared 0.3). Drawing group: G1 [U] |

**Grammar.** Base §8 unchanged, with the U10 slot added. No areas and no utility islands; S13 (plant weakly
connected) stands.

**Coverage deck.** Each pattern has a seeded deck of its variants: shuffle all, deal in order, reshuffle when
empty. The deck is keyed by pattern id in the master stream, so unit *u*'s variant depends only on units < *u*
(prefix stability holds). Every variant appears once per |variants| instances.

**Per-train conventions.** One train = one design contractor: `on_off_letter` and `spare_naming` are drawn once per
train and fixed inside it.

### 5.3 ISA templates added (base §4.4 stays)

Controllers (letters with C) are `ProcessControlFunction`. Indicators, alarms, switches and HS stay
`ProcessInstrumentationFunction`.

| Template | Placed in | Grounding |
|---|---|---|
| **Cascade**: master `xIC` → slave `FIC` (← `FT`) → AF → `FV`; TC → steam FC, LIC → FC, AIC → TIC | U1, U3, U6; `p_cascade` per eligible slot (declared 0.5) | F2 4 cascades, H3 LC → FC → LV [HC]; frequency not countable |
| **Split range**: `PIC` → AF₁ → `PV-A`, AF₂ → `PV-B` | U1 drum, U6; `p_split_range` **0** by default | one unconfirmed case (D1 [U]) |
| `HS → AEF → machine`, `YI` | motor-driven machines | H3, F3 [HC]; Valdosta [Vw] |
| `xIC → AEF` (VFD) | U2, U8 | Valdosta [Vw] |
| `LSH`, `LSL` → `LAH`, `LAL` (point level) | tanks, sumps, drain pots | LSL / LSHH on H2, H3 [HC] |
| `CT → CI`, `CSHH → XV/YV` | condensate drain pot (tube-leak trip) | H1 CE/CT/CI/CSHH [HC] |
| `IT → II` (motor current) | U2 machines | HW1 [HC] |
| `UC` (multivariable) | U3 reactor | D1 [HC] |

**On-off valves** take the train's letter: `XV`/`XY` or `YV`/`YY` (WTP, HWVP YV/YY; FB&D XV [HC]).

**First letters:** A B C F H I L P S T U V X Y Z (15). 14 of them are among the 18 the samples show; B is from
FB&D [V] and the base flame trip.

### 5.4 Trims added (base §6 stays)

| Trim | Arrangement | Grounding | Parameter (declared) |
|---|---|---|---|
| Open drain | drain valve → `Funnel` (instead of `BlindFlange`) | "open equipment drain" [L] | `p_open_drain` 0.3 |
| Orifice flange set | `Flange` → `RestrictionOrifice` → `Flange` | C03 Equinor: Flange 3, RO 1 [C] | every RO |
| Skillet blind | `PipeFlangeSpade` (closed) / `PipeFlangeSpacer` (open), tagged `SB` | F2 skillets #545–547, #720 [HC] | `p_skillet` 0.5 at reactor and furnace inlets |
| Flexible connector | `Compensator` on pump suction and discharge | W2 [HC]; bellows coupling [L] | `p_flex_connector` 0.3 |
| Removable spool | `FlangedConnection` either side of a `ConicalStrainer` | [U] | with every temporary strainer |
| Flushing / purge connection | `GateValve` → `PipeCoupling` (quick connect) → capped open end, on vessels and pump casings | quick-connect coupling [L]; W1 "nitrogen purge tap with isolation valve … cap" (samples §6) | `p_flush_connection` 0.3 |
| Atmospheric steam vent | PSV on a steam supply stub, ejector discharge → `Silencer` → open end | [U] | on U1 ejectors and steam stubs |
| Atmospheric tank vent | `VentilationDevice` (instead of breather + arrestor) | [U] | non-flammable tanks |
| Spec break | `PropertyBreak` wherever the line number changes spec (base L20) | spec-break flags PCW\|DEP, HPS\|DEP (samples §6 [R]) | always |
| Condensate | `trap` (base 6.14) / `trap_station` (trap + blocks + bypass) / `drain_pot` (small `PressureVessel`, LT/LIC/LV, CT/CSHH) | F2 trap stations, H1 drain pot [HC] | `condensate_mode_weights` 2 : 1 : 1 |
| Pump pressure | per-pump PI (base 6.3) / header PT | FB&D, W2 vs WTP H3 [HC] | `pump_pressure_mode_weights` 3 : 1 |
| Fuel-gas double block and bleed | XV → vent XV → XV | F1 [HC] | U3 fuel gas |
| Valve bodies | `AngleGlobeValve`, `AngleBallValve` (CV body, bottom drain), `AnglePlugValve` (viscous bottom drain), `StraightwayValve` (diaphragm-type on dosing), `IlluminatedSightGlass` (sight-glass variant) | [U]; diaphragm valve [L] | `class_weights` per role |

## 6. Class lists

Legend: **A** = in ADR-0057; **S** = shown by a read source; **L** = legend symbol only; **U** = declared;
**flag** = kept by the architect for a fluid-process reason the user has not yet seen; easy to veto.

### 6.1 Equipment, 25 generated (of 75 leaves)

| Family | Kept → pattern (grounding) |
|---|---|
| Pump (4) | CentrifugalPump → all pump sets (A); ReciprocatingPump → U8 dosing (A); RotaryPump → U4 viscous (A); **EjectorPump** → U8 eductor (L, flag) |
| Compressor (4) | CentrifugalCompressor, ReciprocatingCompressor → U2 (A); **RotaryCompressor** → U2 screw, U1 liquid-ring vacuum (L, flag); **AirEjector** → U1 vacuum (S: H2) |
| Vessel (2) | Tank, PressureVessel (A) |
| Column (1) | ProcessColumn (A) |
| Heat exchange (5) | TubularHeatExchanger, PlateHeatExchanger, AirCoolingSystem (fans internal), ElectricHeater (A); **SpiralHeatExchanger** → U5 (U, flag) |
| Heater (1) | Furnace → U3, no burner, blower or chimney nodes (A; F1) |
| Separator (3) | GravitationalSeparator, ScrubbingSeparator (A); **ElectricalSeparator** → U10 desalter (U, flag) |
| Filter (2) | LiquidFilter, GasFilter (A) |
| Mixer / agitator (3) | StaticMixer, Agitator (A; Agitator now via `has_agitator`; D2); **RotaryMixer** → U8 (U) |

The 6 new ones: 1 S (AirEjector), 2 L (EjectorPump, RotaryCompressor), 3 U.

**Dropped from generation and from the schema (50 leaves)**, by the user's scope. They import by ancestry, to a
kept parent where one exists, else to `GenericItem`:
- CentrifugalBlower, AxialFan (ADR-0057's U3 blower and fan), AxialBlower, RadialFan.
- Boiler, SteamGenerator, Burner, Chimney, Flare.
- WetCoolingTower, DryCoolingTower, SprayCooler.
- SteamTurbine, GasTurbine, AlternatingCurrentGenerator, DirectCurrentGenerator.
- AlternatingCurrentMotor, DirectCurrentMotor, CombustionEngine (standalone; the AC motor *component* is generated).
- AxialCompressor (Q5).
- Silo, Feeder, BatchWeigher, ContinuousWeigher, Conveyor, Lift, LoadingUnloadingSystem, PackagingSystem.
- Crusher, Grinder, RevolvingSieve, StationarySieve, VibratingSieve.
- RotatingGrowthAgglomerator, RotatingPressureAgglomerator, ReciprocatingPressureAgglomerator.
- RotatingExtruder, ReciprocatingExtruder, Kneader.
- ConvectionDryer, HeatedSurfaceDryer, ThinFilmEvaporator.
- FilteringCentrifuge, SedimentalCentrifuge, MechanicalSeparator.
- Truck, RailWaggon, Ship, TransportableContainer, ForkliftTruck.

The 24 non-allowlist parents and 25 Custom* equipment classes are also outside the schema.

### 6.2 Piping, all 55 in the schema; 47 of 50 leaves generated

**Generated, from ADR-0057 (30):** as base §4.2.

**Generated, new (17):**

| Class | Kind | Grounding |
|---|---|---|
| AngleBallValve, AngleGlobeValve, AnglePlugValve | operated | U |
| StraightwayValve | operated | L (symbol), U (mapping) |
| TurbineFlowMeter, VolumeFlowMeasuringElement | primary element | L (turbine, ultrasonic meters) |
| Flange | fitting | S: C03 [C] |
| Compensator | fitting | S: W2 [HC] |
| PipeFlangeSpade | fitting | S: F2 [HC] |
| PipeCoupling | fitting | L (quick connect) |
| Funnel | fitting | L (open drain) |
| PipeFlangeSpacer | fitting | U (open counterpart of the skillet) |
| FlangedConnection | fitting | U |
| InLineMixer | fitting | U |
| IlluminatedSightGlass | fitting | U |
| Silencer | fitting | U |
| VentilationDevice | fitting | U |

**Import-only (3 leaves).** Their only placements were in dropped contexts:
- `Hose` (truck/rail/ship loading);
- `ClampedFlangeCoupling` (loading coupler);
- `Penetration` (Q5).

Piping parents `OperatedValve`, `SafetyValveOrFitting`, `InlinePrimaryElement` and `PipeFitting` are import-only.
`CheckValve` is generated (base §4.2).

### 6.3 Instrumentation, break, connectors

- PSGF, PIF, AF (A).
- **ProcessControlFunction** (controllers) and **ActuatingElectricalFunction** (HS / VFD → machine), both new.
- `PropertyBreak` (S, spec breaks).
- 4 off-page connectors (splitter).

**Totals:**
- Generator classes = 25 + 47 + `CheckValve` + `PropertyBreak` + 5 = **79**; with the 4 connectors, 83 of the 98
  schema classes appear in a v2 corpus.
- Import-only: 15 = 8 equipment parents, 3 piping leaves, 4 piping parents.

## 7. Consequences

### 7.1 Parameters and bands changed by the samples

| Item | Base value | New value | Basis (samples note) |
|---|---|---|---|
| `p_cv_station` | 0.8 | **0.6** | D1: 5 of 8 (0.625); F2 ≥ 4 of ≥ 6 (lower bounds); WTP 0 of 4 [HC]. Company-dependent; sweep |
| Cascade loops | excluded | templates, `p_cascade` 0.5 (declared) | F2 4, H3 1 [HC] |
| Split range | excluded | template, `p_split_range` 0 | one unconfirmed case |
| On-off letter | X | per train ∈ {X, Y}, 1 : 1 (declared) | WTP and HWVP YV/YY; FB&D XV [HC] |
| Spare naming | A/B/C suffix | per train ∈ {suffix, consecutive}, 3 : 2 | 2 of 5 tag styles number spares consecutively (Covestro PA100/PA101, Wenatchee PMP-510-06/-07) [HC] |
| Pump-set drawing group | with the suction vessel | variant `own_sheet`, 2 : 1 (declared) | FB&D vs WTP [HC] |
| `min_equipment_per_sheet` | 3 | **1** (Q6 = A) | 4 of 16 sheets carry 1–2 items [HC] |
| `max_equipment_per_sheet` | 10 | **16** (Q6 = A) | D1 16; 15 of 16 sheets ≤ 10 [HC] |
| `p_triple_pump_set` 0.15, `p_single_pump` 0.2 | — | unchanged | inside the observed ranges 0–3/8 and 0–1/3 [HC] |
| Line numbers | full grammar | kept everywhere | wastewater sheets carry none [HC]; the headline corpus is fluid-process, and G1 at DRAWING_ONLY relies on unique line numbers |
| Band: equipment per sheet | ≥ 90 % in 3–10, none > 10 | every sheet 1–16; ≥ 90 % ≤ 10 | 1–16; 15 of 16 ≤ 10 [HC] |
| Band: off-page stubs | mean 5–11; every sheet ≤ 16 | mean 5–11; every sheet ≤ 21 | 1–21 (HW1 ≈ 21) [HC] |
| Band: distinct kinds | ≥ 21 / ≥ 28 / ≥ 18 | **class coverage**: each of the 79 generator classes ≥ 1 on D1000g2; D100g2 reported | §8 |
| Signal off-page connectors | not reported | reported per sheet, no band | WTP 5–6 per sheet [HC]; cascades and split loops can create them |

All other base bands stay. They are OPEN100-based (a fluid / steam plant), which fits the fluid-only scope better
than the proposed version did.

### 7.2 Class weights

Weights are declared per role (base §8.2). The variant deck (§5.2) cycles through every eligible class. A role's
primary class is dealt twice per deck: centrifugal pumps, gate valves as blocks, globe CV bodies,
`FlowMeasuringElement`, tubular exchangers. No weight is a frequency claim (composition note §10).

### 7.3 Scale

- Per-sheet density stays bounded by the sheet caps (`max_symbols_before_stubs` 100; equipment ≤ 16).
- Total nodes = sheets × density, so the x-axis is unchanged.
- By construction, each motor-driven machine adds 1 motor component, 1 nozzle and, with `p_motor_hs`, 1 HS PIF,
  1 `SignalLineFunction`, 1 AEF and 1 `YI` PSGF. That is up to 5 DEXPI objects and up to 3 graph nodes per machine.
- R0 re-checks plant-generator.md's kill criterion and K-NEO at M1 and at the headline corpus.

### 7.4 Question families

| Family / code | Change | v1 effect |
|---|---|---|
| `families_loop._controllers_by_tag` | select controllers by label (`ProcessInstrumentationFunction` ∈ labels: PIF or PCF); a candidate needs exactly one AF successor and exactly one **PSGF** predecessor (a cascade slave also has a PCF predecessor); split-range controllers (2 AFs) skipped and counted | v1 has no PCF or cascade → same list (question goldens) |
| LOOKUP_TYPE / CLASS_NAME (Q3 = B) | instruction lists the node classes present in the corpus's load plan | v1 corpora: pinned `V1_NODE_CLASSES` text, byte-identical |
| TAG_PATH ("equipment items and valves only") | reference paths keep `EQUIPMENT ∪ VALVE_CLASSES`; fittings, primary elements, breaks skipped | v1 none |
| Valve counts | `VALVE_CLASSES` (valves only) | v1 classes unchanged |
| Flow walks | `send_to` only (verify every family uses `send_to_successors` or `relation_successors(send_to)`); `has_agitator` and AEF `control` never enter a flow walk | — |
| UPSTREAM_ISOLATION | operated set now includes angle bodies and `StraightwayValve` | v1 none |
| Newly possible, not added to the frozen sets | "which hand switch starts P-…", "which agitator is on R-…", "which controller sets the speed of P-…" | demo / industry use |

### 7.5 F1, store, schema text, demo

- **F1:** same code, prompts, pins and policies (ADR-0053). On v2 corpora only the CLASS_NAME list differs, and
  its prompt hash is recorded. The plan-derived label list grows; its length on H100g2 is measured in R3.
- The frozen paragraph's sentence "equipment -measured_by-> transmitter" is incomplete on v2: sensors on line
  components, AEFs on machines. Base Q2's rule applies: frozen first; a v2 legend only as a labelled system.
- **Store:** labels via `labels_for`. No per-label index (§2). Relationship type `has_agitator` is new.
- **Splitter:** the rider rule gives an AEF, its HS and an agitator the group of their machine or vessel.
  Invariant S20 forbids cutting `has_agitator` and AEF `control`.
- **Demo:** `family_of` walks the label chain to the first entry of `GLYPH_FAMILIES`: 8 equipment parents +
  `ProcessColumn` and `Agitator`, then 7 piping kinds, then 5 instrument kinds. Leaf glyphs are kept where the base
  note has them; otherwise the family glyph is drawn with the class name. Test: every one of the 98 classes
  resolves; v1 exports unchanged.

## 8. Validation additions (base §12 stays)

- **Coverage report** (`benchmark/v2/coverage.py`, inside the composition CLI): per generator class, the count,
  the patterns it came from, and its grounding tag (§6). Acceptance: zero absent on D1000g2; D100g2 reported,
  absentees named.

| # | Invariant |
|---|---|
| S18 | checked-in vocabulary table == `derive_vocabulary()`; v1 rows == v1 `CLASS_SPECS` |
| S19 | every `control` edge into equipment comes from an AEF; every AEF has one `control` target and ≥ 1 signal source |
| S20 | no `has_agitator` or AEF `control` edge crosses a sheet |
| S21 | every motor-driven machine has exactly one `MotorAsComponent`, sub-tagged with the machine's number |
| S22 | cascade: the slave PCF has one PSGF and one PCF predecessor; the valve carries the slave's loop tag (ADR-0044) |
| S23 | `on_off_letter` and `spare_naming` constant within a train |
| S24 | no generator class outside the allowlist, no Custom*, no parent other than `CheckValve` / `ProcessInstrumentationFunction` |

## 9. Coder tasks (replace base §14 from T1)

- One Sonnet coder at a time (ADR-0006). Sizes are estimates; pace unmeasured.
- Each task ends with the full suite green, the `V1_*` goldens unchanged, `ruff` and `mypy --strict` clean, files
  ≤ ~400 lines, and the coder style rules.
- The user commits each task.
- T1 reuses the saved V2-T1 partial (`scratchpad/v2t1_partial/`: the schema split, kind constants,
  `V1_NODE_CLASSES` + `final_answer` pin, pin tests). It replaces the curated `schema_classes.py` body with the
  generated table.

| # | Task | Files | Tests | Acceptance | Size |
|---|---|---|---|---|---|
| T0 | Freeze v1 | — | — | **done** (`0ba680a`) | S |
| T1 | **Schema from the rule on the allowlist**: derivation, table, 103-member enum, kinds incl. `break`, constants, `has_agitator`, endpoints + AEF pair rule, untagged set, `V1_NODE_CLASSES` pin | `adapters/pydexpi_vocabulary.py`, `graph/schema_vocabulary.py`, `graph/schema_classes.py`, `graph/schema.py`, `graph/validation.py`, `qa/final_answer.py`, `scripts/derive_schema_vocabulary.py` | S18; pins ⊂ live; live ∩ v1 = pins; label regex | all v1 goldens unchanged | M |
| T2 | Tag grammar + role vocabulary (new codes, 15 letters, X/Y on-off, suffix/consecutive spares) | `benchmark/v2/tags.py`, `benchmark/v2/vocabulary.py` | base T2 + new productions round-trip; consecutive spares injective | — | S |
| T3 | Config, plan models, oracle, **variant deck**, per-train conventions | `benchmark/v2/config.py`, `plan_models.py`, `deck.py`, `tests/graph_plant_builder_v2.py` | base T3 + deck covers every variant per cycle, prefix-stable | `GeneratorConfig` JSON unchanged | M |
| T4 | DEXPI builder v2 core (base T4) | as base T4 | as base T4 | as base T4 | L |
| T5 | Builder and adapter extensions: motor components, AEF + signal line, agitator reference, `PropertyBreak`; adapter `vocabulary` parameter and the three edge rules | `adapters/pydexpi_builder_v2_equipment.py`, `adapters/pydexpi_rules_v2.py`, `adapters/pydexpi_adapter.py` (signature) | the §2 probe as assertions; S19, S21 | probe reproduced | M |
| T6 | `--vocabulary v2` import, Custom* rule, `EX01v2` | `adapters/pydexpi_proteus_import.py`, `ingest/__main__.py`, import record | EX01 under v1 = golden; under v2 true classes; Custom* table | `EX01v2` ingests | S |
| T7 | Trims: base 6.1–6.19 + §5.4 | `benchmark/v2/trims.py`, `trims_extra.py` | one per trim + its rule invariant | — | L |
| T8 | Instruments: base templates + §5.3 (cascade, split range, AEF, PCF, X/Y) | `benchmark/v2/instruments.py`, `instruments_extra.py` | S8, S9, S22 | — | M |
| T9 | Patterns A: pump set (own-sheet, header-PT, flexible-connector variants), U4, U6, U7 | as base T7 | as base T7 | — | M |
| T10 | Flowsheet grammar, planner, sheets (T9 patterns; U10 slot; sheet knobs 1–16) | as base T8 | as base T8 | first v2 plant end to end | L |
| T11 | Dispatch, preset, size search, CLI | as base T9 | as base T9 | `--headline-v2 --target-sheets 10 --no-neo4j` runs | S |
| T12 | Splitter strategy + downstream fixes (base T10 + §7.4 + S20) | as base T10 + `qa/questions/families_loop.py` | every family generates on v2; v1 question sets byte-identical | **M1: first measurable v2 corpus (liquid handling)** → main session: R0, R1 | M |
| T13 | Patterns B: U1 (vacuum/ejector, cascades, condensate variants), U5 (spiral), U10 desalter | `patterns/{column,heat,desalting}.py` | per pattern + S22 | — | M |
| T14 | Patterns C: U2 (screw, VFD, IT), U3 (furnace without blower, DBB, agitated reactor, skillets, UC), U8 (eductor, rotary mixer, in-line mixer, agitator, dosing VFD) | `patterns/{compression,reaction,blending}.py` | per pattern + S19 | — | M |
| T15 | Demo families and glyphs for the 98 classes (rule-based) | `demo/drawing/{families,glyphs,glyph_families}.py` | every class → glyph; v1 exports unchanged | visual check possible | S |
| T16 | Composition + coverage report, invariant suite S1–S24, headline preset v2 | `benchmark/v2/{composition,coverage}.py`, `tests/v2/test_invariants.py`, `ingest/headline_v2.py` | report = hand count on a fixture; coverage 0 absent at D1000g2 | **headline corpus** → R0–R3 free, visual check, then paid R4/R5 estimates to the user | M |

Totals after T0: **16 tasks — 4 S (T2, T6, T11, T15), 9 M, 3 L (T4, T7, T10)**.

**Partial results along the way:**
- M1 (T12) is measurable early.
- T6 delivers the industrial import right after T5.
- The headline corpus is ready at T16.

## 10. Risks

| Risk | L / I | Mitigation | Revisit |
|---|---|---|---|
| A v1 artefact changes (enum growth reaches a prompt; edge rules reach EX01) | medium / high | pins, plan-derived text, CLASS_NAME pin, vocabulary-gated rules, EX01 golden | any golden diff blocks the task |
| [U] placements (3 equipment, 9 piping new) read as invention | certain / low | grounding tag per class; flagged items listed for veto | a sample shows otherwise |
| Families crash on PCF, cascade or split range | high without T12 / high | §7.4 fixes, v1 question goldens | zero-candidate family reported |
| pyDEXPI edge cases (agitator reference, AEF, `PropertyBrake` typo in pyDEXPI's collapse list) | medium / medium | §2 probe as T5 tests | drop the construct and say so |
| Coverage at ~100 sheets incomplete | likely / low | deck; absentees named; acceptance at D1000g2 | — |
| Bands fail | medium / medium | parameters, logged rounds | > 3 rounds → report the gap |
| pyDEXPI upgrade | low / medium | S18 drift test, version pin | — |
| Driver–machine link only by tag number | certain / low | DEXPI's own convention | pyDEXPI gains a relation |

## 11. Decisions recorded (2026-10-25) and what is still open

Answers: Q1 = A, Q2 = B, Q3 = B, Q4 = B, Q5 = B, Q6 = A (ADR-0058 Status).

Still open for the user (vetoes only; defaults hold if unanswered):
1. **Architect-flagged keeps:** `EjectorPump` (eductor in blending), `RotaryCompressor` (screw compressor,
   liquid-ring vacuum), `SpiralHeatExchanger` (viscous / fouling service), `ElectricalSeparator` with its U10
   crude-desalter pattern. Each is a one-line toggle. U10 is the only new pattern, so dropping `ElectricalSeparator`
   also removes U10.
   **Decided 2026-10-25:** keep `EjectorPump` and `RotaryCompressor`; do not generate `SpiralHeatExchanger` or
   `ElectricalSeparator` (U10 dropped). Both stay in the schema allowlist for import. 23 generated equipment
   classes; T10 has no U10 slot and T13 no desalter.
2. **Main-session borderline keeps:** `Agitator`, `StaticMixer`, `RotaryMixer`, `InLineMixer`, `AirEjector`,
   `Furnace` (no burner, chimney or blower nodes), `AirCoolingSystem`.

## 12. Follow-ups (not decided here)

- Utility stubs naming the partner equipment and drawing (samples §6): a cross-sheet identity hook; it changes
  connector labels, so it needs its own ADR.
- A visible Custom* `typeName` on import: it changes every schema text (F1).
- Widening the allowlist later: the rule takes any class list; the proposed version's placements (ADR-0058
  "Proposed version") are the starting point.

## 13. Declared parameter values (for T8–T10)

Added 2026-10-25, after T3. Base §8.2, base §4.4/§12 and this note (§5.2, §7.2) name knobs but give no value.
This section gives each one a value. It changes no accepted decision. Two findings need the user (§13.8).
It follows the 2026-10-25 decision: 23 generated equipment classes, no `SpiralHeatExchanger` variant in U5, no U10
slot, `p_desalter` unused.

### 13.1 How to read the values

**Grounding tags.**
- **[HC]** a sample hand count (samples note, sheet ID).
- **[C]** an OPEN100 figure computed in the composition note.
- **[B]** derived from an acceptance band; the arithmetic is in §13.7.
- **[R]** a codified rule, or a value already in the base note or this note.
- **[U]** declared, with a one-line reason why the value is a neutral choice.

**Rule V (declared; it generalises §7.2's "primary class dealt twice per deck").**
- An axis that chooses a class or an arrangement deals its **primary** option twice per deck and every alternative
  once.
- An optional item (written `[x]` in base §7.2) is a deck {absent 1, present 1}.
- A size range is uniform over the range the note gives.

No value is a frequency claim (composition note §10). Rule V exists so that no single weight needs its own
justification.

**Draws and decks.**
- Pattern choices per grammar slot are weighted draws from the master stream (base §8.2).
- Variant axes and role classes are **decks** (§5.2, §7.2). There is one deck per key: `"{pattern}.{axis}"` or
  `"role:{role}"` (`VariantDecks` takes any string key). Multiplicities are integers ≥ 1. To switch an option off,
  remove it from the deck.

### 13.2 Flowsheet grammar (T10; `FlowsheetKnobs`)

| Knob | Value | Grounding |
|---|---|---|
| `conditioning_count_weights` (Conditioning{0..2}) | 0 : 1, 1 : 1, 2 : 1 (mean 1) | [U] uniform over the grammar's range; the base note names the range but no knob, and T10 needs one |
| `conditioning_weights` | U5 1 : U7 1 : U8 1 | [U] no source ranks feed-conditioning steps, so equal |
| `core_weights` | `U3+U2` 1 : `U3` 1 : `U6` 2 | [U] U3 vs U6 1 : 1, then U2 on U3's gas outlet as an optional item (1 : 1) |
| `separation_count_weights` (Separation{1..3}) | 1 : 1, 2 : 1, 3 : 1 (mean 2) | [U] uniform over the grammar's range |
| `separation_weights` (U1 \| U6) | U1 1 : U6 1 | [U] equal; base §8.1 names the alternatives, not a weight |
| `units_per_train_min` / `_max` | 3 / 9, **derived, not config fields** | [R] the grammar fixes them: first train 4–9 (FeedFarm + 0–2 + 1–2 + 1–3 + ProductFarm), later trains 3–8. T10 asserts the range; a train cut short by `n_units` is exempt. Separate fields could contradict the count weights |
| `p_side_draw`, `p_shared_farm_feed` | 0.2, 0.2 | [R] base §8.1, already in config |

Consequence, used in §13.7: a later train has **5.25 units** on average. Per train that is U4 1, U5 ⅓, U7 ⅓, U8 ⅓,
U3 ½, U2 ¼, U6 1½ (½ as Core, 1 as Separation) and U1 1.

### 13.3 Pattern variants (`variant_weights`; T9 now, T13/T14 later)

| Deck key | Options : multiplicity | Grounding | Task |
|---|---|---|---|
| `pump_set.group` | `with_suction_vessel` 2 : `own_sheet` 1 | [R] §7.1; FB&D rule vs WTP [HC]; already in config | T9 |
| `U4.tank_count` | 2 : 1, 3 : 1, 4 : 1 | [R] base "2–4", uniform | T9 |
| `U4.transfer_pump` | CentrifugalPump 2 : RotaryPump 1 | Rule V | T9 |
| `U4.metering` | none 4 : MassFlow 1 : PositiveDisplacement 1 : Turbine 1 : VolumeFlow 1 | Rule V: optional 1 : 1, then 4 meter classes equal | T9 |
| `U4.manifold` | GateValve 2 : PlugValve 1 | Rule V (PlugValve is the base's "variant") | T9 |
| `U4.tank_service` | flammable 1 : non_flammable 1 | [U] neutral. Flammable = breather + arrestor (6.19); non-flammable = `VentilationDevice` | T9 |
| `U6.vessel` | PressureVessel 2 : GravitationalSeparator 1 | Rule V | T9 |
| U7 | no axis | — | T9 |
| `U1.vacuum` | none 2 : air_ejector 1 : liquid_ring 1 | Rule V; ejectors on H2 [HC] | T13 |
| `U1.condenser` | TubularHeatExchanger 2 : AirCoolingSystem 1 | Rule V (tubular is primary, §7.2) | T13 |
| `U1.feed_preheater`, `U1.reflux_sight_glass` | absent 1 : present 1 each | Rule V (optional) | T13 |
| `U2.compressor` | Centrifugal 2 : Reciprocating 1 : Rotary 1 | Rule V | T14 |
| `U2.aftercooler` | TubularHeatExchanger 2 : AirCoolingSystem 1 | Rule V | T14 |
| `U2.suction_filter`, `U2.discharge_ko_drum` | absent 1 : present 1 each | Rule V (optional) | T14 |
| `U3.reactor` | plain 2 : agitated 1 | Rule V; agitated reactor on D2 [HC] | T14 |
| `U5.exchanger_count` | 2 : 1, 3 : 1, 4 : 1 | [R] base "2–4", uniform | T13 |
| `U5.trim_heater` | absent 1 : ElectricHeater 1 | Rule V (optional) | T13 |
| `U5.utility` (per exchanger) | steam 1 : cooling_water 1 | [U] neutral; base U5 names both stubs | T13 |
| `U8.mixer` | StaticMixer 2 : RotaryMixer 1 : eductor (`EjectorPump`) 1 | Rule V | T14 |
| `U8.agitated_vessel`, `U8.additive_injection` (plain / `InLineMixer`) | 1 : 1 each | Rule V (optional) | T14 |

Already in config, unchanged: `p_column_combined` 0.3, `p_triple_pump_set` 0.15, `p_single_pump` 0.2,
`condensate_mode_weights` 2 : 1 : 1, `pump_pressure_mode_weights` 3 : 1, `p_split_range` 0.

**Pump-set drawing group (T3's reading confirmed).** §7.1's "variant `own_sheet`, 2 : 1" means
`with_suction_vessel` 2 : `own_sheet` 1. FB&D's rule is the default and WTP's separate pump sheets are the variant,
so each deck cycle of three pump sets has one `own_sheet`. Two rules make the variant well defined (§13.6):
- only spared sets (A/B, A/B/C) are dealt from this deck. A single pump always stays with its suction vessel.
  The 8 WTP pump-sheet titles all name lettered sets [R].
- an `own_sheet` group is never merged back.

### 13.4 Class weights per role (`class_weights`; T7 trims, T8, T9)

| Role | Classes : multiplicity | Grounding |
|---|---|---|
| Block valve (pump, CV station, PSV, exchanger utility, filter) | GateValve 2 : ButterflyValve 1 | Rule V; gate is primary (§7.2); butterfly "large-line blocks" (base §4.2) |
| Compressor suction block | ButterflyValve, fixed | [R] base 6.16 / L16 |
| Vent / drain valve | GateValve 2 : BallValve 1 | Rule V |
| Tank bottom drain | GateValve 2 : AngleBallValve 1; on rotary-pump farms AnglePlugValve, fixed | Rule V; §5.2 U4, §5.4 |
| Control-valve body | GlobeValve 2 : BallValve 1 : ButterflyValve 1 | Rule V; ADR-0044 |
| Letdown control-valve body (drum or separator liquid outlet) | AngleValve 2 : AngleGlobeValve 1 : AngleBallValve 1 | Rule V; base U3 letdown, §5.4 |
| CV-station bypass; on-off valve | GlobeValve; BallValve, both fixed | [R] L9; base 6.9 |
| Pressure-tap root | BallValve 2 : NeedleValve 1 | Rule V; C01 ball-valve root [V] |
| DP-tap root; temperature / analyser tap root | NeedleValve; BlindFlange, both fixed | [R] base §4.2, §4.3 |
| Dosing-line isolation (U8) | GateValve 2 : StraightwayValve 1 | Rule V; §5.2 U8 [L]/[U] |
| Check: pump discharge / minimum flow / compressor discharge | SwingCheckValve / GlobeCheckValve / CheckValve, fixed | [R] L1, L6, L16 |
| Vessel PSV | SpringLoadedGlobeSafetyValve 2 : SpringLoadedAngleGlobeSafetyValve 1 | Rule V |
| PD-pump relief | SpringLoadedAngleGlobeSafetyValve, fixed | [R] 6.5 |
| Flow element, liquid | FlowMeasuringElement 2 : ElectromagneticFlowMeter 1 | Rule V |
| Flow element, gas / steam | FlowMeasuringElement 2 : VenturiTube 1 : FlowNozzle 1 | Rule V; base §4.2 services |
| U8 main / additive meter | ElectromagneticFlowMeter / MassFlowMeasuringElement, fixed | [R] base U8 |
| Sight glass | SightGlass 2 : IlluminatedSightGlass 1 | Rule V |
| Skillet | PipeFlangeSpade 1 : PipeFlangeSpacer 1 | [U] closed and open positions; neither is primary |
| Purge-connection meter (deck over flush connections, §5.4) | plain 2 : `VariableAreaFlowMeter` 1 | Rule V; base §4.2 "rotameter on purge lines" (no other placement exists) |
| U5 exchanger | TubularHeatExchanger 2 : PlateHeatExchanger 1 | Rule V |
| Strainers, pump classes outside the decks above | as base 6.1, 6.2, 7.1 | [R] |

`GeneratorConfigV2.equipment_weights` (T3) now overlaps the equipment decks. T9/T10 should document it as a
multiplier on deck multiplicities, or drop it. That is a coder choice; no value depends on it.

### 13.5 Instrument density (`InstrumentDensity`; T8)

| Knob | Value | Grounding |
|---|---|---|
| `monitor_points_per_major_item` | uniform integer 5–7 (mean 6) | [B] instruments : valves ≈ 1.36, OPEN100's value inside the 1.0–1.8 band (§13.7) |
| major items (constant `MONITORED_MAJOR_CLASSES`) | ProcessColumn, PressureVessel, Gravitational- and ScrubbingSeparator, Tubular- and PlateHeatExchanger, AirCoolingSystem, ElectricHeater, Furnace, the 3 compressors | [U]. Pumps, tanks, filters, mixers, agitators and ejectors are left out because their patterns already give them a fixed instrument set |
| point mounting | a dedicated nozzle on the item (PSGF on `Nozzle`, v1 rule); no root valve | [R] base §4.3 "on equipment". No valve is added, so the ratio arithmetic stays clean |
| `monitor_variable_weights` | T 1 : P 1 | [U] neutral; the samples show T and P bubbles in similar numbers: T 40, P 34, my sums of the [HC] letters over H1, H2, H3, D1, F2 (samples §3.2; F2 lower bounds) |
| `p_monitor_local` | 0.7 (local gauge `TI`/`PI`, one PSGF), else `TT → TI` / `PT → PI` | [B]/[C] OPEN100's leaf share, 242 / 350 = 69 % [C]; keeps degree-1 ≥ 55 % (§13.7) |
| `tray_temperature_points` | 2–4 | [R] base U1 |
| `reactor_temperature_points` | 3–5 | [R] base U3 |
| `p_optional_instrument` (every `[…]` instrument in base §7.2: AT/AI on distillate, FT/FI on header or inlet, LSLL / LSHH alarms, U7 FIC) | 0.5 | [U] an optional item at even odds (Rule V) |
| `p_point_level_switch` (`LSH → LAH`, `LSL → LAL` on tanks, drums, drain pots) | 0.5 | [U] even odds; LSL / LSLL on H2, H3 [HC] show the template, not a rate |
| `p_bearing_temperature` (`TT → TIAH` on pumps and compressors) | 0.5 | [U] even odds; the template exists in base §4.4 |
| `p_indicator_alarm` (alarm letters on an indicator PIF; letters only, no node) | 0.5 | [U] even odds; samples §5 "alarm levels next to an indicator" |
| `p_motor_current` (`IT → II`, U2) | 0.5 | [U] even odds; HW1 IT/II [HC] |
| `p_vfd` (U2 compressor, U8 dosing pumps) | 0.5 | [U] even odds; Valdosta speed set points [Vw] |
| `p_multivariable` (`UC` on the U3 reactor) | 0.5 | [U] even odds; D1 UC ×1 [HC] |
| hand switches per motor | 1 (the HS of §5.1), no new knob | [R] §5.1. `p_motor_hs` stays 0.5 |

Each monitoring point takes its own `SEQ3` number. The worst unit (U1 at k = 7) needs about 100 instrument
numbers, well under the 999 overflow.

### 13.6 Sheet rules T10 needs (clarifications, no new knob)

1. **Own-sheet pump groups** come from spared sets only (§13.3). The merge step never merges them, because
   merging would undo the variant.
2. **Combined column variant** (`p_column_combined` 0.3) is one pattern group. The caps govern *merging* only
   (base §9, step 3); a pattern group is never split. So this sheet may exceed `max_symbols_before_stubs`. If the
   combined group would hold more than 16 equipment items (maximum 4 + 6 pumps + preheater + drain pot +
   5 ejector-stage items = 17), it falls back to G1/G2. That keeps every sheet within 1–16 equipment.
3. **U7 keeps its own unit and its own group** and never joins another unit's group. Base §7.2 lets U7 join the
   downstream unit's first group, but that contradicts "every sheet shows one unit" (ADR-0025, S16). The accepted
   invariant wins.

### 13.7 Arithmetic: expected composition against the bands

These are **expected values from my arithmetic over the trim and pattern tables, not a run.** R1 measures them.
Read them as ±20 %.

**Assumptions.**
- Counting rule of base §12.1; AF and AEF are not counted.
- One later train in the long run; the first train's extra feed farm is ignored.
- Pumps per set: 0.2 × 1 + 0.65 × 2 + 0.15 × 3 = **1.95**.
- Base 6.4 = one casing vent plus one drain per pump. If T7 reads it as one valve, V falls by about 2 per set.
- A CV with its station = 1 + 0.6 × (3 + 0.3) = **2.98 valves**, 0.6 × (0.5 × 2 + 0.3) = 0.78 fittings.
- A vessel PSV = 1 + 0.5 × 2 + 0.3 = **2.3 valves**.

**Worked example: U6, drum and pump set on one sheet, before the monitoring points.**

Drum:

| Item | Instruments | Valves |
|---|---|---|
| PIC → PV (station) | 2 | 2.98 |
| LIC → LV (station) + cascade 0.5 × (FT, FIC) | 2 + 1 | 2.98 |
| LSHH trip → XV, ZSO/ZSC 0.5 × 2 | 2 + 1 | 1 |
| Local PI, TI on top (6.12); LG; TI on the inlet | 4 | — |
| [LSLL] 0.5 × 2; point level 0.5 × 2 | 2 | — |
| PSV | — | 2.3 |
| Vent and drain (KLM) | — | 2 |
| Flush connection | — | 0.3 |
| Battery limit | — | 1 |
| **Drum total** | **14** | **12.56** |

Pump set:
- Per pump, valves: suction block 1, PI root 0.75, check 1, block 1, vent and drain 2, minimum flow 0.6 = 6.35.
- Per pump, instruments: PI 0.75, HS + YI 0.5 × 2, TT + TIAH 0.5 × 2 = 2.75.
- Header-PT mode adds 0.25 V and 0.5 I per set.
- **Set: V = 12.63, I = 5.86.**

Unit total: I₀ = 19.9, V = 25.2, 1 major item. With k = 6 and s = 0.7, I = 19.9 + 6 × 1.3 = 27.7. Symbols on the
sheet ≈ 2.95 E + 25.2 V + 16.4 fittings + 27.7 I + ≈ 4 stubs = **76**.

**All units, same method.**

| Unit | Per train | E | V | I₀ (k = 0) | Major items | Sheets |
|---|---|---|---|---|---|---|
| U4 (3 tanks on average) | 1 | 5.0 | 27 | 31 | 0 | 1.3 |
| U5 | ⅓ | 3.5 | 24 | 17 | 3.5 | 1.0 |
| U7 | ⅓ | 2.0 | 9.5 | 6 | 0 | 1.0 |
| U8 | ⅓ | 4.0 | 22 | 14 | 0.5 | 1.3 |
| U3 | ½ | 7.5 | 46 | 44 | 5 | 2.3 |
| U2 | ¼ | 4.0 | 30 | 24 | 3.5 | 1.0 |
| U6 | 1½ | 3.0 | 25 | 20 | 1 | 1.3 |
| U1 (incl. ½ vacuum variants) | 1 | 10.2 | 62 | 46 | 5.25 | 2.2 |
| **Per train** | 5.25 units | **27.6** | **175.5** | **147.3** | **M = 11.46** | **7.95** |

**Derivation of k [B].** Each monitoring point adds 2 − s nodes. Solving I₀ + k · M · (2 − s) = 1.36 · V:

k = (1.36 × 175.5 − 147.3) / (11.46 × 1.3) = 91.4 / 14.9 = **6.1 → 6**.

With k = 6: I = 147.3 + 89.4 = 236.7, so I : V = **1.35**, I per sheet = **29.8**, V per sheet = **22.1**.

**Degree-1 share [B].**
- In I₀: about 75 of the 147 nodes have degree 1 (local gauges, indicator PIFs, HS, YI, limit switches). Loops and
  trips have degree ≥ 2.
- Each monitoring point adds exactly one degree-1 node, so N = 68.8 points add 68.8.
- Result: (75 + 68.8) / 236.7 = **61 %**. With s = 0.5 it would be ≈ 58 %, which is why s follows OPEN100's 69 %.

**Off-page stubs.**
- Cuts: 6.9 cross-unit streams × 2, plus U1 and U3 internal cuts, plus own-sheet pump sets ≈ 23 per train.
- Open line ends: utility stubs, relief to flare, open gas stubs ≈ 16 per train.

**Symbols per sheet** = (27.6 + 175.5 + 236.7 + ≈ 97 fittings + 39 stubs) / 7.95 ≈ **72**.

| Band (base §12.1, §7.1) | Expected | Verdict |
|---|---|---|
| Symbols per sheet, mean 56–109 | ≈ 72 | meets |
| ≥ 95 % of sheets inside 40–134 symbols | ≈ 76–90 % inside. Below 40: U7 sheets ≈ 25; A/B pump sets on their own sheet ≈ 38 (≈ 1.15 sheets per train); 2-tank farms whose pumps went to their own sheet ≈ 31. Above 134: combined column sheets ≈ 170–190 (0.3 per train) | **at risk → Q8** |
| Valves per sheet, mean 15–28 | ≈ 22 | meets |
| Instruments per sheet, mean 20–38 | ≈ 30 | meets (k derived) |
| Instruments : valves 1.0–1.8 | ≈ 1.35 | meets (k derived) |
| Off-page stubs, mean 5–11 | ≈ 4.9 if open line ends count; ≈ 2.9 for splitter cuts only. Duplication 0.25 adds an unmeasured share | **at risk → Q7** |
| Off-page stubs, every sheet ≤ 21 | maximum ≈ 15 (combined vacuum column) | meets |
| Equipment, every sheet 1–16 | ≤ 16 by rule 13.6.2 | meets by construction |
| Equipment, ≥ 90 % of sheets ≤ 10 | ≈ 99 %; only some combined column sheets exceed 10 (≈ 1 % of sheets) | meets |
| Instruments of degree 1 ≥ 55 % | ≈ 61 % | meets (s chosen) |
| Equipment in A/B(/C) groups 25–45 % | ≈ 40 % (9.3 spared pumps + 1.0 ejectors + 0.67 filters of 27.6) | meets, near the top. Lever: `p_single_pump` |
| Units on ≥ 2 sheets 25–65 % | ≈ 40 % | meets |
| One unit per sheet | 100 % by rule 13.6.3 | meets |
| Class coverage at D1000g2 | ≈ 126 trains. The rarest classes (IlluminatedSightGlass, PipeFlangeSpacer) are expected about 20–30 times | meets; D100g2 reported |

If R1 misses a band that is marked "meets", the levers are, in order: k and s (instrument bands), `p_single_pump`
(spare share), `p_side_draw` / `p_shared_farm_feed` (stubs). Each change is one logged sweep row (base §12.1).

### 13.8 Open questions for the user (each with a recommendation)

**Q7. What counts as an off-page stub in the composition report?**
- *A (recommended):* every pipe line end that leaves the drawing: utility supply and return stubs, relief lines to
  a flare or relief header, open gas stubs, unmatched ports.
  - Not counted: vent and drain ends closed by a blind flange or a funnel, and atmospheric vents.
  - Why: OPEN100's 8.0 is PID2Graph's inlet/outlet label, which marks every continuation arrow. On the real sheets
    every utility consumer has an off-sheet arrow (samples §6). No run has happened, so this is a clarification,
    not a tuning.
  - Expected ≈ 4.9, still at the band's floor. If R1 shows < 5, report the gap: v2 draws no instrument-air or
    header arrows, which real sheets do.
- *B:* splitter connectors only. Expected ≈ 2.9, so the 5–11 band fails by construction.

**Q8. The per-sheet symbol range (≥ 95 % in 40–134) against the accepted variants.**
The accepted, sample-grounded variants (own-sheet pump sets, combined column sheets) plus the one-unit-per-sheet
rule for U7 put an expected 10–24 % of sheets outside 40–134. The real samples do the same: 5 of the 15 inventoried
sheets fall outside 40–134, by my sums of the [HC] counts (equipment + valves + instruments + off-sheet; fittings
not inventoried, so these are lower bounds).
- above: D1 ≥ 153;
- below: D2 ≥ 18, D3 ≥ 8, O1 ≥ 28, WM ≥ 30.

The options:
- *A (recommended):* keep the **mean** band 56–109 as the pass/fail density criterion. Report the per-sheet
  distribution and the share inside 40–134 with no pass mark, as §7.1 already does for signal connectors. This is
  the same kind of recalibration as Q6.
- *B:* keep the band, set `own_sheet` and `p_column_combined` to 0, and fold U7 into its downstream unit (a
  structural change). This loses two variants the samples show and is still borderline (U7 ≈ 5 % of sheets).
- *C:* keep the band and variants, and give own-sheet pump sets WTP's H3 instrument set (header PT + PI,
  PSLL / PSHH pump trips, HS on every pump). This adds a template, lifts A/B pump sheets to ≈ 41, and still
  leaves the combined columns and U7 outside.
