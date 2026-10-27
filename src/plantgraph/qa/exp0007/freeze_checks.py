"""Checks that the frozen inputs are the ones the sealed run used (gate S0-b).

The two pin files and two parameter files of the tiers live in `data/runs/sealed/inputs/` and are
hashed in `F1.sha256`; the cascade policy names each tier's model pin by hash. This module checks
the link between the two without any model call.
"""

from __future__ import annotations

import json
from pathlib import Path

from plantgraph.llm.models import ModelPin
from plantgraph.qa.cascade.policy import POLICIES_DIR, load_policy

#: Policy tier name -> the pin file in the inputs directory.
TIER_PIN_FILES = {
    "cypher-luna": "pin_cypher_luna_low.json",
    "agent-luna": "pin_agent_luna_final_high.json",
}
PRIMARY_POLICY = "cascade_v3.json"


def pins_match_policy(inputs_dir: Path, policies_dir: Path = POLICIES_DIR) -> list[str]:
    """Problems found comparing each tier's pin file hash with the primary policy (empty = ok)."""
    policy = load_policy(policies_dir / PRIMARY_POLICY)
    problems = []
    for tier in policy.tiers:
        pin_file = inputs_dir / TIER_PIN_FILES[tier.name]
        found = ModelPin.model_validate_json(pin_file.read_text(encoding="utf-8")).pin_hash()
        if found != tier.pin_sha256:
            problems.append(
                f"{tier.name}: {pin_file} hashes to {found}, policy has {tier.pin_sha256}"
            )
    return problems


def ingest_problems(ingest_json: Path, corpus_id: str) -> list[str]:
    """What is wrong with a fresh `--check` ingest: wrong id, failed round trip, imperfect identity.

    G1 is `resolve(split(plant)) == plant`; S16 is identity precision = recall = 1.0 (a corpus
    with no duplicated item has no identity pairs at all, so those two numbers are then absent).
    """
    record = json.loads(ingest_json.read_text(encoding="utf-8"))
    problems = []
    if record.get("corpus_id") != corpus_id:
        problems.append(f"corpus_id is {record.get('corpus_id')!r}, expected {corpus_id!r}")
    if record.get("gate_equal") is not True:
        problems.append(f"gate_equal is {record.get('gate_equal')!r}, expected True (G1)")
    identity = record.get("resolution_score", {}).get("identity", {})
    for name in ("precision", "recall"):
        value = identity.get(name)
        empty = value is None and not any(
            identity.get(k) for k in ("true_positives", "false_positives", "false_negatives")
        )
        if value != 1.0 and not empty:
            problems.append(f"identity {name} is {value!r}, expected 1.0 (S16)")
    return problems


def files_equal(left: Path, right: Path) -> bool:
    """Byte equality of two files (`cmp`)."""
    return left.read_bytes() == right.read_bytes()
