"""Read a JSONL log that a crash may have cut off in its last line.

`calls.jsonl` is appended while a run is alive. If the process dies mid-write, the final line
is half a record. Dropping that one line (with a warning) lets the spend be counted and the run
resumed; a bad line anywhere else means the file is damaged, and that still raises.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_jsonl[T](path: Path, parse: Callable[[str], T]) -> list[T]:
    """Parse every non-blank line with `parse` (which raises `ValueError` on a bad line).

    Raises:
        ValueError: a line other than the last non-blank one does not parse.
    """
    numbered = [
        (number, line)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if line.strip()
    ]
    parsed: list[T] = []
    for position, (number, line) in enumerate(numbered):
        try:
            parsed.append(parse(line))
        except ValueError as error:
            if position < len(numbered) - 1:
                raise ValueError(f"expected JSON in {path} line {number}, found {error}") from error
            logger.warning("Skipping the truncated last line %d of %s: %s", number, path, error)
    return parsed
