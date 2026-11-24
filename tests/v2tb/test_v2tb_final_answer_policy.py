"""The B final-answer rules and parsing, the B policy, and the B pins and parameters."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policy
from plantgraph.qa.final_answer import (
    FinalAnswerParseError,
    parse_final_answer,
    render_final_answer_request,
)
from plantgraph.qa.final_answer_variants import V2T_TEMPLATE_PATH
from plantgraph.qa.models import AnswerType, Outcome
from plantgraph.qa.v2tb.descriptor import Descriptor, Side, decode_item, encode_descriptor
from plantgraph.qa.v2tb.final_answer_b import (
    answer_format_instruction_b,
    parse_final_answer_b,
    render_final_answer_request_b,
    to_outcome_b,
)
from plantgraph.qa.v2tb.policy_b import B_POLICY_NAME, policy_b

_B_DIR = Path(__file__).resolve().parents[2] / "src" / "plantgraph" / "qa" / "v2tb"
_E9_INPUTS = Path(__file__).resolve().parents[2] / "data" / "runs" / "exp0007" / "inputs"

_DESCRIPTOR = {
    "class": "GateValve",
    "line_number": "6-P-1203-A1A",
    "next_to": "FV-1203",
    "side": "upstream",
}


def _reply(answer: object, *, not_present: bool = False) -> str:
    return json.dumps({"answer": answer, "not_present": not_present})


# ---- answer rules and parsing -------------------------------------------------------------------


def test_the_b_types_have_their_own_rules_and_the_others_keep_the_frozen_ones() -> None:
    assert "class" in answer_format_instruction_b(AnswerType.VALVE_SET)
    assert "next_to" in answer_format_instruction_b(AnswerType.VALVE_SET)
    assert "NO, NC, LO, LC, CSO, CSC" in answer_format_instruction_b(AnswerType.POSITION)
    assert "list of tags" in answer_format_instruction_b(AnswerType.TAG_SET)


def test_a_valve_set_answer_mixes_tags_and_descriptors() -> None:
    final = parse_final_answer_b(
        _reply(["GTV-1203", {"tag": "FV-1"}, _DESCRIPTOR]), AnswerType.VALVE_SET
    )
    assert final.not_present is False
    assert isinstance(final.answer, list)
    assert final.answer[:2] == ["GTV-1203", "FV-1"]
    decoded = decode_item(final.answer[2])
    assert decoded == Descriptor(
        class_name="GateValve", line_number="6-P-1203-A1A", next_to="FV-1203", side=Side.UPSTREAM
    )
    assert final.answer[2] == encode_descriptor(decoded)  # stored as one canonical string


def test_an_extra_key_in_a_descriptor_is_ignored() -> None:
    final = parse_final_answer_b(_reply([{**_DESCRIPTOR, "note": "x"}]), AnswerType.VALVE_SET)
    assert isinstance(final.answer, list)
    assert decode_item(final.answer[0]) == decode_item(encode_descriptor(_expected()))


def _expected() -> Descriptor:
    return Descriptor(
        class_name="GateValve", line_number="6-P-1203-A1A", next_to="FV-1203", side=Side.UPSTREAM
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"class": "GateValve"},  # missing keys
        {**_DESCRIPTOR, "side": "left"},
        {"tag": 5},
        7,
    ],
)
def test_a_malformed_valve_set_item_is_a_parse_failure(bad: object) -> None:
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer_b(_reply([bad]), AnswerType.VALVE_SET)
    assert to_outcome_b(_reply([bad]), AnswerType.VALVE_SET) == (Outcome.PARSE_FAILURE, None)


def test_a_valve_set_answer_must_be_a_list() -> None:
    with pytest.raises(FinalAnswerParseError, match="needs a list"):
        parse_final_answer_b(_reply("GTV-1203"), AnswerType.VALVE_SET)


def test_an_abstention_needs_no_answer_shape() -> None:
    final = parse_final_answer_b(_reply(None, not_present=True), AnswerType.VALVE_SET)
    assert final.not_present and final.answer is None


def test_a_position_answer_is_read_as_its_code() -> None:
    assert parse_final_answer_b(_reply("normally closed"), AnswerType.POSITION).answer == "NC"
    with pytest.raises(FinalAnswerParseError, match="POSITION needs one of"):
        parse_final_answer_b(_reply("ajar"), AnswerType.POSITION)


def test_a_reply_with_no_json_is_a_parse_failure() -> None:
    with pytest.raises(FinalAnswerParseError, match="no JSON object"):
        parse_final_answer_b("I think GTV-1203", AnswerType.VALVE_SET)


def test_frozen_types_parse_exactly_as_in_the_frozen_step() -> None:
    reply = _reply(["P-1", "T-1"])
    assert parse_final_answer_b(reply, AnswerType.TAG_SET) == parse_final_answer(
        reply, AnswerType.TAG_SET
    )
    with pytest.raises(FinalAnswerParseError):
        parse_final_answer_b(_reply("not a list"), AnswerType.TAG_SET)


# ---- the request --------------------------------------------------------------------------------


def _pin() -> ModelPin:
    return ModelPin.model_validate_json(
        (_E9_INPUTS / "pin_cypher_luna_low.json").read_text("utf-8")
    )


def test_a_frozen_type_without_primer_renders_the_same_request_as_the_frozen_step() -> None:
    pin, answer_type = _pin(), AnswerType.TAG_SET
    frozen = render_final_answer_request(
        pin=pin,
        context="C",
        question_text="Q",
        answer_type=answer_type,
        template_path=V2T_TEMPLATE_PATH,
    )
    mine = render_final_answer_request_b(
        pin=pin,
        context="C",
        question_text="Q",
        answer_type=answer_type,
        template_path=V2T_TEMPLATE_PATH,
    )
    assert mine == frozen


def test_a_b_request_carries_the_b_primer_and_the_valve_set_rule() -> None:
    request = render_final_answer_request_b(
        pin=_pin(),
        context="C",
        question_text="Q",
        answer_type=AnswerType.VALVE_SET,
        primer=True,
        template_path=V2T_TEMPLATE_PATH,
    )
    text = request.messages[0].content
    assert "Valve positions:" in text and '"next_to"' in text
    assert "<<" not in text  # every slot was filled


# ---- policy, pins, parameters -------------------------------------------------------------------


def test_the_b_policy_is_the_a_policy_under_another_name() -> None:
    policy_a = load_policy(V2T_POLICIES_DIR / "cascade_v4_iso.json")
    policy = policy_b()
    assert policy.name == B_POLICY_NAME == "cascade_v4_iso_b"
    assert policy.model_dump(exclude={"name"}) == policy_a.model_dump(exclude={"name"})


def test_the_b_pins_are_the_pins_of_the_policy_tiers() -> None:
    pins = json.loads((_B_DIR / "pins_b.json").read_text("utf-8"))
    for tier in policy_b().tiers:
        assert ModelPin.model_validate(pins[tier.name]).pin_hash() == tier.pin_sha256


def test_the_b_parameters_are_the_e9_parameters() -> None:
    params = json.loads((_B_DIR / "params_b.json").read_text("utf-8"))
    cypher = json.loads((_E9_INPUTS / "params_cypher_v2t_a.json").read_text("utf-8"))
    agent = json.loads((_E9_INPUTS / "params_agent_v2t.json").read_text("utf-8"))
    assert params == {**cypher, **agent}
