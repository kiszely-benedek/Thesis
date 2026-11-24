"""Plants for the V2T-B tests (not a test module): a tiny hand-built one and a real v2.2 one."""

from __future__ import annotations

from functools import cache

import networkx as nx

from plantgraph.benchmark.generator_dispatch import generate_plant_graph_and_rules
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.ingest.headline_v22 import HeadlinePresetV22
from plantgraph.ingest.pipeline import SyntheticCorpus, build_synthetic_corpus

LINE = '6"-P-1203-A1A'
BRANCH = "2-P-1204-A1A"


def _node(graph: nx.DiGraph[str], node_id: str, node_class: str, tag: str | None = None) -> None:
    attrs = {"node_class": node_class}
    graph.add_node(node_id, **({"tag": tag} if tag else {}), **attrs)


def _flow(graph: nx.DiGraph[str], chain: list[str], line: str) -> None:
    for source, target in zip(chain, chain[1:], strict=False):
        graph.add_edge(source, target, relation="send_to", line_number=line)


def toy_plant() -> nx.DiGraph[str]:
    """P-1 -> g1 -> g2(ball) -> FV-1 -> g3 -> T-1, a tee t on the line with an untagged branch.

    g1 and g3 are untagged gate valves, g2 an untagged ball valve; `t` sits between g1 and g2 and
    feeds the branch valve `b` (another line) into the tagged tank T-2.
    """
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class, tag in [
        ("p", "CentrifugalPump", "P-1"),
        ("g1", "GateValve", None),
        ("t", "PipeTee", None),
        ("g2", "BallValve", None),
        ("fv", "GlobeValve", "FV-1"),
        ("g3", "GateValve", None),
        ("tank", "Tank", "T-1"),
        ("b", "GateValve", None),
        ("tank2", "Tank", "T-2"),
    ]:
        _node(plant, node_id, node_class, tag)
    _flow(plant, ["p", "g1", "t", "g2", "fv", "g3", "tank"], LINE)
    _flow(plant, ["t", "b", "tank2"], BRANCH)
    return plant


def series_plant() -> nx.DiGraph[str]:
    """T-1 -> v1 -> v2 -> T-2 with two untagged gate valves in series: neither can be told apart."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class, tag in [
        ("a", "Tank", "T-1"),
        ("v1", "GateValve", None),
        ("v2", "GateValve", None),
        ("c", "Tank", "T-2"),
    ]:
        _node(plant, node_id, node_class, tag)
    _flow(plant, ["a", "v1", "v2", "c"], LINE)
    return plant


def spec_break_plant() -> nx.DiGraph[str]:
    """Pump P-1 -> untagged discharge block -> tank T-1, the line number changing at the block."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class, tag in [
        ("pump", "CentrifugalPump", "P-1"),
        ("block", "GateValve", None),
        ("tank", "Tank", "T-1"),
    ]:
        _node(plant, node_id, node_class, tag)
    _flow(plant, ["pump", "block"], BRANCH)
    _flow(plant, ["block", "tank"], LINE)
    return plant


def root_valve_plant() -> nx.DiGraph[str]:
    """V-1 -> tee -> V-2; the tee also feeds an untagged needle valve into gauge PI-1."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class, tag in [
        ("v1", "Tank", "V-1"),
        ("t", "PipeTee", None),
        ("v2", "Tank", "V-2"),
        ("root", "NeedleValve", None),
        ("gauge", "PressureIndicator", "PI-1"),
    ]:
        _node(plant, node_id, node_class, tag)
    _flow(plant, ["v1", "t", "v2"], LINE)
    _flow(plant, ["t", "root", "gauge"], BRANCH)
    return plant


def bypass_plant() -> nx.DiGraph[str]:
    """T-1 -> gate -> control valve CV-1 -> gate -> T-2, an untagged globe valve bypassing CV-1."""
    plant: nx.DiGraph[str] = nx.DiGraph()
    for node_id, node_class, tag in [
        ("t1", "Tank", "T-1"),
        ("split", "PipeTee", None),
        ("gate_in", "GateValve", None),
        ("cv", "GlobeValve", "CV-1"),
        ("gate_out", "GateValve", None),
        ("join", "PipeTee", None),
        ("bypass", "GlobeValve", None),
        ("t2", "Tank", "T-2"),
    ]:
        _node(plant, node_id, node_class, tag)
    _flow(plant, ["t1", "split", "gate_in", "cv", "gate_out", "join", "t2"], LINE)
    _flow(plant, ["split", "bypass", "join"], LINE)
    return plant


@cache
def real_plant() -> nx.DiGraph[str]:
    """A small v2.2 plant (8 units, seed 1) whose first document prints no manual-valve tags."""
    plant, _rules = generate_plant_graph_and_rules(GeneratorConfigV22(seed=1, n_units=8))
    return plant


@cache
def real_corpus() -> SyntheticCorpus:
    """The same plant, split and resolved (no Neo4j, no model)."""
    config = GeneratorConfigV22(seed=1, n_units=8)
    return build_synthetic_corpus(config, HeadlinePresetV22().split_config(1))
