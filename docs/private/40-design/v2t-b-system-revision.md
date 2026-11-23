---
component: qa/v2tb — V2T-B, a documented revision of the frozen V2T-A2 that reads valve positions and names untagged valves; run beside V2T-A2 on the same v2.2 plants in EXP-0009 (freeze E10)
status: draft — awaiting review (ADR-0067 proposed)
date: 2026-11-23
related: [ADR-0066, ADR-0067 (proposed), ADR-0053, ADR-0060, ADR-0061, ADR-0065, ADR-0021, ADR-0027, ADR-0028, ADR-0029,
          40-design/generator-v2-2-handbook-rules.md (§8, §10, §11, §12), 40-design/qa-tuning-v2.md,
          30-experiments/EXP-0008-v2-rerun.md, 30-experiments/EXP-0007-V2T-validation.md]
---

# Design — V2T-B: the system revision that sees valve positions and names untagged valves

## 0. Recommendation

The user chose **D1 = C** on 2026-11-23: both systems run on the same v2.2 plants. V2T-A2 stays frozen at E9 and
measures the data. **V2T-B** is a small, additive revision that measures what the new content is worth to a system
that can see it.

V2T-B changes four things and nothing else:
1. The store of a **B corpus** keeps the valve property `operating_position` (NO, NC, CSO, ...). An A corpus of the
   same plant does not.
2. The schema text, the primer and the agent's item properties mention that property, **only on B corpora**.
3. A new answer type, **VALVE_SET**, lets an answer name an untagged valve by a **descriptor**: its class, its line
   number and the tagged item it sits next to.
4. A scorer for VALVE_SET resolves each descriptor to plant nodes and compares node sets.

Every V2T-B file is new. No E9 system-side path changes, so V2T-A2 stays byte-identical (gate G0f). V2T-B gets its
own freeze, **E10**, a tuning budget of at most three rounds on one dev plant, and its own validation pair.

**How the comparison separates data from system:**

| Effect | Comparison | Paired? |
|---|---|---|
| Data (v2.2 against v2.1) | V2T-A2 on v2.2, scope R, against V2T-A2 on v2.1 (EXP-0008), per scale, common families | no (different plants) |
| System, no harm | V2T-B − V2T-A2 on scope R, same plants, same questions | yes |
| System, new content | V2T-B − V2T-A2 on scope X (position-aware and untagged-answer isolation), same plants, same questions | yes |
| Scale (thesis claim) | Q4 on V2T-A2 (scope R) and Q4-B on V2T-B (scope R ∪ X) | no (two scales) |

What this buys the thesis claim: Q4 is then tested twice on the same handbook-checked plants, once by a system that
cannot use the new content and once by one that can. If both hold, "the scale result does not depend on how much of
the drawing the system can read" becomes a measured statement.

## 1. What stays frozen, and what relaxes for the B arm

**Rule of the paired design.** Both arms run on the **same plants**. So nothing that changes the plant data can be
done for B alone. Every data-side deferral that exists because the frozen system cannot ingest it stays deferred.

| Constraint (where it came from) | V2T-A2 | V2T-B | Why |
|---|---|---|---|
| `operating_position` not in the store (design §10, option A) | kept | **relaxed**: stored and visible on B corpora | system-side, per corpus |
| Isolation candidates whose answer holds an untagged valve are refused (§11) | kept in scope R | **relaxed** in scope X: answered with descriptors | gold side plus B's answer type |
| Gold is topological only (§11) | kept | **relaxed** for the new family OPEN_VALVES_TO_ISOLATE (§4) | a new family with its own natural wording |
| Primer (ADR-0041) explains ISA only | kept | **extended** by one paragraph on positions and untagged valves | additive file |
| Fail action (FO/FC/FL) out of the store | kept | **kept** | no question uses it; a visible field nobody asks about cannot be measured |
| TOG73 untagged branch pipes (frozen `graph/line_view.py`) | deferred | **still deferred** | the plants are shared, and A2's frozen line view must ingest them |
| Functional-only gauge tags, parallel loop numbering (resolver, ADR-0027 key) | deferred | **still deferred** | store-side, shared by both arms |
| API "S" letters (primer) | deferred | **still deferred** | the data would contradict A2's frozen primer, so A2 would be harmed by construction |
| Demo (ADR-0064) | H1000g21p1 on V2T-A2 | **no demo** | one corpus in Neo4j; the demo is not an experiment arm |

**Answer to the user's question "could TOG73 become possible?"** Not under D1 = C. It would need a change to the
frozen line view, and V2T-A2 must ingest the same plants. TOG73 would only become possible if the A2 arm were dropped,
and then nothing would separate the data effect from the system effect. It stays deferred (generator design §4.9).

## 2. Store: one plant, two corpora

- **Corpus ids.** The plant `H1000g22p1` is ingested twice: `H1000g22p1` (A view, positions stripped, as T5 does
  today) and `H1000g22p1B` (B view, positions kept). The precedent is the identity arm's `H1000g21p1V`.
- **One generation.** Both views load the same DEXPI file and the same `GenerationRecordV22`; only the adapter's
  strip step differs.
- **One corpus in Neo4j at a time** (user rule). The launcher loads A, runs A2, wipes, loads B, runs B. EXP-0008
  measured the four Neo4j load stages at 27.1 s on a 1,000-sheet plant, so the reload is cheap.
- **Where the property sits.** On the valve node (the `PipingComponent`), as `operating_position` with one of
  `NO NC LO LC CSO CSC`. Valves with no position drawn have none, which reads "normally open" (TOG p.114).

**Alternatives considered:**
- *One store with the property, and A2's schema text hiding it.* Rejected. A2's agent tools read
  `VISIBLE_NODE_PROPERTIES`, and a Cypher query can name any property. A2 would then not be the E9 system.
- *Positions as separate `:Position` nodes.* Rejected. A property is the boring option, and it is how DEXPI carries
  it (a custom attribute on the component, §8 of the generator design).

## 3. System files (all new, under `src/plantgraph/qa/v2tb/`)

| File | What it does | Basis |
|---|---|---|
| `visible.py` | `VISIBLE_NODE_PROPERTIES_B = VISIBLE_NODE_PROPERTIES \| {"operating_position"}`; the B item-property keys for `plant_api` | `graph/schema.py` unchanged |
| `schema_text_b.py` | builds A's schema text, then adds the position paragraph **iff** the corpus's `LoadPlan` holds `operating_position` | `qa/schema_text.py` unchanged |
| `primer_b.py` | A's primer plus one paragraph: what NO/NC/CSO/LO/LC/CSC mean (TOG p.114), that a valve without a position is normally open, that in some areas manual valves carry no tag, and how to name such a valve | ADR-0041 primer unchanged |
| `final_answer_b.py` | the VALVE_SET answer rules (§5) | V2T final-answer rules (ADR-0061) unchanged for other types |
| `scoring_b.py` | the descriptor resolver and set comparison (§5) | `qa/scoring.py` unchanged |
| `policy_b.py` | the cascade policy `cascade_v4_iso_b`: the same tiers and escalation rule as `cascade_v4_iso`, with VALVE_SET treated as TAG_SET in the escalation rule | ADR-0061 5C |
| `pins_b.json`, `params_b.json` | the same Luna pins and parameters as E9 | E9 |

**Selection.** The harness picks the B files when the run config names system `v2t_b`. With system `v2t_a2` nothing
new is imported. A test asserts that importing `plantgraph.qa.v2tb` changes no E9 module object.

**Schema-text paragraph (draft, the tuning may reword it):**

> Valves may carry `operating_position`: NO normally open, NC normally closed, LO/LC locked open/closed, CSO/CSC
> car-sealed open/closed. A valve without the property is normally open. Manual valves in some areas carry no tag.
> Such a valve is named by its class, its `line_number` and the tagged item it sits next to (see the answer rules).

## 4. Question families and scopes

Two draws per plant. Both are gold-side changes, made under the ADR-0060 1B pattern. The v2.1 question sets stay
byte-identical (T0 hash).

**Scope R — replication** (the EXP-0008 recipe, 280 questions per plant). The §11 rules of the generator design hold:
candidates whose answer holds an untagged valve are refused. Both arms answer R.

**Scope X — extension** (new, 50 questions per plant for B, 40 for A2):

| Family | Question (template) | Answer type | Split | Asked of |
|---|---|---|---|---|
| OPEN_VALVES_TO_ISOLATE | "Which normally open valves must be closed to cut {tag} off from everything upstream?" | VALVE_SET | dev | both |
| OPEN_VALVES_TO_ISOLATE_DOWNSTREAM | "... from everything downstream?" | VALVE_SET | held-out (sealed) | both |
| UPSTREAM_ISOLATION_X | the registered UPSTREAM_ISOLATION text, drawn **without** the untagged refusal and not already in R | VALVE_SET | dev | both |
| DOWNSTREAM_ISOLATION_X | the registered DOWNSTREAM_ISOLATION text, drawn the same way | VALVE_SET | held-out (sealed) | both |
| POSITION_OF_VALVE | "What is the normal operating position of valve {tag}?" | POSITION (new enum) | dev | B only |

- **Gold of OPEN_VALVES_TO_ISOLATE.** The topological walk of UPSTREAM_ISOLATION (first operated valve on every
  route), minus the valves whose position is NC, LC or CSC: a route whose first valve is already closed needs no
  action. The wording says "normally open valves", so it is a new, natural question, not a rewording of the
  registered one (user rule: natural questions only).
- **Why the registered isolation families keep topological gold.** "Which valves must be closed" includes a valve
  that is already closed: an isolation list names it so it is locked and verified. Changing its gold would change
  the meaning of a registered family.
- **Why A2 is asked the X isolation families.** A2 cannot see positions or name untagged valves. Its score on X is
  the baseline that makes B − A2 on X the value of the new content, on the same questions. A2 receives each X question
  with answer type TAG_SET, through a gold-side adapter, because A2's frozen final-answer code knows no VALVE_SET. A2
  can still be right where the gold holds only tagged valves and no closed one.
- **Why A2 is not asked POSITION_OF_VALVE.** It cannot see the property, so its score is fixed by construction, and
  its frozen code knows no POSITION type.
- **Availability.** At least 10 candidates per family per plant (ADR-0029, as §11). Under the per-document tagging
  unit (generator design §5), a 100-sheet plant is one document. On an untagged 100-sheet plant, R's two isolation
  families have no candidate, so they are **pre-registered unavailable in scope R on v2.2**, at both scales. Their
  content moves to X, where both arms are asked.
- **Reported per X question:** whether the gold holds an untagged valve, and whether OPEN_VALVES gold differs from the
  topological gold (the "discriminating share").

## 5. VALVE_SET: naming an untagged valve

**Answer item:** either `{"tag": "GTV-1203"}` or
`{"class": "GateValve", "line_number": "6\"-P-1203-A1A", "next_to": "FV-1203", "side": "upstream"}`.
`side` says on which side of `next_to` the valve sits along the flow.

**Gold.** Each untagged valve in a gold answer gets a canonical descriptor: its class, its line number, the nearest
tagged item along `send_to` on the same line (downstream first, else upstream), and the side. A candidate is
**refused** if any untagged valve in its answer has no descriptor that resolves to exactly that one node. The
refused share is reported.

**Scoring (`scoring_b.py`).**
1. Each answered item is resolved to plant nodes.
   - A tag resolves as today.
   - A descriptor resolves to every node with that class and line number that has `next_to` as its nearest tagged
     neighbour on that side, across untagged fittings and valves only.
2. An item that resolves to zero or to two or more nodes is wrong.
3. The answer is right iff the set of resolved nodes equals the gold node set.

So any description that picks out exactly the right valve counts, not only the canonical string.

**Self-tests (free, before E10):**
- the gold descriptors score 1.0 against their own gold;
- a descriptor with the wrong side, line or class scores 0;
- the A2 adapter's TAG_SET answers score as the frozen scorer does on R.

**Audit.** The scorer audit (P1) samples B's VALVE_SET and POSITION rows as their own stratum, because the scorer is
new.

**Alternatives considered:**
- *(class, line number) only.* Rejected: the two block valves of a control-valve station share both.
- *An exact canonical string.* Rejected: it would score phrasing rather than identification.
- *Expose the store's internal uid.* Rejected: it is bookkeeping that the schema text never mentions, and no engineer
  could say it.

## 6. Tuning, freeze E10 and re-validation

- **Tuning set:** the dev plant `D100g22` only, with B's dev families plus scope R's dev families.
- **Budget:** at most three rounds (ADR-0061 precedent). The basis is EXP-0007's measured V2T tuning, about $1.30
  for three rounds (`EXP-0007-V2T-validation.md`).
- **What tuning may touch:** only the B files of §3, and each round's change is logged in ADR-0067. The held-out X
  families are never generated on a dev plant.
- **Stopping rule:** stop when a round raises B's dev accuracy by less than 1 point, or after round 3.
- **Freeze E10** (one user commit):
  - the E9 system-side path list, unchanged (checked as in ADR-0060 1B);
  - the sha256 of every B file;
  - the PREREG A of EXP-0009.

  The replays must be byte-identical at E10: one cache-only replay per A2 tier, as E9 requires, plus one per B tier
  of the B validation runs.
- **Re-validation:** B on `VAL100g22` and `VAL1000g22`, the same pair as A2.
  - **G1-B:** no dev family below 50 % on both plants (EXP-0008's G1).
  - **G1-B2:** on the pair, B − A2 on scope R ≥ −0.05 (point estimate). Otherwise B is not run sealed, and the
    finding is reported.
  - The validation pair also measures B's $/q, from which the sealed caps are recomputed.

## 7. Claims (pre-registered in EXP-0009 PREREG A)

| Claim | Arm and scope | Pass |
|---|---|---|
| Q4 (primary) | A2, scope R, S1000 − S100 | interval contains 0 or lies above (ADR-0053) |
| Q4-B | B, scope R ∪ X | the same rule |
| SB1 no harm | B − A2, scope R, paired | the lower bound of the interval is above −0.03 |
| SB2 content value | B − A2, scope X (isolation families), paired | the interval lies above 0 |
| K1–K3, Q5 | A2, scope R | as EXP-0008 |
| Descriptive | data effect per scale; X sub-scopes (untagged gold, discriminating share); POSITION_OF_VALVE accuracy; refused shares | — |

**The SB1 margin.** I set it at −0.03, about the half-width of EXP-0008's Q4 interval (−0.005, [−0.035, +0.025]).
This is a declared choice, not a measured threshold.

## 8. How each part reports its own accuracy

| Part | Measured against | Where |
|---|---|---|
| Descriptor gold | uniqueness: refused share per family and plant | gold report |
| Scorer B | self-tests; audit stratum | G0 gate; audit report |
| Store B | resolution gate G0g on the B corpus; `operating_position` count equals the DEXPI count | ingest report |
| Arm B | Q4-B, SB1, SB2 | sealed report |

## 9. Open questions

1. **The SB1 margin −0.03** is a declared value. The user may prefer to report B − A2 on R descriptively.
2. **Valves with no tagged neighbour.** A root valve on a network sheet of an untagged document may have only
   connectors and tees around it, none of them tagged. Such a valve has no descriptor, so a candidate whose answer
   holds it is refused (§5). I propose no special rule. The coder reports the refused share on the dev plants before
   E10. If it exceeds a quarter of an X family's candidates, the case returns to the architect.
