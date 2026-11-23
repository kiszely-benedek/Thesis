---
adr: 0066
title: Build generator v2.2 beside a pinned v2.1, with a cited rule registry and a plant-level correctness layer verified on every built plant, and measure it in EXP-0009 with the frozen V2T-A2 and the revision V2T-B on the same plants (stage P1 under $37.50)
status: proposed
date: 2026-11-22 (amended 2026-11-23 with the user's decisions D1–D8)
supersedes: none. Clarifies ADR-0021 (hidden ordinal design state is not equipment data). Amends ADR-0059 (composition bands judged on process sheets; network and interarea sheets reported apart) and the S15 invariant of generator-v2-realism.md §12.2 (network sheets and boundary groups are not prefix-stable). ADR-0053, ADR-0060 and ADR-0065 protocols carry over. The B arm is decided in ADR-0067.
design: 40-design/generator-v2-2-handbook-rules.md (decisions in §15, worked out in §18); 40-design/v2t-b-system-revision.md
---

# ADR-0066 — Generator v2.2: handbook rules, checked on every plant

## Context

- **Four comparisons** of handbooks against generator v2.1 (Toghraei 2019, API RP 14C 2001, Liptak IEH Vol. 1
  2003, Liptak IEH Process Control 1995; `10-literature/`) found verified rule violations in the code:
  - a check valve on reciprocating pumps;
  - min-flow lines on PD pumps;
  - the min-flow take-off between the check and the block valve;
  - throttling FVs on PD pump discharges;
  - anti-surge on PD compressors;
  - line numbers on short branches.

  They also found missing content: valve positions, untagged manual valves, network and interarea sheets.
- **The user (2026-11-22)** chose scope (b), with these terms:
  - fix the violations and add that content;
  - every rule gets an id, a code comment and a test on every generated plant;
  - data we do not model becomes declared parameters;
  - the generator samples among source alternatives;
  - the later source wins a conflict (recorded case: no external check valve on reciprocating pumps, Toghraei 2019
    over API 14C 2001);
  - the thesis claim is "derived from handbooks, cited per rule, checked by tests on every generated plant".
- **The user also asked whether correct rules guarantee a correct plant.** They do not:
  - local rules can compose into global errors, such as two CVs in series across a pattern boundary, a pressure rise
    without a mover, or an inventory controlled twice;
  - unencoded rules are never violated;
  - most frequencies are declared, not measured.
- **The user decided D1–D8 on 2026-11-23** (design §15):
  - D1: both systems on the same plants;
  - D2: weights "whichever gives the more accurate result";
  - D3: yes; D4: as proposed;
  - D5: P1 now, with the user's own proposals (3 + 3 plants, sheet bands) to be worked through;
  - D6: re-triage the deferred list;
  - D7: an expert review; D8: A.
- **The constraints:**
  - v2.1 is the measured headline (EXP-0008) and the demo's data, so it must stay rebuildable byte for byte;
  - V2T-A2 is frozen (freeze E9);
  - the user will top up the OpenRouter credit, so cost must not block the agreed arms.

## Options considered

**1. Versioning**
- **V-A. Fork** `benchmark/v2/` into a frozen `benchmark/v2_1/`. Safe, but it doubles about 9,100 lines of code
  that a professor reads.
- **V-B. Gate in place.** A new `GeneratorConfigV22` type, every new behaviour behind `handbook` knobs, new draws
  only from new named streams, no v2.1 draw removed or reordered, and v2.1 goldens recorded before the first change.
- **V-C. Checkout-only reproducibility,** as done for the superseded `v2`. Cheapest, but the demo and every EXP-0008
  corpus would then need a checkout to rebuild.

**2. Where rules are checked**
- **R-A. In pytest on seeds 1–5 only,** as S1–S24 are today. "Every generated plant" would then be false for the
  sealed plants.
- **R-B. A registry plus `verify_plant` at build time.** A violation refuses the build, every corpus carries
  `rules.json`, and the pytest suite adds a positive, a mutation and a non-vacuity test per rule.

**3. Closing the gap between local rules and a correct plant**
- **P-A. Local rules only,** with the gap stated as a limitation.
- **P-B. A plant-level layer without hidden state:** stream closure, control structure, network closure.
- **P-C. P-B plus a hidden ordinal design state:**
  - pressure levels per segment;
  - pump power bands;
  - column reflux class;
  - fluid class per service;
  - exception codes.

  The state drives spec breaks, check valves, PSD need and derived API 14C exceptions, and is checked for
  consistency. It is never written to DEXPI, the store, a drawing, a prompt or gold.

**4. Sampling units and weights**
- **U-A. Everything per plant.** Five plants per scale would then give wildly different plants, and the pooled claims
  would measure the coin.
- **U-B. Identification conventions per train, engineering arrangements per item, coupled choices from one hidden
  cause,** with neutral declared weights. This follows the existing `TrainConventions` precedent.
- **U-C. Everything per item.** This mixes conventions within one contractor's area, which no source describes.
- **U-D. Company conventions per document** (a run of consecutive trains of about 100 sheets), arrangements per item,
  coupled choices from one hidden cause, and weights counted from real drawing sets where they exist. Added
  2026-11-23 after the evidence check of design §18.2:
  - 9 of 12 real drawing sets leave manual valves untagged;
  - every multi-sheet set keeps one convention throughout;
  - a v2.1 train is only about 9 sheets.

**5. The retrieval system in EXP-0009**
- **S-A. Frozen V2T-A2, a pure data replication.** Positions stay out of the store, gold stays topological, and
  candidates whose answer holds an untagged valve are refused on the gold side, with the refused share reported.
- **S-B. A documented revision V2T-B** only. Positions become visible, isolation becomes position-aware, and untagged
  valves are named by a descriptor. Without a paired A2 arm it cannot tell data from system.
- **S-C. Both arms** on the same v2.2 plants (ADR-0067 designs V2T-B).

**6. Money and shape of stage P1**
- **M-A. Everything at once** (P1 + P2).
- **M-B. P1 now, P2 later.** P1 is B's tuning, one validation pair per arm, the sealed plants of both arms, and the
  scorer audit. The shapes put to the user were 3 + 3, 4 + 4 or 5 + 5 plants per scale (design §18.3):

  | Shape | P1 estimate | Q4 interval width (from EXP-0008's counts) |
  |---|---|---|
  | 3 + 3 | $18.74 | 0.073 (median over all subsets) |
  | 4 + 4 | $21.85 | 0.067 |
  | 5 + 5 | $24.95 | 0.059 |

- **Sizes:** fixed targets of 100 and 1,000 sheets, or targets drawn in bands of 90–110 and 900–1,100 (the user's
  proposal).

## Decision

1. **V-B.**
   - T0 records the v2.1 goldens before any change.
   - Corpus ids carry `g22`; the B view of a plant appends `B`.
   - Fresh test seeds are drawn, and the EXP-0008 seeds are retired.
2. **R-B.**
   - The registry holds 54 encoded rules (35 local, 19 plant-level) and 15 deferred entries, each with its reason
     (55/36/14 at proposal; TOG73 deferred in T3).
   - Each rule has an id naming the book and page, a paraphrase, its sources marked page-checked, its conflict and
     the choice made, declared parameters, exception codes and a check.
   - **Deferred-list triage (D6):** 1 entry is done now (the API 14C SAC devices, in T10), 2 are done only if the
     expert review flags them before the freeze (blanketing/VRU, fired-heater detail), and 12 are out of scope, each
     with its reason (design §4.9, §18.4).
3. **P-C.**
   - The hidden state is ordinal or banded, has no values and no units, and is never shown or asked. It is therefore
     not equipment data under ADR-0021; this ADR clarifies ADR-0021 and does not supersede it. **The user confirmed
     this on 2026-11-23 (D3).**
   - What stays unguaranteed is stated in the thesis: chemistry, mass and energy balance, sizing, set points, real
     frequencies, and deferred or unread rules.
4. **U-D** (replaces U-B; D2):
   - manual valves untagged per document at **0.75** (measured: 9 of 12 sets);
   - spare naming 3 : 2 and on-off letter 1 : 1, unchanged, now per document;
   - pressure-control stations without a bypass at 0.5 per document;
   - pump nozzle reducers at **0.75** per pump set (measured: 3 of 4 sets);
   - pump power bands 1 : 1 : 1 : 1 and reflux class 1 : 1 (no evidence; declared).

   The sealed plants are **stratified**: 0.8 of the documents untagged at each scale, fixed in PREREG A.
   - **Exchanger isolation (D8 = A):** one fixed policy, no process-side isolation, utility-side blocks allowed.
5. **S-C** (D1), with V2T-B as designed in ADR-0067.
   - Scope R is the EXP-0008 recipe and is answered by both arms.
   - Scope X holds the position-aware and untagged-answer isolation families: both arms answer its isolation
     families, B alone answers POSITION_OF_VALVE.
   - R's two isolation families are pre-registered unavailable: under U-D an untagged 100-sheet plant has no
     candidate for them.
6. **M-B, 5 + 5 plants per scale, sizes drawn in the bands** (D5):
   - **Free gates first:** goldens, rule suite, build verification with an empty owed list, composition on process
     sheets, availability, frozen-system replays, resolution 1.0 on both views, prompt fit, the B scorer self-tests,
     allocation and size, descriptor uniqueness, review triage.
   - **Paid gates:** G1 for both arms; G1-B2 (B − A2 on scope R ≥ −0.05 on the validation pair) before B runs sealed.
   - **Primary claim:** Q4 on V2T-A2, scope R. Q4-B, SB1 and SB2 are registered for the B arm (ADR-0067).
   - **Carried over:** K1–K3 and Q5.
   - **Reported descriptively:** V2T-A2 on v2.2 − V2T-A2 on v2.1, per scale.
   - **P1:** estimate **$24.95**, ledger hard cap **$37.50**. **P2** (ladder, identity, optional F1; V2T-A2 only):
     $7.83 without F1, hard cap $13.50.
7. **Network and interarea sheets** (D4) count toward the sheet targets. Each process sheet sends one network
   connector per service, through a local sub-header. A network sheet holds at most 16 tie-ins.
8. **External checks:** an expert review of 12 dev-plant sheets against a 25-item checklist keyed to rule ids (D7;
   design §18.5), triaged before the EXP-0009 freeze.

## Rationale

- **Thesis claim.** The scale claim is only as strong as the plants it is measured on. A cited, tested rule set
  answers "toy topology" better than more realism by assertion.
  - Measuring with the frozen system makes any change against EXP-0008 attributable to the data.
  - The paired B arm tests Q4 a second time, by a system that can read the new content, and measures that content's
    value on the same questions.
- **Per document rather than per train.** It is what the real sets show. It also puts the variety of conventions on
  the scale axis: one contractor's style at 100 sheets, about ten at 1,000 sheets. That is a property of plant scale
  the claim is about.
- **Five plants per scale.**
  - 3 + 3 widens Q4's interval by about a quarter.
  - Q4's pass rule is easier to meet with a wider interval.
  - v2.2 adds a between-plant factor: a 100-sheet plant is wholly tagged or untagged.
  - Only five (or four) plants can hold the same tagging mix at both scales.

  The user said cost must not block.
- **Sheet bands.** They cost no precision, because EXP-0008's slope is about −0.005 accuracy per decade and the cost
  elasticity is 0.044. They remove the artefact of exactly 100 pages.
- **Honesty about the gap.**
  - R-B makes "checked on every plant" literally true.
  - P-C closes the global errors that local rules cannot see, as far as that is possible without data.
  - Listing the deferred rules keeps the claim from outrunning the code.
  - Only two weights are measured, on a 12-set convenience sample, and the thesis says so.
- **Boring where possible:**
  - no new node class;
  - no change to the frozen system;
  - pairing of network connectors as today;
  - the EXP-0008 launcher reused.

  The novelty budget stays with retrieval at scale and identity.
- **Money follows measurement.** Every estimate comes from EXP-0008's de-duplicated, measured per-arm spend:
  - validation $1.16;
  - V2T-A2 sealed $6.69;
  - audit main $3.61;
  - ladder $3.02;
  - P4 $4.48;
  - D4 decisions $0.33;
  - F1 $4.44.

  EXP-0007's V2T tuning cost about $1.30. Each estimate is scaled by the questions per plant (A2 320, B 330). The
  launcher's "runs $26.56" double-counts $5.17 of call files copied under `reports/`; the de-duplicated figure is
  $21.40.

## Consequences

**Makes easy:**
- a thesis appendix table printed from the registry;
- a reviewer can trace any symbol on a v2.2 sheet to a page;
- free v2.1 → v2.2 diffs on the same seeds;
- data effect and system effect reported separately.

**Makes hard:**
- R's isolation families are unavailable, so the isolation content is measured only in scope X;
- 100-sheet plants are wholly tagged or untagged, which needs a stratified allocation;
- network sheets lengthen paths, so k and u distributions change, and v2.1 and v2.2 numbers are compared unpaired;
- composition bands may move (stubs, instruments per sheet), and a failed band stops the run under the ADR-0065 U4
  rule;
- P1 needs about 46 h of machine time.

**Code:**
- Done: T0–T4, T9, T9b, T9c, T11, T7a and T5's plan and DEXPI part.
- Remaining, in order: T8 → T7 → T6 → T10 → T12a → T14 → T15 → T12b → T16 → T13, with the researcher's SAC
  transcription (T10a) in parallel.

**Revisit if:**
- a v2.1 golden cannot be kept;
- G0d, G0e, G0l or G1-B2 fails;
- the validation pair's $/q puts a sealed step above the ledger;
- the expert review finds a structural error that a rule cannot fix before the freeze.
