"""Crop the off-page connectors out of the drawings and arrange them onto readable sheets.

Why this approach: a connector's label can only be obtained from the image (the
annotation file has no text at all, see extract.py). A trial run on 2026-08-25
showed that the label sits entirely within the symbol's bounding box, and reads
clearly once cropped. So there is no need to train an OCR model — cropping and
reading it is enough.

The crops are strung into montages — one montage stacks images of a few dozen
connectors on top of each other — so a single read can process many labels at
once. Each row gets its connector's identifier written on the left, otherwise
the text read back off it could not be matched to its source.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from plantgraph.benchmark.models import ConnectorObservation

#: How far the crop extends sideways, as a multiple of the box width.
#: The label sits inside the box, but the pipe's identifier sits next to it —
#: this margin reaches that too.
X_FACTOR = 3.0

#: Vertical margin in pixels, so a two-line label's frame still fits.
Y_MARGIN = 25

#: How many rows go on one montage. Enough to make a single read worthwhile,
#: but not so many that shrinking it down makes it unreadable.
ROWS_PER_MONTAGE = 12

_ROW_WIDTH = 1500
_GUTTER = 130
_PAD = 14


def crop_connector(image: Image.Image, observation: ConnectorObservation) -> Image.Image:
    """Crop a connector out of its sheet, together with the pipe identifier running next to it."""
    box = observation.bbox.expanded(X_FACTOR, Y_MARGIN).clipped_to(*image.size)
    return image.crop(box.as_pixels()).convert("L")


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """A proper font if one is found on the machine, otherwise PIL's tiny built-in font."""
    for candidate in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _scaled(crop: Image.Image, width: int) -> Image.Image:
    """Scale the crop to a uniform width, keeping the aspect ratio."""
    height = max(1, round(width * crop.height / crop.width))
    return crop.resize((width, height), Image.Resampling.LANCZOS)


def build_montage(crops: list[tuple[str, Image.Image]], row_width: int = _ROW_WIDTH) -> Image.Image:
    """Stack the crops on top of each other, writing each one's identifier alongside it.

    Args:
        crops: (identifier, image) pairs. The identifier is placed on the left
            margin, so a label read off a row can be traced back to its connector.
        row_width: the pixel width the rows are scaled to.

    Raises:
        ValueError: if crops is empty — building an empty montage makes no sense.
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
    """A short row identifier: the sheet number, then the node's number.

    Sheet 5's 'inlet/outlet47' node becomes '5/47'. Short enough to fit the
    margin, and unique across the whole drawing series.
    """
    digits = "".join(ch for ch in observation.node_id if ch.isdigit())
    return f"{observation.sheet_file}/{digits}"


def write_montages(
    observations: list[ConnectorObservation],
    image_for_sheet: dict[str, Image.Image],
    out_dir: Path,
    rows_per_montage: int = ROWS_PER_MONTAGE,
) -> dict[str, str]:
    """Write out the montages covering every connector, and return the row-to-connector mapping.

    Args:
        observations: the connectors to process, in sheet order.
        image_for_sheet: the opened drawing for each sheet, for cropping.
        out_dir: where the montage_NN.png files are written.
        rows_per_montage: how many connectors go on one montage.

    Returns:
        {row identifier: connector key} — the traceability chain. Without it, a
        label read off a montage could not be attributed to its source.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tag_to_key = {montage_tag(o): o.key for o in observations}

    batches = [
        observations[i : i + rows_per_montage]
        for i in range(0, len(observations), rows_per_montage)
    ]
    for index, batch in enumerate(batches):
        crops = [(montage_tag(o), crop_connector(image_for_sheet[o.sheet_file], o)) for o in batch]
        build_montage(crops).save(out_dir / f"montage_{index:02d}.png")
    return tag_to_key
