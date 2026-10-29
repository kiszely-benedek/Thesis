"""The sealed claims for V2T: same rules as F1, pointed at cascade_v4_iso and V2T's references."""

from __future__ import annotations

from pathlib import Path

import pytest

from cascade_toy import CORPUS
from cascade_v4_toy import tier_sources
from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade import cli as cascade_cli
from plantgraph.qa.cascade import join
from plantgraph.qa.cascade.checks import load_questions_file
from plantgraph.qa.cascade.evaluate import LatencyBound, evaluate_policy
from plantgraph.qa.cascade.join import JoinedCorpus, join_corpus
from plantgraph.qa.cascade.limits import SETTING_A
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, V2T_REFERENCES_DIR, load_policies
from plantgraph.qa.cascade.report import build_report
from plantgraph.qa.cascade.report_claims import CLAIM_PRESETS, F1_CLAIMS, V2T_CLAIMS
from plantgraph.qa.cascade.report_sealed import build_sealed
from plantgraph.qa.cascade.report_sealed_views import SealedCorpus
from plantgraph.qa.need.labels import NeedLabel


@pytest.fixture(autouse=True)
def _label_by_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    """The toy corpus has no graph: the first question is a first-valve one, the rest generic."""
    monkeypatch.setattr(
        join,
        "classify_need",
        lambda text, finder: (
            NeedLabel.UPSTREAM_TO_FIRST_VALVE if "E-10-1" in text else NeedLabel.GENERIC
        ),
    )


def _v2t_policies() -> dict[str, CascadePolicy]:
    return {**load_policies(V2T_POLICIES_DIR), **load_policies(V2T_REFERENCES_DIR)}


def _corpus(tmp_path: Path, corpus_id: str, n_sheets: int) -> SealedCorpus:
    sources = tier_sources(tmp_path, timeout_s=SETTING_A.cypher_timeout_s)
    _, questions = load_questions_file(tmp_path / "questions", CORPUS)
    joins: dict[str, JoinedCorpus] = {
        name: join_corpus(
            policy, sources, CORPUS, tmp_path / "questions", find_anchors=lambda text: Anchors()
        )
        for name, policy in _v2t_policies().items()
    }
    evaluations = {name: evaluate_policy(j, SETTING_A.cutoff_s) for name, j in joins.items()}
    return SealedCorpus(corpus_id, n_sheets, questions, None, joins, evaluations)


def test_the_reference_policies_are_one_tier_copies_of_the_v4_tiers() -> None:
    policies = _v2t_policies()
    v4 = policies["cascade_v4"]

    assert set(load_policies(V2T_REFERENCES_DIR)) == {"always_c_v2t", "always_g_v2t"}
    cypher_only, agent_only = policies["always_c_v2t"], policies["always_g_v2t"]
    assert [t.name for t in cypher_only.tiers] == [v4.tiers[0].name]
    assert [t.name for t in agent_only.tiers] == [v4.tiers[1].name]
    assert cypher_only.tiers[0].pin_sha256 == v4.tiers[0].pin_sha256
    assert agent_only.tiers[0].pin_sha256 == v4.tiers[1].pin_sha256


def test_the_presets_name_policies_that_exist() -> None:
    assert CLAIM_PRESETS == {"f1": F1_CLAIMS, "v2t": V2T_CLAIMS}
    names = set(_v2t_policies())
    assert {V2T_CLAIMS.primary, V2T_CLAIMS.tier2_comparator} <= names
    assert {V2T_CLAIMS.cypher_comparator, V2T_CLAIMS.random_reference} <= names
    assert V2T_CLAIMS.primary == "cascade_v4_iso" and V2T_CLAIMS.random_reference == "cascade_v4"


def test_the_claims_are_about_cascade_v4_iso_and_k2_uses_its_unrouted_sibling(
    tmp_path: Path,
) -> None:
    small = _corpus(tmp_path / "small", "T1", 10)
    large = _corpus(tmp_path / "large", "T1b", 100)

    sealed = build_sealed([small, large], LatencyBound(cutoff_s=SETTING_A.cutoff_s), V2T_CLAIMS)

    rules = {v.rule for v in sealed.claims}
    assert "Q4 (primary) cascade_v4_iso" in rules and "Q4' cascade_v4" in rules
    pairs = {(p.claim, p.policy, p.reference) for p in sealed.paired_rows if p.corpus_id == "T1b"}
    assert ("K1", "cascade_v4_iso", "always_g_v2t") in pairs
    assert ("K2", "cascade_v4", "random escalation") in pairs
    assert ("Q5", "always_g_v2t", "always_c_v2t") in pairs
    k3 = next(v for v in sealed.claims if v.rule == "K3")
    assert k3.status != "INCOMPLETE"


def test_the_f1_default_still_looks_for_cascade_v3(tmp_path: Path) -> None:
    small = _corpus(tmp_path / "small", "T1", 10)
    large = _corpus(tmp_path / "large", "T1b", 100)

    sealed = build_sealed([small, large], LatencyBound())

    primary = [v for v in sealed.claims if v.rule == "Q4 (primary)"]
    assert primary and "cascade_v3 on both corpora is not available" in primary[0].headline


def test_a_setting_sets_the_cutoff_and_a_different_cutoff_is_refused() -> None:
    parse = cascade_cli._parse_args
    base = ["report", "--corpus", "c", "--questions-root", "q", "--out", "o", "--run", "c:t=r"]

    assert cascade_cli._cutoff_s(parse([*base, "--setting", "A"])) == 120.0
    assert cascade_cli._cutoff_s(parse([*base, "--setting", "B"])) == 900.0
    assert cascade_cli._cutoff_s(parse(base)) == 120.0
    assert cascade_cli._cutoff_s(parse([*base, "--cutoff-s", "60"])) == 60.0
    with pytest.raises(SystemExit, match="expected --cutoff-s 120 for setting A"):
        cascade_cli._cutoff_s(parse([*base, "--setting", "A", "--cutoff-s", "60"]))


def test_without_baselines_the_report_holds_only_the_policies_given(tmp_path: Path) -> None:
    sources = tier_sources(tmp_path, timeout_s=SETTING_A.cypher_timeout_s)
    v4 = load_policies(V2T_POLICIES_DIR)["cascade_v4"]
    questions_root = tmp_path / "questions"

    report = build_report([CORPUS], {CORPUS: sources}, questions_root, [v4], with_baselines=False)

    corpus = report.corpora[0]
    assert [p.summary.policy for p in corpus.policies] == ["cascade_v4"]
    assert corpus.not_evaluated == []  # F1's always-N/C/G would be listed here as not evaluated
    with pytest.raises(ValueError, match="expected --policy"):
        build_report([CORPUS], {CORPUS: sources}, questions_root, None, with_baselines=False)
