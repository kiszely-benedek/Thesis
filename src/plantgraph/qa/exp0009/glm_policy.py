"""The cascade policy of the GLM comparison arm: `cascade_v4_iso` with GLM's two tier pins.

A **tier pin** is the exact model configuration a cascade tier is checked against: the offline
evaluation refuses a run whose answer pin hashes differently from its tier's
(`qa/cascade/checks.py`).
`cascade_v4_iso` names the GPT-6 Luna pins, so the GLM runs of stage P1g are refused by it. The
rules, tier names and strategies are the frozen policy's; only the two pin hashes are replaced,
built in code the way `v2tb.policy_b` builds B's policy, so the two cannot drift apart.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.models import CascadePolicy
from plantgraph.qa.cascade.policy import V2T_POLICIES_DIR, load_policy

A2_POLICY_NAME = "cascade_v4_iso"
GLM_POLICY_NAME = "cascade_v4_iso_glm"
INPUTS = Path(__file__).resolve().parents[4] / "data" / "runs" / "exp0009" / "inputs"
#: tier index in the policy (Cypher first, agent second) -> its GLM pin file in `inputs/`
GLM_PIN_FILES = ("pin_cypher_glm_fireworks_low.json", "pin_agent_glm_fireworks_high.json")


def glm_pin_hash(file_name: str, inputs: Path = INPUTS) -> str:
    """`ModelPin.pin_hash()` of one pin file of the inputs folder."""
    text = (inputs / file_name).read_text(encoding="utf-8")
    return ModelPin.model_validate_json(text).pin_hash()


@cache
def policy_glm() -> CascadePolicy:
    """`cascade_v4_iso` under the name `cascade_v4_iso_glm`, its tiers pinned to GLM.

    Raises:
        ValueError: the frozen policy does not have exactly the two tiers the pins are for.
    """
    policy = load_policy(V2T_POLICIES_DIR / f"{A2_POLICY_NAME}.json")
    if len(policy.tiers) != len(GLM_PIN_FILES):
        raise ValueError(
            f"expected {len(GLM_PIN_FILES)} tiers in {A2_POLICY_NAME}, found {len(policy.tiers)}"
        )
    tiers = tuple(
        tier.model_copy(update={"pin_sha256": glm_pin_hash(file_name)})
        for tier, file_name in zip(policy.tiers, GLM_PIN_FILES, strict=True)
    )
    return policy.model_copy(update={"name": GLM_POLICY_NAME, "tiers": tiers})
