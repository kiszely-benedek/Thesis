"""Gate checks and scoring that may freely see the answer key (design `kg-construction.md` §5.6-§6).

`plantgraph.resolution` must never import back into this package (§5.7 — enforced
by an AST test): the resolver stays blind to the splitter and to OPEN100, and this
package exists precisely to compare that blind output against the answer key.
"""

from __future__ import annotations
