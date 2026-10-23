"""custom_crop.py SHEET X0 Y0 X1 Y1 OUT [SCALE] — arbitrary region from a sheet PNG."""
import sys
from pathlib import Path
from PIL import Image
ROOT = Path(r"C:\Users\b.kiszely\Desktop\Projects\Work Done\PID2Graph\Complete\PID2Graph OPEN100")
sheet, x0, y0, x1, y1, out = sys.argv[1:7]
scale = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
img = Image.open(ROOT / f"{sheet}.png").convert("L")
box = (max(0,int(x0)), max(0,int(y0)), min(img.width,int(x1)), min(img.height,int(y1)))
c = img.crop(box)
if scale != 1.0:
    c = c.resize((int(c.width*scale), int(c.height*scale)), Image.LANCZOS)
c.save(out); print(out, c.size)
