"""Compare two tuning rounds family by family (stop rule 3 of the V2T protocol)."""

from __future__ import annotations

from plantgraph.qa.cascade.tune_models import FamilyChange, TuneReport


def family_changes(current: TuneReport, previous: TuneReport, policy: str) -> list[FamilyChange]:
    """Per-family change of `policy` between two rounds, worst drop first.

    Raises:
        ValueError: the rounds are not on the same corpus and setting.
    """
    if (current.corpus_id, current.setting) != (previous.corpus_id, previous.setting):
        raise ValueError(
            "expected two rounds on the same corpus and setting, found "
            f"{previous.corpus_id}/{previous.setting.name} and "
            f"{current.corpus_id}/{current.setting.name}"
        )
    now, before = current.results[policy].by_family, previous.results[policy].by_family
    changes = [
        FamilyChange(family=family, previous=before[family].correct, current=cell.correct)
        for family, cell in now.items()
    ]
    return sorted(changes, key=lambda change: change.delta)


def regressed_families(changes: list[FamilyChange], min_drop: int = 2) -> list[str]:
    """Families that lost `min_drop` or more questions: the rule asks for a traced reason."""
    return [change.family for change in changes if change.delta <= -min_drop]
