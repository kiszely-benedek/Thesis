"""The schema's node classes, categories and per-class record.

Split out of `schema.py` for the 400-line limit; import everything from `plantgraph.graph.schema`,
which re-exports it. Terms, for a reader who does not know process engineering:

- **P&ID**: a piping and instrumentation diagram, the technical drawing of a plant's pipes and
  instruments.
- **equipment**: the big items a pipe connects (pumps, tanks, heat exchangers); **piping
  component**: a small item inline on a pipe (a valve, a pipe tee, a flow meter).
- **node_class**: a pyDEXPI class name (e.g. `CentrifugalPump`). Its Neo4j label chain is the class
  name plus its ancestor classes, cut at the first "schema root" (`Equipment` plus its parent
  `TaggedPlantItem`, or `PipingComponent`).

The per-class facts (label chain, category, piping kind, tag prefix) are not written here: they are
derived from pyDEXPI's class hierarchy by `adapters/pydexpi_vocabulary.py` and stored in the
generated `schema_vocabulary.py` (ADR-0058). This module only holds the types and the enum.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class NodeCategory(str, Enum):
    """Which functional group a node_class belongs to."""

    EQUIPMENT = "equipment"
    PIPING = "piping"
    INSTRUMENTATION = "instrumentation"
    CONNECTOR = "connector"
    STRUCTURE = "structure"
    #: the `GenericItem` fallback's category, when pyDEXPI's ancestor chain has no schema root
    #: (ADR-0016, kg-construction.md section 3.1 "Label cut-off")
    OTHER = "other"


class NodeClass(str, Enum):
    """Every node class in the schema.

    98 classes come from the pyDEXPI allowlist (ADR-0058), 4 are structural classes that exist
    only in the graph store, and `GenericItem` is the fallback. A test keeps this list equal to
    the generated vocabulary table.
    """

    # --- equipment ---
    PUMP = "Pump"
    CENTRIFUGAL_PUMP = "CentrifugalPump"
    RECIPROCATING_PUMP = "ReciprocatingPump"
    ROTARY_PUMP = "RotaryPump"
    EJECTOR_PUMP = "EjectorPump"
    COMPRESSOR = "Compressor"
    CENTRIFUGAL_COMPRESSOR = "CentrifugalCompressor"
    RECIPROCATING_COMPRESSOR = "ReciprocatingCompressor"
    ROTARY_COMPRESSOR = "RotaryCompressor"
    AIR_EJECTOR = "AirEjector"
    VESSEL = "Vessel"
    TANK = "Tank"
    PRESSURE_VESSEL = "PressureVessel"
    PROCESS_COLUMN = "ProcessColumn"
    HEAT_EXCHANGER = "HeatExchanger"
    TUBULAR_HEAT_EXCHANGER = "TubularHeatExchanger"
    PLATE_HEAT_EXCHANGER = "PlateHeatExchanger"
    SPIRAL_HEAT_EXCHANGER = "SpiralHeatExchanger"
    AIR_COOLING_SYSTEM = "AirCoolingSystem"
    ELECTRIC_HEATER = "ElectricHeater"
    HEATER = "Heater"
    FURNACE = "Furnace"
    SEPARATOR = "Separator"
    GRAVITATIONAL_SEPARATOR = "GravitationalSeparator"
    SCRUBBING_SEPARATOR = "ScrubbingSeparator"
    ELECTRICAL_SEPARATOR = "ElectricalSeparator"
    FILTER = "Filter"
    LIQUID_FILTER = "LiquidFilter"
    GAS_FILTER = "GasFilter"
    MIXER = "Mixer"
    STATIC_MIXER = "StaticMixer"
    ROTARY_MIXER = "RotaryMixer"
    AGITATOR = "Agitator"
    # --- piping: operated valves ---
    OPERATED_VALVE = "OperatedValve"
    GATE_VALVE = "GateValve"
    GLOBE_VALVE = "GlobeValve"
    BALL_VALVE = "BallValve"
    BUTTERFLY_VALVE = "ButterflyValve"
    NEEDLE_VALVE = "NeedleValve"
    PLUG_VALVE = "PlugValve"
    STRAIGHTWAY_VALVE = "StraightwayValve"
    ANGLE_VALVE = "AngleValve"
    ANGLE_BALL_VALVE = "AngleBallValve"
    ANGLE_GLOBE_VALVE = "AngleGlobeValve"
    ANGLE_PLUG_VALVE = "AnglePlugValve"
    # --- piping: check valves ---
    CHECK_VALVE = "CheckValve"
    SWING_CHECK_VALVE = "SwingCheckValve"
    GLOBE_CHECK_VALVE = "GlobeCheckValve"
    # --- piping: safety devices ---
    SAFETY_VALVE_OR_FITTING = "SafetyValveOrFitting"
    SPRING_LOADED_GLOBE_SAFETY_VALVE = "SpringLoadedGlobeSafetyValve"
    SPRING_LOADED_ANGLE_GLOBE_SAFETY_VALVE = "SpringLoadedAngleGlobeSafetyValve"
    RUPTURE_DISC = "RuptureDisc"
    BREATHER_VALVE = "BreatherValve"
    FLAME_ARRESTOR = "FlameArrestor"
    # --- piping: inline primary elements (flow meters) ---
    INLINE_PRIMARY_ELEMENT = "InlinePrimaryElement"
    FLOW_MEASURING_ELEMENT = "FlowMeasuringElement"
    VENTURI_TUBE = "VenturiTube"
    FLOW_NOZZLE = "FlowNozzle"
    ELECTROMAGNETIC_FLOW_METER = "ElectromagneticFlowMeter"
    MASS_FLOW_MEASURING_ELEMENT = "MassFlowMeasuringElement"
    VARIABLE_AREA_FLOW_METER = "VariableAreaFlowMeter"
    POSITIVE_DISPLACEMENT_FLOW_METER = "PositiveDisplacementFlowMeter"
    TURBINE_FLOW_METER = "TurbineFlowMeter"
    VOLUME_FLOW_MEASURING_ELEMENT = "VolumeFlowMeasuringElement"
    # --- piping: junction and fittings ---
    PIPE_TEE = "PipeTee"
    PIPE_FITTING = "PipeFitting"
    PIPE_REDUCER = "PipeReducer"
    BLIND_FLANGE = "BlindFlange"
    LINE_BLIND = "LineBlind"
    FLANGE = "Flange"
    FLANGED_CONNECTION = "FlangedConnection"
    PIPE_COUPLING = "PipeCoupling"
    CLAMPED_FLANGE_COUPLING = "ClampedFlangeCoupling"
    COMPENSATOR = "Compensator"
    HOSE = "Hose"
    FUNNEL = "Funnel"
    PENETRATION = "Penetration"
    STRAINER = "Strainer"
    CONICAL_STRAINER = "ConicalStrainer"
    RESTRICTION_ORIFICE = "RestrictionOrifice"
    STEAM_TRAP = "SteamTrap"
    SIGHT_GLASS = "SightGlass"
    ILLUMINATED_SIGHT_GLASS = "IlluminatedSightGlass"
    IN_LINE_MIXER = "InLineMixer"
    SILENCER = "Silencer"
    VENTILATION_DEVICE = "VentilationDevice"
    PIPE_FLANGE_SPADE = "PipeFlangeSpade"
    PIPE_FLANGE_SPACER = "PipeFlangeSpacer"
    # --- piping: spec break ---
    PROPERTY_BREAK = "PropertyBreak"
    # --- instrumentation ---
    PROCESS_SIGNAL_GENERATING_FUNCTION = "ProcessSignalGeneratingFunction"
    PROCESS_INSTRUMENTATION_FUNCTION = "ProcessInstrumentationFunction"
    PROCESS_CONTROL_FUNCTION = "ProcessControlFunction"
    ACTUATING_FUNCTION = "ActuatingFunction"
    ACTUATING_ELECTRICAL_FUNCTION = "ActuatingElectricalFunction"
    # --- off-page connector stubs ---
    FLOW_OUT_PIPE_OFF_PAGE_CONNECTOR = "FlowOutPipeOffPageConnector"
    FLOW_IN_PIPE_OFF_PAGE_CONNECTOR = "FlowInPipeOffPageConnector"
    FLOW_OUT_SIGNAL_OFF_PAGE_CONNECTOR = "FlowOutSignalOffPageConnector"
    FLOW_IN_SIGNAL_OFF_PAGE_CONNECTOR = "FlowInSignalOffPageConnector"
    # --- structure (graph store only) ---
    PROCESS_PLANT = "ProcessPlant"
    PLANT_SECTION = "PlantSection"
    DRAWING_SET = "DrawingSet"
    SHEET = "Sheet"
    #: fallback for a real file's pyDEXPI class the schema does not list (ADR-0016)
    GENERIC_ITEM = "GenericItem"


#: What a piping component is, for counting and for choosing a family of questions: operated valve
#: (a person or an actuator moves it), check valve (lets flow pass one way), safety device,
#: fitting (an inline part that is not a valve), junction (a pipe tee), inline primary element (a
#: flow meter or orifice that senses the fluid) and break (a marker where the line's pipe
#: specification changes; it is not a physical part).
PipingKind = Literal[
    "operated", "check", "safety", "fitting", "junction", "primary_element", "break"
]


class ClassSpec(BaseModel):
    """A node_class's Neo4j label chain, category, tag prefix and piping kind."""

    model_config = ConfigDict(frozen=True)

    labels: tuple[str, ...]
    category: NodeCategory
    tag_prefix: str | None = None
    #: only for `PIPING` classes; separates valves from fittings in every count
    piping_kind: PipingKind | None = None
    #: True if pyDEXPI has no (non-custom) subclass of this class; a parent such as `Pump` is not
    #: a leaf, and a real file's generic item may import as it
    leaf: bool = False


class VocabularyRow(ClassSpec):
    """One row of the generated vocabulary table: a `ClassSpec` with the class name."""

    name: str
