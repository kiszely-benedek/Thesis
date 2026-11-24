"""R9: each new scope X text gets the need label of its registered twin, in both arms.

The frozen rules classifier is called, never changed. If a twin were routed differently, B and A2
would start the pair at different cascade tiers and SB2 would measure the router, not the content.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from plantgraph.qa.cascade.labels import anchor_finder, classify_need
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.questions.scope_x import SCOPE_X_ROUTING_TWIN
from plantgraph.qa.questions.templates import upstream_isolation_text
from plantgraph.qa.questions.templates_heldout import downstream_isolation_text
from plantgraph.qa.questions.templates_x import (
    open_valves_downstream_text,
    open_valves_upstream_text,
    position_of_described_valve_text,
    position_of_valve_text,
)
from qa_routing_toy import ToyCorpus

F = QuestionFamily
_TAG = "P-1"

#: new text, registered twin text (same tag)
_PAIRS = [
    (open_valves_upstream_text, upstream_isolation_text),
    (open_valves_downstream_text, downstream_isolation_text),
]


def _label(text: str) -> NeedLabel:
    toy = ToyCorpus()
    toy.item("S1", "a", _TAG, unit_id="1")
    toy.item("S1", "b", "GTV-1203", unit_id="1")  # the valve of the tag-form position text
    return classify_need(text, anchor_finder(toy.view()))


@pytest.mark.parametrize(("new_text", "twin_text"), _PAIRS, ids=["dev", "held-out"])
def test_a_new_template_gets_the_label_of_its_registered_twin(
    new_text: Callable[[str], str], twin_text: Callable[[str], str]
) -> None:
    assert _label(new_text(_TAG)) is _label(twin_text(_TAG))


def test_the_labels_are_the_ones_the_design_table_gives() -> None:
    assert _label(open_valves_upstream_text(_TAG)) is NeedLabel.UPSTREAM_TO_FIRST_VALVE  # tier 1
    assert _label(open_valves_downstream_text(_TAG)) is NeedLabel.DOWNSTREAM_ALL  # tier 0


def test_the_isolation_x_families_are_routed_like_the_registered_families() -> None:
    assert _label(upstream_isolation_text(_TAG)) is NeedLabel.UPSTREAM_TO_FIRST_VALVE
    assert _label(downstream_isolation_text(_TAG)) is NeedLabel.DOWNSTREAM_ALL


def test_every_twin_named_for_a_scope_x_family_is_a_registered_isolation_family() -> None:
    assert set(SCOPE_X_ROUTING_TWIN.values()) == {F.UPSTREAM_ISOLATION, F.DOWNSTREAM_ISOLATION}
    assert F.POSITION_OF_VALVE not in SCOPE_X_ROUTING_TWIN


@pytest.mark.parametrize("side", ["upstream", "downstream"])
def test_the_descriptor_position_text_is_routed_like_the_tag_text(side: str) -> None:
    descriptor_text = position_of_described_valve_text("GateValve", '6"-P-1203-A1A', side, _TAG)

    assert _label(descriptor_text) is _label(position_of_valve_text("GTV-1203"))
    assert _label(descriptor_text) is NeedLabel.GENERIC
