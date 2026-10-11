"""Tag matching on free text, and cascade_v3 derived from the tier rows with the frozen rules."""

from __future__ import annotations

from typing import Any

import pytest

from plantgraph.qa.cascade.policy import load_policy
from plantgraph.qa.exp0001.ex01_cascade import derive_cascade_rows, tier_arms
from plantgraph.qa.exp0001.ex01_models import CASCADE_ARM, Ex01AnswerRow, Ex01ChecklistItem
from plantgraph.qa.exp0001.ex01_runner import CASCADE_POLICY_FILE
from plantgraph.qa.exp0001.ex01_tags import check_tags, first_position
from plantgraph.qa.models import Outcome


def _item(**fields: Any) -> Ex01ChecklistItem:
    base: dict[str, Any] = {"qid": "CP15", "required_tags": [], "ordered": False}
    return Ex01ChecklistItem(**{**base, **fields})


def test_a_tag_matches_with_case_and_spaces_ignored() -> None:
    assert first_position("close hv 4750.01 now", "HV4750.01") == 6
    assert first_position("close HV4750.01.", "hv4750.01") == 6


def test_a_tag_is_not_found_inside_a_longer_token() -> None:
    assert first_position("H10070 and XH1007", "H1007") is None
    assert first_position("(H1007)", "H1007") == 1


def test_an_alias_counts_for_its_tag() -> None:
    item = _item(required_tags=["P4711"], aliases={"P4711": ["inlet"]})
    assert check_tags("water from the inlet", item).found == ["P4711"]


def test_missing_and_forbidden_tags_are_reported() -> None:
    item = _item(required_tags=["HV4750.01", "PV4712.02"], forbidden_tags=["TV4750.03"])
    hits = check_tags("close HV4750.01 and TV4750.03", item)
    assert hits.found == ["HV4750.01"] and hits.missing == ["PV4712.02"]
    assert hits.forbidden_present == ["TV4750.03"] and hits.order_ok is None


def test_order_is_checked_only_when_the_item_is_ordered() -> None:
    item = _item(required_tags=["P4711", "H1007", "T4750"], ordered=True)
    assert check_tags("P4711 -> H1007 -> T4750", item).order_ok is True
    assert check_tags("T4750 <- H1007 <- P4711", item).order_ok is False


# ---- cascade_v3 ---------------------------------------------------------------------------


def _row(arm: str, qid: str = "CP11", repeat: int = 1, **fields: Any) -> Ex01AnswerRow:
    base: dict[str, Any] = {
        "run_id": "r", "qid": qid, "arm": arm, "repeat": repeat, "outcome": Outcome.ANSWERED,
        "answer_text": f"{arm} answer", "not_present": False, "cost_usd": 0.001, "latency_s": 2.0,
        "local_compute_s": 0.5, "prompt_tokens": 1, "completion_tokens": 1, "context_chars": 10,
        "trace": {"retrieval": {"n_rows": 3}},
    }  # fmt: skip
    return Ex01AnswerRow(**{**base, **fields})


def _derive(cyp: Ex01AnswerRow, ag: Ex01AnswerRow) -> Ex01AnswerRow:
    policy = load_policy(CASCADE_POLICY_FILE)
    (derived,) = derive_cascade_rows([cyp, ag], policy)
    return derived


def test_the_policy_tiers_map_to_the_cyp_and_ag_arms() -> None:
    assert tier_arms(load_policy(CASCADE_POLICY_FILE)) == {
        "cypher-luna": "cyp",
        "agent-luna": "ag",
    }


def test_an_accepted_first_tier_settles_the_question_and_the_agent_is_not_charged() -> None:
    derived = _derive(_row("cyp"), _row("ag", cost_usd=0.01))
    assert derived.arm == CASCADE_ARM and derived.answer_text == "cyp answer"
    assert derived.cost_usd == pytest.approx(0.001)
    assert derived.latency_s == pytest.approx(2.0)
    assert derived.trace == {"answered_by": "cypher-luna", "tiers_tried": ["cypher-luna"]}


@pytest.mark.parametrize(
    "cyp_fields",
    [
        {"trace": {"retrieval": {"n_rows": 0}}},  # the query returned nothing
        {"not_present": True},  # the answer abstains
        {"outcome": Outcome.RETRIEVAL_ERROR, "answer_text": None},
    ],
)
def test_a_rejected_first_tier_hands_over_to_the_agent_and_both_are_charged(
    cyp_fields: dict[str, Any],
) -> None:
    derived = _derive(_row("cyp", **cyp_fields), _row("ag", cost_usd=0.01))
    assert derived.answer_text == "ag answer"
    assert derived.cost_usd == pytest.approx(0.011)
    assert derived.latency_s == pytest.approx(4.0)
    assert derived.trace["tiers_tried"] == ["cypher-luna", "agent-luna"]


def test_when_no_tier_is_accepted_the_first_tiers_answer_stands() -> None:
    derived = _derive(
        _row("cyp", trace={"retrieval": {"n_rows": 0}}),
        _row("ag", outcome=Outcome.PARSE_FAILURE, answer_text=None),
    )
    assert derived.answer_text == "cyp answer"
    assert derived.trace["answered_by"] == "cypher-luna"


def test_nothing_is_derived_when_a_tier_row_is_missing_or_errored() -> None:
    policy = load_policy(CASCADE_POLICY_FILE)
    errored = _row("ag", outcome=Outcome.PROVIDER_ERROR, answer_text=None, cost_usd=None)
    assert derive_cascade_rows([_row("cyp")], policy) == []
    assert derive_cascade_rows([_row("cyp"), errored], policy) == []


def test_each_question_and_repeat_gets_its_own_cascade_row() -> None:
    policy = load_policy(CASCADE_POLICY_FILE)
    rows = [
        _row(arm, qid, repeat)
        for arm in ("cyp", "ag")
        for qid in ("CP11", "CP12")
        for repeat in (1, 2)
    ]
    derived = derive_cascade_rows(rows, policy)
    assert [(r.qid, r.repeat) for r in derived] == [
        ("CP11", 1),
        ("CP11", 2),
        ("CP12", 1),
        ("CP12", 2),
    ]
