"""The pre-registered choice between cascade_v4 and cascade_v4_iso (ADR-0061, design 7.4).

The rule was fixed before any tuning-set answer was seen, and is code so it cannot drift:

    cascade_v4_iso replaces cascade_v4 if and only if its primary accuracy on the tuning set T
    is at least cascade_v4's.

The primary accuracy is the setting's own number (ADR-0061, status table): for setting A the
correct answers *within its 120 s limit*, for setting B the *uncut* ones (no deadline counts).
"On T" means the rule refuses any other corpus, so it cannot be re-run on the held-back
validation plants.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

#: The tuning plant of the V2T protocol (design 7.1).
TUNING_CORPUS_ID = "X100g2s211"
V4 = "cascade_v4"
V4_ISO = "cascade_v4_iso"


class VariantChoice(BaseModel):
    """Which variant the rule picked, and the two counts it compared."""

    model_config = ConfigDict(frozen=True)

    chosen: str
    setting: Literal["A", "B"]
    #: What the counts below are: correct answers "within 120 s" (A) or "uncut" (B).
    basis: str
    n_questions: int
    n_correct_v4: int
    n_correct_v4_iso: int
    rule: str = (
        "cascade_v4_iso replaces cascade_v4 iff its primary accuracy on T is >= cascade_v4's"
    )


#: The count each setting decides on: its primary number.
PRIMARY_BASIS = {"A": "within 120 s", "B": "uncut"}


def select_variant(
    corpus_id: str,
    setting: Literal["A", "B"],
    n_questions: int,
    n_correct_v4: int,
    n_correct_v4_iso: int,
) -> VariantChoice:
    """Apply the rule to both variants' primary correct counts (see `PRIMARY_BASIS`).

    The caller passes the count that matches `setting`: within-120 s for A, uncut for B.

    Raises:
        ValueError: `corpus_id` is not the tuning set, or a count is outside 0..n_questions.
    """
    if corpus_id != TUNING_CORPUS_ID:
        raise ValueError(
            f"expected the choice on the tuning set {TUNING_CORPUS_ID!r}, found {corpus_id!r}"
        )
    for count in (n_correct_v4, n_correct_v4_iso):
        if not 0 <= count <= n_questions:
            raise ValueError(f"expected a correct count in 0..{n_questions}, found {count}")
    chosen = V4_ISO if n_correct_v4_iso >= n_correct_v4 else V4
    return VariantChoice(
        chosen=chosen,
        setting=setting,
        basis=PRIMARY_BASIS[setting],
        n_questions=n_questions,
        n_correct_v4=n_correct_v4,
        n_correct_v4_iso=n_correct_v4_iso,
    )
