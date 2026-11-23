---
adr: 0066
title: Build generator v2.2 beside a pinned v2.1, with a cited rule registry and a plant-level correctness layer verified on every built plant, and measure it with the frozen V2T-A2 as EXP-0009 (stage P1 inside $16.50)
status: proposed
date: 2026-11-22
supersedes: none. Clarifies ADR-0021 (hidden ordinal design state is not equipment data). Amends ADR-0059 (composition bands judged on process sheets; network and interarea sheets reported apart) and the S15 invariant of generator-v2-realism.md §12.2 (network sheets are not prefix-stable). ADR-0053, ADR-0060 and ADR-0065 protocols carry over.
design: 40-design/generator-v2-2-handbook-rules.md
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
  - the frequencies are declared, not measured.
- **The constraints:**
  - v2.1 is the measured headline (EXP-0008) and the demo's data, so it must stay rebuildable byte for byte;
  - V2T-A2 is frozen (freeze E9);
  - the user has about $17 of OpenRouter credit now.

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

**4. Sampling units**
- **U-A. Everything per plant.** This is how a real owner standard works, but five plants per scale would then give
  wildly different plants, and the pooled claims would measure the coin.
- **U-B. Identification conventions per train, engineering arrangements per item, coupled choices from one hidden
  cause.** This follows the existing `TrainConventions` precedent.
- **U-C. Everything per item.** This mixes conventions within one contractor's area, which no source describes.

**5. The retrieval system in EXP-0009**
- **S-A. Frozen V2T-A2, a pure data replication.** Positions stay out of the store, gold stays topological, and
  candidates whose answer holds an untagged valve are refused on the gold side, with the refused share reported.
- **S-B. A documented revision V2T-B.** Positions become visible, isolation becomes position-aware, and untagged
  valves are named by a descriptor. It needs a new freeze, a re-validation, and a paired V2T-A2 arm to tell data
  from system.
- **S-C. Both arms** on the same v2.2 plants.

**6. Money**
- **M-A. Everything at once:** P1 + P2, estimate $19.29 without F1. It does not fit $17.
- **M-B. Stage P1 now** (validation pair, V2T-A2 on 5 + 5 sealed plants, scorer audit): estimate $11.46, ledger hard
  cap $16.50. Stage P2 (ladder, P4 identity, optional F1) after a top-up, under a $13.50 hard cap.

## Decision

1. **V-B.**
   - T0 records the v2.1 goldens before any change.
   - Corpus ids carry `g22`.
   - Fresh test seeds are drawn, and the EXP-0008 seeds are retired.
2. **R-B.**
   - The registry holds 54 encoded rules (35 local, 19 plant-level) and 15 deferred groups, each with its reason
     (55/36/14 at proposal; TOG73 deferred in T3).
   - Each rule has an id naming the book and page, a paraphrase, its sources marked page-checked, its conflict and
     the choice made, declared parameters, exception codes and a check.
3. **P-C.**
   - The hidden state is ordinal or banded, has no values and no units, and is never shown or asked. It is therefore
     not equipment data under ADR-0021; this ADR clarifies ADR-0021 and does not supersede it.
   - What stays unguaranteed is stated in the thesis: chemistry, mass and energy balance, sizing, set points, real
     frequencies, and deferred or unread rules.
4. **U-B,** with declared neutral weights:
   - manual valves untagged in a train at 0.5;
   - pressure-control stations without a bypass at 0.5;
   - spare naming unchanged at 3 : 2;
   - pump power bands 1 : 1 : 1 : 1;
   - reflux class 1 : 1.

   The deferred alternatives are: functional-only gauges, parallel loop numbering, API "S" letters, a solenoid on
   the control valve, PCV kickback and FSL min-flow, and the 3-way exchanger valve.
5. **S-A for EXP-0009.** S-B is considered only if EXP-0009's rows trace a large drop to positions or untagged items.
6. **M-B.**
   - **Free gates first:** goldens, rule suite, build verification, composition on process sheets, availability
     ≥ 10 per family per plant, frozen-system replays, resolution 1.0, prompt fit.
   - **Primary claim:** Q4 on v2.2.
   - **Carried over:** K1–K3 and Q5.
   - **Reported descriptively:** v2.2 − v2.1 per scale.
7. **Network and interarea sheets** count toward the sheet targets. Each process sheet sends one network connector
   per service, through a local sub-header. A network sheet holds at most 16 tie-ins.

## Rationale

- **Thesis claim.** The scale claim is only as strong as the plants it is measured on. A cited, tested rule set
  answers "toy topology" better than more realism by assertion. Measuring with the frozen system (S-A) makes any
  change against EXP-0008 attributable to the data, which is the question a replication asks.
- **Honesty about the gap.** R-B makes "checked on every plant" literally true. P-C closes the global errors that
  local rules cannot see, as far as that is possible without data. Listing the deferred rules keeps the claim from
  outrunning the code.
- **Boring where possible:**
  - no new node class;
  - no resolver, schema text or prompt change;
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

  The launcher's "runs $26.56" double-counts $5.17 of call files copied under `reports/`; the de-duplicated figure
  is $21.40.

## Consequences

**Makes easy:**
- a thesis appendix table printed from the registry;
- a reviewer can trace any symbol on a v2.2 sheet to a page;
- free v2.1 → v2.2 diffs on the same seeds;
- Q4 on v2.2 inside the current credit.

**Makes hard:**
- isolation questions come only from tagged trains;
- positions are drawn but unused by the system;
- network sheets lengthen paths, so k and u distributions change, and v2.1 and v2.2 numbers are compared unpaired;
- composition bands may move (stubs, instruments per sheet), and a failed band stops the run under the ADR-0065 U4
  rule.

**Code:** 14 coder tasks (T0–T13). Seven of them (T0–T4, T9, T11) and the plan/DEXPI part of T5 do not depend on an
open decision.

**Revisit if:**
- a v2.1 golden cannot be kept;
- verification makes a 1,000-sheet build impractical;
- a plant check fails on v2.1 seeds in a way that needs a design change;
- G0d or G0e fails;
- the validation pair's $/q puts the sealed cap above the ledger;
- the user chooses S-B or S-C.
