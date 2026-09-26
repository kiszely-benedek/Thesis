"""Records which OPEN100 file holds which drawing.

The PID2Graph dataset provides the 12 OPEN100 drawings under bare names, 0.png
through 11.png, with no accompanying metadata. But resolving a connector's
reference ("continues on sheet 1 of drawing 120") requires knowing which file
drawing 120 lives in. This module keeps that mapping.

The data comes from the drawings' title blocks (the header box printed on each
sheet naming the drawing and its number), read off on 2026-08-25; see
docs/private/10-literature/pid2graph.md for the supporting evidence.

All 12 sheets belong to a single plant: the Energy Impact Center's OPEN 100
nuclear power plant design, same author and date. Four systems span two sheets
each — these give the most reliable cross-sheet references.
"""

from __future__ import annotations

from pydantic import BaseModel

from plantgraph.benchmark.models import SheetRef


class Open100Sheet(BaseModel):
    """One OPEN100 drawing: which file, which system, and its position within the sheet series."""

    file_stem: str
    system: str
    pid: str
    sheet_no: int
    sheet_count: int

    @property
    def ref(self) -> SheetRef:
        """The sheet's reference form, matching how connector labels refer to it."""
        return SheetRef(pid=self.pid, sheet_no=self.sheet_no)


_ROWS: tuple[tuple[str, str, str, int, int], ...] = (
    # file name, system name, P&ID number, sheet number, total sheet count
    ("0", "Main Steam System", "140", 1, 1),
    ("1", "Air Cooled Condenser", "150", 1, 1),
    ("2", "Condensate System", "160", 1, 1),
    ("3", "Feedwater System", "170", 1, 2),
    ("4", "Extraction Steam System", "180", 1, 1),
    ("5", "Reactor Coolant System", "100", 1, 2),
    ("6", "Reactor Coolant System", "100", 2, 2),
    ("7", "Aux Cooling Water System", "210", 1, 2),
    ("8", "Aux Cooling Water System", "210", 2, 2),
    ("9", "Residual Heat Removal System", "120", 2, 2),
    ("10", "Chemical Volume Cooling Water", "110", 1, 1),
    ("11", "Residual Heat Removal System", "120", 1, 2),
)

SHEETS: dict[str, Open100Sheet] = {
    stem: Open100Sheet(file_stem=stem, system=system, pid=pid, sheet_no=sheet_no, sheet_count=count)
    for stem, system, pid, sheet_no, count in _ROWS
}

# Reverse lookup: drawing reference to file. Deliberately incomplete — the
# drawings reference sheet 2 of system 170, but it is not in the dataset.
BY_REF: dict[str, Open100Sheet] = {s.ref.canonical(): s for s in SHEETS.values()}

# Systems the 12 sheets reference but whose drawing we do not have. These become
# the real "dangling" references: questions whose correct answer is "we don't
# know". Not a bug, but a useful test case.
#
# The 2026-08-25 review only identified 190/240/290; the 2026-08-31 manual label
# reading pass (stage 2) found the rest. Number 320 appears under two different
# names on the drawings ("RAD WASTE SYSTEM" and "CHEMICAL ADDITION SYSTEM") —
# either it is two systems in one shared building, or a typo; either way we
# cannot resolve it, so telling the two apart does not matter here.
KNOWN_ABSENT: dict[str, str] = {
    "130": "Service Water System",
    "190": "High Pressure Steam Drains",
    "240": "Turbine System",
    "250": "Turbine Exhaust",
    "270": "Waste Process System",
    "290": "Water Sample System",
    "300": "Make-Up Water",
    "320": "Rad Waste / Chemical Addition System",
}


def resolve(ref: SheetRef) -> Open100Sheet | None:
    """Find which file holds the referenced drawing.

    Returns:
        The sheet, or None if the referenced drawing is not in the dataset —
        the latter is expected and allowed, see KNOWN_ABSENT.
    """
    return BY_REF.get(ref.canonical())
