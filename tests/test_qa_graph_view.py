"""`NetworkxGraphView` against `build_load_plan`: same content, no gold key (QA-T3, `qa-system.md`).

The comparison mirrors `test_neo4j_plan.py`'s own cross-checks, but from the
opposite side: those tests recompute `LoadPlan.expected_*` independently of
`neo4j_rows.py`; these recompute them independently of `graph_view.py`, so
neither module's own arithmetic is trusted twice.
"""

from __future__ import annotations

from collections import Counter
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
from plantgraph.qa.graph_view import ItemRecord, NetworkxGraphView
from plantgraph.qa.serialize import serialize_occurrence_graph
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution, ResolutionReport
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"
_CORPUS_ID = "acme-plant-01"


def _four_unit_corpus(duplication_rate: float) -> tuple[list[SheetGraph], Resolution]:
    """A 4-unit generated plant (`GeneratorConfig`'s default `n_units`), split into sheets."""
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=duplication_rate)
    sheets, _manifest = split(builder.graph, split_config)
    localized, _occurrence_map = localize(sheets)
    return localized, resolve(localized)


def _ex01_corpus() -> tuple[list[SheetGraph], Resolution]:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    imported = import_proteus_sheet(_EX01_PATH)
    localized, _occurrence_map = localize([imported.sheet])
    return localized, resolve(localized)


def _empty_resolution() -> Resolution:
    report = ResolutionReport(
        n_sheets=0,
        n_occurrences=0,
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


def _class_chain(item: ItemRecord) -> tuple[str, ...]:
    """The label chain `neo4j_rows._occurrence_labels` would give this item, minus `CorpusNode`."""
    if item.node_class == schema.NodeClass.GENERIC_ITEM.value:
        dexpi_labels = item.properties["dexpi_labels"]
        assert isinstance(dexpi_labels, list)
        return (*dexpi_labels, "GenericItem")
    return schema.labels_for(item.node_class)


def _occurrence_label_counts(items: list[ItemRecord]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        counts.update(_class_chain(item))
    return dict(counts)


def _plan_occurrence_label_counts(plan: LoadPlan) -> dict[str, int]:
    """`plan.expected_node_labels`, with the structural bookkeeping labels removed.

    Those three labels (`CorpusNode`, `Sheet`, `DrawingSet`) count the
    corpus marker and the per-sheet nodes the store adds — `NetworkxGraphView`
    never materializes either as a node (§5: `sheet_id` is an attribute
    instead), so they are not part of what this comparison checks.
    """
    return {
        label: count
        for label, count in plan.expected_node_labels.items()
        if label not in ("CorpusNode", "Sheet", "DrawingSet")
    }


def _plan_topology_relationship_counts(plan: LoadPlan) -> dict[str, int]:
    """`plan.expected_relationship_types`, with the two structural relations removed.

    `has_sheet` and `is_drawn_on` describe edges to a `Sheet` node that this
    view never creates; the acceptance check (`qa-system.md` §18 QA-T3)
    compares those two counts separately, "from the sheet attribute".
    """
    return {
        relation: count
        for relation, count in plan.expected_relationship_types.items()
        if relation not in (schema.Relation.HAS_SHEET.value, schema.Relation.IS_DRAWN_ON.value)
    }


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_node_label_counts_match_the_load_plan(duplication_rate: float) -> None:
    sheets, resolution = _four_unit_corpus(duplication_rate)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    assert _occurrence_label_counts(view.items()) == _plan_occurrence_label_counts(plan)


@pytest.mark.parametrize("duplication_rate", [0.0, 0.5])
def test_relationship_counts_match_the_load_plan(duplication_rate: float) -> None:
    sheets, resolution = _four_unit_corpus(duplication_rate)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    topology_counts = dict(Counter(edge.relation for edge in view.edges()))
    assert topology_counts == _plan_topology_relationship_counts(plan)

    # is_drawn_on/has_sheet are folded into the sheet_id attribute, not modelled as
    # edges here — recomputed straight from what the view does model (§18 QA-T3).
    assert len(view.items()) == plan.expected_relationship_types[schema.Relation.IS_DRAWN_ON.value]
    assert len(view.sheets()) == plan.expected_relationship_types[schema.Relation.HAS_SHEET.value]


def test_serialized_text_carries_no_bookkeeping_label() -> None:
    sheets, resolution = _four_unit_corpus(0.5)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)
    serialized = serialize_occurrence_graph(view)

    for forbidden in ("CorpusNode", 'attr.name="uid"', 'attr.name="corpus_id"'):
        assert forbidden not in serialized.text


# --- sheet_neighbours: symmetric, and matches the resolver's own pairs --------------------


def test_sheet_neighbours_is_symmetric_and_matches_continues_as_pairs() -> None:
    sheets, resolution = _four_unit_corpus(0.0)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)
    assert resolution.connector_pairs, "fixture must actually exercise a cross-sheet link"

    for pair in resolution.connector_pairs:
        sheet_a, _, _ = pair.from_key.partition(":")
        sheet_b, _, _ = pair.to_key.partition(":")
        assert sheet_b in view.sheet_neighbours(sheet_a)
        assert sheet_a in view.sheet_neighbours(sheet_b)


# --- find_by_tag: excludes connectors, matches piping_component_name too ------------------


def test_find_by_tag_excludes_off_page_connectors() -> None:
    sheets, resolution = _four_unit_corpus(0.0)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)

    connector_tag = next(
        item.properties["connector_number"]
        for item in view.items()
        if item.node_class in schema.CONNECTOR_CLASSES
    )
    assert view.find_by_tag(connector_tag) == []


def test_find_by_tag_is_case_and_whitespace_insensitive() -> None:
    sheets, resolution = _four_unit_corpus(0.0)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)
    known_tag = next(item.tag for item in view.items() if item.tag is not None)

    assert view.find_by_tag(known_tag) == view.find_by_tag(f"  {known_tag.lower()}  ")


def test_find_by_tag_matches_ex01_valve_by_piping_component_name() -> None:
    sheets, resolution = _ex01_corpus()
    view = NetworkxGraphView("ex01", sheets, resolution)

    matches = view.find_by_tag("66KL21")

    assert len(matches) == 1
    assert matches[0].piping_component_name == "66KL21"
    assert matches[0].properties["dexpi_class"] == "ButterflyValve"


def test_ex01_serializes_with_no_bookkeeping_label() -> None:
    sheets, resolution = _ex01_corpus()
    view = NetworkxGraphView("ex01", sheets, resolution)
    serialized = serialize_occurrence_graph(view)

    for forbidden in ("CorpusNode", 'attr.name="uid"', 'attr.name="corpus_id"'):
        assert forbidden not in serialized.text


def test_sheets_of_unit_and_unit_ids_agree_with_occurrence_properties() -> None:
    sheets, resolution = _four_unit_corpus(0.0)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)

    for unit_id in view.unit_ids():
        expected_sheets = {item.sheet_id for item in view.items() if item.unit_id == unit_id}
        assert set(view.sheets_of_unit(unit_id)) == expected_sheets


def test_run_cypher_is_not_implemented_on_the_networkx_view() -> None:
    sheets, resolution = _four_unit_corpus(0.0)
    view = NetworkxGraphView(_CORPUS_ID, sheets, resolution)
    with pytest.raises(NotImplementedError):
        view.run_cypher("MATCH (n) RETURN n", timeout_s=1.0, row_cap=10)


def test_view_rejects_sheets_that_were_never_localized() -> None:
    """The resolver-boundary contract still applies here (`kg-construction.md` §5.7)."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("occ1", node_class="CentrifugalPump", tag="P-1", stream_kind="process")
    sheet = SheetGraph(sheet_id="0", graph=graph)

    with pytest.raises(ValueError, match="hidden properties"):
        NetworkxGraphView(_CORPUS_ID, [sheet], _empty_resolution())
