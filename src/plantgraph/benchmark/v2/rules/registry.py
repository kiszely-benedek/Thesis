"""Types of the handbook-rule registry (design generator-v2-2-handbook-rules.md 3.1 and 3.3).

A **rule** is one design practice taken from a handbook (see the package docstring). Each rule
names its source page, says what kind of statement it is, and points at the check that verifies a
generated plant. A rule is either ENCODED (the generator follows it, a check verifies it) or
DEFERRED (read, not encoded, with the reason). Entries are data, in `catalogue*.py`.

A check is a dotted path to a function `RuleView -> CheckResult`. While the generator change a
rule needs is still to be built, the path reads `pending:<task>` (for example `pending:T3`), so
the registry is complete today and a test lists exactly which checks are still owed.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from enum import Enum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from plantgraph.benchmark.v2.rules.view import RuleView

BookId = Literal["TOG2019", "API14C2001", "LIP2003V1", "LIP1995PC", "DESIGN"]

#: a check path that starts with this prefix is owed by the named task; it is not an import path
PENDING_PREFIX = "pending:"
_RULE_ID = re.compile(r"^[A-Z0-9]+(-[A-Z0-9.]+)+$")
#: `DESIGN` (a derived rule, no book) is allowed only for ids with these prefixes
_DERIVED_PREFIXES = ("PLT-", "PRS-")


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class SourceRef(_Frozen):
    """Where in a book a rule comes from."""

    book: BookId
    locator: str  # for example "p.271", "p.33–34", "§1.1 PDF p.76"; no parentheses
    page_checked: bool  # True only if the page was read against the PDF


class ConflictNote(_Frozen):
    """Two sources disagree: what v2.2 does and why."""

    other: SourceRef
    choice: str
    basis: Literal["later_source", "stated"]


class RuleKind(str, Enum):
    """What a rule says: where a part goes, what must not be, a choice, or a plant property."""

    PLACE = "place"
    FORBID = "forbid"
    ALTERNATIVE = "alternative"
    PLANT = "plant"


class RuleStatus(str, Enum):
    """ENCODED: the generator follows it. DEFERRED: read, not built, with a reason."""

    ENCODED = "encoded"
    DEFERRED = "deferred"


class HandbookRule(_Frozen):
    """One rule of the registry."""

    rule_id: str
    title: str
    statement: str  # a paraphrase, never a quote
    sources: tuple[SourceRef, ...]
    kind: RuleKind
    status: RuleStatus = RuleStatus.ENCODED
    since: Literal["v2.1", "v2.2"] = "v2.2"  # v2.1: already true, now cited and tested
    conflict: ConflictNote | None = None
    sampling_unit: Literal["train", "item"] | None = None  # ALTERNATIVE rules only
    declared_parameters: tuple[str, ...] = ()  # config paths of the declared weights
    exception_codes: tuple[str, ...] = ()  # the only allowed reasons for the rule to be absent
    check: str | None = None  # dotted path, or `pending:<task>`; None iff DEFERRED
    deferral_reason: str | None = None

    @model_validator(mode="after")
    def _well_formed(self) -> Self:
        rid = self.rule_id
        if not _RULE_ID.match(rid):
            raise ValueError(f"expected a rule id like 'TOG192-RECIP-NO-CHECK', got {rid!r}")
        if not self.sources:
            raise ValueError(f"{rid}: a rule needs at least one source")
        if any(s.book == "DESIGN" for s in self.sources) and not rid.startswith(_DERIVED_PREFIXES):
            raise ValueError(f"{rid}: only PLT-/PRS- rules may cite DESIGN")
        deferred = self.status is RuleStatus.DEFERRED
        if deferred != (self.check is None):
            raise ValueError(f"{rid}: check must be None exactly when the rule is DEFERRED")
        if deferred != (self.deferral_reason is not None):
            raise ValueError(f"{rid}: a deferral reason is required exactly for DEFERRED rules")
        if (self.kind is RuleKind.ALTERNATIVE) != (self.sampling_unit is not None):
            raise ValueError(f"{rid}: a sampling unit is required exactly for ALTERNATIVE rules")
        return self


class Violation(_Frozen):
    """One thing a check found wrong."""

    rule_id: str
    node_id: str
    detail: str


class CheckResult(_Frozen):
    """What a check found: how many things it looked at, and what was wrong."""

    checked: int
    violations: tuple[Violation, ...] = ()
    exceptions: dict[str, int] = {}


Check = Callable[[RuleView], CheckResult]


def is_pending(rule: HandbookRule) -> bool:
    """True when the rule's check is still owed by a later task."""
    return rule.check is not None and rule.check.startswith(PENDING_PREFIX)


def pending_task(rule: HandbookRule) -> str:
    """The task that owes a pending rule's check, for example `T3`."""
    if not is_pending(rule) or rule.check is None:
        raise ValueError(f"expected a pending rule, but {rule.rule_id} has check {rule.check!r}")
    return rule.check.removeprefix(PENDING_PREFIX)


def resolve_check(rule: HandbookRule) -> Check:
    """Import the check of a wired rule.

    Raises:
        ValueError: the rule is deferred or its check is still pending.
        ImportError, AttributeError: the dotted path does not lead to a function.
    """
    if rule.check is None or is_pending(rule):
        raise ValueError(f"expected a wired check for {rule.rule_id}, got {rule.check!r}")
    module_path, _, function_name = rule.check.rpartition(".")
    return getattr(importlib.import_module(module_path), function_name)  # type: ignore[no-any-return]


class RuleRow(_Frozen):
    """One line of a plant's rule report."""

    rule_id: str
    checked: int
    violations: int
    exceptions: dict[str, int] = {}


class RuleReport(_Frozen):
    """What `verify_plant` found; written as `<corpus>/rules.json` once v2.2 generation lands."""

    generator_version: str
    rows: tuple[RuleRow, ...]
