"""The rule registry as data: ids, counts, checks, `# rule` code comments, the table CLI (3.2-3.4).

No plant is generated here; `test_rule_checks.py` runs the checks on plants.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pytest

import plantgraph.benchmark.v2 as v2_package
from plantgraph.benchmark.v2.rules import checks_v21
from plantgraph.benchmark.v2.rules.__main__ import main as table_main
from plantgraph.benchmark.v2.rules.catalogue import all_rules, rule_by_id, rules_with_status
from plantgraph.benchmark.v2.rules.registry import (
    HandbookRule,
    RuleKind,
    RuleStatus,
    SourceRef,
    is_pending,
    pending_task,
    resolve_check,
)
from plantgraph.benchmark.v2.rules.verify import pending_rules, wired_rules

_ENCODED = rules_with_status(RuleStatus.ENCODED)
_DEFERRED = rules_with_status(RuleStatus.DEFERRED)
_V2_SOURCE_DIR = Path(v2_package.__file__).parent
_RULE_COMMENT = re.compile(r"^\s*# rule ([A-Z0-9][A-Z0-9.-]*): (.*)$")

#: the checks still owed, by the task that builds them (design 13); T3 removed its seven, T4 its
#: two, T9 its eight and two of the unassigned (TOG207, TOG326), T9b the API14C-A8 pair, T11 its six
_PENDING_BY_TASK = {"T5": 5, "T6": 1, "T7": 5, "T8": 6, "T10": 4}


# ---- ids, counts -------------------------------------------------------------------------------


def test_rule_ids_are_unique() -> None:
    ids = [rule.rule_id for rule in all_rules()]
    assert len(ids) == len(set(ids)), [i for i, n in Counter(ids).items() if n > 1]


def test_the_catalogue_has_54_encoded_rules_19_of_them_plant_level_and_15_deferred_groups() -> None:
    """The design has 55 and 14; T3 deferred TOG73 (`test_tog73_line_view.py`)."""
    assert len(_ENCODED) == 54
    assert sum(rule.kind is RuleKind.PLANT for rule in _ENCODED) == 19
    assert len(_ENCODED) - 19 == 35
    assert len(_DEFERRED) == 15
    assert "TOG73-UNTAGGED-BRANCH-PIPES" in {rule.rule_id for rule in _DEFERRED}


def test_a_malformed_rule_is_refused() -> None:
    source = SourceRef(book="TOG2019", locator="p.1", page_checked=True)
    with pytest.raises(ValueError, match="rule id"):
        HandbookRule(rule_id="lower-case", title="t", statement="s", sources=(source,),
                     kind=RuleKind.PLACE, check="pending:T3")  # fmt: skip
    with pytest.raises(ValueError, match="only PLT-/PRS- rules may cite DESIGN"):
        HandbookRule(
            rule_id="TOG1-X",
            title="t",
            statement="s",
            sources=(SourceRef(book="DESIGN", locator="x", page_checked=True),),
            kind=RuleKind.PLACE,
            check="pending:T3",
        )
    with pytest.raises(ValueError, match="sampling unit"):
        HandbookRule(rule_id="TOG1-X", title="t", statement="s", sources=(source,),
                     kind=RuleKind.ALTERNATIVE, check="pending:T3")  # fmt: skip


def test_rule_by_id_names_what_it_expected_when_the_id_is_unknown() -> None:
    assert rule_by_id("TOG192-RECIP-NO-CHECK").kind is RuleKind.FORBID
    with pytest.raises(KeyError, match="expected a rule id from the catalogue"):
        rule_by_id("NOPE-1")


def test_the_one_source_conflict_is_recorded() -> None:
    conflicts = [rule.rule_id for rule in _ENCODED if rule.conflict is not None]
    assert conflicts == ["TOG192-RECIP-NO-CHECK"]


# ---- every encoded rule has a check, wired or explicitly pending ---------------------------------


def test_every_encoded_rule_has_a_check_and_every_deferred_rule_a_reason() -> None:
    assert all(rule.check for rule in _ENCODED)
    assert all(rule.check is None and rule.deferral_reason for rule in _DEFERRED)


def test_every_wired_check_resolves_to_a_function() -> None:
    wired = wired_rules()
    assert len(wired) == 33
    assert all(callable(resolve_check(rule)) for rule in wired)


def test_the_pending_checks_are_exactly_the_ones_each_later_task_owes() -> None:
    """A task that builds a check removes its rows here, so the debt is always visible."""
    owed = Counter(pending_task(rule) for rule in pending_rules())
    assert dict(owed) == _PENDING_BY_TASK
    assert sum(owed.values()) + len(wired_rules()) == len(_ENCODED)


def test_resolving_a_pending_check_is_refused() -> None:
    pending = next(rule for rule in _ENCODED if is_pending(rule))
    with pytest.raises(ValueError, match="expected a wired check"):
        resolve_check(pending)


def test_the_facade_exports_every_v21_invariant_check() -> None:
    expected = {
        f"check_s{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 19, 20, 21, 22, 23, 24)
    }
    assert set(checks_v21.__all__) == expected


# ---- `# rule <ID>: ... (<locator>)` comments in the generator code ------------------------------


def _rule_comments() -> list[tuple[str, str, str]]:
    """(file name, rule id, rest of the comment) for every `# rule` comment under `v2/`."""
    found = []
    for path in sorted(_V2_SOURCE_DIR.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _RULE_COMMENT.match(line)
            if match:
                found.append((path.name, match.group(1), match.group(2)))
    return found


def test_every_rule_comment_names_a_rule_of_the_registry() -> None:
    known = {rule.rule_id for rule in all_rules()}
    unknown = [(f, rid) for f, rid, _ in _rule_comments() if rid not in known]
    assert not unknown, f"comments cite rule ids that are not in the registry: {unknown}"


def test_every_wired_rule_is_applied_in_the_code_at_least_once() -> None:
    cited = {rid for _, rid, _ in _rule_comments()}
    missing = sorted(rule.rule_id for rule in wired_rules() if rule.rule_id not in cited)
    assert not missing, f"wired rules with no `# rule` comment in the generator: {missing}"


def test_the_page_in_a_rule_comment_is_a_locator_of_that_rule() -> None:
    for file_name, rule_id, text in _rule_comments():
        locators = [source.locator for source in rule_by_id(rule_id).sources]
        assert any(locator in text for locator in locators), (
            f"{file_name}: the comment for {rule_id} cites none of {locators}: {text!r}"
        )


# ---- the table CLI -------------------------------------------------------------------------------


def test_the_table_prints_one_row_per_rule_and_the_counts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    table_main(["--table"])
    lines = capsys.readouterr().out.splitlines()
    rows = [line for line in lines if line.startswith("| ") and not line.startswith("| Id")]
    assert len(rows) == 54 + 15
    assert any(line.startswith("| TOG192-RECIP-NO-CHECK |") for line in rows)
    assert lines[-1] == "54 encoded rules (33 with a wired check), 15 deferred groups."
