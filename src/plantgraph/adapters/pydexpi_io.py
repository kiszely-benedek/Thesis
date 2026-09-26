"""Perzisztencia egy pyDEXPI `DexpiModel`-hez: JSON és Proteus XML (`plant-generator.md` §3.7).

Külön modul, nem `pydexpi_adapter.py` (ami épp a 400 soros korlát alá esne, de
felelősség szerint sem oda való): ez a modul semmit sem alakít át, csak lemez
és `DexpiModel` között visz. A JSON az egyetlen **veszteségmentes** alak; a
Proteus export pyDEXPI 1.2.0-ban csak berendezést ír — lásd `save_proteus_equipment_only`.
"""

from __future__ import annotations

from pathlib import Path

from pydexpi.dexpi_classes.pydantic_classes import DexpiModel
from pydexpi.loaders.json_serializer import JsonSerializer
from pydexpi.loaders.proteus_serializer import ProteusSerializer


def save_json(model: DexpiModel, directory: Path, filename: str) -> None:
    """Elmenti a modellt pyDEXPI JSON-ként — ez a publikálható, veszteségmentes alak (§3.7)."""
    JsonSerializer().save(model, directory, filename)


def load_json(directory: Path, filename: str) -> DexpiModel:
    """Visszatölt egy `save_json`-nal mentett modellt."""
    loaded = JsonSerializer().load(directory, filename)
    return _require_dexpi_model(loaded)


def save_proteus_equipment_only(model: DexpiModel, directory: Path, filename: str) -> None:
    """Proteus XML export — **csak berendezés és `MetaData`** pyDEXPI 1.2.0-ban (§3.7).

    `ProteusSerializer`/`PlantModelExporter` csak a `taggedPlantItems`-en
    iterál (mérve: a csővezeték és a műszerezés kimarad) — a fájlnév ezért
    jelzi explicit, mi HIÁNYZIK belőle, nem csak mit tartalmaz.
    """
    # override_export_info=True a jelenlegi munkakönyvtárból nyitná meg a
    # pyproject.tomlt (proteus_exporter/exporter_modules.py) — ez a
    # generátornak, ami bárhonnan futhat, nem biztonságos alapértelmezés
    serializer = ProteusSerializer(override_export_info=False)
    serializer.save(model, directory, filename)


def load_proteus(directory: Path, filename: str) -> DexpiModel:
    """Betölt egy tetszőleges Proteus XML-t — külső, teljes rajzot is (`kg-construction.md` §3 T1).

    A pyDEXPI **parser** csővezetéket és műszerezést is olvas, nemcsak
    berendezést; ez a belépési pont ezért felel meg egy valódi fájlnak
    (pl. EX01), amit a `pydexpi_proteus_import` importere dolgoz fel tovább.
    """
    return ProteusSerializer().load(directory, filename)


def load_proteus_equipment_only(directory: Path, filename: str) -> DexpiModel:
    """Betölt egy `save_proteus_equipment_only`-val írt, csak berendezést tartalmazó fájlt.

    Ugyanaz a hívás, mint `load_proteus` — a külön név csak azt jelzi, hogy ide
    csak a generátor csonkolt exportja való, ahol a plusz (csővezeték/műszer)
    tudás garantáltan üres listaként tér vissza.
    """
    return load_proteus(directory, filename)


def _require_dexpi_model(loaded: object) -> DexpiModel:
    """`JsonSerializer.load` típusa `DexpiBaseModel`.

    Itt igazoljuk, hogy tényleg egy `DexpiModel` jött vissza.
    """
    if not isinstance(loaded, DexpiModel):
        raise TypeError(
            f"expected a DexpiModel from JsonSerializer.load, got {type(loaded).__name__}"
        )
    return loaded
