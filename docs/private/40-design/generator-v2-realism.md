---
component: benchmark/generator v2 — process patterns, ISA tags, standard trims, sheet composition
status: draft — awaiting review (ADR-0057 proposed)
related: [ADR-0057 (proposed), ADR-0007, ADR-0016, ADR-0017, ADR-0021, ADR-0025, ADR-0028, ADR-0031, ADR-0044,
          10-literature/real-pid-composition-2026-10.md, 10-literature/pid-structural-rules.md,
          40-design/plant-generator.md, 40-design/splitter.md, 40-design/control-valve-tagging.md]
date: 2026-10-25
---

# Design — generator v2: plants that look like real P&IDs

## 0. Recommendation

Build a **second generator, v2**, beside the frozen v1. v2 assembles a plant from **unit-operation patterns**
(column system, compressor stage, heater–reactor–separator, tank farm, exchanger train, flash drum, filtration,
blending) that are wired by a **seeded flowsheet grammar** over typed ports. Every pattern places its equipment
with **standard trims** (the codified local rules L1–L16 of `pid-structural-rules.md`), its **ISA-5.1 instruments**
(control loops, trip loops with XV on-off valves, local gauges hanging on lines), **A/B(/C) spares**, and real
**line numbers**. A new splitter strategy draws **one sheet per drawing group** the pattern declares (a column
per sheet, a fired heater per sheet, pumps with their suction vessel — Ford, Bacon & Davis slide 64).

Four choices carry the design:
1. **v1 is frozen, v2 is opt-in by type, not by a default.** v1's classes, config, preset and every constant it reads
   are pinned to their current values before the schema grows; v2 has its own config class with a
   `generator_version: Literal["v2"]` discriminator, its own preset and its own corpus ids (§2).
2. **v2 adds no new visible property.** The device kind of an item is machine-readable from `node_class` plus the
   ISA letters of its `tag`, parsed by one published grammar (§5, §11) — exactly as on a printed P&ID. This keeps
   the store, the resolver and the Cypher schema text unchanged in shape.
3. **Line-mounted instruments use DEXPI C01's own tap structure** (a `PipeTee` on the line, a branch to the root
   component, the sensor located there). Measured today: a sensor located on a `PipingNetworkSegment` loses its
   edge in pyDEXPI's abstraction; one located on a piping component keeps it (§3).
4. **Targets come from OPEN100 (one nuclear plant) or are declared design parameters**; no per-class frequency is
   published anywhere (`real-pid-composition-2026-10.md` §10), so class weights are parameters with a composition
   check, not calibrations (§12).

Effort, **estimate** (coder pace is unmeasured): 15 coder tasks, 4 S, 9 M, 2 L (§14). Every task leaves the 2,048
tests green and the v1 golden digests unchanged.

## 1. Goals and what the claim needs

**User goal (2026-10-24).** Synthetic P&IDs that resemble real ones almost entirely: many instrument kinds, and
connections with meaning, following current practice; "real life is more complicated than 3 valve types and 6
equipment types". Chosen depth: vocabulary + standard trims + sheet density + process patterns.

**Thesis claim.** The optimal retrieval strategy is a function of corpus scale; the single-page optimum inverts at
plant scale. v1 measured it on random-tree plants (EXP-0001 ladder, EXP-0002 sealed test). v2 serves the claim in
three ways:

| Need | Why the claim needs it | v2 mechanism |
|---|---|---|
| External validity | An examiner can say the inversion is an artefact of toy topology. ADR-0007 deferred realism to "a later phase"; this is that phase. | Patterns, trims, ISA tags, OPEN100-level density |
| Same x-axis | `k` (sheet crossings on an evidence path) and sheet count are the axes. A real sheet holds ≈ 82 symbols vs ≈ 42.6 nodes today (composition note §7) — so "1,000 sheets" means different corpora. | Sheet composition targets from OPEN100 §9.5 |
| A replication, not a new system | v2 must be measured by the **frozen** system (F1, ADR-0053), so a change in results is attributable to the data. | No new visible property; v1 prompts and schema text unchanged for v1 corpora (§10) |
| Contribution 2 (cross-sheet identity) | A/B spares (≈ 35 % of OPEN100's listed equipment) are the realistic hard case for identity. | Spares with `A/B/C` suffixes in shared tag blocks (§5) |

**Non-goals (this phase).** Utility headers and utility P&IDs (parked by the user 2026-10-01; only consumer-side
stubs, §6.6, open question Q1); equipment or datasheet data (ADR-0021); rendering realism beyond the demo export;
several plants per corpus; KKS or IEC 81346 tag systems (OPEN100 uses neither, `pid-structural-rules.md` P4).

## 2. Versioning: v1 frozen, v2 opt-in

**The hazard is not the v1 files, it is the shared constants they read.** Verified in code today:

| v1 code path | Reads | What growing the schema would do |
|---|---|---|
| `generator.py` `_add_valves` | `rng.choice(sorted(VALVE_CLASSES))` | a different valve on every stream, a different RNG stream after it |
| `generator_models.py` `GeneratorConfig.equipment_weights` default | `sorted(schema.EQUIPMENT_CLASSES)` | different equipment classes; `ingest.json` bytes change |
| `generator.py` loop candidates | `OPERATED_VALVE_CLASSES` | safe on v1 plants, but frozen anyway |
| `split_models.py` `SplitConfig.equipment_classes` default | `schema.EQUIPMENT_CLASSES` | `ingest.json` `config.split` bytes change |
| `pydexpi_adapter.topology_node_class` (also used by the Proteus import of EX01) | `IMPORTABLE_CLASSES` + ancestor walk | **EX01's `SwingCheckValve`, `PipeTee`, `ReciprocatingPump`, … would map to new classes instead of `CheckValve` / `GenericItem` / `Pump`** — EXP-0001's EX01 anchor would change |
| `qa/schema_text.py` `build_schema_text` | `sorted(VISIBLE_NODE_PROPERTIES)` | every CypherRAG prompt changes, so the F1 prompt hashes break |

**Mechanism.**
1. **Stage 0 pins v1 first** (§14, V2-T0). New constants `V1_EQUIPMENT_CLASSES`, `V1_VALVE_CLASSES`,
   `V1_OPERATED_VALVE_CLASSES`, `V1_IMPORTABLE_CLASSES` hold today's exact values. `generator.py`, the
   `GeneratorConfig` default, the `SplitConfig` default and `topology_node_class`'s default vocabulary switch to them.
   Behaviour is identical; golden tests prove it before any class is added.
2. **v2 has its own types**, never a new field on v1 types:
   - `benchmark/v2/config.py`: `GeneratorConfigV2(BaseModel)` with `generator_version: Literal["v2"] = "v2"` and all
     v2 knobs. `GeneratorConfig` (v1) gains **no** field, so its JSON is byte-identical.
   - `benchmark/v2/planner.py`: `plan_plant_v2(config, builder: PlantBuilderV2) -> GenerationRecordV2`.
   - `adapters/pydexpi_builder_v2.py`: `DexpiPlantBuilderV2`, `generate_plant_v2(config)`.
   - `ingest/headline_v2.py`: `HeadlinePresetV2` and `smallest_n_units_v2`. `HeadlinePreset` is untouched.
3. **One dispatch point**, `benchmark/generator_dispatch.py`:
   `AnyGeneratorConfig` = a Pydantic union with a **callable `Discriminator`** (`"v2"` iff the key
   `generator_version` equals `"v2"`, else `"v1"`). A plain `GeneratorConfig | GeneratorConfigV2` union is not
   enough: in smart mode a v1 dict without the key could validate as v2 through the default;
   `generator_config_from_json(data: dict) -> AnyGeneratorConfig` returns v2 iff `data.get("generator_version") == "v2"`,
   else v1 (every existing `ingest.json` has no such key); `generate_plant_graph_any(config) -> nx.DiGraph`.
   Callers that change: `ingest/pipeline.py` (`build_synthetic_corpus`, `generate_plant_graph`), `qa/corpus.py`
   (`_rebuild_synthetic_artifacts`), `qa/models.py` (`CorpusRecord.generator_config: AnyGeneratorConfig`),
   `ingest/__main__.py` (`--generator {v1,v2}`, default `v1`; `--headline` keeps meaning the v1 preset,
   `--headline-v2` is new).
4. **Corpus ids carry the version**: `D100g2`, `D1000g2` (dev, seed 1), `H100g2`, `H1000g2` (test, fresh seeds,
   ADR-0045's rule). v1 ids are never reused.
5. **Golden tests that guard v1** (V2-T0), all recorded at the HEAD before V2-T0:
   - the existing `_GOLDEN_SMALL` and `_GOLDEN_HEADLINE_5_UNITS_SEED_1` topology digests (`tests/test_control_valve_tagging.py`);
   - sha256 of `JsonSerializer` bytes of `generate_plant(GeneratorConfig(seed=s))`, s = 0, 1, 2, and of the headline preset at 5 units;
   - the `config` block of `run_synthetic(...)` for those configs, as JSON bytes;
   - `build_schema_text` on a v1 toy load plan (both profiles), as text;
   - the EX01 import: sorted `(node_class, tag)` pairs, sorted edges with relations, and the `ImportReport` counts.
   Any later task that changes one of these fails the suite.

**What v1 artefacts stay valid.** EXP-0001 ladder (H1–H30), EXP-0002 sealed test (H100, H1000), D100/D1000 dev runs,
the demo's plants and all their question sets: they are rebuilt from `ingest.json` through the dispatch, which
returns `GeneratorConfig` for them, and the goldens hold the bytes.

## 3. Evidence this design rests on (incl. a prototype run)

Sources already gathered (not re-swept): `real-pid-composition-2026-10.md` (§7 gap, §8 ranking, §9 vocabulary,
§9.5 targets, §10 not published), `pid-structural-rules.md` (L1–L20, C1–C11, S1–S17), DEXPI C01 reference file
(`data/external/C01V04-VER.EX01.xml`).

**Verified today, 2026-10-25** (pyDEXPI 1.2.0 in the repo's `uv` environment, scratch scripts in the session
scratchpad, not in the repository):

| Check | Result |
|---|---|
| Every class name used in §4 exists in `pydexpi.dexpi_classes.pydantic_classes` | all 99 names checked are present (they include every class in §4); ancestor chains printed (e.g. `Agitator` is **not** under `Mixer`; `AirCoolingSystem` and `ElectricHeater` are under `HeatExchanger`; `Furnace`, `Boiler`, `SteamGenerator` under `Heater`) |
| C01's pressure tap | `PipeTee-3` on the line → branch segment → `BallValve-3` (root valve) → `BlindFlange-1`; `PT4712.01` "is located in" `BlindFlange-1` (XML lines 1287–1398, 2291–2297). `TT4750.03` is located in `Nozzle-17`. |
| PSGF located on a `PipingNetworkSegment` | **edge lost** in `GraphAbstractor.build_conceptual_graph`: no `sensingLocation` edge survives |
| PSGF located on a piping component (`BlindFlange`, `FlowMeasuringElement`, `GateValve`) | `reference/sensingLocation` edge kept → the adapter's `measured_by` rule applies |
| PSGF located on a dedicated equipment nozzle | kept (v1 rule, re-confirmed) |
| Branch from a `PipeTee` (split) and two segments into one `PipeTee` (merge) | both kept: `pu→tee`, `tee→ch`, `tee→rb`; `pa→mt`, `pb→mt`, `mt→v` |
| Open end at the segment target (vessel → block valve → PSV, nothing after) | kept: `v→gp`, `gp→psv`; PSV is a leaf |
| Open start (utility supply stub) | `construct_new_segment` with the first item as source **raises `IndexError`**; with `source_connector_item=None` and a leading dangling `Pipe` it builds, and `g→ex` survives |
| Piping nodes in the conceptual graph | carry `lineNumber` and `collapsed_from = "<system id>,<segment id>"` — so a piping node's unit can be read from its `PipingNetworkSystem.parentStructure` in the model |
| Unknown classes on the **generated** path | `map_conceptual_graph` drops them (prototype: GateValve 3, Strainer, PipeTee, FE, BlindFlange, PSV dropped) — v2 classes must enter the schema |
| Safety valves | have `positionNumber`, **no** `pipingComponentNumber` |

One side effect to record: a `uv run --frozen` call re-synced one package in the project venv (to the lock file);
no dependency changed.
## 4. Vocabulary

All class names verified in pyDEXPI 1.2.0 (§3). "Default on" = used by a pattern whose default weight is > 0.
Weights are **design parameters** (no published frequency exists, composition note §10); the composition check
in §12 is what keeps them honest.

### 4.1 Equipment — 25 classes (v1: 6)

| Class | pyDEXPI parent | Type code (by role) | Roles in patterns (§7) | Default on | Grounding |
|---|---|---|---|---|---|
| `CentrifugalPump` | Pump | `P` | every pump set (U1–U8) | yes | OPEN100 PU on 8 of 9 systems [P] |
| `ReciprocatingPump` | Pump | `P` | dosing / metering pump (U8), PD transfer | yes | DEXPI C01 [C]; rule L5 |
| `RotaryPump` | Pump | `P` | viscous transfer in tank farm (U4) | yes | composition note §9.1 |
| `CentrifugalCompressor` | Compressor | `K` | compressor stage (U2) | yes | KLM/HNF compressor rules L16 |
| `ReciprocatingCompressor` | Compressor | `K` | compressor stage variant (U2) | yes | same |
| `CentrifugalBlower` | Blower | `B` | combustion-air blower of the fired heater (U3) | yes | FB&D "fired heaters" [V] |
| `AxialFan` | Fan | `B` | induced-draft fan of the fired heater (U3, variant) | yes | — [U], declared |
| `Tank` | Vessel | `TK` | atmospheric storage (U4) | yes | OPEN100 TK [P]; FB&D tanks 1–2 per P&ID [V] |
| `PressureVessel` | Vessel | `V` drum, `R` reactor, `D` reflux drum | reflux drum (U1), reactor (U3), flash drum (U6), agitated vessel (U8) | yes | OPEN100 V/VE/XR [P] |
| `ProcessColumn` | — | `T` | distillation column (U1) | yes | FB&D slides 64–65 [V]; DEXPI C02 [C] |
| `TubularHeatExchanger` | HeatExchanger | `E` | reboiler, condenser, feed/effluent, coolers (U1, U3, U5) | yes | DEXPI C01 [C]; OPEN100 HX [P] |
| `PlateHeatExchanger` | HeatExchanger | `E` | exchanger-train variant (U5) | yes | DEXPI C01 [C] |
| `AirCoolingSystem` | HeatExchanger | `EA` | air condenser / aftercooler (U1, U2, U3) | yes | OPEN100 ACC-AC [P] |
| `ElectricHeater` | HeatExchanger | `EH` | trim heater in an exchanger train (U5) | yes | OPEN100 HTR [P] (role mapping [U]) |
| `Furnace` | Heater | `H` | fired heater (U3) | yes | FB&D "one fired heater per P&ID" [V] |
| `GravitationalSeparator` | Separator | `V` | product separator (U3), three-phase flash (U6) | yes | composition note §9.1 |
| `ScrubbingSeparator` | Separator | `V` | compressor suction KO drum (U2) | yes | rule L16 (suction side) |
| `LiquidFilter` | Filter | `F` | filter package A/B (U7) | yes | OPEN100 FL/FLT, CVCS-FL-112A/B [P] |
| `GasFilter` | Filter | `F` | compressor suction / fuel-gas filter (U2, U3) | yes | composition note §9.1 |
| `StaticMixer` | Mixer | `M` | blending (U8) | yes | pyDEXPI sample patterns have a mixer [P] |
| `Agitator` | — | `M` | agitator of the agitated vessel (U8); its own node, fed by nothing | yes | DEXPI `Tank.agitator` field exists [C] |
| `Boiler` | Heater | `H` | utility steam unit (U9) | **no** | utilities parked |
| `SteamGenerator` | Heater | `H` | utility steam unit (U9) | **no** | OPEN100 SG [P] |
| `WetCoolingTower` | CoolingTower | `CT` | cooling-water unit (U9) | **no** | utilities parked |
| `Flare` | WasteGasEmitter | `FS` | flare unit (U9) | **no** | utilities parked |

Not used: drivers (`AlternatingCurrentMotor`, `SteamTurbine`) — a driver as its own node would add an equipment item
per pump without a P&ID line (composition note §9.1 marks them [U]); v1's generic `Compressor` and `HeatExchanger`
stay v1-only. Type codes are a **design choice** close to OPEN100's style (PU→`P`, HX→`E`, TK, V) and v1's letters;
real codes are company-specific (`pid-structural-rules.md` P8).

**Nozzles.** Every equipment item gets one `Nozzle` per line end plus dedicated sensing nozzles (v1 rule). C02 shows 11
nozzles on a column system of 8 equipment elements [C]; v2's nozzle count follows from the pattern, not a parameter.

### 4.2 Piping components — 31 classes (v1: 3)

`piping_kind` is a new `ClassSpec` field (§4.5). It is what separates "valves" from fittings in every count and
family.

| Class | `piping_kind` | Tag code | Where it is placed (§6, §7) | Grounding |
|---|---|---|---|---|
| `GateValve` | operated | `GTV` | block valves: pump suction/discharge, CV-station blocks, PSV inlet block, drains, vents | L1, L2, L9, L10, L13 |
| `GlobeValve` | operated | `GV` (manual) / `xV` (control) | CV-station bypass; control-valve body (sliding stem) | L9; ADR-0044 |
| `BallValve` | operated | `BV` / `XV` | instrument root valves (C01); on-off valve bodies (XV) | DEXPI C01 [V] |
| `ButterflyValve` | operated | `BFV` / `xV` | large-line block valves; gas control-valve body | composition note §9.2 |
| `NeedleValve` | operated | `NV` | root valve of DP taps; sample points | — declared |
| `PlugValve` | operated | `PGV` | tank-farm manifolds (variant) | — declared |
| `AngleValve` | operated | `xV` | letdown control-valve body (separator liquid outlet) | — declared |
| `CheckValve` | check | `CHV` | compressor discharge; utility return | L16 |
| `SwingCheckValve` | check | `CHV` | pump discharge (L1 prefers non-wafer) | L1 (KLM: avoid wafer type) |
| `GlobeCheckValve` | check | `CHV` | minimum-flow and small lines | L6 |
| `SpringLoadedGlobeSafetyValve` | safety | `PSV` | vessel / column / drum / exchanger shell PSVs | L10, L11; DEXPI C01 |
| `SpringLoadedAngleGlobeSafetyValve` | safety | `PSV` | PSV variant; PD-pump external relief | L5 |
| `RuptureDisc` | safety | `PSE` | reactor (with or without a PSV downstream) | composition note §9.2 |
| `BreatherValve` | safety | `PVSV` | atmospheric tank vents | composition note §9.2 |
| `FlameArrestor` | safety | `FA` | tank vents with the breather valve | composition note §9.2 |
| `PipeTee` | junction | — (untagged) | every split, merge, bypass and instrument tap | DEXPI C01 [V] |
| `PipeReducer` | fitting | — (untagged) | either side of a control valve (CV smaller than the line) | DEXPI C01, C02 [C] |
| `BlindFlange` | fitting | — (untagged) | end of vents and drains; stand-in for a thermowell flange (§4.3) | DEXPI C01 [V] |
| `LineBlind` | fitting | — (untagged) | battery-limit isolation at unit inlets/outlets | composition note §9.2 |
| `Strainer` | fitting | `STR` | permanent basket strainer, rotary/PD pumps | L2 (HNF: "for all rotary pumps") |
| `ConicalStrainer` | fitting | `STR` | temporary suction screen, centrifugal pumps and compressors | L2, L16 |
| `RestrictionOrifice` | fitting | `FO` | minimum-flow bypass, purge lines | L6; ISA `FO` (O = orifice) |
| `SteamTrap` | fitting | `ST` | condensate outlet of steam heaters / reboilers | L15 |
| `SightGlass` | fitting | `SG` | flow sight glass on the reboiler return / reflux line (variant) | composition note §9.2 |
| `FlowMeasuringElement` | primary element | `FE` | orifice-type flow element of a flow loop | OPEN100 FE bubbles [P] |
| `VenturiTube` | primary element | `FE` | gas / steam flow (variant) | composition note §9.2 |
| `FlowNozzle` | primary element | `FE` | steam flow (variant) | same |
| `ElectromagneticFlowMeter` | primary element | `FE` | water / conductive liquid flow | same |
| `MassFlowMeasuringElement` | primary element | `FE` | Coriolis mass flow: custody/metering in U4 and U8 | added for the joint project's Coriolis meter (§11) |
| `VariableAreaFlowMeter` | primary element | `FI` | local rotameter on purge / seal lines (local instrument) | same |
| `PositiveDisplacementFlowMeter` | primary element | `FE` | tank-farm metering (variant, with FQI) | same |

Dropped from the composition note's list: `Flange` (no placement a P&ID draws). Added: `MassFlowMeasuringElement`,
`PositiveDisplacementFlowMeter`. **Control valves stay `GlobeValve` / `ButterflyValve` / `BallValve` / `AngleValve`
bodies with the loop's `xV` tag** (ADR-0044's rule, extended to four bodies).

### 4.3 Instrumentation — 9 classes, two modelling conventions

| Class | Role in v2 | In the `DiGraph`? |
|---|---|---|
| `ProcessSignalGeneratingFunction` (PSGF) | the sensor: transmitter (`xT`), element (`xE`), local indicator (`PI`, `TI`, `LG`, `FI`), position switch (`ZSO`, `ZSC`) | yes |
| `ProcessInstrumentationFunction` (PIF) | the bubble that does something with a signal: indicator (`xI`), controller (`xIC`), alarm (`xAH`), switch/trip (`xSHH`, `xSLL`), hand switch (`HS`), totaliser (`FQI`), ratio (`FFIC`) | yes |
| `ActuatingFunction` (AF) | the actuator of a control or on-off valve; untagged (ADR-0044) | yes |
| `MeasuringLineFunction`, `SignalLineFunction` | PSGF→PIF and PIF→AF links | as `send_signal_to` |
| `InstrumentationLoopFunction` | groups a loop's PIFs | collapsed |
| `ActuatingSystem` | carries the valve's tag (`actuatingSystemNumber`, ADR-0044) and the operated-valve reference | collapsed |
| `ControlledActuator` | **on XV: `subTagName = "XY-…"` marks the solenoid** (ISA Y = relay/compute/solenoid function); on control valves present without data | collapsed (stays in the DEXPI JSON) |
| `Positioner` | on control valves (`subTagName = "…_ZC"`-style is not used; present without data) | collapsed |

`ProcessControlFunction` is **not** used: the loop families select controllers by `node_class == PIF`; a subclass
would need a schema promotion for no question (ADR-0016 rule 4).

**Convention I-1 — loop instrument = PSGF + PIF** (DEXPI C01: every measuring bubble has a PSGF, e.g.
`PT4712.01`). PSGF tag `xT-…` (or `xE-…`), PIF tag `xIC-…`, `xI-…`, `xSHH-…`; one loop number for all members.

**Convention I-2 — local instrument = one PSGF, no PIF.** A pressure gauge, a dial thermometer, a level glass or a
rotameter is one bubble on the drawing with one printed tag (`PI-12021`). Modelling it as a PSGF alone gives one
node of degree 1 (sheet graph: one `measured_by` edge), which is what OPEN100 shows for 242 of 350 instruments
(69 %, composition note §5.2). **Deviation from C01** (which would add an untagged PSGF behind a PIF bubble), chosen to
keep one node per drawn bubble and one tag per node; recorded in ADR-0057.

**Where a sensor is located** (the only three forms that survive pyDEXPI's abstraction, §3):

| Mounting | DEXPI `sensingLocation` | Graph result | Used for |
|---|---|---|---|
| on equipment | a dedicated `Nozzle` (v1 rule) | `equipment -measured_by-> PSGF` | LT, LG, LSHH, LSLL, PT/PI on vessel top, TT on column trays, ST/VT on a machine |
| inline flow element | the `InlinePrimaryElement` itself | `FE -measured_by-> FT` | every flow measurement |
| line tap (C01 structure) | the root component at the end of a branch from a `PipeTee` on the line | `line … -send_to-> PipeTee -send_to-> root -measured_by-> PSGF` | PT, PI, PDT taps (root = `BallValve` or `NeedleValve`); TT, TI, AT taps (root = `BlindFlange`, **our stand-in for a thermowell / probe flange** — DEXPI has no thermowell class) |
| on a valve | the valve | `XV -measured_by-> ZSO` | position switches on on-off valves |

### 4.4 ISA-5.1 letters and function templates

Letters are valid by the ISA table (composition note §4.1, [V], secondary source); **which combinations are common
is not published** (§4.2 there, [U]). The template set below is a design choice; each row says where v2 places it.

| Template | Classes | Placed in | Example |
|---|---|---|---|
| `xT → xIC → AF → xV` (control loop) | PSGF, PIF, AF, CV body | every pattern's controlled variables (§7) | `LT-12005`, `LIC-12005`, `LV-12005` |
| `xT → xI` (indicating transmitter, monitoring) | PSGF, PIF | key temperatures, pressures, flows | `TT-12008`, `TI-12008` |
| `xT → xI` with alarm in the PIF letters | PIF letters `IAH` / `IAL` | vessel levels, bearing temperature | `LIAH-12011` |
| `xT → xSHH / xSLL → AF → XV` (trip) | PSGF, PIF, AF, `BallValve` with solenoid `XY` | tank overfill, KO-drum high level, separator high pressure, fuel gas low pressure | `LT-12030`, `LSHH-12030`, `XV-12030` |
| `HS → AF → XV` (remote manual on-off) | PIF (category `H`), AF, `BallValve` | tank inlets, unit battery limits | `HS-12031`, `XV-12031` |
| `ZSO`, `ZSC` on an XV | PSGF located on the XV | every XV with probability `p_limit_switches` | `ZSO-12030` |
| local gauges | PSGF alone | pump discharge (L3), vessel tops, exchanger inlets/outlets | `PI-12021`, `TI-12022`, `LG-12023` |
| `PDT → PDI` | PSGF (`P`, modifier `D`), PIF | filter packages, column ΔP, strainers of compressors | `PDT-12040`, `PDI-12040` |
| `FT → FQI` (totaliser) | PSGF, PIF (`F`, modifier `Q`) | tank-farm metering | `FQI-12050` |
| `FT, FT → FFIC → AF → FV` (ratio) | two PSGFs, PIF (`F`, modifier `F`) | blending (U8) | `FFIC-12060` (Hirtreiter's SFILES examples use FFC [V]) |
| `AT → AIC` / `AT → AI` | PSGF, PIF | product quality on column overhead / blend outlet | `AT-12061`, `AIC-12061` |
| `ST → SI`, `VT → VAH` | PSGF on machine nozzle, PIF | compressors | `ST-12070`, `VAH-12071` |
| `BE → BSL → AF → XV` (flame failure trip) | PSGF on furnace nozzle, PIF, AF, XV | fired heater fuel gas | `BSL-12080`, `XV-12080` |

First letters in use: **A, B, F, H, L, P, S, T, V, X, Z** (11; v1: F, L, P, T). Modifiers: D, F, Q, S (S = safety, as in PSV).
Readout/output: E, G, I, T, C, S, V, A, Y. Function modifiers: H, L, HH, LL, O, C. About **20 function templates** (v1: one). The
DEXPI slots are filled as follows, **keeping v1's convention** so the adapter's tag rule — shared with the EX01
import — does not change: `processInstrumentationFunctionCategory` = first letter;
`processInstrumentationFunctionModifier` = **all succeeding letters** (`"IC"`, `"DI"`, `"SHH"`); additionally
`processInstrumentationFunctions` = the function letters alone (DEXPI fidelity; the adapter ignores it).

### 4.5 Schema changes (`graph/schema.py`, split into `schema.py` + `schema_classes.py` for the 400-line cap)

- `NodeClass` gains the 49 new classes of §4.1–§4.2 (25 + 31, minus the 7 already in the schema:
  `CentrifugalPump`, `Tank`, `PressureVessel`, `ProcessColumn`, `GlobeValve`, `BallValve`, `CheckValve`).
  21 equipment classes are default-on; the 4 utility classes wait for U9. `CLASS_SPECS` gets a curated
  label chain for each, cut at the first schema root exactly as today (`SwingCheckValve:CheckValve:PipingComponent`,
  `PipeTee:PipeFitting:PipingComponent`, `MassFlowMeasuringElement:InlinePrimaryElement:PipingComponent`,
  `CentrifugalCompressor:Compressor:Equipment:TaggedPlantItem`, …). A test checks each chain against pyDEXPI's own
  ancestry and the Neo4j label regex.
- `ClassSpec.piping_kind: Literal["operated", "check", "safety", "fitting", "junction", "primary_element"] | None = None`.
  v1's three classes get `operated`, `operated`, `check`.
- Constants (values for v1's classes unchanged by construction):
  `PIPING_CLASSES` = every `PIPING` category class; `VALVE_CLASSES` = kinds operated ∪ check ∪ safety;
  `FITTING_CLASSES`, `JUNCTION_CLASSES`, `PRIMARY_ELEMENT_CLASSES`; `CONTROL_VALVE_BODY_CLASSES` = Globe, Ball,
  Butterfly, Angle; `OPERATED_VALVE_CLASSES` = kind operated; `EQUIPMENT_CLASSES` = every equipment class;
  `V1_*` pins (§2). `UNTAGGED_CLASSES` += `PipeTee`, `PipeReducer`, `BlindFlange`, `LineBlind`.
- `RELATION_ENDPOINTS`: `send_to` over `EQUIPMENT ∪ PIPING`; `control` targets `CONTROL_VALVE_BODY_CLASSES`;
  `measured_by` sources `EQUIPMENT ∪ PIPING`. Only more is allowed, so every v1 graph still validates.
- `VISIBLE_NODE_PROPERTIES`, `VISIBLE_EDGE_PROPERTIES`: **unchanged**.

## 5. Tag and line-number grammar

One module, `benchmark/v2/tags.py`, holds every `format_*` function and `parse_tag(tag) -> ParsedTag | None`.
Fixed-width sequence fields make each number injective without a separator inside it (unit `u` is variable
width, the sequence after it is fixed width). Every tag and line number matches the question-anchor token
`[A-Za-z0-9]+(?:[-.][A-Za-z0-9]+)*` (`qa/anchors.py`), so no `"` for inches and no `/` in sizes.

```
equipment   := TYPE "-" u SEQ2 [TRAIN]             P-1203A   T-1201   E-1204   TK-1202   K-1201
TYPE        := P | K | B | TK | V | R | D | T | E | EA | EH | H | F | M | CT | FS
TRAIN       := "A" | "B" | "C"                      installed spares and parallel trains (§7.1)
instrument  := ISA "-" u SEQ3                       FIC-12014  PT-12014  FV-12014  PI-12021  XV-12030
ISA         := FIRST [MOD] FUNCS [FMOD]             FIRST ∈ A B F H L P S T V X Z; MOD ∈ D F Q S;
                                                    FUNCS ∈ E G I T C S V A Y (1–3); FMOD ∈ H L HH LL O C
                                                    (PVSV for breather valves is a plant code, not ISA grammar)
loop        := all members of one loop share u SEQ3 (FT-12014, FIC-12014, FV-12014)
manual valve:= VCODE "-" u SEQ3                     GTV-12107  BV-12108  CHV-12109  NV-12110
safety      := PSV | PSE | PVSV | FA "-" u SEQ3     PSV-12012 (instrument-style number, ISA practice)
fitting     := STR | FO | ST | SG "-" u SEQ3        STR-12041 ; PipeTee/PipeReducer/BlindFlange/LineBlind untagged
line number := SIZE "-" SVC "-" u SEQ4 "-" SPEC "-" INS
                                                    6-P-120017-A1A-N   2-CWS-120031-A1A-N   1-FL-120044-B1A-N
SIZE        := 1 | 2 | 3 | 4 | 6 | 8 | 10 | 12 | 16 | 20 | 24      (NPS inch, integer)
SVC         := P (process liquid) | PG (process gas) | CWS | CWR | LPS | MPS | CD | FG | FL | IA | N
SPEC        := A1A | B1A | C1A | D1A                 (piping class, invented codes, pressure-rating order)
INS         := N | H | C | P | HT                    (none, hot, cold, personnel protection, heat traced)
```

- `SEQ2` per (unit, TYPE) for equipment, 01–99; A/B/C share one number (`P-1203A`, `P-1203B`).
- `SEQ3` per unit, **one counter shared by every instrument loop, local instrument, safety device and fitting
  number**, in planning order, so loop numbers interleave as on real drawings. Manual valves have their own `SEQ3`
  counter per (unit, VCODE).
- `SEQ4` per unit for lines; for a two-digit unit, `u SEQ4` gives OPEN100's six-digit form (`RCS-100007` ↔ `120017`).
- Overflow (more than 99 / 999 / 9,999 in a field) **raises**; the planner never truncates.
- **Fluid code** (`fluid_code` on `send_to`, already visible) = `SVC`. v1 used `PL` / `PG`; v2 uses the service code.
- **Spec break → new line number** (L20): a line changes number where its spec changes (compressor discharge,
  letdown valve downstream side).
- DEXPI fields filled for every `PipingNetworkSystem`: `lineNumber` (the string), `fluidCode`, `pipingClassCode`,
  `nominalDiameterRepresentation` (`"6"`), `insulationType` (INS). These are the line-list fields FB&D slide 26
  names (size, service, number, spec, insulation, tracing) — line identification, **not equipment data**
  (ADR-0021 is about equipment/datasheet attributes).
- Unit names: `PlantSection.plantSectionName = "{SYS} {title}"`, e.g. `"DST Crude column"`; `SYS` is the pattern's
  system code (U1 `DST`, U2 `CMP`, U3 `RXN`, U4 `TKF`, U5 `HXT`, U6 `FLS`, U7 `FIL`, U8 `BLD`, U9 `UTL`).
  `unit_id` stays `str(u)` (v1's form; the unit router and `normalize_unit_id` keep working).
## 6. Standard trims (local arrangements)

A **trim** is a pure function in `benchmark/v2/trims.py` that returns planned items (no RNG of its own; it receives
the pattern's `random.Random`). Flow order inside each line is from source to target. `[x]` = optional, with the
named probability, a **declared parameter** in `TrimConvention` (`benchmark/v2/config.py`); the default value is
chosen to hit the §12 valve target, never claimed to be sourced.

| # | Trim | Planned arrangement (flow order) | Rule / source | Parameters (default) |
|---|---|---|---|---|
| 6.1 | **Centrifugal pump suction** | vessel nozzle → `GateValve` (suction block) → `ConicalStrainer` (temporary screen, at the first flanged joint) → pump suction nozzle | L2 (HNF 3.2.5.3, KLM p. 19) | — |
| 6.2 | **Rotary / PD pump suction** | as 6.1 with a permanent `Strainer` | L2 ("permanent basket strainers for all rotary pumps") | — |
| 6.3 | **Pump discharge** | pump nozzle → `PipeTee` tap → root `BallValve` → `PI` (local) ; → `SwingCheckValve` → `GateValve` (block) → header | L1 (check between pump and block), L3 (PI between nozzle and check) | — |
| 6.4 | **Pump vent / drain** | casing nozzle → `GateValve` → `BlindFlange` (open end) | L4 | `p_pump_vent_drain` (1.0, KLM shows them) |
| 6.5 | **PD-pump external relief** | discharge `PipeTee` (before the check) → `SpringLoadedAngleGlobeSafetyValve` → back to the suction line (`PipeTee`) | L5; DEXPI C01 has exactly this path | always for `ReciprocatingPump`, `RotaryPump` |
| 6.6 | **Minimum-flow bypass** | discharge `PipeTee` (after check, before block) → `RestrictionOrifice` → `GlobeCheckValve` → `GateValve` → suction vessel (recycle line) | L6 — KLM lists it; **no source states when it is required** | `p_min_flow` (0.3) |
| 6.7 | **Control-valve station** | `PipeTee` → `GateValve` → [`PipeReducer`] → CV body (`xV`) → [`PipeReducer`] → `GateValve` → `PipeTee`; bypass `PipeTee` → `GlobeValve` → `PipeTee`; [drain `GateValve` → `BlindFlange` between upstream block and CV] | L9 (HNF 3.2.4.2: "in general … block valves and a by-pass"; KLM block and bypass sizes); primer line already says so (`primer_pid_v1.txt`) | `p_cv_station` (0.8), `p_cv_reducers` (0.5), `p_cv_drain` (0.3) |
| 6.8 | **Bare control valve** | CV body inline, no blocks | L9 "in general" means not universal | 1 − `p_cv_station` |
| 6.9 | **On-off valve (XV)** | `BallValve` inline with AF + `ActuatingSystem(ControlledActuator(subTagName="XY-…"))`; [`ZSO`, `ZSC` PSGFs on the valve] | ISA X = on-off valve (composition note §4.2 [V]) | `p_limit_switches` (0.5) |
| 6.10 | **PSV on a vessel** | vessel top nozzle → [`GateValve` inlet block, car-sealed open] → `SpringLoadedGlobeSafetyValve` → [`GateValve` outlet block] → open end (FL service line toward the flare header — header parked) | L10 (block valves locked/car-sealed open; drain between block and PSV), L11 (on top outlet or directly on the vessel) | `p_psv_blocks` (0.5); `p_psv_drain` (0.3) |
| 6.11 | **Vessel drain and vent** | bottom nozzle → `GateValve` → `BlindFlange`; top nozzle → `GateValve` → `BlindFlange` | L13 — **sources conflict**: KLM "a valved drain for all columns and vessels", HNF "only when they connect to a closed system or are required" | `vent_drain_convention ∈ {klm_all, hnf_closed}` (`klm_all`); HNF = draw with p = 0.3 |
| 6.12 | **Vessel top instruments** | dedicated nozzle → `PI` (local); top outlet line tap → `TI` (local) | L13 (KLM: one local PI on top, one local TI on the top outlet line) | — |
| 6.13 | **Exchanger utility stub (supply)** | open start (dangling first `Pipe`, §3) → `GateValve` (block) → [`TI` tap] → utility inlet nozzle; service `CWS` / `LPS` / `MPS` | C4 (HNF: utility lines "originate and terminate adjacent to the equipment", origin "by descriptive title only"; KLM: end at a service box) | — |
| 6.14 | **Exchanger utility stub (return)** | utility outlet nozzle → [`TI` tap] → [`SpringLoadedGlobeSafetyValve` thermal relief, CW only] → `GateValve` → open end; steam service: `SteamTrap` before the block, service `CD` | L12 (cooler thermal relief on the CW return between cooler and block valve), L15 (steam-heated: PI on steam and condensate) | `p_thermal_relief` (1.0 for CW coolers, rule text says "all") |
| 6.15 | **Exchanger vents / drains** | shell and channel nozzles → `GateValve` → `BlindFlange` | L15 (KLM) | `p_exchanger_vent_drain` (0.5) |
| 6.16 | **Compressor suction / discharge** | suction: `ButterflyValve` (block) → `ConicalStrainer` → nozzle; discharge: nozzle → `CheckValve` → `GateValve`; `PSV` on discharge | L16 (KLM: suction and discharge valves, suction strainer, discharge check, safety valves) | — |
| 6.17 | **Battery limit** | at a unit's first inlet and last outlet: `GateValve` → `LineBlind` | composition note §9.2 (`LineBlind` exists; placement is our convention) | `p_battery_limit` (0.5) |
| 6.18 | **Flow measurement** | `FlowMeasuringElement` (or variant, §4.2) inline, `FT` located on it; straight-run not modelled | OPEN100 FE bubbles [P] | element weights per service |
| 6.19 | **Tank vent** | roof nozzle → `FlameArrestor` → `BreatherValve` → open end | composition note §9.2 | 1.0 for `Tank` |

Not encoded, on purpose: L7 warm-up bypass (trigger condition is in KLM 8.1.4, not read), L12's 1.5 × design-pressure
rule (needs design data, ADR-0021), L14 valve-on-nozzle (a drawing rule; the graph has no pipe nodes), C8 vendor
package boundary, auxiliary lube/seal-oil systems (HNF: separate auxiliary P&ID; parked with utilities).
## 7. Process-pattern library

**Grounding, stated once.** The *composition* of each pattern (which equipment belongs together on a drawing) is
grounded in FB&D slides 64–65 [V], the OPEN100 systems (`Notes/open100-rendszerkodok.md` [P]), the pyDEXPI
`column_pattern_1` (ProcessColumn 1, HeatExchanger 3, Tank 1, OperatedValve 7, PipeTee 2 [P]) and Hirtreiter et al.'s
sub-process patterns (thermal separation, reaction; control structures TC, LC, FC, FFC, PC [V]). The *trims* cite
§6. **The control schemes** (which variable is controlled by which valve) follow common textbook practice that
**no source read in this project codifies** — they are marked [U] and are design choices, one scheme per pattern
with at most one variant. Every pattern is a module function
`build_<pattern>(ctx: PatternContext) -> PatternInstance` with ports, drawing groups and a role per item.

**Ports.** Each pattern declares typed ports: `Port(name, direction, phase ∈ {L, G}, kind ∈ {process, recycle})`.
The flowsheet grammar (§8) wires ports; nothing else creates a cross-unit stream.

### 7.1 Building block: pump set (`build_pump_set`, used by U1–U8)

| Item | Content |
|---|---|
| Equipment | N identical pumps, N ∈ {2 (A/B), 3 (A/B/C)}, class from the service (centrifugal default; PD for dosing/viscous) |
| Streams | suction header from the suction vessel → `PipeTee` split → per pump: 6.1/6.2 → pump → 6.3 → `PipeTee` merge → discharge header |
| Trims | 6.1–6.6 per pump; 6.7 on the discharge header if the pattern controls flow there |
| Instruments | `PI` per pump discharge (L3); [`FT/FI` on header]; [motor running status is not drawn] |
| Spares | the A/B(/C) suffix on one tag number (`P-1203A/B`), identical class and trim (L8: installed spares are drawn) |
| Drawing group | **the suction vessel's group** (FB&D: "pumps — include with related equipment (suction)") |
| Parameters | `p_triple_pump_set` (0.15; OPEN100 has one A/B/C triple among 7 lettered groups [P]); `p_single_pump` (0.2, unspared service pumps) |

### 7.2 The unit-operation patterns

| Id | Pattern (system code) | Equipment (roles) | Ports | Loops and trips (scheme [U]) | Local / monitoring instruments | Safety and other trims | Drawing groups |
|---|---|---|---|---|---|---|---|
| **U1** | **Distillation column system** (`DST`) | `ProcessColumn` T; reboiler `TubularHeatExchanger` E (steam); condenser `TubularHeatExchanger` E (CW) or `AirCoolingSystem` EA; reflux drum `PressureVessel` D; reflux pump set; bottoms pump set; [feed preheater E] | in: feed (L); out: distillate (L), bottoms (L), [overhead vapour (G) when no condenser liquid] | column pressure PIC → CV on the drum vapour outlet; reflux FIC → FV (CV station); drum level LIC → distillate LV; bottoms level LIC → bottoms LV; tray temperature TIC → reboiler steam TV | PDT/PDI across the column; TT/TI on 2–4 trays; PI top and bottom; LG on drum and column sump; TI on each exchanger outlet; [AT/AI on distillate] | PSV on column top and on drum (6.10); drains/vents (6.11); utility stubs (6.13/6.14) with steam trap; [LSHH on drum → alarm only] | **G1:** column + reboiler + bottoms pumps; **G2:** condenser + drum + reflux pumps (FB&D: one column per P&ID; "reflux 1 (include with condenser)"). Variant `p_column_combined` (0.3): one group, as FB&D slide 65 "Column Systems (Combined)" |
| **U2** | **Compressor stage** (`CMP`) | suction KO drum `ScrubbingSeparator` V; [`GasFilter` F]; compressor `CentrifugalCompressor` or `ReciprocatingCompressor` K; aftercooler `AirCoolingSystem` EA or `TubularHeatExchanger` E; [discharge KO drum V] | in: gas (G); out: compressed gas (G); out: KO liquid (L, optional, else to a drain stub) | anti-surge: FT on suction → FIC → recycle FV from aftercooler outlet back to the KO drum inlet (**the recycle stream**); suction PIC → speed / inlet valve (modelled as PV on suction); KO drum LIC → LV on the liquid outlet; **trip**: LT → LSHH → XV on the compressor suction | PI/TI suction and discharge; ST/SI and VT/VAH on the machine; PDT/PDI across the filter | PSV on discharge (L16); suction strainer and block, discharge check and block (6.16); thermal relief on cooler CW return (6.14) | **G1:** KO drum + compressor + aftercooler (FB&D: "compressors 1 (complex)") |
| **U3** | **Heater–reactor–separator** (`RXN`) | feed/effluent exchanger E; fired heater `Furnace` H with `CentrifugalBlower` B [or `AxialFan`]; reactor `PressureVessel` R; effluent cooler `AirCoolingSystem` EA; separator `GravitationalSeparator` V; separator liquid pump set | in: feed (L); in: recycle gas (G, optional); out: separator liquid (L); out: separator gas (G) | heater outlet TIC → fuel-gas TV (fuel-gas stub 6.13 service FG); fuel-gas PIC; **trip**: BE → BSL → XV on fuel gas; reactor inlet TIC (bypass on feed/effluent exchanger); separator PIC → gas PV; separator LIC → liquid LV (`AngleValve` body, letdown, **spec break** → new line number); **trip**: PT → PSHH → XV on separator inlet | reactor TT/TI multi-point (3–5); reactor PDT/PDI; PI on heater outlet; TI on every exchanger outlet; LG on separator | `RuptureDisc` (+ PSV) on reactor; PSV on separator; drains/vents | **G1:** heater + blower; **G2:** feed/effluent exchanger + reactor; **G3:** cooler + separator + pumps (FB&D: "fired heaters 1") |
| **U4** | **Tank farm with transfer pumps** (`TKF`) | 2–4 `Tank` TK; transfer pump set (centrifugal or `RotaryPump`); [metering skid: `MassFlowMeasuringElement` or `PositiveDisplacementFlowMeter` FE] | in: 1–2 receipt lines (L); out: 1 transfer line (L) | per tank: inlet `HS → XV`; **overfill trip** LT → LSHH → XV on the inlet; transfer FIC → FV; metering FT → FQI | per tank: LT/LI, TI, [LSLL → alarm]; PI on pump discharge | tank vents 6.19; drains 6.11; [`PlugValve` manifold variant] | **G1, G2, …:** two tanks per group (FB&D: "tanks 1 to 2"); pumps join the group of the tank they draw from (the last tank group) |
| **U5** | **Exchanger train** (`HXT`) | 2–4 exchangers in series (`TubularHeatExchanger` / `PlateHeatExchanger`), [`ElectricHeater` EH trim heater last] | in: cold stream (L); out: heated stream (L) | outlet TIC → bypass TV around the last exchanger (bypass on a parallel `PipeTee` path); steam heater: TIC → steam TV | TI between every pair; PI inlet/outlet; [FT/FI on inlet] | utility stubs 6.13/6.14 per exchanger (steam trap on condensate, thermal relief on CW return); vents/drains 6.15; PSV on a blockable shell side (L12 cooler part) | **G1:** whole train if ≤ 4 exchangers; else split at the midpoint |
| **U6** | **Flash / separation drum** (`FLS`) | `PressureVessel` or `GravitationalSeparator` V; liquid pump set | in: feed (L/G); out: vapour (G), liquid (L) | PIC → vapour PV; LIC → liquid LV; **trip**: LT → LSHH → XV on the inlet; [LSLL → pump trip as alarm only] | PI, TI on top (6.12); LG; TI on inlet | PSV on top (6.10); drains/vents | **G1:** drum + pumps |
| **U7** | **Filter package** (`FIL`) | `LiquidFilter` F A/B in parallel (one running, one spare) | in: liquid (L); out: filtered (L) | none by default; [FIC on outlet] | PDT/PDI across each filter (or one across the pair); PI inlet/outlet | block valves on each filter inlet/outlet; drains/vents per filter | joins the **downstream** unit's first group if the unit is small (≤ 3 equipment), else its own group |
| **U8** | **Blending / mixing** (`BLD`) | `StaticMixer` M; [agitated vessel `PressureVessel` + `Agitator` M]; dosing pump set (`ReciprocatingPump`) | in: main (L), additive (L); out: blend (L) | **ratio**: FT (main), FT (additive) → FFIC → additive FV; AT → AIC (analyser trim on the ratio set point, modelled as a second PIF); vessel LIC → outlet LV | PI on dosing pump discharge; TI on blend; FE: `MassFlowMeasuringElement` on additive (Coriolis), `ElectromagneticFlowMeter` on main | PD-pump relief 6.5; PSV on vessel | **G1:** mixer + dosing pumps; **G2:** agitated vessel |
| **U9** | **Utility units** (`UTL`) — **default weight 0** | steam: `Boiler` / `SteamGenerator` + feed pumps; cooling water: `WetCoolingTower` + CW pumps; flare: KO drum + `Flare` | none to process units (headers parked) | standard level, pressure, flow loops | as above | as above | per FB&D | 

**What a pattern instance records** (gold, `GenerationRecordV2`): `pattern` and `variant` per unit; `role` per node
(`reflux_drum`, `bottoms_pump_spare`, `cv_station_bypass`, …); `drawing_group` per node; `stream_kind` per line
(§8); `item_kind` per tag (§11).

**Not a pattern (on purpose).** No process-specific chemistry; no packaged-unit boundary (C8); no lube-oil console;
no split-range loops (ADR-0044 "revisit if" clause needs a sourced rate); no cascade loops (one PIF per loop, which
the loop families rely on). Each is a later extension, not a hole in the claim.
## 8. Flowsheet grammar: how randomness is constrained

**Principle.** Randomness chooses *among meaningful options*; it never chooses an arbitrary pair to connect. v1's
random recursive tree, recycle and cross-link steps are replaced by a grammar over ports. This follows the
published precedent — Hirtreiter et al. join sub-process patterns by "a first-order Markov chain-like sampling
process with fixed probabilities" and need multi-outlet patterns to branch (`pid-structural-rules.md` §6.2) — with
our own patterns and ports.

### 8.1 The grammar (`benchmark/v2/flowsheet.py`)

```
Plant      := Train+                                  trains share tank farms: the product farm of train k
                                                      is the feed farm of train k+1 (intermediate tankage)
Train      := FeedFarm Conditioning{0..2} Core Separation{1..3} ProductFarm
FeedFarm   := U4                                      (the first train only; later trains reuse the previous ProductFarm)
Conditioning := U5 | U7 | U8                          weights: conditioning_weights
Core       := U3 [U2 on its gas outlet, recycled to U3's recycle-gas port]  | U6        weights: core_weights
Separation := U1 | U6                                 a column's bottoms feed the next Separation; its distillate
                                                      goes to the ProductFarm or to a later Separation
ProductFarm:= U4
```

- **Ports are typed; wiring is phase-compatible.** An out-port of phase L connects only to an in-port of phase L;
  gas outlets go to a U2 (compression) or, if none follows, to an **open gas stub** (service `FL` or `FG`, the
  header parked) — never to a liquid inlet.
- **Every stream is one of** (`StreamKindV2`, gold): `process` (port to port inside a train), `cross_unit`
  (between units), `recycle` (U2 → U3 recycle gas; U2 anti-surge; pump minimum-flow), `trim` (vents, drains,
  bypasses, taps, relief), `utility_stub`. v1's `tree` / `cross_link` kinds do not exist in v2.
- **Cross-links, made meaningful.** With `p_side_draw` (0.2) a column gets a side draw to a ProductFarm tank of the
  same or the next train; with `p_shared_farm_feed` (0.2) a train's Conditioning takes a second feed from an
  earlier train's ProductFarm. These are the only long-range extra edges; both exist in real plants (side
  products, blending from intermediate tanks) and both are [U] as to frequency.
- **Branching** comes from multi-outlet patterns (U1: distillate + bottoms; U3, U6: gas + liquid) — the
  mechanism the sample-pattern analysis showed is required (`pid-structural-rules.md` §6.1).

### 8.2 Randomness and determinism

| What is random | Drawn from | Example knob (all in `GeneratorConfigV2`, all declared parameters) |
|---|---|---|
| train count, train shape | master `random.Random(f"{seed}:flowsheet")` | `units_per_train_min/max` |
| pattern choice per slot | master | `conditioning_weights`, `core_weights`, `separation_count_weights` |
| pattern variant and sizes (tanks per farm, exchangers per train, A/B vs A/B/C, condenser type, combined column sheet) | **per-unit** `random.Random(f"{seed}:unit:{u}")` | per-pattern `variant_weights` |
| optional trims and instruments | per-unit stream, then per-trim calls in planning order | `TrimConvention`, `InstrumentDensity` |
| class choice among equivalent classes (valve body, flow element, PSV body) | per-unit stream | `class_weights` per role |

- **Prefix stability** (the size search needs it, as in v1): the master stream decides the unit sequence first; a
  unit's internals use only its own stream; wiring of unit `u` reads only units `< u` (a later unit takes the open
  out-ports of earlier ones). Hence the first `n` units of a larger plant have **identical internals and drawing
  groups** to the `n`-unit plant; only out-ports still open at unit `n` differ (open stub vs a stream to unit
  `n + 1`), which moves no sheet count (a test, §12).
- No `set` iteration, no global `random` (v1 invariants 3, 4 carried over); every DEXPI id explicit
  (`{plant_id}-u{u}-{kind}{seq}`, kinds `eq`, `va`, `ft`, `in`, `tp`).
- **Wiring never raises on a valid config**: an unmatched out-port becomes an open stub of its phase; an unmatched
  in-port takes the train's FeedFarm. Both counts are recorded in `GenerationRecordV2` and reported.
- **Plant size** is controlled by the number of trains and units; `HeadlinePresetV2` picks the smallest unit
  count whose **realized** sheet count (planned drawing groups merged by §9's rule) reaches the target, using a
  counting builder (no pyDEXPI), as v1's `smallest_n_units` does.
## 9. Sheet composition and splitter changes

**Who decides the sheets.** In practice the drafter "assigns which equipment goes on each drawing" (FB&D slide 63
[V]); no source gives an item count (`pid-structural-rules.md` S8). v2 therefore lets the **planner** assign every
node to a *sheet group* and the splitter only honours it. Three steps, all in `benchmark/v2/sheets.py`:

1. **Pattern drawing groups** (§7.2 last column): the pattern's own layout rule (one column per sheet, one fired
   heater, one complex compressor, 1–2 tanks, pumps with their suction vessel — FB&D slide 64 [V]).
2. **Rider rule**: every non-equipment node gets the group of the equipment its trim belongs to; a line's inline
   items get the group of the line's **source** item (v1's "owned by the source's unit", applied per group); a
   loop's PSGF, PIF and AF get the group of the item the PSGF is located on. The cut therefore falls where a real
   drawing cuts: at a nozzle, between trims, never inside a CV station.
3. **Merge to the sheet targets**: consecutive groups **of the same unit**, in flow order, are merged while
   equipment ≤ `max_equipment_per_sheet` and pre-split symbols ≤ `max_symbols_before_stubs`; a group below
   `min_equipment_per_sheet` is merged forward if the caps allow. The result is written as the gold node attribute
   **`sheet_group = "{u}:{k}"`**.

| Knob (in `GeneratorConfigV2.sheets`) | Default | Basis |
|---|---|---|
| `max_equipment_per_sheet` | 10 | the user's 3–10; OPEN100 lists 1–9 per drawing [P, incomplete] |
| `min_equipment_per_sheet` | 3 | the user's 3–10 |
| `max_symbols_before_stubs` | 100 | OPEN100 symbols mean + 1 sd = 82.3 + 26.3 = 108.6, minus OPEN100's mean 8.0 off-page stubs, ≈ 100 [C] arithmetic; **a declared cap** |

**Splitter.** One new strategy, `by_sheet_group` in `benchmark/strategies.py` (registered in `STRATEGIES`; the file
is at 322 lines, so the strategy goes into `benchmark/strategies_v2.py` and is imported into the registry):
- sheet = distinct `sheet_group`, sheets numbered in sorted `(u, k)` order (flow order by construction, S6/S7);
- raises `ValueError("by_sheet_group needs sheet_group on every node")` otherwise — it is a v2-only strategy;
- `sheet_equipment_budget` is ignored by it (documented), so `SplitConfig` gains **no field** (its JSON is part of
  every v1 `ingest.json`, §2);
- duplication, connector cutting, label detail, rejoin: unchanged code. `HeadlinePresetV2.split_config` passes
  `strategy="by_sheet_group"`, `equipment_classes=set(EQUIPMENT_CLASSES)` (the grown set, explicitly),
  `connector_label_detail=DRAWING_ONLY` (ADR-0023), `duplication_rate=0.25` (ADR-0028; open question Q4),
  `exact_match_tags=True`.
- `sheet_group`, like `stream_kind`, is **gold**: `localize` already keeps only `VISIBLE_NODE_PROPERTIES`
  (`resolution/localize.py:107`), and `resolution/contract.py` rejects anything else, so it cannot reach the store.

**Size search.** `smallest_n_units_v2(target_sheets, preset, seed)` plans with the counting builder and counts
distinct `sheet_group` values per unit prefix; the CLI asserts the realized sheet count as v1 does
(`check_realized_sheets`).

**Expected (not measured) composition.** The §12 report measures it; the design aims at OPEN100 §9.5 and does not
predict a number here.
## 10. Downstream impact per stage

"v1-safe" means: on a v1 plant, or on EX01, the output is byte-identical; each claim is guarded by a §2 golden or
an existing test.

| Stage | Must change | Must not change | Why v1 stays identical | Risk |
|---|---|---|---|---|
| **Schema** `graph/schema.py` | 49 classes, `piping_kind`, the constants of §4.5, endpoint sets, `UNTAGGED_CLASSES` += 4 fittings | `VISIBLE_*` sets; v1 classes' label chains and tag prefixes; `Relation` | constants only grow; `V1_*` pins feed every v1 code path | medium: any consumer that silently treated "piping" as "valve" (audit list below) |
| **Builder** `adapters/pydexpi_builder_v2.py` (new) | lines with tees, branches, open ends (open start = leading dangling `Pipe`), sensing on components, XV + solenoid `ControlledActuator`, PSV `positionNumber`, line-list fields | `pydexpi_builder.py` (v1) | separate file | medium: pyDEXPI toolkit edge cases (the open-start `IndexError` already found) |
| **Adapter** `adapters/pydexpi_adapter.py` | `map_conceptual_graph(..., vocabulary=V1_IMPORTABLE_CLASSES, piping_units=None, node_gold=None)`; with `piping_units` given (v2) every piping node takes the unit of its `PipingNetworkSystem.parentStructure`, read from the model via `collapsed_from` (§3); `_tag_of` falls back to `positionNumber` for safety valves; the helpers live in a new `adapters/pydexpi_units.py` (adapter is at 399 lines) | the default call path; `_assign_valve_units` | defaults reproduce today's call; EX01 import passes nothing new | low |
| **Proteus import** (EX01) | nothing | `topology_node_class` result for every EX01 class | the import path uses `V1_IMPORTABLE_CLASSES` | **high if missed**: growing `IMPORTABLE_CLASSES` without the pin would remap EX01's `SwingCheckValve`, `PipeTee`, `ReciprocatingPump`, … — the EX01 golden catches it |
| **Splitter** | `by_sheet_group` (new file); nothing else | `flow_greedy`, `by_unit`, duplication, connectors, `SplitConfig` fields | new strategy only | low |
| **Off-page connectors** | none in code; more cuts per sheet (target 8.0) | ADR-0027 signal labels, DRAWING_ONLY | — | medium: G1 at DRAWING_ONLY must hold with many parallel lines between two sheets of one unit — line numbers are now unique per line, which helps pairing |
| **Resolver / identity groups** | none | exact `(tag, node_class)` grouping | — | **EXP-0004 gets harder**: A/B spares share digits, so ADR-0031's blocking key `(node_class, digits)` puts `P-1203A` and `P-1203B` in one block; a naming variant that drops the suffix makes them indistinguishable. Realistic, but must be reported as a v2 condition |
| **Neo4j loader** | none (labels from `labels_for`) | profiles, plant layer | — | medium: ≈ 2–3× nodes per sheet (estimate from the targets, not measured) → H1000g2 load time; K-NEO (600 s) is re-checked by the scale smoke |
| **Cypher schema text** `qa/schema_text.py` | nothing for labels (taken from the plan) | the property list and both paragraphs (F1) | `VISIBLE_*` unchanged → identical text for v1 plans (golden) | medium: the paragraph says "equipment -measured_by-> transmitter"; on v2 a sensor may also be located on a line component. Under F1 the frozen text is used anyway (Q2) |
| **Legends, primer** `qa/prompts/*` | nothing under F1 | all files | — | same as above; the primer already describes CV stations and check valves, which v2 now draws |
| **Graph-tool agent** `qa/plant_api`, `qa/agent` | nothing | primitives, tool registry | generic over labels | low; more nodes per hop (tees, trims) → more steps per path, which is part of what is measured |
| **Question families** | (a) `families_loop._controllers_by_tag`: only PIFs with exactly one AF successor (actuated) / one PSGF predecessor located on **equipment** (measured equipment) — v2 has indicator-only, trip and HS loops; (b) `families_abstain.absent_tags`: also parse the v2 grammar via `tags.parse_tag`; (c) counts of "valves" use `VALVE_CLASSES` (now valves only), walks over piping use `PIPING_CLASSES` where they meant "any inline item" (`families_heldout_paths.py:215` counts valves — keep `VALVE_CLASSES`) | templates, wordings, reference functions, scoring (natural-question rule) | on v1 plants every PIF is a full loop on equipment → same candidate list; v1 tags match the v1 regex first | **high**: without (a) `single_successor` raises on the first indicator-only PIF and question generation crashes on v2 |
| **UPSTREAM_ISOLATION** | none in code | the walk | `OPERATED_VALVE_CLASSES` grows; v1 plants contain none of the new classes | semantic: in v2 the first operated valve upstream is usually a block valve, as an operator would close; a CV station's downstream block is met before the CV — realistic |
| **Demo drawing** `demo/drawing/families.py`, `glyphs.py` | `family_of`: new families `fitting`, `junction` (a dot), `primary_element`, `safety`; glyphs for them; instrument bubbles for PSGF-only local instruments | v1 glyphs | v1 classes keep their families | low; needed for the visual check (§12.3) |
| **Size search / CLI** | `ingest/headline_v2.py`, `--generator`, `--headline-v2`, dispatch | `HeadlinePreset`, `smallest_n_units` | separate | low |
| **Reports** (`plant_summary.py`, infra report) | `PlantSummary` is v1's; v2 gets `PlantSummaryV2` with per-kind counts | v1 summary | separate model | low |

**Audit list for "piping meant valve"** (coder task V2-T10 greps and decides each): `adapters/pydexpi_adapter.py`
(`_tag_of`, `_assign_valve_units`), `demo/drawing/families.py`, `qa/questions/families_abstain.py:47`,
`families_dev2_local.py`, `families_dev2_reach.py`, `families_heldout_paths.py`, `families_heldout_reach.py`.
## 11. Joint-project hook: machine-readable device kind

A separate joint project (outside this repository, read-only here) links P&ID tags to vendor datasheet graphs. The
generator holds **no** datasheet data (ADR-0021). What it must guarantee is that every device kind the joint
project knows appears on the drawings where a real plant would put it, with a kind that can be read off the drawing.

**The kind is `(node_class, ISA letters of the tag, mounting)`**, all visible, the way an engineer reads a P&ID:
`parse_tag(tag) -> ParsedTag(kind: Literal["equipment","instrument","valve","safety","fitting"], letters: str,
first: str, functions: str, unit: int, seq: int, train: str | None)` in `benchmark/v2/tags.py`, pure and
documented by the §5 grammar. As a convenience the generator also writes the **gold** map
`GenerationRecordV2.item_kind: dict[tag, ItemKind]` (`ItemKind` enum in `benchmark/v2/vocabulary.py`); the
joint project may read either. No new visible property is added, so nothing in the thesis pipeline changes for it.

| Device kind (joint project) | How it appears in v2 | Machine-readable as | Patterns |
|---|---|---|---|
| Sliding-stem globe **control valve** | `GlobeValve` body, tag `LV-` / `FV-` / `PV-` / `TV-…`, at the end of `xT → xIC → AF`, usually inside a CV station with block valves and a bypass | `node_class == GlobeValve` ∧ letters ∈ {LV, FV, PV, TV} ∧ has a `control` in-edge | U1–U8 |
| Pneumatic **actuator** of a control valve | the loop's AF (untagged, ADR-0044); in DEXPI an `ActuatingSystem` with `ControlledActuator` and `Positioner` | AF whose `control` target is a control-valve body | same |
| 2/2-way **solenoid valve** (on-off) | `BallValve` (or `GlobeValve` on 1–2 in lines) tagged `XV-…`, actuated by a trip or `HS`, DEXPI `ControlledActuator.subTagName = "XY-…"`; [`ZSO`/`ZSC`] | letters == XV; line size from the line number (`SIZE` field) | U2, U3, U4, U6 |
| **Centrifugal pump** (incl. self-priming, multistage) | `CentrifugalPump` `P-…A/B` in a pump set with suction strainer, discharge check + block + PI | `node_class == CentrifugalPump`; service from the unit and the role | all |
| **Pressure transmitter** | PSGF `PT-…` (and `PDT-…`) on a line tap (C01 structure) or on a vessel nozzle, feeding a PIC / PI / PSHH | letters ∈ {PT, PDT} | all |
| **Coriolis flow meter** | `MassFlowMeasuringElement` `FE-…` inline with `FT-…` located on it | `node_class == MassFlowMeasuringElement` ∧ FT sensing it | U4, U8 |

The A/B suffix and the shared number tell the joint project which tags are installed spares of one service.
## 12. Validation plan

Three layers: composition statistics against OPEN100, structural invariants as tests, and a visual check.

### 12.1 Composition report (`benchmark/v2/composition.py`, CLI `python -m plantgraph.benchmark.v2.composition`)

Computed on the **sheet graphs** (after the split, before localize), per sheet, then mean / sd / min / max, at
D100g2 and D1000g2 (seeds 1) and two further seeds at ~100 sheets. **Counting rule**, fixed before the first run so
it cannot be tuned: *symbol* = equipment + valves + fittings except `PipeTee` + primary elements + PSGF + PIF +
off-page stubs; `PipeTee` is a junction (PID2Graph counts junctions as `connector`, excluded from its 82.3
symbols), AF is drawn as part of its valve.

**Acceptance bands.** OPEN100 is **one nuclear plant** (one design, one drafter, 12 sheets); the bands are therefore
**declared design criteria built on that single plant**, not a calibration claim. The band is OPEN100's observed
range for per-sheet values and roughly ± one OPEN100 sd for the mean.

| Statistic | OPEN100 (composition note §9.5) | v2 acceptance band |
|---|---|---|
| Symbols per sheet, mean | 82.3 ± 26.3 [C] | 56–109 |
| Symbols per sheet, every sheet | 40–134 [C] | ≥ 95 % of sheets inside 40–134 |
| Valves per sheet, mean | 21.4 (9–35) [C] | 15–28 |
| Instruments (PSGF + PIF) per sheet, mean | 29.2 (9–49) [C] | 20–38 |
| Instruments : valves | 1.36 [C] | 1.0–1.8 |
| Off-page stubs per sheet, mean | 8.0 (2–12) [C] | 5–11; every sheet ≤ 16 |
| Equipment per sheet | 1–9 per drawing [P, incomplete]; user 3–10 | ≥ 90 % of sheets in 3–10, none above 10 |
| Instruments with sheet-graph degree 1 | 242 / 350 = 69 % [C] | ≥ 55 % |
| Equipment in A/B(/C) groups | 15 / 43 ≈ 35 % [P] + arithmetic | 25–45 % |
| Units drawn on ≥ 2 sheets | 4 of 9 drawing numbers [P] | 25–65 % of units |
| Every sheet shows one unit (ADR-0025 rule) | — | 100 % |
| Distinct equipment / piping / instrument-template kinds on D1000g2 | pyDEXPI 99 / 55; ISA 176 symbols | ≥ 21 / ≥ 28 / ≥ 18 |

If a band fails, the response is a **parameter change with a recorded reason** (one sweep row per change in the run
note), never a silent edit; a failure that needs a structural change goes back to the architect.

### 12.2 Structural invariants (tests; each one names its rule)

| # | Invariant | Rule |
|---|---|---|
| S1 | Every centrifugal pump: suction path vessel → block → strainer → pump | L2 |
| S2 | Every pump: discharge path pump → (tap) → check → block; the PI tap is before the check | L1, L3 |
| S3 | Every PD pump has a relief path from discharge (before the check) to suction | L5 |
| S4 | Every AF `control` target is a control-valve body whose tag is the loop's `xV` and shares the loop number | ADR-0044, L17 |
| S5 | Every CV station: two block valves and a bypass valve between the same two tees | L9 |
| S6 | Every `PressureVessel`, `ProcessColumn`, `GravitationalSeparator`, `ScrubbingSeparator` has ≥ 1 safety device reachable over `send_to` from it without passing equipment | L11 |
| S7 | Every XV has a solenoid `ControlledActuator` (`XY-…`) in the model and is driven by a trip PIF or an `HS` | §4.4 |
| S8 | Every loop: one PSGF → one PIF → [one AF → one valve]; members share `u SEQ3` | L17, L18 |
| S9 | Every tag is unique, parses with `parse_tag`, and its letters agree with its class (`PT` is a PSGF, `P-` is a pump, …) | L17, C11 |
| S10 | Every line number parses, is unique per `PipingNetworkSystem`, and changes at every spec change | C3, L20 |
| S11 | A/B(/C) members: same class, same role, same unit, parallel between the same split and merge tees | L8 |
| S12 | Gas out-ports never wire to liquid in-ports; no pump discharges to its own suction except via 6.5/6.6 | §8 |
| S13 | Plant weakly connected; zero nodes dropped in `ConversionReport`; `validate_plant_graph == []`; every sheet `validate_sheet_graph == []` | v1 invariants 1, 2, 12 |
| S14 | Same seed ⇒ identical pyDEXPI JSON bytes under `PYTHONHASHSEED` 1, 2, 3; global `random` untouched; no uuid ids | v1 invariants 3, 4, 9, 10 |
| S15 | Prefix stability of unit internals and sheet groups (§8.2) | size search |
| S16 | Every sheet shows one unit; G1 true at DRAWING_ONLY; identity P = R = 1.0 at exact tags | ADR-0025, ADR-0027, ADR-0028 gates |
| S17 | All §2 v1 goldens unchanged | §2 |

### 12.3 Visual check

Export with the demo drawing exporter (`python -m plantgraph.demo.drawing`) one sheet of every pattern and variant
(≈ 15 sheets) from D100g2. Checklist for the reader (the user, and if available one practising P&ID engineer):
pump trims in L1–L3 order; CV stations with bypass; PSV on every vessel; instruments as bubbles on lines, not
inline; loop numbers shared; line numbers readable; A/B spares side by side; one column / heater / compressor per
sheet; off-page flags at sheet edges. Findings go into the run note; a "looks wrong" with a rule reference becomes a
task, a taste remark does not.

## 13. Re-measurement plan

**What stays valid.** All v1 results (§2). v2 results are **added** beside them, never replace them.

**Order of runs** (each a main-session run note under `30-experiments/`):

| # | Run | Paid? | What it answers |
|---|---|---|---|
| R0 | `scale_smoke` on v2 at ~100 and ~1,000 sheets: seed → `DiGraph`, split, resolve, Neo4j load times and peak memory | free | v2 is feasible on this machine (plant-generator.md kill criterion: 10 min seed → `DiGraph`; K-NEO 600 s) |
| R1 | Composition report (§12.1) and gates (S16) on D100g2, D1000g2 | free | v2 is realistic by the declared bands |
| R2 | Question availability (ADR-0029 per-bin gate) and `k` distribution on D100g2, D1000g2 | free | the families still cover the `k` bins |
| R3 | Prompt-size dry run: ContextRAG serialized chars per sheet on the v2 ladder sizes (no API call) | free | what ContextRAG will cost and where it stops fitting (the wall moves to fewer sheets if a sheet holds more) |
| R4 | **EXP-0001-style ladder on v2**: H1g2, H3g2, H10g2, H30g2 — ContextRAG at high effort vs the frozen `cascade_v3` and its tiers (ADR-0054 protocol, same question count per size) | **paid** | does the single-sheet end of the claim reproduce on realistic sheets? |
| R5 | **EXP-0002-style sealed test on v2**: H100g2, H1000g2 (fresh seeds), `cascade_v3` only, 20 questions per family, F1 freeze (ADR-0053 protocol) | **paid** | does the plant-scale end reproduce? |
| R6 | EXP-0004 resolver on v2 variant copies (H100g2-V), exact + free deciders only | free | the A/B-spare effect on identity resolution |

**F1 applies.** R4 and R5 run the frozen system (code, prompts, pins, policies of EXP-0002) on v2 data, so a change
is attributable to the data alone. A v2-aware prompt (legend sentence on line-mounted sensors) would be a new
system and is only run if R4/R5 show failures traced to that sentence (open question Q2).

**Cost estimate method** (no figure is given until R3 has run):
- tiers: `cost = n_questions × c_q`, with `c_q` the measured per-question cost of the tier on the matching v1
  corpus (EXP-0002: ≈ $0.0004–0.0007 per question for the Luna tiers, ADR-0054 context), corrected by
  `t_v2 / t_v1`, the ratio of mean tokens per question on a 10-question staged pilot on D100g2 vs the same 10
  families on D100 (more nodes per hop means longer tool outputs for the agent tier);
- ContextRAG: `tokens = Σ_questions (sheets × chars_per_sheet_v2) / chars_per_token`, with `chars_per_sheet_v2`
  from R3, `chars_per_token` from the PROMPT-04 measurement, and the OpenRouter price listing of the run day, price
  step at 272,000 prompt tokens included (ADR-0054 context);
- every paid run is **estimated, capped and staged** (the project's budget rule), with the cap written into the
  run config before the first call.
## 14. Staged implementation plan (coder tasks)

One Sonnet `coder` at a time (ADR-0006). Sizes are **estimates** (S < M < L; coder pace is unmeasured). Every task
ends with: full suite green (2,048 tests today, plus its own), the §2 v1 goldens unchanged, `ruff` and `mypy
--strict` clean, files under ~400 lines, functions small, ≤ 2 nesting levels, no stacked loops
(`.claude/agents/coder.md`). The user commits each task; the coder prints the command and message.

**New files** (all under `src/plantgraph/`): `benchmark/v2/{__init__,config,vocabulary,tags,plan_models,trims,
instruments,ports,flowsheet,sheets,planner,composition}.py`, `benchmark/v2/patterns/{__init__,pump_set,storage,
separation,column,heat,compression,reaction,blending}.py`, `benchmark/strategies_v2.py`,
`benchmark/generator_dispatch.py`, `adapters/pydexpi_builder_v2.py`, `adapters/pydexpi_builder_v2_lines.py`,
`adapters/pydexpi_units.py`, `graph/schema_classes.py`, `ingest/headline_v2.py`; tests in
`tests/v2/` and `tests/graph_plant_builder_v2.py`.

| # | Task | Files touched | Tests to add | Acceptance check | Size |
|---|---|---|---|---|---|
| **V2-T0** | **Freeze v1.** Record goldens at HEAD; add `V1_EQUIPMENT_CLASSES`, `V1_VALVE_CLASSES`, `V1_OPERATED_VALVE_CLASSES`, `V1_IMPORTABLE_CLASSES` (today's values); point `generator.py`, `GeneratorConfig.equipment_weights`, `SplitConfig.equipment_classes`, `topology_node_class` default at them | `graph/schema.py`, `benchmark/generator.py`, `benchmark/generator_models.py`, `benchmark/split_models.py`, `adapters/pydexpi_adapter.py` | `tests/test_v1_goldens.py`: DEXPI JSON sha256 (seeds 0–2, headline 5 u), `run_synthetic` config bytes, schema text (both profiles), EX01 import digest | goldens recorded **before** the code edit and equal after it | S |
| **V2-T1** | **Schema vocabulary.** 49 classes, `piping_kind`, constants of §4.5, endpoints, untagged fittings; split into `schema_classes.py` | `graph/schema.py`, `graph/schema_classes.py`, `graph/validation.py` (uses `PIPING_CLASSES` for `send_to`) | every new class exists in pyDEXPI and its label chain is a prefix of pyDEXPI's ancestry cut at a schema root; label regex; `VALVE_CLASSES ∩ {PipeTee,…} = ∅`; v1 class specs unchanged | goldens unchanged (EX01 especially) | M |
| **V2-T2** | **Tag grammar and vocabulary tables** (pure, no pyDEXPI) | `benchmark/v2/tags.py`, `benchmark/v2/vocabulary.py` | round trip `parse(format(x)) == x` for every production; injectivity over 10⁴ random fields; overflow raises; every tag matches the anchor token regex; `ItemKind` from `(class, letters)` | — | S |
| **V2-T3** | **Config, plan models, builder protocol, graph oracle** | `benchmark/v2/config.py`, `benchmark/v2/plan_models.py`, `tests/graph_plant_builder_v2.py` | config validation (weights > 0, keys ⊆ classes, min ≤ max); plan models frozen; oracle builds a hand-written two-unit plan | `GeneratorConfig` JSON unchanged (golden) | M |
| **V2-T4** | **DEXPI builder v2 + adapter hooks.** Lines with tees, branches, open start (leading dangling `Pipe`) and open end; sensing on nozzle / primary element / tap / valve; loops, trips, `HS`, XV with solenoid `ControlledActuator`; PSV `positionNumber`; line-list fields; `map_conceptual_graph(vocabulary, piping_units, node_gold)`; `_tag_of` safety fallback | `adapters/pydexpi_builder_v2.py`, `adapters/pydexpi_builder_v2_lines.py`, `adapters/pydexpi_units.py`, `adapters/pydexpi_adapter.py` (signature only) | one micro model per construct through `plant_graph`: zero dropped nodes, expected edges (the §3 table as assertions); oracle ≡ DEXPI path on node and edge properties; JSON round trip; determinism under `PYTHONHASHSEED` 1–3; linear loader ≡ stock loader (v1 invariant 11) on a v2 micro plant | every §3 behaviour reproduced in a test | **L** |
| **V2-T5** | **Trims** 6.1–6.19 | `benchmark/v2/trims.py` | one test per trim: planned sequence and the rule invariant (S1–S7, S10 parts) | — | M |
| **V2-T6** | **Instruments**: templates of §4.4, conventions I-1/I-2, density knobs, loop numbering | `benchmark/v2/instruments.py` | S8, S9; every template yields the expected class chain and letters; loop members share a number | — | M |
| **V2-T7** | **Patterns A**: pump set, U4 tank farm, U6 flash drum, U7 filter package | `benchmark/v2/patterns/{pump_set,storage,separation}.py`, `ports.py` | per pattern: ports, roles, drawing groups, S1–S3, S6, S11 | — | M |
| **V2-T8** | **Flowsheet grammar, planner, sheet groups** (with only the T7 patterns available) | `benchmark/v2/{flowsheet,planner,sheets}.py` | S12, S13 on the oracle, S14, S15; wiring never raises on 50 random configs; merge rule respects caps | first v2 plant generated end to end on the oracle | **L** |
| **V2-T9** | **Dispatch, preset, size search, CLI** | `benchmark/generator_dispatch.py`, `ingest/headline_v2.py`, `ingest/pipeline.py`, `ingest/__main__.py`, `qa/corpus.py`, `qa/models.py` | v1 `ingest.json` rebuild unchanged; v2 `ingest.json` round trip; realized sheets = predicted | `ingest synthetic --headline-v2 --target-sheets 10 --no-neo4j` runs | S |
| **V2-T10** | **Splitter strategy and downstream fixes**: `by_sheet_group`; loop-family filter; abstain v2 grammar; the piping-vs-valve audit (§10) | `benchmark/strategies_v2.py`, `benchmark/strategies.py` (registry line), `qa/questions/families_loop.py`, `families_abstain.py`, audited files | S16 on a small v2 corpus; every family generates without error on v2; v1 question sets byte-identical (sealed-set and per-family goldens) | **milestone: first v2 corpus through ingest, resolve, questions** → main session runs R0, R1 on it | M |
| **V2-T11** | **Patterns B**: U1 column system (both variants), U5 exchanger train, utility stubs | `benchmark/v2/patterns/{column,heat}.py` | per pattern as T7; S4–S6; utility stubs only on utility nozzles | — | M |
| **V2-T12** | **Patterns C**: U2 compressor stage (anti-surge recycle), U3 heater–reactor–separator, U8 blending (ratio) | `benchmark/v2/patterns/{compression,reaction,blending}.py` | per pattern; S7; recycle stream kind recorded | — | M |
| **V2-T13** | **Composition report** and the full invariant suite over every pattern and variant | `benchmark/v2/composition.py`, `tests/v2/test_invariants.py` | report numbers on a fixture equal hand counts; S1–S17 on 5 seeds | CLI prints the §12.1 table | M |
| **V2-T14** | **Demo drawing families and glyphs** for fittings, junctions, primary elements, safety devices, PSGF-only bubbles | `demo/drawing/{families,glyphs}.py` | every v2 class has a family; a v2 sheet exports to PDF; v1 exports unchanged (existing demo tests) | §12.3 visual check possible | S |

After T13 the main session runs R1–R3 (free), files the composition run note, and brings the paid R4/R5 estimates
to the user.
## 15. Risks

| Risk | Likelihood / impact | Mitigation | Kill or revisit criterion |
|---|---|---|---|
| A v1 artefact changes by accident (shared constants, EX01 mapping, schema text, `ingest.json` bytes) | medium / **high** — frozen results would no longer be reproducible | V2-T0 goldens recorded first; v1 code reads `V1_*` pins only | any golden diff blocks the task |
| pyDEXPI toolkit edge cases (open start raised `IndexError`; merge tees, nested branches not exercised at scale) | medium / medium | micro-model tests per construct in V2-T4; the leading-dangling-`Pipe` workaround is measured | if a construct cannot be built within V2-T4, drop it (e.g. supply stubs) and say so in the note |
| Scale: ≈ 2–3× nodes per sheet (estimate) and many more DEXPI objects per unit | medium / medium | R0 scale smoke before any paid run | plant-generator.md kill criterion (10 min seed → `DiGraph` at the largest size) and K-NEO 600 s |
| Bands fail and tuning becomes curve-fitting to one plant | medium / medium | counting rule fixed before the first run; every parameter change logged with a reason; bands are declared criteria, not targets to hit exactly | more than 3 tuning rounds → stop and report the gap instead |
| Question families crash or change meaning on v2 (indicator-only PIFs, line-mounted loops, tag grammar) | **high** without T10 / high | T10 fixes (a)–(c) of §10; v1 question goldens | any family with zero candidates on D100g2 is reported, not hidden |
| F1 prompts describe v1 shapes ("equipment -measured_by-> transmitter") | medium / low–medium | run frozen first (R4/R5); a v2 legend only as a labelled new system (Q2) | — |
| EXP-0004 gets harder with A/B spares (same digits) | certain / medium | report as a v2 condition; blocking pair completeness is measured (ADR-0031) | blocking completeness < 0.99 → ADR-0031's own revisit rule |
| Realism is still one plant's drafting (OPEN100) plus codified rules; control schemes are [U] | certain / medium for the thesis argument | stated in the note, ADR-0057 and the thesis limitations; no per-class frequency is claimed | a second real multi-sheet set appears → re-derive the bands |
| Effort larger than estimated | medium / medium | staged: the T10 milestone already yields a v2 corpus (liquid handling: tank farms, drums, filters, pumps) that can be measured | — |
| Temperature taps use `BlindFlange` as a thermowell stand-in | certain / low | documented convention; class weights let a later version switch | a DEXPI thermowell class in a later pyDEXPI |

## 16. Open questions for the user

Only decisions with a real alternative; each has a recommendation.

1. **Utilities.** v2 draws the *consumer side* of utilities (cooling water, steam, fuel gas, flare lines as short
   lines with a block valve and a service code, ending at the sheet's edge without a header) — the codified
   practice (HNF, KLM: consumers stay on the unit sheet with a service-labelled stub). Headers and utility sheets
   stay parked. *Alternative:* draw no utility lines at all (less realistic, fewer valves). **Recommendation:
   consumer stubs yes, headers still parked.**
2. **Prompts on v2 runs.** *A:* run the frozen system (F1: same code, prompts, models) on v2 corpora, so any change
   is caused by the data. *B:* first amend the legend/schema text for line-mounted sensors, then run. **Recommendation:
   A**; B only if A's failures trace to that sentence, and then as a separately labelled system.
3. **Role of v2 in the thesis.** *A:* v1 stays the headline (it is measured and sealed), v2 is a robustness
   replication ("the inversion also holds on realistic plants"). *B:* v2 becomes the headline and v1 the
   development set. **Recommendation: A** — it keeps every frozen number valid and makes v2 an external-validity
   test rather than a re-run.
4. **Duplication rate on v2.** *A:* keep ADR-0028's 0.25 (comparable with v1). *B:* lower it (you said real
   duplication is probably rarer). **Recommendation: A** for R4/R5, with the 0 and 0.5 sensitivity points only if
   R5's result differs from v1.
5. **Which paid runs.** *A:* both R4 (single-sheet ladder) and R5 (sealed plant-scale test) on v2. *B:* R5 only.
   **Recommendation: A**, each estimated, capped and staged after the free R3 dry run gives the prompt sizes.
