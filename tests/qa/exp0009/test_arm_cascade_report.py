"""The offline cascade per arm, on the toy tier runs of the cascade tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from cascade_toy import CORPUS
from cascade_v4_toy import tier_sources
from plantgraph.llm.models import ModelPin
from plantgraph.qa.anchors import Anchors
from plantgraph.qa.cascade.join import JoinRefused
from plantgraph.qa.cascade.limits import SETTING_A
from plantgraph.qa.exp0009 import cascade_report as cr
from plantgraph.qa.need.labels import NeedLabel


@pytest.fixture(autouse=True)
def _no_corpus(monkeypatch: pytest.MonkeyPatch) -> None:
    """The toy corpus has no graph; the first question is labelled first-valve."""
    monkeypatch.setattr(cr, "load_corpus_view", lambda root, corpus_id: None)
    monkeypatch.setattr(cr, "anchor_finder", lambda view: lambda text: Anchors())
    from plantgraph.qa.cascade import join

    monkeypatch.setattr(
        join,
        "classify_need",
        lambda text, finder: (
            NeedLabel.UPSTREAM_TO_FIRST_VALVE if "E-10-1" in text else NeedLabel.GENERIC
        ),
    )


def test_a2_report_counts_per_family(tmp_path: Path) -> None:
    sources = tier_sources(tmp_path, timeout_s=SETTING_A.cypher_timeout_s)
    report = cr.build_arm_report(CORPUS, "A2", sources, tmp_path / "questions", tmp_path)
    assert report.policy == "cascade_v4_iso" and report.n_questions == 4
    assert sum(t for _c, t in report.by_family.values()) == 4
    assert sum(c for c, _t in report.by_family.values()) == report.n_correct
    assert 0.0 <= report.accuracy() <= 1.0


def test_b_policy_reads_the_b_strategy_names() -> None:
    policy = cr.policy_of("B")
    assert policy.name == "cascade_v4_iso_b"
    assert all(t.strategy.endswith("_b") for t in policy.tiers)
    with pytest.raises(ValueError, match="arm"):
        cr.policy_of("C")  # type: ignore[arg-type]


def test_the_frozen_need_classifier_accepts_every_x_question_text() -> None:
    """The cascade routes by need label: it must not raise on the scope X texts (§19.12 6)."""
    from exp0009_small import built_small
    from test_records import two_runs

    from plantgraph.qa.cascade.corpus_checks import load_corpus_view
    from plantgraph.qa.cascade.labels import anchor_finder, classify_need

    spec, corpora, _record = built_small()
    finder = anchor_finder(load_corpus_view(corpora, spec.b_id))
    texts = [q.text for q in two_runs().b_questions]
    assert texts and all(classify_need(text, finder) is not None for text in texts)


# ---- the GLM arm's policy (T13c, B3) --------------------------------------------------------


def _glm_pins(monkeypatch: pytest.MonkeyPatch) -> None:
    """The toy tier runs get GLM's pins (from `inputs/`) instead of the Luna pins of EXP-0007."""
    import cascade_v4_toy
    from plantgraph.qa.exp0009 import glm_policy

    files = {
        "pin_cypher_luna_low.json": glm_policy.GLM_PIN_FILES[0],
        "pin_agent_luna_final_high.json": glm_policy.GLM_PIN_FILES[1],
    }

    def glm_pin(file_name: str) -> ModelPin:
        text = (glm_policy.INPUTS / files[file_name]).read_text(encoding="utf-8")
        return ModelPin.model_validate_json(text)

    monkeypatch.setattr(cascade_v4_toy, "pin", glm_pin)


def test_the_glm_policy_is_a2_with_only_the_two_tier_pins_replaced() -> None:
    a2, glm = cr.policy_of("A2"), cr.policy_of("GLM")
    assert glm.name == "cascade_v4_iso_glm"
    assert [t.pin_sha256 for t in glm.tiers] != [t.pin_sha256 for t in a2.tiers]
    for a_tier, g_tier in zip(a2.tiers, glm.tiers, strict=True):
        assert g_tier.model_copy(update={"pin_sha256": a_tier.pin_sha256}) == a_tier
    assert glm.model_copy(update={"name": a2.name, "tiers": a2.tiers}) == a2


def test_glm_runs_pass_the_pin_check_of_the_glm_policy_and_are_refused_by_a2s(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _glm_pins(monkeypatch)
    sources = tier_sources(tmp_path, timeout_s=SETTING_A.cypher_timeout_s)
    report = cr.build_arm_report(CORPUS, "GLM", sources, tmp_path / "questions", tmp_path)
    assert report.arm == "GLM" and report.policy == "cascade_v4_iso_glm"
    assert report.n_questions == 4
    with pytest.raises(JoinRefused, match="pin"):
        cr.build_arm_report(CORPUS, "A2", sources, tmp_path / "questions", tmp_path)
