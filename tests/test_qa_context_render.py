"""Plant and occurrence renderers, their legends and byte-identity of the old prompts (PG-T2)."""

from __future__ import annotations

import hashlib
import io
from typing import Any

import networkx as nx
import pytest

from plantgraph.qa.context_render import (
    OccurrenceRenderer,
    PlantRenderer,
    legend_text,
)
from plantgraph.qa.harness.registry import build_strategy
from plantgraph.qa.need.rules import RuleNeedClassifier
from plantgraph.qa.plant_api.item_graph import build_item_graph
from plantgraph.qa.serialize import serialize_graph
from plantgraph.qa.strategies.context_rag import ContextRag
from qa_hierarchical_toy import chain_toy, strategy
from qa_need_toy import ISOLATION_QUESTION, PATH_QUESTION, need_strategy, need_toy
from qa_routing_toy import ToyCorpus, key

_NO_THROUGH: dict[str, tuple[str, ...]] = {}
_UPSTREAM = "Is TA upstream of TE?"


def _tank_toy() -> ToyCorpus:
    """The T-11-1 shape: tank `T-1` on A whose two outgoing pipes both leave for sheet B."""
    toy = ToyCorpus()
    toy.item("A", "t", "T-1")
    toy.item("B", "c1", "CHV-1")
    toy.item("B", "c2", "CHV-2")
    toy.cut("A", "t", "B", "c1", "k1")
    toy.cut("A", "t", "B", "c2", "k2")
    return toy


def _plant(toy: ToyCorpus) -> PlantRenderer:
    return PlantRenderer(build_item_graph(toy.view()))


def _parse(text: str) -> nx.DiGraph[str]:
    """Read the GraphML of a rendered text, after its legend paragraph."""
    xml = text[text.index("<graphml") :]
    return nx.read_graphml(io.BytesIO(xml.encode("utf-8")))  # type: ignore[no-any-return]


def _tags(graph: nx.DiGraph[str]) -> set[str]:
    return {attrs["tag"] for _, attrs in graph.nodes(data=True) if "tag" in attrs}


def _edge_tags(graph: nx.DiGraph[str]) -> set[tuple[str, str, str]]:
    tag = nx.get_node_attributes(graph, "tag")
    return {(tag[s], tag[t], a["relation"]) for s, t, a in graph.edges(data=True)}


def test_a_tank_whose_outgoing_pipes_are_both_cut_has_two_direct_edges() -> None:
    rendered = _plant(_tank_toy()).render(frozenset({"A"}), _NO_THROUGH)
    graph = _parse(rendered.text)

    assert _edge_tags(graph) == {("T-1", "CHV-1", "send_to"), ("T-1", "CHV-2", "send_to")}
    assert {a["crossed_sheets"] for *_, a in graph.edges(data=True)} == {"A to B"}


def test_paired_stubs_vanish_but_an_unpaired_one_stays_as_an_item() -> None:
    toy = _tank_toy()
    toy.dangling_stub("A", "t", "lost")
    graph = _parse(_plant(toy).render(frozenset({"A"}), _NO_THROUGH).text)

    classes = [a["node_class"] for _, a in graph.nodes(data=True)]
    stubs = [c for c in classes if "OffPageConnector" in c]
    assert stubs == ["UnresolvedOffPageConnector"]


def test_frontier_items_are_written_with_only_their_boundary_edge() -> None:
    rendered = _plant(need_toy()).render(frozenset({"S1"}), _NO_THROUGH)
    graph = _parse(rendered.text)

    assert "P-2" in _tags(graph) and "P-3" not in _tags(graph)
    assert rendered.frontier_items == 1
    assert [e for e in _edge_tags(graph) if "P-2" in e[:2]] == [("XV-1", "P-2", "send_to")]


def test_a_frontier_item_adds_its_sheets_to_the_context_sheets() -> None:
    rendered = _plant(need_toy()).render(frozenset({"S1"}), _NO_THROUGH)

    assert rendered.sheets == ("S1",)
    assert rendered.context_sheets == ("S1", "S2")


def test_a_repeated_drawing_is_one_node_listing_both_sheets() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "R-1")
    toy.item("S2", "r", "R-1")
    toy.identity("R-1", ("S1", "a"), [("S2", "r")])
    rendered = _plant(toy).render(frozenset({"S2"}), _NO_THROUGH)
    graph = _parse(rendered.text)

    assert [a["sheets"] for _, a in graph.nodes(data=True)] == ["S1|S2"]
    assert rendered.keys == (key("S1", "a"), key("S2", "r"))


def test_through_line_keys_select_only_their_items() -> None:
    through = {"B": (key("B", "c1"),)}
    rendered = _plant(_tank_toy()).render(frozenset(), through)
    graph = _parse(rendered.text)

    assert rendered.through_line_sheets == ("B",)
    assert _tags(graph) == {"CHV-1", "T-1"}  # CHV-1 selected, the tank is its frontier
    assert rendered.items == 2 and rendered.frontier_items == 1


def test_the_plant_text_is_deterministic_and_starts_with_its_legend() -> None:
    renderer = _plant(_tank_toy())
    first = renderer.render(frozenset({"A"}), _NO_THROUGH)

    assert first == renderer.render(frozenset({"A"}), _NO_THROUGH)
    assert first.text.startswith(legend_text("plant") + "\n\n<graphml")


def test_the_occurrence_renderer_adds_a_legend_only_when_asked() -> None:
    view = _tank_toy().view()
    plain = OccurrenceRenderer(view).render(frozenset({"A"}), _NO_THROUGH)
    legend = OccurrenceRenderer(view, legend=True).render(frozenset({"A"}), _NO_THROUGH)

    assert plain.text == serialize_graph(view.subgraph(["A"])).text
    assert legend.text == f"{legend_text('occurrence')}\n\n{plain.text}"
    assert (plain.items, plain.frontier_items) == (0, 0)


# --- paired strategies: the selection is the same, the representation is not ---------------


def _params(**extra: Any) -> dict[str, Any]:
    return {
        "route_mode": "flow_path",
        "budget_mode": "through_line",
        "sheet_hops": 0,
        "max_context_chars": 10**9,
        **extra,
    }


@pytest.mark.parametrize(
    ("occurrence", "plant"),
    [
        ("hierarchical", "hierarchical_plant"),
        ("hierarchical_need_rules", "hierarchical_need_rules_plant"),
    ],
)
def test_paired_names_select_the_same_sheets_and_the_plant_keeps_every_item(
    occurrence: str, plant: str
) -> None:
    view = chain_toy().view()
    graph = build_item_graph(view)
    a = build_strategy(occurrence, _params(), view).retrieve(_UPSTREAM)
    b = build_strategy(plant, _params(), view).retrieve(_UPSTREAM)

    for field in ("routed_sheets", "through_line_sheets"):
        assert a.trace[field] == b.trace[field]
    assert (a.trace["representation"], b.trace["representation"]) == ("occurrence", "plant")
    seen = {graph.item_of_key(k) for k in a.trace["serialized_keys"]} - {None}
    assert seen <= {graph.item_of_key(k) for k in b.trace["serialized_keys"]}
    assert b.trace["serialized_items"] > 0 and b.trace["context_sheets"]


def test_a_cross_sheet_question_is_smaller_on_the_plant() -> None:
    view = chain_toy(junk_per_sheet=0).view()
    a = build_strategy("hierarchical", _params(), view).retrieve(_UPSTREAM)
    b = build_strategy("hierarchical_plant", _params(), view).retrieve(_UPSTREAM)

    assert a.context is not None and b.context is not None
    assert len(b.context) < len(a.context)


def test_the_plant_need_strategy_runs_its_program_and_falls_back_to_the_plant() -> None:
    view = need_toy().view()
    plant_strategy = build_strategy("hierarchical_need_rules_plant", _params(), view)

    used = plant_strategy.retrieve(ISOLATION_QUESTION)
    generic = plant_strategy.retrieve("What is P-1?")

    assert plant_strategy.name == "hierarchical_need_rules_plant"
    assert used.trace["need_used"] is True and used.trace["representation"] == "plant"
    assert used.context is not None and "OffPageConnector" not in used.context
    assert generic.trace["need_used"] is False
    assert generic.trace["representation"] == "plant"


def test_a_tight_budget_cuts_plant_need_items_like_occurrence_ones() -> None:
    view = need_toy().view()
    wide = build_strategy("hierarchical_need_rules_plant", _params(), view)
    tight = build_strategy("hierarchical_need_rules_plant", _params(max_context_chars=2000), view)
    full = wide.retrieve(PATH_QUESTION).trace
    cut = tight.retrieve(PATH_QUESTION).trace

    assert full["need_items_dropped"] == 0
    assert cut["need_items_dropped"] > 0  # a dropped item may stay on as a frontier item


# --- registry -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["hierarchical_plant", "hierarchical_need_rules_plant"])
def test_plant_arms_have_no_defaults_and_no_legend_switch(name: str) -> None:
    view = need_toy().view()
    with pytest.raises(ValueError, match="max_context_chars"):
        build_strategy(name, {"route_mode": "flow_path"}, view)
    with pytest.raises(ValueError, match="always on"):
        build_strategy(name, _params(legend=False), view)


def test_the_occurrence_legend_switch_must_be_a_boolean() -> None:
    with pytest.raises(ValueError, match="legend"):
        build_strategy("hierarchical", _params(legend="yes"), need_toy().view())


def test_an_occurrence_arm_with_legend_true_prepends_the_occurrence_legend() -> None:
    view = chain_toy().view()
    plain = build_strategy("hierarchical", _params(), view).retrieve(_UPSTREAM)
    legend = build_strategy("hierarchical", _params(legend=True), view).retrieve(_UPSTREAM)

    assert legend.context == f"{legend_text('occurrence')}\n\n{plain.context}"


def test_an_unknown_name_lists_the_registered_ones() -> None:
    with pytest.raises(ValueError, match="hierarchical_need_rules_plant"):
        build_strategy("hierarchical_nope", _params(), need_toy().view())


# --- byte identity of the existing occurrence prompts ---------------------------------------


def _digest(text: str | None) -> str:
    assert text is not None
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def test_default_occurrence_contexts_are_byte_identical_to_commit_f272b20() -> None:
    """Golden digests taken from the code before the renderer existed (the legend is off)."""
    full = strategy(chain_toy()).retrieve(_UPSTREAM)
    cut = strategy(chain_toy(), budget_mode="through_line", max_context_chars=3000).retrieve(
        _UPSTREAM
    )
    rules = RuleNeedClassifier()
    isolation = need_strategy(need_toy(), rules).retrieve(ISOLATION_QUESTION)
    path = need_strategy(need_toy(), rules).retrieve(PATH_QUESTION)
    path_cut = need_strategy(need_toy(), rules, max_context_chars=3500).retrieve(PATH_QUESTION)
    whole = ContextRag(need_toy().view()).retrieve("anything")

    assert [_digest(r.context) for r in (full, cut, isolation, path, path_cut, whole)] == [
        "f3d82cb7440c9498",
        "0cec59644d7b3ee9",
        "19c681914a19aced",
        "2f0d6a0fcaea498c",
        "308bfffc76340545",
        "fdf0107e11ec5d48",
    ]
