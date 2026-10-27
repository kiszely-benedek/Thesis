"""The report on v2 plants: corpus ids with `g2`, X6 not run, stage C not applicable, wall chars."""

from __future__ import annotations

import argparse

import pytest
from report_toy import scores

from plantgraph.qa.exp0001.prompt_size import (
    PRICE_STEP_TOKENS,
    WINDOW_TOKENS,
    estimate_tokens,
    parse_corpus_args,
    size_from_counts,
)
from plantgraph.qa.exp0001.report import LADDER_IDS_V2, build_ladder_report
from plantgraph.qa.exp0001.report_claims import V2_EDITION, WallSettings
from plantgraph.qa.exp0001.report_cli import _wall_settings, parse_wall_chars
from plantgraph.qa.exp0001.report_load import CorpusScores, CtxCall
from plantgraph.qa.exp0001.report_models import CASCADE, CTX_HIGH, SizePoint

N = 20
SHEETS = {"H1g2": 1, "H3g2": 3, "H10g2": 10, "H30g2": 30}


def _corpus(corpus_id: str, with_ctx: bool) -> CorpusScores:
    sheets = SHEETS[corpus_id]
    chars = 800 + 40_000 * sheets
    size = SizePoint(
        corpus_id=corpus_id,
        n_sheets=sheets,
        n_occurrence_nodes=100 * sheets,
        ctx_prompt_chars=chars if with_ctx else None,
        ctx_prompt_tokens_median=chars // 3 if with_ctx else None,
        chars_per_token=3.0 if with_ctx else None,
    )
    arms = {CASCADE: scores([True] * N, ["A", "B"])}
    calls = []
    if with_ctx:
        arms[CTX_HIGH] = scores([True] * N, ["A", "B"])
        calls = [CtxCall(chars, chars // 3)] * 3
    return CorpusScores(size=size, scores=arms, families=frozenset({"A", "B"}), ctx_calls=calls)


def _report(with_ctx: bool = True, wall: WallSettings | None = None):  # type: ignore[no-untyped-def]
    corpora = [_corpus(cid, with_ctx) for cid in SHEETS]
    return build_ladder_report(corpora, 120.0, LADDER_IDS_V2, wall, V2_EDITION)


def _claim(report, claim_id: str):  # type: ignore[no-untyped-def]
    return next(c for c in report.claims if c.id == claim_id)


def test_x6_is_reported_as_not_run_on_v2() -> None:
    claim = _claim(_report(), "X6")
    assert (claim.verdict, claim.value) == ("NOT_RUN", "not run on v2 (ADR-0060), see EXP-0001")


def test_x3_says_stage_c_is_not_applicable_on_v2() -> None:
    value = _claim(_report(), "X3").value
    assert value == "no accuracy flip up to 30 sheets; stage C not applicable on v2 (ADR-0060)"


def test_a_tier_only_report_has_no_contextrag_claims_but_scores_the_cascade() -> None:
    report = _report(with_ctx=False)
    assert _claim(report, "X1").verdict == "NOT_RUN"
    assert _claim(report, "X5").verdict == "NOT_RUN"
    assert {c.policy for c in report.cells} == {CASCADE}


def test_x5_lists_only_the_big_corpora_it_was_given() -> None:
    wall = WallSettings(big_prompts=(("H100g2", 3_948_282),))
    value = _claim(_report(wall=wall), "X5").value
    assert "H100g2 (3,948,282 chars" in value and "does not fit" in value
    assert "H1000" not in value


def test_x5_without_big_corpora_still_gives_the_wall() -> None:
    value = _claim(_report(wall=WallSettings(big_prompts=())), "X5").value
    assert "c = 40,000 chars/sheet" in value and "fit" not in value.split("sheets (window")[1]


def test_wall_chars_are_parsed_and_malformed_items_refused() -> None:
    assert parse_wall_chars("H100g2=10,H1000g2=20") == (("H100g2", 10), ("H1000g2", 20))
    for bad in ("H100g2", "H100g2=", "=5", "H100g2=-3", "H100g2=0"):
        with pytest.raises(ValueError, match="H100g2=3948282"):
            parse_wall_chars(bad)


def test_v1_defaults_stay_and_v2_has_no_default_big_corpora() -> None:
    v1 = argparse.Namespace(wall_chars=None, edition="v1", max_prompt_tokens=922_000)
    v2 = argparse.Namespace(wall_chars=None, edition="v2", max_prompt_tokens=922_000)
    assert [name for name, _ in _wall_settings(v1).big_prompts] == ["H100", "H1000"]
    assert _wall_settings(v2).big_prompts == ()


def test_prompt_size_thresholds_follow_the_token_estimate() -> None:
    small = size_from_counts("X", sheets=1, nodes=10, context_chars=10_000)
    assert small.prompt_chars == 12_087 and small.est_prompt_tokens == estimate_tokens(12_087)
    assert not small.above_price_step and small.fits_window
    step_chars = int((PRICE_STEP_TOKENS + 185) / 0.39414)
    assert size_from_counts("X", 1, 1, step_chars).above_price_step
    wall_chars = int((WINDOW_TOKENS + 185) / 0.39414)
    assert not size_from_counts("X", 1, 1, wall_chars + 10_000).fits_window


def test_prompt_size_refuses_an_empty_corpus_and_bad_arguments() -> None:
    with pytest.raises(ValueError, match="at least one sheet"):
        size_from_counts("X", 0, 5, 100)
    with pytest.raises(ValueError, match="ID=ingest.json"):
        parse_corpus_args(["D100g2"])
    assert parse_corpus_args(["D1=a/b.json"])[0][0] == "D1"
