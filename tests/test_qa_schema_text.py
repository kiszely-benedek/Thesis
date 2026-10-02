"""The schema text CypherRAG shows the LLM, built from a `LoadPlan` (QA-T12), no database."""

from __future__ import annotations

import re

import pytest

from plantgraph.qa.schema_text import build_schema_text, schema_labels, schema_relationship_types
from plantgraph.store.neo4j_plan import LoadPlan
from qa_cypher_corpus import four_unit_corpus, load_plan_of


@pytest.fixture(scope="module")
def plan() -> LoadPlan:
    return load_plan_of(four_unit_corpus(), "pytest-schema-text")


def test_labels_and_types_come_from_this_corpus_without_bookkeeping(plan: LoadPlan) -> None:
    labels = schema_labels(plan)
    assert "CorpusNode" not in labels
    assert set(labels) == set(plan.expected_node_labels) - {"CorpusNode"}
    assert set(schema_relationship_types(plan)) == set(plan.expected_relationship_types)


def test_text_describes_units_and_connectors_and_hides_bookkeeping(plan: LoadPlan) -> None:
    text = build_schema_text(plan)

    for expected in (
        "PlantSection",
        "ProcessPlant",
        "is_located_in",
        "continues_as",
        "is_drawn_on",
    ):
        assert expected in text
    for hidden in ("CorpusNode", "corpus_id"):
        assert hidden not in text
    assert (
        re.search(r"\buid\b", text) is None
    )  # `fluid_code` contains "uid" but is a word of its own


def test_text_is_the_same_for_the_same_plan(plan: LoadPlan) -> None:
    assert build_schema_text(plan) == build_schema_text(plan)


def test_a_label_the_schema_does_not_allow_is_refused(plan: LoadPlan) -> None:
    bad = plan.model_copy(update={"expected_node_labels": {"drop table": 1}})
    with pytest.raises(ValueError, match="drop table"):
        build_schema_text(bad)


def test_an_imported_generic_label_is_allowed(plan: LoadPlan) -> None:
    labels = {**plan.expected_node_labels, "PipeTee": 3}
    text = build_schema_text(plan.model_copy(update={"expected_node_labels": labels}))
    assert "PipeTee" in text


def test_an_unknown_relationship_type_is_refused(plan: LoadPlan) -> None:
    bad = plan.model_copy(update={"expected_relationship_types": {"hacked_by": 1}})
    with pytest.raises(ValueError, match="hacked_by"):
        build_schema_text(bad)
