"""The question generator: templates, reference functions, evidence and sampling.

Every module here reads only the **ground-truth** plant graph, the
splitter's `SplitManifest`, and the raw (pre-`localize()`) `SheetGraph`s —
never the Neo4j store and never `Resolution.plant` (design `qa-system.md`
§2.1, §9; ADR-0013 points 1-2). That is what lets a question's reference
answer be computed once, in plain Python, and trusted regardless of how any
retrieval strategy under test later answers it.

- `evidence.py`: which off-page connectors a reference answer's evidence
  crosses (`k`), and which sheets show that evidence.
- `common.py`: small graph-walk helpers and `Question` assembly, shared by
  every family module.
- `templates.py`: the one wording of each question template.
- `families_lookup.py`, `families_flow.py`, `families_loop.py`,
  `families_isolation.py`, `families_aggregate.py`, `families_abstain.py`:
  one candidate-generating function per question family (design §9's table).
- `families_dev2_reach.py`, `families_dev2_local.py`: the six dev-new families (design
  `question-aware-retrieval.md` §8.2), including the two yes/no ones.
- `families.py`: collects every family under one name per `QuestionFamily`, split into the
  12 dev-old and the 6 dev-new generators.
- `availability.py`, `sample.py`: k-bins, the seeded stratified draw, and the
  report of candidates per family and bin.
- `cli.py`: `python -m plantgraph.qa.questions` writes the JSONL and report.
"""

from __future__ import annotations
