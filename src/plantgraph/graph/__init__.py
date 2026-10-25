"""The graph schema package.

This holds what the generator emits and the splitter cuts up: the node and
relationship types, the properties required on each, and the functions that check
them (`docs/private/40-design/plant-generator.md` §4). The class list is a generated table
(`schema_vocabulary.py`, ADR-0058), so no pyDEXPI import is needed here. The package does not
import `pydexpi`, and knows nothing about the `benchmark` package — the latter builds on
top of this one, never the other way round.
"""

from __future__ import annotations
