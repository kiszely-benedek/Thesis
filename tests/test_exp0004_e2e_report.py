"""The E2E report on toy arms with known differences: claims, refusal, exposure split, spend."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from plantgraph.exp0004.e2e_report_load import (
    PREREGISTERED_HEADLINE_N,
    real_spend_usd,
    require_arm_size,
    require_headline_size,
)
from plantgraph.exp0004.e2e_report_models import R5_ARM, ArmData, E2EReport
from plantgraph.exp0004.e2e_report_render import render_markdown
from plantgraph.exp0004.e2e_report_tables import (
    build_e2e_report,
    check_same_questions,
    exposure_groups,
)
from plantgraph.llm.models import CallRecord, ChatResponse
from plantgraph.qa.models import Question

N = 200
IDS = [f"T:{i:03d}" for i in range(N)]
#: The first 40 questions are exposed (k_identity = 2); the rest are unexposed (0 or None).
N_EXPOSED = 40


def _question(index: int) -> Question:
    k_identity: int | None = 2 if index < N_EXPOSED else (0 if index % 2 else None)
    fields: dict[str, Any] = {
        "question_id": IDS[index],
        "corpus_id": "T",
        "family": "CONNECTED" if index % 2 else "LOOKUP_TYPE",
        "template_id": "t",
        "template_version": "1",
        "text": "?",
        "answer_type": "BOOLEAN",
        "answerable": True,
        "reference": "yes",
        "generator_seed": 1,
        "k_identity": k_identity,
    }
    return Question.model_validate(fields)


QUESTIONS = [_question(i) for i in range(N)]


def _arm(label: str, wrong: range, ids: list[str] | None = None) -> ArmData:
    """An arm that answers every question correctly except those at the `wrong` positions."""
    chosen = ids or IDS
    return ArmData(
        label=label,
        correct={qid: IDS.index(qid) not in wrong for qid in chosen},
        outcomes={"cypher-v2t": {"ANSWERED": len(chosen)}},
        spend_usd=0.0,
    )


def _arms() -> dict[str, ArmData]:
    return {
        R5_ARM: _arm(R5_ARM, range(0)),
        "V-d0": _arm("V-d0", range(40)),  # all 40 exposed questions lost
        "V-d2": _arm("V-d2", range(5)),  # most of them won back, 5 still lost
        "V-d4": _arm("V-d4", range(0)),  # all won back
    }


def _report() -> E2EReport:
    return build_e2e_report(_arms(), QUESTIONS, "cascade_v4_iso", 120.0)


def test_each_claim_has_the_known_paired_difference_and_verdict() -> None:
    claims = {c.claim: c for c in _report().claims}

    assert claims["E1"].difference.mean == pytest.approx(-0.2)
    assert claims["E1"].passed
    assert claims["E2"].difference.mean == pytest.approx(35 / N)
    assert claims["E2"].passed
    assert claims["E3"].difference.mean == pytest.approx(0.2)
    assert claims["E3"].passed
    # D2 sits 5 questions below R5: -0.025, but its interval reaches below -0.03
    assert claims["E4 (D2)"].difference.mean == pytest.approx(-0.025)
    assert not claims["E4 (D2)"].passed
    assert claims["E4 (D4)"].difference.mean == 0
    assert claims["E4 (D4)"].passed


def test_e1_fails_when_the_variant_loses_nothing() -> None:
    arms = _arms() | {"V-d0": _arm("V-d0", range(0))}

    claims = {c.claim: c for c in build_e2e_report(arms, QUESTIONS, "p", 120.0).claims}

    assert not claims["E1"].passed
    assert not claims["E2"].passed  # D2 cannot beat a D0 that lost nothing


def test_arms_with_different_question_sets_are_refused() -> None:
    arms = _arms() | {"V-d2": _arm("V-d2", range(0), ids=IDS[:-1])}

    with pytest.raises(ValueError, match="expected arm V-d2 to hold the same questions"):
        build_e2e_report(arms, QUESTIONS, "p", 120.0)


def test_check_same_questions_returns_the_sorted_shared_ids() -> None:
    assert check_same_questions([_arm("a", range(0)), _arm("b", range(0))]) == IDS


def test_exposed_split_counts_none_as_unexposed() -> None:
    groups = exposure_groups(QUESTIONS, IDS)

    exposed, unexposed = (len(g) for g in groups.values())
    assert (exposed, unexposed) == (N_EXPOSED, N - N_EXPOSED)
    rows = [r for r in _report().exposure if r.arm == "V-d0"]
    assert [(r.n, r.n_correct) for r in rows] == [(40, 0), (160, 160)]


def test_family_table_and_markdown_name_every_claim() -> None:
    report = _report()
    text = render_markdown(report)

    assert {r.group for r in report.families} == {"CONNECTED", "LOOKUP_TYPE"}
    for claim in ("E1", "E2", "E3", "E4 (D2)", "E4 (D4)"):
        assert claim in text
    assert "PASS" in text and "FAIL" in text


def _call(cost: float, *, from_cache: bool) -> CallRecord:
    response = ChatResponse(
        text="x", prompt_tokens=1, completion_tokens=1, cost_usd=cost, latency_s=0.1,
        provider_response_id=None, finish_reason="stop", from_cache=from_cache,
        created_at=datetime.now(UTC),
    )  # fmt: skip
    return CallRecord(
        run_id="r", question_id="q", strategy="s", purpose="answer",
        cache_key="k", pin_hash="p", prompt_sha256="h", response=response,
    )  # fmt: skip


def test_spend_sums_only_calls_not_served_from_the_cache(tmp_path: Path) -> None:
    calls = [
        _call(0.5, from_cache=False),
        _call(7.0, from_cache=True),
        _call(0.25, from_cache=False),
    ]
    (tmp_path / "calls.jsonl").write_text(
        "\n".join(c.model_dump_json() for c in calls) + "\n", encoding="utf-8"
    )

    assert real_spend_usd(tmp_path) == pytest.approx(0.75)


def test_spend_of_a_run_without_calls_is_zero(tmp_path: Path) -> None:
    assert real_spend_usd(tmp_path) == 0.0


def test_headline_scope_of_the_wrong_size_is_refused() -> None:
    require_headline_size([f"q{i}" for i in range(PREREGISTERED_HEADLINE_N)])  # no error
    with pytest.raises(ValueError, match="440"):
        require_headline_size(["q1", "q2"])


def test_an_arm_that_lost_headline_questions_is_refused_by_name() -> None:
    require_arm_size("V-d0", PREREGISTERED_HEADLINE_N)  # no error
    with pytest.raises(ValueError, match=r"V-d2.*439"):
        require_arm_size("V-d2", PREREGISTERED_HEADLINE_N - 1)
