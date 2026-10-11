"""One Markdown table helper shared by the report renderers."""

from __future__ import annotations

from collections.abc import Sequence


def table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """A Markdown table as lines, followed by a blank line."""
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return lines + ["| " + " | ".join(r) + " |" for r in rows] + [""]
