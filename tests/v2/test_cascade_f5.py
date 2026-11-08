"""F5: recall over the scope, offline acc@C following the live fallback, report --setting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from cascade_toy import CORPUS, write_questions
from cascade_v4_toy import AGENT_V2T, agent_rows, tier_sources, write_tier
from plantgraph.qa.cascade import cli as cascade_cli
from plantgraph.qa.cascade.evaluate import evaluate_policy, first_tier_acceptance
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policies
from plantgraph.qa.cascade.tune_report import correct_within
from plantgraph.qa.cascade.tune_select import V4

CASCADE_V4_JSON = V2T_POLICIES_DIR / "cascade_v4.json"


def _join(sources: dict[str, TierSource], tmp_path: Path) -> JoinedCorpus:
    policy = load_policies(V2T_POLICIES_DIR)[V4]
    return join_corpus(policy, sources, CORPUS, tmp_path / "questions")


def test_first_tier_recall_counts_only_the_scope_questions(tmp_path: Path) -> None:
    sources = tier_sources(tmp_path, timeout_s=30.0)
    joined = _join(sources, tmp_path)
    # a stored run may hold more rows than the scope asks for: one extra correct row
    rows = joined.runs["cypher-v2t"].rows
    rows["T1:outside-scope"] = rows["T1:q1"].model_copy(update={"question_id": "T1:outside-scope"})

    acceptance = first_tier_acceptance(joined, joined.policy)

    # in scope the Cypher tier is right on q1 and q2 only (q3, q4 are marked wrong)
    assert acceptance.n_first_tier_correct == 2
    assert (acceptance.n_accepted, acceptance.n_accepted_correct) == (1, 1)
    assert acceptance.recall == 0.5


def _late_agent_rows() -> list[dict[str, Any]]:
    """The agent answers q2 correctly but only after 130 s, past the 120 s cutoff."""
    rows = agent_rows()
    for row in rows:
        if row["question_id"] == "T1:q2":
            row["latency_s"] = 130.0
    return rows


def test_offline_acc_at_cutoff_follows_the_live_fallback(tmp_path: Path) -> None:
    # q2: Cypher answered but was cut at the row cap, so it is not accepted; the agent is late.
    # Live, the agent is cut at the deadline and the policy falls back to Cypher's answer (right).
    cypher = tier_sources(tmp_path, timeout_s=30.0)["cypher-v2t"]
    agent = write_tier(
        tmp_path, "a2", AGENT_V2T, "pin_agent_luna_final_high.json", _late_agent_rows()
    )
    joined = _join({"cypher-v2t": cypher, "agent-v2t": TierSource(agent)}, tmp_path)

    evaluation = evaluate_policy(joined, cutoff_s=120.0)

    by_id = {s.decision.question_id: s for s in evaluation.scored}
    assert by_id["T1:q2"].timed_out and by_id["T1:q2"].correct_at_cutoff
    # the raw (uncut) count is untouched: q2 is the agent's correct answer there
    assert evaluation.summary.n_correct == 3


def test_secondary_cutoff_columns_use_the_same_late_fallback(tmp_path: Path) -> None:
    cypher = tier_sources(tmp_path, timeout_s=30.0)["cypher-v2t"]
    agent = write_tier(
        tmp_path, "a2", AGENT_V2T, "pin_agent_luna_final_high.json", _late_agent_rows()
    )
    joined = _join({"cypher-v2t": cypher, "agent-v2t": TierSource(agent)}, tmp_path)
    evaluation = evaluate_policy(joined, cutoff_s=120.0)

    # at 120 s: q1 (Cypher), q2 (fallback to Cypher); the 130 s agent answers do not count
    assert correct_within(joined, evaluation, 120.0) == 2
    assert correct_within(joined, evaluation, 300.0) == 3  # q2 by the agent, nothing is late


def test_a_late_answer_with_a_wrong_first_tier_fallback_stays_wrong(tmp_path: Path) -> None:
    # q4: Cypher abstained (wrong); the agent's 130 s answer is late; the fallback is wrong too
    sources = tier_sources(tmp_path, timeout_s=30.0)
    joined = _join(sources, tmp_path)

    evaluation = evaluate_policy(joined, cutoff_s=120.0)

    q4 = next(s for s in evaluation.scored if s.decision.question_id == "T1:q4")
    assert q4.timed_out and not q4.correct_at_cutoff


def _report_arguments(tmp_path: Path, sources: dict[str, TierSource], setting: str) -> list[str]:
    return [
        *("report", "--corpus", CORPUS, "--questions-root", str(tmp_path / "questions")),
        *("--policy", str(CASCADE_V4_JSON), "--no-baselines", "--setting", setting),
        *("--out", str(tmp_path / "out")),
        *("--run", f"{CORPUS}:cypher-v2t={sources['cypher-v2t'].run_dir}"),
        *("--run", f"{CORPUS}:agent-v2t={sources['agent-v2t'].run_dir}"),
    ]


def test_report_setting_refuses_runs_made_under_other_limits(tmp_path: Path) -> None:
    sources = tier_sources(tmp_path, timeout_s=120.0)  # setting B's Cypher timeout

    with pytest.raises(SystemExit, match=r"(?s)match setting A.*timeout_s 30"):
        cascade_cli.main(_report_arguments(tmp_path, sources, "A"))


def test_report_setting_accepts_runs_made_under_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sources = tier_sources(tmp_path, timeout_s=30.0)
    write_questions(tmp_path / "questions")

    cascade_cli.main(_report_arguments(tmp_path, sources, "A"))

    assert "cascade_v4" in capsys.readouterr().out
