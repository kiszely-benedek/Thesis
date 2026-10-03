"""A toy plant for the need-aware tests, built on `qa_routing_toy.ToyCorpus`.

Flow (one pipe per arrow; `~` is an off-page cut), unit in brackets:

    S1: P-1 [1] -> XV-1 [1] ~ S2: P-2 [1] ~ S3: P-3 [2]

`XV-1` is a ball valve (an operated valve); every other item is a pump. Each sheet also holds
unconnected junk pumps, so "only the selected items" is visibly smaller than "the whole sheet".
"""

from __future__ import annotations

from typing import Any

from plantgraph.graph.schema import NodeClass
from plantgraph.qa.need.classifiers import NeedClassifier
from plantgraph.qa.strategies.hierarchical_need import NeedAwareHierarchical
from qa_routing_toy import ToyCorpus

#: Big enough that no test ever hits the limit unless it sets its own.
UNLIMITED = 10**9

ISOLATION_QUESTION = "To isolate P-3 from all upstream equipment, which valves must be closed?"
PATH_QUESTION = "Trace the process flow path from P-1 to P-3. List every equipment item and valve."


def need_toy(*, junk_per_sheet: int = 3) -> ToyCorpus:
    """The three-sheet chain `P-1 -> XV-1 ~ P-2 ~ P-3` with junk on every sheet."""
    toy = ToyCorpus()
    toy.item("S1", "a", "P-1", unit_id="1")
    toy.item("S1", "v1", "XV-1", node_class=NodeClass.BALL_VALVE, unit_id="1")
    toy.flow("S1", "a", "v1")
    toy.item("S2", "m", "P-2", unit_id="1")
    toy.item("S3", "t", "P-3", unit_id="2")
    toy.cut("S1", "v1", "S2", "m", "c1")
    toy.cut("S2", "m", "S3", "t", "c2")
    for sheet in ("S1", "S2", "S3"):
        for index in range(junk_per_sheet):
            toy.item(sheet, f"j{sheet}{index}", f"J-{sheet}-{index}", unit_id="9")
    return toy


def need_strategy(
    toy: ToyCorpus,
    classifier: NeedClassifier,
    *,
    max_context_chars: int = UNLIMITED,
    tau: float = 0.0,
    sheet_hops: int = 0,
) -> NeedAwareHierarchical:
    """A need-aware strategy over `toy` whose fallback is flow route + drop-rings."""
    params: dict[str, Any] = {"route_mode": "flow_path", "budget_mode": "drop_rings"}
    return NeedAwareHierarchical(
        toy.view(),
        classifier,
        sheet_hops=sheet_hops,
        max_context_chars=max_context_chars,
        tau=tau,
        **params,
    )
