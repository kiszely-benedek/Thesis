"""Draw a seeded, stratified question set from every family's candidates (design §9, "Sampling").

Per bin: shuffle each family's candidates with a seeded RNG, then deal them
out round-robin, one family at a time, until the bin's target is met or its
candidates run out. Round-robin keeps one prolific family (FLOW_PATH has
thousands of candidates) from crowding the others out of a bin.
"""

from __future__ import annotations

import random
import time
from collections.abc import Collection

import networkx as nx

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.questions.availability import (
    AvailabilityReport,
    BinTargets,
    KBin,
    build_report,
    k_bin_of,
)
from plantgraph.qa.questions.families import all_candidates


def group_by_bin(
    candidates: dict[QuestionFamily, list[Question]],
) -> dict[KBin, dict[QuestionFamily, list[Question]]]:
    """Regroup candidates as bin -> family -> questions, keeping only non-empty cells."""
    grouped: dict[KBin, dict[QuestionFamily, list[Question]]] = {k_bin: {} for k_bin in KBin}
    for family, questions in candidates.items():
        for question in questions:
            grouped[k_bin_of(question)].setdefault(family, []).append(question)
    return grouped


def _ordered_pool(questions: list[Question], rng: random.Random) -> list[Question]:
    """The family's candidates in draw order, to be taken from the END of the list.

    Sorted then shuffled, so the order depends on the seed only. A yes/no family is dealt
    yes, no, yes, no ... (starting side seeded) so a small draw stays balanced.
    """
    pool = sorted(questions, key=lambda q: q.question_id)
    if not pool or pool[0].answer_type is not AnswerType.BOOLEAN:
        rng.shuffle(pool)
        return pool
    yes = [q for q in pool if q.reference == "yes"]
    no = [q for q in pool if q.reference != "yes"]
    rng.shuffle(yes)
    rng.shuffle(no)
    first, second = (yes, no) if rng.random() < 0.5 else (no, yes)
    dealt = [q for pair in zip(first, second, strict=False) for q in pair]
    dealt += first[len(second) :] + second[len(first) :]  # the longer side's leftovers
    return dealt[::-1]


def draw_bin(
    by_family: dict[QuestionFamily, list[Question]], target: int, rng: random.Random
) -> list[Question]:
    """Up to `target` questions from one bin, dealt round-robin over its families."""
    # Families sorted by name, pools sorted then shuffled: the result depends on the seed only.
    pools = [
        _ordered_pool(by_family[family], rng) for family in sorted(by_family, key=lambda f: f.value)
    ]
    drawn: list[Question] = []
    while len(drawn) < target and any(pools):
        for pool in pools:
            if pool and len(drawn) < target:
                drawn.append(pool.pop())
    return drawn


def draw_sample(
    candidates: dict[QuestionFamily, list[Question]],
    targets: BinTargets,
    *,
    corpus_id: str,
    seed: int,
) -> tuple[list[Question], AvailabilityReport]:
    """The sampled questions (bin order, then draw order) and the matching availability report."""
    grouped = group_by_bin(candidates)
    sample: list[Question] = []
    for k_bin in KBin:
        # one RNG per bin: a bin's draw does not shift when another bin's target changes
        rng = random.Random(f"{seed}:{k_bin.value}")
        bin_questions = draw_bin(grouped[k_bin], targets.for_bin(k_bin), rng)
        sample.extend(bin_questions)
    report = build_report(candidates, targets, sample, corpus_id=corpus_id, seed=seed)
    return sample, report


def generate_question_set(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    targets: BinTargets,
    *,
    corpus_id: str,
    seed: int,
    families: Collection[QuestionFamily] | None = None,
) -> tuple[list[Question], AvailabilityReport]:
    """Enumerate the candidates of `families` (default all) on one corpus and sample from them."""
    started = time.perf_counter()
    candidates = all_candidates(
        plant, manifest, sheets, corpus_id=corpus_id, seed=seed, families=families
    )
    build_seconds = time.perf_counter() - started
    sample, report = draw_sample(candidates, targets, corpus_id=corpus_id, seed=seed)
    return sample, report.model_copy(update={"build_seconds": build_seconds})
