"""The rule classifier: every dev template maps to its gold label; masking and anchor counts."""

from __future__ import annotations

import pytest

from plantgraph.qa.anchors import extract_anchors, mask_anchors
from plantgraph.qa.harness.need_gold import gold_need_of_family
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.need.classifiers import NeedInput, build_need_input
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.need.rules import RuleNeedClassifier
from plantgraph.qa.questions import templates as t
from qa_routing_toy import ToyCorpus

F = QuestionFamily

#: One real question text per dev family, over tags `P-1`, `P-2` and units `1`, `2`.
_DEV_TEXTS: list[tuple[QuestionFamily, str]] = [
    (F.LOOKUP_TYPE, t.lookup_type_text("P-1")),
    (F.LOOKUP_UNIT, "Which unit is P-1 located in?"),
    (F.NEIGHBOURS_DOWNSTREAM, t.neighbours_downstream_text("P-1")),
    (F.LOOP_ACTUATED_VALVE, "Which valve is actuated by control loop P-1?"),
    (F.LOOP_MEASURED_EQUIPMENT, "Which equipment item does control loop P-1 measure?"),
    (F.FLOW_PATH, t.flow_path_text("P-1", "P-2")),
    (F.UPSTREAM_ISOLATION, t.upstream_isolation_text("P-1")),
    (F.CROSS_UNIT, t.cross_unit_text("1")),
    (F.COUNT_IN_UNIT, t.count_in_unit_text("centrifugal pumps", "1")),
    (F.NO_PATH, t.flow_path_text("P-1", "P-2")),
    (F.SHEETS_OF_TAG, t.sheets_of_tag_text("P-1")),
    (F.CONNECTED, t.connected_text("P-1", "P-2")),
    (F.DOWNSTREAM_IN_UNIT, t.downstream_in_unit_text("1", "P-1")),
    (F.INSTRUMENTS_OF_ITEM, t.instruments_of_item_text("P-1")),
    (F.UPSTREAM_SOURCES, t.upstream_sources_text("P-1")),
    (F.SAME_UNIT, t.same_unit_text("P-1", "P-2")),
    (F.LOOPS_NEAR_ITEM, t.loops_near_item_text("P-1")),
]


def _corpus_view_toy() -> ToyCorpus:
    toy = ToyCorpus()
    toy.item("S1", "a", "P-1", unit_id="1")
    toy.item("S1", "b", "P-2", unit_id="2")
    return toy


def _label_of(text: str) -> NeedLabel:
    anchors = extract_anchors(text, _corpus_view_toy().view())
    return RuleNeedClassifier().classify(build_need_input(text, anchors)).label


@pytest.mark.parametrize(("family", "text"), _DEV_TEXTS, ids=[f.value for f, _ in _DEV_TEXTS])
def test_every_dev_template_maps_to_its_gold_label(family: QuestionFamily, text: str) -> None:
    assert {_label_of(text)} == gold_need_of_family(family)


def test_the_rules_cover_every_dev_family_but_the_unanswerable_one() -> None:
    covered = {family for family, _ in _DEV_TEXTS}

    assert covered == set(QuestionFamily) - {F.UNANSWERABLE_TAG}


def test_a_tag_the_plant_lacks_does_not_change_the_label() -> None:
    # the three templates an unanswerable question wraps, with a tag that names no item
    assert _label_of(t.lookup_type_text("Z-999")) is NeedLabel.ITEM
    assert _label_of(t.neighbours_downstream_text("Z-999")) is NeedLabel.NEIGHBOURS_DOWNSTREAM
    assert _label_of(t.flow_path_text("P-1", "Z-999")) is NeedLabel.PATH


def test_the_same_two_anchors_give_path_or_item_by_wording() -> None:
    assert _label_of("Can process flow reach P-2 from P-1?") is NeedLabel.PATH
    assert _label_of("Are P-1 and P-2 in the same unit?") is NeedLabel.ITEM


def test_a_unit_rule_needs_a_unit_anchor_and_no_tag() -> None:
    assert _label_of("Which other units receive process flow directly from unit 1?") is (
        NeedLabel.UNIT_SCOPE
    )
    # a tag is named too, so the unit is only a restriction
    assert _label_of(t.downstream_in_unit_text("1", "P-1")) is NeedLabel.DOWNSTREAM_ALL
    # no unit is named, so the unit rule stays silent
    assert _label_of("How many units does the plant have?") is NeedLabel.GENERIC


def test_the_isolation_wording_is_symmetric_upstream_and_downstream() -> None:
    assert _label_of("To isolate P-1 from all downstream equipment, which valves close?") is (
        NeedLabel.DOWNSTREAM_TO_FIRST_VALVE
    )
    assert _label_of("Which items flow directly into P-1?") is NeedLabel.NEIGHBOURS_UPSTREAM


def test_text_matching_no_rule_is_generic_and_gives_no_confidence() -> None:
    need_input = NeedInput(
        text="Tell me a story about P-1.",
        masked_text="Tell me a story about <TAG>.",
        n_tag_anchors=1,
        n_unit_anchors=0,
    )

    decision = RuleNeedClassifier().classify(need_input)

    assert decision.label is NeedLabel.GENERIC
    assert decision.score is None and decision.scores is None
    assert decision.classifier == "rules" and decision.call is None


def test_masking_hides_tags_and_unit_ids_but_keeps_the_word_unit() -> None:
    text = "Does P-1 feed P-2 in unit 1?"
    view = _corpus_view_toy().view()

    assert (
        mask_anchors(text, extract_anchors(text, view)) == "Does <TAG> feed <TAG> in unit <UNIT>?"
    )


def test_masking_a_tag_printed_with_a_space_and_a_text_without_anchors() -> None:
    toy = ToyCorpus()
    toy.item("S1", "a", "SV 104.01")
    view = toy.view()
    spaced = "Is SV  104.01 open?"  # two spaces; the tag still matches after normalizing

    assert mask_anchors(spaced, extract_anchors(spaced, view)) == "Is <TAG> open?"
    assert mask_anchors("Hello there", extract_anchors("Hello there", view)) == "Hello there"
