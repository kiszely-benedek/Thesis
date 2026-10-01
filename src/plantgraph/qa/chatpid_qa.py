"""ChatP&ID's 19 EX01 questions and reference answers (design `qa-system.md` §10, task QA-T15).

ChatP&ID (arXiv:2603.22528) is the paper whose result this thesis re-tests.
Its App. Table 1 lists 19 questions about one example drawing, "EX01" (a
*P&ID*: the piping and instrumentation diagram of a process plant), each
with a reference answer. EXP-0001 asks our system the same questions.

The file `data/external/chatpid_ex01_qa.jsonl` holds one transcribed row per
table entry. Each row is tagged `scope`: ADR-0021 puts every question that
needs equipment (datasheet) values out of scope, so those rows are listed in
the report but never asked or judged. Running this module prints a summary
of the file and its sha256 (the hash the thesis quotes):

    uv run python -m plantgraph.qa.chatpid_qa [path]
"""

from __future__ import annotations

import hashlib
import sys
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_PATH = Path("data") / "external" / "chatpid_ex01_qa.jsonl"

TaskType = Literal[
    "Graph Query (Single)",
    "Graph Query (Multi)",
    "Path Exploration",
    "Knowledge Inference",
    "Graph Summarization",
]
Scope = Literal["scored", "out_of_scope_datasheet"]

#: Rows per task type that design §10 expects of App. Table 1 (19 in total).
DESIGN_TASK_TYPE_COUNTS: dict[str, int] = {
    "Graph Query (Single)": 8,
    "Graph Query (Multi)": 2,
    "Path Exploration": 5,
    "Knowledge Inference": 3,
    "Graph Summarization": 1,
}


class ChatPidQA(BaseModel):
    """One App. Table 1 entry: a question, its reference answer and its scope tag."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    qid: str = Field(pattern=r"^CP\d{2}$")
    task_type: TaskType
    question: str = Field(min_length=1)
    reference_answer: str = Field(min_length=1)
    source: str
    source_page: int = Field(ge=28, description="PDF page where the table row starts")
    last_page: int = Field(ge=28, description="PDF page where its reference answer ends")
    scope: Scope
    scope_reason: str = Field(min_length=1)
    #: ChatP&ID's own score for this question, if the paper prints one (it does not).
    chatpid_score: float | None = None
    transcribed_by: str
    #: Set to true only by the user, after comparing the file with the PDF.
    checked_by_human: bool = False


class ChatPidSummary(BaseModel):
    """Counts and hash of a loaded question file, for the run note."""

    model_config = ConfigDict(frozen=True)

    sha256: str
    row_count: int
    per_scope: dict[str, int]
    per_task_type: dict[str, int]
    matches_design_counts: bool
    paper_gives_per_question_scores: bool
    out_of_scope: list[tuple[str, str]]  # (qid, scope_reason)


def load_chatpid_qa(path: Path = DEFAULT_PATH) -> list[ChatPidQA]:
    """Read the JSONL file, one `ChatPidQA` per non-empty line.

    Raises:
        FileNotFoundError: the file is missing (it is git-ignored, so it is local).
        ValueError: a line is not a valid row, or two rows share a `qid`.
    """
    if not path.is_file():
        raise FileNotFoundError(f"expected the ChatP&ID question file at {path}, found nothing")
    rows = [_parse_line(path, number, line) for number, line in _numbered_lines(path)]
    _reject_duplicate_qids(path, rows)
    return rows


def _numbered_lines(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    return [(n, line) for n, line in enumerate(text.splitlines(), start=1) if line.strip()]


def _parse_line(path: Path, number: int, line: str) -> ChatPidQA:
    try:
        return ChatPidQA.model_validate_json(line)
    except ValueError as error:
        raise ValueError(f"{path} line {number} is not a valid ChatPidQA row: {error}") from error


def _reject_duplicate_qids(path: Path, rows: list[ChatPidQA]) -> None:
    repeated = [qid for qid, n in Counter(row.qid for row in rows).items() if n > 1]
    if repeated:
        raise ValueError(f"expected unique qids in {path}, found repeats: {sorted(repeated)}")


def file_sha256(path: Path) -> str:
    """Hash of the file's bytes: what the thesis and `RunConfig.question_set_sha256` quote."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarise(rows: list[ChatPidQA], sha256: str) -> ChatPidSummary:
    """Count rows per scope and task type; report, do not assert, the scope split."""
    per_task_type = dict(Counter(row.task_type for row in rows))
    return ChatPidSummary(
        sha256=sha256,
        row_count=len(rows),
        per_scope=dict(Counter(row.scope for row in rows)),
        per_task_type=per_task_type,
        matches_design_counts=len(rows) == 19 and per_task_type == DESIGN_TASK_TYPE_COUNTS,
        paper_gives_per_question_scores=any(row.chatpid_score is not None for row in rows),
        out_of_scope=[(r.qid, r.scope_reason) for r in rows if r.scope != "scored"],
    )


def format_summary(summary: ChatPidSummary) -> str:
    """Human-readable summary, one fact per line."""
    lines = [
        f"rows: {summary.row_count} (design expects 19 in 8/2/5/3/1 task types: "
        f"{'match' if summary.matches_design_counts else 'MISMATCH'})",
        f"sha256: {summary.sha256}",
        f"per scope: {summary.per_scope}",
        f"per task type: {summary.per_task_type}",
        f"paper gives per-question scores: {summary.paper_gives_per_question_scores}",
        "out of scope (qid: reason):",
    ]
    lines += [f"  {qid}: {reason}" for qid, reason in summary.out_of_scope]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Print the summary of the question file given on the command line (or the default)."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_PATH
    summary = summarise(load_chatpid_qa(path), file_sha256(path))
    print(format_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
