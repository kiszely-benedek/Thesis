"""CV2-T1: total question latency, the cutoff C, and the LB-1 / LB-2 verdicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cascade_toy import (
    CORPUS,
    CYPHER,
    NEED,
    ToyRun,
    cypher_rows,
    need_rows,
    need_spec,
    policy,
    write_questions,
    write_run,
)
from plantgraph.qa.cascade import cli
from plantgraph.qa.cascade.evaluate import (
    DEFAULT_CUTOFF_S,
    LatencyBound,
    Summary,
    compare,
    evaluate_policy,
)
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.models import Decision
from plantgraph.qa.cascade.policy import decide_all
from plantgraph.qa.cascade.references import (
    evaluate_always,
    evaluate_oracle,
    random_escalation,
)
from plantgraph.qa.cascade.report import build_report
from plantgraph.qa.cascade.report_render import render_markdown
from plantgraph.qa.cascade.report_verdicts import check_latency_bound

Rows = list[dict[str, Any]]


def _with_latency(rows: Rows, question_id: str, latency_s: float) -> Rows:
    return [{**r, "latency_s": latency_s} if r["question_id"] == question_id else r for r in rows]


def _with_retrieval_latency(rows: Rows, question_id: str, llm_latency_s: float) -> Rows:
    usage = {"n_calls": 1, "prompt_tokens": 1, "completion_tokens": 1, "cost_usd": 0.001}
    usage["llm_latency_s"] = llm_latency_s
    return [{**r, "retrieval_usage": usage} if r["question_id"] == question_id else r for r in rows]


def _sources(
    tmp_path: Path,
    cypher: Rows,
    need: Rows,
    cypher_compute: dict[str, float] | None = None,
    need_compute: dict[str, float] | None = None,
) -> tuple[dict[str, TierSource], Path]:
    questions_root = write_questions(tmp_path / "questions")
    runs_root = tmp_path / "runs"
    cypher_run = ToyRun("c", CYPHER, "low", cypher, local_compute_s=cypher_compute)
    need_run = ToyRun("n", NEED, "default", need, local_compute_s=need_compute)
    sources = {
        "cypher-low": TierSource(write_run(runs_root, questions_root, cypher_run)),
        "need-default": TierSource(write_run(runs_root, questions_root, need_run)),
    }
    return sources, questions_root


def _join(
    tmp_path: Path,
    cypher: Rows,
    need: Rows,
    cypher_compute: dict[str, float] | None = None,
    need_compute: dict[str, float] | None = None,
) -> JoinedCorpus:
    sources, questions_root = _sources(tmp_path, cypher, need, cypher_compute, need_compute)
    return join_corpus(policy(), sources, CORPUS, questions_root)


def _decisions(joined: JoinedCorpus) -> list[Decision]:
    return decide_all(joined.policy, joined.question_ids, joined.need_labels, joined.signals)


# --- summed latency ---


def test_a_two_tier_decision_sums_every_call_of_both_tiers(tmp_path: Path) -> None:
    # q2 escalates: tier 1 = 1 s final + 2 s query writing + 0.5 s local; tier 2 = 1 + 4 + 0.25 s
    cypher = _with_retrieval_latency(cypher_rows(), "T1:q2", 2.0)
    need = _with_retrieval_latency(need_rows(), "T1:q2", 4.0)
    joined = _join(
        tmp_path, cypher, need, cypher_compute={"T1:q2": 0.5}, need_compute={"T1:q2": 0.25}
    )

    decision = {d.question_id: d for d in _decisions(joined)}["T1:q2"]

    assert decision.tiers_tried == ("cypher-low", "need-default")
    assert decision.latency_s == pytest.approx(8.75)
    assert joined.signals["cypher-low"]["T1:q2"].final_latency_s == pytest.approx(1.0)


def test_latency_without_timings_is_flagged_incomplete(tmp_path: Path) -> None:
    # only q1 has timings, and only in tier 1: q2 and q4 try both tiers, q3 too
    joined = _join(
        tmp_path, cypher_rows(), need_rows(), cypher_compute={"T1:q1": 0.5}, need_compute={}
    )

    flags = {d.question_id: d.latency_complete for d in _decisions(joined)}

    assert flags == {"T1:q1": True, "T1:q2": False, "T1:q3": False, "T1:q4": False}
    assert evaluate_policy(joined).summary.n_latency_incomplete == 3


# --- the cutoff ---


def test_a_correct_answer_at_121_s_is_wrong_for_every_arm(tmp_path: Path) -> None:
    # q1 is correct in both runs but arrives at 121 s
    late = _with_latency(cypher_rows(), "T1:q1", 121.0), _with_latency(need_rows(), "T1:q1", 121.0)
    joined = _join(tmp_path, *late)

    cascade = evaluate_policy(joined)
    always_c = evaluate_always(joined, joined.policy.tiers[0])
    always_n = evaluate_always(joined, need_spec())

    for arm in (cascade, always_c, always_n):
        q1 = next(s for s in arm.scored if s.decision.question_id == "T1:q1")
        assert q1.correct and q1.timed_out and not q1.correct_at_cutoff
        assert arm.summary.n_correct_at_cutoff == arm.summary.n_correct - 1
        assert arm.summary.n_timed_out == 1


def test_the_cutoff_is_a_parameter_and_is_inclusive(tmp_path: Path) -> None:
    joined = _join(tmp_path, _with_latency(cypher_rows(), "T1:q1", 121.0), need_rows())

    at_default = evaluate_policy(joined)
    at_180 = evaluate_policy(joined, cutoff_s=180.0)
    at_exact = evaluate_policy(joined, cutoff_s=121.0)

    assert at_default.summary.cutoff_s == DEFAULT_CUTOFF_S == 120.0
    assert at_180.summary.n_correct_at_cutoff == at_180.summary.n_correct
    assert at_exact.summary.n_timed_out == 0  # exactly C is still in time


def test_references_and_bootstrap_use_the_same_cutoff(tmp_path: Path) -> None:
    joined = _join(tmp_path, _with_latency(cypher_rows(), "T1:q1", 121.0), need_rows())

    oracle = evaluate_oracle(joined)
    random = random_escalation(joined, n_draws=50)
    cascade = evaluate_policy(joined)
    always_n = evaluate_always(joined, need_spec())
    comparison = compare(cascade.series(), always_n.series())

    assert oracle.summary.n_correct_at_cutoff < oracle.summary.n_correct
    assert random.correct_at_cutoff_mean <= random.correct_mean
    assert len(random.series().correct_at_cutoff) == 4
    # raw: the cascade is ahead of always-N; at C it loses q1, so its lead shrinks
    assert comparison.accuracy.mean > comparison.accuracy_at_cutoff.mean


# --- LB-1 / LB-2 ---


def _summary(median: float, p90: float) -> Summary:
    return Summary(
        policy="p", corpus_id="D100", n_questions=10, n_correct=9, cutoff_s=120.0,
        n_correct_at_cutoff=9, n_timed_out=0, n_latency_incomplete=0, total_cost_usd=1.0,
        cost_per_question_usd=0.1, latency_median_s=median, latency_mean_s=median,
        latency_p90_s=p90, latency_p95_s=p90, latency_max_s=p90, tier_shares={}, tier_calls={},
    )  # fmt: skip


@pytest.mark.parametrize(
    ("median", "p90", "lb1", "lb2"),
    [
        (10.0, 60.0, "PASS", "PASS"),  # the limits themselves pass
        (10.1, 60.0, "FAIL", "PASS"),
        (5.7, 60.1, "PASS", "FAIL"),
        (14.9, 167.5, "FAIL", "FAIL"),  # always-N on D1000 in the design note
    ],
)
def test_lb_verdicts_on_hand_made_numbers(median: float, p90: float, lb1: str, lb2: str) -> None:
    verdicts = check_latency_bound(_summary(median, p90), LatencyBound())

    assert [(v.rule, v.status) for v in verdicts] == [("LB-1", lb1), ("LB-2", lb2)]
    assert "D100" in verdicts[0].headline


# --- the report ---


def test_report_shows_the_bound_the_verdicts_and_the_chosen_cutoff(tmp_path: Path) -> None:
    sources, questions_root = _sources(
        tmp_path, _with_latency(cypher_rows(), "T1:q1", 121.0), need_rows()
    )
    chosen = [policy()]

    default = build_report([CORPUS], {CORPUS: sources}, questions_root, chosen)
    wide = build_report(
        [CORPUS], {CORPUS: sources}, questions_root, chosen, LatencyBound(cutoff_s=180.0)
    )
    text = render_markdown(default)

    assert default.bound.cutoff_s == 120.0
    assert "C = 120 s" in text
    assert "acc@120" in text
    assert "### Latency bound" in text
    # the 121 s answer is the toy's p90, so the median passes and the tail fails
    assert "LB-1 PASS" in text and "LB-2 FAIL" in text
    toy = default.corpora[0].policies[0]
    assert [v.rule for v in toy.latency_verdicts] == ["LB-1", "LB-2"]
    assert toy.summary.n_correct_at_cutoff == toy.summary.n_correct - 1
    assert wide.corpora[0].policies[0].summary.n_timed_out == 0
    assert "acc@180" in render_markdown(wide)


def test_cli_takes_the_cutoff_as_an_option(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sources, questions_root = _sources(tmp_path, cypher_rows(), need_rows())
    policy_path = tmp_path / "toy.json"
    policy_path.write_text(policy().model_dump_json(), encoding="utf-8")

    cli.main(
        [
            *("report", "--corpus", CORPUS, "--questions-root", str(questions_root)),
            *("--policy", str(policy_path), "--out", str(tmp_path / "out")),
            *("--cutoff-s", "180"),
            *("--run", f"{CORPUS}:cypher-low={sources['cypher-low'].run_dir}"),
            *("--run", f"{CORPUS}:need-default={sources['need-default'].run_dir}"),
        ]
    )

    assert "C = 180 s" in capsys.readouterr().out
