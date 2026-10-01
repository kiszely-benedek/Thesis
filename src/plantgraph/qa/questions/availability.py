"""k-bins and the availability report: how many candidates each family has in each bin.

Design `qa-system.md` §9 ("Sampling"): questions are binned by `k`, the
number of off-page connectors their evidence crosses, into `{0, 1, 2, >=3}`.
Unanswerable questions have no `k` and sit in their own bin, never in the k
curve (ADR-0013, ADR-0011 item 3). The report is written beside the sampled
JSONL so a reader can see what the sample was drawn from, and which bins had
too few candidates to reach their target count.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.models import Question, QuestionFamily


class KBin(str, Enum):
    """One stratum of the sample, in the order bins are reported and drawn."""

    K0 = "0"
    K1 = "1"
    K2 = "2"
    K3_PLUS = "3+"
    UNANSWERABLE = "unanswerable"


def k_bin_of_k(k: int) -> KBin:
    """The bin of an answerable question with `k` crossings."""
    if k >= 3:
        return KBin.K3_PLUS
    return KBin(str(k))


def k_bin_of(question: Question) -> KBin:
    """The bin a question falls in; an unanswerable question has `k=None` and gets its own."""
    if question.k is None:
        return KBin.UNANSWERABLE
    return k_bin_of_k(question.k)


class BinTargets(BaseModel):
    """How many questions to draw per bin. Every field is required: the pilot fixes them (§12).

    There is deliberately no default, so a sample can never be drawn with a
    number nobody chose.
    """

    model_config = ConfigDict(frozen=True)

    k0: int = Field(ge=0)
    k1: int = Field(ge=0)
    k2: int = Field(ge=0)
    k3_plus: int = Field(ge=0)
    unanswerable: int = Field(ge=0)

    def for_bin(self, k_bin: KBin) -> int:
        """The target count of `k_bin`."""
        return {
            KBin.K0: self.k0,
            KBin.K1: self.k1,
            KBin.K2: self.k2,
            KBin.K3_PLUS: self.k3_plus,
            KBin.UNANSWERABLE: self.unanswerable,
        }[k_bin]


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


def build_report(
    candidates: dict[QuestionFamily, list[Question]],
    targets: BinTargets,
    drawn: dict[KBin, int],
    *,
    corpus_id: str,
    seed: int,
) -> AvailabilityReport:
    """Assemble the report; per-bin totals are summed from the same table the cells come from."""
    table = count_candidates(candidates)
    per_bin = {k_bin: sum(row[k_bin] for row in table.values()) for k_bin in KBin}
    return AvailabilityReport(
        corpus_id=corpus_id,
        seed=seed,
        candidates=table,
        candidates_per_bin=per_bin,
        n_candidates=sum(per_bin.values()),
        targets={k_bin: targets.for_bin(k_bin) for k_bin in KBin},
        drawn=drawn,
        underpowered=[k_bin for k_bin in KBin if per_bin[k_bin] < targets.for_bin(k_bin)],
    )
