---
topic: What real P&IDs contain — vocabulary, per-sheet composition, multi-sheet structure — and what the synthetic generator should adopt first
date: 2026-10-22
status: draft, researcher agent
question: >
  The generator has 6 equipment classes, 3 valve types, 3 instrument-function classes and random topology.
  What do real P&IDs (and the standards/papers that describe them) contain, with sources, and which additions
  to the generator buy the most realism per unit of effort?
related: [10-literature/pid-structural-rules.md, 10-literature/2411.13929.md, 10-literature/pid2graph.md,
          40-design/realism-units-duplication-reach.md, 30-experiments/2026-09-26-smoke-06-density.md,
          Notes/open100-rendszerkodok.md, ADR-0007, ADR-0017, ADR-0031]
---

# What real P&IDs contain, and what a realistic generator adds first

## 0. How to read this note

**Evidence tags** (every figure carries one):

| Tag | Meaning |
|---|---|
| **[V]** | I opened the source in this session and read the text/table/figure that states it. |
| **[V-S]** | Read through the `WebFetch` tool, which returns a *summary* of the page by a small model, not raw text. The page was fetched in full; numbers were cross-checked for internal consistency or by a second independent fetch. Treat as verified-with-a-caveat. |
| **[C]** | Computed by me today from a local artefact (installed pyDEXPI 1.2.0 by introspection; PID2Graph graphml files on `C:/Users/Otthon/Desktop/Munka/PID2Graph`; DEXPI example XML). Reproducible; scripts are in the session scratchpad, not in the repo. |
| **[P]** | Taken from a project note that verified it in an earlier session; **not** re-opened today. |
| **[U]** | Unverified: recalled, inferred, or an interpretation of mine. Never used as a number. |

**Not found is a result.** Section 10 lists everything I looked for and did not find. Nothing there is padded.

---

## 1. Bottom line

1. **The vocabulary gap is large and cheap to close.** pyDEXPI 1.2.0 (DEXPI 1.3) has **99 non-custom equipment classes** (75 of them leaves), **55 non-custom piping-component classes**, and **31 instrumentation classes**; the generator uses 6 + 3 + 3. [C]
2. **Instrument diversity does not live in classes.** pyDEXPI has no "pressure transmitter" class. An instrument is a `ProcessInstrumentationFunction` / `ProcessSignalGeneratingFunction` whose *kind* is carried by free strings (`processInstrumentationFunctionCategory`, `processInstrumentationFunctions`, `sensorType`). Real instrument diversity therefore has to come from an **ISA-5.1 tag grammar**, not from new classes. [C]
3. **The generator's instrument letters (`FLPT`) equal a teaching-slide minimum**, not real diversity: a Ford, Bacon & Davis course deck (AIChE, 2019) lists exactly function letters A, F, L, P, T and type letters C, E, I, T, V as "ISA typical". [V] Real data uses many more letter codes: the real P&ID-like set of Hirtreiter et al. has a vocabulary of **390** tokens against **113** for their generated data, "mainly a diversity of additional, new letter codes". [V]
4. **Real sheets are item-dense in valves and instruments, not in equipment.** On the 12 real OPEN100 sheets the mean is **21.4 valves, 29.2 instruments, 8.0 off-page connectors** and about **82 symbol nodes** per sheet [C]; the equipment on those systems is of the order of **1 to 9 named items per drawing** [P, incomplete]. Our headline sheet is the opposite. I generated the headline preset (`HeadlinePreset`, 30 units, seed 0, 59 sheets) and counted per sheet: **14.71 equipment, 14.95 valves, 7.78 instrument-function nodes (5.18 of them sensor/indicator bubbles), 5.18 off-page stubs, 42.6 nodes in total.** [C, one seed, one size]
5. **Real instruments hang on lines; they are not inline.** In OPEN100, **242 of 350** instrumentation nodes (69 %) have graph degree 1, 72 degree 2, 36 degree 0. [C]
6. **A practitioner source gives a sheet-composition rule after all**, contrary to `pid-structural-rules.md` S8 ("no source gives an item count"): Ford, Bacon & Davis "Layout Recommendations" — one column per P&ID, one fired heater, one complex compressor, 1 to 2 tanks or feed/storage vessels, pumps drawn with their suction vessel. [V] It is slides, not a standard.
7. **Standards sizes:** ISO 10628-2 has **198 equipment symbols in 20 categories, 60 piping symbols in 5 categories**, and (one read) 52 instrumentation symbols in 3 categories; PIP PIC001 has 48 / 63 / 92 (+6 other); ANSI/ISA-5.1 has **176 instrumentation symbols in 11 categories**. [V-S] The largest published symbol vocabulary I found on real digitized P&IDs is **76 labels (25 equipment, 33 piping, 18 instrumentation)**. [V-S]
8. **No published per-class frequency table exists for real P&IDs** (valve types, instrument types, equipment types). Section 10. Per-class weights in the generator must therefore be declared design parameters and swept, not sourced.
9. **Real multi-sheet structure observed in OPEN100:** 4 of 9 observed drawing numbers span two sheets; 96 connectors on 12 sheets; real identity oddities (symbol vs schedule spelling, system-code synonyms). [P] Utilities: codified rules put headers on separate utility P&IDs and leave consumers on the unit sheet with a service-labelled stub. [P]
10. **Do first:** (a) ISA-5.1 tag grammar with ~10 variable letters and ~15 function combinations plus line-attached local instruments; (b) valve/fitting vocabulary 3 → ~30 piping classes with standard trims; (c) equipment 6 → ~25 classes, A/B spares; (d) re-centre sheets on a major item with 3 to 10 equipment, valve and instrument density at the OPEN100 level. Ranking and reasoning in section 8.

---

## 2. The DEXPI / pyDEXPI class vocabulary (introspected, [C])

**Method.** `uv` environment of the repo, `pydexpi==1.2.0` ("Supports DEXPI version 1.3", package METADATA line 40). Counted with `inspect` over `pydexpi.dexpi_classes.pydantic_classes` (514 classes, 49 of them enumerations). "Leaf" = no subclass in the package. "Custom*" = the `Custom…` escape-hatch subclasses (not real vocabulary). Counts are of *classes in the Python model*, which is what the generator can instantiate; they are not a count of ISO 15926 RDL entries (no published total found, section 10).

### 2.1 Equipment (`TaggedPlantItem → Equipment`)

| Quantity | Count |
|---|---|
| Descendants of `Equipment` | **124** |
| of which Custom* | 25 |
| non-custom | **99** |
| of which leaves (most specific) | **75** (100 leaves − 25 Custom) |
| of which inner / generic parents (also instantiable, e.g. `Pump`, `Compressor`, `Vessel`, `HeatExchanger`) | 24 |

The 24 inner parents are: Agglomerator, Blower, Centrifuge, Compressor, CoolingTower, Dryer, ElectricGenerator, Extruder, Fan, Filter, HeatExchanger, Heater, Mill, Mixer, MobileTransportSystem, Motor, Pump, Separator, Sieve, StationaryTransportSystem, Turbine, Vessel, WasteGasEmitter, Weigher.

Named leaves by family (the families a process plant actually draws are bold):

| Family | Named leaves | Count |
|---|---|---|
| **Pump** | CentrifugalPump, ReciprocatingPump, RotaryPump, EjectorPump | 4 |
| **Compressor** | CentrifugalCompressor, ReciprocatingCompressor, RotaryCompressor, AxialCompressor, AirEjector | 5 |
| **Blower / fan** | CentrifugalBlower, AxialBlower, RadialFan, AxialFan | 4 |
| **Vessel** | Tank, PressureVessel, Silo | 3 |
| **Column** | ProcessColumn (sub-items: ColumnSection, ColumnPackingsArrangement, ColumnTraysArrangement) | 1 |
| **Heat exchange** | TubularHeatExchanger, PlateHeatExchanger, SpiralHeatExchanger, AirCoolingSystem, ElectricHeater, ThinFilmEvaporator | 6 |
| **Fired / steam** | Furnace, Boiler, SteamGenerator, Burner | 4 |
| **Separator** | GravitationalSeparator, MechanicalSeparator, ScrubbingSeparator, ElectricalSeparator | 4 |
| **Filter** | LiquidFilter, GasFilter | 2 |
| Centrifuge | SedimentalCentrifuge, FilteringCentrifuge | 2 |
| **Mixer / agitator** | StaticMixer, RotaryMixer, Kneader, Agitator | 4 |
| **Driver** | AlternatingCurrentMotor, DirectCurrentMotor, CombustionEngine, SteamTurbine, GasTurbine | 5 |
| Generator | AlternatingCurrentGenerator, DirectCurrentGenerator | 2 |
| **Cooling tower** | WetCoolingTower, DryCoolingTower, SprayCooler | 3 |
| **Flare / stack** | Flare, Chimney | 2 |
| Dryer | ConvectionDryer, HeatedSurfaceDryer | 2 |
| Solids handling | Conveyor, Feeder, Crusher, Grinder, Lift, PackagingSystem, StationarySieve, RevolvingSieve, VibratingSieve, BatchWeigher, ContinuousWeigher | 11 |
| Size reduction / forming | ReciprocatingExtruder, RotatingExtruder, 3 Agglomerator subtypes | 5 |
| Transport | Truck, RailWaggon, Ship, ForkliftTruck, TransportableContainer, LoadingUnloadingSystem | 6 |
| (total) | the 19 families above account for all 75 named leaves | 75 |

Equipment is a `NozzleOwner` and a `ChamberOwner`: nozzles (`Nozzle`: `subTagName`, nominal pressure fields) and chambers (e.g. shell/tube side) are first-class sub-items. `equipment.py` exports 159 names; 125 are `Equipment` or subclasses, the remainder are sub-components (Impeller, TubeBundle, ColumnSection, GearBox, Screw, …). [C]

**The 6 classes in use** are `CentrifugalPump`, `Compressor` (generic parent), `Tank`, `PressureVessel`, `ProcessColumn`, `HeatExchanger` (generic parent) — 6 of 99. [P: `graph/schema.py` read today]

### 2.2 Piping components (`PipingComponent`)

| Group | Named classes | Count |
|---|---|---|
| **Operated valves** (`OperatedValve`) | GateValve, GlobeValve, BallValve, ButterflyValve, NeedleValve, PlugValve, AngleValve, AngleBallValve, AngleGlobeValve, AnglePlugValve, StraightwayValve (+ generic `OperatedValve` used for control valves, + CustomOperatedValve) | 11 |
| **Check valves** | CheckValve, SwingCheckValve, GlobeCheckValve (+ CustomCheckValve) | 3 |
| **Safety devices** (`SafetyValveOrFitting`) | SpringLoadedGlobeSafetyValve, SpringLoadedAngleGlobeSafetyValve, RuptureDisc, BreatherValve, FlameArrestor | 5 |
| **Inline primary elements** (`InlinePrimaryElement`) — **flow only** | FlowMeasuringElement, FlowNozzle, VenturiTube, ElectromagneticFlowMeter, TurbineFlowMeter, VariableAreaFlowMeter, PositiveDisplacementFlowMeter, MassFlowMeasuringElement, VolumeFlowMeasuringElement | 9 |
| **Fittings** (`PipeFitting`) | PipeTee, PipeReducer, Flange, BlindFlange, FlangedConnection, LineBlind, PipeFlangeSpade, PipeFlangeSpacer, PipeCoupling, ClampedFlangeCoupling, Compensator, Hose, Strainer, ConicalStrainer, RestrictionOrifice, SteamTrap, SightGlass, IlluminatedSightGlass, Silencer, Funnel, InLineMixer, Penetration, VentilationDevice | 23 |

Totals: `PipingComponent` has 61 descendants; 6 Custom*; **55 non-custom, of which 50 specific + 5 generic parents** (OperatedValve, CheckValve, SafetyValveOrFitting, InlinePrimaryElement, PipeFitting). [C]

Other piping-network classes (not components): `PipingNetworkSystem` (line number, fluid code, piping class code, nominal diameter, insulation, heat tracing), `PipingNetworkSegment`, `Pipe`, `PipingNode`, `PropertyBreak` (spec/insulation/class breaks), `DirectPipingConnection`, `FlowInPipeOffPageConnector` / `FlowOutPipeOffPageConnector` plus three reference classes. The segment/system classes carry the line-level attributes a real line list has (`pipingClassCode`, `nominalDiameter*`, `fluidCode`, `insulationType`, `heatTracingType`, `operatingTemperature`, `slope`, `siphon`, `onHold`). [C]

**Note: no inline temperature or pressure elements exist as classes** (thermowell, orifice plate for DP etc.). pyDEXPI covers them only as `SensingLocation` + `ProcessSignalGeneratingFunction`. [C]

**In use today:** `GlobeValve`, `BallValve`, `CheckValve` = 3 of 55.

### 2.3 Instrumentation

`instrumentation.py` exports 34 names, 3 Custom → **31**. They are:

| Role | Classes |
|---|---|
| Instrument function (the "bubble") | ProcessInstrumentationFunction (+ subclass ProcessControlFunction), ProcessSignalGeneratingFunction, ActuatingFunction, ActuatingElectricalFunction, InstrumentationLoopFunction |
| Signal links | SignalConveyingFunction (+ MeasuringLineFunction, SignalLineFunction), SignalConveyingFunctionSource/Target, FlowIn/OutSignalOffPageConnector and three signal-connector reference classes |
| Hardware under a function | ProcessSignalGeneratingSystem (+ **FlowDetector**, the only detector subclass), ActuatingSystem, ActuatingElectricalSystem, ControlledActuator, Positioner, Transmitter, ElectronicFrequencyConverter, PrimaryElement (+ InlinePrimaryElementReference, OfflinePrimaryElement), OperatedValveReference |

`ProcessInstrumentationFunction` fields that carry the ISA identity: `processInstrumentationFunctionCategory`, `processInstrumentationFunctions`, `processInstrumentationFunctionModifier`, `processInstrumentationFunctionNumber` (all `str | None`), plus `location`, `safetyRelevanceClass`, `panelIdentificationCode`. `ProcessSignalGeneratingFunction.sensorType` is also a free string. [C]

**In use today:** ProcessSignalGeneratingFunction, ProcessInstrumentationFunction, ActuatingFunction (3 of 31) with variable letters `F, L, P, T` (`generator.py`: `self.rng.choice("FLPT")`). [P]

### 2.4 Plant structure and off-page

`Enterprise`, `Site`, `IndustrialComplex`, `ProcessPlant`, `PlantArea`, `PlantSection`, `PlantSystem`, `PlantTrain` (+ parent/located-structure helper classes); 17 names in `plantStructure.py`. Equipment, piping systems and instrument functions carry `plantSystem`, `plantTrain`, `plantArea`. [C] The generator uses `ProcessPlant`/`PlantSection` only (unit = `PlantSection`).

### 2.5 Real DEXPI examples are tiny (context, not evidence of plant composition)

Counted from the public DEXPI TrainingTestCases (CC BY 4.0), [C]:

| File | Equipment elements | Piping components | Segments / systems | Instrument functions / loops | Off-page |
|---|---|---|---|---|---|
| C01 DEXPI Reference P&ID (1.3, V04) | 21 (incl. sub-items) | 27 | 23 / 11 | 6 PIF, 3 PSGF, 3 AF / 4 loops | 4 pipe |
| C02 Process Column (BASF) (1.3) | 8 (ColumnSection 2, ColumnPackingsArrangement 2, ProcessColumn 1, Chamber 1) | 13 (BlindFlange 4, OperatedValve 3, PipeReducer 1, PipeTee 1) | 9 / 4 | 4 PIF, 2 PSGF | 2 |
| C03 Piping (Equinor) (1.3) | 0 | 16 (Flange 3, PipeFitting 1, BlindFlange 1, OperatedValve 1, RestrictionOrifice 1, BallValve 1, PipeReducer 1, …) | 5 / 3 | 2 PIF, 1 AF | 2 |

C01 class mix by `ComponentClass`: BallValve 5, PipeTee 5, GlobeValve 3, BlindFlange 2, ButterflyValve, SwingCheckValve, PipeReducer, SpringLoadedGlobeSafetyValve 1 each; equipment PlateHeatExchanger, TubularHeatExchanger, CentrifugalPump, ReciprocatingPump, Tank 1 each. These are **training demonstrators**, built to exercise the data model; they say which classes the *standard authors* consider typical, not how often they occur.

---

## 3. Symbol-set sizes in the standards

Source: Kim, Kim, Moon, Lee, Mun, "End-to-end digitization of image format piping and instrumentation diagrams at an industrially applicable level", *J. Comput. Des. Eng.* 9(4):1298–1326 (2022), DOI 10.1093/jcde/qwac056, section 2.3. [V-S: two independent fetches agree on all numbers except the ISO 10628-2 instrumentation figure, which one fetch truncated.]

| Standard | Equipment | Piping | Instrumentation | Other |
|---|---|---|---|---|
| **ISO 10628-2** | 20 categories, **198** items | 5 categories, **60** items | 3 categories, 52 items (single read) | — |
| **PIP PIC001** | 7 categories, **48** items | 6 categories, **63** items | 7 categories, **92** items | 6 items |
| **ANSI/ISA-5.1** | — | — | 11 categories, **176** items | — |
| ISO 15519-2 | 1 category, 6 items | 2 categories, 41 items | 3 categories, 52 items | — |

- DEXPI, ISO 15926 and XMpLant are described in the same section **without** class counts. [V-S]
- **ISO 15926-4 RDL total class count: not found** (section 10). The PCA Part 4 Edition 4 browser groups content into 29 subject areas and one class-count table shows e.g. 251 `ClassOfAbstractObject`; these are per-entity-type figures, snapshot date unknown. [U: from a search snippet, not opened]
- **Reading:** the *symbol* vocabulary of ISO 10628-2 (198 equipment symbols) is of the same order as pyDEXPI's 99 non-custom equipment classes (a symbol is a drawing, a class is a type; many symbols are variants). The generator's 6 is 6 % of pyDEXPI's 99 and 3 % of ISO's 198.

---

## 4. ISA-5.1 instrument identification

### 4.1 The grammar [V: Wikipedia raw wikitext, "Piping and instrumentation diagram", secondary to ANSI/ISA-5.1; the ISA standard text itself was not read]

Up to five letters: (1) **measured variable**, (2) modifier, (3) readout/passive function, (4) output/active function, (5) function modifier; then a loop number unique to the loop. Example from the source: `FIC045` = Flow Indicating Controller in loop 045; `FT045` = flow transmitter in the same loop. Alphabet of the table:

| Letter | Column 1 (measured variable) | Letter | Column 1 |
|---|---|---|---|
| A | Analysis | N | User's choice (usually torque) |
| B | Burner, combustion | O | User's choice |
| C | User's choice (usually conductivity) | P | Pressure |
| D | User's choice (usually density) | Q | Quantity |
| E | Voltage | R | Radiation |
| F | Flow rate | S | Speed, frequency |
| G | User's choice (usually gauging) | T | Temperature |
| H | Hand | U | Multivariable |
| I | Current | V | Vibration, mechanical analysis |
| J | Power | W | Weight, force |
| K | Time, time schedule | X | User's choice (usually on-off valve as XV) |
| L | Level | Y | Event, state, presence |
| M | User's choice | Z | Position, dimension |

Modifiers (column 2): D difference, F ratio, G gas, J scan, K time rate of change, Q totalize, S safety, X x-axis, Y y-axis, Z z-axis or Safety Instrumented System. Readout/passive (column 3): A alarm, E sensor, G glass/gauge/viewing, I indicate, L light, O orifice, P point/test connection, R record, W well or probe, Q totalize, U multifunction, X accessory. Output/active (column 4): C control, K control station, S switch, T transmit, V valve or damper, Y auxiliary devices, Z actuator/driver/final control element. Function modifiers (column 5): C close, H high, L low, M middle, O open, R run, S stop, D deviation. [V, same source]

### 4.2 Typical families

The standard's tables define combinations; the *commonness* of any combination is **not** in a source I could open. What I can ground:

| Combination | Where it is attested | Tag |
|---|---|---|
| FIC, FT (same loop 045) | Wikipedia ISA-5.1 text | [V] |
| XV (on-off valve) | Wikipedia table, letter X | [V] |
| FE / FT-10xx | OPEN100 sheet 5: six "pump"-labelled graphml nodes are flow-element instrument bubbles with tags `FE`/`FT-10xx` | [P] |
| PI, LIC (`PI P0020`, `LIC L0012`) | Covestro C08 two-sheet example title-block text | [P] |
| TC, LC, FC, FT, FFC, PC | The control structures in Hirtreiter et al.'s SFILES 2.0 examples (arXiv 2211.05583) | [V] |
| Function A, F, L, P, T × type C, E, I, T, V | "ISA Typical" slide, Ford, Bacon & Davis, AIChE 2019, slides 24–25 | [V] |
| PT, PI, PIC, PDT, PDI, PSH, PSL, PSV, PCV, TT, TE, TI, TIC, TW, TSH, LT, LI, LG, LIC, LSH, LSL, LAH, LAL, AT, AIT, HV, ZSO, ZSC | letters are all defined in the table above; **that these are the common combinations is [U]** (recalled practice) | [U] |

**Family list (for the generator, [U] for commonness, [V] for letter validity):** transmitter (xT), element/sensor (xE), local indicator (xI), indicating controller (xIC), controller (xC), switch (xS + H/L), alarm (xA + H/L), gauge glass (LG), thermowell (TW), control valve (xV, same loop number — already ADR-0044), on-off valve (XV), hand valve (HV), position switch (ZSO/ZSC), analyser (AT/AIT). Measured variables with first-class presence on process P&IDs: **F, L, P, T, A** (slide-minimum, [V]) plus **S, W, Z, Q, V** ([U] for commonness).

### 4.3 What DEXPI does with it

DEXPI has the same five slots as strings on `ProcessInstrumentationFunction` (section 2.3). Nothing validates them. The generator can therefore use any ISA combination without a pyDEXPI change. [C]

---

## 5. Published statistics from papers that digitized real P&IDs

### 5.1 Table: every paper I could open, what it reports

| Paper (ID, authors, date) | Real data | Classes | Per-sheet numbers | Tag |
|---|---|---|---|---|
| **Rahul, Paliwal, Sharma, Vig**, "Automatic Information Extraction from P&IDs", arXiv 1901.11383, 28 Jan 2019 | "4 number of sheets consisting of 672 flow diagrams" (as written), oil firm | **10 symbol classes** + "Others": ball valve, check valve, chemical seal, circle valve, concentric (reducer), flood connection, gate valve nc, globe valve, globe valve nc, insulation | Text reports test instances "79 ball valve", "68 globe valve", "57 globe valve nc"; Table 1: **32 inlets, 21 outlets** detected (100 % each); 71 pipeline codes; no per-sheet totals; sheet size not stated | [V] |
| **Paliwal, Jain, Sharma, Vig**, "Digitize-PID", arXiv 2109.03794, 8 Sep 2021 | **12 real sheets**, private, "very high resolution image with hundreds of visual and textual components" each | Dataset-P&ID (synthetic): **32 symbols**, 500 sheets, 4:1 split; symbols 1–25 "complex", 26–32 basic shapes | no counts per class or per sheet reported; line detection 90 774 / 91 416 complete lines and 20 620 / 24 848 dashed lines on the synthetic test split | [V] |
| **Stürmer, Graumann, Koch**, "From Engineering Diagrams to Graphs", arXiv 2411.13929, Table A3 | **60 real P&IDs** (train, "various plants"); **12 OPEN100** (test) | 7 node classes (general, pump/compressor, arrow, tank/vessel, instrumentation, inlet/outlet, valve) + crossing/ankle/border; 2 edge classes | nodes per plan: Real World **497 ± 338**, OPEN100 **382 ± 125**, Dataset-P&ID 452 ± 86, Synthetic 131 ± 14; edges per plan: Real World 457 ± 338, OPEN100 381 ± 126. "Real-world P&IDs … higher mean numbers of nodes and edges per plan, as well as greater variance." The `general` class "overwhelmingly dominates" in every dataset **except OPEN100** | [V] (read from the rendered table) |
| **Kim, Kim, Moon, Lee, Mun**, JCDE 9(4) 2022 | **83 image P&IDs**: 65 train, 8 verification, 9 test; 82 digital P&IDs behind the labels | **76 symbol labels: 25 equipment, 33 piping, 18 instrumentation**; 59 text labels; 12 line labels (8 line-sign + 4 flow-arrow); "one of seven line types" | five test P&IDs, symbols / texts / lines: **154/216/222, 82/235/122, 78/227/141, 62/201/112, 86/325/124**. Means (my arithmetic): **92.4 symbols, 240.8 texts, 144.2 lines** per P&ID. Largest label counts (before augmentation): equipment 183, piping 1 046, instrumentation 1 074 instances for the most frequent label of each category | [V-S] |
| **Lopomo et al.**, "Leveraging LLMs and Object Detection for Automated KG Generation from Industrial Schematics", *Big Data Cogn. Comput.* 10(7):210, 29 Jun 2026 | **126 P&IDs** from "plant manuals, real plant designs and diagrams generated by industrial CAD software" (chemical, power, water treatment, distribution) | **24 main semantic classes**, **5 400 annotated symbols** | **"an average of about 43 annotated components per diagram, while some diagrams contain more than 80"**; 70/20/10 split | [V] |
| **Mani, Haddad, Constantini, Douhard, Li, Poirier** (C3.ai), CVPRW 2020 | 18 training + 11 test P&IDs | only 2 symbol classes (tag, locally mounted instrument) + non-symbol | none; but states that diagram-to-diagram links are "reserved symbols" (arrow boxes) whose "connected P&ID diagram names (DWG Number) are very structured" and can be linked with regular expressions | [V] |
| **Hirtreiter, Schulze Balhorn, Schweidtmann**, arXiv 2211.05583 (preprint 26 Oct 2022) | **312** flowsheet images "including control structures", public sources (gas and oil plants, experimental setups, batch operations) | SFILES 2.0 vocabulary: real **390** vs generated **113** tokens | std of node count real **28** vs generated **20**; real mean smaller than generated (Table 1 text extraction is garbled; the prose is clear) | [V] |
| **Prasad & Mahapatra**, SynthPID, arXiv 2604.16513v1, 15 Apr 2026 | OPEN100 only | 7 node classes, 2 edge classes | OPEN100 after collapsing connectors: "between 57 and 210 physical components and 28 to 118 edges"; connectors+crossings "account for 50-65% of all annotated nodes"; real P&IDs "heavy-tailed degree distribution" (asserted; shown as histograms over the same 12 sheets) | [V-S] |
| **Yu, Cha, Lee, Kim, Mun**, *Energies* 12(23):4425 (2019) | two test P&IDs | class list not reachable (403) | — | [U] not read |
| **da Cunha et al.**, "On P&ID Symbol Recognition using Transformers" (SBC ERAMIA/RS) | OPEN100 12 + "IPD" 2 internal sheets | synthetic training: **40 symbol classes**, 700 sheets + 300 grids | none | [V] |

### 5.2 PID2Graph OPEN100, per class and per sheet ([C], computed from the 12 graphml files)

Coverage: 12 real sheets of one plant (OPEN 100, same author and date). Labels are PID2Graph's coarse 7 + helper labels; **no tags, no text** (project note). Nodes per sheet: mean 385.8, sd 125.4, min 181, max 675 (paper: 382 ± 125 — consistent).

| Label | Total | Mean / sheet | Share of all nodes |
|---|---|---|---|
| connector (line junction/ankle) | 2 408 | 200.7 | 52.0 % |
| crossing | 734 | 61.2 | 15.9 % |
| arrow | 451 | 37.6 | 9.7 % |
| **instrumentation** | **350** | **29.2** | 7.6 % |
| **valve** | **257** | **21.4** | 5.6 % |
| general (equipment, fittings, misc. lumped) | 234 | 19.5 | 5.1 % |
| inlet/outlet (off-page) | 96 | 8.0 | 2.1 % |
| background | 48 | 4.0 | 1.0 % |
| tank | 35 | 2.9 | 0.8 % |
| pump | 16 | 1.3 | 0.3 % — **unreliable**: all six `pump` nodes on sheet 5 are flow-element instrument bubbles [P] |

- "Symbol" nodes (instrumentation + valve + general + tank + pump + inlet/outlet): **988 in total, mean 82.3 per sheet, sd 26.3, min 40, max 134.** Per-sheet table:

| Sheet | nodes | edges | valve | instr. | general | tank | pump | in/out | arrow | symbols |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 437 | 433 | 35 | 36 | 20 | 2 | 0 | 9 | 35 | 102 |
| 1 | 320 | 308 | 9 | 9 | 14 | 0 | 3 | 6 | 59 | 41 |
| 2 | 485 | 490 | 26 | 22 | 36 | 7 | 0 | 10 | 43 | 101 |
| 3 | 280 | 279 | 15 | 31 | 20 | 2 | 2 | 3 | 15 | 73 |
| 4 | 385 | 381 | 33 | 30 | 24 | 2 | 0 | 8 | 24 | 97 |
| 5 | 405 | 401 | 21 | 32 | 12 | 3 | 6 | 12 | 38 | 86 |
| 6 | 470 | 468 | 9 | 49 | 21 | 2 | 0 | 10 | 45 | 91 |
| 7 | 351 | 340 | 19 | 27 | 10 | 2 | 5 | 8 | 39 | 71 |
| 8 | 181 | 179 | 11 | 14 | 4 | 0 | 0 | 11 | 17 | 40 |
| 9 | 226 | 215 | 14 | 20 | 14 | 6 | 0 | 2 | 25 | 56 |
| 10 | 675 | 664 | 33 | 39 | 45 | 7 | 0 | 10 | 76 | 134 |
| 11 | 414 | 409 | 32 | 41 | 14 | 2 | 0 | 7 | 35 | 96 |

  Cross-check against the paper: Table A3 gives 2 173 "symbols, crossings & ankles" for OPEN100 = 988 symbols + 734 crossings + 451 arrows (my sum), i.e. the paper counts arrows as symbols. [C, consistent]

- **Instrument : valve ratio = 350 : 257 = 1.36.** Per-sheet instrument counts range 9–49, valve counts 9–35.
- **Degree distributions** (undirected graph; node degree = number of attached lines):
  - instrumentation (n = 350): degree 0: 36, degree 1: **242**, degree 2: 72 → instruments are **leaf attachments** to a line (69 %), rarely inline.
  - valve (n = 257): degree 1: 16, **2: 137 (53 %)**, 3: 67, 4: 36, 5: 1 → about half inline, the rest sit on junctions (annotation convention, [U] interpretation).
  - tank (n = 35): degree 0: 5, 2: 9, 4: 9, 5: 1, 6: 1, 8: 1, 9: 1, 10: 2 → **mean degree 2.9, tail to 10**: vessels are multi-nozzle hubs.
  - inlet/outlet (n = 96): degree 1 in 95 cases.
- Same computation on the two synthetic subsets (for contrast): `Dataset PID` (Paliwal synthetic, 500 sheets): 455.5 nodes/sheet, valve 56.5, instrumentation 24.0, general 35.2, no tank/pump nodes; `PID2Graph Synthetic` (250 sheets): 131.2 nodes/sheet, valve **2.5**, tank 2.7, pump 1.7. A synthetic set is very unlike the real one in its valve share (12.4 % and 1.9 % vs 5.6 %).

### 5.3 What the digitization literature does *not* give

No paper above reports (a) per-class frequencies on real P&IDs, (b) valves per line, (c) instruments per equipment, (d) lines (line numbers) per sheet. Kim 2022's "lines" are line *objects*, not line numbers. Digitize-PID and Rahul report class lists but no frequencies. This is the main reason per-class weights below are parameters.

---

## 6. Typical structure of real multi-sheet sets

### 6.1 What one sheet contains (composition)

| Source | Finding | Tag |
|---|---|---|
| **Ford, Bacon & Davis, "Art of the P&ID", AIChE community event, slides 63–65** (PDF created 18 Nov 2019; slide 64 "Layout Recommendations") | "Equipment: number of items on one P&ID": **Columns 1; Compressors 1 (complex); Fired heaters 1; Packaging equipment: complete system if possible; Pressure vessels: feed 1 to 2, reflux 1 (include with condenser), storage 1 to 2; Pumps: include with related equipment (suction); Tanks 1 to 2.** Slide 63 objectives: "Assign which equipment goes on each drawing; minimize drawing density; leave room for other disciplines to add their symbology and tags". Slide 65 "Column Systems (Combined)" shows a column, its reboiler and its overhead condenser (the three equipment titles are legible at the top of the sheet) with further ancillaries on **one** sheet; I did not count the remaining items from the 70 dpi render. | [V] (slides, read as images) |
| OPEN100, equipment listed per drawing in `Notes/open100-rendszerkodok.md` | RCS 6 (2 sheets), CVCS 9, RHRS 4 (2 sheets), MSS 2, ACC 4, CND 9, FWS 3, ESS 1, ACW 5 (2 sheets) = 43 items over 9 drawings; "what we saw", completeness not claimed | [P], incomplete |
| OPEN100 symbol nodes | 82.3 per sheet (section 5.2) | [C] |
| Lopomo et al. 2026 | ~43 annotated components per diagram, some > 80 (mixed, includes CAD-generated simple diagrams) | [V] |
| Kim 2022 test sheets | 62–154 symbols, 112–222 line objects, 201–325 text items | [V-S] |
| Hirtreiter 2022 | node mean ~37 (real flowsheets, unit-operation + control-structure nodes, not symbols), sd 28 | [V] |

**Reading.** A real sheet is built around **one to two major items** (column, vessel, heat exchanger train) with their ancillaries, and carries **dozens of valves and instruments**. Symbol counts per sheet across four independent sources lie between ~40 and ~150, centred near 80–90. The unit of drawing is a **system**, not a count of equipment. [synthesis]

**Our generator on the same axes** ([C]: I ran `build_synthetic_corpus` with `HeadlinePreset().generator_config(n_units=30, seed=0)` and the matching split config, 59 sheets; one seed, one size, so read as indicative):

| Per sheet | Generated (mean, sd, min–max) | OPEN100 (mean, min–max) | Ratio real / generated |
|---|---|---|---|
| Equipment | 14.71 (sd 2.74, 9–20) | ~3.6 listed per sheet (43 items / 12 sheets; 1–9 per drawing) [P], incomplete | generated ≈ 4× denser |
| Valves | 14.95 (sd 5.17, 4–28) | 21.4 (9–35) | 1.4× |
| Instrument-function nodes | 7.78 (sd 4.44, 0–18); bubbles (PSGF + PIF) 5.18 | 29.2 (9–49) | 3.8× (5.6× on bubbles) |
| Instrument : valve | 0.52 (bubbles 0.35) | 1.36 | 2.6× |
| Off-page stubs | 5.18 | 8.0 (2–12) | 1.5× |
| All nodes incl. stubs | 42.6 | symbol nodes 82.3 (40–134), incl. 8.0 inlet/outlet | 1.9× |

Generator design behind the numbers: valves 0–2 per stream chosen uniformly from 3 classes, one control loop (3 nodes) on one operated valve per equipment with p = 0.5, variable letter chosen from `FLPT`. The earlier SMOKE-06 note ("9.08 stubs/sheet vs OPEN100 8.0, a good match") was measured on the pre-duplication, small-unit setup; with the headline preset the stub density is lower (also 5.80 in the realism design note for duplication 0.25 at H1000 [P]). OPEN100's equipment count is incomplete and it is one nuclear plant (one design, one drafter), so the **direction** of every gap is robust and the **size** is not.

### 6.2 How sheets relate (cross-sheet)

| Fact | Source | Tag |
|---|---|---|
| 12 OPEN100 sheets carry **96 off-page connectors** (mean 8.0); stage-2 annotation (read by a model from crops, **not** human-verified): 23 pairs (46 connector ends) resolve inside the 12-sheet subset, 42 dangle to drawings outside it, 8 unresolved | `open100-annotation.md` lines 97–127 | [P], model-read |
| **4 of the 9 observed drawing numbers span two sheets** (PID 100, 120, 170, 210; PID 170 sheet 2 is absent); the rest are 1-of-1 | `pid2graph.md` table | [P] |
| The 12 sheets reference **19 distinct drawing numbers** (100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 240, 250, 260, 270, 290, 300, 320); only 9 are present | `open100-rendszerkodok.md` | [P] |
| **Equipment spanning sheets**: `RCS-PU-102A/B` on sheet 5 and again as DETAIL A/B on sheet 6, with `DET A SHT 2` callouts; "at most 5" such identity items in the 12 sheets | `open100-annotation.md` item 1 | [P] |
| **Tag variants**: *within* a sheet, the pump symbol reads `RCS-PU-102A` while the schedule lists `RC-P102A`; a third style `COOLANT HT EXCH RC-P100-X001` on sheet 6. **Not observed:** the same tag spelled differently on two *different* sheets. | `open100-annotation.md` lines 85–90 | [P] |
| **System-code synonyms**: ES/ESS, CND/COND, RHR/RHRS, WSS/WWS/WS name one system each; one drawing number (320) referenced as both "RWS / RAD WASTE SYSTEM" and "CAS / CHEMICAL ADDITION SYSTEM" | `open100-rendszerkodok.md` | [P] |
| **Equipment in lettered parallel groups**: A/B pairs (102A/B, 112A/B, 114A/B, 121A/B, 120A/B, 170A/B) and an A/B/C triple (211A/B/C) cover 15 of the 43 items listed (35 %), plus sequential same-service series (PU-151..153, PU-162..164) | `open100-rendszerkodok.md`, my count | [P]+arithmetic |
| OPEN100 tag grammar: `SYS-TYPE-NNN[A]` (`CND-TK-165`, `CVCS-HX-110`, `ACW-PU-211A`); type codes seen: XR, SG, PU, V, VE, HX, FL, ION, VCT, XSS, AC, TK, HTR, FLT, AXC; line numbers `SIZE-SYS-NNNNNN-SPEC-HC-X` | `open100-rendszerkodok.md`, `pid2graph.md` | [P] |
| Covestro C08 (chemical, SmartPlant, 2020): drawing UER-1234567 carries **15** off-page labels naming UER-2345678; UER-2345678 carries **2** naming back; labels are German service text + partner-unit-prefixed code + 3-digit number + partner drawing number. Cross-unit line numbers carry the partner unit prefix. | `pid-structural-rules.md` S5, P7 | [P] |
| Rahul et al.: 32 inlets and 21 outlets detected over the 4 sheets (≈ 13 per sheet if "4 sheets" is read literally) | arXiv 1901.11383 Table 1 | [V] |
| Mani et al.: inlet/outlet "arrow box" symbols carry structured drawing numbers | CVPRW 2020 | [V] |
| ISO 10628-1: continuation lines mutually referenced; same-level recommendation | `pid-structural-rules.md` S1 | [P] |

### 6.3 Utility vs process sheets

Codified rules, all [P] (read in the 2026-09-12 sweep; HNF-64103 §3.2.5.2, KLM p. 6/11/12, ISO 10628-1 4.3.1, Toghraei preface):

- **Main utility headers are not shown on the unit P&ID**; they are drawn on the utility P&ID for that process area. Consumers stay on the unit sheet with a stub that carries a service abbreviation (CWS, CWR, IA …) or "Source/Destination" and drawing reference.
- A utility flow diagram is "a special type of process flow diagram"; auxiliary systems (lube oil, seal oil) go on **separate auxiliary P&IDs**.
- A utility crossing is **one-to-many** (a header serves many consumers) — the current `ConnectorPair` cannot express it (`pid-structural-rules.md` finding 1).
- OPEN100 evidence: of the 19 drawing numbers referenced, at least ACW (aux cooling water), SWS (service water), WTS (water treatment), PDS (plant drains), WPS (waste processing), WSS (sampling) and make-up water are service/utility-type systems; **only ACW is among the 12 sheets** (the classification is my reading of the system names, [U]).
- Utilities are **parked** by the user (2026-10-01). Not re-opened here.

### 6.4 How many sheets, how many plants

- **No public count of P&IDs per plant was found.** Paliwal et al. write only "there are millions of PID sheets". [V]
- The only open real multi-sheet set is OPEN100 (12 of ≥ 19+ drawings). Nothing else complete was found (section 10).

---

## 7. The generator against the real picture

| Dimension | Generator today | Real (source) | Gap |
|---|---|---|---|
| Equipment classes | 6 | 99 non-custom in pyDEXPI [C]; ISO 10628-2 198 equipment symbols [V-S]; Kim 25 equipment labels [V-S] | 4× – 16× |
| Valve/piping classes | 3 (Globe, Ball, Check) | 55 in pyDEXPI [C]; ISO 10628-2 60 piping symbols; Kim 33 piping labels | 11× – 18× |
| Instrument "types" | 3 function classes; variable letters F L P T; one loop shape | 31 classes, but identity is in ISA strings; ISA-5.1 176 symbols; Kim 18 instrument labels; 390-token real vocabulary vs 113 generated | letters 4 vs ≥ 10; combinations 1 vs ≥ 15 |
| Instrument placement | all instruments in control loops on a valve | 69 % leaf attachments (degree 1) in OPEN100 [C]; local indicators dominate by count [U] | structural |
| Instrument density | 7.8 function nodes (5.2 bubbles) per sheet; 0.52 per valve [C] | 29.2 per sheet, 1.36 per valve [C] | 3.8× sparser (5.6× on bubbles) |
| Valve density | 15.0 per sheet [C] | 21.4 per sheet [C] | 1.4× sparser |
| Valve context | none | pump discharge check + block, control valve + bypass, PSV on vessel, drains/vents (HNF/KLM rules L1–L16) [P] | none encoded |
| Equipment per sheet | 14.7 [C] | 1–9 listed per OPEN100 drawing [P]; one column system per sheet [V] | ~3–4× too dense |
| Sheet partition | by unit, ≤ 18 equipment | by system, centred on a major item [V][P] | structural |
| Off-page per sheet | 5.2 [C] (headline preset, duplication 0.25) | 8.0 [C] | 1.5× sparser |
| Topology | random tree + recycles + cross-links | process patterns; heavy-tailed degree [V-S] | structural |
| Spares / parallel equipment | none | A/B(/C) groups in ≈ 35 % of listed equipment [P]+arith. | missing |
| Tag grammar | `{prefix}-{unit}-{n}` | `SYS-TYPE-NNN[A]` with ≥ 15 type codes [P] | prefixes 6 vs ≥ 15 |
| Line identity | `line_number` per stream | SIZE-SYS-NNNNNN-SPEC (class, size, insulation, tracing) [P] | attributes missing |
| Utilities | none (parked) | separate header sheets, one-to-many stubs [P] | parked |

Consequence for the thesis claim: the scale axis is "sheets", but a real sheet holds ~1.9× the symbol nodes of a generated one (≈ 82 vs ≈ 42.6 incl. stubs). A real 1 000-sheet plant would be ~80 000 symbol nodes against our 43 043 at H1000 (SMOKE-06, [P]). The claim (strategy depends on corpus scale) is conservative in that direction — ContextRAG would hit its wall at fewer sheets — but this is a statement about one nuclear plant's drafting and must be stated as such. [synthesis, [C] inputs]

---

## 8. What a realistic generator should add, ranked by realism gain per effort

Effort estimates are mine, relative (S < M < L), not measured. "Gain" is judged by the share of the real graph the change touches and by what question families it unlocks.

| Rank | Addition | Why (gain) | Effort | Evidence |
|---|---|---|---|---|
| **1** | **ISA-5.1 tag grammar**: ≥ 10 variable letters (A F L P T S W Q Z V), ≥ 15 function combinations (T, E, I, IT, IC, C, S+H/L, A+H/L, G, W, V, XV, HV, ZSO/ZSC), loop numbers shared across loop members; **line-attached local instruments** (PI, TI, LG) as leaf nodes; instrument count ≈ 1.4 × valve count | Instruments are the largest labelled real class (29/sheet, 7.6 % of all nodes), the generator has the narrowest vocabulary there, **no new pyDEXPI class needed**; unlocks "which flow transmitters…" question families | S | [C] OPEN100, [V] ISA table, [V] Hirtreiter 390 vs 113 |
| **2** | **Piping-component vocabulary 3 → ~30**: 7 valve types, 3 check, 5 safety devices, ~10 fittings (tee, reducer, blind flange, strainer, orifice, steam trap, sight glass …), ~5 flow elements; classes exist already | Valves + fittings are the next-largest class; `GateValve`, `ButterflyValve`, `PipeReducer`, `PipeTee` are each in the real DEXPI examples [C]; question family "count/locate X valves" gains breadth | S–M | [C] pyDEXPI, [C] C01/C02/C03 |
| **3** | **Standard trims** (pump: suction block + strainer, discharge check + block + PI; control valve + block/bypass; PSV with block valves on vessel; vessel drain/vent; PD pump external relief) | Turns random valve placement into the structure engineers recognise; makes "what is between X and Y" questions realistic | M | [P] HNF 3.2.4/3.2.5.3, KLM; rules L1–L16 |
| **4** | **Equipment vocabulary 6 → ~25** with nozzles; hubs of degree 4–10 | Cheap; multiplies type-filtered question families; matches the real equipment mix (OPEN100's equipment fits ~8 DEXPI classes, section 9) | S | [C] pyDEXPI, [C] tank degree tail |
| **5** | **A/B(/C) spares and same-service series** (tag suffix A/B/C; parallel copies of a pattern) | ≈ 35 % of OPEN100's listed equipment; directly stresses cross-sheet identity (A vs B confusion), the thesis's contribution 2 | S | [P] |
| **6** | **Sheets centred on a major item**: re-partition to 3–10 equipment per sheet, one column/vessel/exchanger system plus ancillaries, pumps with the suction vessel; target 80 ± 30 symbols per sheet | Corrects the density mismatch (section 7) | M (splitter strategy + budget) | [V] FB&D slides, [C] OPEN100 |
| **7** | **Process patterns instead of a random tree**: column + reboiler + condenser + reflux drum + pumps; compressor with KO drum and cooler; heater-reactor-separator; pump A/B | Gives realistic topology (heavy-tailed degree, ring/branch structure) and makes upstream/downstream questions meaningful | L | [V] Hirtreiter (pattern + Markov sampling), [P] pyDEXPI sample patterns are too thin |
| **8** | **Tag type codes and naming variants**: ≥ 15 type codes (PU, TK, HX, FL, VCT, HTR, AC, ION, SG, XR, …), system-code synonyms (ES/ESS …), symbol-vs-schedule spelling differences within a sheet, DETAIL views repeating equipment on a second sheet | Already half-built as EXP-0004 variant operators; type codes are the missing vocabulary | S | [P] OPEN100 |
| **9** | **Line attributes**: size, piping class, fluid code, insulation (`PipingNetworkSegment` fields exist) in a `SIZE-SYS-NNNNNN-SPEC` number | Adds line-level question families; low graph-structure impact | S | [C] pyDEXPI, [P] OPEN100 |
| **10** | **Utility headers, auxiliary sheets** (one-to-many connectors) | Large realism effect on cross-sheet structure (`k`), but needs a new connector concept and the user parked it | L | [P] HNF/KLM; parked 2026-10-01 |

Why this order. Items 1–2 and 4–5 are vocabulary swaps on classes pyDEXPI already has, so they change class counts and question-family breadth at almost no structural risk (the splitter, resolver and store treat the class as a label; ADR-0016 already sends unknown classes to `GenericItem`). Items 3, 6, 7 change topology and sheet composition, which is where retrieval behaviour (hop counts, `k`) could actually move; they should be measured with a before/after run of the existing ladder (EXP-0001 style), not assumed neutral. Item 10 is highest realism for cross-sheet structure but is outside the current scope decision.

---

## 9. Proposed vocabulary the generator can adopt (all names are verified pyDEXPI 1.2.0 classes unless marked)

Weights are **design parameters, not measurements** (no published per-class frequency exists, section 10). Where a ratio is sourced it is stated.

### 9.1 Equipment — 25 core classes + 2 optional drivers (from 6)

| Family | Classes | n | Grounding |
|---|---|---|---|
| Pump | CentrifugalPump, ReciprocatingPump, RotaryPump | 3 | PU-… on 8 of 9 OPEN100 systems [P]; ReciprocatingPump in DEXPI C01 [C] |
| Compressor / blower / fan | CentrifugalCompressor, ReciprocatingCompressor, CentrifugalBlower, AxialFan | 4 | HNF/KLM compressor rules [P] |
| Vessel | Tank, PressureVessel | 2 | TK/V/VE/VCT/XR in OPEN100 [P] (reactor vessel, pressurizer, relief tank, volume-control tank map here; mapping is [U]) |
| Column | ProcessColumn | 1 | FB&D slide 64–65 [V]; DEXPI C02 BASF [C] |
| Heat exchange | TubularHeatExchanger, PlateHeatExchanger, AirCoolingSystem, ElectricHeater | 4 | HX/HTR/AC/AXC in OPEN100 [P]; DEXPI C01 [C] |
| Fired / steam | Furnace, Boiler, SteamGenerator | 3 | SG in OPEN100 [P]; FB&D "fired heaters" [V] |
| Separation | GravitationalSeparator, ScrubbingSeparator, LiquidFilter, GasFilter | 4 | FL/FLT in OPEN100 [P] |
| Mixing | StaticMixer, Agitator | 2 | pyDEXPI sample patterns [P] |
| Cooling / stack | WetCoolingTower, Flare | 2 | HNF flare/ejector list, FB&D slide 78 [P/V] |
| Drivers (optional sub-items) | AlternatingCurrentMotor, SteamTurbine | 2 | — [U] |

Each equipment item gets 2–6 `Nozzle` sub-items (generator-side count is a parameter; C02 shows 11 nozzles on a column system with 8 equipment elements [C]). Not mapped to a pyDEXPI class: ion-exchanger (`ION` in OPEN100) → `Vessel`/`CustomVessel` [U].

### 9.2 Piping components — 30 classes (from 3)

| Group | Classes | n | Grounding |
|---|---|---|---|
| Operated valves | GateValve, GlobeValve, BallValve, ButterflyValve, NeedleValve, PlugValve, AngleValve | 7 | Rahul's 10 real symbol classes are 6 valve variants + fittings [V]; C01/C02/C03 [C] |
| Check valves | CheckValve, SwingCheckValve, GlobeCheckValve | 3 | rule L1 pump discharge [P] |
| Safety devices | SpringLoadedGlobeSafetyValve, SpringLoadedAngleGlobeSafetyValve, RuptureDisc, BreatherValve, FlameArrestor | 5 | rule L10/L11, DEXPI C01 [P][C] |
| Fittings | PipeTee, PipeReducer, BlindFlange, Flange, LineBlind, Strainer, ConicalStrainer, RestrictionOrifice, SteamTrap, SightGlass | 10 | C01/C02/C03 counts [C]; rules L2, L10 [P]; Rahul "concentric" = reducer [V] |
| Flow elements | FlowNozzle, VenturiTube, VariableAreaFlowMeter, ElectromagneticFlowMeter, FlowMeasuringElement | 5 | FE bubbles on OPEN100 sheet 5 [P] |

Control valves stay `GlobeValve`/`ButterflyValve`/`BallValve` with the loop's `ControlledActuator` (ADR-0044).

### 9.3 Instrumentation — 8 structural classes + an ISA grammar (from 3 classes)

| Item | Content | n | Grounding |
|---|---|---|---|
| Classes | ProcessSignalGeneratingFunction, ProcessInstrumentationFunction, ProcessControlFunction, ActuatingFunction, InstrumentationLoopFunction, MeasuringLineFunction (signal), SignalLineFunction, plus the two signal off-page connectors (already used) | 7 + 2 | [C] pyDEXPI; DEXPI C01 loops [C] |
| First letters | A, F, L, P, T, S, W, Q, Z, V | 10 | letters [V] Wikipedia ISA table; commonness [U]; A F L P T in the FB&D slide [V] |
| Function patterns | xE, xT, xI, xIT, xC, xIC, xS(H/L), xA(H/L), LG, TW, xV, XV, HV, ZSO/ZSC, AT/AIT | 15 | letters [V]; commonness [U]; FIC/FT/XV [V]; FE/FT, PI/LIC [P]; TC/LC/FC/FT/FFC/PC [V] |
| Placement | loop members (sensor + transmitter + controller + control valve) **and** local line-attached instruments (leaf, degree 1) | 2 | 69 % of OPEN100 instruments have degree 1 [C] |
| Density target | ≈ 1.4 instruments per valve; ≈ 29 instruments and ≈ 21 valves per real-size sheet | — | [C] OPEN100 (one nuclear plant) |

### 9.4 Plant structure and tags

| Item | Content | Grounding |
|---|---|---|
| Structure | ProcessPlant → PlantArea → PlantSection (unit) → PlantSystem (already `unit`) | [C] pyDEXPI |
| Tag type codes | PU, TK, HX, FL, VCT, HTR, AC, ION, SG, XR, V, VE, AXC, FLT, XSS (15), A/B/C suffix on parallel items | [P] OPEN100 |
| System codes with synonyms | e.g. ES↔ESS, CND↔COND, RHR↔RHRS | [P] OPEN100 |
| Line number | `SIZE-SYS-NNNNNN-SPEC` carrying size, class, insulation, tracing | [P] OPEN100; [V] FB&D slide 26: "pipe size, process or utility service code, number, pipe specification, insulation type and thickness, heat tracing" |

### 9.5 Sheet composition parameters (sourced targets)

| Parameter | Value | Source |
|---|---|---|
| Symbol nodes per sheet | 82.3 ± 26.3 (min 40, max 134) | [C] OPEN100 |
| Valves per sheet | 21.4 (9–35) | [C] |
| Instruments per sheet | 29.2 (9–49) | [C] |
| Off-page connectors per sheet | 8.0 (2–12) | [C] |
| Major items per sheet | 1 column, 1 fired heater, 1 complex compressor, 1–2 tanks/vessels, pumps with suction vessel | [V] FB&D slide 64 |
| Share of multi-sheet drawings | 4 of 9 observed drawing numbers | [P] |
| Share of equipment in A/B(/C) groups | ≈ 35 % of 43 listed items | [P]+arith. |

Class-count summary of the proposal: **25 equipment + 30 piping + 7 instrumentation = 62 classes** (+ 2 optional drivers; plus the ISA grammar of 10 variable letters × 15 function patterns) against 12 today (6 + 3 + 3), with 5 tag/structure additions.

---

## 10. Searched for and not found

| Item | What I did | Result |
|---|---|---|
| Per-class frequencies of valve, instrument or equipment types on real P&IDs | all papers above; web searches | **None published.** Kim 2022 gives category-level counts only; Rahul gives three class instance counts in prose; Digitize-PID none |
| Valves per line, instruments per equipment, line numbers per sheet | same | **Not found** |
| P&IDs per plant / per unit | web search ("how many P&IDs … refinery") | **Not found.** One source says "millions of PID sheets" (all plants worldwide, Paliwal) |
| A complete public multi-sheet real P&ID set other than OPEN100 | web search | **Not found** (DEXPI examples are single demonstrators; HydroShare dataset derives from them) |
| ISO 15926-4 / DEXPI RDL total class count | web search | **Not found.** pyDEXPI class counts used instead |
| ISO 10628-2 category names | web search; iTeh catalog host unreachable | **Not found** (only the counts via Kim 2022) |
| Gao, Zhao, Smidts nuclear P&ID component detection (Prog. Nucl. Energy 2020) | two searches | **Not located**; not read |
| "Mizanur" P&ID paper named in the brief | two searches | **No such paper identified**; if a full name or title exists, it can be searched |
| Moreno-García / Elyan SiED (EANN 2020): 2 432 symbol instances | search only | abstract-level (2 432 instances); class count and per-class table **not read** (RGU repository 403) |
| Yu et al. 2019 class list | MDPI 403 | **Not read** |
| Mani, Haddad … full dataset statistics beyond 18 + 11 diagrams | read | none reported |
| Instrument-type commonness (which ISA combinations are common) | looked for a source with counts | **None**; marked [U] |
| PIP PIC001 and ANSI/ISA-5.1 full text | not legitimately reachable | Only Kim 2022's counts |

---

## 11. Sources

**Papers and documents opened (full text or page):**
- Rahul, Paliwal, Sharma, Vig, arXiv 1901.11383 (28 Jan 2019). PDF, pdftotext.
- Paliwal, Jain, Sharma, Vig, "Digitize-PID", arXiv 2109.03794 (2021). PDF, pdftotext.
- Stürmer, Graumann, Koch, arXiv 2411.13929, Table A3 read as rendered image (page 11 of the arXiv PDF).
- Mani et al., CVPRW 2020, https://openaccess.thecvf.com/content_CVPRW_2020/papers/w8/Mani_Automatic_Digitization_of_Engineering_Diagrams_Using_Deep_Learning_and_Graph_CVPRW_2020_paper.pdf. PDF.
- Hirtreiter, Schulze Balhorn, Schweidtmann, arXiv 2211.05583. PDF.
- Lopomo et al., *Big Data Cogn. Comput.* 10(7):210, https://doi.org/10.3390/bdcc10070210. PDF.
- da Cunha et al., "On P&ID Symbol Recognition using Transformers", https://sol.sbc.org.br/index.php/eramiars/article/download/39477/39249. PDF.
- Ford, Bacon & Davis LLC, "Art of the P&ID", AIChE, https://www.aiche.org/sites/default/files/community/262801/aiche-community-site-event/514546/artofthepid-aiche-rbt11-15-19.pdf (94 slides; PDF creation date 18 Nov 2019).
- Kim et al. 2022, https://academic.oup.com/jcde/article/9/4/1298/6611631 (read through the fetch summarizer, [V-S]).
- Prasad & Mahapatra, arXiv 2604.16513, https://arxiv.org/html/2604.16513 ([V-S]).
- Wikipedia, "Piping and instrumentation diagram", raw wikitext, `action=raw` (fetched 2026-10-22).
- DEXPI TrainingTestCases, https://gitlab.com/dexpi/TrainingTestCases (C02 and C03 for DEXPI 1.3 downloaded; C01 from `data/external/C01V04-VER.EX01.xml`).

**Local artefacts counted:** installed `pydexpi==1.2.0`; `graph/schema.py`, `benchmark/generator.py`, `benchmark/generator_models.py`; PID2Graph graphml at `C:/Users/Otthon/Desktop/Munka/PID2Graph/Complete/{PID2Graph OPEN100, Dataset PID, PID2Graph Synthetic}`.

**Project notes relied on ([P], not re-opened):** `pid-structural-rules.md`, `pid2graph.md`, `Notes/open100-rendszerkodok.md`, `40-design/open100-annotation.md`, `40-design/realism-units-duplication-reach.md`, `30-experiments/2026-09-26-smoke-06-density.md`, ADR-0031.

**Caveats that apply to the whole note.**
1. OPEN100 is **one** nuclear plant (one design, one drafter, one date). Every "real" per-sheet figure drawn from it describes that plant.
2. The PID2Graph labels are coarse (`general` lumps equipment, fittings and miscellany; `pump` is unreliable), so class-level equipment frequencies cannot be derived from it.
3. The OPEN100 off-page pairing (23 pairs, 42 dangling, 8 unresolved) was read by a model from crops and has not had the human verification pass the annotation design specifies.
4. Kim 2022 and SynthPID numbers were read through a summarising fetch tool; the Kim symbol-standard counts were cross-checked by a second fetch, the rest only for internal consistency.
5. Table A3 of the PID2Graph paper is internally hard to reconcile for the "Real World" row (497 ± 338 nodes per plan vs 17 218 symbols for 60 plans); I quote the cells and do not derive from them.
