"""The EXP-0009 judge entry point: B's answer types are described; nothing pre-registered moves."""

from __future__ import annotations

import pytest

from plantgraph.qa.audit import judge
from plantgraph.qa.audit.models import JudgeInput
from plantgraph.qa.exp0009 import audit_judge
from plantgraph.qa.models import AnswerType

#: PREREG A's values (`data/runs/exp0009/prereg/PREREG_A.md`, "both equal EXP-0008's")
TEMPLATE_SHA256 = "b56c89d5fba7111f4270d47ef4d8cd53796eee5c499fc3cc5e1ce3d9d2312eaa"
JUDGE_PIN_SHA256 = "e4794d07b865bf29c276f58309ccf35f205f3a71fabf9257260863cf2a0ea6aa"


@pytest.fixture(autouse=True)
def _fresh_table(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each test starts from a copy of the frozen table, so one test's install cannot leak."""
    monkeypatch.setattr(judge, "_ANSWER_TYPE_HELP", dict(judge._ANSWER_TYPE_HELP))


def _input(answer_type: AnswerType) -> JudgeInput:
    return JudgeInput(
        question_text="Which valves isolate pump P-1?",
        answer_type=answer_type,
        raw_reply='{"answer": ["V-1"]}',
        reference=["V-1"],
        answerable=True,
        plant_excerpt="(excerpt)",
    )


def test_the_preregistered_template_and_judge_pin_hashes_are_unchanged() -> None:
    audit_judge.install_extra_help()
    assert judge.template_sha256() == TEMPLATE_SHA256
    assert judge.judge_pin().pin_hash() == JUDGE_PIN_SHA256


def test_the_frozen_judge_cannot_render_a_b_row_but_the_entry_point_can() -> None:
    with pytest.raises(KeyError):
        judge.build_prompt(_input(AnswerType.VALVE_SET))
    audit_judge.install_extra_help()
    for answer_type in (AnswerType.VALVE_SET, AnswerType.POSITION):
        prompt = judge.build_prompt(_input(answer_type))
        assert audit_judge.EXTRA_ANSWER_TYPE_HELP[answer_type] in prompt
        assert "<<" not in prompt  # every placeholder was filled


def test_the_ten_frozen_lines_and_their_prompts_are_not_touched() -> None:
    before = dict(judge._ANSWER_TYPE_HELP)
    prompt_before = judge.build_prompt(_input(AnswerType.TAG_SET))
    audit_judge.install_extra_help()
    added = set(judge._ANSWER_TYPE_HELP) - set(before)
    assert added == {AnswerType.VALVE_SET, AnswerType.POSITION}
    assert all(judge._ANSWER_TYPE_HELP[t] == line for t, line in before.items())
    assert judge.build_prompt(_input(AnswerType.TAG_SET)) == prompt_before


def test_installing_twice_is_harmless_and_a_conflicting_line_is_refused() -> None:
    audit_judge.install_extra_help()
    audit_judge.install_extra_help()
    judge._ANSWER_TYPE_HELP[AnswerType.POSITION] = "POSITION (something else)"
    with pytest.raises(ValueError, match="POSITION"):
        audit_judge.install_extra_help()


def test_main_prints_the_added_lines_and_their_hash(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audit_judge.cli, "main", lambda argv: 0)
    assert audit_judge.main(["report"]) == 0
    out = capsys.readouterr().out
    assert f"added judge help lines sha256: {audit_judge.extra_lines_sha256()}" in out
    assert all(line in out for line in audit_judge.EXTRA_ANSWER_TYPE_HELP.values())
    assert len(audit_judge.extra_lines_sha256()) == 64
