"""U4 (isolation secondary score) and D1 (named tags never touched) on toy runs and graph."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import qa_plant_api_toy  # noqa: I001
from cascade_toy import CORPUS, CYPHER, ToyRun, cypher_spec, pin, row, write_questions, write_run
from plantgraph.qa.cascade.corpus_checks import control_valve_tags
from plantgraph.qa.cascade.diagnostics import policy_diagnostics
from plantgraph.qa.cascade.evaluate import evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.cascade.report_models import PolicyDiagnostics
from plantgraph.qa.cascade.report_render_diagnostics import diagnostics_lines
from plantgraph.qa.models import Question

AGENT = "graph_agent_low_steps"
_QUESTION_IDS = ("T1:q1", "T1:q2", "T1:q3", "T1:q4")


def _graph() -> Any:
    return qa_plant_api_toy.build_graph(qa_plant_api_toy._ITEMS, qa_plant_api_toy._EDGES)


def _question(number: int, **fields: Any) -> Question:
    base: dict[str, Any] = {
        "question_id": f"T1:q{number}",
        "corpus_id": CORPUS,
        "family": "CONNECTED",
        "template_id": "X",
        "template_version": "1",
        "text": "toy",
        "answer_type": "BOOLEAN",
        "answerable": True,
        "reference": "yes",
        "generator_seed": 1,
    }
    return Question.model_validate(base | fields)


def _solo_join(
    tmp_path: Path, tier: TierSpec, strategy: str, effort: str, rows: Any
) -> JoinedCorpus:
    questions_root = write_questions(tmp_path / "questions")
    run_dir = write_run(tmp_path / "runs", questions_root, ToyRun("r", strategy, effort, rows))
    policy = CascadePolicy(name="solo", tiers=(tier,))
    return join_corpus(policy, {tier.name: TierSource(run_dir)}, CORPUS, questions_root)


def _all_questions() -> dict[str, Question]:
    return {f"T1:q{n}": _question(n) for n in range(1, 5)}


def _plain_rows() -> list[dict[str, Any]]:
    return [row(q, CYPHER, trace={"retrieval": {"n_rows": 1}}) for q in _QUESTION_IDS]


def test_control_valves_are_the_targets_of_control_edges() -> None:
    assert control_valve_tags(_graph()) == {"BV1"}  # FV -control-> BV1; GV2 and CHV are not driven


def test_isolation_secondary_score_removes_control_valves_from_gold(tmp_path: Path) -> None:
    def answered(question_id: str, answer: list[str], correct: bool) -> dict[str, Any]:
        final = {"answer": answer, "not_present": False}
        return row(
            question_id,
            CYPHER,
            final_answer=final,
            correct=correct,
            trace={"retrieval": {"n_rows": 1}},
        )

    rows = [
        answered("T1:q1", ["GV2"], False),  # leaves the control valve out: right on the secondary
        answered("T1:q2", ["BV1", "GV2"], True),  # matches the key: wrong on the secondary
        answered("T1:q3", ["BV1"], True),  # gold holds only a control valve: no secondary
        row(
            "T1:q4",
            CYPHER,
            final_answer={"answer": None, "not_present": True},
            correct=False,
            trace={"retrieval": {"n_rows": 1}},
        ),
    ]
    joined = _solo_join(tmp_path, cypher_spec(), CYPHER, "low", rows)
    references = [["BV1", "GV2"], ["BV1", "GV2"], ["BV1"], ["GV2"]]
    questions = {
        f"T1:q{n}": _question(
            n, family="UPSTREAM_ISOLATION", answer_type="TAG_SET", reference=reference
        )
        for n, reference in enumerate(references, start=1)
    }

    result = policy_diagnostics(joined, evaluate_policy(joined), questions, _graph())

    assert result.isolation is not None
    assert (result.isolation.primary.correct, result.isolation.primary.total) == (2, 4)
    secondary = result.isolation.control_valves_excluded
    assert (secondary.correct, secondary.total) == (1, 3)


def test_isolation_rows_are_labelled_secondary_in_the_report(tmp_path: Path) -> None:
    joined = _solo_join(tmp_path, cypher_spec(), CYPHER, "low", _plain_rows())
    questions = {
        f"T1:q{n}": _question(
            n, family="UPSTREAM_ISOLATION", answer_type="TAG_SET", reference=["GV2"]
        )
        for n in range(1, 5)
    }

    diagnostics = [policy_diagnostics(joined, evaluate_policy(joined), questions, _graph())]
    text = "\n".join(diagnostics_lines(diagnostics, []))

    assert "secondary score, control valves do not isolate" in text
    assert "| solo | 4/4 | 0/4 |" in text  # stored "correct" is True; the answer "yes" is not GV2


def test_no_isolation_score_without_the_item_graph(tmp_path: Path) -> None:
    joined = _solo_join(tmp_path, cypher_spec(), CYPHER, "low", _plain_rows())

    result = policy_diagnostics(joined, evaluate_policy(joined), _all_questions())

    assert result.isolation is None


def _agent_row(question_id: str, touched: list[str]) -> dict[str, Any]:
    steps = [{"index": 1, "tool": "find", "touched_keys": touched}]
    return row(
        question_id, AGENT, trace={"retrieval": {"stop_reason": "done", "agent_steps": steps}}
    )


def test_named_tags_never_touched_are_counted_over_agent_rows(tmp_path: Path) -> None:
    agent_tier = TierSpec(
        name="agent-low-steps",
        strategy=AGENT,
        pin_sha256=pin("default").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )
    rows = [
        _agent_row("T1:q1", ["S1:bv1", "S1:t1"]),  # both named tags touched
        _agent_row("T1:q2", ["S1:bv1"]),  # T1 named, never touched
        _agent_row("T1:q3", []),  # names no plant tag
        _agent_row("T1:q4", ["S1:t1"]),  # names a tag that is not in the plant
    ]
    joined = _solo_join(tmp_path, agent_tier, AGENT, "default", rows)
    texts = {1: "Is BV1 fed by T1?", 2: "Is BV1 fed by T1?", 3: "How many pumps?", 4: "Is Q-9 ok?"}
    questions = {f"T1:q{n}": _question(n, text=text) for n, text in texts.items()}

    result = policy_diagnostics(joined, evaluate_policy(joined), questions, _graph())

    assert result.agent is not None
    assert result.agent.n_with_named_tags == 2
    assert result.agent.named_tag_never_touched is not None
    assert (
        result.agent.named_tag_never_touched.total,
        result.agent.named_tag_never_touched.correct,
    ) == (1, 1)
    assert "never touched" in "\n".join(diagnostics_lines([result], []))


def test_named_tag_check_is_skipped_without_the_item_graph(tmp_path: Path) -> None:
    agent_tier = TierSpec(
        name="agent-low-steps",
        strategy=AGENT,
        pin_sha256=pin("default").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )
    joined = _solo_join(
        tmp_path, agent_tier, AGENT, "default", [_agent_row(q, []) for q in _QUESTION_IDS]
    )

    result: PolicyDiagnostics = policy_diagnostics(
        joined, evaluate_policy(joined), _all_questions()
    )

    assert result.agent is not None and result.agent.named_tag_never_touched is None
