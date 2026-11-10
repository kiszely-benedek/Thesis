"""Choose the rows to audit, in the registered budget order (review-fixes §5.3), under a budget.

Order: (1) every wrong row, (2) a seeded right-sample of at least `right_min` per family and
scale, (3) ContextRAG's wrong rows, (4) more right rows up to `right_max` per family and scale.
That is the order of the cut. The rows are *judged* with the minimum right-sample first, so if
the cap stops the run early, the unbiased agreement rate on right rows still exists.
Two rows with the same question and the same answer are one row for the audit (a duplicate would
get the same verdict twice); the first in (run, strategy) order stands for them.

The right-sample is drawn once per (family, scale) from a seeded shuffle, so the minimum sample
is a prefix of the larger one and the whole selection is reproducible from the seed.
"""

from __future__ import annotations

import random
from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.audit.models import AuditItem, SourceRow, Stratum

RIGHT_MIN_PER_GROUP = 2
RIGHT_MAX_PER_GROUP = 5


class AuditPlan(BaseModel):
    """The selected rows and the numbers the report needs about what the budget covered."""

    model_config = ConfigDict(frozen=True)

    seed: int
    call_usd: float
    remaining_usd: float
    items: list[AuditItem]
    #: Distinct wrong rows available / selected, per tier, to state how much the budget covered.
    wrong_available: int
    wrong_selected: int
    contextrag_available: int
    contextrag_selected: int
    right_extra_available: int
    right_extra_selected: int

    @property
    def estimated_usd(self) -> float:
        """Rows times the sizing cost per call."""
        return len(self.items) * self.call_usd


def dedupe(rows: list[SourceRow], taken: set[tuple[str, str]] | None = None) -> list[SourceRow]:
    """One row per (question, answer); `taken` keys are skipped too and extended."""
    seen = taken if taken is not None else set()
    kept = []
    for row in sorted(rows, key=lambda r: (r.run_id, r.strategy, r.question_id)):
        key = (row.question_id, row.answer_key)
        if key not in seen:
            seen.add(key)
            kept.append(row)
    return kept


def stratified_cut(rows: list[SourceRow], count: int, seed: int, label: str) -> list[SourceRow]:
    """`count` rows spread evenly over families: a seeded shuffle per family, taken round-robin."""
    if count >= len(rows):
        return list(rows)
    by_family: dict[str, list[SourceRow]] = defaultdict(list)
    for row in rows:
        by_family[row.family.value].append(row)
    queues = []
    for family in sorted(by_family):
        queue = by_family[family]
        random.Random(f"{seed}|{label}|{family}").shuffle(queue)
        queues.append(queue)
    chosen: list[SourceRow] = []
    depth = 0
    while len(chosen) < count:
        layer = [queue[depth] for queue in queues if depth < len(queue)]
        chosen.extend(layer[: count - len(chosen)])
        depth += 1
    return chosen


def right_sample_by_group(
    right_rows: list[SourceRow], seed: int
) -> dict[tuple[str, str], list[SourceRow]]:
    """Right rows grouped by (family, scale), each group in a seeded random order."""
    groups: dict[tuple[str, str], list[SourceRow]] = defaultdict(list)
    for row in dedupe(right_rows):
        groups[(row.family.value, row.scale)].append(row)
    for key in sorted(groups):
        random.Random(f"{seed}|right|{key[0]}|{key[1]}").shuffle(groups[key])
    return groups


def _items(rows: list[SourceRow], stratum: Stratum) -> list[AuditItem]:
    return [AuditItem(stratum=stratum, row=row) for row in rows]


def _flatten(
    groups: dict[tuple[str, str], list[SourceRow]], start: int, stop: int
) -> list[SourceRow]:
    return [row for key in sorted(groups) for row in groups[key][start:stop]]


def select_audit(
    pool: list[SourceRow],
    contextrag_pool: list[SourceRow],
    *,
    seed: int,
    call_usd: float,
    remaining_usd: float,
) -> AuditPlan:
    """Build the audit plan; its estimated cost never exceeds `remaining_usd`.

    Raises:
        ValueError: the budget cannot even cover the minimum right-sample.
    """
    taken: set[tuple[str, str]] = set()
    wrong = dedupe([row for row in pool if not row.scorer_correct], taken)
    groups = right_sample_by_group([row for row in pool if row.scorer_correct], seed)
    right_min = _flatten(groups, 0, RIGHT_MIN_PER_GROUP)
    right_extra = _flatten(groups, RIGHT_MIN_PER_GROUP, RIGHT_MAX_PER_GROUP)
    contextrag = dedupe([row for row in contextrag_pool if not row.scorer_correct], taken)

    room = int(remaining_usd // call_usd)
    if room < len(right_min):
        raise ValueError(
            f"expected a budget of at least {len(right_min)} calls for the minimum right-sample, "
            f"found room for {room} at {call_usd:.4f} USD per call"
        )
    wrong_chosen = stratified_cut(wrong, room - len(right_min), seed, "wrong")
    room -= len(right_min) + len(wrong_chosen)
    contextrag_chosen = stratified_cut(contextrag, room, seed, "contextrag")
    room -= len(contextrag_chosen)
    extra_chosen = stratified_cut(right_extra, room, seed, "right_extra")
    items = (
        _items(right_min, "right_min")
        + _items(wrong_chosen, "wrong")
        + _items(contextrag_chosen, "contextrag_wrong")
        + _items(extra_chosen, "right_extra")
    )
    return AuditPlan(
        seed=seed,
        call_usd=call_usd,
        remaining_usd=remaining_usd,
        items=items,
        wrong_available=len(wrong),
        wrong_selected=len(wrong_chosen),
        contextrag_available=len(contextrag),
        contextrag_selected=len(contextrag_chosen),
        right_extra_available=len(right_extra),
        right_extra_selected=len(extra_chosen),
    )
