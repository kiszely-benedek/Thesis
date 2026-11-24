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
| L2 plant-level checks (19) | flow closure, phase compatibility, closed recycles; a consistent **relative** ordinal pressure order with movers, letdowns, check valves, spec breaks and PSD need (§17.13 R1); control structure (each inventory controlled once, ≤ 1 CV in series on a liquid line, FE before FV, every pump's flow controlled); protection present or excepted per API 14C; network closure | the real pressures, which vessel is atmospheric, design pressures (MAWP), the hp, whether the chemistry makes sense |
| L3 external checks | composition inside the OPEN100 bands (process sheets); a reported comparison with the 34 example sheets of Toghraei ch.20; an optional expert review sample | that the plants match any real plant |
| Not covered | process chemistry, mass and energy balance, sizing, set points, real frequencies, rules deferred or never read, company style beyond the sampled alternatives, drawing layout | — |

**The claim the thesis can make**, then:

> v2.2's rules are derived from published practitioner handbooks, cited per rule, and checked by tests on every
> generated plant. In addition, every plant is checked for plant-level consistency of flow, a relative ordinal
> pressure order, control and protection structure. The pressure levels are ranks along the flow, not service or
> design pressures. Where API RP 14C's omissions need a design pressure or atmospheric service, the plants use a
> stated convention or leave the item deferred (§17.13).

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
| TOG219-VESSEL-PSV | Every pressure vessel reaches a PSV (fire case), except the declared condensate pot | TOG p.219; API 14C A.4.2.2.1 c p.27 (re-cited §17.13 R5) | ok (S6) | cite, test | PLACE |
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
| PLT-RECYCLE-CLOSURE | A recycle returns inside its unit, from a higher to a lower pressure level, through a reducing element: an RO, a CV, or the on-off valve of the switching min-flow method (§17.13 R3) | TOG p.317 (spillback discharge → suction); p.179, p.313 (switching method) | not checked | check | PLANT |
| PRS-MONOTONE | Along the flow the pressure level never rises except across a pump, compressor or ejector | DESIGN (§6.2) | — | new | PLANT |
| TOG82-SPEC-BREAK | A spec break where a CV or RO lowers the level, or a pump or compressor raises it | TOG p.82 (Table 6.5) | compressor discharge and letdown only | extend to pumps | PLANT |
| PRS-SPEC-CLASS | The heavier pipe class is on the higher-level side of a break | DESIGN (follows ADR-0065 F8c) | ok at breaks | check | PLANT |
| TOG156-MERGE-CHECK | A process stream (P, PG) that arrives below the level its merge tee carries has a check valve on its own run; relief paths exempt (`relief_path`); the intermittent half is not checked (§17.13 R2) | TOG p.156 | not checked | check | PLANT |
| API14C-A4-OVERPRESSURE | Every A.4 vessel (hydrocarbon pressure vessel, filters included) reaches a PSV, unless SAC c.3 or c.4 holds from structure; non-hydrocarbon vessels are `scope:non_hydrocarbon`. *Restated 2026-11-23 (§17.13 R5): `source_cannot_exceed` removed* | API 14C A.4.2.2.1 c p.27; SAC A-4.2 c; A.4.1 p.26 (scope) | partial | new | PLANT |

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
| 12 | SAC devices without a derivable exception: compressor PSH/PSL/TSH and suction PSV (A-8.2 a–e, h), vessel PSL/LSL, pump PSH/PSL and the rest of T10a §8. *Corrected 2026-11-23 (§17.13 R6):* SDV, BDV and ASH are not SAC items (A.8.2.2.3, A.8.3.3, A.8.3.5 p.45, Fig. A-8) and stay out | API 14C SAC A-4.2, A-5.2, A-6.2, A-7.2, A-8.2, A-10.2 (T10a transcription) | each becomes a DEFERRED SAC row, unless the device is cheap and inside the composition bands | **Now: T10** decides device by device |
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
- exchangers, filters, mixers and pipes keep it;
- *added 2026-11-23 (§17.13 R1):* a vessel stands one level below its lowest process feed, never below ATM. Levels
  are therefore a **relative order along the flow**, not service pressures; on a vessel, ATM is the model's floor.
  No exception may be derived from a vessel's level value.

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
| TOG156-MERGE-CHECK | at a merge tee of process runs (P, PG), a run arriving below the tee's level carries a check valve before the tee; relief paths are exempt (`relief_path`) (§17.13 R2) |
| PLT-RECYCLE-CLOSURE | every spillback or min-flow RECYCLE line goes from a higher to a lower level and holds an RO, a CV or a switching min-flow valve (counted as `switching_valve`); a reactor recycle-gas loop returns inside its core (§17.12, §17.13 R3) |
| API14C-A4-OVERPRESSURE | every A.4 vessel reaches a PSV, or SAC c.3/c.4 holds from structure; non-hydrocarbon vessels are out of scope (§17.13 R5) |

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
- **Revised by §17.14 N2 (2026-11-23):** headers are per (area, service), where an area is a run of 10 consecutive
  trains and is also T6's document. Interarea sheets carry only lines between areas, on one plant interconnecting
  unit. The two bullets below on network units and interarea describe T7 as first built.
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
- **Corrected by §17.15 (2026-11-23).** Three cells of the table above are superseded:
  - FLOW_PATH and NEIGHBOURS_DOWNSTREAM: untagged valves do **not** drop out of the listing; a candidate whose
    answer would name one is refused (S2);
  - the FLOW_PATH tie refusal is withdrawn; F2 stays as in v2.1 (S4);
  - the isolation families stay unavailable in scope R, but for the reason given in S5 (selection), not "no
    candidate".

## 12. EXP-0009: pre-registered re-measurement on v2.2, two arms

### 12.1 Claims (pre-registered; revised 2026-11-23 for D1 = C)

| Claim | Arm and scope | Pass |
|---|---|---|
| **Q4 (primary)** | V2T-A2, scope R, cascade_v4_iso, S1000 − S100, two-stage cluster bootstrap | the interval contains 0 or lies above (ADR-0053, ADR-0065) |
| Q4-B | V2T-B, scope R ∪ X | the same rule |
| SB1 no harm | V2T-B − V2T-A2, scope R, paired on the same questions | descriptive: the difference and its interval, no margin (user, 2026-11-23) |
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

**Superseded for P1 by §19.9 and §19.10 (2026-11-24).** Scope R holds 235 questions per plant, not 280, after
§17.17. The basis is now EXP-0008's measured per-run spend and stage times, and the hard program cap is $35. The
table below is kept as the record of the first estimate.

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

**Done** (2026-11-23): T0, T1, T2, T3, T4, T9, T9b, T9c, T11, T7a, T5's plan and DEXPI part (`cf2eddb`), T10a
(`2a9da7a`) and T8 (`6ae1d0c`). 44 of 54 rules are wired.

**Remaining, in order** (revised 2026-11-23 after D1–D8). Sizes S/M/L follow the previous notes' scale; coder pace is
unmeasured.

| Order | Task | Size | Who | Waits for |
|---|---|---|---|---|
| 1 | **T8** Pressure-level model and PRS-*, TOG82 (pump spec breaks), TOG156, PLT-RECYCLE-CLOSURE, API14C-A4-OVERPRESSURE | M | coder | **done** (`6ae1d0c`); rulings on its report in §17.13 |
| 1′ | **T10a** SAC transcription (A-4.2, A-5.2, A-6.2, A-7.2, A-8.2, A-10.2), page-checked | — | researcher | **done** (`2a9da7a`); rulings in §17.13 |
| 2 | **T7** Networks and interarea: network units, headers, per-sheet sub-headers, network connectors, capacity overflow, splitter grouping, size search on total sheets, composition per sheet kind, TOG32/141/360/33, PLT-NETWORK-CLOSURE; empties `OWED_FIXES`; wires 5 pending rules. **Also R2 of §17.13:** TOG156 narrowed to process services (P, PG) with the `relief_path` exemption, because T7 creates the FL and CHD tees | L | coder | **built, uncommitted**; rulings on its report in §17.14 |
| 2b | **T7b** T7 fixes (§17.14), acceptance criteria below the table | M | coder | **done** (`3e42a6a`); size search ruled in §17.14 N4 |
| 3 | **T6** (**done**, `cc4d5ef`; gold-side rulings in §17.15) Documents and conventions (§5, §18.2): `DocumentRecord` (a document is T7b's area, `trains_per_document` = `trains_per_area`, §17.14 N2.3); per-document draws of manual-valve tagging (0.75 untagged), spare naming, on-off letter and PV without bypass, from new streams (v2.1 per-train draws taken, values ignored); config override `handbook.document_untagged` for the stratified sealed plants; untagged manual valves (TOG113); `p_pump_reducers` 0.75; gold side of scope R (untagged refusal, FLOW_PATH tie rule, refused-share report; isolation families pre-registered unavailable); v2.1 question hash unchanged | M | coder | T7b |
| 4 | **T10** In this order (§17.13): **step 0**, the T8 follow-ups: the R1 docstring in `pressure_levels.py`; R3's `switching_valve` element code and restated statement; R5's re-cite of API14C-A4-OVERPRESSURE and TOG219 to A.4.2.2.1 c p.27, with `source_cannot_exceed` deleted and `scope:non_hydrocarbon` added. **Step 1**, `rules/sac.py` from T10a: items, device letters, locations, and exception codes of three kinds, derived (from structure), declared (R7) and scope. **Step 2**, R7's declarations as constants in `hidden_state.py`, plus `FluidClass.NON_FLAMMABLE` for the non-flammable farms. **Step 3**, the switch-plus-alarm additions of T10a §8: vessel PSHH (where a.4 fails), LSHH and LSLL; filter PSHH; compressor suction/discharge PSHH and PSLL, and TSHH; furnace TSHH and fuel PSHH; additive-tank LSHH. **Step 4**, the valve additions in R8's priority order, with R8's measured stop at 27.5 pooled valves per process sheet: TOG236 emergency vents, compressor suction PSV, furnace tube PSV where l.3 fails. **Step 5**, wire API14C-3.4-TWO-LEVELS, API14C-SAC, TOG207-HX-PSD-BOTH-SIDES and TOG236. Every SAC item without an addition or a derivable, declared or scope code becomes a DEFERRED row with its reason: the heater-outlet check, vessel PSL, pump PSH/PSL, stack and air-intake items, and SDV/BDV/ASH | M | coder | **done** (`8b34921`), with the main-session rulings of §17.16 |
| 4b | **T6b** Gold side of scope R, as ruled in §17.15: one printed-name helper and one untagged-refusal filter for every family, `harness/gold.py` skips untagged endpoints, `gold_scope_r.py` moved to `qa/questions/untagged.py` without the tie rule, the LINE-01 gate for v2.2 (`qa/exp0009/line_view_gate.py`), the frozen-A2 smoke on an untagged plant, `validate_plant_graph_v22`, and the per-family availability table. Acceptance criteria below the table | M | coder | T10 (one coder at a time; the availability table must be measured on the final v2.2 generator) |
| 5 | ~~**T12a** Expert-review package~~ | — | — | **dropped**: no reviewer (§18.8) |
| — | ~~Expert review and triage~~ | — | — | **dropped** (§18.8) |
| 6 | **T14** V2T-B system files (`v2t-b-system-revision.md` §3): B store view, VALVE_SET and POSITION types, `scoring_b.py` and its self-tests, `policy_b.py`, the import-isolation test; G0f stays green | M | coder | **done** (`dd60e6c`); rulings on its report in `v2t-b-system-revision.md` §10 |
| 6b | **T14b** The descriptor walk and its wording (`v2t-b-system-revision.md` §10 R1, R10b): the walk to `next_to` follows every `send_to` edge; line-number fold guard; a non-empty `tag` wins in an object item; "nearest tagged item along the flow" in the format sentence, schema paragraph and primer; toy-plant tests; the proxy re-measured on seeds 1–5 (must equal §10.7) and on seed 7 at 1,000 sheets. Acceptance criteria in §10.6 | S | coder | **done** (`f5d6ef4`) |
| 7 | **T15** Scope X (gold side): OPEN_VALVES_TO_ISOLATE (up, down), UPSTREAM_ISOLATION_X, DOWNSTREAM_ISOLATION_X, POSITION_OF_VALVE, descriptor gold and refusal, the A2 adapter (TAG_SET), discriminating-share report. **Revised 2026-11-24 (`v2t-b-system-revision.md` §10):** the OPEN_VALVES texts are the twins of the registered isolation texts (R9), with a test that `classify_need` gives each the label of its twin; references are sorted `list[str]`, a tag or `encode_descriptor(canonical_descriptor(...))` (R8); an OPEN_VALVES candidate with empty gold is refused and counted (R8); refused count, share and refusing-valve roles per family and plant (R3); stop and return to the architect if any X family refuses more than a quarter of its candidates on a dev plant | M | coder | **done** (`cb6db52`); ruling on its report in `v2t-b-system-revision.md` §10.8 |
| 7a | **T15b** POSITION_OF_VALVE on untagged plants (`v2t-b-system-revision.md` §10.8 R11, R12): an untagged positioned valve is named in the question by its canonical descriptor, "What is the normal operating position of the {class words} on line {line number}, on the {side} side of {next_to}?", or refused without one; `named_by` flag; routing test (the descriptor text gets the tag text's need label); no-answer-in-text test; `qa/exp0009/position_baselines.py` (majority and text prior, fitted on dev seeds 1–5, sha256); the report reproduces §10.8's counts and P3. Acceptance criteria in §10.8 | S | coder | T15 |
| 7b | **T14c** The B ingest step and the B harness (`v2t-b-system-revision.md` §10 R4–R7): `positions.py` (DEXPI reader), `store_b.py` (positions map, plan patch, positions file, G0-B check), `views_b.py`, `answer_b.py`, `strategies_b.py`, `registry_b.py`, `runner_b.py`, `__main__.py`, all under `qa/v2tb/`; runner equivalence, cascade, gold-isolation and expressiveness tests. Acceptance criteria in §10.6; criterion 9 amended in §10.8 (descriptor-form POSITION questions) | M | coder | T15b |
| 7c | **T14d** The B tool lines, the B seed and the B Neo4j loader (`v2t-b-system-revision.md` §10.9 R14–R19): the line number moves from `send_to` edge lines to the untagged valve's own item line; the B seed uses the B item line; one checked sentence in B's agent system prompt; B rendering only on B corpora (empty map = frozen); exactness, seed-coverage and scope R footprint measurements; `load_b.py` with the database-side G0-B count; `x` + `x_b` params refused; `TYPE_CHECKING` allow-list. Acceptance criteria in §10.9 | S | coder | T14c (**done**, `e367e49`) |
| 8 | **T12b** Composition report per sheet kind; the ch.20 comparison table (the annotation by the main session) | S | coder and main session | T7b |
| 9 | **T16** Fixes from the review findings, if any (designed by the architect first) | ? | coder | the review |
| 10 | **T13** EXP-0009 launcher: ledger glob skips `reports/` (with a test on a copied call file); ids `g22` and `…B`; seed draw plus size-target draw in the bands; stratified tagging allocation (§17.15 S9); two-view ingest; the B question files as a corpus-id relabel of A's (§17.15 S3); LINE-01 for v2.2 and `validate_plant_graph_v22` in the plant gates (§17.15 S7, S8); E10 hashes all of `src` again; stages P1a–P1d; caps; PREREG A template. **Added 2026-11-24 (`v2t-b-system-revision.md` §10 R4, R6, R7):** per plant, load A, run A2, wipe, load B with T14c's patched plan, run B; `write_positions_file` in the two-view ingest, with the file's sha256 in the B corpus record and PREREG A; G0-B in the plant gates; B tier runs through `python -m plantgraph.qa.v2tb run`; G0l applies the quarter rule to every X family on the sealed plants; T14c's measured positions-file time added to §12.3. T13 writes no B system code. **Consolidated 2026-11-24 into one ordered specification, §19, which supersedes the criteria scattered above where they differ** | L | coder | all of the above, T14d included |

**T7b acceptance criteria** (§17.14). Every task rule above applies too.
1. **Counting (N1).** An open end continued on the same sheet by a sub-header line is not a stub (`sheet_stats.py`).
   - A unit test covers a 2-tie collection sub-header and a 2-tie distribution sub-header: one connector each, 0
     open-end stubs.
   - v2.1 composition numbers are unchanged.
2. **Areas (N2.1–2).**
   - `HandbookKnobs.trains_per_area`.
   - One header unit per (area, service), numbered 9000 + 10·area + the service index.
   - The network context takes the area's first train's conventions.
3. **k (N2.1).** For k = 8…12 on seed 7 at the 1,000-sheet target, report the median, min and max of total sheets
   per area (process plus header). The default is the k whose median is nearest 100, the smaller k on a tie. The
   table goes into the report.
4. **Interarea (N2.4).**
   - Only lines between areas pass the plant's interconnecting unit (9008), at most 16 lines per sheet.
   - A join inside one area is drawn as in v2.1.
   - TOG33 reports its instance count; 0 at 100 sheets is not a failure.
5. **Relief (N3.1–2).**
   - `reactor_rupture_disc` ties into the FL sub-header and is in TOG32's relief set.
   - A plan check raises if a relief device (PSV, rupture disc, PSV outlet block) on a HYDROCARBON-class line ends
     open.
6. **Size search.** It lands within +2 of the target on seed 7 at 100 and 1,000 sheets, and on a spot check at 90,
   110, 900 and 1,100.
7. **Composition.** Run on seed 7 (100 and 1,000 sheets) and pooled over seeds 1–5 at 100.
   - Every process-sheet band passes, in particular stubs mean 5–11 and max ≤ 21.
   - The kind rows give sheets by kind, the share, and tie-ins and connectors per header sheet (mean, max).
   - On a failed band: stop and report, with no knob moved.
8. **Rules and goldens.**
   - Every wired rule is at 0 violations on seeds 1–5 and on both seed-7 dev plants.
   - The rule report lists the instance counts of TOG32, TOG33, TOG141, TOG360 and PLT-NETWORK-CLOSURE.
   - The v1 and v2.1 goldens are byte-identical (this also proves N3.5).
9. **Process draws unchanged.** A test shows that every process unit's plan before the tie pass is identical to T7's
   for the same seed and unit count.
10. **The report** gives the measured sheet mix against the estimates of §17.14 N2, with measured and estimated
    numbers labelled. It ends with one commit proposal covering T7 and T7b (or two), and nothing is committed.

**T6b acceptance criteria** (§17.15). Every task rule above applies too. No Neo4j, no paid call.
1. **EXP-0008's questions reproduce.** After the change, regenerate the sealed question files of `H100g21p1`,
   `H100g21p2` and `H1000g21p1` with the EXP-0008 command (`lib_plants.sh` `sealed_questions`: seed 31, the same
   bin, family and wording counts, sample seed 20261031) from their stored `ingest.json`. Each `questions.jsonl` is
   byte-identical to `data/runs/exp0008/questions/<id>/questions.jsonl`. The v1 and v2.1 goldens, the H1g21
   question hash included, are unchanged.
2. **One rule, one place (S2).**
   - Family code reads a printed name only through one helper, which returns the tag or the fixed marker.
   - One filter after candidate building drops every question whose text, anchors or reference holds the marker,
     and returns the refused count per family.
   - `is_path_item` and `next_path_items` are unchanged.
3. **No family raises.** Every registered family's candidate builder runs without an exception on:
   - the 100-sheet v2.2 dev plants of seeds 1–5 with every document forced untagged (`handbook.document_untagged`);
   - the same plants forced tagged;
   - seed 7 at 1,000 sheets (drawn tagging).

   No kept question holds the marker (test).
4. **Behaviour tests.**
   - VALVES_ON_PATH: an untagged valve on the route is counted.
   - NEIGHBOURS_DOWNSTREAM: an untagged valve directly downstream refuses the candidate; it is not looked through.
   - FLOW_PATH: a reference path holding an untagged valve refuses the pair; two equal-length, fully tagged routes
     do not.
   - `harness/gold.py`: a path answer that skips an untagged valve is invalid; a fully tagged route is valid.
5. **Module.** `benchmark/v2/gold_scope_r.py` moves to `qa/questions/untagged.py`. `tagged_sequences_differ` and its
   tests are deleted. `SCOPE_R_UNAVAILABLE_FAMILIES` and `RefusedShare` stay.
6. **Availability table (S6).** Per family: candidates, refused, kept, on each plant of criterion 3. The report lists
   every family below 10 kept candidates on any forced-untagged 100-sheet seed. By S6 these are pre-registered
   unavailable in scope R; the main session copies the list into §11.
7. **LINE-01 for v2.2 (S7).** `qa/exp0009/line_view_gate.py` passes (precision = recall = 1, 0 key collisions) on
   the forced-untagged seed-1 plant and on seed 7 at 1,000 sheets. On `D100g21` it gives the same items, edges and
   verdict as the frozen LINE-01.
8. **Frozen-A2 smoke (S7).** On the forced-untagged seed-1 plant, the frozen `build_item_graph` over
   `NetworkxGraphView`, the line view and the schema text run without an exception. If a frozen system module
   raises, T6b stops and reports; the case returns to the architect.
9. **Validation (S8).** `validate_plant_graph_v22` gives 0 violations on the plants of criterion 3. The number of
   violations it removes equals the record's count of untagged manual and check valves. Removing the tag of one
   control valve or PSV gives exactly one violation.
10. **G0f.** `git diff --name-only $(cat data/runs/exp0008/prereg/E9.commit) HEAD` over the system-side path list
    (EXP-0007 plan §2, with ADR-0060's named exceptions) is empty.
11. **The report** gives the availability table, the refused shares, criterion 1's three `cmp` results and the
    machine time of the H1000 regeneration. It ends with one commit proposal; nothing is committed.

**Now (2026-11-24):** T14d (T15b, T14c and T12b done; rulings on T14c in `v2t-b-system-revision.md` §10.9). Next:
T13 as specified in §19, then T17 (the sealed analysis, §19.11) before the E10 freeze. No coder runs in parallel.

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

### 17.13 Rulings on T8 (`6ae1d0c`) and on the SAC transcription (T10a, `2a9da7a`), 2026-11-23

**Inputs.**
- The T8 coder's report: 6 rules at 0 violations on seeds 1–5 and on both seed-7 dev plants; 44 of 54 rules wired.
- The researcher's transcription `10-literature/api-rp-14c-2001-sac-transcription.md` (pages printed = PDF − 8,
  each checked).
- My own re-read of Toghraei p.156 (PDF 175) and p.179 (PDF 197), and p.313 (PDF 329), on 2026-11-23.

#### R1. Vessel levels: keep the relative model, and say what it means

**What T8 does.**
- Each vessel stands one level below its lowest process feed, never below ATM.
- Every vessel therefore sits at ATM, columns and reactors included. Pipe runs carry the rest: ATM ≈ 260–354,
  LP ≈ 293–349, MP 8–20, VAC 3–11, HP never.

**The options:**
- **(a) Keep the relative model.** Levels are an order along the flow: a mover lifts, a letdown or a vessel inlet
  lowers. They are not service pressures.
- **(b) Declare a level per vessel role** (for example reactor HP, flash drum MP, column LP), with the lowering
  control valve on each vessel feed drawn as a spec break. Then TOG82 needs a break at every lowering control valve.

**Ruling: (a).**
- **(b) buys almost nothing for T10.**
  - API's MAWP exceptions (A-4.2 a.2, A-7.2 f.2, A-10.2 a.2) compare a source with a **design** pressure. Neither
    model holds a design pressure, so both leave them underivable.
  - The "operates at atmospheric" codes (A-4.2 a.6, b.2; A-10.2 b.2) would apply under (b) only to vessels declared
    ATM, and no A.4 pressure vessel would be declared ATM.
  - (b) also adds a role table with no page behind it, and a spec break per lowering valve, which moves the valve
    band.
- **(a) already supports what the six checks need:** an order, rises only at movers, breaks where the order changes,
  recycles that run downhill, and check valves where a lower stream joins.

**Consequences, binding on T10 and later tasks:**
- **No exception may be derived from a vessel's level value.** On a vessel, ATM is the model's floor, not
  atmospheric service.
- **"Atmospheric service" has two sources only:** the class `Tank` (API A.5, the atmospheric vessel) and the
  declared utility levels (§6.2).
- **Codes that need atmospheric service or a MAWP** become either a declared convention, stated as one (R7), or a
  DEFERRED SAC row.
- **§6.2 is amended** to state the vessel rule, and `pressure_levels.py`'s docstring must say the same (T10 step 0).

**What the thesis may claim:**

> Every plant is checked for a consistent **relative** pressure order: no rise without a pump, compressor or
> ejector; a spec break wherever the order changes; recycles running from a higher to a lower level through a
> reducing element; check valves where a lower process stream joins another. The levels are ordinal ranks along the
> flow, not service or design pressures. The plants make no statement about which vessel operates at atmospheric
> pressure, nor about design pressures.

#### R2. TOG156: confirm the coder's reading, and narrow it to process streams

**The page (p.156, re-read).** The passage sits in §9.9.4, on tying several streams into one nozzle of a container:
"If there is a chance of intermittent flow in one of the tying streams, or the chance of dropping pressure in any of
these streams, a check valve should be installed on the intermittent or low pressure stream."

**Ruling.**
- **Confirmed:** a process stream that arrives below the level its merge tee carries needs a check valve on its own
  run, upstream of the tee.
- **Scope: process services only** (P, PG), which is the page's context.
- **Relief paths are exempt,** under exception code `relief_path`, counted in `rules.json`:
  - PSV outlets;
  - PD-pump relief returns;
  - FL tie-ins.

  A check valve in a relief path could block relief. This is a design reading (DESIGN), not a page.
- **Collection headers are out of scope:** the closed-drain (CHD) and utility collection headers.
- **Not checked, and recorded:** the "intermittent" half. The plan does not know which streams flow intermittently.
- **Timing.** The T7 coder applies the narrowing in T7, because T7 creates the FL and CHD tees that the present check
  would flag.

#### R3. PLT-RECYCLE-CLOSURE: confirm the switching valve, as a declared reading

**The pages.**
- p.179 (Fig. 10.9) and p.313 (Fig. 15.36) describe the 20–35 hp method as a flow sensor and an on-off valve that
  "will be opened to recirculate some flow". Neither text mentions an orifice beside it.
- p.313 calls an RO "a frozen control valve".

**Ruling.**
- **Confirmed:** the switching valve of that method counts as the recycle's reducing element.
- **Counted apart:** the check counts it under element code `switching_valve` in `rules.json`, so the reader sees how
  often the reading carries a recycle.
- **Registry:** the statement becomes "…through an RO, a CV, or the on-off valve of the switching min-flow method
  (TOG p.179, p.313)".

#### R4. Pump and compressor discharge spec breaks: accepted

**Ruling.**
- Every pump and compressor discharge starts at a `discharge_spec_break`, and the discharge is the next heavier class.
- **Why it is right:**
  - Table 6.5 (p.82) puts a spec break where a pump or compressor raises the pressure.
  - The ordering follows ADR-0065 F8c (PRS-SPEC-CLASS).
- **One step heavier is enough,** even where the mover lifts two levels: only the order is checked, never the size of
  the step.
- **It also carries R7's shut-off declaration** for centrifugal pumps.

#### R5. `source_cannot_exceed`: remove it; condensate pots become a scope exclusion

**The finding (T10a §9, accepted).**
- SAC A-4.2 c (the vessel PSV) has no "source cannot exceed" exception; that condition exists only for the PSH
  (a.2).
- A.4.2.2.1 c (p.27) says a vessel should always have a PSV.
- A.4 covers vessels that handle hydrocarbons under pressure (A.4.1, p.26).

**Ruling (in T10, step 0):**
- **API14C-A4-OVERPRESSURE** is re-cited to **A.4.2.2.1 c p.27 / SAC A-4.2 c**. Its statement becomes: "every A.4
  vessel reaches a PSV, unless c.3 or c.4 holds from structure".
  - `source_cannot_exceed` is deleted.
  - The rule keeps its id (an id is a name, not a claim).
- **TOG219-VESSEL-PSV** cites "API 14C A.4.2.2.1 c p.27", replacing "p.26".
- **The steam condensate pots** (12 on seeds 1–5, 47 on the 1,000-sheet plant) carry `scope:non_hydrocarbon`. That is
  a scope exclusion with the page (A.4.1 p.26), not an SAC omission. TOG219 already excepts them as the declared
  condensate pot.

#### R6. A-8.2: SDV, BDV and ASH are not SAC items

**Correction:** §4.9 #12 and §18.4 #12 named a blowdown valve among the SAC devices. It is not one.
- A-8.2 has items a–h: suction and discharge PSH and PSL, suction and discharge PSV, the final-discharge check valve,
  and the TSH.
- The SDV on inflow and fuel-gas lines, the blowdown valve on the final discharge, and gas detection (ASH) in
  enclosed buildings come from the text (A.8.2.2.3, A.8.3.3, A.8.3.5, p.45) and Figure A-8 only.

**Ruling:** SDV, BDV and ASH stay **out**.
- They are not SAC items.
- ASH needs an enclosed building that is not modelled.
- SDV and BDV would add valves against the tight valve band (R8).

§4.9 #12 is corrected in place.

#### R7. Declared conventions and scope

Each item is declared once in `hidden_state.py` (a constant, never drawn), listed in the registry with its own
exception code, and named in the thesis limitations as a convention.

| # | Question | Ruling | Exception code (where it applies) |
|---|---|---|---|
| a | U3 furnace natural draft | **yes**. The model draws no blower or fan (the allowlist has none), so natural draft is the only consistent reading. Forced draft would make d, f and i required with no class to draw them | `declared:natural_draft` (A-6.2 d.2, f.2, i.2) |
| b | Centrifugal pump discharge piping rated for shut-off | **yes, for centrifugal pumps only**, tied to R4's heavier discharge class. PD pumps keep their relief valve (A-7.2 f.1) | `declared:discharge_rated_for_shutoff` (A-7.2 f.2) |
| c | Utility side designed for its header pressure | **yes, for the PSH item only** (A-10.2 a.2). Not for the PSV: c.6 also needs "no overpressure from the other section" (tube rupture), which no declaration covers; cooling-water thermal relief stays as drawn | `declared:utility_designed_for_header` |
| d | A switch with an alarm as the drawn form of an SAC sensor | **yes.** It is the form the generator already draws (`LSHH → LAHH`) and it passes S7 and S8. The shut-in action at the source stays deferred (§4.9 #13), and the thesis says the sensors are drawn without their shutdown action | — |
| e | Steam condensate pots | **out of A.4** (R5) | `scope:non_hydrocarbon` |
| f | Filters (`LiquidFilter`, `GasFilter`) | **in A.4** (API p.28 names fuel-gas filters among pressure vessels; per the transcription). Items: a PSH as a cheap switch; d LSH by d.3 (no separated phases); e LSL by e.2 (no level loop, no heater); c PSV by c.3 or c.4 from structure where it holds, otherwise a DEFERRED row per filter (valve band, R8) | `derived:…`, `deferred:valve_band` |
| g | Liquid-ring vacuum pumps | **out of A.8.** They draw below atmospheric and discharge near it, so A-8.2's suction PSH and PSV serve no purpose there | `scope:vacuum_service` |
| h | A pump that sends product over the battery limit | **not a pipeline pump.** The region's battery limit is not a pipeline leaving a platform (A.7.1), so A-7.2 a, c and e do not apply | — |
| i | U4 "non_flammable" tanks against the plant-wide hydrocarbon declaration | a new `FluidClass.NON_FLAMMABLE` for the tanks of a farm drawn non-flammable, and their own trims. A.5 then does not cover them (A.5.1, p.30: chemical storage is not covered). TOG141 treats them as non-innocent, so their drains still go to the closed drain. The farm's flag overrides the plant-wide declaration for that farm's items only. A non-flammable farm feeding a hydrocarbon train is a chemistry inconsistency, recorded under "chemistry not modelled" | `scope:non_hydrocarbon` |

#### R8. Valve headroom: priorities and a measured stop

**The facts.**
- The ADR-0059 valve band is 15–28 valves per sheet, judged on the **pooled mean** per scale on process sheets
  (G0d).
- Seed 2 alone measures 27.23 (T10a).
- EXP-0008's D100g21 pooled 24.11.
- The T10a arithmetic puts all the proposed valve additions at about +0.12 per sheet, before TOG236.

**Ruling.**
1. **Only these valve additions, in this priority order:**
   - (1) TOG236's emergency vent on every atmospheric tank (an encoded rule; drawn as §6.4 says);
   - (2) the compressor suction PSV (A-8.2 e);
   - (3) the furnace tube PSV, only where l.3 does not hold from structure.
2. **Deferred:**
   - the heater-outlet check valve (A-6.2 m): m.2 is a judgement, and a check valve at a heater outlet is the kind of
     thing the expert should call;
   - every SDV and BDV (R6).
3. **The measured stop.** After each addition, T10 measures the pooled mean valves per process sheet over seeds 1–5,
   and on each seed-7 dev plant (100 and 1,000 sheets).
   - If a mean exceeds **27.5** (half a valve under the band's top, a margin for the spread of sealed plants), the
     lowest-priority addition still in is withdrawn, and its rows become `deferred:valve_band`.
   - If TOG236 itself does not fit, T10 stops and reports. An encoded rule is not dropped silently.
4. **Instruments.** The switch-plus-alarm package adds about +2.2 instruments per sheet (T10a). T10 measures the
   pooled instrument mean and the instrument : valve ratio against 20–38 and 1–1.8, with the same report-and-stop
   rule.
5. **Order.** T7 runs before T10, so T10 measures on plants that already carry the network sheets.

#### R9. Who does what, and whether T7 runs beside T8 follow-ups

- **One coder at a time** (ADR-0006, CLAUDE.md). T7 does not run in parallel with any other coder task.
- **No T8 follow-up blocks T7, except the TOG156 narrowing (R2).** T7 creates the FL and CHD tees, so the T7 coder
  does R2.
- **The other follow-ups go into T10 as its step 0.** They are R1's docstring, R3's element code and statement, and
  R5's re-cite and code removal. They touch the same files T10 works in (`checks_overpressure.py`, the catalogue).

### 17.14 Rulings on T7 (networks and interarea, uncommitted), 2026-11-23

**Inputs.**
- **The T7 coder's report (seed 7):**
  - 100 sheets: 37 units, 102 sheets = 60 process + 36 network + 6 interarea.
  - 1,000 sheets: 330 units, 1,000 sheets = 555 process + 383 network + 62 interarea.
  - Off-page stubs per process sheet: mean 9.13 / 9.49, max 16 / **22**, against the ≤ 21 band.
- **My re-read of Toghraei on 2026-11-23:**
  - pp.32–34 (PDF 51–53);
  - pp.360–362 (PDF 375–377);
  - p.368 (PDF 383);
  - the two ch.20 network sheets, "Relief Flare Header" (PDF 441) and "Glycol Distribution Header" (PDF 442), which
    carry no printed page number.
- **Page offsets.** Printed = PDF − 16 holds up to p.349. From p.359 it is **− 15** (p.360 = PDF 375).
- **Read-only probes** on the T7 plans (seed 7; the scripts are in the session scratchpad, not committed):
  - the stub breakdown per sheet;
  - a what-if of the header grouping.
- **Where the stub bands come from** (`generator-v2-pid-vocabulary.md` §7.1):
  - **≤ 21** is the top of the hand-counted real sheets (1–21: HW1 ≈ 21, D1 16, F2 13;
    `real-pid-samples-2026-10.md` §5).
  - **5–11** brackets the OPEN100 mean of 8.0.
  - On those real sheets every utility is already an off-sheet arrow (same note, §6), so the band counts network
    connectors.

#### N1. The max-stub failure is a counting defect: correct the count, change neither the generator nor the band

**Finding.** A sub-header with two or more tie-ins is counted twice on its sheet:
- once as its connector (a crossing, correctly);
- once more as an "open end".

The open end is:
- the first tie-in of a collection sub-header (the sub-header line starts from its last part);
- or the last tie-in of a distribution sub-header (the sub-header line ends at its first part).

`wired_out_ends` and `fed_start_ends` accept as a continuation only a line of another unit or a bare join. The
sub-header line has parts and belongs to the same unit, so the continuation is missed.
- **Sheet 296:1** shows FL, CHD, CD, CWR and LPS each as one crossing **and** one open end.
- **The corpus already counts correctly.** Its pipe connectors equal the plan's crossings (`composition_corpus.py`),
  so only the plan-level stub count is wrong.

**Measured with the corrected count** (probe, same plans):

| Plant | Stubs per process sheet, as counted (mean / max) | Corrected (mean / max) | Sheets > 21 |
|---|---|---|---|
| seed 7, 100 sheets (37 units) | 9.13 / 16 | **7.75 / 12** | 0 |
| seed 7, 1,000 sheets (330 units) | 9.49 / 22 | **8.19 / 18** (63:1, 296:1, 328:1) | 0 |

**Ruling.**
- **Correct the counting rule.** An open end that a sub-header line continues on the same sheet is not a stub.
  - This is the same kind of fix as the PCF counting correction of ADR-0059 round 1: the rule is restored, not
    tuned.
  - No draw moves.
  - v2.1 counts are unchanged, because v2.1 has no sub-headers.

**Why not the offered options:**
- **(a) One shared sub-header for several services.** Physically wrong: flare, closed drain, cooling water and steam
  are different pipes and different specs. Even a multiple-commodity network sheet draws one pipe per commodity (p.34;
  the glycol sheet, PDF 442, draws GLS and GLR apart).
- **(b) Relax ≤ 21 on sheets with network connectors.** The band's source already counts utility arrows, so there is
  no evidence for a higher ceiling.
- **(c) Split the heavy U1 sheets.** It moves the sample-grounded combined layout (D1, FB&D) and v2.2's process sheet
  assignment away from v2.1's, and it is not needed.
- **(d) Cap the connectors per sheet and push the overflow to a neighbouring sheet.** The overflow line still leaves
  the sheet, so the count does not fall. It also adds a process-to-process crossing that a real sheet would not have.

**If a sheet still exceeds 21 after T7b** (larger unit counts after N2): T7b stops and reports (the U4 rule of
ADR-0065), and the architect rules. No knob is pre-tuned.

#### N2. Headers per area (the document's run of trains), not per train

**What Toghraei says.**
- **p.34:** network P&IDs "are generally drawn to follow the plot plan". They are organised by plant area.
- **p.34:** utility network P&IDs are single- or multiple-commodity. "The tendency is toward developing
  single-commodity P&IDs when the plant is huge and the utility users are large."
- **p.32:** a network P&ID is "mainly pipes and does not have equipment".
- **pp.33–34:** interconnecting P&IDs show process pipes passing the **internal borders between areas**. Their pipes
  are straight.
- **p.362:** root valves, manual isolation (gate) valves, sit at the start of sub-headers and branches.
- **Ch.20, Relief Flare Header (PDF 441):** 7 tie-ins from several drawings join one header that leaves "To Flare
  Header", so the sheet has 8 connectors.
- **Ch.20, Glycol Distribution Header (PDF 442):** supply and return on one sheet, 4 users, 10 connectors.

**What T7 built.**
- One header unit per (train, service).
- A train is about 9 process sheets (seed 7, 1,000 sheets: median 9, range 3–15, 63 trains).
- So a header sheet holds 3.3 tie-ins on average, and the 8 services give about 6 header sheets per train.
- The result:
  - network and interarea sheets are 41–45 % of all sheets;
  - process sheets fall to 60 / 555, against v2.1's about 100 / 1,000.
- A train-sized plot area has no support in the books or the samples, and it nearly halves the process content the
  questions are drawn from.

**Options.** A what-if on the seed-7 plans with T7's tie-ins per (train, service) and capacity 16. Unless marked, the
numbers come from the probe.

| Option | Network + interarea share | Process sheets at ~1,000 total | Tie-ins per header sheet | Verdict |
|---|---|---|---|---|
| T7 as built: per (train, service), one interarea sheet per train join | 44.5 % (measured) | 555 (measured) | 3.3 | no |
| Multiple-commodity, per train: one relief/drain sheet and one utility sheet, plus the interarea sheet | ≈ 25 % (arithmetic: 63 × 2 + 62 sheets; not simulated) | ≈ 750 (arithmetic) | ≈ 10 | no: still train-sized areas, and p.34 says big plants tend to single-commodity |
| Per area of 4 trains | 24.4 % | ≈ 755 | 7.8 | no: an area of about 35 process sheets matches no document unit |
| **Per area of 10 trains, single-commodity, interarea only between areas** | **17.2 % / 17.0 %** (490 / 505 units: 989 / 1,022 sheets) | **819 / 848** | **11.8 / 11.9** | **chosen** |
| Per plant: one header per service | 13.1 % | ≈ 870 | 15.2 | no: a ~10-document region has no single plant-wide flare drawing, and every interarea sheet is lost |

**Ruling.**
1. **Area.** An area is a run of `trains_per_area` = k consecutive trains: train t lies in area ⌈t / k⌉.
   - **Declared k = 10, by definition.** The area is the ~100-sheet document of §18.2. At k = 10 the what-if gives
     about 88 process sheets and 16 header sheets per area.
   - **T7b measures it and applies a fixed rule.** It measures the median area's total sheets for k = 8–12 on the
     seed-7 1,000-sheet dev plant, and sets k to the integer whose median is nearest 100 (on a tie, the smaller k).
   - This fixes what a document is (the thesis scope's ~100 pages). It is fitted to no score.
2. **Header units.** One header unit per (area, service), numbered 9000 + 10·area + the service index.
   - Single-commodity (p.34).
   - The capacity of 16 and the continuation connector are unchanged.
   - Until T6, the conventions are those of the area's first train.
3. **T6's document is this area.** `trains_per_document` is `trains_per_area`. T7b does T6's step "declared from the
   median trains per 100 total sheets after T7": one knob, one meaning.
4. **Interarea sheets.**
   - **Which lines.** Only a line whose two trains lie in different areas passes an interconnecting sheet
     (pp.33–34: area borders). A join inside one area stays as v2.1 drew it, a process-to-process off-page pair.
   - **One unit for the plant.** All inter-area lines go on one interconnecting unit, numbered 9008 (area slot 0,
     interarea index).
     - At most 16 lines per sheet, in area order, with overflow on the next sheet.
     - Its conventions are area 1's.
     - On seed 7 every train join runs from train t to t + 1, so each area border carries one line. One sheet per
       border would be a sheet holding one straight pipe, which the ch.20 interconnection sheets are not.
5. **Prefix stability.**
   - The area of train t depends on t alone.
   - Total sheets stay monotone in n: a new unit adds tie-ins to the last area's headers, or opens a new area and
     one inter-area line.
   - The S15 restatement of §7 holds unchanged.
6. **What changes with scale.**
   - A 100-sheet plant is one area: no interconnecting sheet, and TOG33 has 0 instances there (reported, not a
     failure).
   - A 1,000-sheet plant has about 10 areas and one interconnecting sheet.
   - So only at 1,000 sheets does a line between areas gain a sheet crossing. Like the per-document conventions
     (§18.2), this is a real property of plant scale, and it is reported, not hidden.
7. **Header sheet density.** About 12 tie-ins per header sheet is denser than the two ch.20 sheets (7 and 8) but
   inside the capacity and the stub ceiling. T12b reports the comparison.

**Expected sheet mix after T7b.** Estimates from the what-if at k = 10; T7b measures them.

| | 100-sheet target | 1,000-sheet target |
|---|---|---|
| units | ≈ 48–50 | ≈ 490–505 |
| process sheets | ≈ 81–86 | ≈ 820–845 |
| network (header) sheets | ≈ 14–15 | ≈ 160–165 |
| interarea sheets | 0 | 1 |
| network + interarea share | ≈ 15–16 % | ≈ 16–17 % |
| tie-ins per header sheet, mean | ≈ 11–13 | ≈ 12 |

For comparison: v2.1 had about 100 / 1,000 process sheets (EXP-0008), and T7 as built 60 / 555 (measured).

#### N3. The T7 coder's assumptions

| # | Assumption | Ruling | Reason |
|---|---|---|---|
| 1 | Rupture-disc outlets stay end fittings | **overruled** | The reactor rupture-disc line is drawn in service FL and documented "to the flare" (`patterns/reaction_parts.py`). Yet 39 of them end open on the seed-7 1,000-sheet plan. Relief devices discharge into the emergency release collection network (p.368). T7b ties `reactor_rupture_disc` into the FL sub-header like a PSV and adds it to TOG32's relief set. TOG156 exempts it as `relief_path` (R2) |
| 2 | Non-FL thermal PSV outlets (on CWR, 103 on that plan) and steam-stub PSV outlets (on MPS, 68) stay end fittings | **accepted** | Water and steam are innocent fluids: their vents go to atmosphere (TOG Table 8.9, pp.140–141). The real WTP sheet discharges its CW thermal PSVs "TO SAFE LOCATION" (`real-pid-samples-2026-10.md` §6 #1). **Condition:** T7b asserts that no relief device on a HYDROCARBON-class line ends open |
| 3 | Vacuum-line drains stay capped (`vacuum_drain`) | **accepted**, as a DESIGN reading with no page | Nothing flows from vacuum into the closed-drain header, so the cap is a maintenance end. The count is reported, and checklist item 18 lets the expert call it |
| 4 | TOG207 and TOG270 treat sub-header and header tees as non-process paths | **accepted**, by role (`sub_header_tee`, `header_tee`), never by position | Consistent with R2 (process services only). A pump is not "flow-controlled" through a flare header, and an exchanger is not "isolated" by a network tee |
| 5 | A machine's `ActuatingElectricalFunction` is drawn on the machine's sheet (`sheets.py`) | **accepted** | Motor control sits at the motor (TOG pp.351–356), and a control edge is never cut (S20). **Condition:** the v1 and v2.1 goldens stay byte-identical, which proves the coder's "v2.1 already agrees" |
| 6 | Network root valves are NO and take the generic tag convention until T6 | **accepted** | Root valves are manual isolation valves at the start of sub-headers and branches (p.362), normally open. Only distribution headers get them: p.368 says manual valves on the flare network should be eliminated or locked open. After T6 they follow their area's document convention (N2.3) |

#### N4. The size search after T7b (main session, 2026-11-23)

T7b's report (committed `3e42a6a`) measured the following on seed 7. Every unit step that opens a new area adds that area's header sheets at once, so the total sheet count jumps:

| From | To |
|---|---|
| 56 units, 109 sheets | 57 units, 114 sheets |
| 1,099 sheets | 549 units, 1,103 sheets |

As a result, "the fewest units whose total is at least the target" overshoots by +4 at a target of 110 and by +3 at 1,100. Seed 5 at a target of 100 lands at 103. The +4 at 110 leaves the user's band of 90–110.

**Ruling.**
- The v2.2 size search returns the unit count whose total is **nearest** the target. A tie goes to the fewer units.
- The landed total must lie inside the user's band: 90–110 for the 100-sheet scale and 900–1,100 for the 1,000-sheet scale. A total outside the band raises.
- Acceptance criterion 6 of T7b becomes "within ±3 of the target, and inside the band". It is checked at 90, 100, 110, 900, 1,000 and 1,100 on seed 7, and at 100 on seeds 1–5.
- The v2.1 search keeps its "at least" semantics, so the v2.1 goldens do not change.
- Reason: the band, not the exact target, is what the user fixed (D5). Nearest-total halves the worst miss, and it never leaves the band at the band edges.
- This change is step 0 of T6.

T7b itself is done and committed as `3e42a6a`. On seed 7 it measures:

| Measure | 100-sheet plant | 1,000-sheet plant |
|---|---|---|
| Total sheets | 100 | 1,000 |
| Process sheets | 84 | 836 |
| Header sheets | 16 | 163 |
| Interarea sheets | 0 | 1 |
| Network share | 16.0% | 16.4% |
| Stubs per sheet, maximum | 12 | 18 |

The chosen k is 10 trains per area.

### 17.15 Rulings on T6 (`cc4d5ef`): the gold side of scope R, 2026-11-23

**Inputs.**
- The T6 coder's five issues. Its numbers are its own one-off measurements and I did not re-run them: the literal
  tie rule refuses 54 % of 400 random FLOW_PATH pairs on a fully tagged plant and 72 % on an untagged one; the
  untagged refusal removes 213 of 262 isolation candidates on an untagged plant; the frozen validator gives 1,175
  "missing tag" violations there.
- My read-only reading on 2026-11-23: `qa/questions/{common,families_flow,families_isolation,
  families_heldout_paths,families_heldout_route,templates}.py`, `qa/harness/{gold,line_view_fidelity}.py`,
  `qa/scoring.py` (`score_path`), `graph/line_view.py`, `qa/harness/question_set.py`, ADR-0060 and the system-side
  path list in `30-experiments/EXP-0007-v2-remeasurement-plan.md` §2, and the E9 file list.

**Four facts from the code that decide the rulings.**
- **F-a.** `qa/questions/` is not on ADR-0060's system-side path list (EXP-0007 plan §2), and §10 already calls it
  gold side. `E9.sha256` hashes all of `src` only because EXP-0008 froze everything at once. G0f checks the
  system-side subset.
- **F-b.** `score_path` marks a FLOW_PATH answer correct when it runs from the source to the target over real flow
  edges (`_is_valid_ordered_path`). The F2 reference path feeds only the F1 sub-score and the evidence (k, u). A tie
  between equal-length routes never made a question ambiguous for correctness.
- **F-c.** The templates ask "Which equipment items and valves receive flow directly from X?" and "List every
  equipment item and valve in order". The frozen line view (`LINE_ITEM_CLASSES` = equipment | valves) treats every
  valve as a line item, tagged or not. An untagged gate valve is a valve.
- **F-d.** `item_valve_counts` (VALVES_ON_PATH) counts only path items. If `is_path_item` returned False for an
  untagged valve, that valve would be folded away like a tee and not counted.

So §11's "untagged valves drop out of the listing, as fittings do now" was my error. That gold would omit a valve
the question asks for, and it would disagree with A2's own line view. The coder's smallest fix (`is_path_item`
False when untagged) would carry the same error, and by F-d it would also break §11's "VALVES_ON_PATH: counted".

#### S1. Question generation is gold side, and it may change for EXP-0009, under three conditions

- No system-side path changes (G0f, F-a).
- **EXP-0008's own sealed question files regenerate byte for byte** (T6b criterion 1). This is stronger than the
  H1g21 golden, because a one-sheet plant does not exercise every family.
- The E10 freeze hashes all of `src` again, so the changed gold files are frozen for EXP-0009.

*Why:* this is ADR-0060 1B's pattern; E7 changed `gold.py`, `family_meta.py` and `need_gold.py` the same way. The
v2.1 question hash cannot change, because v2.1 plants hold no untagged valve: the frozen validator requires a tag on
every valve class. *Who:* T6b.

#### S2. One refusal rule for every family, as ADR-0066 decision 5 (S-A) words it

- **Rule.** A candidate is refused when its text, its anchors or its reference would have to name a node that
  prints no tag. This applies to every family, not only the isolation families.
- **`is_path_item` and `next_path_items` stay unchanged.** Untagged valves remain items:
  - they stop the "directly downstream" walk, as in the frozen line view;
  - they count in VALVES_ON_PATH;
  - they sit on FLOW_PATH routes, where they refuse the pair.
- **Mechanism.** Family code reads a printed name through one helper, which returns the tag or a fixed marker. One
  filter after candidate building drops every question that carries the marker and counts the refusals per family.
  - One rule, one place, one count.
  - The random draws are untouched (a refused candidate consumes its draw as before), so on v2.1 the bytes are the
    same.
- **`harness/gold.py`.** `_edges_through_fittings` skips untagged endpoints, as `_direct_tag_edges` already does. A
  path answer that skips an untagged valve is then invalid. That is right, because the question asks for every
  valve.
- **Module.** `gold_scope_r.py` moves to `qa/questions/untagged.py`. It is question-generation code, and the
  generator package should not import `qa`.
- **Rejected:**
  - the coder's `is_path_item` change (F-c, F-d);
  - refusal inside each builder (about 25 tag reads and 25 counters);
  - drawing another target when one is refused (it prefers tagged routes, shifts the k distribution, and adds code).

*Who:* T6b.

#### S3. How A2 and B answer the same scope-R questions

- **One generation.** The questions are generated once per plant, on the A corpus id, from the gold plant that both
  views share.
- **B's file is a relabel.** It changes only the corpus id (the field and the question-id prefix). The frozen
  `harness/question_set.py` refuses questions of another corpus, so B needs its own id.
- **Test.** The two files are equal after the corpus id is stripped. SB1 pairs rows by the stripped id. The 40 X
  questions both arms answer are relabelled the same way.
- *Why:* the two files are identical by construction, and B needs no second question pool. §12.3 puts the pools of
  six 1,000-sheet plants at about 14.3 h.

*Who:* T13 (R) and T15 (X).

#### S4. The FLOW_PATH tie rule is withdrawn; F2 stays as in v2.1

- **Why:** by F-b, ties never affected correctness. The literal rule refused 54 % of pairs even on a fully tagged
  plant, which would have changed R's recipe against EXP-0008.
- **Untagged valves are handled by S2.** A pair is refused when its F2 reference path holds an untagged valve.
  `tagged_sequences_differ` is deleted.
- **A known property, accepted.** In a tie, F2 ranks an untagged node by its node id (`layer_sort_tags`). When a
  tagged route and a route through an untagged valve tie, node-id order therefore decides whether the pair
  survives. The order is deterministic and tied to no score. It is documented, not fixed.

*Who:* T6b.

#### S5. The isolation survivors: not used in R; in X they are ordinary members

- **R's two isolation families stay pre-registered unavailable at both scales.** The stated reason is corrected:
  - It is not "no candidate": 49 of 262 survived on the coder's untagged plant.
  - The reason is **selection**. A survivor is an item whose first valve on every route is an automatic valve
    (control or switching), because those keep their tags.
  - R would then ask about every item on a tagged plant but only about such items on an untagged one. Its question
    population would depend on the tagging draw, and the data-effect comparison with EXP-0008 would compare
    different populations.
- **In X.** The X isolation families are drawn without the refusal, so the survivors are ordinary members of that
  population. X already reports per question whether the gold holds an untagged valve. That is where the survivors
  show.
- **Reported:** R's would-be kept share per plant, descriptively.

*Who:* T6b counts the shares; T15 builds X.

#### S6. Availability of the families S2 now thins, fixed before any seed is drawn

- **Which families.** FLOW_PATH, NEIGHBOURS_DOWNSTREAM and ROUTE_AVOIDING can lose most of their candidates on
  untagged plants. FIRST_MEETING_POINT is already unavailable on v2 (ADR-0060).
- **Rule.** T6b counts each family's kept candidates on the 100-sheet dev plants of seeds 1–5 with every document
  forced untagged. A family below 10 on any of them is pre-registered unavailable in scope R at both scales, for the
  §11 reason:
  - four of every five sealed 100-sheet plants are untagged (§18.3);
  - the weight is not tuned to rescue a family.
- **Reporting.** Its refused share is reported. No new X family is added for it: ADR-0067 fixes X, and growing it
  is scope.
- **G0e** still applies on the sealed plants.

*Who:* T6b measures; the main session copies the resulting list into §11 before PREREG A.

#### S7. LINE-01 on v2.2, and a smoke test of the frozen system on an untagged plant

**The problem.** The frozen `system_line_view` raises on an untagged line item, and `gold_line_view` reads tags.
EXP-0008's launcher runs LINE-01 on every plant (`lib_plants.sh` `line_view_gate`). The file is on the system-side
list, so it stays as it is.

**Ruling.**
- **A new gate, `qa/exp0009/line_view_gate.py`.** It makes the same comparison, but keys untagged line items by their
  neighbours, as `api_fidelity` already names an untagged item.
  - Colliding keys are counted and must be 0.
  - On a v2.1 plant it must reproduce the frozen LINE-01.
- **A free smoke test.** The frozen A2 layers that use no model (`build_item_graph` over `NetworkxGraphView`, the line
  view, the schema text) must run on an untagged dev plant without an exception.
  - D1 = C assumes that A2 can ingest these plants.
  - If a frozen module raises, T6b stops and the case returns to the architect.

*Who:* T6b builds both; T13 puts the gate into the plant gates.

#### S8. Validation: leave the frozen validator, and add a v2.2 wrapper

- **Leave `graph/validation.py` byte-unchanged.** It is frozen, the Proteus import uses it, and so do the v1 and v2.1
  tests.
- **Add `benchmark/v2/validation_v22.py`: `validate_plant_graph_v22(plant, record)`.** It runs the frozen validator
  and removes exactly the "missing tag" violations on manual and check valves in documents that the record marks
  untagged. Every other violation stays.
- **Rejected:**
  - exempting valve classes inside `validation.py`: it touches a frozen file, and a control valve or PSV could then
    lose its tag unnoticed;
  - not validating v2.2: it would lose a free structural check on exactly the plants EXP-0009 measures.

*Who:* T6b builds it; T13 wires it into G0c.

#### S9. The stratified allocation belongs to T13 (confirmed)

`handbook.document_untagged` is only the override that carries the allocation. T13 draws the allocation after the
size search has landed, because a document is an area (§17.14 N2):
- **100-sheet plants:** exactly 4 of the 5 sealed plants are untagged. Which four is drawn from the seed tool's
  stream.
- **1,000-sheet plants:** each plant leaves round(0.8 × its documents) untagged, rounding half up (7 of 9, 8 of 10,
  9 of 11). Which documents is drawn from the same stream.
- The allocation is written into PREREG A before any build, and G0k checks it.

### 17.16 Main-session rulings on the T10 report, 2026-11-24 (committed `8b34921`)

1. **Size search at the band edge.** T10's added instruments moved the sheet totals. For seed 7 at target 900, the total nearest the target became 899, which is outside the band.
   - **Amendment to N4:** only totals inside the target's band compete. A tie goes to the fewer units. The search raises only if no total lands in the band.
   - The headers of a new area arrive about five sheets at a time, so the spot-check tolerance is now **±5 inside the band**, not ±3. The band is the binding constraint.
   - Seed 7, measured: 90 → 91, 100 → 100, 110 → 110, 900 → 904, 1,000 → 999, 1,100 → 1,100. Seeds 1–5 at 100 land at 99–100.
2. **The fuel PSHH sits after the last regulator.** API 14C A.6.3.3, p.33, puts it on a new `fuel_gas_psh_tee` between the PV and the TV station. The existing `fuel_gas_pressure_tee` no longer carries the switch.
3. **The coder's choices, all accepted.**
   - Compressor sensors sit on `compressor_suction_tee` and on `discharge_psv_tee`.
   - TOG236 covers every hydrocarbon tank. The emergency vent stays outside `RELIEF_ROLES`.
   - No new random streams: every addition is structural.
   - TOG207-HX-PSD-BOTH-SIDES adds nothing, because every side is `side_not_blockable` (D8).
4. **Counts after T10.** All 54 encoded rules are wired. There are now **24 deferred rows**, not 15, because the generic SAC deferral was split into 10 item rows.
5. **Composition after T10, measured (all bands pass):**

   | Run | Valves per process sheet | Instruments per process sheet | Instruments : valves |
   |---|---|---|---|
   | Seeds 1–5 pooled | 24.54 | 34.52 | 1.41 |
   | Seed 7, 100 sheets | 23.16 | 35.80 | 1.55 |
   | Seed 7, 1,000 sheets | 25.00 | 36.47 | 1.46 |

   Seed 2 alone measures 37.19 instruments per sheet, against a band top of 38. Any later addition must re-check that headroom.

### 17.17 Main-session rulings on the T6b report, 2026-11-24 (committed `a2beb7e`)

1. **The line-view gate key is colour refinement.** Measured key collisions with each key:

   | Key | Seed 1 | Seed 7, 1,000 sheets |
   |---|---|---|
   | Nearest tagged items up and down | 200 | 706 |
   | Same, with the valve class added | 96 | – |
   | Colour refinement | 0 | 0 |

   - Colour refinement starts from tags and classes and refines over the whole flow graph until stable (`qa/exp0009/structure_names.py`). It is still "keyed by its neighbours", carried out to the fixed point. **Accepted.**
   - Truly automorphic twins would still collide, and the gate counts them as designed.
   - On D100g21 the gate gives the frozen LINE-01 result.
2. **Scope R availability after S6, measured** on the forced-untagged 100-sheet seeds 1–5.
   - Kept below 10, and so pre-registered **unavailable in scope R at both scales**:
     - DOWNSTREAM_IN_UNIT (0 on every seed);
     - UPSTREAM_SOURCES (0 on every seed).
   - Already unavailable for other reasons: UPSTREAM_ISOLATION and DOWNSTREAM_ISOLATION (S5), and FIRST_MEETING_POINT (excluded on v2).
   - The families S6 anticipated stay available: FLOW_PATH keeps ≥ 92, NEIGHBOURS_DOWNSTREAM ≥ 203 and ROUTE_AVOIDING ≥ 651.
3. **UPSTREAM_SOURCES and the line blinds.** Even on tagged plants this family keeps only 6–24 of about 270 candidates, because an untagged spectacle blind can head a battery-limit line. **No exemption** for non-valve parts: S2 stays one rule. The family is unavailable by rule 2 above anyway, so an exemption would change nothing that is measured.
4. **Consequence for the thesis.** Scope R in EXP-0009 is narrower than EXP-0008's set by these families. The comparison with EXP-0008 is made on the families both runs share, and the dropped families are listed with the reason for each.
5. **Byte-for-byte check.** EXP-0008's sealed questions regenerated identically for all three plants:

   | Plant | Machine time |
   |---|---|
   | H100g21p1 | 39 s |
   | H100g21p2 | 35 s |
   | H1000g21p1 | 6,657 s |

   G0f is `[]`.

### 17.18 Main-session rulings on the T14d report, 2026-11-24

1. **There is no B seed.**
   - §10.9 assumed that `GraphAgentLinesB` inherits a seed from `build_seed`.
   - In the code, `GraphAgentLines` has `_seeded = False`. Only the dropped `HierAgent` called `build_seed` (ADR-0047). So neither A2 nor B starts from a seed map.
   - `seed_b.py` is deleted, together with the seed-coverage and seed-footprint checks. What B shows is its tool item lines. The exactness check covers those: 100% on forced-untagged seed 1, with 8,571 items, 1,493 positioned and 1,713 untagged valves carrying line numbers.
   - Before the deletion, the dropped footprint check measured 2 of 148 scope-R seeds (1.35%) cut by B but not by A. That number describes a seed no agent shows, so it is recorded here for completeness only.
2. **Accepted as built.**
   - `line_numbers` is a `|`-packed string. No generator line number contains `|`.
   - The literal example in the B prompt sentence may be reworded during the P1a tuning rounds.
   - `load_b` takes the profile from `ingest.json`. T13 ingests B corpora with `plant_lines`.
3. **The B Neo4j loader is tested with stubs only.**
   - The local Neo4j was not running.
   - T13's first B load is the first live run of `count_positions_in_database`. If it fails, T13 stops.

### 17.19 Main-session rulings on the T13 report, 2026-11-24 (committed `2995480`)

1. **The policy hash is canonical.**
   - `policy_b().model_dump_json()` is not stable between processes, because the `accept` sets are written in hash-seed order. The coder measured three different digests across three runs.
   - E10 therefore hashes a canonical form: sorted keys and sorted string lists. This was tested under three hash seeds.
   - **Accepted.** It replaces "the raw dump" of §10.9.
2. **G0e for the validation and dev plants** is applied over each role's own plants, because the sealed pools do not exist before B10. **Accepted.**
3. **Gaps accepted.**
   - G0h is not built. The harness's own run-start check stays in place.
   - The smoke run does not cover P1d's judge or the live G0f replays. P1d and the first live Neo4j loads are the first runs of those code paths, and a failure there stops the launcher.
4. **The coder's assumptions, all accepted.**
   - The split names are `x-dev` and `x-held-out`.
   - The T17 path prefixes are as built.
   - The A build uses store profile `both` (the CLI default). The B load takes `plant_lines` from `ingest.json`.
   - Readiness reuses EXP-0008's helpers.
   - A $0 run falls back to the §19.9 cost keys.
   - The G0l stop asks the user. The main session then brings in the architect.
5. **Before F10,** everything must be committed, because E10 hashes tracked files only.
   - The draw is run once. It scans `data/runs` for seeds already used.

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
| 12 | Extra protection devices from API 14C (compressor pressure and temperature switches, vessel level and pressure switches; corrected: the blowdown valve is not an API table item and stays out) | **now, in T10** | cheap devices are added where the composition bands allow; the rest are listed one by one as deferred |
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

### 18.8 The user's answers of 2026-11-23, second round

- **Item 1:** ADR-0066 and ADR-0067 are accepted.
- **Item 2:** 5 + 5 plants per scale.
- **Item 3:** yes. The document unit (the area of §17.14 N2) also applies to spare naming and to the XV/YV letter.
- **Item 5: there will be no expert reviewer.**
  - T12a (the review package) and the review half of T16 are dropped.
  - The thesis states plainly that no practising engineer reviewed the generated sheets. It lists this as a limitation beside the unmodelled chemistry, sizing, set points and frequencies.
  - The rules are book-cited and machine-checked, but they are not externally reviewed.
  - The 25-item checklist of §18.5 stays in the record as the map from plain questions to rule ids. Items 1–23 are each covered by an automatic check, item 24 by the composition bands, and item 25 is not covered.
- **Item 4:** no margin. SB1 is reported descriptively, as B − A2 on R with its interval.
- **Measurement record (user, 2026-11-23; T13 acceptance).** EXP-0009 keeps EXP-0008's record format for both arms. For each model call, `calls.jsonl` holds the tokens, cost, latency and provider id. For each answer, `answers.jsonl` holds the final answer, correctness, tokens, cost, latency and the retrieval trace. Each run also writes `timings.jsonl` and `environment.jsonl`. With these records and the gold answers, precision, recall and F1 can be recomputed after the run without paying for new model calls. A T13 test asserts that every scored answer has a matching call record with cost and token fields filled in.
- **Item 6:** the user tops up about $25. With the roughly $17 already on the account, P1 fits even at its $37.50 cap.
  - **Update (2026-11-24, main session):** the user set a **hard total cap of $35** for P1 (runs and audit together) and
    approved P1 even if the estimate rises above $25. The OpenRouter balance is $37.11. §19.9 applies it.

## 19. T13 specification: the EXP-0009 P1 launcher (2026-11-24)

This section is the one ordered specification of T13. Where it differs from the T13 row of §13 or from §12.2–§12.4,
§17.15 S3/S7–S9, §17.17, §18.8 or `v2t-b-system-revision.md` §10, this section wins, and the reason is given in place.
ADR-0068 (proposed) records the five launcher choices that had a real alternative.

### 19.0 What T13 is, and is not

- **What it is.** T13 builds and tests the EXP-0009 launcher for **stage P1 only**, plus the draw tool that feeds
  PREREG A. P2 (ladder, identity, D4, F1) is a later task.
- **The task rules.**
  - Every rule of §13 applies.
  - T13 makes **no paid call and builds no EXP-0009 plant**. Its tests use fake senders, tiny plants, the small real
    v2.2 plant of `tests/v2tb/plants_b.py`, and the EXP-0008 plants that already exist.
  - It ends with one commit proposal.
- **T13 writes no B system code** (`v2t-b` R7). It calls `qa/v2tb` through its public functions and its two CLI
  subcommands, `run` and `load` (T14d).
- **No file of E9's system-side path list changes** (G0f). EXP-0008's own scripts and modules are not edited either:
  they are hashed in `E9.sha256`. T13 copies what it needs into the EXP-0009 folders, with each copy's docstring
  naming its original.
- **Prerequisite.** T14d is committed.

### 19.1 Layout and ids

**Folders.** The root is `data/runs/exp0009/`, with the same layout as `exp0008/`:
- `state/`, `logs/`, `prereg/`, `inputs/`;
- `corpora/`, `neo4jplant/`, `cypcorp/plant_lines/`;
- `qpool/`, `questions/`;
- `tune/`, `val/`, `sealed/`, `audit/`, `reports/`.

The scripts are `run_all.sh`, `launch.sh`, `lib.sh`, `lib_plants.sh`, `lib_runs.sh`, `stages/*.sh`, `README.md` and
`PREREG_A.template.md`. `inputs/` holds copies of the E9 pins and parameters: `params_b.json`, `pins_b.json` and the
EXP-0008 A2 inputs. The environment variables are EXP-0008's, under the prefix `E10_`.

**Ids.**

| Role | A id | B id | Seed | Size |
|---|---|---|---|---|
| tuning (dev) | `D100g22` | `D100g22B` | 1 | target 100 |
| P0 composition and rules only | `D1000g22` | — | 1 | target 1,000 |
| validation | `VAL100g22`, `VAL1000g22` | `VAL100g22B`, `VAL1000g22B` | drawn | drawn in band |
| sealed | `H100g22p1`…`p5`, `H1000g22p1`…`p5` | the same ids + `B` | drawn | drawn in band |

An id names the **nominal** scale (100 or 1,000), never the drawn target. A plant with target 97 is `H100g22p3`.

**Python package `src/plantgraph/qa/exp0009/`.** These modules are new; the ones that exist stay as they are.

| Module | Holds |
|---|---|
| `plan.py` | `PlantSpec22` and `Exp0009Plan` (Pydantic, frozen): per plant its id, scale, seed, drawn target, `n_units`, predicted total sheets, document count, untagged-document flags; the plant lists by role |
| `draw.py` | the draw of §19.2 |
| `build.py` | the A build, the B relabel, the positions step and the corpus record of §19.4 |
| `load.py` | the A Neo4j load and the `cypcorp` copy (§19.4); B loads go through `python -m plantgraph.qa.v2tb load` |
| `questions.py` | pools, drop set, samples, A2 and B files, relabel, baselines file (§19.6) |
| `gates.py` | G0c, G0e, G0k, G0l, the G0-B wiring, G1, G1-B, G1-B2 (§19.5, §19.7) |
| `caps.py`, `ledger.py` | §19.9 |
| `freeze.py`, `prereg_b.py` | §19.8 (they reuse `exp0008.freeze`'s pure helpers by import) |
| `records.py` | the measurement-record check and the offline re-score (§19.11) |
| `cascade_report.py` | the offline cascade per arm, with `cascade_v4_iso` for A2 and `policy_b()` for B |
| `audit_b.py` | the B stratum selection (§19.7, P1d) |
| `smoke_harness.py` | the fake-transport entry points of both arms, for `--smoke` |
| `launcher.py` | `python -m plantgraph.qa.exp0009.launcher <command>`: every decision the shell needs, each with a test |

### 19.2 Step 0: the draw, before PREREG A (free)

`python -m plantgraph.qa.exp0009.launcher draw --draw-seed N`. It never overwrites a file it writes. A refusal
writes nothing.
1. **Seeds.**
   - `exp0008.draw_seeds.draw_seed_plan(N, hygiene.retired_seeds(data/runs), …)` gives the draw. The retired set
     includes every EXP-0008 seed, because hygiene reads `data/runs`.
   - The result goes to `prereg/seeds.json`.
   - The ladder seeds are drawn too, unused in P1, so that P2 needs no second draw.
2. **Size targets.**
   - The stream is `random.Random(f"exp0009:targets:{N}")`.
   - The order is VAL100g22, VAL1000g22, H100 p1–p5, H1000 p1–p5.
   - Each target is `randint(90, 110)` or `randint(900, 1100)`.
3. **Size search.**
   - Each plant runs `smallest_n_units_v2(target, HeadlinePresetV22(), seed)`, the call the ingest CLI and
     `exp0009/dev_plants.py` make. It records `n_units` and the predicted total.
   - **Refusal:** |predicted − target| > 5. This is §17.16's tolerance, which replaces G0k's "within 2".
4. **Documents.** The count is `len(plan_plant(config).documents)`.
5. **Tagging allocation (S9).** The stream is `random.Random(f"exp0009:tagging:{N}")`, in the same order.
   - **100-sheet sealed:** `sample(p1…p5, 4)` are untagged.
     - Every document of an untagged plant is untagged, and every document of a tagged plant is tagged.
     - A 100-sheet plant normally has one document, but a 110-sheet plant may have two.
   - **1,000-sheet sealed:** per plant, `sample(documents, round_half_up(4/5 × n_documents))` are untagged.
     - Compute it with exact `Fraction` arithmetic.
     - Half never binds, since 4n/5 never ends in .5, but the rule stays as S9 states it.
   - **Validation (ruling).** VAL100g22 is untagged, and VAL1000g22 follows the 1,000-sheet rule.
     - *Why:* G1-B must test B on the population the sealed plants mostly are.
     - A drawn tagging would leave the 100-sheet validation plant tagged with a chance of 0.25. Its X questions would
       then barely exercise descriptors.
   - **Dev plants.** D100g22 keeps its drawn tagging. Measured today with `plan_plant`: one document, untagged.
     D1000g22 keeps its draw (10 documents, 9 untagged, measured today).
   - **Flags.** `handbook.document_untagged` gets exactly `n_documents` flags.
6. **Text prior (R12).** `position_baselines` fits on dev seeds 1–5 and writes `prereg/position_prior.json` (sorted
   keys). Its sha256 goes into the plan file. The majority code is recorded as well: NO, as measured in §10.8.
7. **Output.** The tool writes `prereg/plan.json` and prints the PREREG A tables: seeds, targets, `n_units`, predicted
   totals, documents, allocation, prior sha256.

**Measured today (architect, `plan_plant`, free):**
- the 1,000-sheet size search for seed 1 took 27.1 s (one 1,000-sheet plan 7.6 s);
- a 100-sheet plan took 2.3 s.

The whole draw is therefore minutes. The prior fit is extra, and its time is not measured here.

### 19.3 PREREG A (template; filled by the main session, committed on the user's order before P0)

`data/runs/exp0009/PREREG_A.template.md` follows EXP-0008's template and adds the following.
- **Frozen code.** The A2 system is E9 (`5d31cbb…`), checked by G0f.
  - "Part A code commit: `<40 hex>`" is the HEAD at the commit of part A.
  - Between that commit and E10 only these may change:
    - B files under `src/plantgraph/qa/v2tb/` and `tests/v2tb/` (tuning);
    - the T17 analysis module and its tests (§19.11);
    - `data/runs/exp0009/prereg/`;
    - `docs/`.
- **Claims.** Q4, Q4-B, SB1 (descriptive), SB2, K1–K3 and Q5, with their pass rules (§12.1). The descriptive list adds:
  - the Q4-B sensitivity row without POSITION_OF_VALVE;
  - POSITION accuracy by form and by code, beside the majority and the text prior;
  - the realized `named_by` mix per scale;
  - the X sub-scopes;
  - refused shares;
  - network-touching shares.
- **Plants.** The tables of §19.2.
- **Scope R.**
  - The available families, which are all v2 families except these five, pre-registered unavailable at both scales:
    - UPSTREAM_ISOLATION and DOWNSTREAM_ISOLATION (S5);
    - DOWNSTREAM_IN_UNIT and UPSTREAM_SOURCES (§17.17);
    - FIRST_MEETING_POINT (v2).
  - The recipe: EXP-0008's sealed recipe, then the drop set.
  - G0e's rule.
- **Scope X.**
  - The five families, their splits, and 10 per family: B 50, A2 40 via the TAG_SET adapter.
  - R9's texts and R11's two POSITION forms.
  - G0l's quarter rule.
- **POSITION baselines.** The majority code, the prior file and its sha256.
- **Positions file.** The method only (§10.9 R18), not a hash.
- **Money.** §19.9: the program cap of $35, the ledgers, the per-tier costs, the caps without dry runs.
- **B tuning.**
  - At most three rounds, on D100g22 only, dev families only.
  - Stop when a round adds less than 1 point, or after round 3.
  - The E10 candidate is the round with the highest B dev accuracy, and a tie goes to the earlier round.
  - The log is kept in the EXP-0009 experiment note, not in ADR-0067, because an accepted ADR is not edited.
- **Gates.** §19.5 and §19.7, including the branch: if G1-B or G1-B2 fails, B is not run sealed.
- **Audit.** EXP-0008's rule, plus a B stratum half the main sample's size; the judge prompt and pin hashes.
- **Bootstrap.** The resample count and seed of the EXP-0008 claims code.

### 19.4 Building and loading a plant: two views, one corpus in Neo4j at a time

**Build (free).** `launcher build --plant <A id>`, for each plant of `plan.json`:
1. **A build.**
   - The config is `HeadlinePresetV22().generator_config(n_units, seed)`, with `handbook.document_untagged` from the
     plan.
   - It goes into `ingest.pipeline.run_synthetic(corpus_id=<A id>, check=True, settings=None)`, with the preset's split
     config and the store profile EXP-0008's `build_plant` used (the CLI default).
   - The frozen writer (`ingest/__main__._write_result`, imported, not copied) writes
     `corpora/<id>/ingest.json` and `rules.json`.
   - The seed is checked against `prereg/seeds.json` with `require_drawn_test_seed`, **never** against the
     EXP-0008 default path.
2. **B corpus files.**
   - `corpora/<id>B/ingest.json` is A's file with `corpus_id` replaced, which is the S3 pattern for questions. A
     test checks that the two files are byte-identical once the id is replaced back.
   - `rules.json` is copied.
   - *Why a relabel:* the uids are built from the corpus id at rebuild time, and nothing else in the file depends on
     it. A second build would cost one 1,000-sheet generation (8–12 min) per plant for identical content.
3. **Positions.** `v2tb.store_b.ingest_positions(config, corpora/<id>B)` writes `operating_positions.json`. G0-B check 1
   runs inside it.
4. **Record.** `corpora/<id>B/corpus_b.json` holds the A id, the sha256 of both ingest files, the positions file's
   sha256 and count per code, and the seconds of steps 1–3.

**Neo4j (only inside paid stages). Every load recreates the database first (`--fresh-database`).**
- **A load.**
  - `launcher load-a --plant <id>` runs `run_synthetic` with Neo4j settings, `store_profile="plant_lines"` and
    `StoreMeasurement(fresh_database=True)`, on the config of `corpora/<id>/ingest.json`.
  - It writes `neo4jplant/<id>/ingest.json`.
  - It copies that file to `cypcorp/plant_lines/<id>/` **once**, never replacing it, as in EXP-0008.
  - `check_loaded_matches` follows.
- **B load.**
  - `cypcorp/plant_lines/<id>B/ingest.json` is the relabel of A's `cypcorp` copy. The positions file is copied
    beside it, and its sha256 is checked against `corpus_b.json`.
  - Then `python -m plantgraph.qa.v2tb load --corpus-id <id>B --corpora-root cypcorp/plant_lines --fresh-database`
    runs. Its database-side G0-B (R19) must pass.
- **One corpus at a time** (user rule): every load wipes first.
- **End state.** The last action of END runs the EXP-0008 `demo_load.sh` steps: wipe, then H1000g21p1 with
  `plant_lines`, the plant the demo expects (ADR-0064, `demo-v2.md`). A stop leaves the last plant loaded. The README
  says how to restore the demo plant by hand.

### 19.5 The free gates, and when each runs

| Gate | Check | Runs on | When |
|---|---|---|---|
| G0a | full `pytest`, `ruff`, `mypy --strict`; v1 and v2.1 goldens | — | P0 |
| G0b | the rule-suite tests; every rule and alternative non-vacuous over dev seeds 1–5 (the T7b/T10 report) | dev seeds | P0 |
| G0c | `OWED_FIXES == {}`; the plant's `rules.json` holds 0 violations of every wired rule; `validate_plant_graph_v22(plant, record)` gives 0 violations | every built plant | at its build |
| G0d | ADR-0059 bands pooled per scale on process sheets; network statistics reported | dev plants (gate); sealed plants (report only, after the freeze, as EXP-0008 M4) | P0; B10 |
| G0e | ≥ 10 kept candidates per family, per scope, per plant | every sealed plant | B10, before any sampling (§19.6) |
| G0f | `git diff --name-only $(cat data/runs/exp0008/prereg/E9.commit) HEAD` over the system-side list is empty; cache-only replays of `S7-CYP-H100g21p1` (with H100g21p1 loaded) and `S7-AG-H100g21p1` from `exp0008/m6a` are byte-identical | — | P0 (diff and replays); F10 (diff) |
| G0g | `exp0007 check-ingest` (pair precision = recall = 1.0, network connectors included) on the A view; the B view is the relabel, so the byte test of §19.4 stands in for it | every plant | at its build |
| line view | `qa/exp0009/line_view_gate.py`: P = R = 1, 0 key collisions | every plant (A view) | at its build |
| G0h | each arm's first-turn prompts, rendered for the longest question of the plant's file, fit the pin's context wall; the harness's own run-start check stays | every plant, both arms | after its questions |
| G0j | `tests/v2tb` (the B scorer's self-tests) | — | P0 and F10 |
| G0k | the documents' `manual_valves_untagged` flags equal the plan's; the built total sheets equal the predicted total in `plan.json` exactly, and lie in the band | every plant | at its build |
| G0-B | checks 1–3 (`check_g0b` on the corpora plan); check 4 (database) at every B load | every B corpus | at its build; at its load |
| G0l | per X family and plant, refused for a non-unique descriptor ≤ 25 % | dev, validation and sealed plants | after the pool step |
| records | §19.11's record check on every finished run | every run | after each run |

- **The stops.**
  - A failed G0a, G0b, G0c, G0f, G0g, G0j, G0k, G0-B, line-view or records check stops the launcher. The stop is
    `[infrastructure]` for G0-B check 4; every other gate stops `[needs the user]`.
  - A failed G0l stops it and returns the case to the architect (ADR-0067).
  - G0e does not stop. Its drops are pre-registered (§19.6).
  - A failed G0d band on the dev plants stops (U4). On the sealed plants it is reported only.
- **Why G0k's "within 2" changes.** §17.16 measured 900 → 904 on seed 7. The draw now refuses beyond 5, and the build
  must reproduce the recorded total exactly. That is stricter than a tolerance, and it also proves that the
  allocation override leaves the sheet count alone.

### 19.6 Questions

**One pool step per plant**, in one process, so the corpus is generated once. It runs
`launcher questions-pool --plant <A id> --recipe sealed|dev`.
- **R pool.** The frozen `sealed_set.build_pool(artifacts, targets, seed)`.
  - Sealed plants use EXP-0008's sealed recipe: seed 31, 500 per bin, 100 unanswerable.
  - Dev and validation plants use EXP-0008's dev recipe: seed 1, 97 and 97.
  - The pool goes to `qpool/<id>/`, with its availability.
- **X candidates.**
  - `scope_x_candidates(plant, manifest, sheets, positions, corpus_id=<A id>, seed=…)`, with the same seed as R.
  - The families are the five on sealed plants, and the dev three on dev and validation plants. Held-out X is never
    built on those plants (§6).
  - The positions come from `positions_of(plan_plant(config).unit_plans)`. A test shows that they equal those of
    `generate_plant_v2(config).plan`, so the gold side needs no pyDEXPI.
  - Kept candidates, refusals and T15b's `FamilyReport` go to `qpool/<id>/scope_x/`.
- **POSITION keys.** For each POSITION candidate, the text-prior key fields (P3) are stored, so that later steps need
  no plant.

**The drop set**, fixed after **all** pools of a role exist and before any sampling:
- R's five pre-registered unavailable families;
- **G0e:** every family of R or X with fewer than 10 kept candidates on any sealed plant. It is dropped at both
  scales, and an event NOTE lists it. No stop: this rule was written before the seeds were drawn (§11).
- **G0l** is evaluated at the same moment.

**Samples.**
- **R, sealed plants.** `sample_sealed_set(pool − dropped families, 10, 5, 20261031, v2=True)`.
- **R, dev and validation plants.** `per_family` with n = 10 and seed 20261101, after the same drop.
- **Recipe test.**
  - With an empty drop set, the two-step path (pool, then sample) reproduces `exp0008/questions/H100g21p1` and
    `H100g21p2` byte for byte, from their stored `ingest.json`. That is T6b's check, about 40 s each.
  - A second test shows that dropping families before sampling leaves every other family's draw unchanged, on a
    forced-tagged dev plant. If the sampler shares one stream across families, the drop moves to after the sample,
    and the test documents why.
- **X.** `sample_family(kept, 10, sample_seed)` per family, with the same sample seeds as R.
  - There is no stratification by `named_by`, position code, "discriminating" or untagged gold (R11, R13.4).
  - The realized mixes are reported.

**Files.**
- **A2.** `questions/<A id>/questions.jsonl` holds R plus `for_a2(q)` of every X isolation question (no POSITION).
- **B.** `questions/<B id>/questions.jsonl` holds R relabelled plus all X, relabelled.
- **The relabel** changes only `corpus_id` and the question-id prefix.
- **`splits.json`** follows the same rule. The X families take the split of `scope_x.py`.
- **S3 test.** The two files are equal on every R question and every X isolation question once the corpus id is
  stripped and the answer type is set to TAG_SET. SB1 and SB2 pair rows by the stripped id.
- **`questions/<B id>/position_baselines.jsonl`.** One line per POSITION question: id, `named_by`, gold code,
  majority prediction, text-prior prediction.
- **`questions/<id>/scope_report.json`.** Kept, refused and sampled counts per family. For X it adds the untagged-gold
  flag, the discriminating flag, the empty-gold refusals (R8) and the `named_by` mix.

**Counts (derived, not measured; G0e confirms them at B10).**
- **Sealed.** EXP-0008's set has 280 questions over 23 families. Taking out the four R families in it (45 questions)
  leaves R = 235.
  - A2 answers 235 + 40 = **275** per plant.
  - B answers 235 + 50 = **285**.
- **Validation and tuning.** EXP-0008's dev set had 163 questions over 18 families. Three of those families drop.
  - R-dev is about 133.
  - A2 answers about 153 (with 2 X families).
  - B answers about 163 (with 3 X families).

### 19.7 Stages, in order

**P0 — free gates, $0.**
- Builds D100g22 (with its B files) and D1000g22.
- Gates: G0a, G0b, G0c, G0d (gate), G0f (diff and replays), G0g, the line view, G0j, G0k, G0-B (checks 1–3).
- R14f's checks on D100g22B: exactness 100 %, footprint ≤ 5 %.
- The prior refit: its sha256 must equal `plan.json`'s.
- The ledger test, and the records test on fake runs of both arms.
- **Refuses to start** if `PREREG_A.md` holds a `<<FILL` marker or is not committed. The readiness rules are
  EXP-0008's `readiness.py`, copied for EXP-0009.

**P1a — B tuning on D100g22, PAID.**
- **Setup.** D100g22's dev questions (§19.6, dev recipe), and G0l on its X dev families.
- **Round 1** runs first and only once:
  - the **A2 baseline**: load A, `CYP-A` and `AG` on the A2 dev file;
  - then B round 1: load B, `CYP-B` and `AG-B` on the B dev file.
- **Each round writes:**
  - `tune/round<k>/b_code.sha256` (every `qa/v2tb/` file and the `policy_b` dump);
  - the B cascade report, with per-family dev accuracy over R-dev ∪ X-dev;
  - B − A2 on R-dev.
- **After round 1** the launcher stops `[needs the main session]` with the report.
  - The main session either changes B files (round 2) and resumes with `--from P1a`, or ends tuning with
    `launcher finish-tuning`.
  - From round 2, a round whose B dev accuracy rises by less than 1 point ends tuning automatically.
  - Round 3 always ends it. A fourth round is refused.
  - The launcher refuses a round whose `b_code.sha256` equals an earlier round's.
- **The E10 candidate** is the round with the highest B dev accuracy, ties to the earlier round. The main session
  restores and commits those B files on the user's order.
- **Run ids:** `U9-A-CYP-D100g22`, `U9-A-AG-D100g22`, `U9-<k>-CYP-D100g22B`, `U9-<k>-AG-D100g22B`.
- **No replays in tuning,** as EXP-0008 M1.

**P1b — validation, PAID.**
- **Precondition.** A clean tree under the frozen paths, and the B files' hashes equal to the chosen round's.
- **Plants.** VAL100g22, then VAL1000g22. Each gets:
  - its build and gates;
  - dev-recipe questions;
  - A2 `CYP-A` then `AG`;
  - B `CYP-B` then `AG-B`.
- **The B runs are replayed cache-only.** These are the E10 replays "per B tier of the B validation runs" (§6), with
  the Cypher replay prefix allowed as ADR-0062 allows.
- **The VAL1000g22 pool step** runs under EXP-0008's `memory-probe`, so its peak memory is recorded. It is the first
  1,000-sheet v2.2 pool.
- **Gates:**
  - **G1** (A2): no R dev family below 50 % on both plants. A fail stops the launcher `[needs the user]`, as
    EXP-0008's U2.
  - **G1-B** (B): no dev family of R ∪ X below 50 % on both plants.
  - **G1-B2:** B − A2 on R, the mean of the per-plant paired differences, ≥ −0.05.
  - If G1-B or G1-B2 fails, B is **not run sealed** (ADR-0067). The launcher records it for part B and continues with
    A2 alone. It drops B's P1c runs and the B audit stratum.
  - Accuracies come from `cascade_report.py`. It runs the frozen offline evaluation with `cascade_v4_iso` (A2) and
    `policy_b()` (B) over the two tier runs, for every family the file holds, R and X. `qa.cascade tune-report` is
    not used, because it does not know the X families.
- **Run ids:** `V9-CYP-<id>`, `V9-AG-<id>`, `V9-CYP-<id>B`, `V9-AG-<id>B`.

**F10 — freeze E10 and part B, free (§19.8).**

**B10 — the sealed plants, free.**
- **Precondition.** `E10.sha256` exists.
- **Per plant**, 100-sheet plants first: build (§19.4), the plant gates, the pool step.
- **Then:** the drop set, G0l, the samples and files, G0h, the sealed bands (reported), and `D10.sha256`.
  - `D10.sha256` covers `E10.commit`, every `corpora/*/ingest.json`, `rules.json`, `operating_positions.json`,
    `corpus_b.json`, every `questions/*/questions.jsonl`, `splits.json`, `scope_report.json` and
    `position_baselines.jsonl`.
  - It is written once and never overwritten.

**P1c — sealed, PAID.**
- `require_frozen` checks `E10.sha256`, `PREREG.sha256` and `D10.sha256`.
- **Per plant**, in plan order (100 p1–p5, then 1,000 p1–p5), A2 then B (§12.4):
  1. load A; `S9-CYP-<id>` and its replay;
  2. load B; `S9-CYP-<id>B` and its replay;
  3. `S9-AG-<id>` and its replay; `S9-AG-<id>B` and its replay. The agent runs need no database.
- **Every sealed run is replayed cache-only, as in EXP-0008 M6a** (ADR-0068, decision 4).
- **Concurrency** 4, as EXP-0008. Nothing else runs on the machine meanwhile (K1, K3).
- **The B cap** is recomputed before the first B run from P1b's measured B $/q (§19.9).

**P1d — the scorer audit, PAID.**
- **The main sample.** EXP-0008's `qa.audit select` and `judge` over the A2 sealed runs, in the pre-registered order.
- **The B stratum** (`audit_b.py`).
  - **Size:** ⌈0.5 × the main sample's row count⌉ rows of the B sealed runs.
  - **Rows:** VALVE_SET and POSITION rows only, every wrong row first, then a random right sample (fixed seed),
    deduplicated by question and parsed answer.
  - It is judged with the same judge pin and prompt.
  - The excerpts are cut with `scripts/audit_export_subgraphs.py` on the B corpus.
  - The disagreement sheet prints, for each B row, the B scorer's resolution: each answered item and the nodes it
    resolved to.
- **The audit ledger** is §19.9's. The launcher stops after the judge. Classifying disagreements is the main session's
  work under the audit rule, as in EXP-0008.

**END — free.**
- Cascade reports per plant and arm.
- §19.11's record check over every run.
- The ledger summary.
- The T17 analysis entry point, if present (§19.11). A missing T17 is noted, not a stop.
- The demo database restore (§19.4). As in EXP-0008 M10b, a failed report is named, the restore still runs, and only
  then does the stage stop.

### 19.8 Freeze E10 and part B (stage F10)

1. **The tree.**
   - `git status --porcelain` over the frozen paths is empty.
   - The frozen paths are `src :!src/plantgraph/demo`, `scripts/audit_export_subgraphs.py`, the EXP-0009 scripts,
     `stages/` and `inputs/`, `pyproject.toml` and `uv.lock`.
   - The changes since part A's named commit lie only in §19.3's allowed list. `exp0009/freeze.py` reuses
     `exp0008.freeze.check_head`'s rule with that list.
2. **G0f diff** is empty again, and G0j is green.
3. **The B files** equal the chosen tuning round's hashes, and the P1b B runs' `b_code.sha256`.
4. **Writes `E10.commit` and `E10.sha256`.** The second file lists every tracked frozen file. This is "all of `src`
   again", which also freezes the v2.2 gold side (S1).
5. **Writes `B_FILES.sha256`.** It lists every file under `src/plantgraph/qa/v2tb/` plus one line
   `<sha256> *policy:cascade_v4_iso_b` for `policy_b().model_dump_json()` (R15).
6. **Writes `PREREG_B.md`.**
   - G1, G1-B and G1-B2, with the numbers per plant and family.
   - The B-sealed decision.
   - The tuning log summary: rounds, the change made in each, the B dev accuracy, and B − A2 on R-dev.
   - The replay verdicts.
   - The measured $/q per arm, tier and scale, with the recomputed sealed caps.
   - Peak memory of the VAL1000 pool.
   - The E10 hashes.
7. **Writes `PREREG.sha256`** over part A, part B, `seeds.json`, `plan.json`, `position_prior.json`, the E10 files
   and the judge prompt.

The launcher never commits. The user commits part B and the hash files on their order, as after EXP-0008 M3.

### 19.9 Money

**Basis, measured.** I computed it today with `exp0008.ledger.paid_usd_of_calls` over EXP-0008's call files
(non-cached calls only). Each EXP-0008 run answered every question on both tiers.

| Runs | Paid | Per question (both tiers) |
|---|---|---|
| V2T-A2 validation, `V8-CYP-A-*` + `V8-AG-*`, 2 plants × 163 q | $0.694 | $0.00213 |
| V2T-A2 sealed at 100 sheets, `S7-*-H100g21p1…p5`, 5 × 280 q | $3.281 | $0.00234 |
| V2T-A2 sealed at 1,000 sheets, `S7-*-H1000g21p1…p5`, 5 × 280 q | $3.410 | $0.00244 |
| per tier, sealed (cost key) | CYP $1.058 / AG $2.223 at 100; CYP $1.015 / AG $2.395 at 1,000 | `cyp-100` 0.000756, `ag-100` 0.001588, `cyp-1000` 0.000725, `ag-1000` 0.001711 |
| EXP-0007 V2T tuning, three rounds (`EXP-0007-V2T-validation.md`) | ≈ $1.30 | — |
| EXP-0008 scorer audit, main sample | $3.61 | — |

**Estimate for P1** (A2 at its measured $/q; B at A2's × 1.10, an **assumed** overhead for its two extra paragraphs
and brackets, which P1a measures):

| Step | Questions | Estimate | Step ceiling (1.5×) |
|---|---|---|---|
| P1a A2 dev baseline, D100g22 | ≈ 153 | $0.33 | |
| P1a B, at most 3 rounds | ≈ 3 × 163 | $1.15 | |
| **P1a** | | **$1.48** | **$2.22** |
| P1b A2, validation pair | ≈ 2 × 153 | $0.65 | |
| P1b B, validation pair | ≈ 2 × 163 | $0.76 | |
| **P1b** | | **$1.41** | **$2.12** |
| P1c A2, 5 + 5 plants | 275 each | $6.57 | |
| P1c B, 5 + 5 plants | 285 each | $7.49 | |
| **P1c** | | **$14.06** | **$21.09**, recomputed after P1b |
| **P1d** audit, main sample + B stratum (EXP-0008 main × 1.5) | | **$5.42** | **$8.13** (audit ledger) |
| **P1** | | **$22.37** | runs ledger **$26.87** + audit ledger **$8.13** = **$35.00 hard** |

**Rules (`qa/exp0009/caps.py`, `ledger.py`).**
- **Program cap: $35.00 hard**, runs and audit together.
  - Runs ledger: $26.87, which is $35 less the audit's $8.13.
  - Audit cap: min($8.13, $35 − runs spent), so money the runs leave unused stays usable by the audit.
  - The step ceilings above sum to $25.43, inside the runs ledger.
- **A run's cap, without a dry run** (ADR-0068, decision 1):
  - The cap is n questions in the run's file × the tier's cost key × 1.5. It is never below 5 questions' cost
    (EXP-0008's `RESERVED_QUESTIONS`).
  - Then the cap is cut to the step ceiling left and the runs ledger left. A resumed run adds what it already spent
    (`resumed_run_cap_usd`'s rule).
  - B's cost keys are A2's × 1.10 until P1a has run. P1c's B and A2 keys are replaced by the per-tier $/q measured in
    P1b at each scale (written in part B).
- **The balance** must cover each cap before the run starts, as `exp0008.balance` checks. Today it is $37.11.
- **The ledger glob fix (§12.3 finding).** `exp0009.ledger.runs_spent_usd(root)` counts `*calls.jsonl` under `root`
  but skips every path with a `reports` or `audit` component.
  - Test: one paid `calls.jsonl` plus its byte copy under `reports/x/` sums to the single file's spend.
  - EXP-0008's own ledger is left as it is, so its record stays reproducible.
- **The estimate is printed before each paid stage.** One event NOTE gives:
  - the stage's questions per run, cost keys, estimate and ceiling;
  - the runs ledger spent and left;
  - the audit ledger;
  - the balance.

  Before P1c the NOTE also gives the recomputed caps from P1b.
- **Money stops** (cap, ledger, balance) are resolved by the main session without asking (user rule, 2026-11-15). Gate
  stops are not.

**Free and paid at a glance.**

| Free ($0) | Paid |
|---|---|
| the draw, P0, F10, B10, END; every replay; every gate; every build, pool and Neo4j load | P1a, P1b, P1c (model calls of both arms); P1d (judge calls) |

### 19.10 Machine time

| Stage | Basis (measured unless marked) | Estimate |
|---|---|---|
| draw | size search 27.1 s at 1,000 sheets, a 100-sheet plan 2.3 s (today); prior fit not measured | minutes |
| P0 | v2.2 1,000-sheet generation 8–12 min (T-task measurements); EXP-0008 replays at 100 sheets 12.2 min (Cypher) and 0.8 min (agent) (M6a log); full test suite not measured | ≈ 1–1.5 h plus the suite |
| P1a | EXP-0008 run time per question at 100 sheets: Cypher 2.9 s, agent 4.35 s (`S7-*-H100g21p2`, M6a log) | ≈ 1.3 h of runs; the tuning work between rounds is not machine time |
| P1b | EXP-0008 M1 3 h 37 min (two plants, two arms, 163 q); plus the positions step 7.8 min at 1,000 (T14c), the B replays and the slower v2.2 generation (estimated) | ≈ 4.5–6 h |
| F10 | EXP-0008 M3 18 s | minutes |
| B10 | v2.1 1,000-sheet pool 6,657–8,585 s (T6b; review-fixes §6); v2.2 generation 8–12 min; positions 7.8 min; X candidates at 1,000 not measured (generation, graph and index 840.5 s, §10.8) | ≈ 12–15 h |
| P1c | EXP-0008 M6a 17.7 h for **one** arm on ten plants, dry runs, loads and replays included (log, 06:49 → 00:30); × 2 arms; less the dry runs (≈ 12 min each at 1,000, ≈ 4 h, estimated); plus the slower v2.2 generation (+1.3 to +5.3 min on each of about 50 corpus rebuilds at 1,000, ≈ 1–4.5 h, estimated) | ≈ 32–36 h |
| P1d | EXP-0008 M10a 1 h 05 min; × 1.5 for the B stratum (estimated) | ≈ 1.6 h |
| END | EXP-0008 M10b 5 h (more reports than here); demo load: one v2.1 generation 404.8–421.6 s + 27.1 s | ≈ 1–2 h |
| **P1** | | **≈ 54–64 h** |

**Why this is above ADR-0067's "about 46 h".** §12.3 scaled only the runs. It did not count the replays, the dry runs
or the corpus rebuild at the start of each run. EXP-0008's measured M6a, 17.7 h for one arm, includes all three.

### 19.11 Records, and the analysis handoff

- **The four record files.** Every run of both arms writes `calls.jsonl`, `answers.jsonl`, `timings.jsonl` and
  `environment.jsonl` in EXP-0008's format (§18.8).
- **`records.py: check_run_records(run_dir)`**, a gate after each run, checks three things:
  - every scored answer has at least one matching call record, by question id and strategy;
  - every call record has `response.prompt_tokens`, `response.completion_tokens`, `response.cost_usd`,
    `response.latency_s` and `response.provider` set, the field names of EXP-0008's `calls.jsonl`. A cached reply
    keeps its recorded values;
  - the timings and environment files exist and are non-empty.
- **`records.py: rescore(run_dir, questions, corpus)`** rescores offline, with no model call.
  - It re-scores every row from `answers.jsonl` and the question file: the frozen scorer for A2, `score_answer_b`
    with a `PlantIndex` for B.
  - Its `correct` must equal the stored one on 100 % of rows.
  - For set answers (TAG_SET, VALVE_SET, paths) it also gives precision, recall and F1 over node sets.
- **Tests on fake-sender runs of both arms:**
  - a full record passes the check;
  - a run with one call record deleted, or one `cost_usd` blanked, fails it;
  - `rescore` reproduces `correct` on every row.
- **T17, the sealed analysis, is outside T13.** It covers Q4, Q4-B and its sensitivity row, SB1, SB2, K1–K3, Q5, the
  POSITION rows beside both baselines, the `named_by` mix, the sub-scopes and the data effect against EXP-0008.
  - It reads only result files.
  - It must be committed **before F10**, so that E10 hashes it. It can be built during the tuning pause.
  - END calls it when it is present.

### 19.12 T13 acceptance criteria

1. **Draw.** On a temporary `data/runs` copy, the draw:
   - reproduces itself for the same N;
   - refuses an existing file;
   - refuses a size outside ±5;
   - allocates exactly 4 of 5 at 100 sheets and `round_half_up(4/5 × n)` at 1,000 sheets (unit tests for n = 8–12);
   - prints the PREREG A tables.
2. **Ids.** Every id of §19.1 comes from `plan.py`. The id uses the nominal scale. `require_drawn_test_seed` reads the
   EXP-0009 seeds file. Tests cover all three.
3. **Build and relabel.**
   - On a small dev-seed v2.2 plant with no tagging override, the A build gives the same `ingest.json` content
     (timings aside) as the frozen CLI. The CLI call is
     `ingest synthetic --headline-v2 --generator v2.2 --n-units … --seed … --corpus-id … --check --no-neo4j`.
   - The B file is byte-identical once the id is replaced back.
   - `load_corpus_artifacts(<id>B)` gives the A counts.
   - `corpus_b.json` holds the positions sha256.
4. **Gates.** Each gate of §19.5 passes on a good input and fails on a spoiled one, for example:
   - a flipped allocation flag;
   - a sheet total one off;
   - a deleted position;
   - a rule violation;
   - an X family with 26 % descriptor refusals.

   G0f's diff runs on the real repository.
5. **Questions.**
   - The EXP-0008 byte reproduction (H100g21p1, H100g21p2) passes.
   - The drop-before-sample test passes.
   - The S3 test passes.
   - The A2 file holds no POSITION question and no VALVE_SET type.
   - `position_baselines.jsonl` agrees with `position_baselines.py` on seed 1.
6. **Frozen code meets the X families.** On fake senders, these all run without an exception on a file that holds X
   questions:
   - the frozen harness (A2 arm, X questions through `for_a2`);
   - the B runner;
   - `exp0007 health`;
   - `replay-compare`;
   - `cascade_report.py`.

   If a frozen module raises on an X family, T13 stops and reports. The case returns to the architect, because frozen
   code cannot change.
7. **Money.**
   - Caps without dry runs follow §19.9: unit tests for the minimum, the ceiling and ledger cut, and the resume.
   - The ledger glob test passes.
   - The audit cap is the lesser of $8.13 and what is left of $35.
   - The estimate NOTE is printed before each paid stage in the smoke.
8. **Freeze.** On stub git facts, F10:
   - refuses a dirty tree;
   - refuses a change outside §19.3's list;
   - refuses B files that differ from the chosen round;
   - writes `E10.sha256`, `B_FILES.sha256` (with the policy line), `PREREG_B.md` and `PREREG.sha256`, and never
     overwrites them.
9. **Records.** §19.11's tests pass.
10. **Smoke.** `run_all.sh --smoke` runs draw → P0 → P1a (one round, then `finish-tuning`) → P1b → F10 → B10 → P1c →
    P1d → END.
    - It uses tiny plants, the fake transport for both arms, and no Neo4j: the Cypher tiers are stood in by the
      agent, and the loads write files only, as in EXP-0008.
    - It ends with `SMOKE_PASSED`.
    - `--force g1|g1b|g1b2|g0l|cap|dirty-tree|wrong-head|b-files` each stops or branches as specified and resumes.
      `g1b` and `g1b2` take the "B not sealed" branch without a stop.
11. **Task rules.** `pytest`, `ruff` and `mypy --strict` are green, and the goldens are unchanged. G0f is `[]`. No
    EXP-0009 plant is built under `data/runs/exp0009/`, and no paid call is made. The report gives the smoke's machine
    time and one commit proposal.

### 19.13 After T13 (main session)

1. Run the draw.
2. Fill `PREREG_A.md`.
3. Write the EXP-0009 experiment note with an empty tuning log.
4. On the user's order, commit part A with `seeds.json`, `plan.json` and `position_prior.json`.
5. Run readiness.
6. Start the launcher on the user's word. P0 is free; P1a is the first paid step.

## 20. The user's model-comparison arm (2026-11-24): task T13b

**Decision.** The user asked whether EXP-0009 compares models. As specified, it does not: both arms run GPT-6 Luna, with low effort on the Cypher tier and high effort on the agent tier. The model choice rests on October's dev bake-off (`_results.md` BAKEOFF-1/2, CASCADE-V3).

The user was offered three options:
- **A:** cite the bake-off only;
- **B:** a small GLM arm on sealed plants;
- **C:** a full GLM arm, which would need a top-up.

The user chose **B**.

**The A2-GLM arm.**
- **Code.** The frozen V2T-A2 code, policy `cascade_v4_iso`, unchanged.
- **Pins.** A copy of the A2 pins with only the model swapped. The copy is new and lives outside the system-side paths, so G0f stays empty.
  - The model is `z-ai/glm-5.3-flash`.
  - The provider is pinned to the BAKEOFF host (fireworks). BAKEOFF-1 showed that unpinned routing spread one config over 15 hosts.
  - The effort per tier is the same as A2's: Cypher low, agent high.
  - The token caps are the same as A2's.
- **Plants.** One sealed 100-sheet plant and one sealed 1,000-sheet plant: the first of each scale in `plan.json` order. This rule is fixed in PREREG A before any plant exists.
- **Questions.** Scope R only, the same 235 questions per plant that A2 answers. That is 470 questions in all.
- **Reporting.** Descriptive only: paired GLM − Luna accuracy per plant, with the bootstrap interval, and cost per question, latency and outcome mix beside A2's.
  - No gate, no claim, and no role in Q4. A single plant per scale cannot carry a scale claim.
  - The same records are kept (calls, answers, timings, environment), so precision, recall and F1 can be recomputed offline.
- **Cost.**
  - **Estimate:** about $1.5–2. This is derived from EXP-0008's measured sealed A2 cost of $0.00234–0.00244 per question, times GLM's dev cost ratio of 1.2–1.9 (CASCADE-V2/V3, BAKEOFF-2).
  - **Hard cap:** $2.50.
  - **Timing:** the arm runs after P1c, when P1's actual spend is known. If the OpenRouter balance cannot cover the cap at that point, the main session asks the user for a top-up before starting.
- **Freeze.** The GLM pins file is hashed into E10 with the other run inputs.
- **Who does it.** T13b, a small coder task after T13. It adds the pins file, a stage `P1g` in the launcher with its own cap, and a test that the GLM arm reuses the A2 question files byte for byte.
