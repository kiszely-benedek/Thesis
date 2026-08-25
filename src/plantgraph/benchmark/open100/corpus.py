"""Végigmegy a 12 OPEN100 rajzon, és olvasásra készíti elő a csatlakozóikat.

Ez az annotációs munka első fele. A cél, hogy a rajzokból visszanyerjük, melyik
cső melyik másik lapon folytatódik — ez a megoldókulcs, amihez majd a rendszert
mérjük. A folyamat két szakasza:

  1. **ez a modul**: megkeresi a csatlakozókat és képeket készít róluk olvasásra,
  2. később: a feliratok értelmezése és a lapok közötti párosítás.

Részletes terv: docs/private/40-design/open100-annotation.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from plantgraph.benchmark.models import ConnectorObservation, SplitManifest
from plantgraph.benchmark.open100 import crops, extract
from plantgraph.benchmark.open100.sheets import SHEETS

SOURCE_NAME = "PID2Graph/OPEN100"


class Open100Corpus:
    """A 12 OPEN100 rajz és a hozzájuk tartozó annotációs fájlok együtt."""

    def __init__(self, root: Path) -> None:
        """Args:
        root: a 'Complete/PID2Graph OPEN100' könyvtár, amelyben a 0.png .. 11.png
            rajzok és a hozzájuk tartozó .graphml fájlok vannak.

        Raises:
            FileNotFoundError: ha a könyvtár nincs meg, vagy bármelyik lap hiányzik.
                Inkább itt bukjon el, mint hogy egy hiányos rajzsorozatból készült
                megoldókulcsra alapozzunk mérést.
        """
        self.root = root
        if not root.is_dir():
            raise FileNotFoundError(f"OPEN100 directory not found: {root}")
        missing = [
            stem
            for stem in SHEETS
            if not (root / f"{stem}.png").exists()
            or not (root / f"{stem}.graphml").exists()
        ]
        if missing:
            raise FileNotFoundError(
                f"expected 12 png/graphml pairs in {root}; missing for sheets: "
                f"{', '.join(sorted(missing))}"
            )

    def image(self, file_stem: str) -> Image.Image:
        """Megnyitja egy lap rajzát. A hívó dolga lezárni."""
        return Image.open(self.root / f"{file_stem}.png")

    def observations(self) -> list[ConnectorObservation]:
        """Az összes lapközi csatlakozó mind a 12 rajzról, lapsorrendben.

        A rajz szélessége azért kell, mert abból dől el, hogy a csatlakozó a bal
        vagy a jobb lapszélen van.
        """
        found: list[ConnectorObservation] = []
        for stem in sorted(SHEETS, key=int):
            with self.image(stem) as img:
                width = img.width
            found.extend(
                extract.connectors_in_sheet(self.root / f"{stem}.graphml", width)
            )
        return found

    def prepare_reading(self, out_dir: Path) -> dict[str, str]:
        """Kiírja a montázsokat és a hozzájuk tartozó két kísérőfájlt.

        Amit a kimeneti könyvtárban hagy:
          - montage_NN.png: a csatlakozók képei, olvasásra,
          - tag_to_key.json: melyik montázssor melyik csatlakozó (nyomkövetés),
          - manifest_stage1.json: a megoldókulcs csontváza, egyelőre feliratok nélkül.
        """
        observations = self.observations()
        images = {stem: self.image(stem) for stem in SHEETS}
        try:
            tag_to_key = crops.write_montages(observations, images, out_dir)
        finally:
            # A 12 nagy felbontású rajz sok memóriát fog; hiba esetén is engedjük el.
            for img in images.values():
                img.close()

        (out_dir / "tag_to_key.json").write_text(
            json.dumps(tag_to_key, indent=2), encoding="utf-8"
        )
        (out_dir / "manifest_stage1.json").write_text(
            self.draft_manifest(observations).model_dump_json(indent=2),
            encoding="utf-8",
        )
        return tag_to_key

    def draft_manifest(self, observations: list[ConnectorObservation]) -> SplitManifest:
        """A megoldókulcs első változata: csak az, hol vannak a csatlakozók.

        A feliratok és a párosítások a második szakaszban kerülnek bele.
        """
        return SplitManifest(
            source=SOURCE_NAME,
            sheet_files=sorted(SHEETS, key=int),
            connectors=observations,
        )
