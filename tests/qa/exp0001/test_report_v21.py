"""The ladder report takes EXP-0008 ids such as `H30g21`; the v1 and v2 ids still work."""

from __future__ import annotations

import pytest
from report_toy import scores

from plantgraph.qa.exp0001.report import LADDER_IDS_V2, LADDER_IDS_V21, build_ladder_report
from plantgraph.qa.exp0001.report_claims import V2_EDITION, _nominal_sheets
from plantgraph.qa.exp0001.report_load import CorpusScores
from plantgraph.qa.exp0001.report_models import CASCADE, CTX_HIGH, SizePoint

SHEETS = {"H1g21": 1, "H3g21": 3, "H10g21": 10, "H30g21": 30}


@pytest.mark.parametrize(
    ("corpus_id", "expected"),
    [("H30", 30), ("H30g2", 30), ("H30g21", 30), ("H1000g21", 1000)],
)
def test_nominal_sheets_parse_every_generation(corpus_id: str, expected: int) -> None:
    assert _nominal_sheets(corpus_id) == expected


@pytest.mark.parametrize("corpus_id", ["H30g", "H30g2x", "X30g21", "H30g21p1"])
def test_nominal_sheets_refuse_other_ids(corpus_id: str) -> None:
    with pytest.raises(ValueError, match="expected a corpus id like"):
        _nominal_sheets(corpus_id)


def _corpus(corpus_id: str, n_sheets: int) -> CorpusScores:
    arms = {
        CASCADE: scores([True] * 20, ["A", "B"]),
        CTX_HIGH: scores([True] * 20, ["A", "B"]),
    }
    size = SizePoint(
        corpus_id=corpus_id,
        n_sheets=n_sheets,
        n_occurrence_nodes=100 * n_sheets,
        ctx_prompt_chars=None,
        ctx_prompt_tokens_median=None,
        chars_per_token=None,
    )
    return CorpusScores(size=size, scores=arms, families=frozenset({"A", "B"}), ctx_calls=[])


def test_the_v21_ladder_reports_its_largest_size_from_the_id() -> None:
    corpora = [_corpus(corpus_id, n) for corpus_id, n in SHEETS.items()]

    report = build_ladder_report(corpora, 120.0, LADDER_IDS_V21, None, V2_EDITION)

    x3 = next(c for c in report.claims if c.id == "X3")
    assert x3.value.startswith("no accuracy flip up to 30 sheets")
    assert LADDER_IDS_V2 == ("H1g2", "H3g2", "H10g2", "H30g2")  # the first measurement's ids stay
