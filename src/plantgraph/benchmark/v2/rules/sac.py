"""API RP 14C Safety Analysis Checklist (SAC) items the generator checks (design 6.4, T10a).

The SAC is the standard's table, per component kind, of the safety devices that component should
carry: a pressure switch high (PSH), a level switch low (LSL), a pressure safety valve (PSV), and
so on. Each item may be left out for one of API's numbered **omission conditions** ("a.4: a
downstream PSH also protects this vessel"). API prints no code string, so a code here is
`<kind>:<table> <item>.<number>`, our format, in three kinds (design 17.13 R7):

- `derived`: the condition is read from the drawn structure by the check;
- `declared`: it follows from a convention stated once in `hidden_state.py`;
- `scope`: the component is outside the table's scope (a page says so).

Pages are API's printed page (PDF page minus 8). Items that are not here are DEFERRED rows of the
registry (`catalogue_deferred.py`), each with its reason. This module is data only.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SacItem(BaseModel):
    """One checked SAC item: the device, where it sits, its page and its allowed omission codes."""

    model_config = ConfigDict(frozen=True)

    table: str  # `A-4.2`
    letter: str  # API's item letter
    device: str  # `PSH`
    location: str  # where API puts it, paraphrased
    page: int  # printed page of the table
    codes: tuple[str, ...] = ()  # the omission codes this generator can report for the item

    @property
    def item_id(self) -> str:
        """`A-4.2 a`: the key the checks and the report use."""
        return f"{self.table} {self.letter}"


SAC_ITEMS: tuple[SacItem, ...] = (
    # A.4 pressure vessel (table p.29; locations A.4.3.1 p.28)
    SacItem(
        table="A-4.2",
        letter="a",
        device="PSH",
        location="gas section",
        page=29,
        codes=("derived:A-4.2 a.4",),
    ),
    SacItem(
        table="A-4.2",
        letter="c",
        device="PSV",
        location="vessel or its outlet",
        page=29,
        codes=("scope:non_hydrocarbon", "deferred:valve_band"),
    ),
    SacItem(
        table="A-4.2",
        letter="d",
        device="LSH",
        location="liquid section",
        page=29,
        codes=("declared:no_separated_phases",),
    ),
    SacItem(
        table="A-4.2",
        letter="e",
        device="LSL",
        location="liquid outlet",
        page=29,
        codes=("derived:A-4.2 e.2",),
    ),
    SacItem(
        table="A-4.2",
        letter="g",
        device="TSH",
        location="heated vessel",
        page=29,
        codes=("declared:A-4.2 g.3 steam_limited",),
    ),
    # A.5 atmospheric vessel (table p.31; vent and PSV on top, A.5.3.1 p.32)
    SacItem(table="A-5.2", letter="a", device="vent", location="roof", page=31),
    SacItem(
        table="A-5.2",
        letter="b",
        device="PSV",
        location="roof or vent line",
        page=31,
        codes=("derived:A-5.2 b.2",),
    ),
    SacItem(table="A-5.2", letter="c", device="LSH", location="liquid section", page=31),
    SacItem(
        table="A-5.2",
        letter="d",
        device="LSL",
        location="liquid section",
        page=31,
        codes=("derived:A-5.2 d.3",),
    ),
    # A.6 fired component (table p.38; TSH and fuel PSH locations A.6.3 p.33)
    SacItem(table="A-6.2", letter="a", device="TSH", location="heater outlet line", page=38),
    SacItem(
        table="A-6.2",
        letter="d",
        device="PSL",
        location="air supply",
        page=38,
        codes=("declared:natural_draft",),
    ),
    SacItem(table="A-6.2", letter="e", device="PSH", location="fuel line", page=38),
    SacItem(
        table="A-6.2",
        letter="f",
        device="PSL",
        location="fuel line",
        page=38,
        codes=("declared:natural_draft",),
    ),
    SacItem(table="A-6.2", letter="g", device="BSL", location="burner", page=38),
    SacItem(
        table="A-6.2",
        letter="h",
        device="FSL",
        location="heated medium",
        page=38,
        codes=("derived:A-6.2 h.2",),
    ),
    SacItem(
        table="A-6.2",
        letter="i",
        device="motor interlock",
        location="draft fan",
        page=38,
        codes=("declared:natural_draft",),
    ),
    SacItem(
        table="A-6.2",
        letter="l",
        device="PSV",
        location="medium circulating tube",
        page=38,
        codes=("derived:A-6.2 l.3", "deferred:valve_band"),
    ),
    # A.7 pump (table p.44)
    SacItem(
        table="A-7.2",
        letter="f",
        device="PSV",
        location="discharge",
        page=44,
        codes=("declared:discharge_rated_for_shutoff",),
    ),
    SacItem(
        table="A-7.2",
        letter="g",
        device="FSV",
        location="discharge",
        page=44,
        codes=("conflict:TOG192-RECIP-NO-CHECK",),
    ),
    # A.8 compressor (table p.47; locations A.8.3.1 p.45)
    SacItem(table="A-8.2", letter="a", device="PSH", location="suction", page=47),
    SacItem(table="A-8.2", letter="b", device="PSH", location="discharge", page=47),
    SacItem(table="A-8.2", letter="c", device="PSL", location="suction", page=47),
    SacItem(table="A-8.2", letter="d", device="PSL", location="discharge", page=47),
    SacItem(
        table="A-8.2",
        letter="e",
        device="PSV",
        location="suction",
        page=47,
        codes=("deferred:valve_band",),
    ),
    SacItem(table="A-8.2", letter="f", device="PSV", location="discharge", page=47),
    SacItem(table="A-8.2", letter="g", device="FSV", location="final discharge", page=47),
    SacItem(table="A-8.2", letter="h", device="TSH", location="discharge", page=47),
    # A.10 shell-tube exchanger, per section (table p.53)
    SacItem(
        table="A-10.2",
        letter="a",
        device="PSH",
        location="utility section",
        page=53,
        codes=(
            "declared:utility_designed_for_header",
            "derived:A-10.2 a.4",
            "deferred:process_section_psh",
        ),
    ),
)

#: every code a SAC check may report: the items' own, and the scope codes of whole components
SAC_EXCEPTION_CODES: tuple[str, ...] = tuple(
    sorted({code for item in SAC_ITEMS for code in item.codes} | {"scope:vacuum_service"})
)

#: SAC tables left out of scope for a component (a page says so); see `catalogue_deferred.py`
SCOPE_NOTES: dict[str, str] = {
    "scope:non_hydrocarbon": "condensate pots (A.4.1 p.26); non-flammable farm tanks (A.5.1 p.30)",
    "scope:vacuum_service": "liquid-ring vacuum pumps are not A.8 compressors (A.8.1 p.45)",
}


def sac_item(table: str, letter: str) -> SacItem:
    """The checked item `table letter`.

    Raises:
        KeyError: the item is not in `SAC_ITEMS` (it is a deferred row or not an item).
    """
    for item in SAC_ITEMS:
        if item.table == table and item.letter == letter:
            return item
    raise KeyError(f"expected a checked SAC item such as 'A-4.2 a', got {table} {letter!r}")
