"""Configuration used only by the synthetic splitter.

Holds what only the synthetic splitter needs — not required by the OPEN100
annotation pipeline, which recovers connections from real drawings instead. The
answer-key models shared by both sources (`ConnectorPair`, `OffPageConnector`,
`IdentityGroup`, `SplitManifest`, ...) stay in `models.py`; this module was split
out only because together they would have exceeded the 400-line file limit, not
for a conceptual reason (`plant-generator.md` §5, "Things to watch").
`OffPageConnector` deliberately did **not** move here: a list of them lives inside
`SplitManifest` (models.py), and this module would then need to import
`Direction` from models.py — the two would import each other in a circle.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from plantgraph.graph import schema


class NumberingScheme(str, Enum):
    """The labelling convention for off-page connectors — deliberately variable, not fixed.

    Per splitter.md section 3, sheet numbering and labelling are generator
    parameters: if a downstream component only works for one such convention,
    the benchmark should expose that, not hide it.
    """

    SEQUENTIAL = "sequential"  # e.g. "SHEET-3-OPC-07"
    PID_STYLE = "pid_style"  # e.g. "PID-120-1" — the form observed on OPEN100


class ConnectorLabelDetail(str, Enum):
    """How much label text a connector stub carries — the harder EXP-0004 condition too.

    Under FULL, the stub also carries its partner's own label
    (`referenced_connector_number`). DRAWING_ONLY leaves that out: the resolver
    must then tell apart two connectors on the same sheet pair using the
    `line_number` and `fluid_code` instead (`plant-generator.md` §5, finding 2b).
    """

    FULL = "full"
    DRAWING_ONLY = "drawing_only"


class SplitConfig(BaseModel):
    """Every setting for the synthetic splitter — strategy to labelling convention.

    Every field here is deliberately a parameter, not a hardcoded constant
    (splitter.md section 3): the research question is precisely how these
    conventions affect retrieval accuracy.
    """

    strategy: str = "flow_greedy"
    sheet_equipment_budget: int = Field(default=10, ge=1)
    seed: int = 0
    duplication_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    equipment_classes: set[str] = Field(default_factory=lambda: set(schema.EQUIPMENT_CLASSES))
    numbering_scheme: NumberingScheme = NumberingScheme.SEQUENTIAL
    use_grid_reference: bool = False
    exact_match_tags: bool = True
    connector_label_detail: ConnectorLabelDetail = ConnectorLabelDetail.FULL
