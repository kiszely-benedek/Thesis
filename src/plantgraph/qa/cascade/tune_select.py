"""The pre-registered choice between cascade_v4 and cascade_v4_iso (ADR-0061, design 7.4).

The rule was fixed before any tuning-set answer was seen, and is code so it cannot drift:

    cascade_v4_iso replaces cascade_v4 if and only if its uncut accuracy on the tuning set T
    is at least cascade_v4's.

"Uncut" means no latency limit counts, as in the design; "on T" means the rule refuses any
other corpus, so it cannot be re-run on the held-back validation plants.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

#: The tuning plant of the V2T protocol (design 7.1).
TUNING_CORPUS_ID = "X100g2s211"
V4 = "cascade_v4"
V4_ISO = "cascade_v4_iso"


class VariantChoice(BaseModel):
    """Which variant the rule picked, and the two counts it compared."""

    model_config = ConfigDict(frozen=True)

    chosen: str
    n_questions: int
    n_correct_v4: int
    n_correct_v4_iso: int
    rule: str = "cascade_v4_iso replaces cascade_v4 iff its uncut accuracy on T is >= cascade_v4's"


def select_variant(
    corpus_id: str, n_questions: int, n_correct_v4: int, n_correct_v4_iso: int
) -> VariantChoice:
    """Apply the rule to the uncut correct counts of both variants on the same questions.

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
        n_questions=n_questions,
        n_correct_v4=n_correct_v4,
        n_correct_v4_iso=n_correct_v4_iso,
    )
