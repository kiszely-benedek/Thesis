---
component: benchmark/generator v2.2 — handbook rule registry, plant-level correctness layer, valve positions, untagged manual valves, network and interarea sheets; EXP-0009 re-measurement plan
status: draft — user decisions D1–D8 of 2026-11-23 folded in (§18); ADR-0066 and ADR-0067 proposed, awaiting acceptance
date: 2026-11-22 (decisions folded in 2026-11-23)
related: [ADR-0066 (proposed), ADR-0067 (proposed), 40-design/v2t-b-system-revision.md, ADR-0016, ADR-0021, ADR-0027, ADR-0029, ADR-0053, ADR-0057, ADR-0058, ADR-0059, ADR-0060, ADR-0065,
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
   and a check function. The design encodes **54 rules**: 35 local rules and 19 plant-level checks (§4). It records
   **15 deferred entries** (14 groups read but deferred, plus TOG73, deferred in T3), each with a reason.
2. **A plant-level correctness layer** (§2, §6) on top of the local rules. It checks stream closure, an ordinal
   **pressure-level model** kept as hidden generator state, control structure, protection presence-or-exception
   (API RP 14C), and network closure. **Every v2.2 plant is verified when it is built.** A violation refuses the
   build, and every corpus carries a `rules.json` report beside its `ingest.json`. That is what makes "checked on
   every generated plant" literally true, not only true for test seeds.
3. **The new content the user chose** (scope b, 2026-11-22):
   - valve positions: NO/NC/CSO and fail actions;
   - tagged or untagged manual valves, drawn **per document** (a contractor's ~100-sheet drawing set) at
     **0.75 untagged**, the share measured on 12 real drawing sets (D2, §18.2);
   - network and interarea sheets reached through network off-page connectors;
   - the verified fixes;
   - the cheap gaps.
   No new node class is added. Everything stays inside the 77-class allowlist (ADR-0016).
4. **EXP-0009 runs two systems on the same v2.2 plants** (D1 = C, §18.1):
   - the frozen **V2T-A2** (freeze E9), as a pure data replication;
   - a documented revision **V2T-B** (`40-design/v2t-b-system-revision.md`, ADR-0067), which sees valve positions
     and names untagged valves, frozen as **E10**.

   It runs free gates first, then the paid stage P1:
   - B's tuning;
   - one validation pair per arm;
   - five sealed plants per scale, with sizes drawn in the bands 90–110 and 900–1,100 sheets (D5, §18.3);
   - the scorer audit.

   P1 is estimated at **$24.95** from EXP-0008's measured spend, under a hard ledger cap of **$37.50** (§12). The
   ladder and the identity arm (P2) follow, on V2T-A2 only.

What this buys the thesis claim: if the scale result (Q4) holds on plants whose rules are cited and checked, then
the examiner's "toy topology" objection is answered with a stronger generator. The A2 arm changes nothing in the
retrieval system, so its difference against EXP-0008 comes from the data. The B arm, paired with A2 on the same
questions, measures what a system gains by reading the new content, and tests Q4 a second time.

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
- **User decisions, 2026-11-23 (D1–D8):** D1 = C (two arms), D2 = calibrate from evidence, D3 = yes, D4 = as
  proposed, D5 = P1 now (shape analysed in §18.3), D6 = re-triage, D7 = yes (reviewer to be found), D8 = A. §15 lists
  them; §18 works out each one.

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
- **Frequency.** No per-class frequency is published (`generator-v2-realism.md` §0). Two weights now rest on counts
  over 12 real drawing sets (§18.2), which is a small convenience sample; every other weight is declared. A plant can
  be correct and still be statistically unlike real plants, and the thesis must not claim real frequencies.
- **Physics we do not model.** We model no chemistry, mass or energy balance, sizing, set pressures or temperatures
  (ADR-0021).

**What closes the gap as far as it can be closed without datasheet data** (§6):

| Layer | Guarantees on every built plant | Does not guarantee |
|---|---|---|
| L1 local rules (35) | no encoded local pattern is violated; every sampled alternative is one a book names | anything across trims |
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
    sampling_unit: Literal["document", "train", "item"] | None   # ALTERNATIVE only; "document" since D2 (§18.2)
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
  - Run time: verification of a 1,000-sheet v2.2 dev plant takes **11.9 s** after the piping-graph cache
    (`e5b987b`, §17.11 F4), against 390.99 s of generation on H1000g21p1 (`EXP-0008-v2-rerun.md`).
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

- **Rules:** 54 encoded (35 local, 19 plant-level) and 15 deferred entries (the 14 groups of §4.9 and TOG73, which
  T3 deferred because the frozen line view could not take unnumbered branches).
- **Wired today (after `cf2eddb`, 2026-11-23):** 38 of the 54 have a check that runs. The other 16 are
  `pending:<task>`: T8 6, T7 5, T10 4, T6 1 (counted with `grep pending(` over `rules/`).
- **Tests:** 54 positive tests (270 parametrised cases over 5 seeds), 54 mutation tests, the non-vacuity tests and
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
| TOG28-SPARE-NAMING | Installed spares are tagged P-125A/B, or as unrelated numbers P-125/P-126; one convention per document (was per train in v2.1; §18.2) | TOG p.28; LIP1 §1.1 PDF p.76 (A/B suffix on spares' instruments) | ok: already drawn per train, suffix : consecutive = 3 : 2 (`vocabulary.py` `SPARE_NAMING_WEIGHTS`) | cite, test; v2.2 draws it per document | ALT, document |
| TOG113-MANUAL-VALVE-TAGS | Within a document (one contractor's drawing set), either every manual valve carries a tag or none does; automatic valves, safety valves and instruments are always tagged | TOG p.113; unit and share from 12 real drawing sets (§18.2) | every manual valve tagged | new | ALT, document |
| TOG73-UNTAGGED-BRANCH-PIPES | No line number on a short pipe to a plugged or blinded vent or drain valve, nor on a control-valve bypass pipe | TOG p.73 (Table 6.3) | branches numbered (`trim_plan.py`) | **DEFERRED in T3** (§10: the frozen line view fails on the fixture); counted in §4.9 | FORBID |
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
| TOG207-HX-NO-ISOLATION | **Restated 2026-11-23 (§17.5).** Isolation at an exchanger is company policy ("subjective", p.207); v2.2 follows the no-isolation policy on the **process side**: the process side is never blocked in on both inlet and outlet, and has no hand bypass, unless the exchanger has an installed spare or a cleaning-in-place system. Utility-side valves are outside the rule | TOG p.207 | ok on the restated rule (T9 diagnostic, seeds 1–5) | cite, test | FORBID |
| TOG320-HX-NONTARGET | The temperature controller moves the non-target stream: directly on a utility, by a bypass on a process stream | TOG p.320–321 | not checked | check | PLANT |
| TOG322-HX-BYPASS-VARIANT | A bypass TV alone, or control valves on both the main and the bypass branch | TOG p.322 | bypass alone | new | ALT, item |
| TOG326-STEAM-CONDENSATE | Steam heater condensate: trap, trap station, or a condensate pot with level control | TOG p.326–327 | ok (`CondensateMode`, 2 : 1 : 1) | cite, test | ALT, item |
| TOG214-FUEL-SWITCHING-VALVES | One switching valve, or two in series, on the fuel line | TOG p.214 ("in some designs") | one XV | new; each valve gets its own actuator and number | ALT, item |

### 4.6 Control structure

| Id | Rule | Sources | v2.1 | v2.2 | Kind |
|---|---|---|---|---|---|
| TOG271-ONE-CV-LIQUID | At most one control valve in series on a liquid-filled line between two containers; a flooded vessel counts as pipe; the valves of a temperature split around an exchanger (bypass TV, or the TOG322 valve pair) do not throttle the line and do not count (§17.2) | TOG p.271; p.321–322 (split valves keep the total flow) | **fails** (T9): FV of a farm transfer, then the optional FV of a filter package | check; v2.2 fix in T9b (§17.2) | PLANT |
| TOG267-FE-UPSTREAM-FV | A flow element sits upstream of the FV of its loop | TOG p.267 | not checked | check | PLANT |
| TOG295-INVENTORY-ONCE | A non-flooded liquid container has exactly one level loop; a container a process gas line passes through, or whose function depends on pressure, exactly one pressure loop; any other container at most one; a flooded container none. Exception codes (derived by the check, §17.3): `storage_tank_batch`, `pressure_floating_on:<id>`, `pressure_optional` | TOG p.295 (Table 15.1), p.270 (rule 8; "may choose to control both"), p.305 (flows to storage and intermittent flows) | fails before §17.3 (additive day tanks, one blend vessel) | check | PLANT |
| TOG309-SPLIT-PAIRING | At a drum split, flow control goes on the smaller stream and level control on the other | TOG p.309 | fixed: reflux FIC, distillate LV | new; the hidden reflux class decides | ALT, item |
| TOG122-PV-NO-BYPASS | Some companies give pressure-control valve stations no bypass | TOG p.122 | always a bypass | new; per document (company policy, §18.2) | ALT, document |

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

**Count:** §4.1 5, §4.2 6, §4.3 10, §4.4 4, §4.5 5, §4.6 5, §4.7 6, §4.8 14 rows, which made 55 rules; TOG73 was
deferred in T3, so **54 rules are encoded** (35 local, 19 plant-level). The 19 plant-level rules are those of kind
PLANT. 38 of the 54 are wired after `cf2eddb` (§3.4).

### 4.9 Read but deferred (status DEFERRED, in the registry with a reason)

The last column is the user's triage request D6 (2026-11-23), re-done after D1 = C (§18.4). **Now** = done in a v2.2
task before EXP-0009's data freeze. **If flagged** = done only if the expert review (T12, D7) flags it and it fits
before the freeze; otherwise it stays deferred. **Out** = not in this thesis.

| # | Group | Sources | Why deferred | Bin (D6) |
|---|---|---|---|---|
| 1 | Functional-only identification for local gauges (no loop number) | LIP1 §1.1 PDF p.56 | gauges would share tags like `PI`; this breaks S9 and identity by tag in the frozen resolver | **Out**: both arms share the resolver, and A2's is frozen |
| 2 | Parallel loop numbering | LIP1 §1.1 PDF p.58 | FIC-101 and LIC-101 would share a loop number, which collides with the ADR-0027 signal-connector key | **Out**: store key change shared by both arms |
| 3 | Gaps in tag sequences | LIP1 §1.1 PDF p.58, p.76 | no effect on what the thesis measures | **Out**: no question or check can see it |
| 4 | API "S" device letters (PSH/LSH meaning "safety") | API 14C §2 (section) | the same letters mean different things in ISA; the frozen primer (ADR-0041) explains ISA | **Out**: the shared data would contradict A2's frozen primer |
| 5 | Trip by a solenoid on the control valve | LIP1995 §8.19 (section, not re-verified) | one valve with two drivers breaks S7 and LOOP_ACTUATED_VALVE | **Out**: changes a registered family's answer; source not page-checkable |
| 6 | Min-flow by a PCV kickback or an FSL pump trip | LIP1995 §8.23 (section, not re-verified) | page not verifiable; the FSL trip is a new motor-trip shape | **Out**: no page-checkable source |
| 7 | 3-way exchanger valve | TOG p.322 | needs a new class (ADR-0016) | **Out**: a new class changes the schema text of every corpus |
| 8 | Pulsation dampener; back-pressure regulator on dosing pumps; self-acting regulators | TOG p.192, p.195 | no fitting class for a dampener; a one-member regulator loop breaks S8 | **Out**: new class and a new loop shape |
| 9 | Tank blanketing and VRU | TOG ch.9, ch.15 (note, not re-verified) | needs split-range PCVs and a VRU network | **If flagged** (it would also close the §17.3 vapour gap); size L |
| 10 | Double block and bleed; blinds at pump isolation valves | TOG ch.8, p.175 (note) | changes isolation answers; low value | **Out**: it changes what "the valves to close" means for both arms' isolation gold |
| 11 | Fired heater passes, pilot gas line, snuffing steam | TOG p.213–215 | new heater pattern variant; large | **If flagged**; size L |
| 12 | Compressor PSH/PSL/TSH/BDV, vessel LSL and the other SAC devices without a derivable exception | API 14C SAC A-4.2, A-8.2 (T10) | each becomes a DEFERRED SAC row, unless the device is cheap and inside the composition bands | **Now: T10** decides device by device |
| 13 | Shut-in at the primary source | API 14C §4.2.3 p.14 | needs trip → motor interlock edges across sheets, which S19/S20 forbid; v2.2 reports the share of trips that act at the source | **Out**: changes the signal model; reported as a share |
| 14 | Interlock-diamond drawing style; multi-stage compressors; lube-oil and seal systems | TOG ch.16, ch.10 (note) | drawing style, or detail P&IDs | **Out**: style is not in the graph; seal and lube systems are vendor detail sheets |
| 15 | TOG73 untagged branch pipes (was encoded; deferred in T3) | TOG p.73 (Table 6.3) | the frozen line view (`graph/line_view.py`) cannot take unnumbered branches | **Out**: under D1 = C the A2 arm must ingest the same plants (v2t-b note §1) |

**Count:** 14 groups plus TOG73 = **15 deferred entries** in the registry. Triage: 1 now, 2 if flagged, 12 out.

## 5. Sampled alternatives and their sampling unit

**Principle** (*revised 2026-11-23, D2, §18.2*).
- **Company conventions** (manual-valve tagging, spare naming, on-off valve letter, pressure-control stations
  without a bypass) are drawn **per document**.
  - A document is one contractor's drawing set. In the generator it is a run of consecutive trains, about 100 sheets
    long (`DocumentRecord`, task T6).
  - The evidence: every real multi-sheet set we hold keeps one convention on all its sheets, and a v2.1 train is only
    about 9 sheets (§18.2). v2.1 drew `on_off_letter` and `spare_naming` per train; v2.2 takes those draws and
    ignores their values (randomness rule below), drawing the conventions again per document.
- **Engineering arrangements** are a choice per item, so they are drawn **per item**.
- **Coupled choices come from one hidden cause.** Where a choice has a cause the books name (hp, reflux ratio), the
  generator samples the **hidden cause** and derives the visible consequence. Independent coins for coupled features
  are avoided.

| Alternative | Unit | Driver | Basis (§18.2) | Included |
|---|---|---|---|---|
| Manual valves tagged or untagged | **document** | `p_untagged_manual_document` = **0.75** | **measured**: 9 of 12 real drawing sets untagged | yes |
| Spare naming: suffix or consecutive | **document** | 3 : 2 (unchanged) | 4 : 2 sets; 0.6 lies inside the interval | yes (exists) |
| On-off valve letter X or Y | **document** | 1 : 1 (unchanged) | 2 : 2 sets | yes (exists) |
| Pressure-control stations without a bypass | **document** | `p_pv_no_bypass_document` = 0.5 | no count; neutral | yes |
| Min-flow method | pump set | hidden power band, `<5 : 5–20 : 20–35 : >35` = 1 : 1 : 1 : 1 | none (power is datasheet data) | yes |
| Battery-limit isolation, 3 variants | item | 1 : 1 : 1 | one sheet only | yes |
| Pump nozzle reducers | pump set | `p_pump_reducers` = **0.75** | **measured**: 3 of 4 sets that draw pump trims | yes |
| Exchanger bypass: TV alone, or two CVs | item | 1 : 1 | no count | yes |
| Steam heater condensate mode | item | 2 : 1 : 1 (unchanged) | existence only | yes (exists) |
| Fuel switching valves: one, or two in series | furnace | 1 : 1 | one sheet | yes |
| Accumulator split pairing | column | hidden reflux class low : high = 1 : 1 | none (L/D is datasheet data) | yes |
| The deferred list of §4.9 | — | — | — | no |

- **Measured where we can, declared where we cannot.** Two weights now rest on counts from real drawing sets
  (untagged share, pump reducers). The rest stay neutral declared values, and §18.2 gives the reason per weight.
- **The sealed plants are stratified on the tagging convention** (§18.3). Their untagged share is fixed at 0.8 per
  scale instead of being drawn, so the two scales carry the same mix.

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
  nothing asked. ADR-0066 records this as a clarification of ADR-0021, not a supersession. **The user confirmed it
  on 2026-11-23 (D3 = yes), so T8 is unblocked.**
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
- **TOG295.** *Superseded by §17.3 (2026-11-23).* The exception codes are **derived by the check** from the plan's
  structure, not written by the pattern (T9's choice, accepted: derived, never drawn, as §6.4 asks). An atmospheric
  tank with a level transmitter and no level loop is `storage_tank_batch` (p.305 is now page-checked). A drum that
  floats on a controlled neighbour with no valve between gets `pressure_floating_on:<id>`. A container that needs no
  pressure loop and has none is `pressure_optional`.
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
| Expert review | 12 dev-plant sheets reviewed by a P&ID engineer against a 25-item checklist keyed to rule ids, plus "anything that looks wrong"; each finding becomes a fix before the freeze, a rule change or a recorded limitation. The user is finding the reviewer (D7 = yes); the plan is §18.5 | no gate; findings are triaged before the EXP-0009 freeze |
| Rule report | per rule: instances checked, 0 violations, exceptions by code; the encoded / deferred counts | yes (build refuses on a violation) |

## 7. Network and interarea sheets

**Which networks** (D4, decided by the user on 2026-11-23 as proposed; T7 is unblocked):
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
- **Root valves.** Distribution tie-ins get a root block valve on the network sheet (NO; tagged by the document's
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
- The A-view adapter drops both before the store (V2T-A2). The B view keeps `operating_position` on the valve node and still drops the fail action (D1 = C; `v2t-b-system-revision.md` §2).

**Untagged manual valves.**
- In a document drawn "untagged" (§5, §18.2), `format_valve_tag` is not called for manual valve roles. The node has no `tag`, like
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
   - identity arm `H1000g22pkV`;
   - the B view of each sealed or validation plant: the same id with `B` appended (`H1000g22p1B`, D1 = C).

   Fresh test seeds are drawn by the `draw_seeds` tool (F12). The EXP-0008 test seeds are retired.
5. **Every coder task** keeps the full suite green and the v1 and v2.1 goldens unchanged. A failing golden means the
   change is wrong, never the constant.

## 10. Impact on the frozen system (V2T-A2, freeze E9) and the B arm

**Decision D1 = C (user, 2026-11-23).** Both arms run on the same v2.2 plants: the frozen V2T-A2 and the documented
revision V2T-B. V2T-B is designed in `40-design/v2t-b-system-revision.md` and recorded in ADR-0067 (proposed). The
user will top up the credit, so cost does not block the B arm. The table shows what each arm sees.

| Component | What v2.2 touches | V2T-A2 (frozen, E9) | V2T-B (revision, E10) |
|---|---|---|---|
| Schema text (`qa/schema_text.py`, built from `graph.schema.VISIBLE_NODE_PROPERTIES`) | a visible `operating_position` would change the text of **every** corpus, v1's goldens included | not added; positions stay out of the A store | one added paragraph, only on B corpora (`qa/v2tb/schema_text_b.py`) |
| Resolver (identity by tag; ADR-0027 connector key) | untagged valves cannot merge by tag; network connectors pair by number | unchanged: untagged valves are single-occurrence items, as fittings are now; network pairs are ordinary pairs | the same, shared |
| Line view (`graph/line_view.py`, frozen) | branches without a line number (TOG73) | T3 showed the frozen module fails on them, so TOG73 is DEFERRED | the same: the plants are shared |
| Prompts, primer, Cypher, agent tools | none | unchanged | primer paragraph on positions and untagged valves; `operating_position` among the item properties |
| CLASS_NAME instruction (ADR-0058 point 5) | lists the classes present | no new class, so the same list | the same |
| Question generation and gold (`qa/questions/*`, gold side under ADR-0060) | untagged answers; networks change reach | scope R (§11) | scope R plus scope X |
| Scorer | none | unchanged | `qa/v2tb/scoring_b.py` for VALVE_SET and POSITION |
| Demo | none | stays on H1000g21p1 (one corpus in Neo4j) | no demo |

**The options for D1, as they were put to the user.**
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
- **C. Both arms on the same v2.2 plants.** The most informative and the dearest: B plus A. **Chosen by the user.**

The architect had recommended A. The user chose C, and the design follows C. The B arm's estimated cost is in §12.3.

## 11. Question validity

**Two scopes since D1 = C** (`v2t-b-system-revision.md` §4):
- **Scope R (replication),** the EXP-0008 recipe, is answered by both arms. Its gold stays **topological** (any
  piping path, whatever the valve positions), as in v2.1. The table below gives its rules.
- **Scope X (extension)** holds the position-aware family OPEN_VALVES_TO_ISOLATE (up and down) and isolation
  questions whose answers may name untagged valves. Both arms answer its isolation families; only B answers
  POSITION_OF_VALVE.

Rules of scope R:

| Family | Untagged manual valves | Network / interarea sheets | Action (gold side) |
|---|---|---|---|
| UPSTREAM_ISOLATION, DOWNSTREAM_ISOLATION (TAG_SET of valves) | an answer may hold an untagged valve | routes may end at a network root valve (tagged by convention) | refuse a candidate whose answer holds an untagged item; report the refused share per plant |
| FLOW_PATH, NEIGHBOURS_DOWNSTREAM (tagged items along the path) | untagged valves drop out of the listing, as fittings do now | longer paths, more crossings | refuse a pair whose equal-length shortest paths differ in their tagged sequence (extends the F2 rule) |
| VALVES_ON_PATH (count) | counted, since a count needs no name | unchanged rule | none |
| CONNECTED, NO_PATH, UPSTREAM_SOURCES, FEEDING_UNITS, UNITS_REACHED, CROSS_UNIT | none | process → collection networks and distribution networks → process add reach and units | none; report the share of questions whose evidence touches a network sheet (a new descriptive column beside k and u) |
| LOOP_ACTUATED_VALVE (single TAG) | none | none | two fuel switching valves get two actuators and two numbers, so the answer stays single |
| LOOKUP_*, SHEETS_OF_TAG, INSTRUMENTS_OF_ITEM, UNANSWERABLE_TAG, SAME_UNIT, COUNT_IN_UNIT, DOWNSTREAM_IN_UNIT, ROUTE_AVOIDING | fewer valve anchors | network units appear as units | none |

- **What "topological" means for the reader.** "Which valves must be closed" includes a bypass valve that is
  normally closed, and an isolation list in practice includes verifying NC valves. The thesis states that scope R
  does not use positions; only scope X's new family does.
- **Availability (ADR-0029 and ADR-0053's fixed n).** Each family needs at least 10 candidates on every sealed plant
  (10 per family per plant, as EXP-0008). A family below that on any plant is pre-registered as unavailable on v2.2.
  It is not rescued by changing the untagged weight, because that would tune the data to the questions.
- **A known consequence of the document unit (D2).** A 100-sheet plant is one document. On an untagged 100-sheet
  plant, UPSTREAM_ISOLATION and DOWNSTREAM_ISOLATION have no candidate in scope R. Both are therefore
  **pre-registered unavailable in scope R**, at both scales, before any seed is drawn. Their content is measured in
  scope X instead, by both arms. The data-effect comparison with EXP-0008 uses the families both experiments share.
- **Not reworded.** No question is reworded (user, natural questions only).

## 12. EXP-0009: pre-registered re-measurement on v2.2, two arms

### 12.1 Claims (pre-registered; revised 2026-11-23 for D1 = C)

| Claim | Arm and scope | Pass |
|---|---|---|
| **Q4 (primary)** | V2T-A2, scope R, cascade_v4_iso, S1000 − S100, two-stage cluster bootstrap | the interval contains 0 or lies above (ADR-0053, ADR-0065) |
| Q4-B | V2T-B, scope R ∪ X | the same rule |
| SB1 no harm | V2T-B − V2T-A2, scope R, paired on the same questions | the lower bound is above −0.03 (declared margin) |
| SB2 content value | V2T-B − V2T-A2, scope X isolation families, paired | the interval lies above 0 |
| K1, K2, K3, Q5 | V2T-A2, scope R | as EXP-0008 |
| Descriptive | data effect: V2T-A2 on v2.2 − V2T-A2 on v2.1 (EXP-0008) per scale, on the families both share (unpaired, the same bootstrap); X sub-scopes (untagged gold, discriminating share); POSITION_OF_VALVE accuracy; refused shares; network-touching shares; `rules.json` summaries | — |
| In P2 | X1/X2 (ladder) and E1–E4 (identity), on V2T-A2, as registered | — |

### 12.2 Gates

**Free gates (all before the first paid call; $0).**

| Gate | Pass |
|---|---|
| G0a goldens | v1 and v2.1 goldens unchanged; full suite green |
| G0b rule suite | every positive and mutation test passes; every rule and alternative non-vacuous over the 5 seeds |
| G0c build verification | `OWED_FIXES == {}`; every EXP-0009 plant built with 0 violations; `rules.json` hashed into the freeze |
| G0d composition | ADR-0059 bands pooled per scale on process sheets; network sheet statistics reported |
| G0e availability | ≥ 10 candidates per family, per scope and per sealed plant, else pre-registered unavailable; R's two isolation families are pre-registered unavailable by design (§11) |
| G0f frozen system | E9 system-side paths unchanged; one cache-only replay per A2 tier byte-identical (ADR-0060 1B) |
| G0g resolution | pair precision = recall = 1.0 at exact tags, network connectors included, on the A view and on the B view |
| G0h prompt size | every prompt of both arms fits, as in EXP-0008 M4 |
| G0i v2.1 → v2.2 diff | the same dev seeds built both ways; descriptive table of what changed (counts per rule, sheet kinds); no gate |
| G0j scorer B | the self-tests of `v2t-b-system-revision.md` §5 pass |
| G0k allocation and size | each sealed plant's documents carry the tagging written in PREREG A; each plant's total sheets lie in its band (90–110 or 900–1,100) and within 2 of its drawn target |
| G0l descriptors | per X family and plant, the share of candidates refused for a non-unique descriptor ≤ 25 %; otherwise the case returns to the architect |
| G0m expert review | if a review took place before the freeze, every finding is triaged (fix, rule change or recorded limitation; §18.5) |

**Paid gates (in P1, before the sealed plants are built).**

| Gate | Pass |
|---|---|
| G1 | V2T-A2 on the validation pair: no dev family below 50 % on both plants (as EXP-0008) |
| G1-B | the same for V2T-B, on scope R ∪ X |
| G1-B2 | V2T-B − V2T-A2 on scope R, pooled over the pair, ≥ −0.05 (point estimate); otherwise B is not run sealed and the finding is reported |

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
| EXP-0007 V2T tuning, three rounds (`EXP-0007-V2T-validation.md`) | ≈ $1.30 |

**Questions per plant.** Scope R holds 280 (the EXP-0008 recipe). Scope X adds 40 for V2T-A2 and 50 for V2T-B
(`v2t-b-system-revision.md` §4). So A2 answers 320 and B 330 per plant.

**EXP-0009, stage P1 (D5: five plants per scale, both arms):**

| Step | Basis | Estimate | Step cap (1.5×) |
|---|---|---|---|
| P1a V2T-B tuning, ≤ 3 rounds on D100g22 | V2T tuning | $1.30 | $1.95 |
| P1b V2T-A2 validation pair, 320 q per plant | M1 × 320/280 | $1.33 | $2.00 |
| P1b V2T-B validation pair, 330 q per plant | M1 × 330/280 | $1.37 | $2.06 |
| P1c V2T-A2 sealed, 5 + 5 plants × 320 | M6a × 320/280 | $7.65 | $11.48 |
| P1c V2T-B sealed, 5 + 5 plants × 330 | M6a × 330/280 | $7.88 | $11.82 |
| P1d scorer audit: the main sample plus a B stratum half its size (same judge pin and prompt, no pilot) | audit main × 1.5 | $5.42 | $8.13 (hard) |
| **P1** | | **$24.95** | **ledger hard cap $37.50** |

- **Assumptions, stated.** Cost is proportional to the number of questions, at EXP-0008's measured $/q. B's prompt
  is longer (one schema paragraph and one primer paragraph), which is not measured. The validation pair measures
  each arm's real $/q on v2.2, and the sealed caps are recomputed from it before the sealed stage.
- **The ledger binds**, not the sum of the step caps ($37.44).
- **The size bands do not move the estimate.** EXP-0008 measured a cost elasticity of 0.044 per tenfold sheets, so
  ±10 % in size changes the cost per question by well under 1 %.
- **A money stop** (cap or cost guard) is resolved by the main session without asking (user rule, 2026-11-15). A gate
  stop is not.

**Stage P2 (V2T-A2 only, after P1):**
- ladder $3.02 (cap $4.53);
- P4 identity $4.48 (cap $6.72), with the D4 decisions $0.33 (cap $0.50);
- optional F1 baseline $4.44 (cap $6.66).

P2 is estimated at $7.83 without F1 and $12.27 with it, under a ledger hard cap of $13.50.

**Program:** estimate **$32.78** without F1 ($37.22 with it); hard caps P1 $37.50 + P2 $13.50 = **$51**.

**Machine time (P1), from EXP-0008's per-unit figures** (`review-fixes.md` §6: H1000 question pool 8,585 s,
generation 421.6 s; at 1,000 sheets Cypher 1.44 h + agent 1.70 h per 560 questions, at 100 sheets 0.38 h + 0.50 h),
scaled by the question counts above:

| Block | Time |
|---|---|
| question pools (6 × 1,000-sheet: five sealed and VAL1000g22) | ≈ 14.3 h, plus the X families (unmeasured) |
| builds plus verification (11.9 s per 1,000-sheet plant, §3.3), two store views per plant | ≈ 2–3 h |
| B tuning | ≈ 1 h |
| validation, both arms | ≈ 3.5 h |
| sealed V2T-A2 (5 × 1.79 h + 5 × 0.50 h) | ≈ 11.5 h |
| sealed V2T-B (5 × 1.85 h + 5 × 0.52 h) | ≈ 11.8 h |
| audit | ≈ 1.5 h |
| **Total** | **≈ 45–47 h** of machine time |

### 12.4 Protocol

- **Pre-registration.** As EXP-0008: part A is committed before the button. It holds the claims, gates, seeds, the
  drawn size targets, the tagging allocation, caps, ledger and judge hashes. Part B and the E10 freeze are written by
  the launcher after the validation step and before the first test plant.
- **Order inside P1:** P1a tuning → E10 candidate → P1b validation (G1, G1-B, G1-B2) → E10 freeze and part B → test
  plants built → P1c sealed, A2 then B per plant → P1d audit.
- **Two views per plant.** The launcher loads the A view, runs V2T-A2, wipes Neo4j, loads the B view and runs V2T-B
  (one corpus in Neo4j at a time).
- **Launcher.** It reuses the EXP-0008 launcher structure in `data/runs/exp0009/`.
- **Stops.** The launcher stops only on a gate, a cap or an infrastructure error.
- **Start.** Nothing starts before the user's word.

## 13. Coder tasks (Sonnet, one at a time)

**Every task:**
- leaves `pytest`, `ruff` and `mypy --strict` green, and the v1 and v2.1 goldens unchanged;
- builds no EXP-0009 data and makes no paid call;
- ends with one commit proposal (files listed, one-line message), with nothing committed without the user's order.

**Done** (2026-11-23): T0, T1, T2, T3, T4, T9, T9b, T9c, T11, T7a, and T5's plan and DEXPI part (`cf2eddb`).
38 of 54 rules are wired.

**Remaining, in order** (revised 2026-11-23 after D1–D8). Sizes S/M/L follow the previous notes' scale; coder pace is
unmeasured.

| Order | Task | Size | Who | Waits for |
|---|---|---|---|---|
| 1 | **T8** Pressure-level model and PRS-*, TOG82 (pump spec breaks), TOG156, PLT-RECYCLE-CLOSURE (scope of §17.12), API14C-A4-OVERPRESSURE; wires 6 pending rules | M | coder | **nothing** (D3 = yes); uncommitted T8 files are already in the working tree on 2026-11-23 (`pressure_levels.py`, `checks_pressure.py`, `checks_overpressure.py`, tests) |
| 1′ | **T10a** SAC transcription (A-4.2, A-5.2, A-6.2, A-7.2, A-8.2, A-10.2), page-checked against the API text layer | — | researcher | **nothing: start now**, in parallel (not a coder) |
| 2 | **T7** Networks and interarea: network units, headers, per-sheet sub-headers, network connectors, capacity overflow, splitter grouping, size search on total sheets, composition per sheet kind, TOG32/141/360/33, PLT-NETWORK-CLOSURE; empties `OWED_FIXES`; wires 5 pending rules | L | coder | T8 (one coder at a time; D4 = as proposed) |
| 3 | **T6** Documents and conventions (§5, §18.2): `DocumentRecord` (runs of consecutive trains, `trains_per_document` declared from the median trains per 100 total sheets on v2.2 dev plants after T7); per-document draws of manual-valve tagging (0.75 untagged), spare naming, on-off letter and PV without bypass, from new streams (v2.1 per-train draws taken, values ignored); config override `handbook.document_untagged` for the stratified sealed plants; untagged manual valves (TOG113); `p_pump_reducers` 0.75; gold side of scope R (untagged refusal, FLOW_PATH tie rule, refused-share report; isolation families pre-registered unavailable); v2.1 question hash unchanged | M | coder | T7 |
| 4 | **T10** `rules/sac.py` from T10a; API14C-3.4-TWO-LEVELS, API14C-SAC, TOG207-HX-PSD-BOTH-SIDES, TOG236; cheap SAC devices added, the rest DEFERRED one by one; wires 4 pending rules | M | coder | T10a, T8 |
| 5 | **T12a** Expert-review package (§18.5): the 12 sheets drawn by the fixed rule, exported with the demo drawing export plus a legend sheet; the checklist printed from the registry | S | coder | T6, T7, T10 (the plants are complete) |
| — | Expert review and triage | — | the user's reviewer; architect triages | T12a |
| 6 | **T14** V2T-B system files (`v2t-b-system-revision.md` §3): B store view, VALVE_SET and POSITION types, `scoring_b.py` and its self-tests, `policy_b.py`, the import-isolation test; G0f stays green | M | coder | T6 |
| 7 | **T15** Scope X (gold side): OPEN_VALVES_TO_ISOLATE (up, down), UPSTREAM_ISOLATION_X, DOWNSTREAM_ISOLATION_X, POSITION_OF_VALVE, descriptor gold and refusal, the A2 adapter (TAG_SET), discriminating-share report | M | coder | T14 |
| 8 | **T12b** Composition report per sheet kind; the ch.20 comparison table (the annotation by the main session) | S | coder and main session | T7 |
| 9 | **T16** Fixes from the review findings, if any (designed by the architect first) | ? | coder | the review |
| 10 | **T13** EXP-0009 launcher: ledger glob skips `reports/` (with a test on a copied call file); ids `g22` and `…B`; seed draw plus size-target draw in the bands; stratified tagging allocation; two-view ingest; stages P1a–P1d; caps; PREREG A template | L | coder | all of the above |

**A coder can start now:** T8 (or finish it: its files are already in the working tree, uncommitted), then T7. The researcher can start T10a at the same time.

## 14. Risks

- **Composition drift.** Networks raise stubs per process sheet; FIC min-flow loops and SAC devices raise
  instruments per sheet. Mitigations: per-sheet sub-headers, cheap devices only, and the G0d gate. A failed band
  stops the run (U4 rule of ADR-0065): adjust a declared knob as a recorded generator change, or report the miss.
- **Availability.** Under the document unit, R's isolation families are unavailable by design (§11). The other
  families are measured by G0e and are not tuned.
- **B does not reach G1-B2.** Then B is not run sealed, the money of P1c-B is not spent, and the finding (the
  revision harms the replication scope) is reported. EXP-0009 still delivers Q4 on A2.
- **Descriptors are not unique often enough** (G0l). Then the case returns to the architect before E10.
- **Between-plant spread grows on v2.2.** A 100-sheet plant is now wholly tagged or wholly untagged, which EXP-0008's
  plants never were. The stratified allocation keeps the mix equal across scales; five plants per scale keep the
  interval honest (§18.3).
- **Machine time** of about 45–47 h for P1 (§12.3).
- **Unverified sources.** Liptak 1995 cannot be page-checked. It supports nothing that is encoded.

## 15. Decisions for the user

**Decided by the user on 2026-11-23.** What each decision changed is in §18.

| # | Decision | Options put | Recommended | **Decided** | What it unblocks |
|---|---|---|---|---|---|
| D1 | System for EXP-0009 | A frozen V2T-A2 · B revision V2T-B · C both | A | **C: both arms on the same v2.2 plants** (credit will be topped up) | T14, T15; ADR-0067 |
| D2 | Sampling units and weights | as proposed (per train, 1 : 1) | as proposed | **"whichever gives the more accurate result"**: calibrated from evidence (§18.2): conventions per document, untagged 0.75, pump reducers 0.75, the rest kept with reasons | T6 |
| D3 | Hidden ordinal pressure model under ADR-0021 (clarification) | yes · no | yes | **yes** | T8 |
| D4 | Networks: FL, CHD, CWS/CWR, LPS/MPS/CD, FG plus interarea; counted in the sheet target | this set · fewer · not counted | this set, counted | **as proposed** | T7 |
| D5 | EXP-0009 scope | P1 now, P2 later · everything at once; the user added 3+3 plants and sheet bands for study | P1 now | **P1 now**, shape after the analysis of §18.3: **5 + 5 plants, size bands 90–110 and 900–1,100, both arms**; $24.95, cap $37.50 | T13 |
| D6 | The deferred list (§4.9) | accept · pull items in | accept | **re-triage asked** → §4.9 bins, explained in §18.4 | T10 (bin "now") |
| D7 | Expert review of 12 sheets | a reviewer exists · not | only if available | **yes; the user finds the expert** → plan §18.5 | T12a |
| D8 | Exchanger isolation policy (§17.5) | A fixed: no process-side isolation, utility blocks allowed · B sampled per train | A | **A** | nothing to build: T9b already built A |

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

**Addendum 2026-11-23 (T9 findings, by the architect).**
- **Pages re-read** against the PDF (pdftotext, 1-based PDF page numbers): 207 (PDF 225), 270–271 (PDF 286–287),
  294–295 (PDF 310–311), 305 (PDF 321), 321–322 (PDF 337–338).
- **Offset correction.** The offset is −18 up to p.237, −17 from p.243 to p.267 and **−16 from p.270**. The line
  above ("−17 at p.265–271") is wrong for p.270–271.
- **p.305 is now page-checked.** "A stream that goes to a large storage tank possibly doesn't need to be flow
  controlled; an intermittent flow may not need to be flow controlled either." §6.3 had marked it unverified.
- **p.207 says less than §4.5 claimed.** See §17.5.

## 17. T9 findings and fixes (2026-11-23)

### 17.1 What T9 found

T9 (`6f7f906`) wired ten plant-level checks and changed no generator line. Four checks fail on today's plants
(30-sheet plants, seeds 1–5). The failures are recorded as strict xfails in `tests/v2/t9_support.py`
`KNOWN_FAILURES`. I re-ran the four checks for free on 2026-11-23 (scripts in the session scratchpad, not in the repo).
I classified every violation by pattern and role. The counts below come from that run.

| Rule | v2.2 violations, seeds 1–5 | v2.1 | What they are |
|---|---|---|---|
| TOG271-ONE-CV-LIQUID | 3, 1, 4, 6, 3 | 4, 3, 4, 6, 4 | (i) a bypass TV of the next unit's exchanger counted as a second valve in series; (ii) a farm-transfer FV (U4), then the filter package's optional FV (U7), with no container between |
| TOG295-INVENTORY-ONCE | 0, 3, 1, 1, 0 | same | additive day tanks (U8, `additive_tank`) with an LT and no level loop; one blend vessel (seed 2 V-1101) whose only "gas" lines are its capped vent and thermometer trims |
| PLT-STREAM-CLOSURE | 39, 40, 38, 35, 40 (192 in all) | similar | see §17.4: 52 are lines the flowsheet join continues, 11 end at a battery-limit valve, 71 are open process ends at the plant boundary, 58 are PSV outlets and fuel-gas bleeds |
| TOG207-HX-NO-ISOLATION | 2, 4, 2, 1, 5 of 11, 17, 8, 10, 16 exchangers | similar | `utility_supply_block` on a cooling-water or steam nozzle; a compressor's own discharge block upstream of its aftercooler (one side only) |

**Verdicts in short.**
- TOG271: check (a) and generator (b).
- TOG295: check (a).
- PLT-STREAM-CLOSURE: check (a), then a new task T7a (b), then T7 (c).
- TOG207: check and statement (a), with a policy choice (D8).

### 17.2 TOG271-ONE-CV-LIQUID

**The text (p.271, re-read).** "Don't put more than one control valve on liquid-filled pipelines. A vessel that is
flooded with liquid is considered as a piece pipe […]. There are a few exceptions to this rule, but these cases are
very rare. On gas pipes there may be more than one control valve, but they cannot be very close to each other."

**Case (i): too strict, change the check.**
- **What the book says.** A bypass TV does not throttle the line. Toghraei p.321 says it outright: with the valve on
  the bypass, "we haven't changed the total flow rate". On p.322 the two-valve variant uses "parallel control […] to
  maintain a constant flow rate", and a single three-way valve can replace the pair.
- **Why the series count is wrong.** Two valves fight only when both set the same flow. A split valve sets how the
  flow divides, not how much flows.
- **Check change** (in `rules/control_graph.py`, used by `checks_control.py`):
  - Move `_bypasses_a_heat_transfer_item` from `checks_exchangers.py` to `control_graph.py`, unchanged, as
    `bypasses_a_heat_transfer_item`.
  - Add `split_valves(view) -> frozenset[str]`. It returns every valve of a TEMPERATURE loop whose controller
    senses the same point as a temperature loop whose valve bypasses a heat-transfer item. That covers the bypass TV
    alone and the TOG322 pair. *Corrected 2026-11-23 (§17.11):* the pair is drawn as two independent TT → TIC → TV
    loops on one sensed point, not one controller with two valves, so T9b groups the valves by sensed point.
  - `check_one_cv_liquid` counts only control valves that are not split valves. Each route where it discounted one
    is counted under the exception `split_valve` in the result, so `rules.json` shows how often it happens.
  - Registry: TOG271 sources gain `tog("p.321–322")`, page-checked.
- **Measured effect** (free re-run with the split valves left out): v2.2 drops from 3, 1, 4, 6, 3 to **1, 0, 1, 2, 0**.
  Every remaining violation is case (ii).

**Case (ii): a real violation, so the generator changes on v2.2.**
- **The four pairs:** FV-13006 → FV-14002 (seed 1), FV-17008 → FV-18002 (seed 3), FV-1010 → FV-2002 and
  FV-13010 → FV-14002 (seed 4).
- **Why the generator is wrong.** In each pair the second FV is the optional outlet flow loop of the filter package
  (`patterns/filter_package.py` `_flow_loop`, drawn at `p_optional_instrument`). A filter package has no pump and no
  container, so the flow through it is always set upstream: by the farm's transfer loop, a vessel's LV or a pump.
  Its own FV is therefore always a second valve on the same liquid line.
- **Generator fix (v2.2 only, task T9b).**
  - In `build_filter_package`, `flow_loop = ctx.chance(...)` is still drawn. With `ctx.trim.handbook` on, a true
    draw builds a **flow indicator** `FE`, `FT → FI` on the outlet instead of `FE`, `FT → FIC → FV`.
  - Add the helper `flow_indicator(ctx, style, element)` to `instruments.py`, modelled on `totaliser` (one shared
    number, so S8 holds).
  - Skipped body and numbering draws inside the trim follow T3's precedent for the TOG314 dosing valve
    (`blending_parts.dosing_header`).
  - Rule comment at the branch:
    `# rule TOG271-ONE-CV-LIQUID: no flow valve on the filter package, its feed's flow is set upstream (Toghraei 2019 p.271)`
- **What remains:** 0 on seeds 1–5. That is a prediction from the two measurements above, to be confirmed by T9b.
  Other pairs may exist only on larger plants, which is why T9b also verifies dev plants at 100 and 1,000 sheets
  (§17.7).
- **Not checked, and recorded:** p.271's gas half ("not very close to each other") needs distances. A P&ID has none.

### 17.3 TOG295-INVENTORY-ONCE

**The text.**
- Table 15.1 (p.295): gas container → P-loop; non-flooded liquid container → L-loop; flooded → F-loop.
- p.270: "In a non-flooded pressurized vessel, both pressure and level may be important parameters and **you may
  choose** to control both of them. In a storage tank for a liquid we only control level." Rule 8: "Always control
  the pressure for unit operations […] whose function depends on pressure. Examples are flash drums, two-phase flow
  separators, and hydrocyclones."
- p.305 (now checked): flows to a large storage tank and intermittent flows may not need flow control.

**Additive day tanks: too strict, change the check.**
- **What the generator draws.** The U8 day tank is filled through a manual block valve (`tank_fill_block`), which is
  an intermittent fill, and drained by metered dosing pumps. Every such tank on seeds 1–5 carries an LT, and most
  carry LSL switches too.
- **Reading.** I read p.270's "we only control level" for a storage tank as naming the *variable*: level, not
  pressure. The operator controls it from the transmitter and its alarms, and p.305 says such flows often need no
  loop. That is exactly the tank-farm case, which already passes.
- **Check change.** `storage_tank_batch` is no longer tied to the role `tank`. It applies to any atmospheric `Tank`
  that has no level loop **and has a level transmitter** (the LT is now required, so the exception cannot hide a
  tank nobody watches).
- **Measured on seeds 1–5:** every `Tank` has at least one LT, so no new failure appears.
- **Registry:** sources gain `tog("p.305")`.

**Blend vessel: too strict, change the check.**
- **What the generator draws.** V-1101 has no process gas line. Its "gas" lines are trims: a top tee with a blinded
  thermometer flange and a vent valve with a cap (StreamKind TRIM). It holds a liquid inventory and has its level
  loop.
- **Why it is not a violation.** Rule 8 does not require a pressure loop for a blending vessel, and p.270 makes
  pressure control on other pressurized vessels a choice.
- **Check change:**
  - Gas services count only on lines whose `record.stream_kind` is not TRIM.
  - A pressure loop is **required** (exactly one, or `pressure_floating_on:<id>`) when a non-trim gas line touches
    the container, or when its role is in a declared `PRESSURE_DEPENDENT_ROLES` in `control_graph.py`. That set is
    `flash_drum`, `separator` and `suction_ko_drum`, after Toghraei's examples. The coder lists any other role that
    should join (column accumulators) and reports it.
  - Otherwise the container may have **at most one** pressure loop. None is the exception `pressure_optional`, which
    cites p.270.
- **What remains:** 0 on seeds 1–5 (a prediction; T9b confirms it).
- **What is still missing, and recorded.** A closed liquid vessel needs somewhere for its vapour to go: a vent,
  blanketing or a pressure loop. The generator models none of these, and §4.9 already defers blanketing and VRU. The
  thesis limitations list states it.

**Mutation tests (T9b):**
- remove the LT from a farm tank, so the check fails;
- add a second LIC to a drum, so it fails;
- remove the PIC from a flash drum that has no floating partner, so it fails.

### 17.4 PLT-STREAM-CLOSURE

**The check reads the wrong layer (a).** It walks `unit.instance.plan.lines`, the pattern-level lines. Every port
line ends open there by construction, even where the flowsheet joins it to the next unit. That accounts for 52 of
the 192 ends. Another 11 are in-ports that start at a battery-limit block, with the blind one part further in. The
check only recognises a blind as the last part.

**Check change (T9b).**
- Find dead ends on the plant flow graph (`flow(view.graph)`, after the joins): a non-equipment node with flow
  out-degree 0 (a sink end) or in-degree 0 (a source end).
- Each dead end is declared, tried in this order, as one of:
  - `battery_limit`: the node's role, or the role of its one neighbour on the line, is a role of the
    `trims_valves.battery_limit` group (`battery_limit_block`, `battery_limit_blind`, plus the check-valve role T11
    adds);
  - `utility_stub`: the node's line is UTILITY_STUB;
  - `end_fitting`: as today.
- Otherwise it is a violation. `checked` is the number of dead ends. Each violation's detail names the stream kind,
  the pattern and the role.

**What then remains: 129 ends over the five seeds.**

| Group | Count | Owner | Fix |
|---|---|---|---|
| Unjoined process out-ports at the plant boundary: flash-drum vapour (28), reactor gas (6) and liquid (2), column vapour (9), distillate, bottoms and side draw (6); non-port process ends: vacuum liquid-ring pump discharge (4), compressor suction KO-drum liquid (2) | 57 | **T7a** (new) | TOG34 battery-limit group on the open end; declared `battery_limit` ("leaves the modelled region") |
| Unjoined in-ports without a battery limit: farm receipts (4), additive fill (2) | 6 | **T7a** | the same, forced at the plant boundary (the `p_battery_limit` coin is still drawn; its value is ignored there) |
| Reactor `recycle_gas` in-port with no paired compressor (core `U3` without `U2`). *Corrected in §17.12:* 2 of the 8 are U3+U2 cores whose compressor is never joined back, which is a wiring bug fixed in T9c; 6 stay for T7a | 8 | **T7a** | becomes makeup gas over a battery limit: stream kind PROCESS, roles `makeup_gas_block` / `makeup_gas_check`. Dropping the line was rejected: it would remove v2.1 draws (§5 randomness rule), and a reactor fed with gas from outside is ordinary |
| PSV outlets (`psv_outlet_block`) | 50 | **T7** | tie-in to the unit's FL sub-header (TOG32–34) |
| Fuel-gas double-block-and-bleed bleeds (`dbb_bleed_valve`) | 8 | **T7** | tie-in to FL: hydrocarbon, so never open to the atmosphere (fluid class §6.1) |

- **After T7a:** 58 remain, all owed to T7.
- **After T7:** 0 (a prediction).
- **If D4 drops FL**, those 58 end at a declared `network_stub:<service>` (the UTILITY_STUB analogue), so closure
  holds without the network sheets.

**T7a (new task, decision-independent, size M).** The post-join pass that T7 also needs: it adds parts to a unit's
plan after the flowsheet has decided its joins, and before sheets are assigned.
- **Placement.** `src/plantgraph/benchmark/v2/boundary.py`, v2.2 only.
- **Battery limit.** It calls the existing `battery_limit` builder with presence forced, so T11's TOG34 variants apply
  to these ends unchanged.
- **Rule comment:**
  `# rule TOG34-BL-ISOLATION: a plant-boundary crossing gets the battery-limit isolation (Toghraei 2019 p.34)`
- **Prefix stability.** A port that is open in an n-unit plant may be joined in an (n+1)-unit plant. S15 is therefore
  restated like the network sheets (§7): "process parts are prefix-stable, boundary groups are a function of the
  included units". T7a measures it.

**Why a battery limit rather than an FG or flare tie-in for off-gas.**
- **Alternative:** off-gas and side products could tie into the FG network or the flare.
- **Rejected because** no checked page says which, and §6.5 already ends every header at a battery limit toward
  out-of-scope treatment.
- **The boring option is consistent:** the region's boundary is a battery limit, which is TOG p.34, checked.

### 17.5 TOG207-HX-NO-ISOLATION

**The text (p.207, re-read in full).**
- "Isolation valves, however, don't exist for all heat exchangers. The requirement […] depends on the service of the
  heat exchanger and the maintenance policy of the plant. Some companies don't put any isolation valves around their
  heat exchangers. […] Therefore, placing isolation valves around heat exchangers is **subjective**."
- On bypass pipes: "the majority of companies don't put bypass pipes around heat exchangers because they cannot
  afford to send on a stream without its temperature adjusted."
- "One case in which placing isolation valves and a bypass pipe around a heat exchanger is justifiable is […] an
  available spare heat exchanger or […] a clean-in-place (CIP) system or […] mechanical-in-place system (MIP)."

**Verdict: the rule as encoded was stronger than the page (a).**
- **What §4.5 claimed.** It said "no isolation valves […] unless a spare or a cleaning system". The book says
  isolation is a company policy.
- **What the argument is about.** The book's argument concerns taking the exchanger out of the **process** stream
  (the stream goes on "without temperature change"). A block valve on a cooling-water or steam nozzle isolates the
  utility supply, which is the common battery-limit practice at a consumer. The page does not address it.
- **One valve is not isolation.** A single block on one side, such as the compressor discharge block before an
  aftercooler, cannot shut the exchanger in.

**Restated rule** (registry statement, same id; D8 = A):
> Isolation at an exchanger is company policy (p.207). v2.2 follows the policy with no isolation on the process side:
> no exchanger has blocks on all of its process inlets and outlets, and none has a hand bypass around its process
> side, unless it has an installed spare or a cleaning-in-place system. Utility-side valves are outside the rule.

**Check change (T9b, `checks_exchangers.py`).**
- **Nozzle runs that are skipped:**
  - a run whose service is in `UTILITY_SERVICES`, counted under the exception `utility_side_block` when it holds a
    block;
  - a run whose service is FL, or that holds a `psv_inlet_block` (a relief branch, which belongs to
    TOG224/TOG207-PSD; seed 5 u3-t1 showed one).
- **Valves that do not count as blocks:** control-valve bodies (`is_control_valve`). The `hx_main_control_valve` of
  the TOG322 pair has a ball-valve body.
- **When it is a violation:**
  - **isolation:** every process inlet run *and* every process outlet run holds a block valve;
  - **bypass:** `_manual_bypass`, unchanged.
- **Exception codes:** `has_spare` (as now) and `cleaning_system`. The second is declared and never drawn, so its
  count is 0 and the thesis says so.

**Measured on seeds 1–5** (free re-run of the restated logic): no exchanger is isolated on both process sides; no
hand bypass; utility nozzle runs holding a block: 2, 4, 2, 1, 3; one-sided process blocks only at aftercoolers
(after control-valve bodies and relief runs are excluded). So the
restated check passes on today's plants with no generator change. T9b confirms it.

**A link that is easy to miss.** The utility-side blocks now matter for T10: an exchanger side that can be blocked in
and is fed from a higher level needs its PSD (TOG207-HX-PSD-BOTH-SIDES). T10 reads `utility_side_block` from this
check's helper rather than finding the blocks again.

### 17.6 The coder's other interpretation choices

| Choice (T9 report) | Verdict |
|---|---|
| TOG267: one upstream FE per loop is enough (ratio loops sense two) | accepted |
| TOG270: counted per discharge route | accepted |
| TOG271: only routes that are liquid all the way (P, CD, CWS, CWR); reactors count as flooded | accepted. A flooded reactor is a declared assumption (`FLOODED_CONTAINER_ROLES`) and is listed in the limitations |
| TOG207: any block on a nozzle run counts, utility blocks included | **overturned** (§17.5) |
| A bypass counts only without a CV | accepted; p.321 confirms the CV bypass is control |
| `# rule` comments of pure checks sit at the check function | accepted |
| TOG295 exceptions derived by the check, not written by the pattern | accepted; §6.3 amended |

### 17.7 When `verify_plant` is wired into v2.2 generation

**Recommendation: wire it now (in T9b), with an explicit owed list. Do not wait until T7.**
- **The owed list.** `rules/owed.py` holds `OWED_FIXES: dict[str, str]`, which maps a rule id to the task that owes
  its fix. After T9b it is `{"PLT-STREAM-CLOSURE": "T7"}`.
- **What generation does.** `generate_plant_v2` with a `GeneratorConfigV22` runs `verify_plant` and raises
  `RuleViolationError` on any violation of a rule **not** in the list. A row of an owed rule is written with
  `RuleRow.owed_by = "T7"` (new optional field, default None) and does not raise.
- **Corpus report.** `ingest synthetic --generator v2.2` writes `rules.json`.
- **Gate G0c** (§12.2) additionally requires `OWED_FIXES == {}`, so no EXP-0009 plant is built while a fix is owed.
- **Shrinking the list.** T7a and T7 each remove what they close, and each task's tests assert the list shrank.
- **Why:** every later task then runs under build-time verification. A regression in any of the 25 (then 27) wired
  rules stops the build at once instead of surfacing at G0c.
- **The alternative and why it is rejected:** wire it after T7. It is simpler, but four or more tasks would run with
  verification only in tests on five 30-sheet seeds.
- **v2.1 generation stays untouched** (goldens); v2.1 is verified only in tests.

**Measured in T9b (owed by T1; I found no recorded figure).**
- **Verification time.** Measure verification time on one 1,000-sheet v2.2 dev plant. The yardstick is generation
  time: EXP-0008 measured 390.99 s on H1000g21p1.
- **Why it may be slow.** `routes_between_containers` enumerates simple paths, and parallel spare pumps multiply
  them.
- **Threshold.** If verification takes longer than that generation time, T9b reports and stops. The architect then
  bounds the route enumeration, for example by collapsing spare sets to one branch.
- **Dev plants.** Also verify at least one 100-sheet and one 1,000-sheet dev plant (seeds the coder picks and
  reports, never EXP-0009 seeds; nothing ingested, nothing into Neo4j). This finds violations that five 30-sheet
  seeds do not reach.

### 17.8 Revised order and how the failures map onto the remaining tasks

| Order | Task | Waits for | What it does about the T9 failures | Owed list after it |
|---|---|---|---|---|
| 1 | **T9b** | nothing | TOG271 (check + U7), TOG295, TOG207, the closure check on the graph; wires API14C-A8-FSV and API14C-A8-PSV (the 2 `unassigned`, v2.1 behaviour, cheap); `verify_plant` with the owed list; dev-plant verification and timing | closure → T7 |
| 2 | **T7a** | nothing | 71 boundary ends get a battery limit; makeup gas for unpaired reactors | closure → T7 (58 ends) |
| 3 | T11 | nothing (unless the user vetoes an alternative) | TOG322 pair: the TOG271 split rule already covers it; TOG34 check variant applies at T7a's ends too | unchanged |
| 4 | T5 (plan + DEXPI) | nothing; store part D1 | none. TOG224 CSO blocks sit on the PSV outlets T7 ties in | unchanged |
| 5 | T8 | D3 | PLT-RECYCLE-CLOSURE must not see the T7a makeup gas (now PROCESS); TOG156 sees its check valve | unchanged |
| 6 | T7 | D4 | ties the 58 PSV outlets and bleeds to FL; drains by TOG141 | **empty** → `verify_plant` fully raising |
| 7 | T10 | researcher transcription; D3 | TOG207-PSD uses `utility_side_block` (§17.5) | empty |
| 8 | T6 | D1, D2 | none. HCVs stay tagged (TOG113); `is_control_valve` reads the HV/HCV tag prefix | empty |
| 9 | T12 | D7 for the review | the composition report shows the U7 change (FV and FIC become FI) and the boundary groups per sheet kind | empty |
| 10 | T13 | D1, D5 | G0c checks `OWED_FIXES == {}` and hashes `rules.json` | empty |

**Decision-independent now, in this order:** T9b, T7a, T11, T5 (plan and DEXPI part). T8 is also small, but D3 is
still open.

**When `verify_plant` fully guards generation:** it is wired in T9b. It raises on every rule except
PLT-STREAM-CLOSURE until T7 lands, and on everything after that.

### 17.9 Consequence for v2.1 and the thesis

v2.1 data is never changed (§14). The same findings hold for the v2.1 corpora EXP-0008 measured, and the thesis's
limitations list records them as properties of the v2.1 generator:
- **TOG271:** a filter package after a farm transfer puts two flow valves in series (1, 0, 1, 2, 0 on seeds 1–5).
- **PLT-STREAM-CLOSURE:** relief outlets, bleeds and plant-boundary process ends stay open.
- **TOG295:** no change, since the restated check passes v2.1.

None of these touches a question's gold (gold is topological). An open end only means that a path stops there,
in the gold and in the store alike.

### 17.10 Open questions

1. **D8** (§15): closed 2026-11-23, the user chose A.
2. **Column roles.** Should `PRESSURE_DEPENDENT_ROLES` include the column's accumulator? Toghraei's rule-8 examples
   do not name it. The coder reports which roles exist, and the architect decides in review.
3. **ADR-0066** counts: closed. The decision text reads 54 / 35 / 19 / 15 (amended 2026-11-23).

### 17.11 After T9b (`3ea62cb`): two dev-plant findings, one correction, and the verification time

**Status.** On seeds 1–5, TOG271, TOG295 and TOG207 have 0 violations. PLT-STREAM-CLOSURE has 129, owed to T7, as
§17.4 predicted. The 100-sheet v2.2 dev plant of seed 7 raises on two rules. I re-read both cases on that plant
with verification stubbed out.

**F1. TOG295 on discharge KO drum u11-t5 (V-1102, `ScrubbingSeparator`). Verdict: a floating exception, no PIC.**
- **What is drawn.** The drum sits on unit 11's compressor discharge (a `RotaryCompressor`, so PD). Its inlet comes
  from the aftercooler's `recycle_takeoff_tee`, its gas leaves through `top_outlet_tee`, and its liquid leaves
  through LV-11017. No valve stands between it and the aftercooler.
- **What holds its pressure already.** The PD spillback loop PT → PIC → PV of TOG316 (p.316, Table 15.10) senses the
  aftercooler and holds that discharge pressure. The drum is the same gas inventory as the aftercooler.
- **Why no PIC.** A PIC of its own would be a second pressure loop on one inventory. Table 15.1 (p.295) and the rule
  itself forbid that. p.270 says the same for compressors: control either flow or pressure.
- **Check change.** `_floats_on` accepts as a partner any item whose **pressure loop senses an item joined to the
  container by gas pipe with no control valve between**, an exchanger included, not only a container. The code
  stays `pressure_floating_on:<id>`, here `pressure_floating_on:<aftercooler id>`. Sources: p.295 and p.316.
- **Role set.** Add `discharge_ko_drum` to `PRESSURE_DEPENDENT_ROLES` all the same. It is a two-phase separator,
  which rule 8 on p.270 names, and the set should list it like `suction_ko_drum`. It changes nothing here, because
  process gas touches the drum anyway.
- **What remains open.** A discharge drum behind a *dynamic* stage (an anti-surge FIC, no pressure loop) may find no
  partner. If the build raises on one, it returns to the architect. It is not pre-decided here.

**F2. TOG316 on "control valve" u29-t48. Verdict: a check bug, not a generator bug. This does not confirm the
coder's reading.**
- **What u29-t48 is.** It is BFV-29002, a `ButterflyValve` with the role `compressor_discharge_block`. That is the
  manual discharge block between the check valve and the aftercooler of reciprocating compressor K-2901. No
  controller drives it.
- **Why the check flagged it.** `checks_compressors._capacity_problem` counts any node whose class is in
  `CONTROL_VALVE_BODY_CLASSES`. A butterfly valve can be a control-valve body, so a block valve that happens to be
  drawn as one matches.
- **Fix.** Use `control_graph.is_control_valve` (driven by a controller, or an HCV) in `_capacity_problem`, which is
  the same rule every T9 check uses.
- **Audit.** Do the same search over the T3/T4 checks for any other class-only CV test, and report it.
- **The generator** is right here. T3's fix did not miss a path.

**F3. Correction to §17.2.** The TOG322 pair is two independent TT → TIC → TV loops on the same sensed point (p.322,
"parallel control"), not one controller. T9b groups split valves by sensed point. §17.2 is corrected in place.

**F4. The verification time (fact, from the coder's T9b profiling).**
- **Measurement.** Verification at 1,000 sheets is too slow. The cause is **not** route enumeration, as §17.7
  feared. It is `flow(graph)` in `rules/checks_v21_plant.py`, which rebuilds the piping graph on every call: 654
  calls of about 42 ms each on a 100-sheet plant, about 27 s.
- **Fix, now with a coder:** build the piping graph once per `RuleView` and cache it there. The checks keep their
  signatures.
- **After the fix,** T9b's timing on one 1,000-sheet dev plant is re-measured against the 390.99 s generation
  yardstick of §17.7. Only if it is still too slow is route enumeration looked at.

**Order.** The cache and the F1/F2 check fixes go in before T7a. The 100- and 1,000-sheet dev plants must build
without a non-owed violation before T7a starts.

### 17.12 The discharge KO drum behind a centrifugal stage (1,000-sheet seed 7, after `4d534dc`)

**The case.**
- **What is drawn.** Drum u101-t5 (V-10102, `discharge_ko_drum`) sits behind CentrifugalCompressor u101-t2 and air
  cooler u101-t3. The stage's recycle carries only the anti-surge FIC, and TOG295 finds no pressure loop to float on.
- **What I verified on seeds 3 and 5.** The case is general, not a one-off. In every U3+U2 core the stage's
  `compressed` out-port and the reactor's `recycle_gas` in-port both stay **open**. `flowsheet.wire` joins only a
  unit's first in-port (or a `collects` port), and U3 is wired before its U2 exists. The grammar says
  `Core := U3 [U2 on its gas outlet]`, and the reactor's port is named `recycle_gas`. Both state the intent of a
  recycle-gas loop that the wiring never closes.
- **Not verified on the 1,000-sheet plant.** U2 occurs only inside U3+U2, so u101 is such a core. T9c confirms it.

**The page (re-read, p.316–319).**
- p.316: "for centrifugal gas movers, there are two control systems needed: capacity control, and anti-surge
  control".
- Table 15.11 (p.317) gives suction throttling as "common" for centrifugal machines, and VSD as a general method.
- p.318: the capacity loop may be a flow or a pressure loop.

**What the stage already has.** Both systems:
- **anti-surge:** FE → FIC → FV on the recycle;
- **capacity:** a suction pressure loop PT → PIC → PV on the suction drum (`compression_parts._suction_pressure_valve`)
  or, with a VSD, PT → PIC → AEF (`machine_instruments`).

So the stage's capacity is already controlled, and its discharge pressure is set by the system it delivers into.

**Verdict: (d). Close the recycle loop in the wiring; the drum then floats on the reactor loop's pressure control.**
- **(a) rejected.** A discharge or load PIC would be a second capacity manipulator on a machine that already has one
  (p.316 asks for one capacity control and one anti-surge). Liptak's load loop with anti-surge decoupling is the
  1995 volume, which has no text layer and could not be page-checked (§16).
- **(b) rejected.** A PIC on the drum would be a second pressure loop on the reactor loop's gas inventory (Table 15.1,
  p.295).
- **(c) is right in principle but has nothing to find.** The discharge has no downstream today; the stream ends open.

**Generator change (v2.2 only, new task T9c, size S, decision-independent).**
- **Where.** `src/plantgraph/benchmark/v2/flowsheet.py` (`wire`, or the planner step that builds a composite core).
- **What.** When a U2 is built as the second half of a U3+U2 core, set the U3 instance's `recycle_gas` in-port source
  to the U2's `compressed` out-port (`with_in_port_source`), and drop that out-port from the open outs.
- **What it does not touch.** It adds no draw, so the randomness rule (§5) holds.
- **Rule comment:**
  `# rule PLT-STREAM-CLOSURE: the recycle compressor returns its gas to its reactor (Toghraei 2019 p.24)`
  There is no checked page for the loop itself; the basis is the grammar's own intent (DESIGN).
- **Prefix stability.** A plant cut between U3 and U2 keeps the reactor port open, and T7a's makeup gas closes it.
  S15 is restated as for boundary groups (§17.4).

**Check change (TOG295 `_floats_on`, same task).**
- The partner is the nearest pressure loop reachable from the container along **process pipe, in the flow
  direction, without a throttling control valve**.
- Flooded items count as pipe (p.271), and split valves (§17.2) do not count as throttling.
- The route need not be gas all the way: a liquid-full stretch passes the pressure too. Here the recycle joins the
  liquid reactor feed.
- The partner is then the reactor section's separator loop (or the item it floats on in turn), and the exception
  code stays `pressure_floating_on:<id>`.

**Knock-on effects.**
- **T8, PLT-RECYCLE-CLOSURE.** The rule says "a recycle returns inside its unit through an RO or a CV". That is
  stated for spillbacks (p.317). The rule's scope becomes: spillback and min-flow recycles return inside their unit
  through a reducing element. A reactor recycle-gas loop returns inside its **core** (U3+U2) and is driven by its own
  compressor, so it needs no reducing element.
- **§17.4 counts.** 2 of the 8 open `recycle_gas` ends on seeds 1–5 are U3+U2 cores. T9c closes them, and T7a's
  makeup gas is left with 6. The open `compressed` ends (2) also close; they had been counted among the boundary
  ends.
- **If the build still raises.** If the partner search still finds nothing on the 1,000-sheet plant, the case
  returns with the route printed. Nothing beyond that is pre-decided.

**Class-only control-valve tests listed by the coder.**

| Place | Verdict |
|---|---|
| `checks_compressors.py` `_valves_on_lines` (class + `PV-`) | correct today: a manual valve never carries a `PV-` tag, and an untagged one (T6) has none. Switch to `loop_of(...).variable == PRESSURE` in T9c so the check does not depend on tag letters |
| `checks_pumps.py` `_throttle_problem` (class + `FV-`) | the same: switch to `loop_of(...).variable == FLOW` in T9c; no result changes |
| `checks_v21_instruments.py` S4 | no change. It starts from the actuator and asserts what it drives, so it is not a class-only CV test |
| `checks_v21_instruments.py` S7 | no change. It selects on-off valves by tag letters, which is what the invariant is about; untagged valves fall out |

**Order.** T9c goes next, then T7a. The 1,000-sheet seed-7 dev plant must build with only PLT-STREAM-CLOSURE owed
before T7a starts.

## 18. The user's decisions of 2026-11-23 and what follows from them

### 18.1 D1 = C: two systems on the same plants

- **What it means.** EXP-0009 runs two systems on the same v2.2 plants:
  - the frozen V2T-A2 (freeze E9), which measures the data;
  - the revision V2T-B (freeze E10), which sees `operating_position` and names untagged valves.

  The full design is `40-design/v2t-b-system-revision.md`, recorded in ADR-0067 (proposed).
- **What relaxes for B.** Only system-side things:
  - the property in B's store;
  - B's schema-text and primer paragraphs;
  - the VALVE_SET and POSITION answer types and their scorer;
  - the new scope X families.
- **What does not relax.** Anything in the plant data, because A2 must ingest the same plants. So TOG73, the
  functional-only gauge tags and parallel loop numbering stay deferred (v2t-b note §1).
- **How the effects are separated:**
  - **data effect:** V2T-A2 on v2.2 against V2T-A2 on v2.1 (EXP-0008), unpaired;
  - **system effect:** V2T-B − V2T-A2 on the same questions, paired, in scope R ("no harm") and scope X ("value of
    the content").

### 18.2 D2: weights and units calibrated from evidence

**How I read the decision.** "The more accurate result" means the generator closest to real drawing sets. It never
means the weight that gives the retrieval system the higher score. Choosing a weight for the score would tune the
data to the system, which §11 forbids.

**Manual-valve tagging: the evidence I measured today (2026-11-23, free).** The unit is the drawing set (one
company's convention). Sets come from `C:/Users/Otthon/Desktop/valos-pid-mintak/` (`real-pid-samples-2026-10.md`)
and the Toghraei PDF. I rendered the pages with pdftoppm and read them as images; DEXPI C01 I parsed as XML.

| Drawing set | Industry | Manual valves | What I looked at |
|---|---|---|---|
| Covestro UER-1234567 / UER-2345678 (DEXPI C08) | chemical | **tagged** (`AB002`…`AB065`, unique numbers) | text layer of both sheets: `AB` numbers 64 and 6 times |
| Hanford WTP AR-03207 (Bechtel 2019) | nuclear waste | **tagged** (`DEP-V-44353`, `DEP-V-44848`, `DEP-V-00813`) | page 22 |
| Valdosta WPCP (CDM Smith) | wastewater | **tagged** (`BV-906-1`) | page 3 |
| DEXPI C01 reference P&ID | demonstrator | **untagged**: only a valve-type code, shared (five ball valves read `73KH12`) | the XML |
| BASF process column (DEXPI C02) | chemical | **untagged**: type code `H658B1UV` on two valves, `H672B1V` | the PNG |
| Equinor piping (DEXPI C03) | oil and gas | **untagged**: the manual vent valve has no tag; ESV 3712 has one | the PNG |
| OPEN100 (12 sheets) | nuclear design | **untagged**: pump isolation and transmitter root valves; MOVs tagged | CVCS and RHR sheets |
| Hanford HWVP (Fluor 1990) | nuclear | **untagged**: header valves carry line numbers only; FV/YV/TV tagged | page 23 |
| Wenatchee WWTP (RH2/HDR) | wastewater | **untagged** | page 9 |
| Southwest Middlesex SPS (Stantec) | wastewater | **untagged** | page 4 |
| Ford, Bacon & Davis pump template (slide 74) | gas processing | **untagged** | the slide |
| Toghraei 2019 ch.20 (34 sheets) | textbook | **untagged** | the earlier note (all 34 viewed); the battery-limit sheet (PDF p.454) re-read today |

- **Result:** 9 of 12 sets untagged, **0.75** (Wilson 95 % interval 0.47–0.91). The non-nuclear sets alone give 7 of
  9 (0.78; 0.45–0.94).
- **Toghraei p.113 is not borne out as a rule.** It says critical plants, nuclear among them, commonly tag manual
  valves. Of our three nuclear sets, one tags (WTP) and two do not (OPEN100, HWVP). The convention is
  company-specific.
- **Limits:**
  - twelve sets is a small convenience sample (whatever was public);
  - wastewater and nuclear are over-represented and refinery sets are thin (the El Paso sheet is too coarse to read);
  - the three DEXPI files are demonstrators;
  - reading a shared valve-type code as "untagged" is my interpretation. A code that several valves share cannot
    name one valve, which is what matters for an answer.
- **Chosen:** `p_untagged_manual_document` = **0.75**.

**The sampling unit: per train does not match the evidence.**
- **What the sets show.** Every multi-sheet set I looked at keeps one convention on all its sheets: both Covestro
  sheets, WTP, two OPEN100 sheets, the 34 Toghraei sheets.
- **What a train is.** On EXP-0008's sealed plants (counted today with `draw_flowsheet` on their stored configs)
  there are 10–12 trains per 100-sheet plant and 110–119 per 1,000-sheet plant, so a train is about 9 sheets. A
  per-train draw mixes conventions about ten times finer than any real set does.
- **What the thesis scope says.** One ~100-page document; a plant region of ~10 documents.
- **Chosen: per document.** A document is a run of consecutive trains, about 100 sheets long. It applies to every
  company convention: tagging, spare naming, on-off letter and PV without bypass.
- **What the document unit buys the claim.** A 1,000-sheet plant then mixes about ten contractors' styles, while a
  100-sheet plant has one. That cross-document variety is a real property of plant scale, the very axis the claim is
  about. Per-train sampling would hide it.
- **What it costs:**
  - R's two isolation families are unavailable (§11) and move to scope X;
  - 100-sheet plants become wholly tagged or wholly untagged, so the sealed plants are stratified (§18.3).

**The other weights.**

| Weight | Evidence | Limits | Chosen |
|---|---|---|---|
| Spare naming suffix : consecutive (3 : 2) | 4 sets suffix (WTP, FB&D `P-551A/B`, OPEN100, Toghraei ch.20) : 2 consecutive (Covestro, Wenatchee), from `real-pid-samples-2026-10.md` §5 (earlier hand count, not re-opened); 4/6 = 0.67, interval 0.30–0.90; Toghraei p.28 calls consecutive "the current trend" | six sets | **keep 3 : 2**: 0.6 lies inside the interval, and the book leans the other way |
| On-off letter X : Y (1 : 1) | X: FB&D fired heater, Toghraei Table 7.9 (p.113); Y: WTP, HWVP | four sets | **keep 1 : 1** |
| PV station without bypass (0.5) | no count of pressure stations. WTP draws no bypass on any of its 4 control valves (a broader policy); Covestro bypasses 5 of 8 actuated valves, without recording which | none usable | **keep 0.5**. Toghraei's "some companies" (p.122) is no minority signal: his same phrase on p.113 turned out to be 9 of 12 |
| Pump nozzle reducers (0.5) | reducers on the pump nozzles in 3 of the 4 sets that draw pump trims: FB&D template (read today), Toghraei ch.20 pump sheets and WTP H3 (earlier notes); none on Wenatchee (flexible connectors, read today) | four sets; nozzle size is not modelled | **0.75** |
| Min-flow power band (1 : 1 : 1 : 1) | none: pump power is datasheet data (ADR-0021) | — | **keep** |
| Battery-limit isolation, 3 variants (1 : 1 : 1) | Toghraei ch.20 "Plant Battery Limit" (PDF p.454, read today): gate valves at the limit with blinds and drains, no check valve on the part read | one sheet cannot set three weights | **keep** |
| Exchanger bypass TV alone : two CVs (1 : 1) | no count | — | **keep** |
| Condensate trap : station : drain pot (2 : 1 : 1) | existence only (El Paso stations, WTP drain pot) | — | **keep** |
| Fuel valves one : two (1 : 1) | FB&D fired heater draws two in series; p.214 "in some designs" | one sheet | **keep** |
| Reflux class (1 : 1) | none: L/D is datasheet data | — | **keep** |

### 18.3 D5: 3 + 3 against 5 + 5 plants, and sheet bands

**Data.** These are the per-plant headline counts of cascade_v4_iso in EXP-0008, n = 220 per plant, from the T1
tables of `data/runs/exp0008/reports/sealed/report.md`:
- S100: 203, 198, 204, 200, 200;
- S1000: 199, 198, 195, 200, 207.

I ran the repo's own two-stage bootstrap (`stats_cluster.cluster_unpaired_bootstrap`, 5,000 resamples, seed 1) on
these counts for free. The script is in the session scratchpad.

| Quantity | Value |
|---|---|
| between-plant SD of accuracy, S100 / S1000 | 0.011 / 0.020 |
| SD expected from question sampling alone (n = 220) | 0.019 / 0.020 |
| Q4 at 5 + 5 (reproduces EXP-0008's −0.005 [−0.035, +0.025]) | −0.005 [−0.034, +0.025], width **0.059** |
| Q4 over all 25 subsets of 4 + 4 | width median **0.067** (0.058–0.071) |
| Q4 over all 100 subsets of 3 + 3 | width median **0.073** (0.064–0.083); estimate −0.023 to +0.012; 100 of 100 pass |

**Reading.**
1. **On v2.1 the plants differed no more than question sampling explains.** So the precision rests mostly on the
   total number of questions, and 3 + 3 widens the interval by about a quarter.
   - The drop the design would catch with 80 % power (normal approximation, 2.8 × width / 3.92) is about 4.2 points
     at 5 + 5 and 5.2 points at 3 + 3.
2. **Q4 passes when the interval's upper end is at or above 0.** A wider interval passes more easily: all 100 of the
   3 + 3 subsets pass. With fewer plants a pass says less.
3. **v2.2 adds a between-plant factor that EXP-0008 never had.** A 100-sheet plant is wholly tagged or wholly
   untagged (§18.2), so EXP-0008's near-zero plant spread may not carry over. More plants protect against that.
4. **Stratification needs enough plants.**
   - Five plants give 4 untagged + 1 tagged (0.8).
   - Three give 2 + 1 (0.67).
   - At 1,000 sheets each plant gets 8 of its about 10 documents untagged (0.8).

   Only five (or four) plants per scale can hold the same mix at both scales. I fix the allocation at **0.8 per
   scale**: the nearest share to 0.75 that five plants hold exactly. It sits inside the interval of §18.2.

**Cost and time of the shapes** (§12.3 method):

| Shape | P1 estimate | Hard cap (1.5×) | Machine time |
|---|---|---|---|
| 3 + 3, both arms | $18.74 | $28.10 | ≈ 31 h |
| 4 + 4, both arms | $21.85 | $32.80 | ≈ 38 h |
| A2 on 5 + 5, B on the first 3 + 3 of them | $21.80 | $32.70 | ≈ 41 h |
| **5 + 5, both arms** | **$24.95** | **$37.50** | **≈ 46 h** |

**Sheet bands (the user's proposal ii).**
- **The draw.** Each sealed plant draws its target uniformly among the integers 90–110 or 900–1,100 from the seed
  tool's stream. The target is written into PREREG A before any plant is built. The size search counts network
  sheets (D4) and lands within +2 of the target, as EXP-0008's plants did (100–101 and 1,000–1,002 sheets).
- **The effect on the scale claim.** A pair of plants then spans 0.91–1.09 decades instead of exactly 1.0. EXP-0008
  measured about −0.005 accuracy per decade and a cost elasticity of 0.044, so the band moves accuracy by under
  0.001 and cost per question by under 1 %. The precision does not change. Reports give the actual mean sheets, and
  the elasticity uses actual sheets.
- **What it buys.** No real document has exactly 100 pages, and fixed targets were an artefact.

**Recommendation for P1 (the decision D5):**
- **5 + 5 plants, both arms, sizes drawn in the bands, the tagging stratified at 0.8;**
- estimate **$24.95**, ledger hard cap **$37.50**, about 46 h of machine time (§12.3).
- **Why not 3 + 3:** it saves $6.21 and about 15 h, but it widens Q4 by a quarter, weakens a pass, cannot hold the
  same mix at both scales, and breaks the comparison with EXP-0008's five-per-scale design.
- **Why not 4 + 4:** it is the honest middle (exact 0.75 mix, width 0.067). It would be my choice if machine time
  were the binding constraint. The user said cost must not block, so five plants keep EXP-0008's design.
- **Why not the hybrid:** Q4-B would rest on three plants with a 2 : 1 mix.

### 18.4 D6: the deferred list in plain words

One line each, for relay. The full table is §4.9.

| # | What it is | Bin | Why |
|---|---|---|---|
| 12 | Extra protection devices from API 14C (compressor PSH/PSL/TSH, blowdown valve, vessel low-level switch) | **now, in T10** | cheap devices are added where the composition bands allow; the rest are listed one by one as deferred |
| 9 | Nitrogen blanketing of tanks and vapour recovery | **if the expert flags it**, before the freeze | big job (split-range control and a new network); it would also close the "where does a closed vessel's vapour go" gap |
| 11 | Fired-heater detail: burner passes, pilot gas, snuffing steam | **if the expert flags it**, before the freeze | big job; a new heater variant |
| 1 | Local gauges with only a function label (just "PI", no number) | out | identical labels would break tag identity in the frozen system both arms share |
| 2 | Parallel loop numbering (FIC-101 and LIC-101 together) | out | it clashes with the key that joins signal connectors in the shared store |
| 3 | Gaps in tag numbering | out | nothing a question or a check can see |
| 4 | API's "S" letters (PSH meaning "safety") | out | the same letters mean something else in ISA, so the frozen system would be misled by design |
| 5 | Trip through a solenoid on the control valve | out | it changes the answer of a registered question family, and its source page cannot be checked |
| 6 | Minimum flow through a pressure kickback or a low-flow pump trip | out | its source is a scanned book whose pages cannot be checked |
| 7 | Three-way valve at an exchanger | out | it needs a new component class, which changes every corpus's schema text |
| 8 | Pulsation dampener, back-pressure and self-acting regulators | out | new class and a new control-loop shape |
| 10 | Double block and bleed; blinds at pump isolation | out | it changes what "the valves to close" means for both systems' isolation questions |
| 13 | Shutting in at the primary source (trip stops the pump across sheets) | out | it needs a new kind of signal link; we report how many trips act at the source instead |
| 14 | Interlock drawing style; multi-stage compressors; lube-oil and seal systems | out | style is not in the graph; lube and seal systems are vendor detail sheets |
| 15 | Untagged short branch pipes (TOG73) | out | the frozen system cannot read unnumbered branches, and both systems share the plants |

**"Until when":** "now" lands before EXP-0009's data freeze (T10). "If flagged" lands before the freeze only if the
expert review points at it; otherwise it stays deferred for this thesis. "Out" is listed in the thesis as a
limitation, with the count (15 deferred, 54 encoded).

### 18.5 D7: the expert review (T12)

**Which 12 sheets, and how they are chosen.**
- **The plant:** the dev plant `D1000g22`, never an EXP-0009 plant. It has about ten documents, so both tagging
  conventions are on it.
- **The rule** is fixed in T12a with a recorded seed; nobody picks sheets by eye.
  - Sheets 1–8: one per pattern, U1 column, U2 compressor, U3 reactor system (its fired-heater sheet), U4 tank farm, U5
    exchanger train, U6 flash drum, U7 filter package, U8 blending. Each is the first sheet of a unit drawn
    uniformly among that pattern's units (for U3, the furnace's own sheet).
  - Sheet 9: an FL (relief) network sheet. Sheet 10: an interarea sheet. Sheet 11: a pump set on its own sheet.
    Sheet 12: a steam or cooling-water network sheet.
  - **Constraint:** at least 4 sheets from tagged and 4 from untagged documents. If it fails, the last slots are
    redrawn in a fixed order.
- **Export.** The demo drawing export shows tags, line numbers, NO/NC/CSO and FO/FC labels. One legend page is added,
  and a one-page cover note says what the generator does **not** model (chemistry, sizing, set points, real
  frequencies), so that the expert does not judge those.

**The checklist** (plain English). Each item is answered per sheet: OK / Not OK / Not applicable / Can't tell, with
a comment.

| # | Item | Rule ids |
|---|---|---|
| 1 | Each centrifugal pump has a suction block valve and strainer, and a discharge pressure gauge, check valve and block valve | TOG175-PUMP-TRIM |
| 2 | The check valve on each pump discharge is right for the pump type (none on reciprocating pumps) | TOG192-RECIP-NO-CHECK |
| 3 | Minimum-flow lines leave at a sensible place and use a sensible method; none on positive-displacement pumps | TOG177-MINFLOW-TAKEOFF, TOG313-MINFLOW-METHOD, TOG192-PD-NO-MINFLOW |
| 4 | Positive-displacement pumps have a relief path and no throttling valve on the discharge | TOG219-PD-RELIEF, TOG314-PD-NO-THROTTLE |
| 5 | Compressors: anti-surge only on centrifugal machines; capacity control right for the type; discharge check valve and PSV | TOG319, TOG316, API14C-A8-FSV, API14C-A8-PSV |
| 6 | No two control valves in series on one liquid line | TOG271-ONE-CV-LIQUID |
| 7 | Every vessel's level and pressure are controlled once, or plausibly not at all | TOG295-INVENTORY-ONCE |
| 8 | Every pump's flow is controlled somehow (own loop, speed, or a level valve) | TOG270-PUMP-FLOW-CONTROLLED |
| 9 | Flow elements sit upstream of their flow control valves | TOG267-FE-UPSTREAM-FV |
| 10 | Exchanger temperature control moves the right stream; the bypass arrangement is plausible | TOG320-HX-NONTARGET, TOG322-HX-BYPASS-VARIANT |
| 11 | Exchanger isolation matches a "no process-side isolation" company policy | TOG207-HX-NO-ISOLATION (D8) |
| 12 | Vessels and exchangers have relief, and pressure vessels a second protection level | TOG219-VESSEL-PSV, TOG207-HX-PSD-BOTH-SIDES, API14C-3.4-TWO-LEVELS |
| 13 | PSV block valves are car-sealed open, with nothing else between the vessel and its PSV | TOG224-PSV-BLOCKS-CSO, TOG224-PSV-PIPE-CLEAN |
| 14 | Atmospheric tanks have a breather and an emergency vent | TOG236-TANK-EMERGENCY-VENT |
| 15 | The normal positions (NO, NC, CSO) and fail actions (FO, FC) shown are plausible | TOG114-*, TOG120-CV-BYPASS-NC, TOG114-FAIL-ACTION |
| 16 | Manual valves follow one tagging convention on the sheet (all tagged or none) | TOG113-MANUAL-VALVE-TAGS |
| 17 | Tags, spare naming (A/B or consecutive) and loop numbers read naturally | TOG28-SPARE-NAMING, LIP1-1.1-SHARED-LOOP-NUMBER, TOG113-AUTOMATIC-VALVE-LETTERS |
| 18 | Relief, drains and utilities leave through connectors to network sheets; drains go to the right system | TOG32-NETWORK-SHEETS, TOG141-DRAIN-DESTINATION, TOG360-UTILITY-NETWORKS |
| 19 | Network and interarea sheets look like real header and interconnection sheets | TOG32, TOG33-INTERAREA, PLT-NETWORK-CLOSURE |
| 20 | Battery-limit crossings are plausible | TOG34-BL-ISOLATION |
| 21 | Spec breaks sit where the pressure changes | TOG82-SPEC-BREAK, PRS-SPEC-CLASS |
| 22 | Check valves sit where a low-pressure stream joins another | TOG156-MERGE-CHECK |
| 23 | Every line on the sheet starts and ends somewhere sensible | TOG24-NO-VISITING-STREAM, PLT-STREAM-CLOSURE |
| 24 | The amount of equipment, valves and instruments on the sheet is believable | composition bands (ADR-0059) |
| 25 | Anything that looks wrong, or that a real sheet would never show | open |

**How the result enters the thesis.**
- **A table:** per item, the number of sheets judged OK, Not OK and Not applicable.
- **Every "Not OK" is triaged by the architect** into:
  - (a) a fix before the freeze (task T16, under its rule id);
  - (b) a restated rule;
  - (c) a recorded limitation.
- **The wording:** "one practising P&ID engineer reviewed 12 generated sheets against a 25-item checklist". The
  reviewer's background (years, industry) is given, and the name only with their consent. It is an external check
  (L3, §2), not a validation of realism.
- **If the review arrives after the freeze,** it is reported without fixes to the EXP-0009 plants.
- **The expert's time:** about 2–3 hours by my estimate (12 sheets plus the checklist). Not measured.

### 18.6 D3, D4, D8

- **D3 = yes.** The hidden ordinal pressure levels are a clarification of ADR-0021. T8 is unblocked and is the next
  coder task.
- **D4 = as proposed.** The network set plus interarea sheets, counted in the sheet targets. T7 is unblocked.
- **D8 = A.** One fixed policy: no process-side isolation, utility-side blocks allowed. T9b already built it, so
  nothing remains to build.

### 18.7 What still needs the user

1. **Accept ADR-0066** (amended) and **ADR-0067** (V2T-B).
2. **5 + 5 against the user's own 3 + 3** (§18.3). I recommend 5 + 5: about $6.21 and 15 machine hours more.
3. **The document unit also for spare naming and the on-off letter.** I included them because the same evidence
   applies. It changes the structure the identity arm (P2) meets: consecutive spare numbering then covers a whole
   document.
4. **The SB1 margin of −0.03** (B must not lose more than 3 points on the replication scope), or report B − A2 on R
   only descriptively.
5. **The reviewer:** background, consent to be named, and when the review can happen (it is most useful before the
   freeze).
6. **The top-up:** P1 needs up to $37.50 (estimate $24.95); P2 later up to $13.50.
