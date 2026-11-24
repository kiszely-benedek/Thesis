"""The B store view: visible keys, the schema text, the primer and the item graph (design 3)."""

from __future__ import annotations

from plants_b import real_corpus

from plantgraph.graph.schema import VISIBLE_NODE_PROPERTIES
from plantgraph.qa.graph_view import ItemRecord, NetworkxGraphView
from plantgraph.qa.plant_api.item_graph import build_item_graph
from plantgraph.qa.primer import fill_primer_slot, primer_block
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.qa.v2tb.item_graph_b import build_item_graph_b
from plantgraph.qa.v2tb.primer_b import POSITION_PRIMER, fill_primer_slot_b, primer_block_b
from plantgraph.qa.v2tb.schema_text_b import (
    POSITION_PARAGRAPH,
    build_schema_text_b,
    plan_holds_positions,
)
from plantgraph.qa.v2tb.visible import (
    ITEM_PROPERTY_KEYS_B,
    OPERATING_POSITION,
    VISIBLE_NODE_PROPERTIES_B,
)
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan


def _plan(*, with_positions: bool) -> LoadPlan:
    built = real_corpus()
    plan = build_load_plan("tb", built.localized_sheets, built.resolution, profile="plant")
    if with_positions:
        _add_positions(plan)
    return plan


def _add_positions(plan: LoadPlan) -> None:
    """What a B ingest would write: a position on every valve row."""
    for statement in plan.node_statements:
        for row in statement.parameters["rows"]:  # type: ignore[attr-defined]
            if "Valve" in str(row["props"].get("node_class", "")):
                row["props"][OPERATING_POSITION] = "NC"


# ---- visible keys -------------------------------------------------------------------------------


def test_b_sees_one_property_more_than_a() -> None:
    assert VISIBLE_NODE_PROPERTIES_B == VISIBLE_NODE_PROPERTIES | {OPERATING_POSITION}
    assert OPERATING_POSITION not in VISIBLE_NODE_PROPERTIES  # the frozen set is untouched
    assert ITEM_PROPERTY_KEYS_B == VISIBLE_NODE_PROPERTIES_B - {"node_class"}


# ---- schema text --------------------------------------------------------------------------------


def test_an_a_corpus_gets_exactly_the_a_schema_text() -> None:
    plan = _plan(with_positions=False)
    assert not plan_holds_positions(plan)
    assert build_schema_text_b(plan) == build_schema_text(plan)


def test_a_b_corpus_gets_the_property_and_the_paragraph() -> None:
    plan = _plan(with_positions=True)
    assert plan_holds_positions(plan)
    text = build_schema_text_b(plan)
    assert text.startswith(build_schema_text(plan).split("\nItem properties")[0])
    properties = next(line for line in text.split("\n") if line.startswith("Item properties"))
    names = properties.split(": ", 1)[1].split(", ")
    assert OPERATING_POSITION in names
    assert names == sorted(names)
    assert text.endswith(POSITION_PARAGRAPH)
    assert text.count(OPERATING_POSITION) == 2  # the property list and the paragraph


# ---- primer -------------------------------------------------------------------------------------

_TEMPLATE = "intro\n\n<<PRIMER>>\n\nrest"


def test_the_b_primer_is_a_s_plus_one_paragraph() -> None:
    assert primer_block_b() == f"{primer_block()}\n{POSITION_PRIMER}"
    assert fill_primer_slot_b(_TEMPLATE, primer=True).count(POSITION_PRIMER) == 1


def test_with_the_primer_off_both_templates_are_the_same() -> None:
    assert fill_primer_slot_b(_TEMPLATE, primer=False) == fill_primer_slot(_TEMPLATE, primer=False)


# ---- item graph ---------------------------------------------------------------------------------


class _PositionedView:
    """The corpus view, with `operating_position` added to every valve occurrence (as B's would)."""

    def __init__(self, inner: NetworkxGraphView) -> None:
        self._inner = inner

    def items(self) -> list[ItemRecord]:
        return [self._with_position(item) for item in self._inner.items()]

    def edges(self) -> object:
        return self._inner.edges()

    @staticmethod
    def _with_position(item: ItemRecord) -> ItemRecord:
        if "Valve" not in item.node_class:
            return item
        return item.model_copy(update={"properties": {**item.properties, OPERATING_POSITION: "NC"}})


def _view() -> NetworkxGraphView:
    built = real_corpus()
    return NetworkxGraphView("tb", built.localized_sheets, built.resolution)


def test_without_positions_the_b_item_graph_equals_the_frozen_one() -> None:
    view = _view()
    frozen = build_item_graph(view, line_view=True)
    mine = build_item_graph_b(view, line_view=True)
    assert [mine.item(i) for i in mine.all_ids()] == [frozen.item(i) for i in frozen.all_ids()]
    assert mine.edges == frozen.edges


def test_valves_keep_their_position_in_the_b_item_graph() -> None:
    view = _PositionedView(_view())
    graph = build_item_graph_b(view, line_view=True)  # type: ignore[arg-type]
    valves = [graph.item(i) for i in graph.all_ids() if "Valve" in graph.item(i).node_class]
    assert valves and all(v.properties[OPERATING_POSITION] == "NC" for v in valves)
    frozen = build_item_graph(view, line_view=True)  # type: ignore[arg-type]
    assert all(OPERATING_POSITION not in frozen.item(i).properties for i in frozen.all_ids())
