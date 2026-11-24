"""What a B corpus shows beyond an A corpus: one valve property, `operating_position`.

A valve's **normal operating position** says how it stands in ordinary operation: normally open
(NO), normally closed (NC), locked open or closed (LO, LC), car-sealed open or closed (CSO, CSC;
a car seal is a tamper tag that makes the position a controlled one). The fail action of an
automatic valve stays out (design 3: no question uses it).
"""

from __future__ import annotations

from typing import Final

from plantgraph.graph.schema import VISIBLE_NODE_PROPERTIES

OPERATING_POSITION: Final = "operating_position"

#: The six positions the generator draws (`benchmark.v2.plan_models.OperatingPosition`).
POSITION_CODES: Final[tuple[str, ...]] = ("NO", "NC", "LO", "LC", "CSO", "CSC")

#: Node properties the system under test may read on a B corpus.
VISIBLE_NODE_PROPERTIES_B: Final[frozenset[str]] = VISIBLE_NODE_PROPERTIES | {OPERATING_POSITION}

#: The item-property keys of the plant API on a B corpus (`node_class` is its own field).
ITEM_PROPERTY_KEYS_B: Final[frozenset[str]] = VISIBLE_NODE_PROPERTIES_B - {"node_class"}
