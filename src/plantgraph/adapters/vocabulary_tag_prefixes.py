"""The tag prefix of each schema class: the letters before the number (`P-1203`, `GTV-12107`).

A **tag** is the identifier printed next to an item on a drawing. Real companies each use their own
prefixes; these are a declared, OPEN100-style set (generator-v2-realism.md section 4, ADR-0057), not
a frequency claim. A class missing from this table has no prefix: either the drawing prints no tag
for it (a pipe tee, a reducer), or the generator never places it (a pyDEXPI parent class).

Instrument prefixes hold the ISA first letter as `{var}`: a transmitter is `{var}T`, a controller
`{var}IC` (ISA-5.1 is the instrument-letter standard).
"""

from __future__ import annotations

TAG_PREFIXES: dict[str, str] = {
    # --- equipment ---
    "Compressor": "C",  # v1's generic compressor; v2 pumps and compressors use the finer classes
    "HeatExchanger": "E",  # v1's generic exchanger
    "CentrifugalPump": "P",
    "ReciprocatingPump": "P",
    "RotaryPump": "P",
    "EjectorPump": "EJ",
    "CentrifugalCompressor": "K",
    "ReciprocatingCompressor": "K",
    "RotaryCompressor": "K",
    "AirEjector": "EJ",
    "Tank": "TK",
    "PressureVessel": "V",
    "ProcessColumn": "T",
    "TubularHeatExchanger": "E",
    "PlateHeatExchanger": "E",
    "SpiralHeatExchanger": "E",
    "AirCoolingSystem": "EA",
    "ElectricHeater": "EH",
    "Furnace": "H",
    "GravitationalSeparator": "V",
    "ScrubbingSeparator": "V",
    "ElectricalSeparator": "DS",
    "LiquidFilter": "F",
    "GasFilter": "F",
    "StaticMixer": "M",
    "RotaryMixer": "M",
    "Agitator": "M",
    # --- piping: operated valves (angle bodies take their straight body's code) ---
    "GateValve": "GTV",
    "GlobeValve": "GV",
    "BallValve": "BV",
    "ButterflyValve": "BFV",
    "NeedleValve": "NV",
    "PlugValve": "PGV",
    "StraightwayValve": "SWV",
    "AngleBallValve": "BV",
    "AngleGlobeValve": "GV",
    "AnglePlugValve": "PGV",
    # --- piping: check valves ---
    "CheckValve": "CHV",
    "SwingCheckValve": "CHV",
    "GlobeCheckValve": "CHV",
    # --- piping: safety devices ---
    "SpringLoadedGlobeSafetyValve": "PSV",
    "SpringLoadedAngleGlobeSafetyValve": "PSV",
    "RuptureDisc": "PSE",
    "BreatherValve": "PVSV",
    "FlameArrestor": "FA",
    # --- piping: inline primary elements ---
    "FlowMeasuringElement": "FE",
    "VenturiTube": "FE",
    "FlowNozzle": "FE",
    "ElectromagneticFlowMeter": "FE",
    "MassFlowMeasuringElement": "FE",
    "PositiveDisplacementFlowMeter": "FE",
    "TurbineFlowMeter": "FE",
    "VolumeFlowMeasuringElement": "FE",
    "VariableAreaFlowMeter": "FI",  # a local rotameter, read on site
    # --- piping: tagged fittings ---
    "Strainer": "STR",
    "ConicalStrainer": "STR",
    "RestrictionOrifice": "FO",
    "SteamTrap": "ST",
    "SightGlass": "SG",
    "IlluminatedSightGlass": "SG",
    "InLineMixer": "MX",
    "PipeFlangeSpade": "SB",  # a "skillet blind"
    "PipeFlangeSpacer": "SB",
    "Silencer": "SL",
    # --- instrumentation ---
    "ProcessSignalGeneratingFunction": "{var}T",
    "ProcessInstrumentationFunction": "{var}IC",
    "ProcessControlFunction": "{var}IC",
}
