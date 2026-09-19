"""A pyDEXPI-t ismerő rétege a projektnek — máshonnan pyDEXPI sosem importálódik.

Két modul adja a tartalmát: `pydexpi_builder` (a generátor topológia-döntéseiből
egy valódi `DexpiModel`-t épít) és `pydexpi_adapter` (ebből a modellből állítja
elő a `graph.schema` szerinti `nx.DiGraph`-ot, pyDEXPI saját betöltő- és
absztrakciós lépésein át). Ez az egyetlen hely a kódbázisban, ahol a `pydexpi`
csomag megjelenik (ADR-0003: a pyDEXPI AGPL-3.0 licencű, ezért vékony
adapter mögé zárva tartjuk — lásd `plant-generator.md` "Import rule").
"""
