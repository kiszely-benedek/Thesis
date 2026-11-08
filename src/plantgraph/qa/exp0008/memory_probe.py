"""The M0 pool memory probe: run a command and record its peak memory (review-fixes §6, M0).

The first measurement's 1,000-sheet question pool took 2.4 hours; five of them are scheduled, so M0
proves that one finishes on this machine. Peak memory is the largest resident set of the command
and all its children, sampled while it runs.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from collections.abc import Sequence

import psutil
from pydantic import BaseModel, ConfigDict

_SAMPLE_INTERVAL_S = 0.2
#: the probe fails when the command's peak exceeds this share of the machine's memory
DEFAULT_LIMIT_SHARE = 0.9


class ProbeResult(BaseModel):
    """What the probe measured."""

    model_config = ConfigDict(frozen=True)

    command: list[str]
    return_code: int
    seconds: float
    peak_rss_bytes: int
    limit_bytes: int

    @property
    def passed(self) -> bool:
        """The command succeeded and stayed under the limit."""
        return self.return_code == 0 and self.peak_rss_bytes <= self.limit_bytes


def _tree_rss(process: psutil.Process) -> int:
    total = 0
    for member in [process, *process.children(recursive=True)]:
        try:
            total += member.memory_info().rss
        except psutil.NoSuchProcess:
            continue  # a child that ended between listing and reading
    return total


def probe(command: Sequence[str], limit_bytes: int | None = None) -> ProbeResult:
    """Run `command` to the end and report its peak memory."""
    limit = limit_bytes or int(psutil.virtual_memory().total * DEFAULT_LIMIT_SHARE)
    # `which` finds `.venv/Scripts/python` as python.exe; Popen alone cannot on Windows
    executable = shutil.which(command[0])
    if executable is None:
        raise FileNotFoundError(f"expected an executable named {command[0]!r}, found none")
    command = [executable, *command[1:]]
    started = time.monotonic()
    child = subprocess.Popen(list(command))  # noqa: S603 - the launcher's own command line
    handle = psutil.Process(child.pid)
    peak = 0
    while child.poll() is None:
        peak = max(peak, _tree_rss(handle))
        time.sleep(_SAMPLE_INTERVAL_S)
    return ProbeResult(
        command=list(command),
        return_code=int(child.returncode),
        seconds=round(time.monotonic() - started, 2),
        peak_rss_bytes=peak,
        limit_bytes=limit,
    )
