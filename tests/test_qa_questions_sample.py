"""`qa.questions.sample`, the availability report and the CLI (QA-T7), all offline."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest.__main__ import main as ingest_main
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.availability import (
    AvailabilityReport,
    BinTargets,
    KBin,
    k_bin_of,
)
from plantgraph.qa.questions.cli import main as questions_main
from plantgraph.qa.questions.cli import write_question_set
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.questions.sample import draw_sample, generate_question_set

# Arbitrary counts for the tests only: the real ones come from the paid pilot.
_TARGETS = BinTargets(k0=12, k1=9, k2=6, k3_plus=3, unanswerable=8)


def _corpus(budget: int = 16) -> SyntheticCorpus:
    return build_synthetic_corpus(
        GeneratorConfig(n_units=10, seed=0), SplitConfig(sheet_equipment_budget=budget, seed=0)
    )


def _sample(corpus: SyntheticCorpus, seed: int) -> tuple[list[Question], AvailabilityReport]:
    return generate_question_set(
        corpus.plant, corpus.manifest, corpus.sheets, _TARGETS, corpus_id="t7", seed=seed
    )


def test_same_seed_gives_byte_identical_jsonl(tmp_path: Path) -> None:
    corpus = _corpus()
    paths = []
    for run in ("a", "b"):
        questions, report = _sample(corpus, seed=5)
        paths.append(write_question_set(tmp_path / run, questions, report))

    assert paths[0][0].read_bytes() == paths[1][0].read_bytes()
    assert paths[0][1].read_bytes() == paths[1][1].read_bytes()
    assert b"\r" not in paths[0][0].read_bytes()


def test_a_different_seed_draws_a_different_set() -> None:
    corpus = _corpus()

    first, _ = _sample(corpus, seed=1)
    second, _ = _sample(corpus, seed=2)

    assert [q.question_id for q in first] != [q.question_id for q in second]


def test_each_bin_meets_its_target_with_questions_from_that_bin() -> None:
    questions, report = _sample(_corpus(), seed=0)

    drawn = Counter(k_bin_of(q) for q in questions)
    for k_bin in KBin:
        assert drawn[k_bin] == min(_TARGETS.for_bin(k_bin), report.candidates_per_bin[k_bin])
    assert len({q.question_id for q in questions}) == len(questions)


def test_a_bin_is_dealt_round_robin_over_its_families() -> None:
    questions, _ = _sample(_corpus(), seed=0)

    k0_families = [q.family for q in questions if k_bin_of(q) is KBin.K0]

    # 12 questions over the k=0 families: no family may take more than its fair
    # share plus one, which a draw from the pooled candidates would not guarantee.
    counts = Counter(k0_families)
    assert len(counts) >= 6
    assert max(counts.values()) - min(counts.values()) <= 1


def test_a_short_bin_takes_everything_and_is_flagged_underpowered() -> None:
    candidates = all_candidates(*_plant_inputs(_corpus()), corpus_id="t7", seed=0)
    greedy = BinTargets(k0=1, k1=1, k2=1, k3_plus=10_000, unanswerable=1)

    questions, report = draw_sample(candidates, greedy, corpus_id="t7", seed=0)

    assert KBin.K3_PLUS in report.underpowered
    assert report.drawn[KBin.K3_PLUS] == report.candidates_per_bin[KBin.K3_PLUS]
    assert KBin.K0 not in report.underpowered
    assert len(questions) == sum(report.drawn.values())


def _plant_inputs(corpus: SyntheticCorpus):
    return corpus.plant, corpus.manifest, corpus.sheets


def test_availability_report_sums_to_the_candidate_counts() -> None:
    corpus = _corpus()
    candidates = all_candidates(*_plant_inputs(corpus), corpus_id="t7", seed=0)
    _, report = draw_sample(candidates, _TARGETS, corpus_id="t7", seed=0)

    for family, questions in candidates.items():
        assert sum(report.candidates[family].values()) == len(questions)
    for k_bin in KBin:
        assert report.candidates_per_bin[k_bin] == sum(
            row[k_bin] for row in report.candidates.values()
        )
    assert report.n_candidates == sum(len(q) for q in candidates.values())


def test_unanswerable_bin_holds_exactly_the_abstention_families() -> None:
    questions, _ = _sample(_corpus(), seed=0)

    for question in questions:
        in_unanswerable_bin = k_bin_of(question) is KBin.UNANSWERABLE
        assert in_unanswerable_bin == (question.family in _ABSTAIN)
        assert in_unanswerable_bin == (not question.answerable)
        assert (question.k is None) == in_unanswerable_bin


_ABSTAIN = {QuestionFamily.UNANSWERABLE_TAG, QuestionFamily.NO_PATH}


def test_every_answerable_k_is_zero_on_a_one_sheet_corpus() -> None:
    corpus = _corpus(budget=10_000)
    assert len(corpus.sheets) == 1

    questions, report = _sample(corpus, seed=0)

    assert {q.k for q in questions if q.answerable} == {0}
    assert report.candidates_per_bin[KBin.K1] == 0
    assert KBin.K1 in report.underpowered


def test_bin_targets_have_no_default() -> None:
    with pytest.raises(ValueError, match="k0"):
        BinTargets()  # type: ignore[call-arg]


def test_cli_writes_the_jsonl_and_report_from_an_ingest_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ingest_main(
        [
            "synthetic",
            "--n-units",
            "6",
            "--budget",
            "8",
            "--seed",
            "0",
            "--corpus-id",
            "pytest-t7-cli",
            "--no-neo4j",
            "--out",
            str(tmp_path / "ingest"),
        ]
    )
    capsys.readouterr()
    argv = [
        "--corpus-id",
        "pytest-t7-cli",
        "--ingest-json",
        str(tmp_path / "ingest" / "ingest.json"),
        "--seed",
        "0",
        "--out",
        str(tmp_path / "q"),
        "--n-k0",
        "4",
        "--n-k1",
        "3",
        "--n-k2",
        "2",
        "--n-k3-plus",
        "1",
        "--n-unanswerable",
        "3",
    ]

    questions_main(argv)

    lines = (tmp_path / "q" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
    report = AvailabilityReport.model_validate_json(
        (tmp_path / "q" / "availability.json").read_text(encoding="utf-8")
    )
    assert len(lines) == sum(report.drawn.values())
    assert all(Question.model_validate_json(line).corpus_id == "pytest-t7-cli" for line in lines)
