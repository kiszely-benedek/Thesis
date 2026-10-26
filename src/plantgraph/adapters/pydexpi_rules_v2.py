"""The three v2 edge rules of the pyDEXPI -> schema adapter, gated by the importable vocabulary.

pyDEXPI links a few objects by a plain *reference* field, which the conceptual graph shows as an
edge labelled `reference` with the field's name in `attr_name`. v2 turns two of them into schema
relations (design pid-vocabulary section 3.4, measured on a micro model):

- `reference/agitator`: a vessel to its stirrer, relation `has_agitator`;
- `reference/actuatingElectricalLocation`: a machine's start/stop input to the machine (through
  the machine's nozzle, which the graph abstraction folds away), relation `control`;
- `composition/actuatingElectricalFunctions` stays out: the signal line already carries that signal.

A v1 import must not change, so the rules apply only when the vocabulary is wider than v1's.
"""

from __future__ import annotations

from collections.abc import Mapping

from plantgraph.graph import schema
from plantgraph.graph.schema import Relation

_REFERENCE_RELATIONS: dict[str, Relation] = {
    "agitator": Relation.HAS_AGITATOR,
    "actuatingElectricalLocation": Relation.CONTROL,
}


def uses_v2_rules(vocabulary: frozenset[str]) -> bool:
    """True when `vocabulary` knows classes beyond v1's, so the v2 edge rules apply."""
    return not vocabulary <= schema.V1_IMPORTABLE_CLASSES


def v2_relation_of(attrs: Mapping[str, object]) -> tuple[Relation, bool] | None:
    """The relation of a v2 reference edge and whether to reverse it; None for any other edge."""
    if attrs.get("label") != "reference":
        return None
    relation = _REFERENCE_RELATIONS.get(str(attrs.get("attr_name")))
    if relation is None:
        return None
    return relation, False  # both run source -> target already: vessel -> agitator, AEF -> machine
