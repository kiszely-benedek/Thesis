"""The EX01 run directory: the frozen config and the answer rows (like the harness's `RunDir`).

```
<out_dir>/
    run_config.json        written once, before the first call
    answers.jsonl          one Ex01AnswerRow per line
    calls.jsonl            one line per model call (written by the LLM client)
    cache_ex01_r1.sqlite   the response cache of repeat 1 (r2, r3 likewise)
```

One cache file per repeat: the cache key is the request alone, so a second repeat sharing a cache
would just read back the first repeat's answers.
"""

from __future__ import annotations

from pathlib import Path

from plantgraph.qa.exp0001.ex01_models import VOLATILE_CONFIG_FIELDS, Ex01AnswerRow, Ex01RunConfig
from plantgraph.qa.models import Outcome

#: A row's identity: (arm, qid, repeat). A resume skips keys already on disk.
RowKey = tuple[str, str, int]


def row_key(row: Ex01AnswerRow) -> RowKey:
    """The identity a resume uses to tell whether a row is done."""
    return (row.arm, row.qid, row.repeat)


class Ex01RunDir:
    """Paths and row operations of one EX01 run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.config_path = path / "run_config.json"
        self.answers_path = path / "answers.jsonl"
        self.calls_path = path / "calls.jsonl"

    def cache_path(self, repeat: int) -> Path:
        """The cache file of one repeat."""
        return self.path / f"cache_ex01_r{repeat}.sqlite"

    def freeze(self, config: Ex01RunConfig) -> Ex01RunConfig:
        """Write `config` if the run is new, else check it against the stored one.

        Raises:
            ValueError: a resume whose measured fields differ from the frozen config.
        """
        if not self.config_path.exists():
            self.path.mkdir(parents=True, exist_ok=True)
            self.config_path.write_bytes((config.model_dump_json(indent=2) + "\n").encode("utf-8"))
            return config
        frozen = Ex01RunConfig.model_validate_json(self.config_path.read_text(encoding="utf-8"))
        changed = _differing_fields(frozen, config)
        if changed:
            raise ValueError(
                f"run {config.run_id!r} is already frozen with different {changed}; "
                "use a new --out-dir, or restore the inputs it was started with"
            )
        return frozen

    def read_rows(self) -> list[Ex01AnswerRow]:
        """Every row on disk, in file order.

        Raises:
            ValueError: a row key appears twice.
        """
        if not self.answers_path.exists():
            return []
        text = self.answers_path.read_text(encoding="utf-8")
        rows = [Ex01AnswerRow.model_validate_json(line) for line in text.splitlines() if line]
        keys = [row_key(row) for row in rows]
        if len(set(keys)) != len(keys):
            raise ValueError(f"expected each (arm, qid, repeat) once in {self.answers_path}")
        return rows

    def append_row(self, row: Ex01AnswerRow) -> None:
        """Append one row as a single write, so an interrupt leaves whole lines."""
        with self.answers_path.open("ab") as handle:
            handle.write((row.model_dump_json() + "\n").encode("utf-8"))

    def drop_provider_error_rows(self) -> int:
        """Remove `PROVIDER_ERROR` rows so a resume asks those questions again; returns how many."""
        rows = self.read_rows()
        kept = [row for row in rows if row.outcome is not Outcome.PROVIDER_ERROR]
        if len(kept) == len(rows):
            return 0
        temporary = self.answers_path.with_suffix(".jsonl.tmp")
        temporary.write_bytes("".join(row.model_dump_json() + "\n" for row in kept).encode("utf-8"))
        temporary.replace(self.answers_path)
        return len(rows) - len(kept)


def _differing_fields(frozen: Ex01RunConfig, requested: Ex01RunConfig) -> list[str]:
    old = frozen.model_dump(mode="json", exclude=VOLATILE_CONFIG_FIELDS)
    new = requested.model_dump(mode="json", exclude=VOLATILE_CONFIG_FIELDS)
    return [name for name in old if old[name] != new[name]]
