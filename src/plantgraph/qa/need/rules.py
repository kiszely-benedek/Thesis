"""The rule classifier: an ordered table of wording patterns, first match wins (design §4.2).

Each rule is a regular expression over the *masked* question (tags written `<TAG>`, unit ids
`<UNIT>`, see `anchors.mask_anchors`) plus an optional condition on how many anchors the
question names. The patterns were written from the dev question templates only
(`questions/templates.py`, the dev-new templates of §8.2), with a few obvious synonyms of the
same wording. Text that matches no rule is `GENERIC`: the strategy then falls back to the
generic Hierarchical, so a wording the table has not seen costs accuracy, never correctness.

The anchor counts are conditions on a *rule*, never on the label: a `PATH` question that names
one tag still gets the label `PATH`, and the strategy's precondition check sends it to the
fallback (`programs.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from plantgraph.qa.need.classifiers import NeedDecision, NeedInput
from plantgraph.qa.need.labels import NeedLabel


@dataclass(frozen=True)
class NeedRule:
    """One wording pattern, the label it gives, and the anchor counts it needs."""

    pattern: re.Pattern[str]
    label: NeedLabel
    #: The rule needs at least this many unit anchors.
    min_units: int = 0
    #: The rule needs at most this many tag anchors; `None` for no limit.
    max_tags: int | None = None

    def applies(self, need_input: NeedInput) -> bool:
        """True when the wording matches and the anchor counts allow it."""
        if need_input.n_unit_anchors < self.min_units:
            return False
        if self.max_tags is not None and need_input.n_tag_anchors > self.max_tags:
            return False
        return self.pattern.search(need_input.masked_text) is not None


def _rule(pattern: str, label: NeedLabel, **conditions: int) -> NeedRule:
    return NeedRule(re.compile(pattern, re.IGNORECASE), label, **conditions)


#: Order matters: the first rule that applies decides. A narrower wording goes before a broader one.
RULES: tuple[NeedRule, ...] = (
    # "... unit <UNIT> ..." with no item named: the question is about the unit itself.
    _rule(r"\bunit\b", NeedLabel.UNIT_SCOPE, min_units=1, max_tags=0),
    # Isolation: block valves are the boundary, so stop at the first operated valve.
    _rule(r"\bisolat\w*\b.*\bupstream\b", NeedLabel.UPSTREAM_TO_FIRST_VALVE),
    _rule(r"\bisolat\w*\b.*\bdownstream\b", NeedLabel.DOWNSTREAM_TO_FIRST_VALVE),
    _rule(r"\bindirectly\b|\ball downstream\b|\bdownstream of\b", NeedLabel.DOWNSTREAM_ALL),
    _rule(
        r"\bultimately feeds?\b|\bsource items?\b|\bupstream of\b|\ball upstream\b",
        NeedLabel.UPSTREAM_ALL,
    ),
    _rule(
        r"\bdirectly (upstream|before|into|feeds?)\b|\bfeeds? <TAG> directly\b"
        r"|\bimmediately (upstream|before)\b",
        NeedLabel.NEIGHBOURS_UPSTREAM,
    ),
    _rule(
        r"\breceives? flow directly from\b|\bdirectly (downstream|after)\b"
        r"|\bimmediately (downstream|after)\b",
        NeedLabel.NEIGHBOURS_DOWNSTREAM,
    ),
    _rule(
        r"\binstruments?\b|\bcontrollers?\b|\bactuated\b|\bmeasures?\b|\bcontrol loop\b|\bsignal\b",
        NeedLabel.SIGNAL_CHAIN,
    ),
    _rule(r"\bflow path\b|\b(path|route) (from|between)\b|\breach(es)?\b", NeedLabel.PATH),
    _rule(
        r"\bwhat type\b|\btype of item\b|\bwhich sheets?\b|\bon which sheets\b"
        r"|\bwhich unit is\b|\blocated in\b|\bsame unit\b",
        NeedLabel.ITEM,
    ),
)


class RuleNeedClassifier:
    """Classifies by the first rule of `RULES` that applies; no confidence, no cost."""

    name = "rules"

    def classify(self, need_input: NeedInput) -> NeedDecision:
        """The first matching rule's label, else `GENERIC`."""
        for rule in RULES:
            if rule.applies(need_input):
                return NeedDecision(label=rule.label, classifier=self.name)
        return NeedDecision(label=NeedLabel.GENERIC, classifier=self.name)
