"""The schema text CypherRAG shows the LLM, built from a `LoadPlan` (QA-T12), no database."""

from __future__ import annotations

import hashlib
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


# --- store profiles (ADR-0036, MP-T4) -------------------------------------------------------

#: sha256 of the `occurrence` text for the 4-unit corpus, taken before the plant paragraph
#: existed: the plain `cypher_rag` prompt must not drift.
_OCCURRENCE_TEXT_SHA256 = "8eb49a91c0ccee86d04f26ff30fef31a3464350c68654d134b906529f73ee7ff"


@pytest.fixture(scope="module")
def plant_plan() -> LoadPlan:
    return load_plan_of(four_unit_corpus(), "pytest-schema-text-plant", profile="plant")


def test_the_occurrence_text_is_byte_identical_to_the_one_before_the_plant_layer(
    plan: LoadPlan,
) -> None:
    assert hashlib.sha256(build_schema_text(plan).encode()).hexdigest() == _OCCURRENCE_TEXT_SHA256


def test_the_plant_text_has_the_plant_paragraph_and_not_the_occurrence_one(
    plan: LoadPlan, plant_plan: LoadPlan
) -> None:
    text = build_schema_text(plant_plan)

    assert "(:PlantItem) node" in text
    assert "crossed_sheets" in text
    assert "continues_as" not in text  # the plant has no off-page connector hop
    assert "same_tagged_item_as" not in text
    assert "(:PlantItem)" not in build_schema_text(plan)  # TaggedPlantItem is a class label


def test_the_plant_text_hides_bookkeeping_and_lists_this_plants_labels(
    plant_plan: LoadPlan,
) -> None:
    text = build_schema_text(plant_plan)

    assert "PlantItem" in schema_labels(plant_plan)
    assert "CorpusNode" not in schema_labels(plant_plan)
    for hidden in ("CorpusNode", "corpus_id", "via_connector_uids", "drawn_as"):
        assert hidden not in text
    assert re.search(r"\buid\b", text) is None


def test_crossed_sheets_is_listed_as_a_relationship_property_only_for_the_plant(
    plan: LoadPlan, plant_plan: LoadPlan
) -> None:
    def edge_line(text: str) -> str:
        return next(
            line for line in text.splitlines() if line.startswith("Relationship properties")
        )

    assert "crossed_sheets" in edge_line(build_schema_text(plant_plan))
    assert "crossed_sheets" not in edge_line(build_schema_text(plan))


def test_the_plant_text_reads_the_instrument_chain_in_the_legends_direction(
    plant_plan: LoadPlan,
) -> None:
    flat = " ".join(build_schema_text(plant_plan).split())

    assert (
        "equipment -measured_by-> transmitter -send_signal_to-> controller "
        "-send_signal_to-> actuator -control-> valve"
    ) in flat
    assert "Actuators have no tag" in flat  # ADR-0044, as in the occurrence text


def test_a_plan_holding_both_layers_is_refused() -> None:
    both = load_plan_of(four_unit_corpus(), "pytest-schema-text-both", profile="both")

    with pytest.raises(ValueError, match="'both'"):
        build_schema_text(both)
