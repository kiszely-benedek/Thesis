"""Stored harness runs -> per-question scores -> report, including arms missing at some sizes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from report_toy import (
    AGENT,
    CONTEXT,
    CYPHER,
    luna_pin,
    pin,
    policies,
    row,
    write_ingest,
    write_questions,
    write_run,
)

from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade import join
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.exp0001 import report_load
from plantgraph.qa.exp0001.ex01_cli import main
from plantgraph.qa.exp0001.report import build_ladder_report
from plantgraph.qa.exp0001.report_load import RUN_ARM_OF_STRATEGY, CorpusInputs, score_corpus
from plantgraph.qa.exp0001.report_models import AG, CASCADE, CTX_HIGH, CTX_LOW, CYP
from plantgraph.qa.need.labels import NeedLabel

FAMILIES = {"1": "CONNECTED", "2": "CONNECTED", "3": "FLOW_PATH", "4": "FLOW_PATH"}


def _qids(corpus_id: str) -> list[str]:
    return [f"{corpus_id}:{n}" for n in FAMILIES]


def _ctx_rows(corpus_id: str, correct: list[bool], cost: float = 0.01) -> list[dict]:  # type: ignore[type-arg]
    return [
        row(qid, CONTEXT, ok, cost_usd=cost, latency_s=5.0, context_chars=1500, prompt_tokens=500)
        for qid, ok in zip(_qids(corpus_id), correct, strict=True)
    ]


def _cyp_rows(corpus_id: str) -> list[dict]:  # type: ignore[type-arg]
    """q1 right, q2 wrong (both accepted); q3 returns no rows; q4 is a retrieval error."""
    q1, q2, q3, q4 = _qids(corpus_id)
    return [
        row(q1, CYPHER, True),
        row(q2, CYPHER, False),
        row(q3, CYPHER, False, trace={"retrieval": {"n_rows": 0}}),
        row(q4, CYPHER, False, outcome="RETRIEVAL_ERROR", final_answer=None),
    ]


def _ag_rows(corpus_id: str) -> list[dict]:  # type: ignore[type-arg]
    """The agent tier is run on every question (as `always_g` needs); q2 it gets wrong."""
    q1, q2, q3, q4 = _qids(corpus_id)
    return [
        row(q1, AGENT, True, cost_usd=0.003),
        row(q2, AGENT, False, cost_usd=0.003),
        row(q3, AGENT, True, cost_usd=0.003, latency_s=4.0),
        row(q4, AGENT, True, cost_usd=0.003),
    ]


def _write_size(root: Path, corpus_id: str, arms: set[str], pins: bool = False) -> dict[str, Path]:
    """Questions, ingest and the runs of the arms asked for; returns arm -> run dir."""
    qroot, runs = root / "questions", root / "runs"
    write_questions(qroot, corpus_id, {f"{corpus_id}:{n}": f for n, f in FAMILIES.items()})
    write_ingest(root / "corpora", corpus_id, n_sheets=int(corpus_id[1:]), n_nodes=40)
    make = luna_pin if pins else pin
    dirs: dict[str, Path] = {}
    specs = {
        CTX_HIGH: ("E1-CTXH", CONTEXT, "high", _ctx_rows(corpus_id, [True, True, True, False])),
        CTX_LOW: (
            "E1-CTXL",
            CONTEXT,
            "low",
            _ctx_rows(corpus_id, [True, False, True, False], 0.005),
        ),
        CYP: ("E1-CYP", CYPHER, "low", _cyp_rows(corpus_id)),
        AG: ("E1-AG", AGENT, "high", _ag_rows(corpus_id)),
    }
    for arm in arms:
        prefix, strategy, effort, rows = specs[arm]
        dirs[arm] = write_run(
            runs, qroot, corpus_id, f"{prefix}-{corpus_id}", strategy, make(effort), rows
        )
    return dirs


def _inputs(root: Path, corpus_id: str, dirs: dict[str, Path]) -> CorpusInputs:
    return CorpusInputs(corpus_id, root / "questions", root / "corpora", dirs)


def test_every_arm_is_scored_per_question(tmp_path: Path) -> None:
    dirs = _write_size(tmp_path, "H1", {CTX_HIGH, CTX_LOW, CYP, AG})
    result = score_corpus(_inputs(tmp_path, "H1", dirs), policies(), 120.0)
    correct = {arm: [s.correct_at_cutoff for s in scored] for arm, scored in result.scores.items()}
    assert correct[CTX_HIGH] == [True, True, True, False]
    assert correct[CYP] == [True, False, False, False]
    assert correct[AG] == [True, False, True, True]
    assert correct[CASCADE] == [True, False, True, True]  # q3 and q4 escalate to the agent
    assert result.absent == []
    cascade = result.scores[CASCADE]
    assert cascade[0].cost_usd == pytest.approx(0.001)  # accepted by the first tier
    assert cascade[2].cost_usd == pytest.approx(0.001 + 0.003)  # a question pays for both tiers
    assert cascade[2].latency_s == pytest.approx(1.0 + 4.0)
    assert result.size.n_sheets == 1 and result.size.n_occurrence_nodes == 40


def test_contextrag_prompt_size_and_ratio_come_from_its_rows(tmp_path: Path) -> None:
    dirs = _write_size(tmp_path, "H3", {CTX_HIGH})
    result = score_corpus(_inputs(tmp_path, "H3", dirs), {CTX_HIGH: policies()[CTX_HIGH]}, 120.0)
    assert result.size.ctx_prompt_chars == 1500
    assert result.size.ctx_prompt_tokens_median == 500
    assert result.size.chars_per_token == pytest.approx(3.0)
    assert len(result.ctx_calls) == 4


def test_a_missing_run_is_listed_as_absent_not_skipped(tmp_path: Path) -> None:
    dirs = _write_size(tmp_path, "H3", {CTX_HIGH, CYP})  # no agent run and no ContextRAG-low run
    result = score_corpus(_inputs(tmp_path, "H3", dirs), policies(), 120.0)
    assert set(result.scores) == {CTX_HIGH, CYP}
    assert any(line.startswith("cascade_v3 at H3") and "agent" in line for line in result.absent)
    assert any(line.startswith("ctx-low at H3") for line in result.absent)


def test_ladder_with_contextrag_low_at_only_one_size(tmp_path: Path) -> None:
    h1 = score_corpus(
        _inputs(tmp_path, "H1", _write_size(tmp_path, "H1", {CTX_HIGH, CTX_LOW, CYP, AG})),
        policies(), 120.0,
    )  # fmt: skip
    h3 = score_corpus(
        _inputs(tmp_path, "H3", _write_size(tmp_path, "H3", {CTX_HIGH, CYP, AG})),
        policies(), 120.0,
    )  # fmt: skip
    report = build_ladder_report([h1, h3], 120.0, ladder_ids=("H1", "H3"))
    assert {d.corpus_id for d in report.deltas if d.a == CTX_LOW} == {"H1"}
    assert any("ctx-low at H3" in line for line in report.absent)
    x6 = next(c for c in report.claims if c.id == "X6")
    assert x6.value.startswith("H1:") and "H3" not in x6.value


def test_a_row_missing_for_a_reached_tier_is_refused(tmp_path: Path) -> None:
    dirs = _write_size(tmp_path, "H1", {CTX_HIGH, CYP})
    broken = write_run(
        tmp_path / "runs2", tmp_path / "questions", "H1", "E1-AG-H1", AGENT, pin("high"),
        _ag_rows("H1")[:1],
    )  # fmt: skip
    inputs = _inputs(tmp_path, "H1", {**dirs, AG: broken})
    with pytest.raises(ValueError, match="agent"):
        score_corpus(inputs, policies(), 120.0)


def test_arms_on_different_plants_are_refused(tmp_path: Path) -> None:
    dirs = _write_size(tmp_path, "H1", {CTX_HIGH, CYP})
    config_path = dirs[CYP] / "corpora.json"
    other = config_path.read_text(encoding="utf-8").replace("g" * 64, "h" * 64)
    config_path.write_text(other, encoding="utf-8")
    with pytest.raises(ValueError, match="source_graph_hash"):
        score_corpus(_inputs(tmp_path, "H1", dirs), policies(), 120.0)


def test_a_one_tier_contextrag_policy_joins_like_any_other(tmp_path: Path) -> None:
    """O2: no query row count is needed for a policy that accepts on `answered` alone."""
    tier = TierSpec(
        name="ctx", strategy=CONTEXT, pin_sha256=pin("high").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )  # fmt: skip
    dirs = _write_size(tmp_path, "H1", {CTX_HIGH})
    result = score_corpus(
        _inputs(tmp_path, "H1", dirs), {CTX_HIGH: CascadePolicy(name="p", tiers=(tier,))}, 120.0
    )
    assert [s.correct for s in result.scores[CTX_HIGH]] == [True, True, True, False]


def _write_policy_files(root: Path) -> None:
    inputs = root / "inputs"
    inputs.mkdir(parents=True)
    for arm, effort in ((CTX_HIGH, "high"), (CTX_LOW, "low")):
        tier = TierSpec(
            name=arm, strategy=CONTEXT, pin_sha256=luna_pin(effort).pin_hash(),
            accept=frozenset({AcceptRule.ANSWERED}),
        )  # fmt: skip
        policy = CascadePolicy(name=f"always_{arm}", tiers=(tier,))
        file_name = "always_ctx_high.json" if arm == CTX_HIGH else "always_ctx_low.json"
        (inputs / file_name).write_text(policy.model_dump_json(), encoding="utf-8")


def test_report_command_end_to_end(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for corpus_id, arms in (("H1", {CTX_HIGH, CTX_LOW, CYP, AG}), ("H3", {CTX_HIGH, CYP, AG})):
        _write_size(tmp_path, corpus_id, arms, pins=True)
    _write_policy_files(tmp_path)
    main(["report", "--root", str(tmp_path), "--sizes", "H1,H3"])
    out = tmp_path / "report"
    assert {p.name for p in out.iterdir()} == {
        "report.md", "report.json", "figure.csv", "figure_marks.csv",
    }  # fmt: skip
    markdown = (out / "report.md").read_text(encoding="utf-8")
    assert "The context wall" in markdown and "ctx-low at H3" in markdown
    saved = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert [claim["id"] for claim in saved["claims"]] == ["X1", "X2", "X3", "X4", "X5", "X6"]
    figure = (out / "figure.csv").read_text(encoding="utf-8").splitlines()
    assert figure[0].startswith("corpus_id,n_sheets,log10_sheets,arm,scope")
    assert any(line.startswith("H3,3,") and ",cascade_v3," in line for line in figure)
    assert "X3 REPORTED" in capsys.readouterr().out


def test_a_policy_routed_by_need_label_reads_the_labels_from_the_question_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cascade_v4_iso starts some questions at the agent: the join needs a label per question."""
    seen: list[str] = []
    monkeypatch.setattr(report_load, "load_corpus_view", lambda root, cid: seen.append(cid) or None)
    monkeypatch.setattr(report_load, "anchor_finder", lambda view: lambda text: Anchors())
    monkeypatch.setattr(join, "classify_need", lambda text, finder: NeedLabel.GENERIC)
    dirs = _write_size(tmp_path, "H1", {CYP, AG})
    cascade = policies()["cascade_v3"]
    routed = cascade.model_copy(
        update={"name": "routed", "start_tier_by_label": {NeedLabel.UPSTREAM_TO_FIRST_VALVE: 1}}
    )

    unrouted_scores = score_corpus(_inputs(tmp_path, "H1", dirs), {CASCADE: cascade}, 120.0)
    assert seen == []  # an unrouted policy never reads the corpus graph
    routed_scores = score_corpus(_inputs(tmp_path, "H1", dirs), {CASCADE: routed}, 120.0)

    assert seen == ["H1"]
    assert [s.correct for s in routed_scores.scores[CASCADE]] == [
        s.correct for s in unrouted_scores.scores[CASCADE]
    ]  # no question carries the first-valve label, so the routing changes nothing here


def test_v2t_strategies_map_to_the_same_run_arms_as_f1s() -> None:
    assert RUN_ARM_OF_STRATEGY["cypher_rag_lines"] == RUN_ARM_OF_STRATEGY["cypher_rag_plant"]
    assert RUN_ARM_OF_STRATEGY["graph_agent_lines"] == RUN_ARM_OF_STRATEGY["graph_agent_low_steps"]
