"""The record of where and how a measurement ran: machine, clock, commit, concurrency.

Timings only mean something next to the machine that produced them, so every harness
invocation appends one `RunEnvironment` line to the run's `environment.jsonl`.
"""

from __future__ import annotations

import platform
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
from pydantic import BaseModel, ConfigDict

from plantgraph.qa.harness.freeze import read_git_state

#: The query that returns the memory settings of a Neo4j server (needs admin rights).
NEO4J_MEMORY_SETTINGS_QUERY = (
    "SHOW SETTINGS YIELD name, value WHERE name STARTS WITH 'server.memory'"
)

_WINDOWS_CPU_KEY = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
_LINUX_CPUINFO = Path("/proc/cpuinfo")


class MachineInfo(BaseModel):
    """The computer a measurement ran on."""

    model_config = ConfigDict(frozen=True)

    cpu_name: str
    physical_cores: int | None
    logical_cores: int | None
    ram_bytes: int
    os: str
    python_version: str
    #: Whether a laptop was on mains power; `None` when there is no battery to ask.
    power_plugged: bool | None


class RunEnvironment(BaseModel):
    """One measurement's environment: code version, machine, clock and database settings."""

    model_config = ConfigDict(frozen=True)

    git_commit: str
    git_dirty: bool
    machine: MachineInfo
    #: The clock the timings were taken with, and the smallest step it can tell apart.
    clock: str
    clock_resolution_s: float
    #: Items answered at once; `None` for a measurement that has no such notion.
    concurrency: int | None
    neo4j_version: str | None
    neo4j_memory_settings: dict[str, str]
    recorded_at: datetime


def collect_machine_info() -> MachineInfo:
    """Read the CPU, memory, operating system and power state of this computer."""
    battery = psutil.sensors_battery()
    return MachineInfo(
        cpu_name=_cpu_name(),
        physical_cores=psutil.cpu_count(logical=False),
        logical_cores=psutil.cpu_count(logical=True),
        ram_bytes=psutil.virtual_memory().total,
        os=platform.platform(),
        python_version=platform.python_version(),
        power_plugged=None if battery is None else bool(battery.power_plugged),
    )


def collect_run_environment(
    repo_root: Path,
    concurrency: int | None,
    neo4j_version: str | None = None,
    neo4j_memory_settings: Mapping[str, str] | None = None,
) -> RunEnvironment:
    """The environment of a measurement starting now; the Neo4j facts are given by the caller.

    Raises:
        RuntimeError: git is unavailable in `repo_root` (from `read_git_state`).
    """
    commit, dirty = read_git_state(repo_root)
    return RunEnvironment(
        git_commit=commit,
        git_dirty=dirty,
        machine=collect_machine_info(),
        clock="perf_counter",
        clock_resolution_s=time.get_clock_info("perf_counter").resolution,
        concurrency=concurrency,
        neo4j_version=neo4j_version,
        neo4j_memory_settings=dict(neo4j_memory_settings or {}),
        recorded_at=datetime.now(UTC),
    )


def memory_settings_from_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """`{name: value}` from the rows of `NEO4J_MEMORY_SETTINGS_QUERY`."""
    return {str(row["name"]): str(row["value"]) for row in rows}


def _cpu_name() -> str:
    if sys.platform == "win32":
        return _windows_cpu_name()
    if sys.platform.startswith("linux"):
        return _linux_cpu_name(_LINUX_CPUINFO)
    return platform.processor() or "unknown"


def _windows_cpu_name() -> str:
    import winreg  # Windows only, so imported where it is used

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _WINDOWS_CPU_KEY) as key:
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
    return str(name).strip()


def _linux_cpu_name(cpuinfo: Path) -> str:
    """The first `model name` line of `/proc/cpuinfo`, or `unknown` if there is none."""
    if not cpuinfo.exists():
        return "unknown"
    for line in cpuinfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.split(":", 1)[1].strip()
    return "unknown"
