"""`python -m plantgraph.qa.questions` — write a sampled question set and its availability report.

Rebuilds the corpus from an `ingest.json` (`qa/corpus.py`), samples questions
from the ground-truth plant, and writes `questions.jsonl` and
`availability.json` into the output directory (default
`data/questions/<corpus_id>`, which is git-ignored). No network, no Neo4j.

The per-bin counts are required arguments: the paid pilot fixes them (design
§12), so there is no default to fall back on.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from plantgraph.qa.corpus import CorpusArtifacts, load_corpus_artifacts
from plantgraph.qa.models import Question
from plantgraph.qa.questions.availability import AvailabilityReport, BinTargets
from plantgraph.qa.questions.sample import generate_question_set

QUESTIONS_FILENAME = "questions.jsonl"
AVAILABILITY_FILENAME = "availability.json"
_DEFAULT_OUT_ROOT = Path("data") / "questions"


def write_question_set(
    out_dir: Path, questions: list[Question], report: AvailabilityReport
) -> tuple[Path, Path]:
    """Write the JSONL and the report; return their paths.

    Bytes are written, not text, so Windows does not turn LF into CRLF: the
    same seed must give the same file on every platform.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    questions_path = out_dir / QUESTIONS_FILENAME
    report_path = out_dir / AVAILABILITY_FILENAME
    lines = "".join(question.model_dump_json() + "\n" for question in questions)
    questions_path.write_bytes(lines.encode("utf-8"))
    report_path.write_bytes((report.model_dump_json(indent=2) + "\n").encode("utf-8"))
    return questions_path, report_path


def build_question_set(
    artifacts: CorpusArtifacts, targets: BinTargets, seed: int
) -> tuple[list[Question], AvailabilityReport]:
    """Sample from a rebuilt corpus's ground truth.

    Raises:
        ValueError: the corpus has no ground truth (a real Proteus import).
    """
    plant, manifest = artifacts.gold.plant, artifacts.gold.manifest
    if plant is None or manifest is None:
        raise ValueError(
            f"expected a synthetic corpus with a ground-truth plant, but {artifacts.corpus_id!r} "
            "has none (a Proteus import has no answer key, design §1)"
        )
    return generate_question_set(
        plant, manifest, artifacts.gold.sheets, targets, corpus_id=artifacts.corpus_id, seed=seed
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.qa.questions", description=__doc__)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--ingest-json", required=True, type=Path, help="the corpus's ingest.json")
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--out", type=Path, help="output directory (default data/questions/<id>)")
    parser.add_argument("--n-per-bin", required=True, type=int, help="questions per k-bin")
    parser.add_argument(
        "--n-unanswerable", required=True, type=int, help="questions in the unanswerable bin"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Parse argv, build the question set and write it."""
    args = _parse_args(argv)
    targets = BinTargets(per_bin=args.n_per_bin, unanswerable=args.n_unanswerable)
    artifacts = load_corpus_artifacts(args.corpus_id, args.ingest_json)
    questions, report = build_question_set(artifacts, targets, args.seed)
    out_dir = args.out or _DEFAULT_OUT_ROOT / args.corpus_id
    questions_path, report_path = write_question_set(out_dir, questions, report)
    print(f"wrote {len(questions)} questions to {questions_path} and {report_path}")
    if report.underpowered:
        bins = [k_bin.value for k_bin in report.underpowered]
        print(f"underpowered bins (fewer candidates than target): {bins}")
