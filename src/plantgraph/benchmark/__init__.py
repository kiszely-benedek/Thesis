"""The multi-sheet benchmark: synthetic plant-graph generator, splitter, and OPEN100 answer key.

`generator.py`/`generator_models.py` design a plant's topology (its equipment and
piping layout), `splitter.py` (with its `strategies.py`, `connectors.py`, `rejoin.py`
helper modules) cuts that topology into sheets — the individual drawing pages a real
P&ID set is split across — and `open100/` recovers the same answer-key shape
(`models.py`) from real drawings instead. See the module docstring of `models.py`
for the contract shared by both sources.
"""
