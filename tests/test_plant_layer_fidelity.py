"""PLANT-01 and the plant-layer readback, on a toy corpus replayed through a fake source.

One injected row error must make the checks fail; a faithful replay must pass.
"""

from __future__ import annotations

import pytest

from plant_layer_toy import CORPUS, ReplaySource, Toy
from plantgraph.qa.harness.plant_layer_fidelity import render_report
from plantgraph.store import plant_readback as rb


@pytest.fixture(scope="module", params=[0.0, 0.5])
def toy(request: pytest.FixtureRequest) -> Toy:
    return Toy(request.param)


def test_a_faithful_layer_passes_all_five_parts(toy: Toy) -> None:
    result = toy.check(toy.source())

    assert result.n_items > 50 and result.n_edges > 50
    assert result.a_differences == ()
    assert (result.b_edges.precision, result.b_edges.recall) == (1.0, 1.0)
    assert (result.c_sheets.share, result.d_units.share) == (1.0, 1.0)
    assert result.e_item_graph.differences == ()
    assert result.passed
    assert "PASS" in render_report(result)


def test_the_readback_keys_items_by_home_key_and_keeps_untagged_ones(toy: Toy) -> None:
    layer = rb.read_plant_layer(toy.source(), CORPUS)

    assert set(layer.graph.nodes) == set(toy.item_graph().all_ids())
    assert all(rb.schema.PLANT_ITEM_LABEL in labels for labels in layer.labels.values())
    assert any(layer.graph.nodes[k].get("tag") is None for k in layer.graph.nodes)


def test_a_dropped_edge_row_fails_a_b_and_e() -> None:
    toy = Toy(0.5)
    source = toy.source()
    edge = next(
        r for r in source.relationships if r.rel_type == "send_to" and "crossed_sheets" in r.props
    )
    source.relationships.remove(edge)

    result = toy.check(source)

    assert result.a_differences and result.b_edges.recall < 1.0
    assert result.e_item_graph.differences and not result.passed


def test_a_wrong_sheet_row_fails_c_and_e_but_not_a() -> None:
    toy = Toy(0.0)
    source = toy.source()
    index = next(i for i, r in enumerate(source.relationships) if r.rel_type == "is_drawn_on")
    old = source.relationships[index]
    wrong = old._replace(target_uid=f"{CORPUS}|S9999")
    source.relationships[index] = wrong

    result = toy.check(source)

    assert result.a_differences == ()
    assert result.c_sheets.share < 1.0 and result.e_item_graph.differences


def test_a_wrong_property_fails_only_a() -> None:
    toy = Toy(0.0)
    source = toy.source()
    index = next(i for i, n in enumerate(source.nodes) if n.props.get("tag"))
    node = source.nodes[index]
    source.nodes[index] = node._replace(props={**node.props, "tag": "WRONG"})

    result = toy.check(source)

    assert result.a_differences and result.e_item_graph.differences == ()


def test_a_uid_of_another_corpus_is_refused() -> None:
    toy = Toy(0.0)
    source = toy.source()
    source.nodes[0] = source.nodes[0]._replace(uid="other|item:S1:x")

    with pytest.raises(ValueError, match="plant item uid"):
        rb.read_plant_layer(source, CORPUS)


def test_two_relationships_between_one_pair_are_refused() -> None:
    toy = Toy(0.0)
    source = toy.source()
    edge = next(r for r in source.relationships if r.rel_type == "send_to")
    source.relationships.append(edge._replace(rel_type="control"))

    with pytest.raises(ValueError, match="expected one relationship"):
        rb.read_plant_layer(source, CORPUS)


def test_an_occurrence_only_store_reads_as_an_empty_layer_that_fails() -> None:
    toy = Toy(0.0)

    result = toy.check(ReplaySource([], []))

    assert result.n_items == 0 and not result.passed
