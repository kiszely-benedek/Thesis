"""`examples`: pick the demo's example questions out of a benchmark file, gold kept.

The demo lists a few dozen example questions per plant. They are ordinary benchmark `Question`
lines (same schema as `questions.jsonl`, reference answer and evidence included), so the demo
loader reads the result unchanged; an example asked as written runs live like any question
and is scored against its reference.

Three ways to choose, exactly one per run:
  --variant NAME        keep the rows whose id ends in `#NAME` (a reworded copy of a question)
  --per-family N        keep N questions of each family, ranked by a seeded hash of the id
  --wordings FILE       keep the questions named in a `{question_id: new text}` JSON file and
                        swap in the new text (gold untouched); how reworded examples arrive
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from plantgraph.qa.models import Question


class ExamplesProvenance(BaseModel):
    """What `examples` did; saved next to the output as `<out>.provenance.json`."""

    source: str
    source_sha256: str
    rule: str
    corpus_id: str
    n_questions: int
    question_ids: list[str]


def build_examples_parser(prog: str = "examples") -> argparse.ArgumentParser:
    """The `examples` command line."""
    parser = argparse.ArgumentParser(prog=prog, description="Write a corpus's example questions.")
    parser.add_argument("--from", dest="source", type=Path, required=True, help="questions.jsonl")
    parser.add_argument("--corpus", required=True, help="the corpus id every question must have")
    parser.add_argument("--out", type=Path, required=True, help="the new examples file")
    rule = parser.add_mutually_exclusive_group(required=True)
    rule.add_argument("--variant", help="keep rows whose id ends in '#<variant>', e.g. hu1")
    rule.add_argument("--per-family", type=int, help="keep this many questions per family")
    rule.add_argument("--wordings", type=Path, help="JSON {question_id: text} to keep and reword")
    parser.add_argument("--seed", type=int, default=0, help="seed of the --per-family ranking")
    return parser


def read_questions(path: Path, corpus_id: str) -> list[Question]:
    """The questions of one corpus, in file order.

    Raises:
        ValueError: a line is not a question, or belongs to another corpus.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    questions = [Question.model_validate_json(line) for line in lines if line.strip()]
    foreign = sorted({q.corpus_id for q in questions if q.corpus_id != corpus_id})
    if foreign:
        raise ValueError(f"expected only corpus {corpus_id} in {path}, found {foreign}")
    return questions


def select_variant(questions: Sequence[Question], variant: str) -> list[Question]:
    """The rows whose id ends in `#<variant>`."""
    chosen = [q for q in questions if q.question_id.endswith(f"#{variant}")]
    if not chosen:
        raise ValueError(f"expected question ids ending in '#{variant}', found none")
    return chosen


def select_per_family(questions: Sequence[Question], per_family: int, seed: int) -> list[Question]:
    """`per_family` questions of each family, in file order.

    Within a family the questions are ranked by sha256("<seed>:<id>"): a fixed order that does
    not depend on the Python version, so the same seed always gives the same examples.
    """
    by_family: dict[str, list[Question]] = defaultdict(list)
    for question in questions:
        by_family[question.family.value].append(question)
    kept: set[str] = set()
    for family, members in by_family.items():
        if len(members) < per_family:
            raise ValueError(f"expected {per_family} questions of {family}, found {len(members)}")
        ranked = sorted(members, key=lambda q: _rank(seed, q.question_id))
        kept.update(q.question_id for q in ranked[:per_family])
    return [q for q in questions if q.question_id in kept]


def select_wordings(questions: Sequence[Question], wordings: dict[str, str]) -> list[Question]:
    """The questions named in `wordings`, in file order, each with its new text."""
    known = {q.question_id for q in questions}
    unknown = sorted(set(wordings) - known)
    if unknown:
        raise ValueError(f"expected wordings only for known question ids, found {unknown[:3]}")
    blank = sorted(qid for qid, text in wordings.items() if not text.strip())
    if blank:
        raise ValueError(f"expected a non-blank wording for every question, found {blank[:3]}")
    return [
        q.model_copy(update={"text": wordings[q.question_id].strip()})
        for q in questions
        if q.question_id in wordings
    ]


def _rank(seed: int, question_id: str) -> str:
    return hashlib.sha256(f"{seed}:{question_id}".encode()).hexdigest()


def write_examples(questions: Sequence[Question], out: Path) -> None:
    """One JSON line per question; refuses to overwrite."""
    if out.exists():
        raise FileExistsError(f"refusing to overwrite {out}: pass a --out path that does not exist")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [q.model_dump_json() for q in questions]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_examples(argv: Sequence[str]) -> None:
    """Entry point for `python -m plantgraph.demo.app examples ...`; prints the provenance."""
    args = build_examples_parser().parse_args(argv)
    questions = read_questions(args.source, args.corpus)
    if args.variant is not None:
        chosen, rule = select_variant(questions, args.variant), f"variant {args.variant}"
    elif args.per_family is not None:
        chosen = select_per_family(questions, args.per_family, args.seed)
        rule = f"per-family {args.per_family}, seed {args.seed}"
    else:
        wordings = json.loads(args.wordings.read_text(encoding="utf-8"))
        chosen, rule = select_wordings(questions, wordings), f"wordings {args.wordings}"
    write_examples(chosen, args.out)
    provenance = ExamplesProvenance(
        source=str(args.source),
        source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),
        rule=rule,
        corpus_id=args.corpus,
        n_questions=len(chosen),
        question_ids=[q.question_id for q in chosen],
    )
    sidecar = args.out.with_name(args.out.name + ".provenance.json")
    sidecar.write_text(provenance.model_dump_json(indent=2), encoding="utf-8")
    print(json.dumps(provenance.model_dump(exclude={"question_ids"}), indent=2))
