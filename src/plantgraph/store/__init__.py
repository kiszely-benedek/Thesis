"""Turns a resolved plant into what Neo4j needs to load it (design `kg-construction.md` §7).

A **corpus** here is one set of sheets loaded together under one `corpus_id` —
the unit the loader wipes and reloads as a whole, so that two experiments
never contaminate each other's data. `neo4j_plan.py` (T6) computes the Cypher
statements and parameter batches with no database connection at all, so the
query shape can be tested without a live Neo4j instance; `neo4j_settings.py`
and `neo4j_loader.py` (T7) add the driver that actually runs them: settings
say where and how to connect, and the loader wipes, writes and verifies one
corpus's `LoadPlan` against a real server. `neo4j_probe.py` answers one
narrower question fast — is the server there at all — so a stopped database
is reported in seconds rather than found by waiting for the loader to time out.
"""
