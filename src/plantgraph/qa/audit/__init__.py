"""Scorer audit (review-fixes §5.3): an independent LLM judge re-checks the deterministic scorer.

The scorer in `qa/scoring.py` stays the primary verdict. This package asks a second model, blind
to that verdict, whether each audited answer is right, then measures how often the two agree.

Modules, in the order the data flows:

- `sources`: read stored answer rows and questions into `SourceRow`s.
- `select`: choose which rows to audit, in the registered budget order.
- `excerpt`: turn a gold-side subgraph JSON into the plant text the judge reads.
- `judge`: build the blind judge prompt, call the model, parse its JSON verdict.
- `budget`: the spend ledger with the hard cap, and sizing from a measured per-call cost.
- `pilot`: the 45-row gate-G2 pilot set.
- `runner`: run a plan of rows through the judge under the ledger.
- `report`: agreement, Cohen's kappa, disagreements, the G2 verdict.
- `cli`: `python -m plantgraph.qa.audit` sub-commands.
"""
