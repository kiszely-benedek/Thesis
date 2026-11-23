---
adr: 0067
title: Add V2T-B, an additive revision of V2T-A2 that reads valve positions and names untagged valves by a descriptor, and run it paired with the frozen V2T-A2 on the same v2.2 plants (freeze E10)
status: accepted (user, 2026-11-23)
date: 2026-11-23
supersedes: none. Leaves ADR-0061's V2T-A2 and its freeze E9 unchanged; extends ADR-0060's gold-side/system-side split to a second system.
design: 40-design/v2t-b-system-revision.md
---

# ADR-0067 — V2T-B: a system revision that sees valve positions and untagged valves

## Context

- **What v2.2 adds.** Generator v2.2 (ADR-0066) draws two things a P&ID engineer reads:
  - normal valve positions (NO, NC, CSO, …);
  - drawing sets whose manual valves carry no tag (9 of 12 real sets, design §18.2).
- **What the frozen system can do with them.** V2T-A2 (freeze E9) can use neither:
  - positions are stripped before its store;
  - its answers are tag sets, so an untagged valve cannot be named.
- **The user's choice.** On 2026-11-23 the user chose D1 = C: run both the frozen system and a documented revision on
  the same plants, and top up the credit so cost does not block.
- **What this ADR settles.** How the revision is built so that the data effect and the system effect stay
  separable.

## Options considered

**1. How B's store differs from A's**
- **A. One store per plant with the property, and A2's schema text hiding it.** One load per plant. But A2's agent
  tools read `VISIBLE_NODE_PROPERTIES`, and a Cypher query can name any property, so A2 would no longer be E9.
- **B. Two views of the same generated plant:** an A corpus (stripped, as now) and a B corpus (kept), loaded one at a
  time. The cost is one wipe and reload per plant, which EXP-0008 measured at 27.1 s at 1,000 sheets. A2 stays E9.
- **C. Positions as separate nodes.** A new label and new relations for something DEXPI carries as an attribute.

**2. How an untagged valve is named in an answer**
- **A. (class, line number).** Short, but not unique: a control-valve station's two block valves share both.
- **B. (class, line number, nearest tagged item, side), resolved by the scorer to plant nodes;** right iff the
  resolved node set equals the gold set. It accepts any description that picks out exactly the right valve.
- **C. An exact canonical string.** Easy to score, but it scores phrasing rather than identification.
- **D. The store's internal uid.** Unique, but it is bookkeeping no engineer could say.

**3. Which questions the B arm adds**
- **A. None; B runs scope R only.** It shows no harm, but not what the content is worth.
- **B. Scope X:**
  - OPEN_VALVES_TO_ISOLATE (up; down held-out), a new, naturally worded family whose gold drops already-closed
    valves;
  - the registered isolation questions drawn without the untagged refusal;
  - POSITION_OF_VALVE (B only).

  Both arms answer X's isolation families, so B − A2 on X is the value of the content, on the same questions.
- **C. Change the registered isolation families' gold to position-aware.** It changes the meaning of a registered
  family; "which valves must be closed" rightly includes an already-closed valve that must be locked.

**4. Development and freeze**
- **A. No tuning; freeze B as first written.** Cheapest, but an untested prompt paragraph may lose points that are
  the prompt's fault rather than the content's.
- **B. At most three tuning rounds on one dev plant (ADR-0061 precedent),** only on B files, then freeze E10, then
  re-validate on the A2 validation pair with G1-B and a no-harm gate G1-B2.

## Decision

1B, 2B, 3B, 4B.

- **Files.** Every B file is new, under `src/plantgraph/qa/v2tb/`. No E9 system-side path changes (G0f), and a
  test asserts that importing the B package changes no E9 module object.
- **Fail action stays out** of B's store: no question uses it.
- **Claims** (pre-registered in EXP-0009 PREREG A):
  - **Q4-B** on scope R ∪ X;
  - **SB1 (no harm):** B − A2 on R, paired, reported **descriptively** with its interval. There is no pass margin (user, 2026-11-23); the proposed −0.03 was dropped;
  - **SB2 (content value):** B − A2 on X's isolation families, paired, above 0.
- **No demo** for B.

## Rationale

- **The paired design is what makes C worth its cost.**
  - Same plants and same questions: B − A2 is the system's effect alone.
  - A2 against EXP-0008 is the data's effect alone.
  - Q4 is then tested by two systems that read different amounts of the drawing.
- **Additive files keep the frozen arm frozen.** That is the boring way to run a revision beside a baseline.
- **The descriptor naming is what an engineer says** ("the gate valve on line 6"-P-1203 just upstream of FV-1203").
  Resolving it to nodes scores identification, not wording.
- **Natural questions only** (user rule): the new family has its own wording and gold; no registered question is
  reworded or re-golded.

## Consequences

**Makes easy:**
- separating data from system;
- a second test of Q4;
- the thesis statement of what positions and untagged naming are worth.

**Makes hard:**
- two loads per plant;
- about 46 h of P1 machine time;
- a new scorer that the audit must cover (a B stratum);
- R's isolation families are unavailable (ADR-0066), so isolation is compared in X only.

**Forecloses:** data-side changes that only B could ingest (TOG73, functional-only gauge tags, parallel loop
numbering) stay deferred, because A2 must ingest the same plants.

**Revisit if:**
- G1-B2 fails (B is then not run sealed);
- more than a quarter of an X family's candidates are refused for a non-unique descriptor;
- the B validation pair's $/q puts its sealed step above the ledger.
