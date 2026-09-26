"""The project's only layer that knows about pyDEXPI — no other module ever imports it.

pyDEXPI is the third-party library that models P&IDs (piping and instrumentation
diagrams, the engineering drawings this project reasons about) as typed Python
objects, following the DEXPI data-exchange standard. Two modules make up this
package's content: `pydexpi_builder` (builds a real `DexpiModel` from the
generator's topology decisions) and `pydexpi_adapter` (turns that model into the
`nx.DiGraph` defined by `graph.schema`, via pyDEXPI's own loading and abstraction
steps). This is the only place in the codebase where the `pydexpi` package appears
(ADR-0003: pyDEXPI is AGPL-3.0 licensed, so it is kept behind a thin adapter —
see the "Import rule" in `plant-generator.md`).
"""
