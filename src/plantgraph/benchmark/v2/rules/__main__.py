"""`python -m plantgraph.benchmark.v2.rules --table`: the registry as a Markdown table.

The thesis appendix is this table, so it is printed from the catalogue, never typed by hand.
"""

from __future__ import annotations

import argparse

from plantgraph.benchmark.v2.rules.catalogue import all_rules
from plantgraph.benchmark.v2.rules.registry import (
    HandbookRule,
    RuleStatus,
    SourceRef,
    is_pending,
    pending_task,
)

_HEADER = "| Id | Kind | Since | Status | Sources | Check |"
_RULER = "|---|---|---|---|---|---|"


def _sources(rule: HandbookRule) -> str:
    return "; ".join(_source(s) for s in rule.sources)


def _source(source: SourceRef) -> str:
    unchecked = "" if source.page_checked else " (section only)"
    return f"{source.book} {source.locator}{unchecked}"


def _check_cell(rule: HandbookRule) -> str:
    if rule.status is RuleStatus.DEFERRED:
        return f"none: {rule.deferral_reason}"
    return f"pending {pending_task(rule)}" if is_pending(rule) else "wired"


def _row(rule: HandbookRule) -> str:
    cells = (
        rule.rule_id, rule.kind.value, rule.since, rule.status.value, _sources(rule),
        _check_cell(rule),
    )  # fmt: skip
    return "| " + " | ".join(cells) + " |"


def registry_table() -> str:
    """The whole registry as Markdown, one rule per row, then the counts."""
    rules = all_rules()
    rows = [_HEADER, _RULER, *(_row(rule) for rule in rules)]
    encoded = sum(r.status is RuleStatus.ENCODED for r in rules)
    wired = sum(r.status is RuleStatus.ENCODED and not is_pending(r) for r in rules)
    rows.append("")
    rows.append(
        f"{encoded} encoded rules ({wired} with a wired check), "
        f"{len(rules) - encoded} deferred groups."
    )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> None:
    """Print the registry table."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.benchmark.v2.rules")
    parser.add_argument("--table", action="store_true", required=True, help="print the table")
    parser.parse_args(argv)
    print(registry_table())


if __name__ == "__main__":
    main()
