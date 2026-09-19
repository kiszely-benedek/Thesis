"""A többlapos benchmark: szintetikus üzemgráf-generátor, splitter és OPEN100 megoldókulcs-építő.

`generator.py`/`generator_models.py` egy üzem topológiáját tervezi meg,
`splitter.py` (a hozzá tartozó `strategies.py`, `connectors.py`, `rejoin.py`
segédmodulokkal) lapokra vágja, `open100/` pedig ugyanezt a megoldókulcs-alakot
(`models.py`) valódi rajzokból nyeri vissza. Lásd `models.py` modul-docstringjét
a két forrás közös szerződéséről.
"""
