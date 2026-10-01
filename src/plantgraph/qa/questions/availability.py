"""k-bins and the availability report: how many candidates each family has in each bin.

Design `qa-system.md` §9 ("Sampling") and ADR-0029: questions are binned by
`k`, the number of off-page connectors their evidence crosses, into doubling
bins {0, 1, 2, 3-4, 5-8, 9-16, 17-32, 33+}. Unanswerable questions have no `k`
and sit in their own bin, never in the k curve (ADR-0013, ADR-0011 item 3).
The report is written beside the sampled JSONL so a reader can see what the
sample was drawn from, and which bins had too few candidates.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.models import Question, QuestionFamily


class KBin(str, Enum):
    """One stratum of the sample, in the order bins are reported and drawn.

    The k-bins double in width (ADR-0029), so each keeps a comparable spread of
    difficulty and the long cross-boundary questions are not pooled into one.
    """

    K0 = "0"
    K1 = "1"
    K2 = "2"
    K3_4 = "3-4"
    K5_8 = "5-8"
    K9_16 = "9-16"
    K17_32 = "17-32"
    K33_PLUS = "33+"
    UNANSWERABLE = "unanswerable"


#: A bin is powered when it holds this many candidates: (1.96 * 0.5 / 0.10)^2,
#: the sample size for a +-10 point margin at 95 % (`qa-system.md` §12 step 6).
MIN_POWERED_CANDIDATES = 97

#: Inclusive upper bound of every answerable bin except the open-ended last one.
_K_BIN_UPPER_BOUNDS = (
    (0, KBin.K0),
    (1, KBin.K1),
    (2, KBin.K2),
    (4, KBin.K3_4),
    (8, KBin.K5_8),
    (16, KBin.K9_16),
    (32, KBin.K17_32),
)


def k_bin_of_k(k: int) -> KBin:
    """The bin of an answerable question with `k` crossings.

    Raises:
        ValueError: `k` is negative; a count of crossings cannot be.
    """
    if k < 0:
        raise ValueError(f"expected a crossing count k >= 0, found {k}")
    for upper_bound, k_bin in _K_BIN_UPPER_BOUNDS:
        if k <= upper_bound:
            return k_bin
    return KBin.K33_PLUS


def k_bin_of(question: Question) -> KBin:
    """The bin a question falls in; an unanswerable question has `k=None` and gets its own."""
    if question.k is None:
        return KBin.UNANSWERABLE
    return k_bin_of_k(question.k)


class BinTargets(BaseModel):
    """How many questions to draw per answerable k-bin, and for the unanswerable bin.

    Both fields are required: the pilot fixes them (§12), so there is
    deliberately no default and a sample can never be drawn with a number
    nobody chose. A bin with fewer candidates is reported as underpowered,
    never merged into a neighbour (ADR-0029).
    """

    model_config = ConfigDict(frozen=True)

    per_bin: int = Field(ge=0)
    unanswerable: int = Field(ge=0)

    def for_bin(self, k_bin: KBin) -> int:
        """The target count of `k_bin`."""
        return self.unanswerable if k_bin is KBin.UNANSWERABLE else self.per_bin


class AvailabilityReport(BaseModel):
    """Candidates per family and k-bin, plus what the sampler drew and which bins fell short."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    seed: int
    #: family -> bin -> number of candidates; every bin is listed, zeros included.
    candidates: dict[QuestionFamily, dict[KBin, int]]
    #: Sum over families of each bin's count.
    candidates_per_bin: dict[KBin, int]
    #: Sum of `candidates_per_bin`; equals the total length of the candidate lists.
    n_candidates: int
    targets: dict[KBin, int]
    drawn: dict[KBin, int]
    #: Bins where fewer candidates existed than the target, so all were taken.
    underpowered: list[KBin]
    #: Per bin: at least `MIN_POWERED_CANDIDATES` candidates exist, whatever the target.
    powered: dict[KBin, bool]
    #: Units crossed (`Question.u`) -> number of drawn answerable questions with that value.
    u_histogram: dict[int, int]
    #: Wall-clock seconds spent enumerating candidates; 0.0 when the caller did not time it.
    build_seconds: float = 0.0


def count_candidates(
    candidates: dict[QuestionFamily, list[Question]],
) -> dict[QuestionFamily, dict[KBin, int]]:
    """Candidates per family and bin, with a zero for every empty cell."""
    table: dict[QuestionFamily, dict[KBin, int]] = {}
    for family, questions in candidates.items():
        row = {k_bin: 0 for k_bin in KBin}
        for question in questions:
            row[k_bin_of(question)] += 1
        table[family] = row
    return table


def _u_histogram(sample: list[Question]) -> dict[int, int]:
    """How many answerable sampled questions cross each number of unit boundaries."""
    counts = Counter(question.u for question in sample if question.u is not None)
    return dict(sorted(counts.items()))


def build_report(
    candidates: dict[QuestionFamily, list[Question]],
    targets: BinTargets,
    sample: list[Question],
    *,
    corpus_id: str,
    seed: int,
) -> AvailabilityReport:
    """Assemble the report; per-bin totals are summed from the same table the cells come from."""
    table = count_candidates(candidates)
    per_bin = {k_bin: sum(row[k_bin] for row in table.values()) for k_bin in KBin}
    drawn = Counter(k_bin_of(question) for question in sample)
    return AvailabilityReport(
        corpus_id=corpus_id,
        seed=seed,
        candidates=table,
        candidates_per_bin=per_bin,
        n_candidates=sum(per_bin.values()),
        targets={k_bin: targets.for_bin(k_bin) for k_bin in KBin},
        drawn={k_bin: drawn[k_bin] for k_bin in KBin},
        underpowered=[k_bin for k_bin in KBin if per_bin[k_bin] < targets.for_bin(k_bin)],
        powered={k_bin: per_bin[k_bin] >= MIN_POWERED_CANDIDATES for k_bin in KBin},
        u_histogram=_u_histogram(sample),
    )
