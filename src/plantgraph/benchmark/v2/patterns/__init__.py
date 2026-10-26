"""Process patterns: the reusable blocks a plant drawing is built from (design realism 7).

A **process pattern** is a group of equipment that belongs together on a drawing, with its piping
trims and instrument loops: a tank farm with its transfer pumps, a flash drum, a filter package. A
pattern function takes a `PatternContext` and returns a `PatternInstance`: a plan for one process
unit, its typed ports and the drawing group of each machine. The flowsheet grammar (a later task)
only wires ports; it never reaches inside a pattern.
"""
