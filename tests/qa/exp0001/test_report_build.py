"""The report's claims and tables on synthetic scores whose answers are known by construction."""

from __future__ import annotations

import pytest
from report_toy import scores

from plantgraph.qa.exp0001.ladder_stats import ols_slope
from plantgraph.qa.exp0001.report import build_ladder_report
from plantgraph.qa.exp0001.report_cells import EXCLUDED_FAMILY
from plantgraph.qa.exp0001.report_load import CorpusScores, CtxCall
from plantgraph.qa.exp0001.report_models import (
    CASCADE,
    CTX_HIGH,
    CTX_LOW,
    SCOPE_ALL,
    SCOPE_COMMON,
    LadderReport,
    QuestionScore,
    SizePoint,
)

N = 40
FAMILIES = ["A", "B"]
SHEETS = {"H1": 1, "H3": 3, "H10": 10, "H30": 30}
#: ContextRAG-high wrong answers per size; the cascade is always right: delta = 0, -.1, -.2, -.3.
CTX_WRONG = {"H1": 0, "H3": 4, "H10": 8, "H30": 12}


def _ctx_correct(wrong: int) -> list[bool]:
    return [i >= wrong for i in range(N)]


def _corpus(corpus_id: str, ctx_wrong: int, with_low: bool = False, **kw: float) -> CorpusScores:
    sheets = SHEETS[corpus_id]
    chars = 800 + 16_000 * sheets  # r = 3 chars/token, 16,000 chars per sheet, 800 template
    size = SizePoint(
        corpus_id=corpus_id, n_sheets=sheets, n_occurrence_nodes=40 * sheets,
        ctx_prompt_chars=chars, ctx_prompt_tokens_median=chars // 3, chars_per_token=3.0,
    )  # fmt: skip
    arms = {
        CTX_HIGH: scores(
            _ctx_correct(ctx_wrong), FAMILIES, cost=0.001 * sheets, latency=2.0 * sheets
        ),
        CASCADE: scores([True] * N, FAMILIES, cost=0.002, latency=3.0),
    }
    if with_low:
        arms[CTX_LOW] = scores(
            _ctx_correct(ctx_wrong + 2), FAMILIES, cost=0.0005 * sheets, latency=1.0
        )
    calls = [CtxCall(chars, chars // 3)] * 3
    return CorpusScores(size=size, scores=arms, families=frozenset(FAMILIES), ctx_calls=calls)


def _report(low_at: tuple[str, ...] = ("H1", "H10")) -> LadderReport:
    corpora = [_corpus(cid, wrong, cid in low_at) for cid, wrong in CTX_WRONG.items()]
    return build_ladder_report(corpora, cutoff_s=120.0)


def _claim(report: LadderReport, claim_id: str):  # type: ignore[no-untyped-def]
    return next(c for c in report.claims if c.id == claim_id)


def test_trend_matches_the_hand_computed_slope() -> None:
    report = _report()
    xs = [0.0, 0.47712125, 1.0, 1.47712125]
    expected = ols_slope(xs, [0.0, -0.1, -0.2, -0.3])
    assert report.trends[0].slope == pytest.approx(expected, abs=1e-6)
    assert report.trends[0].sizes == ["H1", "H3", "H10", "H30"]


def test_x1_passes_when_the_gap_widens_with_size() -> None:
    claim = _claim(_report(), "X1")
    assert claim.verdict == "PASS"
    assert claim.wording == "The single-sheet advantage of ContextRAG shrinks with corpus size"


def test_x2_non_inferiority_on_one_sheet_when_the_arms_agree() -> None:
    assert _claim(_report(), "X2").verdict == "PASS"  # delta(H1) is exactly 0, CI [0, 0]


def test_x2_fails_when_contextrag_is_much_worse_on_one_sheet() -> None:
    corpora = [_corpus("H1", 12), _corpus("H3", 12)]  # delta(H1) = -0.3
    assert _claim(build_ladder_report(corpora, 120.0), "X2").verdict == "FAIL"


def test_paired_delta_at_each_size_is_the_difference_of_accuracies() -> None:
    report = _report()
    got = {
        d.corpus_id: d.delta
        for d in report.deltas
        if (d.scope, d.a, d.metric) == (SCOPE_COMMON, CTX_HIGH, "acc@120")
    }
    assert got == pytest.approx({"H1": 0.0, "H3": -0.1, "H10": -0.2, "H30": -0.3})


def test_x3_names_the_first_size_whose_interval_is_below_zero() -> None:
    claim = _claim(_report(), "X3")
    assert claim.value == "s_acc = H3, between H1 and H3"
    assert claim.verdict == "REPORTED"


def test_x3_without_a_flip_makes_stage_c_eligible() -> None:
    corpora = [_corpus(cid, 0) for cid in SHEETS]  # ceiling: both arms always right
    report = build_ladder_report(corpora, 120.0)
    assert (
        _claim(report, "X3").value == "no accuracy flip up to 30 sheets; stage C becomes eligible"
    )
    flat = _claim(report, "X1")
    assert flat.verdict == "FAIL"  # slope 0, CI [0, 0]: upper bound is not below 0


def test_x4_cost_and_latency_flip_sizes() -> None:
    value = _claim(_report(), "X4").value
    # ctx costs 0.001*sheets against 0.002: more from 3 sheets; latency 2*sheets s against 3 s
    assert value.startswith("s_cost = H3; s_lat = H3;")
    assert "H1 0.50" in value and "H30 15.00" in value


def test_x5_wall_from_the_measured_ratio() -> None:
    claim = _claim(_report(), "X5")
    assert "r = 3.00 chars/token" in claim.value
    assert "c = 16,000 chars/sheet" in claim.value
    assert "W = 173 sheets" in claim.value  # 922,000 * 3 / 16,000 = 172.9
    assert "H100 (1,649,451 chars" in claim.value and "fits" in claim.value
    assert "H1000 (16,747,117 chars" in claim.value and "does not fit" in claim.value
    assert _report().wall_sheets == pytest.approx(172.875, rel=1e-3)


def test_x6_uses_only_the_sizes_where_contextrag_low_ran() -> None:
    report = _report(low_at=("H1", "H10"))
    value = _claim(report, "X6").value
    assert value.startswith("H1:") and "H10:" in value and "H3" not in value and "H30" not in value
    pairs = {(d.corpus_id, d.metric) for d in report.deltas if d.a == CTX_LOW}
    assert pairs == {("H1", "acc@120"), ("H1", "cost_usd"), ("H10", "acc@120"), ("H10", "cost_usd")}


def test_x6_not_run_when_contextrag_low_is_missing_everywhere() -> None:
    claim = _claim(_report(low_at=()), "X6")
    assert claim.verdict == "NOT_RUN"


def test_effort_deltas_have_known_values() -> None:
    report = _report(low_at=("H1",))
    accuracy = next(d for d in report.deltas if d.a == CTX_LOW and d.metric == "acc@120")
    cost = next(d for d in report.deltas if d.a == CTX_LOW and d.metric == "cost_usd")
    assert accuracy.delta == pytest.approx(-0.05)  # low is wrong on 2 more of 40 questions
    assert cost.delta == pytest.approx(0.0005 - 0.001)


def test_common_scope_drops_a_family_missing_at_one_size() -> None:
    corpora = [_corpus(cid, wrong) for cid, wrong in CTX_WRONG.items()]
    corpora[0].families = frozenset({"A"})  # H1 has no family B
    report = build_ladder_report(corpora, 120.0)
    assert report.scope_families[SCOPE_COMMON] == ["A"]
    common_n = {c.n for c in report.cells if c.scope == SCOPE_COMMON}
    assert common_n == {N // 2}  # only family A's questions are counted at every size


def test_the_excluded_family_is_never_counted() -> None:
    corpus = _corpus("H1", 0)
    families = ["A", EXCLUDED_FAMILY]
    corpus.scores = {
        CTX_HIGH: scores([True] * 10, families),
        CASCADE: scores([True] * 10, families),
    }
    corpus.families = frozenset(families)
    other = _corpus("H3", 0)
    report = build_ladder_report([corpus, other], 120.0)
    cell = next(
        c for c in report.cells if (c.corpus_id, c.policy, c.scope) == ("H1", CTX_HIGH, SCOPE_ALL)
    )
    assert cell.n == 5  # 10 questions, half in the excluded family
    assert EXCLUDED_FAMILY not in report.scope_families[SCOPE_COMMON]


def test_cell_numbers_for_a_known_arm() -> None:
    cell = next(
        c for c in _report().cells
        if (c.corpus_id, c.policy, c.scope) == ("H3", CTX_HIGH, SCOPE_ALL)
    )  # fmt: skip
    assert (cell.n, cell.correct_at_120) == (40, 36)
    assert cell.acc_at_120.estimate == pytest.approx(0.9)
    assert cell.cost_mean == pytest.approx(0.003)
    assert cell.latency_median == pytest.approx(6.0)
    assert cell.outcomes["ANSWERED"] == 40 and cell.outcomes["TIMED_OUT"] == 0


def test_a_single_ladder_size_gives_no_trend_and_x1_not_run() -> None:
    report = build_ladder_report([_corpus("H1", 0)], 120.0)
    assert report.trends == []
    assert _claim(report, "X1").verdict == "NOT_RUN"


def test_arms_scored_on_different_questions_are_refused() -> None:
    corpus = _corpus("H1", 0)
    shifted: list[QuestionScore] = [
        s.model_copy(update={"qid": f"x{i}"}) for i, s in enumerate(corpus.scores[CASCADE])
    ]
    corpus.scores[CASCADE] = shifted
    with pytest.raises(ValueError, match="same questions"):
        build_ladder_report([corpus, _corpus("H3", 0)], 120.0)


def test_x5_is_not_run_when_prompt_size_does_not_grow_with_sheets() -> None:
    corpora = [_corpus("H1", 0), _corpus("H3", 0)]
    for corpus in corpora:  # same prompt length at both sizes: the per-sheet fit is 0
        corpus.size = corpus.size.model_copy(update={"ctx_prompt_chars": 5000})
    claim = _claim(build_ladder_report(corpora, 120.0), "X5")
    assert claim.verdict == "NOT_RUN" and "not positive" in claim.value
