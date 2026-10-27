"""Which of the generator's classes a planned plant actually uses (design pid-vocabulary 8, 14.6).

The v2 generator draws **77 classes**: every class of the schema's generator vocabulary (94) except
17 that exist only so an imported real drawing can be read (parents such as `Pump`, three piping
leaves nothing places, and the two equipment classes dropped from generation on 2026-10-25). A class
that never appears in a plant is a hole in the corpus: no question can be asked about it. The
report counts each class, names the patterns it came from, and carries its **grounding letter**
from the design (section 6): where the choice of the class comes from.

    A  the user's class list (ADR-0057)       S  shown on a real sheet we read
    L  a legend symbol only                   U  declared by the design, no source
"""

from __future__ import annotations

from collections import Counter, defaultdict

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.symbols import plan_node_classes
from plantgraph.graph.schema import GENERATOR_CLASSES

#: Classes the schema knows only for import: not generated. 8 equipment parents, the two dropped
#: equipment classes, 3 piping leaves with no placement and 4 piping parents (design 6.1, 6.2).
IMPORT_ONLY_CLASSES: frozenset[str] = frozenset(
    {
        "Compressor",
        "Filter",
        "HeatExchanger",
        "Heater",
        "Mixer",
        "Pump",
        "Separator",
        "Vessel",
        "SpiralHeatExchanger",
        "ElectricalSeparator",
        "ClampedFlangeCoupling",
        "Hose",
        "Penetration",
        "InlinePrimaryElement",
        "OperatedValve",
        "PipeFitting",
        "SafetyValveOrFitting",
    }
)

#: The generated classes: the schema's generator vocabulary without the import-only ones.
GENERATED_CLASSES: frozenset[str] = GENERATOR_CLASSES - IMPORT_ONLY_CLASSES

#: Grounding letter of every generated class that is not `A` (design 6.1-6.3); the rest are `A`.
_GROUNDING_EXCEPTIONS: dict[str, str] = {
    **dict.fromkeys(
        ["AirEjector", "Flange", "Compensator", "PipeFlangeSpade", "PropertyBreak"], "S"
    ),
    **dict.fromkeys(["ProcessControlFunction", "ActuatingElectricalFunction"], "S"),
    **dict.fromkeys(
        [
            "EjectorPump",
            "RotaryCompressor",
            "StraightwayValve",
            "TurbineFlowMeter",
            "VolumeFlowMeasuringElement",
            "PipeCoupling",
            "Funnel",
        ],
        "L",
    ),
    **dict.fromkeys(
        [
            "RotaryMixer",
            "AngleBallValve",
            "AngleGlobeValve",
            "AnglePlugValve",
            "PipeFlangeSpacer",
            "FlangedConnection",
            "InLineMixer",
            "IlluminatedSightGlass",
            "Silencer",
            "VentilationDevice",
        ],
        "U",
    ),
}


def grounding_of(node_class: str) -> str:
    """The grounding letter of a generated class: `A`, `S`, `L` or `U`."""
    return _GROUNDING_EXCEPTIONS.get(node_class, "A")


class ClassCoverage(BaseModel):
    """One generated class: how often the plan uses it and from which patterns."""

    model_config = ConfigDict(frozen=True)

    node_class: str
    count: int
    patterns: tuple[str, ...]  # pattern ids (`U1`, `U6`), sorted
    grounding: str


class CoverageReport(BaseModel):
    """Every generated class with its count, rarest first; `absent` names the ones at zero."""

    model_config = ConfigDict(frozen=True)

    rows: tuple[ClassCoverage, ...]

    @property
    def absent(self) -> tuple[str, ...]:
        """The generated classes the plan never uses, sorted."""
        return tuple(sorted(row.node_class for row in self.rows if row.count == 0))


def coverage_report(plan: PlantPlanV2) -> CoverageReport:
    """Count every generated class in `plan`.

    Raises:
        ValueError: if the plan uses a class outside the generated 77 (invariant S24).
    """
    counts: Counter[str] = Counter()
    patterns: dict[str, set[str]] = defaultdict(set)
    for unit in plan.units:
        for node_class in plan_node_classes(unit.instance.plan).values():
            counts[node_class] += 1
            patterns[node_class].add(unit.instance.pattern)
    outside = sorted(set(counts) - GENERATED_CLASSES)
    if outside:
        raise ValueError(
            f"expected only the {len(GENERATED_CLASSES)} generated classes, found {outside}"
        )
    rows = [
        ClassCoverage(
            node_class=node_class,
            count=counts[node_class],
            patterns=tuple(sorted(patterns[node_class])),
            grounding=grounding_of(node_class),
        )
        for node_class in GENERATED_CLASSES
    ]
    rows.sort(key=lambda row: (row.count, row.node_class))
    return CoverageReport(rows=tuple(rows))


def render_coverage(report: CoverageReport, rarest: int = 8) -> str:
    """A summary line, the absent classes by name, and the `rarest` classes with their patterns."""
    present = sum(row.count > 0 for row in report.rows)
    lines = [f"\nclass coverage: {present} / {len(report.rows)} generated classes present"]
    lines.append(f"  absent: {', '.join(report.absent) or 'none'}")
    lines.append("  rarest present:")
    shown = [row for row in report.rows if row.count > 0][:rarest]
    lines += [
        f"    {row.node_class:<32}{row.count:>6}  [{row.grounding}]  {', '.join(row.patterns)}"
        for row in shown
    ]
    return "\n".join(lines)
