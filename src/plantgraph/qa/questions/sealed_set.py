"""`python -m plantgraph.qa.questions.sealed_set` - the question set of the sealed test run.

Design `sealed-test-run.md` section 5 and 7.2. In three steps, with no network and no Neo4j:

1. **Pool.** Candidates of the 18 dev families *and* the 6 held-out ones (an explicit opt-in:
   the default `python -m plantgraph.qa.questions` never builds the held-out ones), drawn
   with the dev recipe: `--n-per-bin` per k-bin, `--n-unanswerable`, seed `--seed`.
2. **Per family.** `--n-per-family` questions of every family, dealt over the k-bins by
   `per_family.sample_family` with `--sample-seed`.
3. **Wordings.** Of ten dev families, the first `--n-per-wording` questions of that same
   draw, asked again in the held-out wording. They are the same items as the dev draw, so
   a wording effect can be read pairwise. Their ids carry the template id (`..._P1`).

Writes `questions.jsonl`, `splits.json` (question id -> `dev-old | dev-new | held-out |
held-out-wording`) and `availability.json` into `--out`; the pool goes to `--pool-out`.
Only test corpora (`H<sheets>`) are accepted: the held-out families must never be
generated on a dev corpus (`D<sheets>`).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.harness.family_meta import FAMILY_META
from plantgraph.qa.models import FinalAnswer, Outcome, Question, QuestionFamily
from plantgraph.qa.questions.availability import AvailabilityReport, BinTargets
from plantgraph.qa.questions.cli import AVAILABILITY_FILENAME, write_question_set
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.questions.families_heldout import HELDOUT_GENERATORS, heldout_candidates
from plantgraph.qa.questions.per_family import (
    QUESTIONS_FILENAME,
    sample_family,
    sample_per_family,
)
from plantgraph.qa.questions.sample import draw_sample
from plantgraph.qa.questions.wordings_heldout import WORDING_FAMILIES, reword
from plantgraph.qa.scoring import score_answer

SPLITS_FILENAME = "splits.json"
WORDING_SPLIT = "held-out-wording"
_TEST_CORPUS_ID = re.compile(r"H\d+")


class SealedSet(BaseModel):
    """The drawn questions, each one's split, and the families that could not be used."""

    model_config = ConfigDict(frozen=True)

    questions: list[Question]
    #: question id -> split name; covers every question exactly once.
    splits: dict[str, str]
    #: family -> why it has no questions in the set.
    dropped: dict[QuestionFamily, str]


class SealedAvailability(BaseModel):
    """What `availability.json` records: the pool's candidates and what the sealed set drew."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    seed: int
    sample_seed: int
    n_per_family: int
    n_per_wording: int
    #: The pool's candidates per family (held-out included) and k-bin.
    pool: AvailabilityReport
    drawn_per_family: dict[QuestionFamily, int]
    drawn_per_wording: dict[QuestionFamily, int]
    drawn_per_split: dict[str, int]
    dropped: dict[QuestionFamily, str]


def require_test_corpus(corpus_id: str) -> None:
    """Refuse anything that is not a test corpus (`H<sheets>`), the dev ones included.

    Raises:
        ValueError: the id does not look like a test corpus id.
    """
    if not _TEST_CORPUS_ID.fullmatch(corpus_id):
        raise ValueError(
            f"expected a test corpus id like 'H100' (held-out families are never generated on "
            f"a dev corpus), found {corpus_id!r}"
        )


def build_pool(
    artifacts: CorpusArtifacts, targets: BinTargets, seed: int
) -> tuple[list[Question], AvailabilityReport]:
    """The dev recipe's pool, with the held-out families added.

    Raises:
        ValueError: the corpus has no ground truth (a real Proteus import).
    """
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    if plant is None or manifest is None:
        raise ValueError(
            f"expected a synthetic corpus with a ground-truth plant, but {artifacts.corpus_id!r} "
            "has none (a Proteus import has no answer key)"
        )
    return build_pool_from_plant(
        plant, manifest, artifacts.gold.sheets, targets, corpus_id=artifacts.corpus_id, seed=seed
    )


def build_pool_from_plant(
    plant: nx.DiGraph[str],
    manifest: SplitManifest,
    sheets: list[SheetGraph],
    targets: BinTargets,
    *,
    corpus_id: str,
    seed: int,
) -> tuple[list[Question], AvailabilityReport]:
    """Enumerate dev and held-out candidates, then draw the pool (`sample.draw_sample`)."""
    started = time.perf_counter()
    candidates = all_candidates(plant, manifest, sheets, corpus_id=corpus_id, seed=seed)
    candidates.update(heldout_candidates(plant, manifest, sheets, corpus_id=corpus_id, seed=seed))
    build_seconds = time.perf_counter() - started
    pool, report = draw_sample(candidates, targets, corpus_id=corpus_id, seed=seed)
    return pool, report.model_copy(update={"build_seconds": build_seconds})


def _own_reference_scores_correct(question: Question) -> bool:
    """Whether the question's own reference, given as the answer, is scored correct."""
    answer = FinalAnswer(answer=question.reference, not_present=False)
    try:
        return score_answer(question, Outcome.ANSWERED, answer).correct
    except ValueError:  # a reference the scorer cannot even read counts as not scoring
        return False


def find_dropped_families(pool: list[Question]) -> dict[QuestionFamily, str]:
    """Families with no question in the pool, or a held-out one whose reference does not score."""
    dropped: dict[QuestionFamily, str] = {}
    for family in FAMILY_META:
        members = [q for q in pool if q.family is family]
        if not members:
            dropped[family] = "no candidate question in the pool"
        elif family in HELDOUT_GENERATORS:
            unscorable = [q.question_id for q in members if not _own_reference_scores_correct(q)]
            if unscorable:
                dropped[family] = f"reference does not score as correct, e.g. {unscorable[0]}"
    return dropped


def sample_sealed_set(
    pool: list[Question], n_per_family: int, n_per_wording: int, sample_seed: int
) -> SealedSet:
    """Steps 2 and 3: `n_per_family` per family, then the held-out wordings.

    Raises:
        ValueError: `n_per_wording` is not positive (`n_per_family` is checked by the sampler).
    """
    if n_per_wording <= 0:
        raise ValueError(
            f"expected a positive number of questions per wording, found {n_per_wording}"
        )
    dropped = find_dropped_families(pool)
    usable = [q for q in pool if q.family not in dropped]
    drawn = sample_per_family(usable, n_per_family, sample_seed)
    wordings = _draw_wordings(usable, n_per_wording, sample_seed)
    splits = {q.question_id: FAMILY_META[q.family].split.value for q in drawn}
    splits.update({q.question_id: WORDING_SPLIT for q in wordings})
    return SealedSet(questions=drawn + wordings, splits=splits, dropped=dropped)


def _draw_wordings(pool: list[Question], n: int, sample_seed: int) -> list[Question]:
    """The held-out wording of the first `n` questions of each wording family's draw."""
    wordings = []
    for family in WORDING_FAMILIES:
        members = [q for q in pool if q.family is family]
        wordings += [reword(q) for q in sample_family(members, n, sample_seed)]
    return wordings


def build_availability(
    sealed: SealedSet,
    pool_report: AvailabilityReport,
    *,
    n_per_family: int,
    n_per_wording: int,
    sample_seed: int,
) -> SealedAvailability:
    """Count what was drawn, per family, per wording and per split."""
    drawn_per_family = {f: 0 for f in FAMILY_META}
    drawn_per_wording = {f: 0 for f in WORDING_FAMILIES}
    for question in sealed.questions:
        is_wording = sealed.splits[question.question_id] == WORDING_SPLIT
        counts = drawn_per_wording if is_wording else drawn_per_family
        counts[question.family] += 1
    split_names = [*dict.fromkeys(m.split.value for m in FAMILY_META.values()), WORDING_SPLIT]
    return SealedAvailability(
        corpus_id=pool_report.corpus_id,
        seed=pool_report.seed,
        sample_seed=sample_seed,
        n_per_family=n_per_family,
        n_per_wording=n_per_wording,
        # wall-clock time stays in the pool's own report, so this file is the same on every run
        pool=pool_report.model_copy(update={"build_seconds": 0.0}),
        drawn_per_family=drawn_per_family,
        drawn_per_wording=drawn_per_wording,
        drawn_per_split={s: list(sealed.splits.values()).count(s) for s in split_names},
        dropped=sealed.dropped,
    )


def write_sealed_set(
    out_dir: Path, sealed: SealedSet, availability: SealedAvailability
) -> tuple[Path, Path, Path]:
    """Write the three files as bytes, so LF stays LF on every platform."""
    out_dir.mkdir(parents=True, exist_ok=True)
    questions = "".join(q.model_dump_json() + "\n" for q in sealed.questions)
    splits = json.dumps(sealed.splits, indent=2) + "\n"
    paths = (
        out_dir / QUESTIONS_FILENAME,
        out_dir / SPLITS_FILENAME,
        out_dir / AVAILABILITY_FILENAME,
    )
    texts = (questions, splits, availability.model_dump_json(indent=2) + "\n")
    for path, text in zip(paths, texts, strict=True):
        path.write_bytes(text.encode("utf-8"))
    return paths


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.questions.sealed_set")
    parser.add_argument("--corpus-id", required=True, help="a test corpus id such as H100")
    parser.add_argument("--ingest-json", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int, help="seed of the candidate pool")
    parser.add_argument("--n-per-bin", required=True, type=int)
    parser.add_argument("--n-unanswerable", required=True, type=int)
    parser.add_argument("--n-per-family", required=True, type=int)
    parser.add_argument("--n-per-wording", required=True, type=int)
    parser.add_argument(
        "--sample-seed", required=True, type=int, help="seed of the per-family draw"
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--pool-out", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Build the pool, draw the sealed set, write both."""
    args = _parse_args(argv)
    require_test_corpus(args.corpus_id)
    artifacts = load_corpus_artifacts(args.corpus_id, args.ingest_json)
    targets = BinTargets(per_bin=args.n_per_bin, unanswerable=args.n_unanswerable)
    pool, report = build_pool(artifacts, targets, args.seed)
    write_question_set(args.pool_out, pool, report)
    sealed = sample_sealed_set(pool, args.n_per_family, args.n_per_wording, args.sample_seed)
    availability = build_availability(
        sealed,
        report,
        n_per_family=args.n_per_family,
        n_per_wording=args.n_per_wording,
        sample_seed=args.sample_seed,
    )
    questions_path, _, _ = write_sealed_set(args.out, sealed, availability)
    print(f"wrote {len(sealed.questions)} questions to {questions_path}")
    for family, reason in sealed.dropped.items():
        print(f"dropped {family.value}: {reason}")


if __name__ == "__main__":
    main()
