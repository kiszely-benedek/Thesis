"""Field-by-field diff: annotations.py vs opus_recheck.py for sheets 3-11."""
import sys, importlib.util
from pathlib import Path
sys.path.insert(0, "src")
from plantgraph.benchmark.open100.annotations import ANNOTATIONS

spec = importlib.util.spec_from_file_location("opus", "docs/private/30-experiments/open100-stage1/opus_recheck.py")
opus = importlib.util.module_from_spec(spec); spec.loader.exec_module(opus)

cur = {(r.sheet, r.node): r for r in ANNOTATIONS if int(r.sheet) >= 3}
fields = ["target_pid", "target_sheet_no", "target_grid", "service", "line_number"]
n_same = 0
for row in opus.ROWS:
    sheet, node, pid, sno, grid, svc, line, conf, note = row
    o = dict(target_pid=pid, target_sheet_no=sno, target_grid=grid, service=svc, line_number=line)
    c = cur[(sheet, node)]
    diffs = [(f, getattr(c, f), o[f]) for f in fields if getattr(c, f) != o[f]]
    if diffs:
        print(f"{sheet}/{node}  [opus conf={conf}]")
        for f, a, b in diffs:
            print(f"    {f:16s} annotations={a!r:35s} opus={b!r}")
    else:
        n_same += 1
print(f"\nexact agreement on all 5 fields: {n_same}/{len(opus.ROWS)}")
