"""Kapuk és pontszámítás, ami szabadon látja a válaszkulcsot (design `kg-construction.md` §5.6-§6).

`plantgraph.resolution` sosem importálhat vissza ebbe a csomagba (§5.7 — egy
AST-teszt ellenőrzi): a resolver vak marad a splitterre és az OPEN100-ra, ez a
csomag pedig pont azért létezik, hogy a vak kimenetet a válaszkulccsal
összevesse.
"""

from __future__ import annotations
