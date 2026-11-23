"""A small counter the checklist checks share: items looked at, items missing, codes used."""

from __future__ import annotations

from collections import Counter

from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation


class Tally:
    """Counts what a check looked at, and collects what was missing and which codes excused it."""

    def __init__(self, rule_id: str) -> None:
        self.rule_id = rule_id
        self.checked = 0
        self.violations: list[Violation] = []
        self.codes: Counter[str] = Counter()

    def present(self) -> None:
        """An item looked at and found drawn."""
        self.checked += 1

    def excused(self, code: str) -> None:
        """An item looked at and left out for the omission, declaration or scope `code`."""
        self.checked += 1
        self.codes[code] += 1

    def missing(self, node: str, item: str) -> None:
        """An item looked at that is neither drawn nor excused."""
        self.checked += 1
        detail = f"expected {item} on {node} or an omission code, found neither"
        self.violations.append(Violation(rule_id=self.rule_id, node_id=node, detail=detail))

    def result(self) -> CheckResult:
        """The `CheckResult`, with the codes sorted so reports compare byte for byte."""
        return CheckResult(
            checked=self.checked,
            violations=tuple(self.violations),
            exceptions=dict(sorted(self.codes.items())),
        )
