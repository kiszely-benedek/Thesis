"""Which node classes a corpus's CLASS_NAME answer may name (ADR-0058 point 5, Q3).

A `LOOKUP_TYPE` question ("what kind of item is P-101?") is answered with a class name, and the
final-answer prompt lists the allowed names. v1 corpora keep one fixed list (the 21 v1 classes,
pinned in `final_answer.py`, so every recorded v1 prompt stays byte-identical). A v2 corpus draws
from a much larger vocabulary, so it lists the classes it actually contains.

A node carries a **label chain**: its own class plus its ancestor classes (a `CentrifugalPump` is
also a `Pump`). The load plan counts every label once per node, so the nodes whose *own* class is
`C` are the nodes labelled `C` minus those labelled by a descendant of `C`.
"""

from __future__ import annotations

from collections.abc import Mapping

from plantgraph.benchmark.generator_dispatch import AnyGeneratorConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.graph import schema
from plantgraph.store.neo4j_plan import LoadPlan


def own_class_names(label_counts: Mapping[str, int]) -> tuple[str, ...]:
    """The schema classes that at least one node has as its own class, sorted.

    Args:
        label_counts: label -> number of nodes carrying it (`LoadPlan.expected_node_labels`).

    Raises:
        ValueError: a count is smaller than the counts of its descendants, i.e. the labels do
            not come from the schema's label chains.
    """
    classes = [c.value for c in schema.NodeClass if c.value in label_counts]
    own_counts: dict[str, int] = {}
    # most specific first, so every descendant of a class is counted before the class itself
    for name in sorted(classes, key=lambda c: -len(schema.labels_for(c))):
        below = sum(n for d, n in own_counts.items() if name in schema.labels_for(d)[1:])
        own_counts[name] = label_counts[name] - below
        if own_counts[name] < 0:
            raise ValueError(
                f"expected label {name!r} to count at least its descendants' {below} nodes, "
                f"found {label_counts[name]}"
            )
    return tuple(sorted(name for name, count in own_counts.items() if count > 0))


def answer_class_names(
    generator_config: AnyGeneratorConfig | None, plan: LoadPlan
) -> tuple[str, ...] | None:
    """The CLASS_NAME vocabulary of a corpus, or `None` to keep the pinned v1 list.

    Only a v2 synthetic corpus gets its own list; v1 and Proteus corpora (no generator config,
    or a v1 one) return `None`.
    """
    if not isinstance(generator_config, GeneratorConfigV2):
        return None
    return own_class_names(plan.expected_node_labels)
