"""Scoring, bootstrap, tuning rule and report of EXP-0004's free path, on a scripted toy (X-T5).

The toy has six candidate pairs in three blocks:

    block A: pair 0 (true, format), pair 1 (false, format)
    block B: pair 2 (true, naming), pair 3 (true, naming)
    block C: pair 4 (false, no variant), pair 5 (true, format)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.eval.blocking_metrics import BlockingMetrics
from plantgraph.eval.resolution_scoring import PairScore
from plantgraph.exp0004 import commands
from plantgraph.exp0004.bootstrap import interval_of, paired_difference, resample_f1
from plantgraph.exp0004.corpus import CorpusSpec, corpus_id_for
from plantgraph.exp0004.deciders import DeciderRun, make_decider
from plantgraph.exp0004.description import CorpusDescription, CorpusFile
from plantgraph.exp0004.metrics import Counts, prf_of
from plantgraph.exp0004.pairs import NONE, PairRecord
from plantgraph.exp0004.report import render_report
from plantgraph.exp0004.scoring import score_corpus
from plantgraph.exp0004.storage import corpus_path, write_model
from plantgraph.exp0004.tuning import TuningRow, pick_best
from plantgraph.resolution.identity_candidates import ContentKey
from plantgraph.resolution.identity_links import IdentityLinkSet

_CLASS = "CentrifugalPump"


def _pair(index: int, block: str, is_true: bool, family: str) -> PairRecord:
    return PairRecord(
        index=index,
        first=ContentKey("S1", f"P-{index}", _CLASS),
        second=ContentKey("S2", f"P{index}", _CLASS),
        block=block,
        is_true=is_true,
        family=family,
        operator="op" if family != NONE else NONE,
    )


TOY_PAIRS = [
    _pair(0, "A", True, "format"),
    _pair(1, "A", False, "format"),
    _pair(2, "B", True, "naming"),
    _pair(3, "B", True, "naming"),
    _pair(4, "C", False, NONE),
    _pair(5, "C", True, "format"),
]


def _run(name: str, said_same: list[bool]) -> DeciderRun:
    empty_score = PairScore(
        true_positives=0, false_positives=0, false_negatives=0, precision=None, recall=None, f1=None
    )
    return DeciderRun(
        decider=name,
        threshold=None,
        link_set=IdentityLinkSet(decider=name, links=[]),
        said_same=said_same,
        pair_level=prf_of(Counts(0, 0, 0)),
        group_level=empty_score,
        n_dropped_one_to_one=0,
        n_identity_conflicts=0,
    )


# pair 3 is missed, everything else right: tp 3, fp 0, fn 1
GOOD = _run("d1", [True, False, True, False, False, True])
# says yes to everything: tp 4, fp 2, fn 0
EAGER = _run("d2", [True] * 6)


def test_point_scores_per_subset() -> None:
    score = score_corpus("toy", TOY_PAIRS, [GOOD], n_resamples=50)
    subsets = score.deciders[0].subsets
    assert set(subsets) == {"all", "format", "naming"}
    assert (subsets["all"].prf.tp, subsets["all"].prf.fp, subsets["all"].prf.fn) == (3, 0, 1)
    assert subsets["all"].prf.f1 == pytest.approx(2 * 1.0 * 0.75 / 1.75)
    assert subsets["format"].prf.f1 == 1.0  # pairs 0, 1, 5 all answered right
    assert subsets["naming"].prf.recall == 0.5  # pair 2 found, pair 3 missed
    assert score.n_blocks == 3


def test_per_operator_counts_true_pairs_only() -> None:
    score = score_corpus("toy", TOY_PAIRS, [GOOD], n_resamples=10)
    assert score.deciders[0].per_operator["op"].gold == 4
    assert score.deciders[0].per_operator["op"].recovered == 3


def test_contrasts_are_later_minus_earlier_and_family_minus_next() -> None:
    score = score_corpus("toy", TOY_PAIRS, [GOOD, EAGER], n_resamples=50)
    pairs = {(c.plus, c.minus) for c in score.contrasts}
    assert ("d2|all", "d1|all") in pairs  # decider contrast
    assert ("d1|format", "d1|naming") in pairs  # family contrast
    family = next(c for c in score.contrasts if (c.plus, c.minus) == ("d1|format", "d1|naming"))
    assert family.estimate == pytest.approx(1.0 - 2 * 1.0 * 0.5 / 1.5)


def test_bootstrap_is_seeded_and_reproducible() -> None:
    first = score_corpus("toy", TOY_PAIRS, [GOOD, EAGER], n_resamples=200, seed=7)
    again = score_corpus("toy", TOY_PAIRS, [GOOD, EAGER], n_resamples=200, seed=7)
    other = score_corpus("toy", TOY_PAIRS, [GOOD, EAGER], n_resamples=200, seed=8)
    assert first.model_dump() == again.model_dump()
    assert first.model_dump() != other.model_dump()


def test_identical_deciders_have_a_zero_paired_difference() -> None:
    twin = _run("d2", list(GOOD.said_same))
    score = score_corpus("toy", TOY_PAIRS, [GOOD, twin], n_resamples=100)
    same = next(c for c in score.contrasts if (c.plus, c.minus) == ("d2|all", "d1|all"))
    assert (same.estimate, same.ci.low, same.ci.high) == (0.0, 0.0, 0.0)


def test_bootstrap_resamples_whole_blocks() -> None:
    # two blocks, one pure hit and one pure false positive: only whole-block mixes can occur
    blocks = [{"m": Counts(1, 0, 0)}, {"m": Counts(0, 1, 0)}]
    values = resample_f1(blocks, ["m"], n_resamples=100, seed=1)["m"]
    assert set(values) <= {1.0, 2 / 3, 0.0}  # (2,0), (1,1) and (0,2) copies of the blocks
    assert len(set(values)) > 1


def test_interval_and_difference_helpers() -> None:
    assert paired_difference([0.5, None, 0.9], [0.1, 0.2, None]) == pytest.approx([0.4])
    ci = interval_of([float(i) for i in range(1001)])
    assert (ci.low, ci.high) == (25.0, 975.0)
    assert interval_of([None]).low is None


def test_misaligned_decision_file_is_refused() -> None:
    with pytest.raises(ValueError, match="another corpus"):
        score_corpus("toy", TOY_PAIRS, [_run("d1", [True])], n_resamples=5)


def test_tuning_tie_goes_to_the_higher_threshold() -> None:
    rows = [TuningRow(tau=0.5, f1=0.9), TuningRow(tau=0.8, f1=0.9), TuningRow(tau=1.0, f1=0.8)]
    assert pick_best(rows) == 0.8
    assert pick_best([TuningRow(tau=0.4, f1=None), TuningRow(tau=0.6, f1=None)]) == 0.6
    with pytest.raises(ValueError, match="at least one"):
        pick_best([])


def test_tuning_refuses_a_test_seed(tmp_path: Path) -> None:
    spec = CorpusSpec(
        corpus_id="H100g2d100V",
        target_sheets=100,
        seed=5002,
        duplication_rate=1.0,
        families=("format",),
    )
    blocking = BlockingMetrics(
        n_candidates=0, n_all_pairs=0, n_gold_links=0, n_gold_links_found=0,
        pair_completeness=None, reduction_ratio=None,
    )  # fmt: skip
    description = CorpusDescription(
        n_units=1, n_sheets=1, generate_s=0.0, n_identity_groups=0, n_variant_draws=0,
        blocking=blocking, n_candidates_true=0, n_candidates_false=0, units_agree_true=0,
        units_agree_false=0, n_ambiguous_occurrences=0, n_without_digits=0,
    )  # fmt: skip
    write_model(corpus_path(tmp_path), CorpusFile(spec=spec, description=description))
    with pytest.raises(ValueError, match="dev"):
        commands.tune_thresholds(tmp_path)


def test_decider_ids_and_thresholds() -> None:
    assert make_decider("d0", None).name == "d0"
    assert make_decider("d2", 0.9).name == "d2"
    with pytest.raises(ValueError, match="threshold"):
        make_decider("d1", None)
    with pytest.raises(ValueError, match="decider id"):
        make_decider("d9", 0.5)


def test_corpus_ids_follow_the_design() -> None:
    assert corpus_id_for(100, 1, 1.0, ["format"]) == "D100g2d100Vf"
    assert corpus_id_for(1000, 5003, 1.0, ["naming", "format"]) == "H1000g2d100V"
    assert corpus_id_for(100, 5002, 0.25, ["format", "naming"]) == "H100g2V"
    with pytest.raises(ValueError, match="duplication rate"):
        corpus_id_for(100, 1, 0.5, ["format"])


def test_report_renders_the_scripted_toy() -> None:
    score = score_corpus("toy", TOY_PAIRS, [GOOD, EAGER], n_resamples=50)
    text = render_report([score])
    assert text.startswith("## toy")
    assert "6 candidate pairs in 3 blocks" in text
    assert "| d1 | n/a | all | 1.000 | 0.750 | 0.857 |" in text
    assert "| d2 | d1 |" not in text  # contrasts are metrics: "d2|all" minus "d1|all"
    assert "| d2|all | d1|all |" in text
    with pytest.raises(ValueError, match="at least one"):
        render_report([])
