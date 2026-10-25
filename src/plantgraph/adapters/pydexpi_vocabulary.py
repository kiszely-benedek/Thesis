"""Derive the schema's class vocabulary from pyDEXPI's own class hierarchy (ADR-0058).

pyDEXPI is the library that models P&IDs (piping and instrumentation diagrams) as Python classes.
The schema does not list every pyDEXPI class: a declared **allowlist** names the fluid-process ones
we keep (pumps, vessels, every piping component, the instrument functions), and one **ancestry
rule** turns each allowlisted class into its schema row:

- *labels*: the class and its pyDEXPI ancestors, cut at the first schema **root** (`Equipment`,
  `PipingComponent`, ...), plus the root's fixed extra labels. For example
  `CentrifugalPump:Pump:Equipment:TaggedPlantItem`.
- *category* and *piping kind*: read off the same ancestry.

`scripts/derive_schema_vocabulary.py` writes the result to `graph/schema_vocabulary.py`; a test
fails if that checked-in table drifts from this rule. The rule needs pyDEXPI, the table does not, so
`graph/` never imports pyDEXPI (ADR-0003).
"""

from __future__ import annotations

import inspect

import pydexpi.dexpi_classes.pydantic_classes as pydexpi_classes

from plantgraph.adapters.vocabulary_tag_prefixes import TAG_PREFIXES
from plantgraph.graph.schema_classes import NodeCategory, PipingKind, VocabularyRow

# ---- the allowlist: one name per line of intent; adding or removing a class is one edit here ----

#: the 25 equipment classes the generator can place, with the 8 pyDEXPI parents they come under
#: (a parent is in the schema so a real file's generic item imports as its family)
_EQUIPMENT: tuple[str, ...] = (
    "Pump", "CentrifugalPump", "ReciprocatingPump", "RotaryPump", "EjectorPump",
    "Compressor", "CentrifugalCompressor", "ReciprocatingCompressor", "RotaryCompressor",
    "AirEjector",
    "Vessel", "Tank", "PressureVessel", "ProcessColumn",
    "HeatExchanger", "TubularHeatExchanger", "PlateHeatExchanger", "SpiralHeatExchanger",
    "AirCoolingSystem", "ElectricHeater",
    "Heater", "Furnace",
    "Separator", "GravitationalSeparator", "ScrubbingSeparator", "ElectricalSeparator",
    "Filter", "LiquidFilter", "GasFilter",
    "Mixer", "StaticMixer", "RotaryMixer", "Agitator",
)  # fmt: skip

#: every non-custom pyDEXPI `PipingComponent` (a test checks this against pyDEXPI), plus the
#: spec-break marker, which is not a `PipingComponent` but sits on a line like one
_PIPING: tuple[str, ...] = (
    "OperatedValve", "GateValve", "GlobeValve", "BallValve", "ButterflyValve", "NeedleValve",
    "PlugValve", "StraightwayValve", "AngleValve", "AngleBallValve", "AngleGlobeValve",
    "AnglePlugValve",
    "CheckValve", "SwingCheckValve", "GlobeCheckValve",
    "SafetyValveOrFitting", "SpringLoadedGlobeSafetyValve", "SpringLoadedAngleGlobeSafetyValve",
    "RuptureDisc", "BreatherValve", "FlameArrestor",
    "InlinePrimaryElement", "FlowMeasuringElement", "VenturiTube", "FlowNozzle",
    "ElectromagneticFlowMeter", "MassFlowMeasuringElement", "VariableAreaFlowMeter",
    "PositiveDisplacementFlowMeter", "TurbineFlowMeter", "VolumeFlowMeasuringElement",
    "PipeTee", "PipeFitting", "PipeReducer", "BlindFlange", "LineBlind", "Flange",
    "FlangedConnection", "PipeCoupling", "ClampedFlangeCoupling", "Compensator", "Hose", "Funnel",
    "Penetration", "Strainer", "ConicalStrainer", "RestrictionOrifice", "SteamTrap", "SightGlass",
    "IlluminatedSightGlass", "InLineMixer", "Silencer", "VentilationDevice", "PipeFlangeSpade",
    "PipeFlangeSpacer",
    "PropertyBreak",
)  # fmt: skip

_INSTRUMENTATION: tuple[str, ...] = (
    "ProcessSignalGeneratingFunction",  # a sensor / transmitter
    "ProcessInstrumentationFunction",  # an indicator, alarm or switch
    "ProcessControlFunction",  # a controller (pyDEXPI's only subclass of the one above)
    "ActuatingFunction",  # the actuator of a control valve
    "ActuatingElectricalFunction",  # a start/stop or speed signal into a machine
)

#: the stubs the splitter places where a line leaves a sheet
_CONNECTORS: tuple[str, ...] = (
    "FlowOutPipeOffPageConnector",
    "FlowInPipeOffPageConnector",
    "FlowOutSignalOffPageConnector",
    "FlowInSignalOffPageConnector",
)

ALLOWLIST: tuple[str, ...] = _EQUIPMENT + _PIPING + _INSTRUMENTATION + _CONNECTORS

# ---- the rule ----------------------------------------------------------------------------------

#: schema roots -> the labels a root adds after its own class, e.g. `Equipment` is followed by its
#: pyDEXPI parent `TaggedPlantItem` (kept for byte-compatibility with v1's label chains)
_ROOT_SUFFIX: dict[str, tuple[str, ...]] = {
    "Equipment": ("TaggedPlantItem",),
    "PipingComponent": (),
    "PropertyBreak": (),
    "ProcessSignalGeneratingFunction": (),
    "ProcessInstrumentationFunction": (),
    "ActuatingFunction": (),
    "ActuatingElectricalFunction": (),
    "PipeOffPageConnector": (),
    "SignalOffPageConnector": (),
}
_ROOT_CATEGORY: dict[str, NodeCategory] = {
    "Equipment": NodeCategory.EQUIPMENT,
    "PipingComponent": NodeCategory.PIPING,
    "PropertyBreak": NodeCategory.PIPING,
    "ProcessSignalGeneratingFunction": NodeCategory.INSTRUMENTATION,
    "ProcessInstrumentationFunction": NodeCategory.INSTRUMENTATION,
    "ActuatingFunction": NodeCategory.INSTRUMENTATION,
    "ActuatingElectricalFunction": NodeCategory.INSTRUMENTATION,
    "PipeOffPageConnector": NodeCategory.CONNECTOR,
    "SignalOffPageConnector": NodeCategory.CONNECTOR,
}
#: the first ancestor found in this order decides the piping kind
_KIND_BY_ANCESTOR: tuple[tuple[str, PipingKind], ...] = (
    ("CheckValve", "check"),
    ("SafetyValveOrFitting", "safety"),
    ("InlinePrimaryElement", "primary_element"),
    ("OperatedValve", "operated"),
    ("PipeFitting", "fitting"),
)
#: classes whose kind is not the first match above: a pipe tee is a fitting in pyDEXPI but a
#: junction for us; the spec break is not a piping component at all
_KIND_OVERRIDE: dict[str, PipingKind] = {"PipeTee": "junction", "PropertyBreak": "break"}


def derive_vocabulary() -> list[VocabularyRow]:
    """One row per allowlisted class, in allowlist order, derived from pyDEXPI's hierarchy.

    Raises:
        ValueError: if the allowlist or the tag-prefix table names a class pyDEXPI does not have.
    """
    unknown_prefixes = sorted(set(TAG_PREFIXES) - set(ALLOWLIST))
    if unknown_prefixes:
        raise ValueError(f"tag prefixes for classes outside the allowlist: {unknown_prefixes}")
    return [_derive_row(name) for name in ALLOWLIST]


def _derive_row(name: str) -> VocabularyRow:
    dexpi_class = _pydexpi_class(name)
    ancestry = [ancestor.__name__ for ancestor in dexpi_class.__mro__]
    root = _first_root(name, ancestry)
    root_class = _pydexpi_class(root)
    labels = [
        ancestor.__name__
        for ancestor in dexpi_class.__mro__
        if _is_pydexpi_class(ancestor) and issubclass(ancestor, root_class)
    ]
    category = _ROOT_CATEGORY[root]
    return VocabularyRow(
        name=name,
        labels=(*labels, *_ROOT_SUFFIX[root]),
        category=category,
        piping_kind=_piping_kind(name, ancestry) if category is NodeCategory.PIPING else None,
        tag_prefix=TAG_PREFIXES.get(name),
        leaf=not _non_custom_subclasses(dexpi_class),
    )


def _pydexpi_class(name: str) -> type:
    found = getattr(pydexpi_classes, name, None)
    if not inspect.isclass(found):
        raise ValueError(f"pyDEXPI has no class named {name!r}; check ALLOWLIST and ancestry roots")
    return found


def _is_pydexpi_class(candidate: type) -> bool:
    """A class defined in pyDEXPI's class module (not a Python or pydantic base class)."""
    return candidate.__module__ == pydexpi_classes.__name__


def _first_root(name: str, ancestry: list[str]) -> str:
    for ancestor in ancestry:
        if ancestor in _ROOT_SUFFIX:
            return ancestor
    raise ValueError(
        f"{name!r} has no schema root in its ancestry {ancestry}; expected one of "
        f"{sorted(_ROOT_SUFFIX)}"
    )


def _piping_kind(name: str, ancestry: list[str]) -> PipingKind:
    if name in _KIND_OVERRIDE:
        return _KIND_OVERRIDE[name]
    for ancestor, kind in _KIND_BY_ANCESTOR:
        if ancestor in ancestry:
            return kind
    expected = [ancestor for ancestor, _ in _KIND_BY_ANCESTOR]
    raise ValueError(f"piping class {name!r} has none of the ancestors {expected} in {ancestry}")


def _non_custom_subclasses(dexpi_class: type) -> list[type]:
    """Subclasses of `dexpi_class` in pyDEXPI, without the `Custom*` extension points."""
    return [
        member
        for _, member in inspect.getmembers(pydexpi_classes, inspect.isclass)
        if _is_pydexpi_class(member)
        and member is not dexpi_class
        and issubclass(member, dexpi_class)
        and not member.__name__.startswith("Custom")
    ]
