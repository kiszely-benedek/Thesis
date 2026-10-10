"""The cascade join: signals, refusals on any mismatch, gap reporting and the `needed` subset."""

from __future__ import annotations

from pathlib import Path

import pytest

from cascade_toy import (
    CORPUS,
    CYPHER,
    NEED,
    TEXTS,
    ToyRun,
    cypher_rows,
    need_rows,
    policy,
    write_questions,
    write_run,
)
from plantgraph.llm.models import ModelPin
from plantgraph.qa.anchors import Anchors, TagAnchor
from plantgraph.qa.cascade.accept import is_accepted, start_index
from plantgraph.qa.cascade.checks import JoinRefused
from plantgraph.qa.cascade.gaps import IncompleteJoinError
from plantgraph.qa.cascade.join import TierSource, join_corpus, require_complete
from plantgraph.qa.cascade.models import Signals
from plantgraph.qa.cascade.needed import write_needed
from plantgraph.qa.cascade.signals import extract_signals
from plantgraph.qa.models import Outcome, QuestionResult
from plantgraph.qa.need.labels import NeedLabel


def _runs(tmp_path: Path, **need_fields: object) -> tuple[Path, dict[str, TierSource]]:
    questions_root = write_questions(tmp_path / "questions")
    runs_root = tmp_path / "runs"
    cypher = ToyRun("c", CYPHER, "low", cypher_rows())
    need = ToyRun("n", NEED, "default", need_rows())
    for field, value in need_fields.items():
        setattr(need, field, value)
    sources = {
        "cypher-low": TierSource(write_run(runs_root, questions_root, cypher)),
        "need-default": TierSource(write_run(runs_root, questions_root, need)),
    }
    return questions_root, sources


def test_join_builds_signals_with_total_cost_and_both_runaway_kinds(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)

    joined = join_corpus(policy(), sources, CORPUS, questions_root)

    cypher, need = joined.signals["cypher-low"], joined.signals["need-default"]
    assert cypher["T1:q1"].cost_usd == pytest.approx(0.003)  # final 0.001 + query call 0.002
    assert cypher["T1:q1"].n_rows == 2 and need["T1:q1"].n_rows is None
    assert cypher["T1:q4"].not_present is True
    assert need["T1:q3"].runaway  # by outcome: PARSE_FAILURE
    assert need["T1:q4"].outcome is Outcome.ANSWERED and need["T1:q4"].runaway  # by token cap
    assert not need["T1:q1"].runaway


def test_need_label_comes_from_the_need_run_trace_for_every_tier(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)

    joined = join_corpus(policy(), sources, CORPUS, questions_root)

    assert joined.signals["cypher-low"]["T1:q1"].need_label is NeedLabel.PATH
    assert joined.signals["need-default"]["T1:q3"].need_label is NeedLabel.UPSTREAM_ALL


def test_rules_classifier_label_equals_the_trace_label(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)
    two_tags = Anchors(
        tags=(
            TagAnchor(text="E-28-2", position=TEXTS["T1:q1"].index("E-28-2"), occurrences=()),
            TagAnchor(text="E-10-1", position=TEXTS["T1:q1"].index("E-10-1"), occurrences=()),
        )
    )

    joined = join_corpus(
        policy(),
        {"cypher-low": sources["cypher-low"]},
        CORPUS,
        questions_root,
        find_anchors=lambda text: two_tags,
    )

    assert joined.need_labels["T1:q1"] is NeedLabel.PATH  # same as the need_rows() trace label


def test_join_without_any_label_source_leaves_labels_empty(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)

    joined = join_corpus(policy(), {"cypher-low": sources["cypher-low"]}, CORPUS, questions_root)

    assert joined.signals["cypher-low"]["T1:q1"].need_label is None


@pytest.mark.parametrize(
    ("field", "value", "named"),
    [
        ("source_graph_hash", "x" * 64, "source_graph_hash"),
        ("primer", False, "primer"),
        ("prompt_overrides", {"final_answer.txt": "0" * 64}, "final_answer.txt"),
        ("repeats", 2, "one-repeat"),
    ],
)
def test_join_refuses_a_mismatched_run(
    tmp_path: Path, field: str, value: object, named: str
) -> None:
    questions_root, sources = _runs(tmp_path, **{field: value})

    with pytest.raises(JoinRefused, match=named):
        join_corpus(policy(), sources, CORPUS, questions_root)


def test_join_refuses_a_changed_question_text(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)
    # the need run was started from a questions file whose q2 was reworded
    reworded = write_questions(tmp_path / "other", TEXTS | {"T1:q2": "Which type is TK-28-1?"})
    need = ToyRun("n2", NEED, "default", need_rows())
    sources["need-default"] = TierSource(write_run(tmp_path / "runs2", reworded, need), reworded)

    with pytest.raises(JoinRefused, match=r"T1:q2.*differs"):
        join_corpus(policy(), sources, CORPUS, questions_root)


def test_join_refuses_a_pin_that_is_not_the_tiers(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)
    wrong = ToyRun("n3", NEED, "high", need_rows())  # the tier spec expects effort "default"
    sources["need-default"] = TierSource(write_run(tmp_path / "runs3", questions_root, wrong))

    with pytest.raises(JoinRefused, match="pin_sha256"):
        join_corpus(policy(), sources, CORPUS, questions_root)


def test_missing_rows_are_listed_with_the_harness_command(tmp_path: Path) -> None:
    questions_root = write_questions(tmp_path / "questions")
    runs_root = tmp_path / "runs"
    partial = ToyRun("n", NEED, "default", need_rows()[:2])  # q3 and q4 have no need row
    sources = {
        "cypher-low": TierSource(
            write_run(runs_root, questions_root, ToyRun("c", CYPHER, "low", cypher_rows()))
        ),
        "need-default": TierSource(write_run(runs_root, questions_root, partial)),
    }
    joined = join_corpus(policy(), sources, CORPUS, questions_root)

    with pytest.raises(IncompleteJoinError) as raised:
        require_complete(joined)

    assert raised.value.gaps == {"need-default": ["T1:q3", "T1:q4"]}
    message = str(raised.value)
    assert "T1:q3, T1:q4" in message
    assert f"--strategy {NEED}" in message and "python -m plantgraph.qa.harness" in message


def test_needed_writes_the_union_of_questions_reaching_a_tier(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)
    out_root = tmp_path / "qsub"

    default_only = write_needed(
        [policy()], "need-default", sources, CORPUS, questions_root, out_root
    )
    # a variant that starts PATH questions (q1) at tier index 1 adds q1 to the union
    variant = policy(start_tier_by_label={NeedLabel.PATH: 1})
    union = write_needed(
        [policy(), variant], "need-default", sources, CORPUS, questions_root, out_root
    )

    assert default_only.question_ids == ["T1:q2", "T1:q3", "T1:q4"]  # tier 1 accepts q1
    assert union.question_ids == ["T1:q1", "T1:q2", "T1:q3", "T1:q4"]
    assert union.n_already_answered == 4
    assert union.path == out_root / "need-default" / CORPUS / "questions.jsonl"
    original = (questions_root / CORPUS / "questions.jsonl").read_bytes()
    assert union.path.read_bytes() == original  # full rows, bare LF


def test_needed_rejects_an_unknown_tier(tmp_path: Path) -> None:
    questions_root, sources = _runs(tmp_path)

    with pytest.raises(ValueError, match="tier named 'nope'"):
        write_needed([policy()], "nope", sources, CORPUS, questions_root, tmp_path / "q")


def test_extract_signals_refuses_a_missing_retrieval_cost() -> None:
    row = QuestionResult.model_validate(
        {
            "run_id": "r",
            "question_id": "q",
            "strategy": CYPHER,
            "repeat": 0,
            "outcome": "ANSWERED",
            "final_answer": None,
            "correct": False,
            "f1": None,
            "prompt_tokens": 1,
            "completion_tokens": 1,
            "cost_usd": 0.1,
            "latency_s": 1.0,
            "context_chars": 1,
            "retrieval_usage": {"n_calls": 1, "cost_usd": None},
        }
    )
    pin = ModelPin(backend="openrouter", model_id="m", max_output_tokens=10)

    with pytest.raises(ValueError, match="no cost"):
        extract_signals(row, "t", pin, None)


def test_signals_has_no_gold_field() -> None:
    gold = {"correct", "f1", "reference", "family", "k", "u", "answerable"}

    assert gold.isdisjoint(Signals.model_fields)


def test_acceptance_rules_on_signals() -> None:
    def signals(**fields: object) -> Signals:
        base: dict[str, object] = {
            "question_id": "q", "tier": "t", "outcome": Outcome.ANSWERED, "n_rows": 1,
            "not_present": False, "runaway": False, "cost_usd": 0.0, "latency_s": 0.0,
            "final_latency_s": 0.0, "latency_complete": True, "need_label": None,
        }  # fmt: skip
        return Signals.model_validate(base | fields)

    rules = policy().tiers[0].accept
    assert is_accepted(signals(), rules)
    assert not is_accepted(signals(n_rows=0), rules)
    assert not is_accepted(signals(not_present=True), rules)
    assert not is_accepted(signals(outcome=Outcome.RETRIEVAL_ERROR), rules)
    with pytest.raises(ValueError, match="row count"):
        is_accepted(signals(n_rows=None), rules)


def test_a_label_policy_without_a_label_is_refused() -> None:
    with pytest.raises(ValueError, match="need label"):
        start_index(policy(start_tier_by_label={NeedLabel.PATH: 1}), None)
