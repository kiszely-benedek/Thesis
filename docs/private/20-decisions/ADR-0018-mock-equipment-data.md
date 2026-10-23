---
adr: 0018
title: Generate seeded mock equipment attributes behind a tag-keyed table that real datasheet data could replace
status: accepted
accepted: 2026-09-26
date: 2026-09-26
supersedes: none
---

# ADR-0018 — Mock equipment data, to test retrieval depth

**Question.** On 2026-09-20 the user dropped equipment data (`plant-generator.md` §4.8, struck). On 2026-09-26 the user
revived it as mock data: mock data, to check retrieval depth. Real datasheet data is out of scope — not part of this thesis. Of ChatP&ID's 19 EX01
questions, 8 ask for equipment data (ADR-0013 outcome log). Should generated plants carry attributes, and in what form?

**Options**
- **A1** No attributes (status quo). Attribute questions exist on EX01 only, so the scale sweep and ChatP&ID's 0.91 are
  measured on different question mixes.
- **A2** Mock attributes: revive §4.8 with seeded values that are labelled mock and are visible node properties. They
  enable attribute questions at scale, including multi-hop ones, behind an interface real datasheet data could fill.
- **A3** Wait for real datasheet data. The values would be real, but that data is out of scope — not part of this thesis.

**Decision: A2, as a should-item. It lands by the pilot freeze (CP2, 2026-10-11) or stays out of the headline.**
1. Values as §4.8 specifies: an attribute set per class, one unit per attribute, declared uniform ranges, and a separate
   `data_rng`, so topology is identical with data on or off. `GeneratorConfig.equipment_data` records the switch.
2. Interface: `EquipmentDataTable`, with rows `(plant_id, tag, attribute, value: float | str, unit, source)`. The mock
   generator emits one. The builder writes it into the pyDEXPI objects by tag, and the adapter reads them the same way
   it reads EX01 (one path, ADR-0009). Real datasheet data would simply be another table.
3. Merge contract: the key is our equipment `tag`, exact and unique per plant. Attribute names are pyDEXPI 1.2.0 names
   (§4.8 table) or come with a mapping he supplies. Each attribute has one canonical unit. Unknown tags or attributes are
   counted in `ConversionReport`, never silently dropped. Data sits on the home occurrence only (`splitter.py:182–184`).
4. The attributes join `VISIBLE_NODE_PROPERTIES`, which reopens the frozen §4.4/§4.5 through §10 Q4. `source` is never visible.
5. New families (`qa-system.md` §9): `LOOKUP_ATTRIBUTE` (k = 0) and `ATTRIBUTE_VIA_PATH`, for example "differential
   pressure of the pump upstream of T-201", whose answer lies k sheets away. Scoring: numeric equality at the generated
   one-decimal rounding, and the unit must match.
6. Data on/off is part of `RunConfig`, and the `ContextWall` is measured with the same setting. It is frozen per sweep.
   The thesis calls the values **mock** wherever they appear.

**Why**
- Depth is the axis of the thesis. A multi-hop attribute question needs the path (k connectors) plus a property at its end.
  ContextRAG pays for every attribute in its prompt; CypherRAG pays for none. The strategies should diverge here.
- It restores ChatP&ID's question mix (8 of 19 are attribute lookups) at scale, so the comparison is like for like.
- The design already exists (§4.8), and its one open question (DISCHARGE → `differentialPressure`) is answered.

**Costs.** The coder work is step 3b, two families and numeric scoring. The estimate is a few tasks of qa-system §18
size, unmeasured, and they compete with 17 must-items. The gate in the Decision caps that risk. Attributes enlarge the
serialized graph, so the wall falls at fewer sheets, and runs with data on and off cannot be compared. Mock values are
not engineering-plausible: they test lookup and depth, never engineering judgement, and realism is never claimed (ADR-0007).

**Revisit if** real datasheet tags cannot be mapped to ours, A2 misses 2026-10-11 (the families become a could-run
after the headline), or the pilot shows k = 0 attribute questions already failing on ContextRAG.

## Outcome log
- **2026-09-26** **The user chose A1, not the recommended A2:** no equipment attributes in the generated plants. Attribute questions exist only in EXP-0001 (EX01). Equipment data is out of scope — not part of this thesis (ADR-0021); `plant-generator.md` §4.8 stays struck.
