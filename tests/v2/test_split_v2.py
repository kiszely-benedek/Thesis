"""The v2 splitter strategy end to end: sheets, connectors, identity groups, the gates, S20."""

from __future__ import annotations

import random

import networkx as nx
import pytest
from corpus_v2 import corpus

from plantgraph.benchmark.models import ConnectorKind
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.v2.split_by_sheet_group import by_sheet_group
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.ingest.pipeline import _check_gate

_MACHINE = NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value


def _two_node_plant(
    relation: Relation, source_class: str, groups: tuple[str, str], units: tuple[str, str]
) -> nx.DiGraph[str]:
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class=source_class, sheet_group=groups[0], unit_id=units[0])
    plant.add_node("b", node_class="CentrifugalPump", sheet_group=groups[1], unit_id=units[1])
    plant.add_edge("a", "b", relation=relation.value)
    return plant


def _run(plant: nx.DiGraph[str]) -> dict[str, str]:
    return by_sheet_group(plant, SplitConfig(), random.Random(0))


def test_a_motor_control_edge_that_crosses_sheets_is_refused_as_s20() -> None:
    plant = _two_node_plant(Relation.CONTROL, _MACHINE, ("1:1", "1:2"), ("1", "1"))
    with pytest.raises(ValueError, match="'control' edge 'a' -> 'b'.*S20"):
        _run(plant)


def test_a_has_agitator_edge_that_crosses_sheets_is_refused_as_s20() -> None:
    plant = _two_node_plant(Relation.HAS_AGITATOR, "Tank", ("1:1", "1:2"), ("1", "1"))
    with pytest.raises(ValueError, match="'has_agitator' edge.*S20"):
        _run(plant)


def test_a_control_valve_signal_may_cross_sheets_because_only_motor_wiring_is_protected() -> None:
    plant = _two_node_plant(Relation.CONTROL, "ActuatingFunction", ("1:1", "1:2"), ("1", "1"))
    assert _run(plant) == {"a": "0", "b": "1"}


def test_the_same_motor_edge_inside_one_sheet_is_fine() -> None:
    plant = _two_node_plant(Relation.CONTROL, _MACHINE, ("1:1", "1:1"), ("1", "1"))
    assert set(_run(plant).values()) == {"0"}


def test_a_sheet_that_mixes_two_units_is_refused() -> None:
    plant = _two_node_plant(Relation.SEND_TO, "Tank", ("1:1", "1:1"), ("1", "2"))
    with pytest.raises(ValueError, match=r"one unit per sheet.*sheet 0.*\['1', '2'\]"):
        _run(plant)


def test_a_node_without_a_unit_does_not_count_as_a_second_unit() -> None:
    plant = _two_node_plant(Relation.SEND_TO, "Tank", ("1:1", "1:1"), ("1", "1"))
    del plant.nodes["b"]["unit_id"]
    assert set(_run(plant).values()) == {"0"}


def test_the_generated_plant_obeys_both_promises_at_30_sheets() -> None:
    plant = corpus().plant
    _run(plant)  # raises on a mixed-unit sheet or a cut S20 edge


def test_every_cut_edge_has_a_connector_pair_of_the_matching_kind() -> None:
    built = corpus()
    pairs = {pair.original_edge: pair for pair in built.manifest.connector_pairs}
    assert pairs, "expected a 30-sheet plant to need off-page connectors"
    for (source, target), pair in pairs.items():
        relation = built.plant.edges[source, target]["relation"]
        kind = ConnectorKind.PIPE if relation == Relation.SEND_TO.value else ConnectorKind.SIGNAL
        stubs = {c.key: c for c in built.manifest.off_page_connectors}
        assert stubs[pair.from_key].kind is kind and stubs[pair.to_key].kind is kind


def test_control_valve_signals_that_leave_a_sheet_get_signal_connectors_with_a_loop_tag() -> None:
    signal = [c for c in corpus().manifest.off_page_connectors if c.kind is ConnectorKind.SIGNAL]
    assert signal, "expected some control valve to sit on another sheet than its controller"
    assert all(c.loop_tag for c in signal)
    assert all(c.line_number is None for c in signal)  # a signal line has no line number


def test_identity_groups_exist_and_follow_the_rate_rule() -> None:
    built = corpus()
    groups = built.manifest.identity_groups
    assert groups
    assert all(group.tag_variants == {} for group in groups)  # exact tags (ADR-0028)
    assert all(
        group.home.split(":")[0] not in {r.split(":")[0] for r in group.references}
        for group in groups
    )


def test_gate_g1_holds_and_identity_and_connector_pairs_are_resolved_perfectly() -> None:
    built = corpus()
    equal, differences, score = _check_gate(
        built.plant, built.resolution, built.occurrence_map, built.manifest
    )
    assert equal, differences[:3]
    assert score.identity.precision == 1.0 and score.identity.recall == 1.0
    assert score.connector_pairs.precision == 1.0 and score.connector_pairs.recall == 1.0


def test_no_sheet_shows_two_units_after_the_split() -> None:
    for sheet in corpus().sheets:
        units = {a["unit_id"] for _, a in sheet.graph.nodes(data=True) if "unit_id" in a}
        assert len(units) <= 1, (sheet.sheet_id, units)


def test_the_split_is_deterministic_for_one_seed() -> None:
    from corpus_v2 import SEED

    from plantgraph.benchmark.splitter import split
    from plantgraph.ingest.headline_v2 import HeadlinePresetV2

    built = corpus()
    _, again = split(built.plant, HeadlinePresetV2().split_config(SEED))
    # `created_at` is the wall clock, the only field that may differ
    assert again.model_dump(exclude={"created_at"}) == built.manifest.model_dump(
        exclude={"created_at"}
    )
