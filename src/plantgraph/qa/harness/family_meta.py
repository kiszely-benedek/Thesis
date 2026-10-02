"""What the harness knows about each question family that strategies must not: split and gold need.

Gold side (design `question-aware-retrieval.md` §8.1): a strategy that could read a family's
split could tune itself to the dev families, so strategies never import this module.
The held-out families join this table only at QAR-T10, after the freeze.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.harness.need_gold import gold_need_of_family
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.questions.families import DEV_NEW_GENERATORS, DEV_OLD_GENERATORS


class FamilySplit(str, Enum):
    """Which part of the family collection a family belongs to (ADR-0035)."""

    DEV_OLD = "dev-old"
    DEV_NEW = "dev-new"


class FamilyMeta(BaseModel):
    """One family's split and its acceptable need labels."""

    model_config = ConfigDict(frozen=True)

    split: FamilySplit
    gold_need: frozenset[NeedLabel]


def _build_family_meta() -> dict[QuestionFamily, FamilyMeta]:
    """The split comes from which generator table a family is registered in: one source."""
    meta = {}
    for split, generators in (
        (FamilySplit.DEV_OLD, DEV_OLD_GENERATORS),
        (FamilySplit.DEV_NEW, DEV_NEW_GENERATORS),
    ):
        for family in generators:
            meta[family] = FamilyMeta(split=split, gold_need=gold_need_of_family(family))
    return meta


FAMILY_META: dict[QuestionFamily, FamilyMeta] = _build_family_meta()


def families_of_split(split: FamilySplit) -> list[QuestionFamily]:
    """The families of one split, in registration order."""
    return [family for family, meta in FAMILY_META.items() if meta.split is split]
