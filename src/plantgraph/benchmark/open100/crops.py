"""Kivágja a csatlakozókat a rajzokból, és olvasható lapokra rendezi őket.

Miért így: a csatlakozók feliratát csak a képről lehet megszerezni (az annotációs
fájlban nincs szöveg, lásd extract.py). Egy 2026-08-25-i próba viszont kimutatta,
hogy a felirat teljes egészében a szimbólum befoglaló dobozán belül van, és
kivágás után jól olvasható. Így nem kell OCR-modellt tanítani: elég kivágni és
elolvasni.

A kivágásokat montázsokba fűzzük — egy montázs több tucat csatlakozó képe egymás
alatt —, mert így egy olvasással sok felirat feldolgozható. Minden sor bal
oldalára odaírjuk, melyik csatlakozóhoz tartozik, különben a visszaolvasott
szöveget nem lehetne a helyére tenni.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from plantgraph.benchmark.models import ConnectorObservation

#: Mennyivel nyúljon ki a kivágás oldalra, a doboz szélességének szorosaként.
#: A felirat a dobozon belül van, de a cső azonosítója mellette — ez a ráhagyás
#: éri el azt is.
X_FACTOR = 3.0

#: Függőleges ráhagyás képpontban, hogy a kétsoros felirat kerete elférjen.
Y_MARGIN = 25

#: Hány sor kerüljön egy montázsra. Elég sok, hogy megérje egy olvasás, de nem
#: annyi, hogy a lekicsinyítés miatt olvashatatlanná váljon.
ROWS_PER_MONTAGE = 12

_ROW_WIDTH = 1500
_GUTTER = 130
_PAD = 14


def crop_connector(image: Image.Image, observation: ConnectorObservation) -> Image.Image:
    """Kivág egy csatlakozót a lapjából, a mellette futó cső azonosítójával együtt."""
    box = observation.bbox.expanded(X_FACTOR, Y_MARGIN).clipped_to(*image.size)
    return image.crop(box.as_pixels()).convert("L")


def _load_font(size: int) -> ImageFont.ImageFont:
    """Rendes betűtípus, ha található a gépen, különben a PIL apró beépített fontja."""
    for candidate in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _scaled(crop: Image.Image, width: int) -> Image.Image:
    """Egységes szélességre húzza a kivágást, megtartva az oldalarányt."""
    height = max(1, round(width * crop.height / crop.width))
    return crop.resize((width, height), Image.LANCZOS)


def build_montage(
    crops: list[tuple[str, Image.Image]], row_width: int = _ROW_WIDTH
) -> Image.Image:
    """Egymás alá fűzi a kivágásokat, mindegyik mellé odaírva az azonosítóját.

    Args:
        crops: (azonosító, kép) párok. Az azonosító a bal margóra kerül, hogy a
            sorból kiolvasott felirat visszavezethető legyen a csatlakozóra.
        row_width: erre a képpontszélességre skálázzuk a sorokat.

    Raises:
        ValueError: ha a crops üres — üres montázst készíteni értelmetlen.
    """
    if not crops:
        raise ValueError("cannot build a montage from zero crops")

    rows = [(tag, _scaled(img, row_width)) for tag, img in crops]
    height = sum(img.height + _PAD for _, img in rows) + _PAD
    sheet = Image.new("L", (row_width + _GUTTER, height), color=255)
    draw = ImageDraw.Draw(sheet)
    font = _load_font(26)

    y = _PAD
    for tag, img in rows:
        draw.line([(0, y - _PAD // 2), (sheet.width, y - _PAD // 2)], fill=0)
        draw.text((8, y + img.height // 2 - 13), tag, fill=0, font=font)
        sheet.paste(img, (_GUTTER, y))
        y += img.height + _PAD
    return sheet


def montage_tag(observation: ConnectorObservation) -> str:
    """Rövid sorazonosító: a lap száma, majd a csomópont sorszáma.

    Az 5-ös lap 'inlet/outlet47' csomópontjából '5/47' lesz. Elég rövid, hogy
    elférjen a margón, és a teljes rajzsorozaton belül egyedi.
    """
    digits = "".join(ch for ch in observation.node_id if ch.isdigit())
    return f"{observation.sheet_file}/{digits}"


def write_montages(
    observations: list[ConnectorObservation],
    image_for_sheet: dict[str, Image.Image],
    out_dir: Path,
    rows_per_montage: int = ROWS_PER_MONTAGE,
) -> dict[str, str]:
    """Kiírja az összes csatlakozót lefedő montázsokat, és visszaadja a hozzárendelést.

    Args:
        observations: a feldolgozandó csatlakozók, lapsorrendben.
        image_for_sheet: laponként a megnyitott rajz, a kivágásokhoz.
        out_dir: ide kerülnek a montage_NN.png fájlok.
        rows_per_montage: hány csatlakozó jusson egy montázsra.

    Returns:
        {sorazonosító: csatlakozókulcs} — ez a nyomkövetési lánc. Nélküle a
        montázsról leolvasott felirat nem rendelhető ahhoz, amelyikről származik.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tag_to_key = {montage_tag(o): o.key for o in observations}

    batches = [
        observations[i : i + rows_per_montage]
        for i in range(0, len(observations), rows_per_montage)
    ]
    for index, batch in enumerate(batches):
        crops = [
            (montage_tag(o), crop_connector(image_for_sheet[o.sheet_file], o))
            for o in batch
        ]
        build_montage(crops).save(out_dir / f"montage_{index:02d}.png")
    return tag_to_key
