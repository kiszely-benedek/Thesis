---
adr: 0027
title: Signal off-page connectors print their loop number, so DRAWING_ONLY corpora resolve exactly
status: accepted
date: 2026-10-01
supersedes: none — amends the label content of ADR-0023 in part (DRAWING_ONLY stands; signal flags gain one field)
---

# ADR-0027 — What a signal off-page flag carries

**Question.** ADR-0023 put the headline corpora on DRAWING_ONLY labels and required G1 to hold there. Does it hold?

**Evidence: it does not hold today.** The architect probe of 2026-10-01 ran today's code, generator defaults,
`flow_greedy` budget 16, seed 0, DRAWING_ONLY.

| Size | Pairs | Unresolved | Pair recall | G1 |
|---|---|---|---|---|
| 1,000 units | 1,566 | 8 | 0.9974 | false |
| 2,900 units | 4,558 | 30 | 0.9967 | false |

All 8 unresolved at 1,000 units were inspected. Each has the reason "ambiguous: 2 outgoing, 2 incoming share this
label". Each is a `SIGNAL` stub, relation `send_signal_to`, with no line number and no fluid.

The cause: two signal lines cut between the same two sheets, in the same direction, leave the shared-label key
(`pairing.py` `_group_key`) with nothing to tell them apart. The 30 at 2,900 units were counted, not inspected.

Unresolved connectors also appear on ADR-0025-style corpora without the fix: 32–96 eq: 8; 24–72 b16 seeds 1 and 2:
4 each. Their reasons were not inspected. The b16 seed 1 and 2 corpora resolve fully once S1 is applied.

ADR-0023's revisit clause, "unresolved at a headline size in this style", has fired.

**Options**
- **S1** A signal stub carries the **loop number** of the cut edge's instrument end (`loop_tag`, already a visible
  property). The pairing key gains `loop_tag`. Rule basis: KLM p. 12 item 8: signals "from sheet to sheet shall be
  terminated … at a box indicating the continuation instrument number, location, and drawing number"
  (`pid-structural-rules.md` C7). Every instrument number in a loop shares the loop number (`FT-3-2`, `FIC-3-2`,
  `FV-3-2`).
- **S2** FULL labels (the partner connector number) for signal stubs only. This works, but it is the easier-than-reality
  label ADR-0023 rejected.
- **S3** Accept the failure, and run every headline corpus on the oracle path (ADR-0010 decision 3). The oracle
  `Resolution` is not built, and the headline would never be end-to-end.
- **S4** Never cut signal lines: keep a whole loop on one sheet. This changes the clustering, and real sets do
  continue signals across sheets (C7).

**Decision: S1.**
- `OffPageConnector` and the stub node gain `loop_tag` on `SIGNAL` cuts.
- `ConnectorLabel` gains `loop_tag: str | None`.
- `_group_key` appends it.
- Pipe stubs are unchanged.

**Scratch result** (monkeypatched prototype, re-measured after the code lands): G1 true with 0 unresolved at 1,000
and at 2,900 units (today's configuration). It is also true on the ADR-0025 configuration at ~H100, seeds 0–2, and
at H1000.

**Why.** It is the only option that keeps both DRAWING_ONLY and an end-to-end headline, and it adds a field that real
flags print. Pair precision stays 1.0 by construction (`kg-construction.md` §5.2), because both stubs carry the same
`loop_tag`.

**Costs.** About 3 modules plus tests. SMOKE-04 is re-run as **SMOKE-04b** on the headline preset, and that run is
the ADR-0023 gate.

**Revisit if** a signal ambiguity survives the loop number: two cuts of one loop between the same sheets, in the same
direction, with the same relation. This was not seen in the probe.

**Accepted 2026-10-01 (user, in chat).** As written. SMOKE-04a (main session, 1,000 units, code `5ea63b5`) confirmed today's failure: G1 false, 8 unresolved, pair R = 0.9974.
