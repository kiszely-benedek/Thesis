"""A 12 valódi OPEN100 P&ID rajz feldolgozása: csatlakozó-kereséstől a megoldókulcsig.

Két szakaszban: `corpus.py`/`extract.py`/`crops.py` megkeresi a lapközi
csatlakozókat és képet készít róluk olvasásra (stage 1), `annotations.py` és
`manifest.py` a leolvasott feliratokból felépíti a végleges `SplitManifest`-et
(stage 2). Lásd `docs/private/40-design/open100-annotation.md`.
"""
