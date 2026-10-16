"""The demo status fields: why the database tier is out and the sheet count.

Reuses the toy server fixtures of `test_demo_app`; no Neo4j is reached (the probe is faked there).
"""

# ruff: noqa: F811  (imported pytest fixtures are re-declared as test arguments)
from __future__ import annotations

from plantgraph.demo.app.store_probe import StoreState
from qa_harness_toy import CORPUS_ID
from test_demo_app import Client, env, make_client, toy  # noqa: F401


def test_status_says_why_the_database_tier_is_out_and_how_many_sheets_there_are(
    make_client: Client,
) -> None:
    client = make_client()

    (corpus,) = client.get("/api/status").json()["corpora"]

    # the toy was ingested with the occurrence layout, the policy's tier reads the plant layout
    assert StoreState.model_validate(corpus["store"]) == StoreState(kind="wrong_profile")
    assert corpus["n_sheets"] == len(client.get(f"/api/corpora/{CORPUS_ID}/index").json()["pages"])


def test_a_corpus_that_is_not_loaded_yet_has_no_store_state(make_client: Client) -> None:
    (corpus,) = make_client(load=False).get("/api/status").json()["corpora"]

    assert corpus["store"] is None and corpus["n_sheets"] is None
