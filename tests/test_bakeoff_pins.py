"""The stage-1 bake-off pin files load as `ModelPin`s and say what the README promises."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantgraph.llm.models import ModelPin

_PINS_DIR = Path(__file__).resolve().parents[1] / "data" / "runs" / "cv1" / "pins_bakeoff"
_CONFIGS = "ABCDEFG"

# `data/runs/` is git-ignored, so a fresh checkout has no pin files to check.
pytestmark = pytest.mark.skipif(not _PINS_DIR.is_dir(), reason="bake-off pin files not present")


def _load(name: str) -> ModelPin:
    return ModelPin.model_validate_json((_PINS_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("letter", list(_CONFIGS))
def test_answer_and_cypher_pins_load_and_share_model_and_host(letter: str) -> None:
    answer = _load(f"{letter}_answer.json")
    cypher = _load(f"{letter}_cypher.json")

    assert (answer.model_id, answer.route_provider) == (cypher.model_id, cypher.route_provider)
    assert cypher.extra["reasoning"] == {"effort": "low"}


@pytest.mark.parametrize("letter", list(_CONFIGS[1:]))
def test_every_config_but_the_baseline_pins_a_host(letter: str) -> None:
    assert _load(f"{letter}_answer.json").route_provider is not None


def test_baseline_is_the_current_default_pin() -> None:
    default = ModelPin.model_validate_json(
        (_PINS_DIR.parent / "pin_default.json").read_text(encoding="utf-8")
    )

    assert _load("A_answer.json") == default


def test_hosts_that_lack_a_parameter_do_not_get_it_sent() -> None:
    assert _load("B_answer.json").seed is None  # Fireworks lists no `seed`
    assert _load("D_answer.json").temperature is None  # Anthropic lists neither
    assert _load("D_answer.json").seed is None
    assert _load("F_answer.json").temperature is None  # OpenAI lists no `temperature`
