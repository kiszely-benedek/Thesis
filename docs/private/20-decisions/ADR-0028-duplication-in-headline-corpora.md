---
adr: 0028
title: Draw some equipment on several sheets in the headline corpora (duplication 0.25, exact tags), and count identity crossings in k
status: accepted
date: 2026-10-01
supersedes: qa-system.md §13.1 `duplication_rate=0.0` and §9's k-by-connectors-only (design-note text, not an ADR); ADR-0013 point 2 is implemented as written ("sheet boundaries its answer crosses")
---

# ADR-0028 — Duplication in the headline

**Question.** The user wants the same item drawn on several sheets (2026-10-01). The splitter (`duplication_rate`,
`IdentityGroup`) and the resolver (`identity.py`) already support it, but the headline runs with it switched off
(rate 0.0). At what rate should it be on, with which tags, and what does it do to `k`?

**Evidence.** Architect probe, 2026-10-01: ADR-0025 configuration (24–72 eq, `by_unit` b18 balanced), DRAWING_ONLY,
ADR-0027 fix, seed 0, exact tags.

| Rate | Identity groups | References | Pairs | Stubs/sheet | Occurrence-graph chars (ContextRAG) | G1 | Identity P / R |
|---|---|---|---|---|---|---|---|
| ~H100, 0.0 | 0 | 0 | 381 | 7.54 | 1,950,991 | true | — |
| ~H100, 0.1 | 31 | 33 | 342 | 6.77 | 1,928,089 | true | 1.0 / 1.0 |
| ~H100, 0.25 | 78 | 86 | 290 | 5.74 | 1,900,267 | true | 1.0 / 1.0 |
| ~H100, 0.5 | 156 | 177 | 215 | 4.26 | 1,866,132 | true | 1.0 / 1.0 |
| ~H100, 1.0 | 311 | 351 | 127 | 2.51 | — | true | 1.0 / 1.0 |
| H1000, 0.25 | 756 | — | 2,931 | — | — | true | 1.0 / 1.0 |
| ~H100, 0.25, with ADR-0025 unit-aware clustering | 79 | — | 285 | 5.64 | — | true | 1.0 / 1.0 |
| H1000, 0.25, with unit-aware clustering | 766 | — | 2,896 | 5.80 | — | true | 1.0 / 1.0 |

The last two rows use the final ADR-0025 configuration. The rows above them were measured before the clustering
refinement.

What the table shows:
- **Eligibility.** 311 of 1,577 equipment items have a neighbour on another sheet. Only these can be duplicated.
- **Prompt size.** Duplication *shrinks* ContextRAG's prompt slightly (−1.2 % to −4.3 %): a reference occurrence
  replaces two connector stubs.
- **`k` breaks.** Today `k` counts connector cuts only (`evidence.py`). An edge resolved by duplication is a sheet
  crossing that `k` misses. At ~H100, FLOW_PATH candidates at k = 0 rise from 11,574 (rate 0.1) to 14,553 (0.5).
  At H1000, rate 0.25 (3,000 sampled sources), the 9–16 bin falls from 14,858 to 3,321.
- **The fix.** Count every evidence edge whose two endpoints have **different home sheets**. That `k` reproduced the
  rate-0.0 distribution bin for bin at rate 0.25 (H1000, scratch). It no longer depends on the rate.

**Options**
- **D1** Stay at 0.0. The identity mechanism and `SHEETS_OF_TAG` are never tested at scale.
- **D2** A fixed rate in every headline corpus, plus a home-sheet `k`.
- **D3** Sweep the rate (0, 0.25, 0.5) at every headline point. This triples the paid runs, for a variable the
  claim does not need.
- **D4** D2, plus a should-item sensitivity run at H100 (rates 0 and 0.5) for the strategies that ran.

**Decision: D4, at rate 0.25, with exact tags.**
1. **Why 0.25.** It is unsourced. No drafting rule prescribes duplication (`pid-structural-rules.md` §8 item 6).
   OPEN100 shows **at least 5** items on more than one sheet across 12 sheets (`open100-annotation.md`:
   RCS-PU-102A/B, CND-TK-165, CND-HTR-166, CVCS-HX-111). That is ≥ 0.42 per sheet, a lower bound with no
   denominator. Of the rates probed, **0.25 is the lowest not below it**: 78 groups over 101 sheets (0.77 per
   sheet), against 0.31 at rate 0.1. Stubs/sheet stays inside OPEN100's 2–12.
2. **Exact tags** (user, 2026-10-01: tags stay 1:1). Inexact tags stay in EXP-0004, the resolver evaluation (see
   below).
3. **How `k` is counted.** `k` = the number of evidence edges whose endpoints' home sheets differ. Each `Question`
   also carries `k_connector` and `k_identity` (they sum to `k`). Home sheet = the `IdentityGroup.home` sheet, or the
   item's only sheet.
4. **`SHEETS_OF_TAG` becomes a must-family:**
   - wording: "On which sheets is {tag} drawn?";
   - answer type: `SHEET_SET`;
   - reference: home sheet plus reference sheets;
   - k = number of reference occurrences;
   - candidates: every identity group, plus the same number of single-sheet equipment items as k = 0 controls.
5. **Gates.** **G1 true** and **identity P = R = 1.0** on every headline corpus (SMOKE-04b). The ~H100 and H1000
   probes above already meet both.

**Inexact tags (the user's question, "are tags really identical on every sheet?").** No.
- **The rule says they must be.** HNF requires designations to match across documents (`pid-structural-rules.md`
  C11).
- **OPEN100 breaks it.** It shows `RCS-PU-102A` vs `RC-P102A` for one pump (`open100-annotation.md`), a violation
  that happens in practice.
- **Its frequency is unknown.** This project has no corpus that could measure it.
- **Where it belongs.** Inexact tags measure the resolver, not retrieval at scale. RESOLVE-01 already shows exact
  matching collapses under variants: identity recall 0.125 / 0.0 / 0.0. Putting them in the headline would confound
  the scale claim with a resolver weakness that EXP-0004 is designed to measure. Tag-normalisation work is later
  (user, 2026-10-01).

**Costs.**
- **Code.** The new `k` definition in `evidence.py` and two `Question` fields; one family; `--headline` sets the rate.
- **A new answer type,** `SHEET_SET`, because the final answer step has one format instruction per answer type.
- **`k` stays put by construction.** Home sheets come from the partition, which runs before duplication
  (`splitter.py`). So the new `k` cannot move with the rate. That was measured for FLOW_PATH. For the other
  families it is a reasoned consequence, checked again by AVAIL-01.
- **Families.** `CROSS_UNIT` keeps 20 candidates at ~H100 at every rate. Under the old `k` they drifted to k = 0
  (3 at rate 0 → 13 at rate 0.5).

**Revisit if** G1 or identity P/R falls below 1.0 on a headline corpus, or a real multi-sheet set gives a rate.

**Accepted 2026-10-01 (user, in chat).** Rate 0.25 in every headline corpus. **Amended by the user:** the H100 sensitivity runs at rates 0 and 0.5 are **required, not optional** (user: real-life duplication is probably rarer than 0.25).
