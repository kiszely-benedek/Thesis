---
adr: 0016
title: Never drop a DEXPI item; unknown classes map to a generic class, promoted only when a question needs it
status: accepted
accepted: 2026-09-26
date: 2026-09-26
supersedes: none
---

# ADR-0016 — What the adapter does with a DEXPI class the schema does not know

**Question.** On EX01 the adapter keeps 23 of 36 conceptual nodes and 16 of 39 edges, silently. The flow path
T4750 → P4712 (a ChatP&ID question) breaks at the first hop. What should happen to an unknown class?

**Options**
- **U1** Add a schema class for every class EX01 uses. Exact, but each new file grows the schema toward all
  514 pyDEXPI classes, and a class that nobody has added yet is still dropped.
- **U2** Generic fallback: an unknown class becomes the node class `GenericItem`, which keeps the pyDEXPI name.
  An unknown edge kind becomes a generic relation that keeps the original label.
- **U3** U2, plus a dedicated schema class only when a named question needs semantics the fallback lacks.
- **U4** Run EXP-0001 on pyDEXPI's conceptual graph and skip our schema, as ChatP&ID does. This is directly
  comparable to their setup, but it gives EXP-0001 and the scale runs two different pipelines.

**Decision: U3, starting with no promotions.**
1. Nodes: an unknown class maps to `GenericItem`. It gets the property `dexpi_class` (the pyDEXPI name) and
   a `category` taken from its pyDEXPI ancestors (`Pump`→equipment, `PipingComponent`→piping). Its labels
   are the ancestor chain up to that root. For example, P4712 becomes `ReciprocatingPump:Pump:Equipment`.
2. Edges: they keep today's relations (`Pipe` → `send_to`, …). All 23 lost EX01 edges already have one.
   Any other unknown edge label maps to `related_to` with `dexpi_label`, so it is kept, not dropped.
3. Off-page connectors in a file map to their existing schema connector classes. They stay unpaired, and
   `connectors == []` still holds. This replaces the "dropped and counted" rule in `kg-construction.md` §3.
4. A class is promoted to the schema only by a later ADR, and only when a named question needs it.
5. Gate before EXP-0001: EX01 maps 36/36 nodes, T4750 → P4712 is a `send_to` path, and
   `ConversionReport` counts nodes per `dexpi_class` so that no loss can be silent.
6. Details (tag rule per category, label cut-off, where the code lives) belong in `kg-construction.md` §3.

**Why**
- It removes the failure the audit found: a real file never loses a node. The schema stays sized to the
  thesis, not to DEXPI.
- EXP-0001 and the scale runs keep one pipeline (ADR-0009). U4 would give that up for comparability.
- Generated plants do not change: they never emit an unknown class.

**Costs.** Code that filters on `node_class in EQUIPMENT_CLASSES` will miss generic equipment. On EX01,
filters must use `category`. The endpoint rules and the visible properties in `schema.py` must allow
`GenericItem`.

**Revisit if** a ChatP&ID question fails on EX01 because a generic node lacks semantics (promote per rule 4),
or if generic nodes exceed about 25 % of the nodes on some real file.

**Node-count gap (verified 2026-09-26, pyDEXPI 1.2.0).** `GraphAbstractor` gives complete 212 / process 66 /
conceptual 36, so **212 matches ChatP&ID**. Our "214" is the loader's graph before that step; the 2 extra nodes are likely `ConceptualModel` and `MetaData`. Their **53** matches
none of the three levels. It is unexplained (unverified: another pyDEXPI version or their own condensation).
Our adapter's own losses (36 → 23) happen downstream of that gap and do not explain it.

## Outcome log
- **2026-09-26** Accepted by the user as recommended (U3, no promotions).
- **2026-09-26** Clarifications (main session): (1) EX01 has 11 generic nodes of 36 ≈ 31 %, above the ~25 % revisit threshold — EX01 is the file this ADR was written for, so the threshold applies to later real files, not to EX01. (2) The per-`dexpi_class` count lives on `ImportReport`, not `ConversionReport`, because the adapter module is at its 400-line cap (rule 6 leaves placement to `kg-construction.md` §3.1).
