"""The method-and-effort cascade: route each question to the cheapest tier that settles it.

A *tier* is one fixed run of one strategy (e.g. a Cypher query at low effort). A cascade
policy tries the tiers in order and stops at the first answer it accepts. The cascade is
evaluated offline: `join.py` lines up the stored per-question rows of the tier runs, so no
model call is made here. `signals.py` is the only view of a row a policy may read, and it
carries no gold (correct / reference) field. See `40-design/method-and-effort-cascade.md`.
"""
