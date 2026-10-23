"""Wide crops (6x width, 80px margin) straight from the source PNGs, sheets 3-11.
Also a 3x-upscaled tight crop of the flag itself for label reading."""
import sys, json
from pathlib import Path
from PIL import Image
sys.path.insert(0, "src")
from plantgraph.benchmark.open100.extract import connectors_in_sheet

ROOT = Path(r"C:\Users\b.kiszely\Desktop\Projects\Work Done\PID2Graph\Complete\PID2Graph OPEN100")
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
index = {}
for sheet in range(3, 12):
    img = Image.open(ROOT / f"{sheet}.png").convert("L")
    obs = connectors_in_sheet(ROOT / f"{sheet}.graphml", img.width)
    for o in obs:
        node = "".join(ch for ch in o.node_id if ch.isdigit())
        b = o.bbox
        wide = b.expanded(6.0, 80).clipped_to(*img.size)
        w = img.crop(wide.as_pixels())
        # upscale so small text survives the viewer's downscale
        scale = 2 if w.width < 1400 else 1
        if scale > 1:
            w = w.resize((w.width*scale, w.height*scale), Image.LANCZOS)
        w.save(OUT / f"{sheet}_{node}_wide.png")
        tight = b.expanded(0.5, 15).clipped_to(*img.size)
        t = img.crop(tight.as_pixels())
        t = t.resize((t.width*3, t.height*3), Image.LANCZOS)
        t.save(OUT / f"{sheet}_{node}_flag.png")
        index[f"{sheet}/{node}"] = dict(bbox=[b.xmin,b.ymin,b.xmax,b.ymax], side=o.side.value, img=[img.width, img.height])
(OUT / "index.json").write_text(json.dumps(index, indent=1))
print(len(index), "connectors cropped")
for k, v in index.items():
    print(k, v["side"], [round(x) for x in v["bbox"]], "size", round(v["bbox"][2]-v["bbox"][0]), "x", round(v["bbox"][3]-v["bbox"][1]))
