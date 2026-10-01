"""Data model for the multi-sheet benchmark's answer key.

Terms, because the code is about an engineering domain the reader may not know:

- **P&ID**: a piping and instrumentation diagram — the technical drawing of a
  plant's pipes and instruments. A full plant spans hundreds of such sheets.
- **sheet**: a single page of the drawing series. A pipe segment rarely fits on
  one sheet, so it continues onto the next.
- **off-page connector**: when a pipe runs off the edge of a sheet, a labelled
  arrow is placed on both affected sheets, stating where it continues ("continues
  on sheet 1 of drawing 120, in cell D-1"). This is the cross-reference between sheets.
- **answer key (ground truth)**: the known-correct answers that the system's
  output is measured against.

Two sources produce the answer key: the synthetic splitter, which cuts a plant
graph into sheets, and the OPEN100 annotation, which recovers the connections
from real drawings. Both emit the same SplitManifest, so downstream code cannot
tell the two sources apart — and must not need to. See:
docs/private/40-design/splitter.md.

This module holds the answer key's rows and the OPEN100-specific findings,
together with the synthetic splitter's stub model (`OffPageConnector`), because
a `SplitManifest` list carries it. What is only the splitter's own configuration,
and doesn't interleave with the manifest — `SplitConfig` and its enums — lives in
`split_models.py`; the split exists because of the 400-line file limit, not a
conceptual difference (`plant-generator.md` §5, "Things to watch").
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Side(str, Enum):
    """Which edge of the sheet the connector symbol sits on: left or right.

    Records only where it is on the image — not whether material flows in or out
    through it. That is what Direction is for.
    """

    LEFT = "left"
    RIGHT = "right"


class Direction(str, Enum):
    """Whether material flows into or out of the sheet through this connector.

    This is stated by the connector's label, not its position. Drafters usually
    place incoming connectors on the left and outgoing ones on the right, but
    that is only convention — a different drafter may do it differently, so
    code must not rely on it.
    """

    INCOMING = "incoming"
    OUTGOING = "outgoing"


class BoundingBox(BaseModel):
    """A rectangle drawn around a symbol, in the image's pixel coordinates.

    This is how the annotation marks an element's location on the drawing:
    top-left and bottom-right corner.
    """

    xmin: float
    ymin: float
    xmax: float
    ymax: float

    @model_validator(mode="after")
    def _check_ordering(self) -> BoundingBox:
        if self.xmax <= self.xmin or self.ymax <= self.ymin:
            raise ValueError(f"degenerate box: expected xmin<xmax and ymin<ymax, got {self!r}")
        return self

    @property
    def width(self) -> float:
        """The box's width in pixels."""
        return self.xmax - self.xmin

    @property
    def height(self) -> float:
        """The box's height in pixels."""
        return self.ymax - self.ymin

    @property
    def centre_x(self) -> float:
        """The box's horizontal centre — this decides which sheet edge it belongs to."""
        return (self.xmin + self.xmax) / 2

    def expanded(self, x_factor: float, y_margin: float) -> BoundingBox:
        """Expand the box: sideways by a multiple of its own width, up-down in pixels.

        Needed because the connector's label sits inside the box, but the pipe's
        identifier (the "line number", e.g. SIZE-RCS-100007-SPEC-HC-X) is written
        beside it, on the pipe itself. Reading that too requires reaching sideways.
        """
        pad = self.width * x_factor
        return BoundingBox(
            xmin=self.xmin - pad,
            ymin=self.ymin - y_margin,
            xmax=self.xmax + pad,
            ymax=self.ymax + y_margin,
        )

    def clipped_to(self, width: int, height: int) -> BoundingBox:
        """Clip the box back inside the image's bounds, so the crop doesn't run off the edge."""
        return BoundingBox(
            xmin=max(0.0, self.xmin),
            ymin=max(0.0, self.ymin),
            xmax=min(float(width), self.xmax),
            ymax=min(float(height), self.ymax),
        )

    def as_pixels(self) -> tuple[int, int, int, int]:
        """Integer coordinates (left, top, right, bottom) — the form PIL's crop method wants."""
        return (round(self.xmin), round(self.ymin), round(self.xmax), round(self.ymax))


class SheetRef(BaseModel):
    """A reference to a drawing sheet: which P&ID, and which sheet number within it.

    The same sheet is referenced in several ways across the drawings — OPEN100
    uses 'PID 120-1', 'PID-120-01', and 'RCS-PID-100-2' for the same target. So
    references are normalized to one form before comparing them; relying on
    literal text equality here would be wrong.
    """

    pid: str
    sheet_no: int

    def canonical(self) -> str:
        """A normalized spelling, e.g. PID-120-1 — only this form may be compared."""
        return f"PID-{self.pid}-{self.sheet_no}"


class ConnectorObservation(BaseModel):
    """A found connector symbol on a sheet, with everything we know about it.

    Filled in over three steps:
      1. geometry — where it is on the image (comes from the annotation file),
      2. label — what is written on it (after the crop has been read),
      3. verified_by_human — whether someone checked it by hand.

    An optional field being empty means the value isn't known yet. It is never
    silently filled with a default: "don't know" and "zero" are two different
    things here.
    """

    sheet_file: str
    node_id: str
    bbox: BoundingBox
    side: Side

    raw_text: str | None = None
    direction: Direction | None = None
    target: SheetRef | None = None
    grid_cell: str | None = None
    service: str | None = None
    line_number: str | None = None

    verified_by_human: bool = False

    @property
    def key(self) -> str:
        """A stable identifier, unique across the whole drawing series."""
        return f"{self.sheet_file}:{self.node_id}"


class MatchRule(str, Enum):
    """Which rule found the pair — the less certain rules stay auditable this way.

    The 1-4 ranking comes from docs/private/40-design/open100-annotation.md
    step 3, extended with the resolver's own, strongest rule
    (`kg-construction.md` §5.2): the rank number is itself the confidence level,
    1 being the strongest.
    """

    CONNECTOR_NUMBER = (
        "connector_number"  # 1. the partner's own number matches mutually from both sides
    )
    LINE_NUMBER = "line_number"  # 2. the identifier matches on both sheets — a strong signal
    GRID_MUTUAL = "grid_mutual"  # 3. the target cell points back the same way from both directions
    SERVICE_DIRECTION = (
        "service_direction"  # 4. only the system and direction match — needs manual review
    )
    SYNTHETIC = "synthetic"  # cut by the synthetic generator — no need to guess, we know


class ConnectorPair(BaseModel):
    """Two connectors found to be the two ends of the same pipe.

    This is one row of the answer key: exactly these pairs are what the system
    must find, and this is what its precision is measured against.

    original_edge is only filled in for the synthetic generator, because there
    we cut the graph edge ourselves, so we know what it was. When annotating a
    real drawing, the connection can be recovered, but the original edge cannot
    — so it stays None.

    match_rule states how much to trust the pair. A line_number match can be
    wrong because of a typo'd label; a service_direction match could be mere
    coincidence. Both go into the answer key, but with different weight.
    """

    from_key: str
    to_key: str
    line_number: str | None = None
    original_edge: tuple[str, str] | None = None
    match_rule: MatchRule = MatchRule.SYNTHETIC
    note: str | None = None


class ConnectorKind(str, Enum):
    """Which kind of edge an off-page connector cuts: a pipe segment or a signal line.

    This decides the stub node's pyDEXPI class (`plant-generator.md` §4.2,
    finding 2a): a cut `send_to` edge becomes a `PipeOffPageConnector`, every
    other relation (`send_signal_to`, `control`, `measured_by`) becomes a
    `SignalOffPageConnector`.
    """

    PIPE = "pipe"
    SIGNAL = "signal"


class OffPageConnector(BaseModel):
    """An off-page connector stub the synthetic splitter inserts in place of a cut edge.

    When the splitter cuts an edge between two sheets, a stub node like this is
    added to both sheets' graphs — this is the synthetic counterpart of what
    ConnectorObservation describes on OPEN100, read off a real sheet.

    key's shape is deliberately **the same** as ConnectorObservation.key's
    (f"{sheet}:{node_id}"): this is the seam that lets ConnectorPair.from_key and
    to_key stay indifferent to whether the synthetic splitter or the OPEN100
    annotation produced the connector — both end up in the same SplitManifest,
    and downstream code never tells the two apart.
    """

    tag: str
    sheet_id: str
    direction: Direction
    partner_sheet_id: str
    partner_tag: str
    attached_node_id: str
    kind: ConnectorKind = ConnectorKind.PIPE
    line_number: str | None = None
    fluid_code: str | None = None
    loop_tag: str | None = None  # signal cuts only: the control loop's number (ADR-0027)

    @property
    def key(self) -> str:
        """The same shape as ConnectorObservation.key — see the class docstring."""
        return f"{self.sheet_id}:{self.attached_node_id}"


class DanglingReference(BaseModel):
    """A connector referencing a sheet we do not have.

    Not a bug, but reality: a drawing series is almost always only a subset of
    the plant. These become the deliberately unanswerable questions, where the
    right answer is "this information is not available" — not the system making
    something up.
    """

    from_key: str
    target: SheetRef
    reason: str = "target sheet not present in corpus"


class IdentityGroup(BaseModel):
    """One physical piece of equipment that was drawn on more than one sheet.

    The same pump might appear on its own system's sheet and on the cooling-water
    sheet too: two drawing symbols, one real pump. The two must be merged.

    This is the other kind of cross-sheet link, and it is the more dangerous one.
    A missed off-page connector leaves a visibly torn-apart graph, which stands
    out. A missed identity, though, leaves the graph looking intact — it just has
    two separate pumps instead of one — so a question like "what feeds this
    pump?" gets a confident but incomplete answer. The silent half-truth is worse
    than the visible error.

    home is the detailed occurrence (full data), references are the shorter
    repeats on the other sheets.

    A real example from OPEN100, verified 2026-08-25: the pump tagged
    RCS-PU-102A appears on sheet 5 as part of the flow diagram, and again on
    sheet 6, where the "DETAIL A" close-up shows the same machine. Two drawing
    symbols, one pump.

    Spelling can vary too: on that same sheet 5, the symbol's label reads
    RCS-PU-102A, but the equipment list at the bottom of the sheet gives
    RC-P102A for the same machine. This particular example, though, is a
    **within-sheet** discrepancy; a tag being spelled differently across
    sheets has not yet been confirmed in this dataset. The tag_variants field
    is ready for it, should it turn up.
    """

    tag: str
    home: str
    references: list[str] = Field(default_factory=list)
    tag_variants: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_not_alone(self) -> IdentityGroup:
        if not self.references:
            raise ValueError(
                f"identity group for {self.tag!r} has no reference occurrences; "
                "a group needs at least two occurrences to be worth recording"
            )
        return self


class UnresolvedConnector(BaseModel):
    """A connector known not to be dangling — but whose partner still wasn't found.

    This is the third case alongside "paired" and "dangling", and it will occur
    on real drawings: the named target sheet is in the corpus, but no matching
    connector can be found on it. There can be several reasons — a reading
    error, the drafter forgot to draw its partner, or the partner isn't marked
    with the "inlet/outlet" label in the annotation. None of these may silently
    disappear: hence its own category, instead of being forced into a pair or
    a wrong "dangling" entry.
    """

    from_key: str
    reason: str


class SplitManifest(BaseModel):
    """A multi-sheet drawing series' complete answer key, in a single file."""

    source: str
    sheet_files: list[str]
    connectors: list[ConnectorObservation] = Field(default_factory=list)
    off_page_connectors: list[OffPageConnector] = Field(default_factory=list)
    connector_pairs: list[ConnectorPair] = Field(default_factory=list)
    dangling: list[DanglingReference] = Field(default_factory=list)
    unresolved: list[UnresolvedConnector] = Field(default_factory=list)
    identity_groups: list[IdentityGroup] = Field(default_factory=list)

    strategy: str | None = None
    seed: int | None = None
    source_graph_hash: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def accounted_for(self) -> bool:
        """True if every connector's fate is known: paired, dangling, or openly unresolved.

        A connector must not disappear without a trace. "Known fate" does not
        mean it was solved — the unresolved list exists precisely so a real,
        not-yet-manually-checked case can be admitted instead of either being
        dropped or forced into a wrong pair.

        connectors (OPEN100) and off_page_connectors (synthetic splitter) are
        filled at the same time: only one of the two is non-empty per source.
        The promise holds for both at once, so a connector can't silently vanish
        from either source.
        """
        placed = {p.from_key for p in self.connector_pairs}
        placed |= {p.to_key for p in self.connector_pairs}
        placed |= {d.from_key for d in self.dangling}
        placed |= {u.from_key for u in self.unresolved}
        expected = {c.key for c in self.connectors} | {c.key for c in self.off_page_connectors}
        return placed == expected
