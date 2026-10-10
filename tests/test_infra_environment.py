"""`collect_machine_info` and `collect_run_environment`: sources are monkeypatched."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.infra import environment
from plantgraph.infra.environment import (
    NEO4J_MEMORY_SETTINGS_QUERY,
    RunEnvironment,
    collect_machine_info,
    collect_run_environment,
    memory_settings_from_rows,
)


def test_windows_branch_reads_the_registry_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(environment.sys, "platform", "win32")
    monkeypatch.setattr(environment, "_windows_cpu_name", lambda: "Fake Ryzen")
    assert collect_machine_info().cpu_name == "Fake Ryzen"


def test_linux_branch_reads_the_first_model_name_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cpuinfo = tmp_path / "cpuinfo"
    cpuinfo.write_text("processor\t: 0\nmodel name\t: Fake Xeon\nmodel name\t: other\n", "utf-8")
    monkeypatch.setattr(environment.sys, "platform", "linux")
    monkeypatch.setattr(environment, "_LINUX_CPUINFO", cpuinfo)
    assert collect_machine_info().cpu_name == "Fake Xeon"


def test_linux_without_cpuinfo_says_unknown(tmp_path: Path) -> None:
    assert environment._linux_cpu_name(tmp_path / "missing") == "unknown"


def test_other_platforms_fall_back_to_the_platform_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(environment.sys, "platform", "darwin")
    monkeypatch.setattr(environment.platform, "processor", lambda: "arm")
    assert collect_machine_info().cpu_name == "arm"


def test_machine_info_reports_memory_and_power_state(monkeypatch: pytest.MonkeyPatch) -> None:
    class Battery:
        power_plugged = True

    monkeypatch.setattr(environment, "_cpu_name", lambda: "x")
    monkeypatch.setattr(environment.psutil, "sensors_battery", lambda: Battery())
    info = collect_machine_info()
    assert info.ram_bytes > 0
    assert info.power_plugged is True
    monkeypatch.setattr(environment.psutil, "sensors_battery", lambda: None)
    assert collect_machine_info().power_plugged is None


def test_run_environment_carries_clock_commit_and_concurrency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(environment, "read_git_state", lambda _root: ("abc123", True))
    monkeypatch.setattr(environment, "_cpu_name", lambda: "x")
    env = collect_run_environment(tmp_path, concurrency=4, neo4j_memory_settings={"a": "1"})
    assert (env.git_commit, env.git_dirty, env.concurrency) == ("abc123", True, 4)
    assert env.clock == "perf_counter"
    assert env.clock_resolution_s <= 1e-6  # the point of the clock fix
    assert env.neo4j_version is None
    assert env.neo4j_memory_settings == {"a": "1"}
    assert RunEnvironment.model_validate_json(env.model_dump_json()) == env


def test_memory_settings_rows_become_a_dict() -> None:
    rows = [
        {"name": "server.memory.heap.max_size", "value": "1G"},
        {"name": "server.memory.pagecache.size", "value": "512m"},
    ]
    assert memory_settings_from_rows(rows) == {
        "server.memory.heap.max_size": "1G",
        "server.memory.pagecache.size": "512m",
    }
    assert "server.memory" in NEO4J_MEMORY_SETTINGS_QUERY
