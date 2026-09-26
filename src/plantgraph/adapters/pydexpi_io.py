"""Persistence for a pyDEXPI `DexpiModel`: JSON and Proteus XML (`plant-generator.md` §3.7).

A separate module from `pydexpi_adapter.py` (which would just fit under the
400-line limit, but this isn't its responsibility either): this module transforms
nothing, it only moves data between disk and `DexpiModel`. JSON is the only
**lossless** form; Proteus (an XML interchange format for P&ID data) export in
pyDEXPI 1.2.0 writes equipment only — see `save_proteus_equipment_only`.
"""

from __future__ import annotations

from pathlib import Path

from pydexpi.dexpi_classes.pydantic_classes import DexpiModel
from pydexpi.loaders.json_serializer import JsonSerializer
from pydexpi.loaders.proteus_serializer import ProteusSerializer


def save_json(model: DexpiModel, directory: Path, filename: str) -> None:
    """Save the model as pyDEXPI JSON — the publishable, lossless form (§3.7)."""
    JsonSerializer().save(model, directory, filename)


def load_json(directory: Path, filename: str) -> DexpiModel:
    """Load back a model saved with `save_json`."""
    loaded = JsonSerializer().load(directory, filename)
    return _require_dexpi_model(loaded)


def save_proteus_equipment_only(model: DexpiModel, directory: Path, filename: str) -> None:
    """Proteus XML export — **equipment and `MetaData` only** in pyDEXPI 1.2.0 (§3.7).

    `ProteusSerializer`/`PlantModelExporter` only iterates `taggedPlantItems`
    (verified: piping and instrumentation are left out) — the filename therefore
    states explicitly what is MISSING from it, not just what it contains.
    """
    # override_export_info=True would open pyproject.toml from the current working
    # directory (proteus_exporter/exporter_modules.py) — unsafe as a default for
    # the generator, which may run from anywhere
    serializer = ProteusSerializer(override_export_info=False)
    serializer.save(model, directory, filename)


def load_proteus(directory: Path, filename: str) -> DexpiModel:
    """Load any Proteus XML file, including an external full drawing (`kg-construction.md` §3 T1).

    The pyDEXPI **parser** reads piping and instrumentation, not only equipment;
    this entry point is therefore the right one for a real file (e.g. EX01),
    which `pydexpi_proteus_import`'s importer then processes further.
    """
    return ProteusSerializer().load(directory, filename)


def load_proteus_equipment_only(directory: Path, filename: str) -> DexpiModel:
    """Load a file written by `save_proteus_equipment_only`, containing equipment only.

    The same call as `load_proteus` — the distinct name only signals that this
    is meant for the generator's stripped-down export, where the extra
    (piping/instrumentation) data is guaranteed to come back as an empty list.
    """
    return load_proteus(directory, filename)


def _require_dexpi_model(loaded: object) -> DexpiModel:
    """`JsonSerializer.load`'s declared return type is `DexpiBaseModel`.

    Here we verify that a `DexpiModel` really came back.
    """
    if not isinstance(loaded, DexpiModel):
        raise TypeError(
            f"expected a DexpiModel from JsonSerializer.load, got {type(loaded).__name__}"
        )
    return loaded
