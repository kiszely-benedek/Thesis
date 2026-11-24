"""Reading the valve positions back out of a DEXPI model, and the file a B corpus keeps them in.

A valve's **normal operating position** (NO, NC, ...) is a custom attribute of the valve in the
DEXPI file (`adapters/pydexpi_valve_attributes.py` writes it). In the synthetic world, reading it
back plays the digitizer that reads the position text printed beside the valve symbol (design
`v2t-b` §10 R4). The gold side reads the same positions from the generator plan instead, and the
ingest gate G0-B (`store_b.py`) demands that the two paths agree.

The positions of one plant travel in `operating_positions.json`, next to the corpus's
`ingest.json`: a sorted-key JSON object `{valve node id: code}`. Its sha256 is what a run records.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydexpi.dexpi_classes.pydantic_classes import CustomStringAttribute, DexpiModel

from plantgraph.adapters.pydexpi_valve_attributes import (
    OPERATING_POSITION_ATTRIBUTE,
    _items_by_id,  # the inverse of `annotate_valves` walks the same components; a copy could drift
)

POSITIONS_FILE_NAME = "operating_positions.json"


def read_operating_positions(model: DexpiModel) -> dict[str, str]:
    """Valve node id -> position code, from the `OperatingPosition` attribute of each component.

    Raises:
        ValueError: a component carries the attribute twice, or not as a string.
    """
    found: dict[str, str] = {}
    for node_id, component in _items_by_id(model).items():
        codes = [
            attribute
            for attribute in component.customAttributes
            if attribute.attributeName == OPERATING_POSITION_ATTRIBUTE
        ]
        if not codes:
            continue
        if len(codes) > 1 or not isinstance(codes[0], CustomStringAttribute):
            raise ValueError(
                f"expected one string OperatingPosition attribute on {node_id!r}, found {codes!r}"
            )
        found[node_id] = str(codes[0].value)
    return found


def positions_file_bytes(positions: dict[str, str]) -> bytes:
    """The bytes of `operating_positions.json`: sorted keys, two-space indent, trailing newline."""
    return (json.dumps(positions, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_positions_file(path: Path, positions: dict[str, str]) -> str:
    """Write the positions file and return its sha256 (hex)."""
    data = positions_file_bytes(positions)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def read_positions_file(path: Path) -> tuple[dict[str, str], str]:
    """The positions in the file and the sha256 of its bytes.

    Raises:
        FileNotFoundError: the corpus has no positions file (it was not ingested as a B corpus).
        ValueError: the file is not a JSON object of strings.
    """
    if not path.is_file():
        raise FileNotFoundError(f"expected a positions file at {path}; found none")
    data = path.read_bytes()
    loaded = json.loads(data)
    if not isinstance(loaded, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in loaded.items()
    ):
        raise ValueError(f"expected {path} to hold a JSON object of strings, found {loaded!r:.80}")
    return loaded, hashlib.sha256(data).hexdigest()
