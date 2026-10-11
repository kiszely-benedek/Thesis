"""The sealed-claims report on toy runs, the CLI guard, and the free dev check on D100."""

from __future__ import annotations

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
    policy,
    write_questions,
    write_run,
)
from plantgraph.qa.cascade import cli
from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.corpus_checks import load_corpus_view
from plantgraph.qa.cascade.evaluate import Evaluation, LatencyBound, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, TierSource, join_corpus
from plantgraph.qa.cascade.labels import anchor_finder, labels_from_run_dirs
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policies
from plantgraph.qa.cascade.report import build_report
from plantgraph.qa.cascade.report_render import render_markdown
from plantgraph.qa.cascade.report_sealed import build_sealed
from plantgraph.qa.cascade.report_sealed_models import SealedClaimsReport
from plantgraph.qa.cascade.report_sealed_views import SealedCorpus
from plantgraph.qa.models import QuestionFamily

PRIMARY, TIER2, CYPHER_ONLY = "cascade_v3", "always_g_luna", "always_c_luna"
SPLITS = {"T1:q1": "dev-old", "T1:q2": "dev-old", "T1:q3": "held-out", "T1:q4": "dev-new"}


def _toy_policies() -> list[CascadePolicy]:
    cascade = policy().model_copy(update={"name": PRIMARY})
    return [
        cascade,
        CascadePolicy(name=TIER2, tiers=(need_spec(),)),
        CascadePolicy(name=CYPHER_ONLY, tiers=(cascade.tiers[0],)),
    ]


def _toy_corpus(
    tmp_path: Path, corpus_id: str, n_sheets: int, splits: dict[str, str] | None
) -> SealedCorpus:
    """The four toy questions; q2 belongs to the family the headline leaves out."""
    questions_root = write_questions(tmp_path / "questions")
    runs_root = tmp_path / "runs"
    sources = {
        "cypher-low": TierSource(
            write_run(runs_root, questions_root, ToyRun("c", CYPHER, "low", cypher_rows()))
        ),
        "need-default": TierSource(
            write_run(runs_root, questions_root, ToyRun("n", NEED, "default", need_rows()))
        ),
    }
    _, questions = load_questions_file(questions_root, CORPUS)
    questions = [
        q.model_copy(update={"family": QuestionFamily.LOOP_ACTUATED_VALVE})
        if q.question_id == "T1:q2"
        else q
        for q in questions
    ]
    joins: dict[str, JoinedCorpus] = {
        p.name: join_corpus(p, sources, CORPUS, questions_root) for p in _toy_policies()
    }
    evaluations: dict[str, Evaluation] = {n: evaluate_policy(j) for n, j in joins.items()}
    return SealedCorpus(corpus_id, n_sheets, questions, splits, joins, evaluations)


@pytest.fixture
def sealed(tmp_path: Path) -> SealedClaimsReport:
    small = _toy_corpus(tmp_path / "small", "T1", 10, None)
    large = _toy_corpus(tmp_path / "large", "T1b", 100, SPLITS)
    sealed_part = build_sealed([small, large], LatencyBound())
    return SealedClaimsReport(
        bound=LatencyBound(), corpora=[], tier3=[], verdicts=[], sealed=sealed_part
    )


def test_scope_sizes_leave_out_the_excluded_family(sealed: SealedClaimsReport) -> None:
    assert sealed.sealed.scope_sizes == {
        "T1": {"headline": 3},
        "T1b": {"headline": 3, "held-out": 1},
    }


def test_headline_rows_keep_the_all_question_count_beside(sealed: SealedClaimsReport) -> None:
    row = next(
        r
        for r in sealed.sealed.scope_rows
        if (r.corpus_id, r.scope, r.policy) == ("T1", "headline", PRIMARY)
    )

    assert row.summary.n_questions == 3
    assert row.n_all_questions == 4
    assert row.n_all_correct_at_cutoff == 3  # the toy cascade gets 3 of 4 (see test_cascade_report)


def test_split_table_and_gap_follow_the_splits_file(sealed: SealedClaimsReport) -> None:
    rows = {(r.policy, r.split): r.cell for r in sealed.sealed.split_rows}
    gap = next(g for g in sealed.sealed.gap_rows if g.policy == PRIMARY)

    assert rows[(PRIMARY, "dev-old")].total == 1  # q2 is excluded from dev-old
    assert rows[(PRIMARY, "held-out")].total == 1
    assert {r.corpus_id for r in sealed.sealed.split_rows} == {"T1b"}  # T1 has no splits.json
    assert (gap.dev.total, gap.held_out.total) == (2, 1)


def test_scale_rows_read_the_sheet_counts(sealed: SealedClaimsReport) -> None:
    row = next(r for r in sealed.sealed.scale_rows if r.policy == PRIMARY)

    assert (row.sheets_small, row.sheets_large, row.scope) == (10, 100, "headline")
    assert {r.scope for r in sealed.sealed.scale_rows} == {"headline"}  # T1 has no held-out


def test_claims_cover_every_scope_and_mark_missing_inputs(sealed: SealedClaimsReport) -> None:
    by_rule = {
        (v.rule, v.headline.split("[")[1].split("]")[0]): v
        for v in sealed.sealed.claims
        if v.status != "NOT_RUN"
    }

    assert by_rule[("Q4 (primary) cascade_v3", "headline")].status in ("PASS", "FAIL")
    assert by_rule[("Q4 (primary)", "held-out")].status == "INCOMPLETE"  # no small-corpus held-out
    assert {"K1", "K2", "K3", "Q5"} <= {rule for rule, _ in by_rule}
    assert [v.rule for v in sealed.sealed.claims if v.status == "NOT_RUN"] == ["Q1", "Q2", "Q3"]


def test_k_bin_rows_cover_only_policies_with_a_tier_one_rule(sealed: SealedClaimsReport) -> None:
    assert {r.policy for r in sealed.sealed.k_bin_rows} == {PRIMARY}
    assert {r.k_bin for r in sealed.sealed.k_bin_rows} == {"unanswerable"}  # toy questions: k=None


def test_markdown_shows_the_claims_and_omits_the_dev_rules(sealed: SealedClaimsReport) -> None:
    markdown = render_markdown(sealed)

    assert "## T4 Claims" in markdown
    assert "## T3 Scale" in markdown
    assert "Pre-registered rules (S1-S3" not in markdown


def test_report_json_round_trips(sealed: SealedClaimsReport) -> None:
    assert SealedClaimsReport.model_validate_json(sealed.model_dump_json()) == sealed


def test_one_corpus_cannot_make_scale_tables(tmp_path: Path) -> None:
    only = _toy_corpus(tmp_path, "T1", 10, None)

    with pytest.raises(ValueError, match="at least two corpora"):
        build_sealed([only], LatencyBound())


def test_build_report_refuses_sealed_claims_without_policies_and_corpora_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="--policy and --corpora-root"):
        build_report([CORPUS], {}, tmp_path, None, sealed_claims=True)


def test_cli_refuses_sealed_claims_without_corpora_root(tmp_path: Path) -> None:
    arguments = ["report", "--sealed-claims", "--corpus", "T1", "--questions-root", "q"]
    arguments += ["--out", "o", "--run", "T1:x=y", "--policy", str(tmp_path / "p.json")]
    (tmp_path / "p.json").write_text(policy().model_dump_json(), encoding="utf-8")

    with pytest.raises(SystemExit, match="--policy and --corpora-root"):
        cli.main(arguments)


# --- the free dev check (needs the git-ignored dev runs) ---

RUNS = Path("data/runs/cv1")
HAVE_DATA = all(
    (RUNS / sub).is_dir()
    for sub in (
        "corpora/D100",
        "questions/D100",
        "runs/CYPL2-D100",
        "runs/AGL3-D100",
        "runs/DEV10-D100",
    )
)


@pytest.mark.skipif(not HAVE_DATA, reason="needs the git-ignored data/runs/cv1 dev runs")
def test_dev_d100_numbers_and_finder_labels_reproduce() -> None:
    """cascade_v3 176, always_g_luna 175, always_c_luna 132, cascade_v3_iso 178 of 180."""
    finder = anchor_finder(load_corpus_view(RUNS / "corpora", "D100"))
    sources = {
        "cypher-luna": TierSource(RUNS / "runs" / "CYPL2-D100"),
        "agent-luna": TierSource(RUNS / "runs" / "AGL3-D100"),
    }
    trace_labels = labels_from_run_dirs([RUNS / "runs" / "DEV10-D100"])
    policies = load_policies(POLICIES_DIR)
    correct = {}
    for name in (PRIMARY, TIER2, CYPHER_ONLY, "cascade_v3_iso"):
        joined = join_corpus(policies[name], sources, "D100", RUNS / "questions", finder)
        correct[name] = evaluate_policy(joined, 120.0).summary.n_correct_at_cutoff
    # the rules classifier on the corpus graph must agree with the need-aware run's own labels
    labels = joined.need_labels
    assert {qid: labels[qid] for qid in trace_labels} == trace_labels

    assert correct == {PRIMARY: 176, TIER2: 175, CYPHER_ONLY: 132, "cascade_v3_iso": 178}
