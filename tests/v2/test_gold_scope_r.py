"""Task T6, gold side of scope R (design 11): the untagged refusal and the FLOW_PATH tie rule.

The graphs are hand-built: a node has a `tag` only when it prints one, as on a v2.2 plant.
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.benchmark.v2.gold_scope_r import (
    SCOPE_R_UNAVAILABLE_FAMILIES,
    RefusedShare,
    holds_untagged_item,
    tagged_sequences_differ,
    untagged_refusal_share,
)
from plantgraph.qa.models import QuestionFamily


def _plant(
    nodes: dict[str, tuple[str, str | None]], pipes: list[tuple[str, str]]
) -> nx.DiGraph[str]:
    graph: nx.DiGraph[str] = nx.DiGraph()
    for node, (node_class, tag) in nodes.items():
        graph.add_node(node, node_class=node_class, **({"tag": tag} if tag else {}))
    graph.add_edges_from(pipes, relation="send_to")
    return graph


#: two routes from the pump to the tank: through gate valve `a` or through gate valve `b`
def _diamond(tag_a: str | None, tag_b: str | None) -> nx.DiGraph[str]:
    nodes = {
        "p": ("CentrifugalPump", "P-101"),
        "t1": ("PipeTee", None),
        "a": ("GateValve", tag_a),
        "b": ("GateValve", tag_b),
        "t2": ("PipeTee", None),
        "k": ("Tank", "TK-101"),
    }
    pipes = [("p", "t1"), ("t1", "a"), ("t1", "b"), ("a", "t2"), ("b", "t2"), ("t2", "k")]
    return _plant(nodes, pipes)


def test_the_isolation_families_are_pre_registered_unavailable() -> None:
    assert set(SCOPE_R_UNAVAILABLE_FAMILIES) == {
        QuestionFamily.UPSTREAM_ISOLATION,
        QuestionFamily.DOWNSTREAM_ISOLATION,
    }


def test_an_answer_that_holds_an_untagged_valve_is_refused() -> None:
    plant = _diamond("GTV-1", None)
    assert holds_untagged_item(plant, ["a", "b"])
    assert not holds_untagged_item(plant, ["a"])


def test_the_refused_share_counts_candidates_and_handles_none() -> None:
    plant = _diamond("GTV-1", None)
    share = untagged_refusal_share(plant, [["a"], ["b"], ["a", "b"], ["p"]])
    assert (share.candidates, share.refused, share.share) == (4, 2, 0.5)
    assert RefusedShare(rule="x", candidates=0, refused=0).share == 0.0


def test_two_routes_with_different_tags_are_a_tie_to_refuse() -> None:
    assert tagged_sequences_differ(_diamond("GTV-1", "GTV-2"), "p", "k")


def test_two_routes_with_the_same_listing_are_not() -> None:
    # both valves untagged: they drop out of the listing, so the two routes list the same items
    assert not tagged_sequences_differ(_diamond(None, None), "p", "k")


def test_a_tagged_and_an_untagged_route_list_different_items() -> None:
    assert tagged_sequences_differ(_diamond("GTV-1", None), "p", "k")


def test_a_single_route_is_never_a_tie() -> None:
    plant = _plant(
        {"p": ("CentrifugalPump", "P-1"), "v": ("GateValve", None), "k": ("Tank", "TK-1")},
        [("p", "v"), ("v", "k")],
    )
    assert not tagged_sequences_differ(plant, "p", "k")


def test_only_shortest_routes_count() -> None:
    plant = _diamond("GTV-1", "GTV-2")
    plant.add_node("long", node_class="GateValve", tag="GTV-9")
    plant.add_edges_from([("t1", "long"), ("long", "a")], relation="send_to")
    assert tagged_sequences_differ(plant, "p", "k")  # a and b still differ
    plant = _diamond("GTV-1", None)
    plant.remove_edge("t1", "b")
    plant.add_edge("t1", "a", relation="send_to")
    assert not tagged_sequences_differ(plant, "p", "k")  # the only shortest route runs through a


def test_an_unreachable_target_raises() -> None:
    with pytest.raises(ValueError, match="reachable"):
        tagged_sequences_differ(_diamond("GTV-1", "GTV-2"), "k", "p")
