"""Checks of the conventions a document keeps on every sheet: manual-valve tags, letters, naming.

A **document** is one contractor's drawing set (design 5, `documents.py`). A convention that holds
for a document holds for every unit of it, process units and network units alike, so these checks
group the plant's units by document before they compare anything.

A **manual valve** is one a person turns: a gate, ball or check valve with no actuator. An
**automatic valve** has an actuator; its tag, like a safety device's, is always printed.
"""

from __future__ import annotations

from plantgraph.benchmark.v2.documents import DocumentRecord, document_of_train
from plantgraph.benchmark.v2.network_models import PLANT_INTERAREA_AREA
from plantgraph.benchmark.v2.rules.registry import CheckResult, Violation
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.vocabulary import MANUAL_VALVE_CLASSES
from plantgraph.graph.schema import VALVE_CLASSES, Relation

_NOT_APPLICABLE = CheckResult(checked=0)
_RULE = "TOG113-MANUAL-VALVE-TAGS"


def unit_documents(view: RuleView) -> dict[int, int]:
    """Unit number -> its document, for every process, header and interarea unit of the plant."""
    return view.cached("unit_documents", lambda: _unit_documents(view))


def _unit_documents(view: RuleView) -> dict[int, int]:
    plan = view.plan
    per_document = view.trains_per_document
    found = {u.slot.unit_no: document_of_train(u.slot.train_no, per_document) for u in plan.units}
    for network in plan.network_units:
        # the plant's interarea unit has area 0 and takes the conventions of document 1
        area = max(network.area_no, PLANT_INTERAREA_AREA + 1)
        found[network.unit_no] = area
    return found


def document_of_node(view: RuleView, node: str) -> int:
    """The document a node's unit belongs to."""
    return unit_documents(view)[int(view.graph.nodes[node]["unit_id"])]


def _is_automatic(view: RuleView, node: str) -> bool:
    """True for a valve that has an actuator on it."""
    return any(
        data["relation"] == Relation.CONTROL.value
        for _, _, data in view.graph.in_edges(node, data=True)
    )


def _valves(view: RuleView) -> list[str]:
    nodes = view.graph.nodes
    return sorted(n for n, d in nodes(data=True) if d["node_class"] in VALVE_CLASSES)


def _tag_problem(view: RuleView, valve: str, record: DocumentRecord) -> str | None:
    """What is wrong with the printing of a valve's tag in its document, or None."""
    data = view.graph.nodes[valve]
    has_tag = bool(data.get("tag"))
    manual = data["node_class"] in MANUAL_VALVE_CLASSES and not _is_automatic(view, valve)
    if not manual:  # automatic valves and safety devices are always tagged (Toghraei p.113)
        return None if has_tag else f"expected a tag on {data['node_class']} {valve}, found none"
    if has_tag == record.manual_valves_untagged:
        state = "untagged" if record.manual_valves_untagged else "tagged"
        found = "a tag" if has_tag else "no tag"
        return f"expected the manual valves of document {record.document_no} {state}, found {found}"
    return None


def check_manual_valve_tags(view: RuleView) -> CheckResult:
    """TOG113-MANUAL-VALVE-TAGS: every manual valve of a document is tagged, or none is."""
    if not view.handbook_enabled:
        return _NOT_APPLICABLE
    # rule TOG113-MANUAL-VALVE-TAGS: one tagging convention per document (Toghraei 2019 p.113)
    documents = {d.document_no: d for d in view.documents}
    valves = _valves(view)
    violations = [
        Violation(rule_id=_RULE, node_id=valve, detail=problem)
        for valve in valves
        if (problem := _tag_problem(view, valve, documents[document_of_node(view, valve)]))
    ]
    return CheckResult(checked=len(valves), violations=tuple(violations))


def check_document_conventions(view: RuleView) -> int:
    """TOG28-SPARE-NAMING, in part: every train of a document keeps the document's conventions.

    Raises:
        AssertionError: a train differs from its document (the form `checks_rules._run` reports).
    """
    if not view.handbook_enabled:
        return 0
    documents = {d.document_no: d for d in view.documents}
    per_document = view.trains_per_document
    for train in view.plan.trains:
        record = documents[document_of_train(train.train_no, per_document)]
        assert train.conventions == record.conventions, (
            f"train {train.train_no}: expected the conventions of document {record.document_no} "
            f"{record.conventions}, found {train.conventions}"
        )
    return len(view.plan.trains)
