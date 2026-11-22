"""The rule catalogue: every encoded rule of design 4.1-4.8 and the deferred groups of 4.9.

The entries are data, in `catalogue_a.py`, `catalogue_b.py`, `catalogue_c.py` and
`catalogue_deferred.py`; this module joins them and answers lookups.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.rules.catalogue_a import IDENTIFICATION, PUMPS, VALVE_POSITIONS
from plantgraph.benchmark.v2.rules.catalogue_b import (
    COMPRESSORS,
    CONTROL,
    EXCHANGERS,
    PROTECTION,
)
from plantgraph.benchmark.v2.rules.catalogue_c import NETWORKS_AND_PRESSURE
from plantgraph.benchmark.v2.rules.catalogue_deferred import DEFERRED
from plantgraph.benchmark.v2.rules.registry import HandbookRule, RuleStatus

#: encoded rules in the order of design 4.1 to 4.8
ENCODED: tuple[HandbookRule, ...] = (
    *IDENTIFICATION,
    *VALVE_POSITIONS,
    *PUMPS,
    *COMPRESSORS,
    *EXCHANGERS,
    *CONTROL,
    *PROTECTION,
    *NETWORKS_AND_PRESSURE,
)


def all_rules() -> tuple[HandbookRule, ...]:
    """Every rule, encoded first, then deferred."""
    return (*ENCODED, *DEFERRED)


def rules_with_status(status: RuleStatus) -> tuple[HandbookRule, ...]:
    """The rules that are ENCODED, or the ones that are DEFERRED."""
    return tuple(rule for rule in all_rules() if rule.status is status)


def rule_by_id(rule_id: str) -> HandbookRule:
    """The rule with this id.

    Raises:
        KeyError: no such rule; the message lists nothing, the id is what to look for.
    """
    for rule in all_rules():
        if rule.rule_id == rule_id:
            return rule
    raise KeyError(f"expected a rule id from the catalogue, got {rule_id!r}")
