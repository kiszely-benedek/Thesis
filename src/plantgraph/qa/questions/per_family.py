"""`python -m plantgraph.qa.questions.per_family` - keep a fixed number of questions per family.

Used by the sealed test (design `sealed-test-run.md` section 5): from a larger candidate file,
take `n` questions of every family, spread over the k-bins (a k-bin groups questions by how many
sheet boundaries their evidence crosses). The draw depends on the seed and the question ids
only, so the same input always gives the same bytes. No network, no Neo4j.
"""

from __future__ import annotations

import argparse
import json
import random
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path

from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.availability import KBin, k_bin_of

QUESTIONS_FILENAME = "questions.jsonl"


def _deal_over_bins(pool: list[Question], n: int) -> list[Question]:
    """Up to `n` questions, one bin at a time in round-robin order (bins in `KBin` order)."""
    by_bin: dict[KBin, list[Question]] = {}
    for question in pool:  # `pool` is already shuffled, so each bin keeps that order
        by_bin.setdefault(k_bin_of(question), []).append(question)
    queues = [by_bin[k_bin] for k_bin in KBin if k_bin in by_bin]
    drawn: list[Question] = []
    position = 0
    while len(drawn) < n and any(position < len(queue) for queue in queues):
        drawn += [queue[position] for queue in queues if position < len(queue)][: n - len(drawn)]
        position += 1
    return drawn


def sample_family(candidates: Sequence[Question], n: int, seed: int) -> list[Question]:
    """`n` questions of one family: sorted by id, shuffled with `seed`, dealt over the k-bins.

    A family with fewer than `n` candidates keeps all of them.
    """
    pool = sorted(candidates, key=lambda q: q.question_id)
    if len(pool) <= n:
        return pool
    random.Random(seed).shuffle(pool)  # a fresh generator per family: other families never shift it
    return _deal_over_bins(pool, n)


def sample_per_family(questions: Sequence[Question], n: int, seed: int) -> list[Question]:
    """Up to `n` questions of every family, in the input order.

    Raises:
        ValueError: `n` is not positive.
    """
    if n <= 0:
        raise ValueError(f"expected a positive number of questions per family, found {n}")
    by_family: dict[QuestionFamily, list[Question]] = {}
    for question in questions:
        by_family.setdefault(question.family, []).append(question)
    chosen = {
        q.question_id
        for family in sorted(by_family, key=lambda f: f.value)
        for q in sample_family(by_family[family], n, seed)
    }
    return [q for q in questions if q.question_id in chosen]


def filter_by_split(
    questions: Sequence[Question], splits: Mapping[str, str], only: Collection[str]
) -> list[Question]:
    """The questions whose split is in `only`.

    Raises:
        ValueError: a question has no entry in `splits`, or `only` names a split nobody has.
    """
    missing = [q.question_id for q in questions if q.question_id not in splits]
    if missing:
        raise ValueError(f"expected every question in the splits file, found {missing[:3]} missing")
    unused = sorted(set(only) - set(splits.values()))
    if unused:
        raise ValueError(f"expected splits that occur in the splits file, found {unused}")
    return [q for q in questions if splits[q.question_id] in only]


def read_questions(path: Path) -> tuple[list[Question], dict[str, str]]:
    """The questions of a JSONL file, and each question's original line (by id)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    questions = [Question.model_validate_json(line) for line in lines]
    ids = [q.question_id for q in questions]
    if len(set(ids)) != len(ids):
        raise ValueError(f"expected unique question ids in {path}, found repeats")
    return questions, dict(zip(ids, lines, strict=True))


def write_questions(out_dir: Path, questions: Sequence[Question], lines: Mapping[str, str]) -> Path:
    """Write the chosen questions with their original lines, as bytes so LF stays LF."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / QUESTIONS_FILENAME
    path.write_bytes("".join(lines[q.question_id] + "\n" for q in questions).encode("utf-8"))
    return path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.questions.per_family")
    parser.add_argument("--in", dest="source", required=True, type=Path, help="questions.jsonl")
    parser.add_argument("--n", required=True, type=int, help="questions per family")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--out", required=True, type=Path, help="directory for questions.jsonl")
    parser.add_argument("--splits", type=Path, help="splits.json: question id -> split name")
    parser.add_argument("--only-splits", help="comma-separated split names to draw from")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Read the candidates, draw `n` per family, write the result."""
    args = _parse_args(argv)
    questions, lines = read_questions(args.source)
    if args.only_splits:
        if args.splits is None:
            raise SystemExit("error: --only-splits needs --splits")
        splits = json.loads(args.splits.read_text(encoding="utf-8"))
        questions = filter_by_split(questions, splits, args.only_splits.split(","))
    chosen = sample_per_family(questions, args.n, args.seed)
    path = write_questions(args.out, chosen, lines)
    print(f"wrote {len(chosen)} of {len(questions)} questions to {path}")


if __name__ == "__main__":
    main()
