"""The summary numbers of Toghraei (2019) chapter 20, counted by hand on its 35 example sheets.

Source: `docs/private/10-literature/toghraei-2019-ch20-sheet-counts.md` (the "Summary" section).
These are textbook illustrations of single items or systems, not a sample of a plant's sheets, so
the comparison shows plausibility only. The three auxiliary sheets (HVAC, fire-and-gas controls,
instrument details) are in the sheet total but have no counterpart in the generator.
"""

from __future__ import annotations

NOTE_PATH = "docs/private/10-literature/toghraei-2019-ch20-sheet-counts.md"

SHEETS = 35
SHEETS_WITHOUT_EQUIPMENT = 9  # 5 network, 2 interarea, 2 auxiliary
NETWORK_AND_INTERAREA_SHEETS = 7

# process sheets (25)
PROCESS_SHEETS = 25
PROCESS_EQUIPMENT_MEAN = 1.72
PROCESS_EQUIPMENT_MEDIAN = 1.0
PROCESS_EQUIPMENT_MAX = 7
PROCESS_EQUIPMENT_DISTRIBUTION = {1: 15, 2: 7, 3: 1, 4: 1, 7: 1}  # items -> sheets
PROCESS_CONNECTORS_MEAN = 3.88
PROCESS_CONNECTORS_MEDIAN = 3.0
PROCESS_CONNECTORS_MAX = 12
PROCESS_CONNECTORS_BY_CODE = {"P": 61, "N": 19, "U": 12, "S": 5}  # 97 in all
PROCESS_SHEETS_WITH_N = 15

# network sheets (5): connectors per sheet 8, 10, 6, 8, 10
NETWORK_SHEETS = 5
NETWORK_CONNECTORS_MEAN = 8.4
NETWORK_CONNECTORS_MEDIAN = 8.0  # the median of the five listed values
NETWORK_CONNECTORS_MAX = 10

# interarea sheets (2): 18 and 13 connectors
INTERAREA_SHEETS = 2
INTERAREA_CONNECTORS_MEAN = 15.5
INTERAREA_CONNECTORS_MAX = 18
