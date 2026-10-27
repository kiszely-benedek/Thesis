"""The acceptance bands of the composition report, one table (design pid-vocabulary 14.2, 14.3).

A **band** is the range a statistic of a generated plant must fall in. OPEN100 is one plant, so the
bands are declared design criteria built on it, not a calibration claim (design realism 12.1). A
band marked `reported` has no pass mark: the number is printed with the band beside it and the
verdict is `reported` (the 40-134 symbol share, decided 2026-10-26; signal cuts; the 0.25 deltas).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class Verdict(str, Enum):
    """How a value stands against its band."""

    PASS = "pass"
    FAIL = "fail"
    REPORTED = "reported"


class Band(BaseModel):
    """An inclusive range `[low, high]`; a missing end is open. `reported` bands never fail."""

    model_config = ConfigDict(frozen=True)

    label: str  # how the band is printed, e.g. `56-109`
    low: float | None = None
    high: float | None = None
    reported: bool = False

    def verdict(self, value: float) -> Verdict:
        """`reported` for a reported band; else `pass` inside the range and `fail` outside."""
        if self.reported:
            return Verdict.REPORTED
        below = self.low is not None and value < self.low
        above = self.high is not None and value > self.high
        return Verdict.FAIL if below or above else Verdict.PASS


def _range(low: float, high: float, unit: str = "") -> Band:
    return Band(label=f"{low:g}-{high:g}{unit}", low=low, high=high)


def _at_most(high: float, unit: str = "") -> Band:
    return Band(label=f"<= {high:g}{unit}", high=high)


def _at_least(low: float, unit: str = "") -> Band:
    return Band(label=f">= {low:g}{unit}", low=low)


def _exactly(value: float) -> Band:
    return Band(label=f"= {value:g}", low=value, high=value)


def _reported(label: str) -> Band:
    return Band(label=label, reported=True)


#: Plan-level bands (symbols per sheet and the like), by the quantity's name in the report.
PLAN_BANDS: dict[str, Band] = {
    "symbols per sheet, mean": _range(56, 109),
    "sheets with 40-134 symbols (share)": _reported("reported (target >= 0.95 not enforced)"),
    "valves per sheet, mean": _range(15, 28),
    "instruments per sheet, mean": _range(20, 38),
    "instruments : valves": _range(1.0, 1.8),
    "off-page stubs per sheet, mean": _range(5, 11),
    "off-page stubs per sheet, max": _at_most(21),
    "equipment per sheet, min": _at_least(1),
    "equipment per sheet, max": _at_most(16),
    "sheets with at most 10 equipment (share)": _at_least(0.9),
    "equipment in A/B(/C) sets (share)": _range(0.25, 0.45),
    "units drawn on 2 or more sheets (share)": _range(0.25, 0.65),
    "signal cuts per sheet, mean": _reported("reported, no band"),
}

#: Corpus-level bands: the degree-1 share and the exact duplication-0 reconciliation.
CORPUS_BANDS: dict[str, Band] = {
    "instruments with sheet-graph degree 1 (share)": _at_least(0.55),
    "sheets that show one unit (share)": _exactly(1.0),
    "dup 0: sheets with corpus symbols = plan symbols (share)": _exactly(1.0),
    "dup 0: sheets with pipe connectors = plan crossings (share)": _exactly(1.0),
    "dup 0: sheets with signal connectors = plan signal cuts (share)": _exactly(1.0),
    "preset duplication: reference copies added per sheet": _reported("reported, no band"),
    "preset duplication: crossings absorbed per sheet": _reported("reported, no band"),
}
