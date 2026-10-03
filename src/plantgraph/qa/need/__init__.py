"""Need-aware retrieval: which evidence shape a question calls for (design note section 4).

- `labels`: the closed set of need labels (one per evidence shape, plus `GENERIC`).
- `classifiers`: the `NeedClassifier` interface and what a classifier may read.
- `rules`: the rule classifier, written from the dev question templates only.
- `programs`: one fixed program of plant-API primitives per label.
- `context`: the selected items as serialized text, cut to the budget farthest-first.

The strategy that wires these together is `strategies/hierarchical_need.py`. Nothing here may
import the harness, the question generator or any gold module (import-ban tests).
"""
