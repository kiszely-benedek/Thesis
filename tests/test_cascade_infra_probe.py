"""`infra-probe` with recording fakes: stage order, which stages a policy needs, memory sizing."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from plantgraph.qa.cascade import live_ask
from plantgraph.qa.cascade.infra_probe import (
    ProbeRequest,
    ProbeSteps,
    run_memory_probe,
    time_startup,
)
from plantgraph.qa.cascade.live import LivePolicyRefused
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policy
from plantgraph.store.neo4j_settings import Neo4jSettings

SETTINGS = Neo4jSettings(uri="neo4j://x", username="u", password=SecretStr("p"))


class _FakeStore:
    def close(self) -> None:
        pass


def _recording_steps(calls: list[str]) -> ProbeSteps:
    artifacts = SimpleNamespace(corpus_id="C", load_plan="plan", stage_seconds={"generate": 1.5})

    def record[T](name: str, result: T) -> T:
        calls.append(name)
        return result

    return ProbeSteps(
        rebuild=lambda corpus_id, path: record("rebuild", artifacts),  # type: ignore[arg-type,return-value]
        graph_view=lambda a: record("graph_view", "view"),  # type: ignore[arg-type,return-value]
        check_tier_runs=lambda policy, dirs: record("tier_runs", None),
        store_view=lambda settings, plan: record("schema_text", _FakeStore()),  # type: ignore[arg-type,return-value]
        check_store=lambda store, plan, policy: record("neo4j_open_check", None),
        item_graph=lambda view: record("item_graph", "items"),  # type: ignore[arg-type,return-value]
        context_prompt=lambda view: record("context_prompt", "abcd"),
    )


def _request(policy: CascadePolicy) -> ProbeRequest:
    return ProbeRequest("C", Path("ingest.json"), policy, {})


def _cascade_v3() -> CascadePolicy:
    return load_policy(POLICIES_DIR / "cascade_v3.json")


def test_stages_run_in_the_order_open_for_ask_builds_them() -> None:
    calls: list[str] = []
    timings = time_startup(_request(_cascade_v3()), SETTINGS, _recording_steps(calls))
    assert calls[:6] == [
        "rebuild",
        "graph_view",
        "tier_runs",
        "schema_text",
        "neo4j_open_check",
        "item_graph",
    ]
    assert list(timings.stage_seconds) == calls[:6]
    assert calls[6:] == ["context_prompt"] * 3  # three timed builds
    assert timings.rebuild_stage_seconds == {"generate": 1.5}
    assert timings.context_rag_chars == 4


def test_open_for_ask_builds_the_rebuild_and_the_view_in_the_probe_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[str] = []
    artifacts = SimpleNamespace(localized_sheets=[], resolution=None, load_plan=None, corpus_id="C")

    def fake_rebuild(*_: Any) -> Any:
        calls.append("rebuild")
        return artifacts

    def fake_view(*_: Any) -> Any:
        calls.append("graph_view")

    def stop(**_: Any) -> Any:
        raise RuntimeError("stop after the two builders")

    monkeypatch.setattr(live_ask, "load_corpus_artifacts", fake_rebuild)
    monkeypatch.setattr(live_ask, "NetworkxGraphView", fake_view)
    monkeypatch.setattr(live_ask, "open_live_cascade", stop)
    args = SimpleNamespace(
        corpus="C",
        corpora_root=tmp_path,
        policy="cascade_v3",
        run=[],
        cache_path=tmp_path,
        calls_log=tmp_path,
        replay_only=True,
        cutoff_s=1.0,
        session_cap_usd=1.0,
    )
    with pytest.raises(RuntimeError, match="stop after"):
        live_ask.open_for_ask(args)  # type: ignore[arg-type]
    assert calls == ["rebuild", "graph_view"]


def test_a_policy_without_a_cypher_tier_skips_the_database_stages() -> None:
    calls: list[str] = []
    policy = _cascade_v3()
    agent_only = policy.model_copy(update={"tiers": tuple(policy.tiers[1:])})
    time_startup(_request(agent_only), None, _recording_steps(calls))
    assert "schema_text" not in calls
    assert "item_graph" in calls


def test_a_cypher_tier_without_neo4j_settings_is_refused() -> None:
    with pytest.raises(ValueError, match="NEO4J_URI"):
        time_startup(_request(_cascade_v3()), None, _recording_steps([]))


def test_label_routing_is_refused_before_any_stage_runs() -> None:
    calls: list[str] = []
    routed = _cascade_v3().model_copy(update={"start_tier_by_label": {"X": "cypher-luna"}})
    with pytest.raises(LivePolicyRefused):
        time_startup(_request(routed), SETTINGS, _recording_steps(calls))
    assert calls == []


def test_memory_probe_counts_what_each_build_keeps_alive() -> None:
    steps = ProbeSteps(
        rebuild=lambda corpus_id, path: SimpleNamespace(),  # type: ignore[arg-type,return-value]
        graph_view=lambda a: [bytes(1000) for _ in range(1000)],  # type: ignore[arg-type,return-value]
        item_graph=lambda view: [bytes(4000) for _ in range(1000)],  # type: ignore[arg-type,return-value]
    )
    probe = run_memory_probe(_request(_cascade_v3()), steps)
    assert 1_000_000 <= probe.view_net_bytes < 1_500_000
    assert 4_000_000 <= probe.item_graph_net_bytes < 4_500_000
    assert probe.traced_peak_bytes >= probe.view_net_bytes + probe.item_graph_net_bytes


def test_cli_writes_the_memory_probe_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from plantgraph.infra.environment import collect_run_environment
    from plantgraph.infra.probe_models import MemoryProbe
    from plantgraph.qa.cascade import infra_probe_cli
    from plantgraph.qa.cascade.cli import main

    probe = MemoryProbe(
        corpus_id="C",
        environment=collect_run_environment(Path(__file__).resolve().parents[1], None),
        view_net_bytes=1,
        item_graph_net_bytes=2,
        traced_peak_bytes=3,
    )
    monkeypatch.setattr(infra_probe_cli, "run_memory_probe", lambda request: probe)
    out = tmp_path / "sub" / "memory.json"
    argv = ["infra-probe", "--corpus", "C", "--policy", "cascade_v3", "--memory", "--out", str(out)]
    main([*argv, "--run", "cypher-luna=a", "--run", "agent-luna=b"])
    assert MemoryProbe.model_validate_json(out.read_text(encoding="utf-8")) == probe
    assert '"view_net_bytes": 1' in capsys.readouterr().out
