"""The package reproduces the committed IDBLOCK-01 result on the 100-sheet dev corpus (X-T5).

`data/runs/exp0004/idblock01/D100g2d100Vf/result.json` was written by the prototype
`data/runs/exp0004/idblock01.py`. Building the plant takes about 10 s, so one module-scoped run
serves every check. The 1,000-sheet corpus is checked by hand, not here (too slow for a unit test).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from plantgraph.exp0004 import commands
from plantgraph.exp0004.corpus import Corpus, CorpusSpec
from plantgraph.exp0004.deciders import DeciderRun, make_decider, run_decider
from plantgraph.exp0004.description import describe
from plantgraph.exp0004.pairs import build_pair_records
from plantgraph.exp0004.scoring import score_corpus
from plantgraph.exp0004.storage import decision_path, links_path
from plantgraph.exp0004.tuning import Taus, TuningRow, tune
from plantgraph.ingest.identity_file import read_identity_links

COMMITTED = Path(__file__).parent.parent / "data/runs/exp0004/idblock01/D100g2d100Vf/result.json"
SPEC = CorpusSpec(
    corpus_id="D100g2d100Vf", target_sheets=100, seed=1, duplication_rate=1.0, families=("format",)
)


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return Corpus(SPEC)


@pytest.fixture(scope="module")
def tuned(corpus: Corpus) -> tuple[Taus, dict[str, list[TuningRow]]]:
    return tune(corpus)


@pytest.fixture(scope="module")
def runs(corpus: Corpus, tuned: tuple[Taus, Any]) -> list[DeciderRun]:
    taus, _ = tuned
    return [
        run_decider(corpus, make_decider("d0", None)),
        run_decider(corpus, make_decider("d1", taus.tau1)),
        run_decider(corpus, make_decider("d2", taus.tau2)),
    ]


def test_tuned_thresholds_match(
    tuned: tuple[Taus, dict[str, list[TuningRow]]], committed: dict[str, Any]
) -> None:
    taus, trace = tuned
    assert (taus.tau1, taus.tau2) == (committed["taus"]["tau1"], committed["taus"]["tau2"])
    assert len(trace["d1"]) == len(committed["tuning_trace"]["d1"])


def test_corpus_counts_and_blocking_gate_match(corpus: Corpus, committed: dict[str, Any]) -> None:
    description = describe(corpus, build_pair_records(corpus))
    assert description.blocking.model_dump() == committed["blocking"]
    assert description.n_candidates_true == committed["n_candidates_true"]
    assert description.units_agree_false == committed["units_agree_false"]


def test_pair_level_and_group_level_scores_match(
    runs: list[DeciderRun], committed: dict[str, Any]
) -> None:
    for run, expected in zip(runs, committed["scores"], strict=True):
        assert run.decider == expected["decider"]
        assert run.pair_level.model_dump() == _with_zero_f1(expected["pair_level"])
        assert run.group_level.model_dump() == expected["group_level"]
        assert run.n_dropped_one_to_one == expected["n_dropped_one_to_one"]
        assert run.n_identity_conflicts == expected["n_identity_conflicts"]
    assert runs[1].pair_level.f1 == 0.9058823529411765
    assert runs[2].pair_level.f1 == 0.983957219251337


def _with_zero_f1(pair_level: dict[str, Any]) -> dict[str, Any]:
    """The prototype wrote F1 None for a decider that accepts nothing; the package writes 0.0.

    The package defines F1 as 2tp / (2tp + fp + fn), the bootstrap's definition, so the point
    estimate and its interval agree. Only that one case differs; every count must still match.
    """
    if pair_level["f1"] is None and pair_level["tp"] == 0 and pair_level["fn"] > 0:
        return {**pair_level, "f1": 0.0}
    return pair_level


def test_per_operator_recovery_matches(
    runs: list[DeciderRun], corpus: Corpus, committed: dict[str, Any]
) -> None:
    score = score_corpus("D100g2d100Vf", build_pair_records(corpus), runs, n_resamples=20)
    for decider in score.deciders:
        expected = committed["per_operator"][decider.decider]
        got = {op: r.model_dump() for op, r in decider.per_operator.items()}
        assert got == expected


def test_files_round_trip_through_the_commands(tmp_path: Path) -> None:
    directory = tmp_path / "D100"
    commands.build(SPEC, directory)
    taus_file = tmp_path / "taus.json"
    taus_file.write_text('{"tau1": 1.0, "tau2": 0.857142857143}', encoding="utf-8")
    run = commands.decide(directory, "d2", taus_file)
    assert run.pair_level.f1 == 0.983957219251337
    assert decision_path(directory, "d2").exists()

    score = commands.score(directory, n_resamples=50)
    assert score.deciders[0].decider == "d2"
    assert score.n_pairs == 200

    # the link file is what `ingest --identity-links` reads
    links = commands.write_links(directory, "d2")
    link_set, _ = read_identity_links(links)
    assert links == links_path(directory, "d2")
    assert len(link_set.links) > 0
    with pytest.raises(FileExistsError):
        commands.write_links(directory, "d2")
