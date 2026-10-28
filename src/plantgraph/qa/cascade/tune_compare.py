"""Compare two tuning rounds family by family (stop rule 3 of the V2T protocol)."""

from __future__ import annotations

from plantgraph.qa.cascade.tune_models import FamilyChange, RoundChange, TuneReport


def _require_same_scope(current: TuneReport, previous: TuneReport) -> None:
    if (current.corpus_id, current.setting) != (previous.corpus_id, previous.setting):
        raise ValueError(
            "expected two rounds on the same corpus and setting, found "
            f"{previous.corpus_id}/{previous.setting.name} and "
            f"{current.corpus_id}/{current.setting.name}"
        )


def round_change(current: TuneReport, previous: TuneReport, policy: str) -> RoundChange:
    """Which questions `policy` newly got right (fixed) or newly got wrong (broken), uncut.

    Raises:
        ValueError: the rounds are not on the same corpus and setting, or lack per-question data.
    """
    _require_same_scope(current, previous)
    now, before = current.results[policy], previous.results[policy]
    if (
        len(now.correct_ids) != now.n_correct_uncut
        or len(before.correct_ids) != before.n_correct_uncut
    ):
        raise ValueError(
            f"expected per-question correct ids in both rounds for {policy}, found none"
        )
    return RoundChange(
        fixed=sorted(set(now.correct_ids) - set(before.correct_ids)),
        broken=sorted(set(before.correct_ids) - set(now.correct_ids)),
    )


def family_changes(current: TuneReport, previous: TuneReport, policy: str) -> list[FamilyChange]:
    """Per-family change of `policy` between two rounds, worst drop first.

    Raises:
        ValueError: the rounds are not on the same corpus and setting.
    """
    _require_same_scope(current, previous)
    now, before = current.results[policy].by_family, previous.results[policy].by_family
    changes = [
        FamilyChange(family=family, previous=before[family].correct, current=cell.correct)
        for family, cell in now.items()
    ]
    return sorted(changes, key=lambda change: change.delta)


def regressed_families(changes: list[FamilyChange], min_drop: int = 2) -> list[str]:
    """Families that lost `min_drop` or more questions: the rule asks for a traced reason."""
    return [change.family for change in changes if change.delta <= -min_drop]


#: Stop rule 2 (design 7.3): a round that fixed fewer questions than this ends the tuning.
MIN_FIXED_PER_ROUND = 3


def round_verdict(change: RoundChange, min_fixed: int = MIN_FIXED_PER_ROUND) -> str:
    """One line on stop rule 2 for one setting."""
    state = "fixed too few: stop rule 2" if len(change.fixed) < min_fixed else "still improving"
    return f"fixed {len(change.fixed)}, broke {len(change.broken)} ({state}, needs {min_fixed})"
