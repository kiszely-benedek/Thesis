"""Stage state files: `state/<stage>.done` holds the sha256 of the stage's outputs (design §5.4).

A rerun skips a done stage only after re-hashing its outputs; a changed or missing output means the
stage runs again. `state/STOPPED` tells the user why the launcher stopped and how to resume.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

STOPPED_FILE = "STOPPED"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_done(state_dir: Path, stage: str, outputs: Sequence[Path]) -> None:
    """Record that `stage` finished, with the hash of each output file.

    Raises:
        FileNotFoundError: an output file is missing (a stage must not report done without it).
    """
    missing = [p for p in outputs if not p.is_file()]
    if missing:
        raise FileNotFoundError(f"expected stage {stage} to have written {missing[0]}, found none")
    record = {
        "stage": stage,
        "finished_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "outputs": {p.as_posix(): _digest(p) for p in sorted(outputs)},
    }
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{stage}.done").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")


def done_problem(state_dir: Path, stage: str) -> str | None:
    """Why `stage` must run: `None` when it is done and every output still hashes as recorded."""
    marker = state_dir / f"{stage}.done"
    if not marker.is_file():
        return "no done marker"
    record = json.loads(marker.read_text(encoding="utf-8"))
    for name, expected in record["outputs"].items():
        path = Path(name)
        if not path.is_file():
            return f"output {name} is missing"
        if _digest(path) != expected:
            return f"output {name} changed since the stage finished"
    return None


def write_stopped(state_dir: Path, stage: str, reason: str, resume: str) -> None:
    """Leave `STOPPED` with the stage, the reason and the exact resume command."""
    state_dir.mkdir(parents=True, exist_ok=True)
    text = f"stage: {stage}\nreason: {reason}\nresume: {resume}\n"
    (state_dir / STOPPED_FILE).write_text(text, encoding="utf-8")
