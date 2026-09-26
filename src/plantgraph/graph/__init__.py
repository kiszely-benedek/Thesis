"""The graph schema package.

This holds what the generator emits and the splitter cuts up: the node and
relationship types, the properties required on each, and the functions that check
them (`docs/private/40-design/plant-generator.md` §4). The package does not import
`pydexpi`, and knows nothing about the `benchmark` package — the latter builds on
top of this one, never the other way round.
"""

from __future__ import annotations
