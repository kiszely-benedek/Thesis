"""Cypher types and the write filter shared by the Neo4j view and CypherRAG (design §5, §7).

Cypher is Neo4j's query language (a graph-pattern language, the way SQL is a
table language). CypherRAG asks an LLM to write one Cypher query, runs it, and
shows the resulting rows to the answering model. Two safeguards sit between the
LLM's text and the database:

- the session is opened read-only, so the server itself refuses a write;
- `reject_write_clauses` refuses the query text *before* it is sent, so a
  rejected query never reaches the database at all.

This module has no `neo4j` import, so the filter and the result types are
tested with no database running.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class WriteClauseError(ValueError):
    """The query contains a clause that changes data; it was not sent."""


class CypherExecutionError(RuntimeError):
    """The database rejected or aborted a read query (syntax error, timeout, ...)."""


class CypherResult(BaseModel):
    """The rows of one read query, cut at `row_cap`."""

    model_config = ConfigDict(frozen=True)

    #: One dict per row, column name to a JSON-ready value.
    rows: list[dict[str, Any]]
    #: True when the query had more rows than `row_cap`; the rest were dropped.
    truncated: bool


class CypherSource(Protocol):
    """What CypherRAG needs from a database view: the schema text and a way to run a query."""

    def corpus_id(self) -> str:
        """Which corpus the database holds."""
        ...

    def schema_text(self) -> str:
        """The schema description shown to the Cypher-writing LLM."""
        ...

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        """Run one read-only query.

        Raises:
            WriteClauseError: the query contains a write clause; nothing was sent.
            CypherExecutionError: the database rejected or aborted the query.
        """
        ...

    def close(self) -> None:
        """Release the database connection."""
        ...


#: The clauses that change data, plus `LOAD` (which reads files from the server).
#: The task's list is CREATE, MERGE, DELETE, SET, REMOVE, DROP; DETACH and LOAD are added
#: here because `DETACH DELETE` would otherwise rely on `DELETE` being found beside it,
#: and `LOAD CSV` is a file read no question needs.
_WRITE_KEYWORDS = ("CREATE", "MERGE", "DELETE", "DETACH", "SET", "REMOVE", "DROP", "LOAD")

#: Text that is not a clause: string literals, backtick names and comments. Blanked out
#: first so a tag such as 'SET-1' or a comment saying "do not DELETE" is not mistaken
#: for a write. An unterminated quote is left in place, which only makes the filter stricter.
_NOT_CODE = re.compile(
    r"'(?:[^'\\]|\\.)*'" r'|"(?:[^"\\]|\\.)*"' r"|`[^`]*`" r"|//[^\n]*" r"|/\*.*?\*/",
    re.DOTALL,
)

#: A keyword on its own: not part of a longer word (`offset`), not a property (`n.set`),
#: not a label (`:Set`) and not a parameter (`$set`).
_WRITE_CLAUSE = re.compile(r"(?<![\w.:$])(" + "|".join(_WRITE_KEYWORDS) + r")(?!\w)", re.IGNORECASE)


def find_write_clause(query: str) -> str | None:
    """The first write keyword in `query` (upper-cased), or `None` if it is read-only."""
    code = _NOT_CODE.sub(" ", query)
    match = _WRITE_CLAUSE.search(code)
    return match.group(1).upper() if match else None


def reject_write_clauses(query: str) -> None:
    """Raise `WriteClauseError` if `query` could change the database.

    Raises:
        WriteClauseError: naming the keyword found.
    """
    keyword = find_write_clause(query)
    if keyword is not None:
        raise WriteClauseError(
            f"expected a read-only Cypher query; found the write clause {keyword}"
        )
