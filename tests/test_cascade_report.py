"""The cascade report: S1-S3 rules on hand-made numbers, the toy report, and the CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cascade_toy import (
    CORPUS,
    CYPHER,
    NEED,
    ToyRun,
    cypher_rows,
    need_rows,
    need_spec,
    pin,
    policy,
    write_questions,
    write_run,
)
from plantgraph.qa.cascade import cli
from plantgraph.qa.cascade.evaluate import Summary
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.models import AcceptRule, CascadePolicy, TierSpec
from plantgraph.qa.cascade.report import build_report
from plantgraph.qa.cascade.report_groups import k_bin
from plantgraph.qa.cascade.report_models import Report, Tier3Tally
from plantgraph.qa.cascade.report_render import render_markdown, write_report
from plantgraph.qa.cascade.report_verdicts import (
    check_label_variant,
    confirm_cascade,
    select_tier3,
    tally_tier3,
)


def _summary(correct: int, total_cost: float, n: int = 100) -> Summary:
    return Summary(
        policy="p",
        corpus_id="D1000",
        n_questions=n,
        n_correct=correct,
        total_cost_usd=total_cost,
        cost_per_question_usd=total_cost / n,
        latency_median_s=1.0,
        latency_mean_s=1.0,
        latency_p90_s=1.0,
        tier_shares={},
        tier_calls={},
    )


def _tally(tier: str, correct: int, cost: float, rows: int = 35) -> Tier3Tally:
    return Tier3Tally(
        tier=tier,
        n_runaways=35,
        n_rows=rows,
        n_correct=correct,
        total_cost_usd=cost,
        mean_latency_s=10.0,
    )


# --- S1 ---


def test_s1_picks_the_most_correct_candidate() -> None:
    verdict = select_tier3([_tally("need-mimo", 12, 0.3), _tally("need-low", 9, 0.1)])

    assert verdict.status == "SELECTED"
    assert "need-mimo" in verdict.headline


def test_s1_tie_goes_to_the_cheaper_candidate() -> None:
    tallies = [_tally("need-mimo", 10, 0.3), _tally("need-low", 10, 0.1), _tally("x", 10, 0.2)]

    assert "need-low" in select_tier3(tallies).headline


def test_s1_is_incomplete_while_a_candidate_lacks_rows() -> None:
    verdict = select_tier3([_tally("need-mimo", 12, 0.3), _tally("need-low", 3, 0.1, rows=15)])

    assert verdict.status == "INCOMPLETE"
    assert "need-low" in verdict.headline
    assert any("3/35" in line for line in verdict.details)  # the partial counts stay visible


def test_s1_flags_when_every_candidate_is_below_half() -> None:
    verdict = select_tier3([_tally("a", 17, 0.3), _tally("b", 9, 0.1)])

    assert any("Sonnet" in line for line in verdict.details)
    assert not any("Sonnet" in line for line in select_tier3([_tally("a", 18, 0.3)]).details)


# --- S2 and S3 ---


@pytest.mark.parametrize(
    ("correct", "cost", "status"),
    [
        (98, 5.0, "PASS"),  # exactly 2 behind is allowed
        (97, 5.0, "FAIL"),  # 3 behind
        (110, 6.0, "FAIL"),  # more accurate but not cheaper
        (100, 6.0, "FAIL"),  # equal cost is not "lower"
    ],
)
def test_s2_thresholds(correct: int, cost: float, status: str) -> None:
    always_n = _summary(100, 6.0)

    assert confirm_cascade(_summary(correct, cost), always_n).status == status


def test_s2_is_incomplete_without_both_summaries() -> None:
    assert confirm_cascade(None, _summary(1, 1.0)).status == "INCOMPLETE"
    assert confirm_cascade(_summary(1, 1.0), None).status == "INCOMPLETE"


@pytest.mark.parametrize(
    ("correct", "cost", "status"),
    [
        (102, 12.5, "PASS"),  # exactly 2 ahead at exactly 1.25x
        (101, 10.0, "FAIL"),  # only 1 ahead
        (110, 12.6, "FAIL"),  # too expensive
    ],
)
def test_s3_thresholds(correct: int, cost: float, status: str) -> None:
    verdict = check_label_variant("v", _summary(correct, cost), _summary(100, 10.0))

    assert verdict.status == status


def test_s3_is_incomplete_without_a_summary() -> None:
    assert check_label_variant("v", None, _summary(1, 1.0)).status == "INCOMPLETE"


def test_k_bins() -> None:
    bins = [k_bin(k) for k in (None, 0, 1, 2, 3, 7)]

    assert bins == ["unanswerable", "k=0", "k=1-2", "k=1-2", "k>=3", "k>=3"]


# --- toy report ---


def _mimo_spec() -> TierSpec:
    return TierSpec(
        name="need-mimo",
        strategy=NEED,
        pin_sha256=pin("mimo").pin_hash(),
        accept=frozenset({AcceptRule.ANSWERED}),
    )


def _always(name: str, tier: TierSpec) -> CascadePolicy:
    return CascadePolicy(name=name, tiers=(tier,))


def _toy_sources(tmp_path: Path, with_mimo: bool = False) -> tuple[dict[str, TierSource], Path]:
    questions_root = write_questions(tmp_path / "questions")
    runs_root = tmp_path / "runs"
    cypher = ToyRun("c", CYPHER, "low", cypher_rows())
    need = ToyRun("n", NEED, "default", need_rows())
    sources = {
        "cypher-low": TierSource(write_run(runs_root, questions_root, cypher)),
        "need-default": TierSource(write_run(runs_root, questions_root, need)),
    }
    if with_mimo:
        rows = [r for r in need_rows() if r["question_id"] in ("T1:q3", "T1:q4")]
        mimo = ToyRun("m", NEED, "mimo", rows)
        sources["need-mimo"] = TierSource(write_run(runs_root, questions_root, mimo))
    return sources, questions_root


def _toy_report(tmp_path: Path, policies: list[CascadePolicy] | None = None) -> Report:
    sources, questions_root = _toy_sources(tmp_path)
    chosen = policies or [
        policy(),
        _always("always_n", need_spec()),
        _always("always_c", policy().tiers[0]),
    ]
    return build_report([CORPUS], {CORPUS: sources}, questions_root, chosen)


def test_toy_report_summarises_each_policy(tmp_path: Path) -> None:
    corpus = _toy_report(tmp_path).corpora[0]
    by_name = {r.summary.policy: r for r in corpus.policies}
    toy = by_name["toy"]

    # q1 tier 1 right, q2 and q4 answered by tier 2, q3 fails -> 3 of 4
    assert toy.summary.n_correct == 3
    assert toy.summary.tier_shares == {"cypher-low": 0.25, "need-default": 0.5, "none": 0.25}
    assert toy.acceptance is not None
    assert toy.acceptance.n_accepted == 1
    assert toy.vs_always_n is not None
    assert toy.oracle is not None
    assert toy.random is not None
    assert by_name["always_n"].vs_always_n is None
    assert corpus.not_evaluated == []


def test_breakdowns_cover_every_question_once(tmp_path: Path) -> None:
    corpus = _toy_report(tmp_path).corpora[0]

    assert set(corpus.breakdowns) == {"need label", "family", "k bin"}
    for groups in corpus.breakdowns.values():
        assert sum(cells["toy"].total for cells in groups.values()) == 4
    assert corpus.breakdowns["need label"]["ITEM"]["toy"].total == 2


def test_policy_with_a_missing_tier_is_listed_not_evaluated(tmp_path: Path) -> None:
    three_tiers = CascadePolicy(name="three", tiers=(*policy().tiers, _mimo_spec()))
    report = _toy_report(tmp_path, [three_tiers, _always("always_n", need_spec())])
    corpus = report.corpora[0]

    assert [p.summary.policy for p in corpus.policies] == ["always_n"]
    assert corpus.not_evaluated[0].policy == "three"
    # q3 fails in tier 2 (parse failure) and so reaches the missing tier 3
    assert corpus.not_evaluated[0].gaps == {"need-mimo": 1}
    assert "needed --tier need-mimo" in corpus.not_evaluated[0].reason


def test_shipped_baselines_with_other_pins_are_flagged_not_crashed(tmp_path: Path) -> None:
    report = _toy_report(tmp_path, [policy()])
    flagged = {p.policy for p in report.corpora[0].not_evaluated}

    assert {"always_n", "always_c"} <= flagged  # the real pins do not match the toy runs


def test_report_without_the_confirmation_corpus_is_incomplete(tmp_path: Path) -> None:
    statuses = {v.rule: v.status for v in _toy_report(tmp_path).verdicts}

    assert statuses["S2"] == "INCOMPLETE"
    assert statuses["S3 cascade_v1_iso"] == "INCOMPLETE"
    assert statuses["S1"] == "INCOMPLETE"  # no candidate has a row for the toy runaways


def test_tier3_tally_counts_runaway_answers(tmp_path: Path) -> None:
    sources, questions_root = _toy_sources(tmp_path, with_mimo=True)
    three = CascadePolicy(name="n3", tiers=(need_spec(), _mimo_spec()))
    joined: JoinedCorpus = join_corpus(three, sources, CORPUS, questions_root)

    tally = tally_tier3([joined], "need-mimo")

    # toy runaways: q3 (parse failure) and q4 (token cap)
    assert (tally.n_runaways, tally.n_rows, tally.n_correct) == (2, 2, 2)
    assert tally.total_cost_usd == pytest.approx(0.002)
    assert tally_tier3([joined], "need-low").n_rows == 0


def test_markdown_and_json_files(tmp_path: Path) -> None:
    report = _toy_report(tmp_path)

    markdown_path, json_path = write_report(report, tmp_path / "out")
    markdown = markdown_path.read_text(encoding="utf-8")

    assert markdown == render_markdown(report)
    assert "## Corpus T1 (4 questions)" in markdown
    assert "| toy | 3/4 |" in markdown
    assert "- **S2: INCOMPLETE**" in markdown
    assert "#### By k bin" in markdown
    assert Report.model_validate_json(json_path.read_text(encoding="utf-8")) == report


def test_cli_report_writes_both_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sources, questions_root = _toy_sources(tmp_path)
    policy_path = tmp_path / "toy.json"
    policy_path.write_text(policy().model_dump_json(), encoding="utf-8")
    out = tmp_path / "out"
    cypher_dir = sources["cypher-low"].run_dir
    need_dir = sources["need-default"].run_dir

    cli.main(
        [
            *("report", "--corpus", CORPUS, "--questions-root", str(questions_root)),
            *("--policy", str(policy_path), "--out", str(out)),
            *("--run", f"{CORPUS}:cypher-low={cypher_dir}"),
            *("--run", f"{CORPUS}:need-default={need_dir}"),
        ]
    )

    assert "| toy | 3/4 |" in capsys.readouterr().out
    written = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert written["corpora"][0]["corpus_id"] == CORPUS


def test_cli_rejects_a_run_without_a_corpus() -> None:
    arguments = ["report", "--corpus", "T1", "--questions-root", "q", "--out", "o", "--run", "x=y"]

    with pytest.raises(SystemExit, match="CORPUS:TIER"):
        cli.main(arguments)
