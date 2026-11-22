"""Short constructors so the catalogue entries read as data (design 4)."""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.registry import PENDING_PREFIX, BookId, SourceRef

#: module of the checks that wrap the v2.1 invariants; `wired("x")` is its function `x`
_WIRED_MODULE = "plantgraph.benchmark.v2.rules.checks_rules"


def _ref(book: BookId, locator: str, page_checked: bool) -> SourceRef:
    return SourceRef(book=book, locator=locator, page_checked=page_checked)


def tog(locator: str, *, checked: bool = True) -> SourceRef:
    """Toghraei 2019, locator like `p.192` (a page range is written `p.33–34`)."""
    return _ref("TOG2019", locator, checked)


def api(locator: str, *, checked: bool = True) -> SourceRef:
    """API RP 14C (2001)."""
    return _ref("API14C2001", locator, checked)


def lip1(locator: str, *, checked: bool = True) -> SourceRef:
    """Liptak, Instrument Engineers' Handbook vol. 1 (2003)."""
    return _ref("LIP2003V1", locator, checked)


def lip_pc(locator: str, *, checked: bool = False) -> SourceRef:
    """Liptak, Process Control (1995); its sections were not re-verified against pages."""
    return _ref("LIP1995PC", locator, checked)


def design(locator: str) -> SourceRef:
    """A rule derived by a design choice of this generator (plant-level rules only)."""
    return _ref("DESIGN", locator, True)


def pending(task: str) -> str:
    """A check owed by coder task `task` (design 13)."""
    return f"{PENDING_PREFIX}{task}"


def wired(function_name: str) -> str:
    """The dotted path of a check in `checks_rules.py`."""
    return f"{_WIRED_MODULE}.{function_name}"
