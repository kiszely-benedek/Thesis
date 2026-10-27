"""Which symbol (glyph) a schema class is drawn as in the ISO-style drawing - a rule, not a list.

A P&ID (piping and instrumentation diagram) draws every kind of item with its own standard symbol:
a pump is a circle with a triangle, a valve a bow-tie, a vessel a rounded rectangle. This module
maps a class to the *name* of such a symbol; `glyph_shapes.py` and friends draw the names.

The rule walks the class's label chain (the class, then its ancestors: `SwingCheckValve`,
`CheckValve`, ...) and takes the first entry of `GLYPH_FAMILIES`. A class with no entry falls back
to
its piping kind and, last, to its category. So a class the schema gains later is drawn as its
nearest ancestor without a code change; `GLYPH_FAMILIES` only lists where that is not enough.
"""

from __future__ import annotations

from collections.abc import Iterable

from plantgraph.demo.drawing.models import GlyphStyle
from plantgraph.graph import schema
from plantgraph.graph.schema import NodeCategory

#: The v1 generator's classes: a corpus made of these alone keeps the classic drawing.
_CLASSIC_CLASSES: frozenset[str] = schema.V1_IMPORTABLE_CLASSES

#: label -> glyph name. Order matters only in that a class is looked up before its ancestors, so a
#: leaf entry overrides its parent's. The first block is the 10 equipment parents plus column and
#: agitator, the second the leaf overrides where the parent's symbol would be wrong.
GLYPH_FAMILIES: dict[str, str] = {
    # equipment families
    "Pump": "pump",
    "Compressor": "compressor",
    "Vessel": "vessel",
    "ProcessColumn": "column",
    "HeatExchanger": "tubular_exchanger",
    "Heater": "furnace",
    "Separator": "separator",
    "Filter": "filter",
    "Mixer": "static_mixer",
    "Agitator": "agitator",
    # equipment leaves whose parent's symbol would be wrong
    "Tank": "tank",
    "ReciprocatingPump": "positive_pump",
    "RotaryPump": "positive_pump",
    "EjectorPump": "ejector",
    "AirEjector": "ejector",
    "PlateHeatExchanger": "plate_exchanger",
    "SpiralHeatExchanger": "spiral_exchanger",
    "AirCoolingSystem": "air_cooler",
    "ElectricHeater": "electric_heater",
    "ScrubbingSeparator": "scrubber",
    "ElectricalSeparator": "electric_separator",
    "RotaryMixer": "rotary_mixer",
    # operated valves (the parent `OperatedValve` is the plain bow-tie, see `_KIND_GLYPH`)
    "OperatedValve": "valve",
    "StraightwayValve": "valve",
    "GateValve": "gate_valve",
    "GlobeValve": "globe_valve",
    "BallValve": "ball_valve",
    "ButterflyValve": "butterfly_valve",
    "NeedleValve": "needle_valve",
    "PlugValve": "plug_valve",
    "AngleValve": "angle_valve",
    "AngleBallValve": "angle_valve",
    "AngleGlobeValve": "angle_valve",
    "AnglePlugValve": "angle_valve",
    # check valves
    "CheckValve": "check_valve",
    "SwingCheckValve": "swing_check_valve",
    # safety devices
    "SafetyValveOrFitting": "safety_valve",
    "SpringLoadedGlobeSafetyValve": "safety_valve",
    "SpringLoadedAngleGlobeSafetyValve": "safety_valve",
    "RuptureDisc": "rupture_disc",
    "BreatherValve": "breather_valve",
    "FlameArrestor": "flame_arrestor",
    # primary elements (flow meters)
    "InlinePrimaryElement": "flow_meter",
    "FlowMeasuringElement": "orifice_plate",
    "VenturiTube": "venturi",
    "FlowNozzle": "venturi",
    "ElectromagneticFlowMeter": "magnetic_meter",
    "MassFlowMeasuringElement": "coriolis_meter",
    "VariableAreaFlowMeter": "rotameter",
    "PositiveDisplacementFlowMeter": "displacement_meter",
    "TurbineFlowMeter": "turbine_meter",
    # fittings
    "PipeFitting": "flanges",
    "Flange": "flanges",
    "FlangedConnection": "flanges",
    "PipeCoupling": "flanges",
    "ClampedFlangeCoupling": "flanges",
    "PipeReducer": "reducer",
    "BlindFlange": "blind_flange",
    "LineBlind": "spectacle_blind",
    "PipeFlangeSpade": "spade",
    "PipeFlangeSpacer": "spacer",
    "Strainer": "strainer",
    "ConicalStrainer": "cone_strainer",
    "RestrictionOrifice": "restriction_orifice",
    "SteamTrap": "steam_trap",
    "SightGlass": "sight_glass",
    "IlluminatedSightGlass": "sight_glass",
    "InLineMixer": "inline_mixer",
    "Silencer": "silencer",
    "Compensator": "bellows",
    "Hose": "hose",
    "Funnel": "funnel",
    "VentilationDevice": "vent",
    "Penetration": "wall",
    "PipeTee": "junction",
    "PropertyBreak": "spec_break",
    # instruments: the bubble differs by where the instrument is mounted (ISA 5.1)
    "ProcessSignalGeneratingFunction": "field_bubble",
    "ProcessControlFunction": "control_room_bubble",
    "ProcessInstrumentationFunction": "control_room_bubble",
    "ActuatingFunction": "panel_bubble",
    "ActuatingElectricalFunction": "electrical_bubble",
}

#: Fallback by piping kind, for a piping class with no label entry (an unlisted valve is a bow-tie).
_KIND_GLYPH: dict[str, str] = {
    "operated": "valve",
    "check": "check_valve",
    "safety": "safety_valve",
    "fitting": "flanges",
    "junction": "junction",
    "primary_element": "flow_meter",
    "break": "spec_break",
}

#: Fallback by category, for a class with neither a label entry nor a piping kind.
_CATEGORY_GLYPH: dict[NodeCategory, str] = {
    NodeCategory.EQUIPMENT: "equipment_box",
    NodeCategory.OTHER: "equipment_box",  # `GenericItem`: a real file's class the schema lacks
    NodeCategory.CONNECTOR: "off_page_flag",
}

#: Glyphs drawn taller than the standard box, as (width factor, height factor) of it: a column is
#: tall and narrow. Used in the ISO style only.
TALL_GLYPHS: dict[str, tuple[float, float]] = {"column": (0.8, 1.3), "scrubber": (0.8, 1.3)}

#: Inline items (fittings, junctions, primary elements) by layout family, as (width, height) factors
#: of the standard box: small, so that they do not dominate the drawing. ISO style only.
SMALL_GLYPH_SIZE: dict[str, tuple[float, float]] = {
    "fitting": (0.55, 0.7),
    "primary_element": (0.55, 0.8),
    "junction": (0.3, 0.45),
    "break": (0.35, 0.6),
}


def glyph_of(node_class: str) -> str:
    """The glyph name for a schema class (`GLYPH_FAMILIES`, then piping kind, then category).

    Raises:
        ValueError: `node_class` is not in the schema, or it is a class that is never drawn
            (a structural class) and so has no glyph.
    """
    for label in schema.labels_for(node_class):
        if label in GLYPH_FAMILIES:
            return GLYPH_FAMILIES[label]
    spec = schema.CLASS_SPECS[schema.NodeClass(node_class)]
    if spec.piping_kind is not None:
        return _KIND_GLYPH[spec.piping_kind]
    if spec.category in _CATEGORY_GLYPH:
        return _CATEGORY_GLYPH[spec.category]
    raise ValueError(f"no glyph for node_class {node_class!r} (category {spec.category.value})")


def glyph_style_for(node_classes: Iterable[str]) -> GlyphStyle:
    """Return "iso" if any class is beyond the v1 vocabulary, else "classic" (v1 unchanged)."""
    return "iso" if any(name not in _CLASSIC_CLASSES for name in node_classes) else "classic"
