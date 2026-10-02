"""The on-disk layout of one run and the row operations on `answers.jsonl` (`qa-system.md` §11).

```
<runs_root>/<run_id>/
    run_config.json   the frozen RunConfig, written once before the first call
    corpora.json      one CorpusRecord per corpus (sizes and stage timings)
    answers.jsonl     one QuestionResult per line
    calls.jsonl       one CallRecord per model call (written by the LLM client)
```

Rows are appended in binary with a bare newline, so the file is byte-identical
on every platform (Windows text mode would turn it into CRLF).
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.harness.freeze import differing_fields
from plantgraph.qa.models import CorpusRecord, Outcome, QuestionResult, RunConfig

#: A row's identity: (question_id, strategy, repeat). Resume skips keys already present.
RowKey = tuple[str, str, int]


def row_key(row: QuestionResult) -> RowKey:
    """The identity resume uses to tell whether a row is already done."""
    return (row.question_id, row.strategy, row.repeat)


class RunDir:
    """One run's directory: freezes the config, reads and appends answer rows."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.config_path = path / "run_config.json"
        self.answers_path = path / "answers.jsonl"
        self.calls_path = path / "calls.jsonl"
        self.corpora_path = path / "corpora.json"

    def freeze(self, config: RunConfig) -> RunConfig:
        """Write `config` if this run is new; otherwise check it against the stored one.

        Returns the stored config on a resume, so the run keeps its original
        `created_at` and commit.

        Raises:
            ValueError: a resume whose measured fields differ from the frozen config.
        """
        if not self.config_path.exists():
            self.path.mkdir(parents=True, exist_ok=True)
            self.config_path.write_bytes((config.model_dump_json(indent=2) + "\n").encode("utf-8"))
            return config
        frozen = RunConfig.model_validate_json(self.config_path.read_text(encoding="utf-8"))
        changed = differing_fields(frozen, config)
        if changed:
            raise ValueError(
                f"run {config.run_id!r} is already frozen with different {changed}; "
                "use a new run_id, or restore the inputs it was started with"
            )
        return frozen

    def write_corpus_records(self, records: list[CorpusRecord]) -> None:
        """Write `corpora.json`: the size and timing record of each corpus in the run."""
        payload = "[" + ",\n".join(record.model_dump_json() for record in records) + "]\n"
        self.corpora_path.write_bytes(payload.encode("utf-8"))

    def read_rows(self) -> list[QuestionResult]:
        """Every row on disk, in file order.

        Raises:
            ValueError: a row key appears twice (an invalid line fails validation).
        """
        if not self.answers_path.exists():
            return []
        rows: list[QuestionResult] = []
        seen: set[RowKey] = set()
        text = self.answers_path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            row = QuestionResult.model_validate_json(line)
            if row_key(row) in seen:
                raise ValueError(
                    f"{self.answers_path} line {number} repeats row {row_key(row)}; "
                    "expected each (question, strategy, repeat) at most once"
                )
            seen.add(row_key(row))
            rows.append(row)
        return rows

    def drop_provider_error_rows(self) -> int:
        """Remove `PROVIDER_ERROR` rows so a resume asks those questions again.

        Returns how many rows were dropped. The file is replaced in one step.
        """
        rows = self.read_rows()
        kept = [row for row in rows if row.outcome is not Outcome.PROVIDER_ERROR]
        if len(kept) == len(rows):
            return 0
        temporary = self.answers_path.with_suffix(".jsonl.tmp")
        temporary.write_bytes("".join(row.model_dump_json() + "\n" for row in kept).encode("utf-8"))
        temporary.replace(self.answers_path)
        return len(rows) - len(kept)

    def append_row(self, row: QuestionResult) -> None:
        """Append one row as a single write, so an interrupt leaves whole lines."""
        with self.answers_path.open("ab") as handle:
            handle.write((row.model_dump_json() + "\n").encode("utf-8"))
