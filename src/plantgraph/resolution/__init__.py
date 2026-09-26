"""A vékony resolver csomagja: lapok -> egyesített üzemgráf, válaszkulcs nélkül.

A bemenet mindig `SheetGraph` — sosem `SplitManifest`, sosem `OccurrenceMap`
(design `kg-construction.md` §4.2, D1 döntés). `localize.py` és `contract.py`
zárja be a splitter és az importáló szivárgásait (§4.1), mielőtt bármi ide
kerülne; a resolver saját lépései (párosítás, azonosság, egyesítés) csak azt
látják, ami egy valódi rajzon is olvasható lenne. Ez a csomag ezért sosem
importál `plantgraph.benchmark.splitter`-t, `rejoin`-t, `strategies`-t vagy
`plantgraph.eval`-t (§5.7) — ezt egy külön teszt is ellenőrzi.
"""

from __future__ import annotations
