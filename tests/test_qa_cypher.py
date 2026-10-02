"""The Cypher write filter and the view's refusal to send a rejected query (QA-T12), no database."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from plantgraph.qa.cypher import WriteClauseError, find_write_clause, reject_write_clauses
from plantgraph.qa.neo4j_view import (
    Neo4jGraphView,
    StoreMismatch,
    check_counts,
    check_single_corpus,
)
from plantgraph.store.neo4j_plan import CypherStatement, LoadPlan
from plantgraph.store.neo4j_settings import Neo4jSettings


@pytest.mark.parametrize(
    ("query", "keyword"),
    [
        ("CREATE (n:Pump {tag: 'P-1'})", "CREATE"),
        ("MATCH (n) DETACH DELETE n", "DETACH"),
        ("MATCH (n) DELETE n", "DELETE"),
        ("MATCH (n) SET n.tag = 'x' RETURN n", "SET"),
        ("MATCH (n) REMOVE n.tag", "REMOVE"),
        ("MERGE (n:Pump {tag: 'P-1'})", "MERGE"),
        ("DROP INDEX corpus_node_tag", "DROP"),
        ("LOAD CSV FROM 'file:///x.csv' AS row RETURN row", "LOAD"),
        ("match (n) set n.tag = 'x'", "SET"),  # case does not matter
        ("MATCH (n)\nWHERE n.tag = 'a'\nCREATE (m)", "CREATE"),  # not on the first line
        ("MATCH (n) // harmless\nSET n.x = 1", "SET"),  # a comment does not hide it
    ],
)
def test_write_clauses_are_found(query: str, keyword: str) -> None:
    assert find_write_clause(query) == keyword
    with pytest.raises(WriteClauseError, match=keyword):
        reject_write_clauses(query)


@pytest.mark.parametrize(
    "query",
    [
        "MATCH (n:Pump {tag: 'SET-1'}) RETURN n.tag",  # a keyword inside a string literal
        'MATCH (n {tag: "DELETE ME"}) RETURN n',
        "MATCH (n) WHERE n.set = 1 RETURN n",  # a property called set
        "MATCH (n) RETURN n.tag ORDER BY n.tag SKIP 1 LIMIT 5",
        "MATCH (n:Sheet) RETURN n.sheet_id // do not CREATE anything",  # inside a comment
        "MATCH (a)-[:send_to|continues_as*1..7]->(b) RETURN DISTINCT b.tag",
        "MATCH (n) WHERE n.offset > 1 RETURN n",  # `offset` merely contains `set`
    ],
)
def test_read_queries_pass(query: str) -> None:
    assert find_write_clause(query) is None
    reject_write_clauses(query)


def _unreachable_view() -> Neo4jGraphView:
    """A view whose server address cannot resolve: any query that is sent fails loudly."""
    settings = Neo4jSettings(
        uri="neo4j://never-sent.invalid:7687", username="u", password=SecretStr("p")
    )
    plan = LoadPlan(
        corpus_id="c",
        schema_statements=[],
        wipe_statement=CypherStatement(query="", parameters={}),
        node_statements=[],
        relationship_statements=[],
        expected_node_labels={"Sheet": 1},
        expected_relationship_types={"has_sheet": 1},
    )
    return Neo4jGraphView(settings, plan)


def test_a_write_clause_is_rejected_before_anything_is_sent() -> None:
    view = _unreachable_view()
    # If the query were sent, the unresolvable host would raise a connection error instead.
    with pytest.raises(WriteClauseError):
        view.run_cypher("CREATE (n:Pump)", timeout_s=1.0, row_cap=10)
    view.close()


def test_row_cap_must_be_positive() -> None:
    with pytest.raises(ValueError, match="row_cap"):
        _unreachable_view().run_cypher("MATCH (n) RETURN n", timeout_s=1.0, row_cap=0)


def test_the_view_serves_only_cypher_rag() -> None:
    with pytest.raises(NotImplementedError, match="NetworkxGraphView"):
        _unreachable_view().items()


def test_one_corpus_check_accepts_exactly_the_expected_drawing_set() -> None:
    check_single_corpus(["run-1"], "run-1")


@pytest.mark.parametrize("found", [[], ["other"], ["run-1", "other"], ["run-1", "run-1"]])
def test_one_corpus_check_refuses_anything_else(found: list[str]) -> None:
    with pytest.raises(StoreMismatch, match="wipe_corpus"):
        check_single_corpus(found, "run-1")


def test_count_check_names_both_sides() -> None:
    check_counts("node label", {"Sheet": 2}, {"Sheet": 2}, "run-1")
    with pytest.raises(StoreMismatch, match="'Sheet': 3"):
        check_counts("node label", {"Sheet": 2}, {"Sheet": 3}, "run-1")
