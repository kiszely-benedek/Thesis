"""The two corpus-dependent prompt inputs that are data, not code, on a v2 corpus (plan section 2).

On v2 plants the CLASS_NAME answer list and the Cypher schema text come from the corpus's own load
plan. They are hashed into the freeze file so that the prompt a model sees is pinned together with
the questions, even though the code that builds it did not change.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.graph.schema import V1_NODE_CLASSES
from plantgraph.qa.class_vocabulary import answer_class_names
from plantgraph.qa.corpus import load_corpus_artifacts
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.store.neo4j_plan import build_load_plan


class PromptInputs(BaseModel):
    """Hashes of one corpus's class list and Cypher schema text."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    n_class_names: int
    class_names_sha256: str
    schema_text_sha256: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prompt_inputs_of(corpus_id: str, ingest_json: Path) -> PromptInputs:
    """Rebuild the corpus and hash its class list (as the final step lists it) and schema text.

    The schema text is the plant profile's, which is what the Cypher tier is given.
    """
    artifacts = load_corpus_artifacts(corpus_id, ingest_json)
    names = answer_class_names(artifacts.generator_config, artifacts.load_plan)
    listed = sorted(V1_NODE_CLASSES if names is None else names)
    plant_plan = build_load_plan(
        corpus_id, artifacts.localized_sheets, artifacts.resolution, profile="plant"
    )
    return PromptInputs(
        corpus_id=corpus_id,
        n_class_names=len(listed),
        class_names_sha256=_sha256(", ".join(listed)),
        schema_text_sha256=_sha256(build_schema_text(plant_plan)),
    )


def write_prompt_inputs(out: Path, items: list[PromptInputs]) -> None:
    """Write the hashes as a JSON list (sorted keys, so the file hashes the same every run)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json") for item in items]
    out.write_bytes((json.dumps(payload, indent=1, sort_keys=True) + "\n").encode("utf-8"))
