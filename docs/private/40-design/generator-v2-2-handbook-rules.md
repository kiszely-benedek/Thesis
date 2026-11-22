---
component: benchmark/generator v2.2 — handbook rule registry, plant-level correctness layer, valve positions, untagged manual valves, network and interarea sheets; EXP-0009 re-measurement plan
status: draft — awaiting review (ADR-0066 proposed)
date: 2026-11-22
related: [ADR-0066 (proposed), ADR-0016, ADR-0021, ADR-0027, ADR-0029, ADR-0053, ADR-0057, ADR-0058, ADR-0059, ADR-0060, ADR-0065,
          10-literature/toghraei-2019-vs-generator.md, 10-literature/api-rp-14c-2001-vs-generator.md,
          10-literature/liptak-2003-vol1-vs-generator.md, 10-literature/liptak-1995-process-control-vs-generator.md,
          40-design/generator-v2-realism.md, 40-design/generator-v2-pid-vocabulary.md, 40-design/review-fixes.md,
          30-experiments/EXP-0008-v2-rerun.md]
---

# Design — generator v2.2: handbook rules, checked on every plant

## 0. Recommendation

Build **generator v2.2** beside v2.1, opt-in by config type, with v2.1 pinned by golden digests before any line
changes. v2.2 does four things:

1. **A rule registry.** Each encoded rule has an id that names the book and page, a paraphrased statement, its
   sources, any conflict and the choice made, its declared parameters, a code comment at the place that applies it,
   and a check function. The design encodes **55 rules**: 36 local rules and 19 plant-level checks (§4). It records
   **14 groups of rules that were read but deferred**, each with a reason.
2. **A plant-level correctness layer** (§2, §6) on top of the local rules. It checks stream closure, an ordinal
   **pressure-level model** kept as hidden generator state, control structure, protection presence-or-exception
   (API RP 14C), and network closure. **Every v2.2 plant is verified when it is built.** A violation refuses the
   build, and every corpus carries a `rules.json` report beside its `ingest.json`. That is what makes "checked on
   every generated plant" literally true, not only true for test seeds.
3. **The new content the user chose** (scope b, 2026-11-22):
   - valve positions: NO/NC/CSO and fail actions;
   - tagged or untagged manual valves, per train;
   - network and interarea sheets reached through network off-page connectors;
   - the verified fixes;
   - the cheap gaps.
   No new node class is added. Everything stays inside the 77-class allowlist (ADR-0016).
4. **EXP-0009 measures v2.2 with the frozen system V2T-A2 (freeze E9)** as a pure data replication. It runs free
   gates first, then the paid stage P1: one validation pair, five sealed plants per scale and the scorer audit. P1 is
   estimated at **$11.46** from EXP-0008's measured spend, under a hard ledger cap of **$16.50**, so it fits the
   $17 credit the user has now. The ladder and the identity arm (P2) wait for a top-up (§12).

What this buys the thesis claim: if the scale result (Q4) holds on plants whose rules are cited and checked, then
the examiner's "toy topology" objection is answered with a stronger generator. Nothing in the retrieval system
changes, so any difference against EXP-0008 comes from the data.

## 1. Inputs and what is already decided

- **Comparisons read:** the four rule-by-rule comparisons in `10-literature/` (Toghraei 2019, API RP 14C 2001,
  Liptak IEH Vol. 1 2003, Liptak IEH Process Control 1995).
- **Pages checked:** I re-checked every page cited below against the PDFs (§16). Liptak 1995 is an image scan with
  no text layer. None of its claims could be re-checked, so it is used only as secondary support or for deferred
  items, and is cited by section.
- **Generator v2.1 code:** `src/plantgraph/benchmark/v2/`. Its existing invariants are S1–S24 in `tests/v2/`
  (`plant_invariants*.py`, `instrument_invariants.py`, `machine_checks.py`), run on seeds 1–5 at about 30 sheets.
- **User decisions, 2026-11-22 (not re-opened):**
  - scope (b);
  - every rule gets an id, a code comment and a test on every generated plant;
  - rules that need data we do not model become declared parameters;
  - sampling among the alternatives the sources give;
  - the conflict rule "the later source wins unless stated", with the recorded case: a reciprocating pump gets no
    external check valve (Toghraei 2019 over API 14C 2001);
  - the thesis claim: "derived from published practitioner handbooks, cited per rule, checked by tests on every
    generated plant". It is not "tested on real diagrams".

## 2. The central question: do correct rules guarantee a correct plant?

**No, and the design does not pretend they do.** A local rule constrains a neighbourhood: a pump and its trims, a
control-valve station, a PSV and its pipe. Rules that are all satisfied locally can still compose into a plant that
is wrong as a whole:

- **Composition across boundaries.** Two patterns that are each correct are joined by the flowsheet. If one ends in
  an LV and the next begins with an FV on the same liquid line, two control valves fight each other (Toghraei p.271).
  Neither pattern sees the other.
- **Global state that no local rule holds.** Whether a stream may flow from A to B depends on pressure. Whether a
  vessel needs a PSV depends on what can feed it. Whether a level is controlled once depends on every loop around the
  vessel. A local rule cannot see any of these.
- **Omission.** A rule that was never encoded is never violated. The four books contain far more than we encode.
- **Frequency.** Every weight is declared, because no per-class frequency is published
  (`generator-v2-realism.md` §0). A plant can be correct and still be statistically unlike real plants.
- **Physics we do not model.** We model no chemistry, mass or energy balance, sizing, set pressures or temperatures
  (ADR-0021).

**What closes the gap as far as it can be closed without datasheet data** (§6):

| Layer | Guarantees on every built plant | Does not guarantee |
|---|---|---|
| L1 local rules (36) | no encoded local pattern is violated; every sampled alternative is one a book names | anything across trims |
| L2 plant-level checks (19) | flow closure, phase compatibility, closed recycles; a consistent ordinal pressure order with movers, letdowns, check valves, spec breaks and PSD need; control structure (each inventory controlled once, ≤ 1 CV in series on a liquid line, FE before FV, every pump's flow controlled); protection present or excepted per API 14C; network closure | the real pressures, the hp, whether the chemistry makes sense |
| L3 external checks | composition inside the OPEN100 bands (process sheets); a reported comparison with the 34 example sheets of Toghraei ch.20; an optional expert review sample | that the plants match any real plant |
| Not covered | process chemistry, mass and energy balance, sizing, set points, real frequencies, rules deferred or never read, company style beyond the sampled alternatives, drawing layout | — |

**The claim the thesis can make**, then:

> v2.2's rules are derived from published practitioner handbooks, cited per rule, and checked by tests on every
> generated plant. In addition, every plant is checked for plant-level consistency of flow, ordinal pressure,
> control and protection structure.

The thesis must also state the encoded and deferred counts, and must not say "realistic" without the composition
bands.

## 3. The rule registry

### 3.1 Types (`src/plantgraph/benchmark/v2/rules/registry.py`)

```python
BookId = Literal["TOG2019", "API14C2001", "LIP2003V1", "LIP1995PC", "DESIGN"]

class SourceRef(BaseModel):          # frozen
    book: BookId
    locator: str                     # "p.271", "§4.2.3 p.14", "§1.1 PDF p.76", "§8.23 (section only)"
    page_checked: bool               # True only if the page was read against the PDF (§16)

class ConflictNote(BaseModel):
    other: SourceRef
    choice: str                      # what v2.2 does
    basis: Literal["later_source", "stated"]

class RuleKind(str, Enum): PLACE = "place"; FORBID = "forbid"; ALTERNATIVE = "alternative"; PLANT = "plant"
class RuleStatus(str, Enum): ENCODED = "encoded"; DEFERRED = "deferred"

class HandbookRule(BaseModel):
    rule_id: str                     # ^[A-Z0-9]+(-[A-Z0-9.]+)+$, e.g. "TOG271-ONE-CV-LIQUID"
    title: str
    statement: str                   # paraphrase, never a quote
    sources: tuple[SourceRef, ...]   # at least one
    conflict: ConflictNote | None
    kind: RuleKind
    status: RuleStatus
    since: Literal["v2.1", "v2.2"]   # v2.1 = already true, now cited and tested
    sampling_unit: Literal["train", "item"] | None   # ALTERNATIVE only
    declared_parameters: tuple[str, ...]             # config paths, e.g. "handbook.pump_power_weights"
    exception_codes: tuple[str, ...]                 # the only allowed reasons for absence
    check: str | None                # dotted path of the check; None iff DEFERRED
    deferral_reason: str | None
```

- **Id format:** book plus page (or §), then a slug: `TOG192-RECIP-NO-CHECK`, `API14C-3.4-TWO-LEVELS`,
  `LIP1-1.1-SHARED-LOOP-NUMBER`.
- **Rules a design choice derives:** plant-level rules derived from several sources use `PLT-` or `PRS-` and list
  those sources; `DESIGN` is allowed only for these.

### 3.2 Code comments

One line at the place that applies the rule:

```python
# rule TOG192-RECIP-NO-CHECK: no external check valve on a reciprocating pump (Toghraei 2019 p.192)
```

A registry test scans `src/plantgraph/benchmark/v2/**/*.py` for `# rule <ID>`:
- every id must exist in the registry;
- every ENCODED rule must appear at least once;
- the comment's page must equal a `SourceRef.locator` of that rule.

### 3.3 Checks, tests and build-time verification

```python
class Violation(BaseModel): rule_id: str; node_id: str; detail: str
class CheckResult(BaseModel): checked: int; violations: tuple[Violation, ...]; exceptions: dict[str, int]
Check = Callable[[RuleView], CheckResult]

class RuleView:  # rules/view.py — built from GeneratedPlantV2, no test helper needed
    plan: PlantPlanV2; graph: nx.DiGraph[str]; roles: dict[str, str]; hidden: HiddenDesignState

def verify_plant(generated: GeneratedPlantV2) -> RuleReport            # rules/verify.py
class RuleRow(BaseModel): rule_id: str; checked: int; violations: int; exceptions: dict[str, int]
class RuleReport(BaseModel): generator_version: str; rows: tuple[RuleRow, ...]   # written as <corpus>/rules.json
```

- **On every plant.** `generate_plant_v2` calls `verify_plant` for every v2.2 config and raises
  `RuleViolationError` on any violation. `ingest synthetic` writes `rules.json`.
  - Every plant of EXP-0009 is therefore verified, the 1,000-sheet sealed plants included.
  - Run time is a measured quantity of the first coder task on a 1,000-sheet dev plant. EXP-0008 measured
    generation at 390.99 s on H1000g21p1 (`EXP-0008-v2-rerun.md`, infrastructure table).
- **Tests per encoded rule:**
  - (a) a positive test, parametrised over seeds 1–5 at about 30 sheets, that asserts 0 violations;
  - (b) a mutation test that breaks the plant on purpose and asserts the check fails;
  - (c) a non-vacuity test over the five seeds, asserting `checked > 0`. Each sampled alternative must also be
    drawn at least once.
  - Patterns (a) and (b) follow `test_s6_fails_on_a_plant_whose_safety_valves_were_removed`; pattern (c) follows
    `test_across_the_five_seeds_every_rule_found_something_to_check`.
- **The existing checks move into the package.** `check_s1` … `check_s24` move from `tests/v2/*.py` into
  `src/plantgraph/benchmark/v2/rules/checks_v21.py`. The tests import them from there, unchanged, so
  generation-time verification can run them.
  - S1–S3, S6 and S12 become registry rules with book sources.
  - The rest stay model invariants (`DESIGN`, not counted as handbook rules).
- **Version-scoped checks.** A v2.1 invariant that v2.2 deliberately changes keeps its v2.1 meaning on v2.1 plants.
  Example: S2 "gauge tap, check, block on every discharge" is false for reciprocating pumps in v2.2.

### 3.4 Size

- **Rules:** 55 encoded (36 local, 19 plant-level) and 14 deferred groups.
- **Tests:** 55 positive tests (275 parametrised cases over 5 seeds), 55 mutation tests, the non-vacuity tests and
  4 registry tests (ids unique and well-formed, every encoded rule has a check and a comment, comments resolve, the
  registry is printed into the thesis appendix table by a CLI).
- **Unknown yet:** the API 14C SAC items (PRT rules) are transcribed in T10. Their per-item count is known only
  after that.

## 4. Rule catalogue (v2.2)

Legend:
- **Status** (behaviour in v2.1): `ok` = already true, now cited and tested; `fix` = a verified violation;
  `new` = new behaviour; `check` = a plant check whose outcome on v2.1 is unknown until it runs (a failure becomes a
  fix designed then).
- **Page checks:** every page in this table was checked (§16) unless it says "section".

### 4.1 Identification

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG28-SPARE-NAMING | Installed spares are tagged P-125A/B, or as unrelated numbers P-125/P-126; one convention per train | TOG p.28; LIP1 §1.1 PDF p.76 (A/B suffix on spares' instruments) | ok: already drawn per train, suffix : consecutive = 3 : 2 (`vocabulary.py` `SPARE_NAMING_WEIGHTS`) | cite, test | ALT, train |
| TOG113-MANUAL-VALVE-TAGS | Within a train, either every manual valve carries a tag or none does; automatic valves, safety valves and instruments are always tagged | TOG p.113 | every manual valve tagged | new | ALT, train |
| TOG73-UNTAGGED-BRANCH-PIPES | No line number on a short pipe to a plugged or blinded vent or drain valve, nor on a control-valve bypass pipe | TOG p.73 (Table 6.3) | branches numbered (`trim_plan.py`) | fix | FORBID |
| LIP1-1.1-SHARED-LOOP-NUMBER | All members of a loop share its number | LIP1 §1.1 PDF p.76 | ok (S4, S8) | cite, test | PLACE |
| TOG113-AUTOMATIC-VALVE-LETTERS | A control valve is the loop's xV; a switching valve is XV/UV; a hand control valve is HCV | TOG p.113 (Table 7.9) | ok (S4, S7) | cite, test | PLACE |

### 4.2 Valve positions (new attribute, §8)

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG114-BLOCK-DEFAULT-NO | A blocking valve is normally open unless marked otherwise | TOG p.114 | none | new | PLACE |
| TOG114-VENT-DRAIN-NC | Vent and drain valves are normally closed | TOG p.114 | none | new | PLACE |
| TOG120-CV-BYPASS-NC | The bypass valve of a control-valve station is closed in normal operation | TOG p.120 | none | new | PLACE |
| TOG224-PSV-BLOCKS-CSO | Manual valves under and over a PSV are full port and car-sealed open | TOG p.224 (Table 12.8, Fig. 12.9) | none (design text only) | new | PLACE |
| TOG114-FAIL-ACTION | Every automatic valve has a fail action (FO/FC/FL); a min-flow control valve fails open | TOG p.114–115 | none | new; the mapping by service is a declared table | PLACE |
| TOG34-BL-ISOLATION | A battery-limit crossing has a blind; or an isolation valve and a blind; or an isolation valve, a blind and a check valve | TOG p.34 | valve + blind at p 0.5 | add the check variant | ALT, item |

### 4.3 Pumps

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG192-RECIP-NO-CHECK | Centrifugal and rotary pump discharges have a check valve; reciprocating pumps have none (internal check) | TOG p.84, p.192 (Fig. 10.31), p.193 (Fig. 10.32). **Conflict:** API 14C A.7.2.2.2 p.40 and SAC A-7.2 g p.44 ("all pumps"). Basis: later source | check on every pump (`trims.py` `pump_discharge`) | fix | FORBID |
| TOG192-PD-NO-MINFLOW | No min-flow line on reciprocating or rotary pumps | TOG p.192, p.193 | drawn at p 0.3 for any class | fix | FORBID |
| TOG177-MINFLOW-TAKEOFF | A min-flow line leaves upstream of the check valve or downstream of the isolation valve, never between them | TOG p.177 | between them (`trims.py` `pump_discharge`) | fix (upstream of the check) | PLACE |
| TOG177-MINFLOW-NEED | Centrifugal pumps that run continuously on the main stream, are above 5 hp, or sit on level control get a spillback; a pump with its own flow loop or a VSD does not | TOG p.177 | a coin at p 0.3 | fix; driven by the hidden power band (§6.2) | PLACE |
| TOG313-MINFLOW-METHOD | Below 5 hp none; 5–20 hp a restriction-orifice line; 20–35 hp an on-off switching valve on an FT; above 35 hp FT → FIC → FV | TOG p.313, p.179 | RO only | new; the band is sampled, the method follows | ALT, item |
| TOG219-PD-RELIEF | A PD pump discharge has a relief path (a blocked outlet has no maximum pressure) | TOG p.219, p.192 | ok (S3) | cite, test | PLACE |
| TOG314-PD-NO-THROTTLE | No flow control valve throttles a PD pump's discharge in series; capacity comes from a VSD or stroke, or from a recirculation line with a CV | TOG p.314 | dosing ratio FV when no VFD (`blending_parts.py`); rotary transfer FIC → FV (`storage_parts.py`) | fix | FORBID |
| TOG270-PUMP-FLOW-CONTROLLED | Each pump set's flow is controlled exactly once: its own flow loop, a VSD, or a level loop's valve on its discharge | TOG p.270 | not checked | check | PLANT |
| TOG175-PUMP-TRIM | Centrifugal pump: suction block and strainer; discharge gauge, check, block | TOG p.175, p.84 | ok (S1, S2; S2 version-scoped) | cite, test | PLACE |
| TOG173-PUMP-REDUCERS | A centrifugal pump may have a reducer on its suction and an enlarger on its discharge | TOG p.173–175 | none | new (`PipeReducer`) | ALT, item |

### 4.4 Compressors

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG319-ANTISURGE-DYNAMIC | Anti-surge recycle only on dynamic (centrifugal) compressors, not on PD gas movers | TOG p.319 | on every class (`compression.py` line 117) | fix | FORBID |
| TOG316-PD-COMP-CAPACITY | A PD compressor's capacity comes from a spillback line with a capacity loop, or a VSD; never discharge throttling | TOG p.316 (Table 15.10), p.317 | the anti-surge shape | fix: the spillback stays, its loop becomes PT → PIC → PV | PLACE |
| API14C-A8-FSV | A check valve on the compressor's final discharge | API 14C A.8.3.2 p.45; TOG p.84 | ok (L16) | cite, test | PLACE |
| API14C-A8-PSV | A PSV on the compressor discharge | API 14C A.8.2.2.1 p.45 | ok | cite, test | PLACE |

### 4.5 Exchangers and fired heaters

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG207-HX-NO-ISOLATION | No isolation valves and no bypass around an exchanger unless it has a spare or a cleaning system | TOG p.207 | ok (`patterns/exchanger.py`) | cite, test | FORBID |
| TOG320-HX-NONTARGET | The temperature controller moves the non-target stream: directly on a utility, by a bypass on a process stream | TOG p.320–321 | not checked | check | PLANT |
| TOG322-HX-BYPASS-VARIANT | A bypass TV alone, or control valves on both the main and the bypass branch | TOG p.322 | bypass alone | new | ALT, item |
| TOG326-STEAM-CONDENSATE | Steam heater condensate: trap, trap station, or a condensate pot with level control | TOG p.326–327 | ok (`CondensateMode`, 2 : 1 : 1) | cite, test | ALT, item |
| TOG214-FUEL-SWITCHING-VALVES | One switching valve, or two in series, on the fuel line | TOG p.214 ("in some designs") | one XV | new; each valve gets its own actuator and number | ALT, item |

### 4.6 Control structure

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG271-ONE-CV-LIQUID | At most one control valve in series on a liquid-filled line between two containers; a flooded vessel counts as pipe | TOG p.271 | not checked | check | PLANT |
| TOG267-FE-UPSTREAM-FV | A flow element sits upstream of the FV of its loop | TOG p.267 | not checked | check | PLANT |
| TOG295-INVENTORY-ONCE | A non-flooded liquid container has exactly one level loop; a gas container exactly one pressure loop; a flooded container none. Exception codes: `storage_tank_batch`, `pressure_floating_on:<id>` | TOG p.295 (Table 15.1), p.270 (rule 8) | not checked | check | PLANT |
| TOG309-SPLIT-PAIRING | At a drum split, flow control goes on the smaller stream and level control on the other | TOG p.309 | fixed: reflux FIC, distillate LV | new; the hidden reflux class decides | ALT, item |
| TOG122-PV-NO-BYPASS | Some companies give pressure-control valve stations no bypass | TOG p.122 | always a bypass | new | ALT, train |

### 4.7 Protection

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG224-PSV-PIPE-CLEAN | No check valve and no control valve between an enclosure and its PSV | TOG p.224 (Table 12.8) | not checked | check | PLANT |
| TOG219-VESSEL-PSV | Every pressure vessel reaches a PSV (fire case), except the declared condensate pot | TOG p.219; API 14C A.4.2.2.1 p.26 | ok (S6) | cite, test | PLACE |
| TOG207-HX-PSD-BOTH-SIDES | Each exchanger enclosure has a pressure safety device, or a pressure-model exception | TOG p.207 | partial | new | PLANT |
| TOG236-TANK-EMERGENCY-VENT | An atmospheric tank has a normal breather and an emergency vent | TOG p.236; LIP1 §7.7 PDF p.968 | breather only | new | PLACE |
| API14C-3.4-TWO-LEVELS | A pressure vessel has two independent levels of protection (PSV plus a sensor trip), or a SAC exception | API 14C §3.4 b p.7 | partial | new (with T10) | PLANT |
| API14C-SAC | Per component (A.4 pressure vessel, A.5 atmospheric vessel, A.6 fired, A.7 pump, A.8 compressor, A.10 exchanger), each SAC device is present or carries an SAC omission code | API 14C App. A; pages per item in T10 | partial | new; items without a derivable exception are DEFERRED one by one | PLANT |

### 4.8 Networks, streams and pressure

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG32-NETWORK-SHEETS | Relief, closed-drain and utility lines continue on network P&IDs (mainly pipes), reached through off-page connectors | TOG p.32–34 | open ends | new (§7) | PLACE |
| TOG141-DRAIN-DESTINATION | Hydrocarbon (non-innocent) drains are hard-piped to the closed drain; water (innocent) drains go to an open drain | TOG p.141 | capped, or a funnel by a coin | fix (by fluid class) | PLACE |
| TOG360-UTILITY-NETWORKS | Every utility has a distribution network; steam, cooling water and similar have a collection network | TOG p.360 (Fig. 17.1) | consumer stubs end open | new | PLACE |
| TOG33-INTERAREA | Lines between areas (trains) run over an interarea P&ID with straight pipes | TOG p.33 | direct process-to-process connectors | new | PLACE |
| TOG24-NO-VISITING-STREAM | Every line on a sheet connects to an item on that sheet | TOG p.24 | not checked | check | PLANT |
| PLT-NETWORK-CLOSURE | Every network connector has a partner; every header ends at a declared end | from TOG p.32–34 | — | new | PLANT |
| PLT-STREAM-CLOSURE | Every line has a source and a sink item, or a declared end (battery limit, network end, vent to atmosphere, capped maintenance drain) | from TOG p.24 | not checked | check | PLANT |
| PLT-PHASE | A gas port never meets a liquid port (S12) | DESIGN (S12) | ok | cite, test | PLANT |
| PLT-RECYCLE-CLOSURE | A recycle returns inside its unit, from a higher to a lower pressure level, through a reducing element (RO, CV) | TOG p.317 (spillback discharge → suction) | not checked | check | PLANT |
| PRS-MONOTONE | Along the flow the pressure level never rises except across a pump, compressor or ejector | DESIGN (§6.2) | — | new | PLANT |
| TOG82-SPEC-BREAK | A spec break where a CV or RO lowers the level, or a pump or compressor raises it | TOG p.82 (Table 6.5) | compressor discharge and letdown only | extend to pumps | PLANT |
| PRS-SPEC-CLASS | The heavier pipe class is on the higher-level side of a break | DESIGN (follows ADR-0065 F8c) | ok at breaks | check | PLANT |
| TOG156-MERGE-CHECK | A low-pressure or intermittent stream tying into another has a check valve | TOG p.156 | not checked | check | PLANT |
| API14C-A4-OVERPRESSURE | An enclosure fed from a higher level, or by a PD mover, has a PSD; otherwise exception `source_cannot_exceed` comes from the pressure model | API 14C A.4.2.2.1 a p.26 | partial | new | PLANT |

**Count:** §4.1 5, §4.2 6, §4.3 10, §4.4 4, §4.5 5, §4.6 5, §4.7 6, §4.8 14, which makes **55 rules**. The 19
plant-level rules are those of kind PLANT.

### 4.9 Read but deferred (status DEFERRED, in the registry with a reason)

| Group | Sources | Why deferred |
|---|---|---|
| Functional-only identification for local gauges (no loop number) | LIP1 §1.1 PDF p.56 | gauges would share tags like `PI`; this breaks S9 and identity by tag in the frozen resolver |
| Parallel loop numbering | LIP1 §1.1 PDF p.58 | FIC-101 and LIC-101 would share a loop number, which collides with the ADR-0027 signal-connector key |
| Gaps in tag sequences | LIP1 §1.1 PDF p.58, p.76 | no effect on what the thesis measures |
| API "S" device letters (PSH/LSH meaning "safety") | API 14C §2 (section) | the same letters mean different things in ISA; the frozen primer (ADR-0041) explains ISA |
| Trip by a solenoid on the control valve | LIP1995 §8.19 (section, not re-verified) | one valve with two drivers breaks S7 and LOOP_ACTUATED_VALVE |
| Min-flow by a PCV kickback or an FSL pump trip | LIP1995 §8.23 (section, not re-verified) | page not verifiable; the FSL trip is a new motor-trip shape |
| 3-way exchanger valve | TOG p.322 | needs a new class (ADR-0016) |
| Pulsation dampener; back-pressure regulator on dosing pumps; self-acting regulators | TOG p.192, p.195 | no fitting class for a dampener; a one-member regulator loop breaks S8 |
| Tank blanketing and VRU | TOG ch.9, ch.15 (note, not re-verified) | needs split-range PCVs and a VRU network; for later |
| Double block and bleed; blinds at pump isolation valves | TOG ch.8, p.175 (note) | changes isolation answers; low value |
| Fired heater passes, pilot gas line, snuffing steam | TOG p.213–215 | new heater pattern variant; large |
| Compressor PSH/PSL/TSH/BDV, vessel LSL and the other SAC devices without a derivable exception | API 14C SAC A-4.2, A-8.2 (T10) | each becomes a DEFERRED SAC row, unless the device is cheap and inside the composition bands |
| Shut-in at the primary source | API 14C §4.2.3 p.14 | needs trip → motor interlock edges across sheets, which S19/S20 forbid; v2.2 reports the share of trips that act at the source |
| Interlock-diamond drawing style; multi-stage compressors; lube-oil and seal systems | TOG ch.16, ch.10 (note) | drawing style, or detail P&IDs |

## 5. Sampled alternatives and their sampling unit

**Principle.**
- **Identification conventions** are a company standard, so they are drawn **per train**. A train is "one design
  contractor's area" (`TrainRecord`, `vocabulary.TrainConventions`), and the existing `on_off_letter` and
  `spare_naming` already set the precedent.
- **Engineering arrangements** are a choice per item, so they are drawn **per item**.
- **Coupled choices come from one hidden cause.** Where a choice has a cause the books name (hp, reflux ratio), the
  generator samples the **hidden cause** and derives the visible consequence. Independent coins for coupled features
  are avoided.

| Alternative | Unit | Driver (declared) | Included |
|---|---|---|---|
| Spare naming: suffix or consecutive | train | weights 3 : 2 (unchanged from v2.1) | yes (exists) |
| Manual valves tagged or untagged | train | `p_untagged_manual_train` = 0.5 | yes |
| Pressure-control stations without a bypass | train | `p_pv_no_bypass_train` = 0.5 | yes |
| Min-flow method | pump set | hidden power band, weights `<5 : 5–20 : 20–35 : >35` = 1 : 1 : 1 : 1 | yes |
| Battery-limit isolation, 3 variants | item | 1 : 1 : 1 | yes |
| Pump nozzle reducers | pump set | `p_pump_reducers` = 0.5 | yes |
| Exchanger bypass: TV alone, or two CVs | item | 1 : 1 | yes |
| Steam heater condensate mode | item | 2 : 1 : 1 (unchanged) | yes (exists) |
| Fuel switching valves: one, or two in series | furnace | 1 : 1 | yes |
| Accumulator split pairing | column | hidden reflux class low : high = 1 : 1 | yes |
| The deferred list of §4.9 | — | — | no |

- **The weights are neutral declared values.** No source gives a frequency (the same stance as
  `generator-v2-pid-vocabulary.md` §13.1).
- **Two changes of declared weight are not made.**
  - Toghraei p.28 calls consecutive spare numbering "the current trend". Flipping 3 : 2 to 2 : 3 would be a
    frequency claim the book does not quantify.
  - The untagged share stays 1 : 1 for the same reason.

**Randomness rule.** v2.2 never removes or reorders a v2.1 draw:
- where a rule replaces a coin (for example `p_min_flow`), the draw is still taken and its value ignored;
- every new draw comes from a new named stream (`f"{seed}:train{t}:handbook"`, `f"{seed}:unit{u}:handbook"`).

This keeps the v2.1 code path byte-identical by construction (§9). A v2.2 plant also shares the flowsheet and the
units of the v2.1 plant with the same seed, so a free, descriptive v2.1 → v2.2 diff can be made on the same seeds
(§12.2).

## 6. The plant-level correctness layer

### 6.1 Hidden design state (`src/plantgraph/benchmark/v2/hidden_state.py`)

```python
class PressureLevel(IntEnum): VAC = 0; ATM = 1; LP = 2; MP = 3; HP = 4      # ordinal, no values
class PumpPowerBand(str, Enum): BELOW_5 = "<5"; B5_20 = "5-20"; B20_35 = "20-35"; ABOVE_35 = ">35"   # hp, TOG p.313, p.179
class RefluxClass(str, Enum): LOW = "low"; HIGH = "high"                     # L/D, TOG p.309
class FluidClass(str, Enum): HYDROCARBON = "hydrocarbon"; WATER = "water"; STEAM = "steam"; INERT = "inert"

class HiddenDesignState(BaseModel):
    segment_level: dict[str, PressureLevel]        # piping segment id -> level
    pump_power: dict[str, PumpPowerBand]           # pump set id -> band
    reflux: dict[str, RefluxClass]                 # column id -> class
    fluid_of_service: dict[str, FluidClass]        # line service code -> class (declared table)
    exceptions: dict[str, dict[str, str]]          # rule id -> item id -> exception code
```

- **Where it lives.** The state lives in `GenerationRecordV22`. It is read by the checks and summarised (as counts)
  in `rules.json`.
- **Where it never goes.** It is never written to the DEXPI model, the graph the store loads, the drawing export, a
  prompt or a question's gold.
- **ADR-0021.** This is not equipment or datasheet data in ADR-0021's sense: no value, no unit, nothing shown,
  nothing asked. ADR-0066 records this as a clarification of ADR-0021, not a supersession (decision D3 confirms it).
- **Fluid classes.** The plant is declared a hydrocarbon plant. Process services are HYDROCARBON, CWS/CWR are
  WATER, LPS/MPS/CD are STEAM, N2 is INERT. That is the only basis for drain and relief destinations.

### 6.2 Pressure-level assignment and checks (PRS-*, TOG82, TOG156, API14C-A4)

**Assignment.** It follows the flowsheet order, from the train's own stream:
- farms and open drains are ATM;
- a pump or compressor discharge is its suction level plus a draw of 1 or 2 (capped at HP);
- an ejector raises VAC to ATM;
- a CV or RO keeps or lowers the level, and a letdown into a lower vessel lowers it;
- exchangers, filters, mixers and pipes keep it.

**Exchangers.** An exchanger is one node in the graph (pyDEXPI abstraction, `generator-v2-realism.md` §3), so the
model keys levels on **segments and service families**, not on nodes. The utility side and the process side of one
exchanger have their own levels.

**Utility network levels** (declared): CWS LP, CWR ATM, LPS LP, MPS MP, CD ATM, FG LP, FL ATM, CHD ATM.

**Checks:**

| Check | What it asserts |
|---|---|
| PRS-MONOTONE | for every `send_to` edge u → v, level(v) ≤ level(u) unless u is a mover's suction side and v its discharge side |
| TOG82-SPEC-BREAK | every segment boundary with a level change has a `PropertyBreak` (pump discharges included, new in v2.2) |
| PRS-SPEC-CLASS | across a break, the spec class on the higher side is the heavier one (ADR-0065 F8c ordering) |
| TOG156-MERGE-CHECK | at a merge tee, if the incoming levels differ, the lower branch carries a check valve before the tee |
| PLT-RECYCLE-CLOSURE | every RECYCLE line goes from a higher to a lower level and holds an RO or a CV |
| API14C-A4-OVERPRESSURE | every enclosure whose feeding level, over any path without an intervening PSD, exceeds its own, or that a PD mover feeds, reaches a PSD; otherwise its exception code is `source_cannot_exceed` |

**Visible effect.** None, except where the books say it shows: spec breaks and pipe classes are already visible line
number fields. So the model makes visible data *consistent* without adding visible data.

### 6.3 Control structure (TOG271, TOG267, TOG295, TOG270, TOG320)

- **Liquid line between two containers.** This is the maximal `send_to` route between two non-flooded containers.
  It may pass pipes, flooded items (exchangers, filters, mixers) and pumps; branches in parallel are separate routes.
- **What counts as a control valve.** A throttling valve driven by a loop, or an HCV. On-off XV/UV switching valves
  are blocking valves and do not count (TOG p.113, Table 7.9).
- **TOG267.** There is a `send_to` path from the FE to its FV, and none from the FV back to the FE except through a
  recycle. This covers the min-flow FIC (FE on the discharge, FV on the spillback) and the anti-surge loop (FE on the
  suction).
- **TOG295.** The exception codes are written by the pattern that builds the container. Tank-farm tanks are
  `storage_tank_batch` (Toghraei p.305 says flow to storage is often not controlled; that page is from the note,
  marked unverified in the registry, so the exception cites p.295 only). A drum that floats on a controlled
  neighbour with no valve between gets `pressure_floating_on:<id>`.
- **No full degrees-of-freedom analysis.** The checks stop at "each inventory controlled once, no stream
  manipulated twice in series, every pump's flow controlled". The thesis says so.

### 6.4 Protection (API14C-3.4, API14C-SAC, TOG207, TOG236, TOG224)

- **T10 transcription first.** The SAC tables A-4.2, A-5.2, A-6.2 (fired), A-7.2, A-8.2 and A-10.2 are transcribed
  before any coder encodes them, by the researcher agent, with each page checked against the API text layer. The
  output is `rules/sac.py`: per component kind, the device letters, the location, and the omission conditions as
  exception codes.
- **Allowed exceptions.** An exception code is allowed only if it is one of API's own omission conditions and is
  derived from the hidden state (pressure model, fluid class), never drawn by a coin.
- **Example: the reciprocating pump check valve.** SAC A-7.2 g lists a check valve for all pumps, while v2.2 omits it
  on reciprocating pumps. The SAC check records that as exception `conflict:TOG192-RECIP-NO-CHECK`, so the conflict
  is visible in every `rules.json`.
- **Devices without a derivable exception.** If the generator does not draw such a device, the SAC item is DEFERRED,
  not silently passed.
  - Cheap additions are made where the instruments-per-sheet band allows it. EXP-0008 measured 31.8–32.4 against the
    20–38 band (`bands/composition_sealed*.json`).
  - TOG207 adds a PSD on each exchanger side that can be blocked in and fed from a higher level.
  - TOG236 adds the emergency vent on tanks (a `SpringLoadedGlobeSafetyValve` tagged PSV, a class already in the allowlist).

### 6.5 Network closure (PLT-NETWORK-CLOSURE)

- Every process-side network connector pairs with exactly one connector on a network or interarea sheet. Pairing is
  by drawing number and connector number, as today, so the resolver is unchanged.
- Every header ends at a declared end: a battery limit toward utility generation, or toward the flare/closed-drain
  treatment, which are out of scope.
- The free resolution gate requires pair precision = recall = 1.0 at exact tags, the same G1 check every corpus
  already runs.

### 6.6 External checks (report, not proof)

| Check | What | Gate? |
|---|---|---|
| Composition bands (ADR-0059) | judged on **process sheets**; network and interarea sheets reported apart. A network sheet has no equipment by design (TOG ch.20 shows such sheets), so "equipment per sheet ≥ 1" would fail on it | yes: U4-style stop |
| Toghraei ch.20 comparison | the 34 example sheets (TOG p.417–452) annotated by hand: equipment per sheet, off-page connectors by target kind (process / network / utility / signal), share of sheets without equipment, into `10-literature/toghraei-2019-ch20-sheet-counts.md`; v2.2 values per sheet kind beside them | no: textbook examples are single-item illustrations, not a sample of plants |
| Expert review | a fixed sample of 12 dev-plant sheets (one per pattern U1–U8, one network, one interarea, one pump set, one furnace), drawn with the demo export, reviewed against a checklist printed from the registry, plus "anything that looks wrong"; each finding becomes a rule, a fix or a recorded limitation | no; only if a reviewer is available (D7) |
| Rule report | per rule: instances checked, 0 violations, exceptions by code; the encoded / deferred counts | yes (build refuses on a violation) |

## 7. Network and interarea sheets

**Which networks** (D4, recommended set):
- relief/flare `FL`;
- closed drain `CHD`;
- cooling water `CWS`/`CWR`;
- steam `LPS`, `MPS` and condensate `CD`;
- fuel gas `FG`;
- the interarea sheets between trains.

Blanket gas and VRU are deferred (§4.9).

**Structure:**
- **Network unit.** Each (train, service) has a network unit. Its unit number comes from a reserved block,
  `9000 + 10·train + service index`, so it cannot collide with a process unit number below 9000 (H1000g21p1 has 608
  units). It holds one header made of `PipeTee`s.
- **Per-sheet sub-header.** On a process sheet, all tie-ins of one service merge into one local sub-header that
  leaves the sheet through **one** network connector. This is the usual "PSV outlets join the unit flare sub-header",
  and it bounds the added off-page stubs per process sheet by the number of services on that sheet.
  - EXP-0008 measured a mean of 5.93–6.10 stubs per sheet and a maximum of 16–17, against the bands 5–11 and ≤ 21
    (`bands/composition_sealed*.json`).
  - The free gate measures v2.2.
- **Network sheet capacity.** At most `max_tie_ins_per_network_sheet` = 16 (declared, under the stub band's maximum
  of 21). Overflow continues on the next network sheet through a header continuation connector.
- **Root valves.** Distribution tie-ins get a root block valve on the network sheet (NO; tagged by the train's
  manual-valve convention). Collection tie-ins get none.
- **Interarea.** A line from train t's product farm to train t+1's feed farm passes one interarea sheet. On it there
  are a straight pipe, the battery-limit isolation of TOG34, and two connectors. Each such line gains one sheet
  crossing (k + 1).

**Counting and prefix stability.**
- Network and interarea sheets count toward the 100 / 1,000-sheet targets, because they are sheets of the set
  (D4). Their share is reported.
- S15 ("the first n units of a bigger plant are the n-unit plant") is **restated for v2.2**: process units and their
  sheets stay prefix-stable, while network sheets are a function of the included units. `smallest_n_units_v2`
  searches on total sheets, which stays monotone in n.

**Store.** Network units are ordinary units (ADR-0026 unit nodes). No resolver, schema text or Cypher change.

## 8. Valve positions and untagged manual valves

**Positions in the plan.**
- `LineItemSpec.operating_position: OperatingPosition | None` with values `NO | NC | LO | LC | CSO | CSC`. It is set
  for every blocking valve by TOG114/TOG120/TOG224; LO/LC are allowed by the type but not drawn in v2.2.
- `ActuatorSpec.fail_action: FailAction` with values `FO | FC | FL`, set by a declared service table:
  - min-flow FV and anti-surge FV: FO;
  - fuel TV and XV: FC;
  - cooling-water TV: FO;
  - steam TV: FC;
  - anything else: FC.
  Only the min-flow row has a checked source (TOG p.115). The other rows are declared and marked so in the registry.

**Positions in DEXPI.**
- Fail action uses the native `ControlledActuator.failAction` (`FailActionClassification`: fail close, fail open,
  fail retain position). I checked that it exists in pyDEXPI 1.2.0 (`pydantic_classes.py`).
- The normal position has no native attribute, so it is a `CustomStringAttribute` named `OperatingPosition` on the
  `PipingComponent`, which is a `CustomAttributeOwner`. Custom attributes are not custom classes, so S24 holds.
- The adapter drops both before the store, under D1 = A (§10).

**Untagged manual valves.**
- In a train drawn "untagged", `format_valve_tag` is not called for manual valve roles. The node has no `tag`, like
  a `PipeTee` today.
- Check valves follow the manual convention. PSVs, rupture discs, control and switching valves, and instruments keep
  their tags (TOG p.113).
- Untagged valves are never duplicated across sheets: ADR-0028 duplication is equipment-only.

## 9. Versioning (v2.1 stays byte-reproducible)

| Option | How | Cost | Verdict |
|---|---|---|---|
| **V-A fork** | copy `benchmark/v2/` to `benchmark/v2_1/` frozen, develop v2.2 in place | about 9,100 lines duplicated (measured `wc -l`), two code bases to read | no |
| **V-B gated in place** | new config type, new draws from new streams, every v2.2 behaviour behind `handbook` knobs that are off for v2.1; v2.1 goldens recorded first | discipline, enforced by goldens | **recommended** |
| **V-C checkout only** | as was done for `v2` (refused by name; rebuild from `E8.commit`) | none now; but the demo (H1000g21p1) and every EXP-0008 corpus would need a checkout to rebuild | no: v2.1 is the measured headline and the demo's data |

**V-B mechanism.**

1. **T0 first: pins and goldens.** Record at HEAD, before any change:
   - sha256 of the pyDEXPI JSON bytes and of `record.model_dump_json()` for seeds 1–5 at the 30-sheet size of the
     invariant tests;
   - the same for the stored configs of `H1g21`, `H3g21`, `H10g21` and `D100g21` (`data/runs/exp0008/corpora/*/ingest.json`);
   - the question-set hash of the H1g21 ladder set.

   The audit of shared constants that v2.1 iterates over in a random draw (the v1 precedent,
   `generator-v2-realism.md` §2) pins any that v2.2 would grow as `V21_*` (for example `LINE_SERVICES` gains
   `CHD`).
2. **Config.** `GeneratorConfigV22(BaseModel)` with `generator_version: Literal["v2.2"]`, all v2.1 knob groups plus
   `handbook: HandbookKnobs` (every weight of §5, `max_tie_ins_per_network_sheet`, the fail-action table, the
   network service set). `GeneratorConfigV2` is **unchanged**, so a v2.1 config's JSON stays byte-identical.
3. **Dispatch.** `generator_dispatch._version_of` returns `"v1" | "v2.1" | "v2.2"`; `AnyGeneratorConfig` gets a
   third tag; `generate_plant_graph_any` checks `GeneratorConfigV22` first. `ingest synthetic --generator v2.2`,
   `HeadlinePresetV22`.
4. **Corpus ids.**
   - dev `D100g22`, `D1000g22`;
   - validation `VAL100g22`, `VAL1000g22`;
   - sealed `H100g22p1..p5`, `H1000g22p1..p5`;
   - ladder `H1g22`, `H3g22`, `H10g22`, `H30g22`;
   - identity arm `H1000g22pkV`.

   Fresh test seeds are drawn by the `draw_seeds` tool (F12). The EXP-0008 test seeds are retired.
5. **Every coder task** keeps the full suite green and the v1 and v2.1 goldens unchanged. A failing golden means the
   change is wrong, never the constant.

## 10. Impact on the frozen system (V2T-A2, freeze E9)

| Component | What v2.2 touches | Under D1 = A (recommended) |
|---|---|---|
| Schema text (`qa/schema_text.py`, built from `graph.schema.VISIBLE_NODE_PROPERTIES`) | a visible `operating_position` would change the text of **every** corpus, v1's goldens included | not added; positions stay out of the store |
| Resolver (identity by tag; ADR-0027 connector key) | untagged valves cannot merge by tag; network connectors pair by number | unchanged: untagged valves are single-occurrence items, as fittings are now; network pairs are ordinary pairs |
| Line view (`graph/line_view.py`, frozen) | branches without a line number (TOG73) | must handle them already (v1 corpora have no line numbers); T3 proves it on a fixture with the frozen module; if it fails, TOG73 is DEFERRED rather than the frozen file changed |
| Prompts, primer, Cypher, agent tools | none | unchanged |
| CLASS_NAME instruction (ADR-0058 point 5) | lists the classes present | no new class, so the same list |
| Question generation and gold (`qa/questions/*`, gold side under ADR-0060) | untagged answers; networks change reach | gold-side changes only (§11); v2.1 question sets byte-identical (T0 hash) |
| Scorer | none | unchanged |
| Demo | none | stays on H1000g21p1 (one corpus in Neo4j) |

**Options for D1.**
- **A. Frozen V2T-A2, data replication (recommended).** Positions are drawn into DEXPI and the hidden record, not
  the store. Gold stays topological, and isolation-family candidates whose answer contains an untagged valve are
  refused on the gold side, with the refused share reported.
  - Buys: any change against EXP-0008 is the data's.
  - Costs: the system cannot use positions, and isolation questions come only from tagged trains.
- **B. Documented system revision V2T-B.** `operating_position` becomes visible on v2.2 corpora only (schema text
  conditional on the corpus), position-aware isolation families, and an answer format naming an untagged valve by
  (class, line number, neighbour tag).
  - Requires a new freeze, a re-validation and a paired V2T-A2 arm on the same plants to separate the effect of the
    data from that of the system.
  - Costs about one extra sealed arm ($6.69 basis, §12.3) plus development.
- **C. Both arms on the same v2.2 plants.** The most informative and the dearest: B plus A.

**Recommendation: A for EXP-0009.** B is reconsidered only if EXP-0009 shows a large drop that the rows trace to
positions or to untagged items.

## 11. Question validity

All gold stays **topological** (any piping path, whatever the valve positions), as in v2.1. The table says what
changes.

| Family | Untagged manual valves | Network / interarea sheets | Action (gold side) |
|---|---|---|---|
| UPSTREAM_ISOLATION, DOWNSTREAM_ISOLATION (TAG_SET of valves) | an answer may hold an untagged valve | routes may end at a network root valve (tagged by convention) | refuse a candidate whose answer holds an untagged item; report the refused share per plant |
| FLOW_PATH, NEIGHBOURS_DOWNSTREAM (tagged items along the path) | untagged valves drop out of the listing, as fittings do now | longer paths, more crossings | refuse a pair whose equal-length shortest paths differ in their tagged sequence (extends the F2 rule) |
| VALVES_ON_PATH (count) | counted, since a count needs no name | unchanged rule | none |
| CONNECTED, NO_PATH, UPSTREAM_SOURCES, FEEDING_UNITS, UNITS_REACHED, CROSS_UNIT | none | process → collection networks and distribution networks → process add reach and units | none; report the share of questions whose evidence touches a network sheet (a new descriptive column beside k and u) |
| LOOP_ACTUATED_VALVE (single TAG) | none | none | two fuel switching valves get two actuators and two numbers, so the answer stays single |
| LOOKUP_*, SHEETS_OF_TAG, INSTRUMENTS_OF_ITEM, UNANSWERABLE_TAG, SAME_UNIT, COUNT_IN_UNIT, DOWNSTREAM_IN_UNIT, ROUTE_AVOIDING | fewer valve anchors | network units appear as units | none |

- **What "topological" means for the reader.** "Which valves must be closed" includes a bypass valve that is
  normally closed, and an isolation list in practice includes verifying NC valves. The thesis states that EXP-0009
  questions do not use positions.
- **Availability (ADR-0029 and ADR-0053's fixed n).** Each family needs at least 10 candidates on every sealed plant
  (10 per family per plant, as EXP-0008). A family below that on any plant is pre-registered as unavailable on v2.2.
  It is not rescued by changing the untagged weight, because that would tune the data to the questions.
- **Not reworded.** No question is reworded (user, natural questions only).

## 12. EXP-0009: pre-registered re-measurement on v2.2

### 12.1 Claims

- **Primary: Q4 on v2.2** (cascade_v4_iso, S1000 − S100, pooled over five plants per scale, two-stage cluster
  bootstrap). Pass if the interval contains 0 or lies above, as in ADR-0053 and ADR-0065.
- **Carried over:** K1, K2, K3, Q5, unchanged.
- **Descriptive:** the "realism effect", v2.2 − v2.1 per scale on the cascade (unpaired, different plants, the same
  bootstrap); refused-candidate shares; network-touching shares; `rules.json` summaries.
- **In P2:** X1/X2 (ladder) and E1–E4 (identity), as registered.

### 12.2 Free gates (all before the first paid call; $0)

| Gate | Pass |
|---|---|
| G0a goldens | v1 and v2.1 goldens unchanged; full suite green |
| G0b rule suite | every positive and mutation test passes; every rule and alternative non-vacuous over the 5 seeds |
| G0c build verification | every EXP-0009 plant built with 0 violations; `rules.json` hashed into the freeze |
| G0d composition | ADR-0059 bands pooled per scale on process sheets; network sheet statistics reported |
| G0e availability | ≥ 10 candidates per family per sealed plant, else pre-registered unavailable |
| G0f frozen system | E9 system-side paths unchanged; one cache-only replay per tier byte-identical (ADR-0060 1B) |
| G0g resolution | pair precision = recall = 1.0 at exact tags (network connectors included) |
| G0h prompt size | every prompt fits, as in EXP-0008 M4 |
| G0i v2.1 → v2.2 diff | the same dev seeds built both ways; descriptive table of what changed (counts per rule, sheet kinds); no gate |

### 12.3 Cost, grounded in EXP-0008's measured spend

**Basis.** I computed the basis with `qa/exp0008/ledger.paid_usd_of_calls` over every EXP-0008 call file (calls not
served from the cache) on 2026-11-22.

**Finding.** The launcher's "runs $26.56" includes **$5.17 of byte-identical copies** of run call files that M10b
assembled under `reports/duplication/` and `reports/r5_1000/`. The de-duplicated runs spend is **$21.40**, and the
audit's **$5.23** is unaffected (own ledger). The ledger glob should skip `reports/` (task T13).

| EXP-0008 arm | Measured paid |
|---|---|
| M1 validation (2 plants) | $1.16 |
| M6a V2T-A2 sealed, 10 plants × 280 | $6.69 |
| M6b F1 baseline, 10 plants (incl. one superseded run, $0.27) | $4.44 |
| M6c duplication + concurrency-1 | $1.18 |
| M8b P4 identity, 5 plants | $4.48 |
| P3 D4 decisions | $0.33 |
| M5 ladder (ContextRAG $2.51 of it) | $3.02 |
| Scorer audit main (pilot $1.62 not repeated) | $3.61 |

**EXP-0009, stage P1 (fits in $17):**

| Step | Basis | Estimate | Step cap (1.5×) |
|---|---|---|---|
| Validation pair (V2T-A2 only; G1's "no dev family below 50 % on both plants") | M1 | $1.16 | $1.74 |
| V2T-A2 sealed, 5 + 5 plants × 280 | M6a | $6.69 | $10.04 |
| Scorer audit (same judge pin and prompt, no pilot) | audit main | $3.61 | $5.00 (hard) |
| **P1** | | **$11.46** | **ledger hard cap $16.50** |

- **The ledger binds, not the sum of step caps.** The step caps sum to $16.78, but the $16.50 ledger is what stops
  a run.
- **Headroom** over the estimate is $5.04. The real step caps come from free dry runs, as in EXP-0008.
- **Per-question cost is not measured on v2.2.** EXP-0008 measured a cost elasticity of 0.044 per tenfold sheets,
  which suggests insensitivity. But networks lengthen paths, so the validation pair measures the real $/q before the
  sealed stage, and the sealed caps are recomputed from it.

**Stage P2 (after a top-up):**
- ladder $3.02 (cap $4.53);
- P4 identity $4.48 (cap $6.72), with the D4 decisions $0.33 (cap $0.50);
- optional F1 baseline $4.44 (cap $6.66).

P2 is estimated at $7.83 without F1 and $12.27 with it, under a ledger hard cap of $13.50.

**Program:** estimate $19.29 without F1, hard cap **$30** (P1 ≤ $16.50, P2 ≤ $13.50).

**What fits in $17:** P1 only (Q4, K1–K3 and Q5 on v2.2, with the audit). Everything else waits for the top-up.

**Machine time (P1), from EXP-0008's per-unit figures** (`review-fixes.md` §6: H1000 question pool 8,585 s,
generation 421.6 s; at 1,000 sheets Cypher 1.44 h + agent 1.70 h per 560 questions, at 100 sheets 0.38 h + 0.50 h):

| Block | Time |
|---|---|
| question pools (6 × 1,000-sheet) | ≈ 14.3 h |
| builds plus verification | ≈ 2–3 h; verification time unmeasured |
| validation | ≈ 1.5 h |
| sealed (5 × 1.57 h + 5 × 0.44 h) | ≈ 10 h |
| audit | ≈ 1 h |
| **Total** | **≈ 29–30 h** of machine time |

### 12.4 Protocol

- **Pre-registration.** As EXP-0008: part A (claims, gates, seeds, caps, ledger, judge hashes) is committed before
  the button; part B and the freeze are written by the launcher after the validation step and before the first test
  plant.
- **Launcher.** It reuses the EXP-0008 launcher structure in `data/runs/exp0009/`.
- **Stops.** The launcher stops only on a gate, a cap or an infrastructure error.
- **Start.** Nothing starts before the user's word.

## 13. Coder tasks (Sonnet, one at a time)

**Every task:**
- leaves `pytest`, `ruff` and `mypy --strict` green, and the v1 and v2.1 goldens unchanged;
- builds no EXP-0009 data and makes no paid call;
- ends with one commit proposal (files listed, one-line message), with nothing committed without the user's order.

**Sizes** S/M/L follow the previous notes' scale. Coder pace is unmeasured.

| # | Task | Size | Waits for |
|---|---|---|---|
| T0 | v2.1 pins and goldens (§9 point 1); audit shared constants v2.1 draws from; `tests/v2/test_v21_goldens.py` | S | **independent: start now** |
| T1 | Registry package: `rules/registry.py`, `rules/catalogue.py` (55 + deferred), `rules/view.py`, `rules/verify.py`, move `check_s1..s24` into `rules/checks_v21.py`, registry tests (§3.2–3.3), `python -m plantgraph.benchmark.v2.rules --table` | M | **independent** |
| T2 | `GeneratorConfigV22`, `HandbookKnobs`, three-way dispatch, `HiddenDesignState` container (empty maps), `--generator v2.2`, `HeadlinePresetV22`; a v2.2 plant with every knob off equals the v2.1 plant of the same seed except the version field | M | **independent** |
| T3 | Verified fixes, gated on v2.2: TOG192-RECIP-NO-CHECK, TOG192-PD-NO-MINFLOW, TOG177-MINFLOW-TAKEOFF, TOG314-PD-NO-THROTTLE, TOG319/TOG316 compressor capacity, TOG73 (with the frozen line-view fixture first); positive and mutation tests | M | **independent** |
| T4 | Hidden pump power band; TOG177-MINFLOW-NEED, TOG313-MINFLOW-METHOD (RO / switching valve / FIC loop) | M | **independent** (the user already ruled "declared parameters") |
| T5 | Valve positions: plan fields, DEXPI fail action and custom attribute, TOG114/120/224/TOG114-FAIL-ACTION, adapter strips them before the store; demo drawing label optional | M | **independent** for plan and DEXPI; store visibility waits for D1 |
| T6 | Manual-valve tagging per train (TOG113); gold-side refusal of untagged answers, the FLOW_PATH tie rule and the refused-share report; v2.1 question hash unchanged | M | **D1, D2** |
| T7 | Networks and interarea: network units, headers, per-sheet sub-headers, network connectors, capacity overflow, splitter grouping, size search on total sheets, composition per sheet kind, TOG32/141/360/33, PLT-NETWORK-CLOSURE | L | **D4** |
| T8 | Pressure-level model and PRS-*, TOG82 (pump spec breaks), TOG156, PLT-RECYCLE-CLOSURE, API14C-A4-OVERPRESSURE | M | **D3** |
| T9 | Control checks TOG271, TOG267, TOG295, TOG270, TOG320, TOG224-PSV-PIPE-CLEAN, TOG24, PLT-STREAM-CLOSURE; any failure on v2.1 seeds is reported back to the architect before a fix | M | **independent** (checks); fixes may need a decision |
| T10 | SAC table `rules/sac.py` from the researcher's page-checked transcription; API14C-3.4-TWO-LEVELS, API14C-SAC, TOG207-HX-PSD-BOTH-SIDES, TOG236 | M | **the transcription** (researcher, not coder); D3 for derived exceptions |
| T11 | Alternatives: TOG34 check variant, TOG173 reducers, TOG322 two-CV bypass, TOG214 double fuel valves, TOG309 reflux class, TOG122 PV without bypass | M | **independent**, unless the user vetoes an alternative |
| T12 | External checks: composition report per sheet kind, the ch.20 comparison table (the annotation itself by the main session), the review checklist export | S | D7 for the review |
| T13 | EXP-0009: ledger glob skips `reports/` (fix of the EXP-0008 double count, with a test on a copied call file), ids `g22`, seed draw, launcher stages, PREREG A template | M | **D1, D5** |

**Decision-independent now:** T0 → T1 → T2 → T3 → T4 → T9 → T11, then T5's plan and DEXPI part.

## 14. Risks

- **Composition drift.** Networks raise stubs per process sheet; FIC min-flow loops and SAC devices raise
  instruments per sheet. Mitigations: per-sheet sub-headers, cheap devices only, and the G0d gate. A failed band
  stops the run (U4 rule of ADR-0065): adjust a declared knob as a recorded generator change, or report the miss.
- **Availability.** Isolation families may lose about the candidates of untagged trains. This is measured by G0e
  and is not tuned.
- **Build time.** Verification on 1,000-sheet plants is unmeasured (T1 measures it).
- **Plant checks may fail on v2.1 seeds** (TOG271, TOG270, TOG320 are unknown). Each failure is a real finding: it
  becomes a v2.2 fix, and the v2.1 record gets a note. v2.1 data is never changed.
- **Unverified sources.** Liptak 1995 cannot be page-checked. It supports nothing that is encoded.

## 15. Decisions for the user

| # | Decision | Options | Recommendation | Consequence |
|---|---|---|---|---|
| D1 | System for EXP-0009 | A frozen V2T-A2 · B revision V2T-B · C both | **A** | clean data replication; positions not used by the system; isolation questions from tagged trains only |
| D2 | Sampling units and weights | train for identification, item for arrangements; untagged 1 : 1 | **as proposed** | half the trains untagged, on average |
| D3 | Hidden ordinal pressure model allowed under ADR-0021 (clarification) | yes · no (then T8 is dropped and PSD need stays per-pattern) | **yes** | 6 plant-level checks and derived SAC exceptions become possible |
| D4 | Networks: FL, CHD, CWS/CWR, LPS/MPS/CD, FG plus interarea; counted in the sheet target | this set · fewer · not counted | **this set, counted** | more cross-sheet links, of the kind real sets have; the share is reported |
| D5 | EXP-0009 scope | P1 now ($11.46, cap $16.50), P2 after a top-up · everything at once | **P1 now** | Q4 on v2.2 inside the current credit |
| D6 | The deferred list (§4.9) | accept · pull items in | **accept** | the thesis states the encoded and deferred counts |
| D7 | Expert review sample of 12 sheets | a reviewer exists · not | only if a reviewer is available | otherwise L3 is bands plus the ch.20 comparison |

## 16. Source verification log (2026-11-22, by the architect)

**Toghraei 2019** (text layer).
- **Page offset.** The printed page was read from the running header on each page. The offset drifts: −19 at
  p.24–34, −18 at p.173–236, −17 at p.265–271, −16 at p.295–328, −12 from ch.20.
- **Pages checked:** 24, 28, 32–34, 73, 82, 84, 113–115, 120, 122, 156, 173–175, 177, 179, 191–193, 195, 207, 214,
  215, 219, 224, 236, 267, 270, 271, 295, 309, 313, 314, 316, 317, 319, 320–322, 326–328, 360, 412.

**Discrepancies with the notes or the task text:**
1. **Spare tagging** is on p.28, not p.30.
2. **The one-CV-on-liquid rule** is on p.271, not p.270.
3. **Table 15.1** is on p.295, not p.294.
4. **Exchanger isolation, no bypass and PSDs on both sides** are on p.207, not p.206.
5. **The min-flow power rules** are on p.313 and p.179. The text layer of p.313 reads "5hp<Power<1020hp". I read it
   as 10–20, and p.179 gives 20–35 for on-off and above 35 for a control loop, so the bands use 5–20, 20–35 and
   above 35.
6. **Two switching valves in series on the fuel line** are "in some designs" (p.214), not "often".
7. **Spare naming in the code.** The note says "GEN: A/B only". The code already draws suffix or consecutive
   numbering per train at 3 : 2 (`vocabulary.py` `SpareNaming`, `SPARE_NAMING_WEIGHTS`).
8. **Equipment per sheet.** The note says "GEN band 3–10, none > 10". EXP-0008 measured equipment per sheet at min 1
   and max 7 (H100g21p1) and max 11 (H1000g21p1), with a share ≤ 10 of 0.998.

**API RP 14C 2001** (text layer; printed = PDF − 8). Pages checked:
- §3.4 b p.7;
- §4.2.3 p.14;
- A.4.2.2.1 p.26;
- A.7.2.2.2 p.40;
- SAC A-7.2 g p.44;
- A.8.2.2.1 and A.8.3.2 p.45;
- B-1 p.59.

The SAC omission conditions per item were **not** checked one by one; that is T10's transcription.

**Liptak IEH Vol. 1 2003** (text layer). §1.1 was found on PDF p.56 (secondary instrumentation, functional
identification only), p.58 (parallel / serial / parallel-serial numbering; gaps allowed) and p.76 (one number per
loop; cancelled numbers not reused; A/B suffix on spares' instruments). §7.7 was found on PDF p.968 (secondary
relieving device when an arrester can clog). Printed pages are not given because the PDF offset drifts.

**Liptak IEH Process Control 1995** is an image scan with no text layer. Nothing was re-checked, and it is cited by
section only, for deferred or secondary items.

**EXP-0008 spend.** Recomputed with the repo's own ledger functions: the runs ledger is $26.57 including $5.17 of
copies under `reports/`, so the de-duplicated runs spend is $21.40. The audit is $5.23.
