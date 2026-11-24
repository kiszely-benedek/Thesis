"""The gold side of scope R (replication) on a v2.2 plant: one refusal rule for untagged valves.

**Scope R** is the EXP-0008 question recipe, re-run on v2.2 plants; its answers stay topological
(any piping path, whatever the valve positions). A v2.2 document may print no tag on its manual
and check valves, and a question that must name such a valve then has nothing to name. The
generator therefore **refuses** the candidate rather than rewording it (user: natural questions
only), and counts the refusals per family so the loss is visible.

One rule, in one place:

- family code reads a node's printed name only through `printed_name`, which returns the tag, or
  the fixed `UNTAGGED_MARKER` for a node that prints none;
- after the candidates are built, `refuse_untagged` drops every question whose text, anchors or
  reference carries the marker. A refused candidate still took its random draw, so a plant with no
  untagged valve (every v1 and v2.1 plant) produces the same questions as before.

An untagged valve stays a path item (`common.is_path_item`): it stops the "directly downstream"
walk, it is counted by VALVES_ON_PATH, and it sits on FLOW_PATH routes, where it refuses the pair.
"""

from __future__ import annotations

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from plantgraph.qa.models import Question, QuestionFamily

#: What a question would print for a node with no tag. No real tag contains `<`, so the marker can
#: never be mistaken for one.
UNTAGGED_MARKER = "<untagged>"

#: families with no scope R questions on v2.2, fixed before any seed is drawn: whether an item has
#: a fully tagged isolation set depends on the document's tagging draw, so R would ask about a
#: different population on a tagged plant than on an untagged one (design 17.15 S5). Both arms
#: answer them in scope X instead.
SCOPE_R_UNAVAILABLE_FAMILIES: tuple[QuestionFamily, ...] = (
    QuestionFamily.UPSTREAM_ISOLATION,
    QuestionFamily.DOWNSTREAM_ISOLATION,
)


class RefusedShare(BaseModel):
    """How many candidates a refusal rule removed, for the per-plant report."""

    model_config = ConfigDict(frozen=True)

    rule: str
    candidates: int = Field(ge=0)
    refused: int = Field(ge=0)

    @property
    def share(self) -> float:
        """Refused over candidates; 0.0 when there were no candidates."""
        return self.refused / self.candidates if self.candidates else 0.0


def printed_name(plant: nx.DiGraph[str], node_id: str) -> str:
    """The tag a node prints, or `UNTAGGED_MARKER` when it prints none."""
    tag = plant.nodes[node_id].get("tag")
    return str(tag) if tag else UNTAGGED_MARKER


def carries_marker(question: Question) -> bool:
    """Whether the question's text, anchors or reference had to name an untagged node."""
    shown = [question.text, *question.anchors, str(question.reference)]
    return any(UNTAGGED_MARKER in part for part in shown)


def refuse_untagged(
    candidates: dict[QuestionFamily, list[Question]],
) -> tuple[dict[QuestionFamily, list[Question]], dict[QuestionFamily, RefusedShare]]:
    """Drop every candidate that names an untagged node; count the refusals per family.

    Returns the kept candidates (same families, same order) and one `RefusedShare` per family.
    """
    kept: dict[QuestionFamily, list[Question]] = {}
    shares: dict[QuestionFamily, RefusedShare] = {}
    for family, questions in candidates.items():
        kept[family] = [q for q in questions if not carries_marker(q)]
        shares[family] = RefusedShare(
            rule="untagged_answer",
            candidates=len(questions),
            refused=len(questions) - len(kept[family]),
        )
    return kept, shares
