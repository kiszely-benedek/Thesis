"""The handbook-rule registry of the v2 generator (design generator-v2-2-handbook-rules.md 3-4).

A **rule** is one design practice from a process-engineering handbook (for example "a reciprocating
pump has no external check valve", Toghraei 2019 p.192). The registry lists every rule with its
source page, its kind and a check that verifies a generated plant; rules read but not encoded are
listed too, with the reason. `python -m plantgraph.benchmark.v2.rules --table` prints it.
"""
