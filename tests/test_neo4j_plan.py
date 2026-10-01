"""`build_load_plan` — pure Cypher/parameter generation, no driver, no database (design §7.7).

Two corpora are checked: a small generated plant (4 units, `duplication_rate=0.5`,
so an identity group actually exists) and, when the file is present, the
imported EX01 sheet (which exercises the `GenericItem` label chain, ADR-0016).
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.graph import schema
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution, ResolutionReport
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

_CORPUS_ID = "acme-plant-01"


def _small_corpus() -> tuple[list[SheetGraph], Resolution]:
    """A 4-unit generated plant, split at `duplication_rate=0.5` so an identity group exists."""
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=0.5)
    sheets, _manifest = split(builder.graph, split_config)
    localized, _occurrence_map = localize(sheets)
    return localized, resolve(localized)


def _ex01_corpus() -> tuple[list[SheetGraph], Resolution]:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    imported = import_proteus_sheet(_EX01_PATH)
    localized, _occurrence_map = localize([imported.sheet])
    return localized, resolve(localized)


# --- coverage: every occurrence and every relationship, exactly once ----------------------


def _expected_node_uids(corpus_id: str, sheets: list[SheetGraph]) -> set[str]:
    uids = {f"{corpus_id}|corpus"}
    for sheet in sheets:
        uids.add(f"{corpus_id}|{sheet.sheet_id}")
        uids |= {f"{corpus_id}|{sheet.sheet_id}:{node_id}" for node_id in sheet.graph.nodes}
    uids |= {f"{corpus_id}|unit:{unit_id}" for unit_id in _drawn_values(sheets, "unit_id")}
    uids |= {f"{corpus_id}|plant:{plant_id}" for plant_id in _drawn_values(sheets, "plant_id")}
    return uids


def _drawn_values(sheets: list[SheetGraph], key: str) -> set[str]:
    """Distinct values of one visible node property, read straight from the sheets."""
    return {
        attrs[key]
        for sheet in sheets
        for _node_id, attrs in sheet.graph.nodes(data=True)
        if key in attrs
    }


def _units_in_plants(sheets: list[SheetGraph]) -> set[str]:
    """Units that have at least one occurrence carrying a `plant_id`."""
    return {
        attrs["unit_id"]
        for sheet in sheets
        for _node_id, attrs in sheet.graph.nodes(data=True)
        if "unit_id" in attrs and "plant_id" in attrs
    }


def _occurrences_with_unit(sheets: list[SheetGraph]) -> int:
    return sum(
        1
        for sheet in sheets
        for _node_id, attrs in sheet.graph.nodes(data=True)
        if "unit_id" in attrs
    )


def _actual_node_rows(plan: LoadPlan) -> list[dict[str, object]]:
    """Every node row across every statement, flattened, with its labels attached."""
    rows = []
    for statement in plan.node_statements:
        labels = _labels_of(statement.query)
        for row in statement.parameters["rows"]:
            assert isinstance(row, dict)
            props = row["props"]
            assert isinstance(props, dict)
            rows.append({"labels": labels, "props": props})
    return rows


def _labels_of(query: str) -> tuple[str, ...]:
    inside = query.split("(n:", 1)[1].split(")", 1)[0]
    return tuple(inside.split(":"))


def _expected_relationship_count(sheets: list[SheetGraph], resolution: Resolution) -> int:
    has_sheet = len(sheets)
    is_drawn_on = sum(sheet.graph.number_of_nodes() for sheet in sheets)
    topology = sum(sheet.graph.number_of_edges() for sheet in sheets)
    continues_as = len(resolution.connector_pairs)
    same_tagged_item_as = sum(len(group.references) for group in resolution.identity_groups)
    is_located_in = _occurrences_with_unit(sheets) + len(_units_in_plants(sheets))
    return has_sheet + is_drawn_on + topology + continues_as + same_tagged_item_as + is_located_in


def _actual_relationship_rows(plan: LoadPlan) -> list[dict[str, object]]:
    rows = []
    for statement in plan.relationship_statements:
        for row in statement.parameters["rows"]:
            assert isinstance(row, dict)
            rows.append(row)
    return rows


@pytest.mark.parametrize("corpus_factory", [_small_corpus, _ex01_corpus])
def test_every_node_is_covered_exactly_once(corpus_factory) -> None:  # type: ignore[no-untyped-def]
    sheets, resolution = corpus_factory()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    actual_rows = _actual_node_rows(plan)
    actual_uids = [row["props"]["uid"] for row in actual_rows]

    assert set(actual_uids) == _expected_node_uids(_CORPUS_ID, sheets)
    assert len(actual_uids) == len(set(actual_uids)), "a node must not be written twice"


@pytest.mark.parametrize("corpus_factory", [_small_corpus, _ex01_corpus])
def test_every_relationship_is_covered_exactly_once(corpus_factory) -> None:  # type: ignore[no-untyped-def]
    sheets, resolution = corpus_factory()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    actual_rows = _actual_relationship_rows(plan)

    assert len(actual_rows) == _expected_relationship_count(sheets, resolution)


# --- labels: only from labels_for(), plus the one validated GenericItem exception ----------


def _expected_occurrence_labels(attrs: dict[str, object]) -> tuple[str, ...]:
    """Reimplemented independently of `neo4j_rows._occurrence_labels`, from the design rule."""
    node_class = attrs["node_class"]
    assert isinstance(node_class, str)
    if node_class == schema.NodeClass.GENERIC_ITEM.value:
        dexpi_labels = attrs["dexpi_labels"]
        assert isinstance(dexpi_labels, list)
        return ("CorpusNode", *dexpi_labels, "GenericItem")
    return ("CorpusNode", *schema.labels_for(node_class))


@pytest.mark.parametrize("corpus_factory", [_small_corpus, _ex01_corpus])
def test_occurrence_labels_come_from_the_schema_or_a_validated_generic_chain(
    corpus_factory,  # type: ignore[no-untyped-def]
) -> None:
    sheets, resolution = corpus_factory()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    expected_by_uid = {
        f"{_CORPUS_ID}|{sheet.sheet_id}:{node_id}": _expected_occurrence_labels(attrs)
        for sheet in sheets
        for node_id, attrs in sheet.graph.nodes(data=True)
    }
    actual_by_uid = {
        row["props"]["uid"]: row["labels"]
        for row in _actual_node_rows(plan)
        if row["props"]["uid"] in expected_by_uid
    }

    assert actual_by_uid == expected_by_uid


# --- no leaked properties: an occurrence row carries only V, uid, and corpus_id ------------


@pytest.mark.parametrize("corpus_factory", [_small_corpus, _ex01_corpus])
def test_occurrence_rows_carry_only_visible_properties(corpus_factory) -> None:  # type: ignore[no-untyped-def]
    sheets, resolution = corpus_factory()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)
    occurrence_uids = {
        f"{_CORPUS_ID}|{sheet.sheet_id}:{node_id}"
        for sheet in sheets
        for node_id in sheet.graph.nodes
    }
    allowed_keys = schema.VISIBLE_NODE_PROPERTIES | {"uid", "corpus_id"}

    for row in _actual_node_rows(plan):
        if row["props"]["uid"] not in occurrence_uids:
            continue
        extra = set(row["props"]) - allowed_keys
        assert not extra, f"occurrence row carries hidden keys {extra}"
        assert "stream_kind" not in row["props"]


# --- uniqueness, determinism, and independently recomputed expected_* counts --------------


def test_uid_values_are_unique_across_every_node_row() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)
    uids = [row["props"]["uid"] for row in _actual_node_rows(plan)]
    assert len(uids) == len(set(uids))


def test_build_load_plan_is_deterministic() -> None:
    sheets, resolution = _small_corpus()
    first = build_load_plan(_CORPUS_ID, sheets, resolution)
    second = build_load_plan(_CORPUS_ID, sheets, resolution)
    assert first == second


def test_expected_counts_match_an_independent_tally() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    # Tally built straight from the sheets/resolution — not from the plan's own rows —
    # so this genuinely cross-checks `expected_node_labels`/`expected_relationship_types`.
    label_counts: dict[str, int] = {}
    for label in ("CorpusNode", schema.NodeClass.DRAWING_SET.value):
        label_counts[label] = label_counts.get(label, 0) + 1
    for sheet in sheets:
        for label in ("CorpusNode", schema.NodeClass.SHEET.value):
            label_counts[label] = label_counts.get(label, 0) + 1
        for _node_id, attrs in sheet.graph.nodes(data=True):
            for label in _expected_occurrence_labels(attrs):
                label_counts[label] = label_counts.get(label, 0) + 1
    units = _drawn_values(sheets, "unit_id")
    plants = _drawn_values(sheets, "plant_id")
    assert units and plants, "the toy plant must show units, or this test checks nothing"
    label_counts["CorpusNode"] += len(units) + len(plants)
    label_counts["PlantSection"] = len(units)
    label_counts["ProcessPlant"] = len(plants)

    assert plan.expected_node_labels == label_counts

    relationship_counts: dict[str, int] = {}
    relationship_counts[schema.Relation.HAS_SHEET.value] = len(sheets)
    relationship_counts[schema.Relation.IS_DRAWN_ON.value] = sum(
        sheet.graph.number_of_nodes() for sheet in sheets
    )
    for sheet in sheets:
        for _source, _target, attrs in sheet.graph.edges(data=True):
            relation = attrs["relation"]
            relationship_counts[relation] = relationship_counts.get(relation, 0) + 1
    if resolution.connector_pairs:
        relationship_counts[schema.Relation.CONTINUES_AS.value] = len(resolution.connector_pairs)
    same_tagged = sum(len(group.references) for group in resolution.identity_groups)
    if same_tagged:
        relationship_counts[schema.Relation.SAME_TAGGED_ITEM_AS.value] = same_tagged
    relationship_counts[schema.Relation.IS_LOCATED_IN.value] = _occurrences_with_unit(sheets) + len(
        _units_in_plants(sheets)
    )

    assert plan.expected_relationship_types == relationship_counts


def test_batches_split_at_batch_size() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution, batch_size=1)

    for statement in [*plan.node_statements, *plan.relationship_statements]:
        assert len(statement.parameters["rows"]) == 1

    # batch_size=1 means one statement per row: the statement count is the row count
    assert len(plan.node_statements) == len(_expected_node_uids(_CORPUS_ID, sheets))
    assert len(plan.relationship_statements) == _expected_relationship_count(sheets, resolution)


# --- wipe statement, schema statements, and the no-interpolation rule ----------------------


def test_wipe_statement_is_scoped_to_one_corpus_and_fully_parametrized() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    assert "corpus_id: $corpus_id" in plan.wipe_statement.query
    assert plan.wipe_statement.parameters["corpus_id"] == _CORPUS_ID
    assert "MATCH (n) DETACH DELETE n" not in plan.wipe_statement.query
    assert _CORPUS_ID not in plan.wipe_statement.query


def test_no_statement_text_ever_carries_an_interpolated_value() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    every_query = [
        statement.query
        for statement in (
            *plan.schema_statements,
            plan.wipe_statement,
            *plan.node_statements,
            *plan.relationship_statements,
        )
    ]
    for query in every_query:
        assert _CORPUS_ID not in query, "corpus_id must travel only through $-parameters"


def test_schema_statements_only_touch_corpus_node() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)
    for statement in plan.schema_statements:
        assert "CorpusNode" in statement.query
        assert statement.parameters == {}


# --- the closed label whitelist: a hostile GenericItem label is rejected -------------------


def _resolution_with_no_links() -> Resolution:
    report = ResolutionReport(
        n_sheets=1,
        n_occurrences=1,
        n_connectors=0,
        pairs_by_rule={},
        unresolved_by_reason={},
        n_identity_groups=0,
        ambiguous_tag_keys=0,
        edge_attribute_conflicts=0,
    )
    return Resolution(
        plant=nx.DiGraph(), connector_pairs=[], identity_groups=[], unresolved=[], report=report
    )


@pytest.mark.parametrize("hostile_label", ["Foo`bar", "Foo}bar", "lowercase", "Trailing Space"])
def test_a_hostile_generic_item_label_is_rejected(hostile_label: str) -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("occ1", node_class="GenericItem", dexpi_labels=[hostile_label])
    sheet = SheetGraph(sheet_id="0", graph=graph)

    with pytest.raises(ValueError, match="unsafe GenericItem label"):
        build_load_plan(_CORPUS_ID, [sheet], _resolution_with_no_links())


def test_a_well_formed_generic_item_label_is_accepted() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("occ1", node_class="GenericItem", dexpi_labels=["ReciprocatingPump", "Pump"])
    sheet = SheetGraph(sheet_id="0", graph=graph)

    plan = build_load_plan(_CORPUS_ID, [sheet], _resolution_with_no_links())

    occurrence_labels = [
        _labels_of(statement.query)
        for statement in plan.node_statements
        if "GenericItem" in statement.query
    ]
    assert occurrence_labels == [("CorpusNode", "ReciprocatingPump", "Pump", "GenericItem")]


# --- input validation: no silent failures ---------------------------------------------------


def test_an_unsafe_corpus_id_is_rejected() -> None:
    sheets, resolution = _small_corpus()
    with pytest.raises(ValueError, match="corpus_id"):
        build_load_plan("has a space", sheets, resolution)


def test_a_non_positive_batch_size_is_rejected() -> None:
    sheets, resolution = _small_corpus()
    with pytest.raises(ValueError, match="batch_size"):
        build_load_plan(_CORPUS_ID, sheets, resolution, batch_size=0)


def test_non_localized_sheets_are_rejected_by_the_resolver_boundary_contract() -> None:
    """`build_load_plan` must never write a leaked property to Neo4j (design §4.2 D1-a)."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("occ1", node_class="CentrifugalPump", tag="P-1", stream_kind="process")
    sheet = SheetGraph(sheet_id="0", graph=graph)

    with pytest.raises(ValueError, match="hidden properties"):
        build_load_plan(_CORPUS_ID, [sheet], _resolution_with_no_links())
